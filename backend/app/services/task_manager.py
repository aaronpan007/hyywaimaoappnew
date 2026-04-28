"""In-memory task lifecycle manager.

Tracks running asyncio.Tasks, heartbeats, and provides cancel/stale cleanup.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.models.task import Task

logger = logging.getLogger(__name__)

HEARTBEAT_TIMEOUT = 300  # 5 minutes

# ── In-memory state ──────────────────────────────────────────────────
running_tasks: dict[int, asyncio.Task] = {}
task_heartbeats: dict[int, float] = {}


# ── Public API ───────────────────────────────────────────────────────

def register_task(task_id: int, atask: asyncio.Task) -> None:
    """Register an asyncio.Task so it can be cancelled later."""
    running_tasks[task_id] = atask
    task_heartbeats[task_id] = time.monotonic()


def remove_task(task_id: int) -> None:
    """Remove a task from tracking (called when pipeline finishes)."""
    running_tasks.pop(task_id, None)
    task_heartbeats.pop(task_id, None)


def update_heartbeat(task_id: int) -> None:
    """Refresh the heartbeat timestamp for a running task."""
    if task_id in running_tasks:
        task_heartbeats[task_id] = time.monotonic()


async def cancel_task(task_id: int, db) -> bool:
    """Cancel a running task: stop asyncio.Task + update DB."""
    atask = running_tasks.get(task_id)
    if atask is not None:
        atask.cancel()

    now = datetime.now(timezone.utc)
    await db.execute(
        update(Task)
        .where(Task.id == task_id)
        .values(status="cancelled", ended_at=now, cancelled=True)
    )
    await db.commit()
    remove_task(task_id)

    logger.info("Task %d cancelled", task_id)
    return True


async def mark_stale_tasks(db) -> int:
    """Find tasks with heartbeat older than HEARTBEAT_TIMEOUT and mark failed.

    Returns the number of tasks marked stale.
    """
    now = time.monotonic()
    stale_ids = [
        tid for tid, ts in task_heartbeats.items()
        if now - ts > HEARTBEAT_TIMEOUT
    ]

    if not stale_ids:
        return 0

    for task_id in stale_ids:
        await db.execute(
            update(Task)
            .where(Task.id == task_id)
            .values(
                status="failed",
                ended_at=datetime.now(timezone.utc),
                result_summary={"error": "任务超时（heartbeat timeout）"},
            )
        )
        # Also cancel the asyncio.Task if still alive
        atask = running_tasks.get(task_id)
        if atask is not None:
            atask.cancel()
        remove_task(task_id)
        logger.warning("Task %d marked as stale (heartbeat timeout)", task_id)

    await db.commit()
    return len(stale_ids)


async def cleanup_on_startup(db) -> int:
    """Mark all status='running' tasks as failed (zombie cleanup on restart).

    Returns the number of tasks cleaned up.
    """
    result = await db.execute(
        update(Task)
        .where(Task.status == "running")
        .values(
            status="failed",
            ended_at=datetime.now(timezone.utc),
            result_summary={"error": "服务重启，任务中断"},
        )
    )
    await db.commit()
    count = result.rowcount
    if count:
        logger.warning("Cleaned up %d zombie task(s) on startup", count)
    return count
