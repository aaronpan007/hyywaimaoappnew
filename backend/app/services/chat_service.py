"""Chat service: start background pipeline + stream task progress from DB."""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator

from sqlalchemy import select

from app.config import settings
from app.models.task import Task, TaskLog
from app.services import task_manager
from app.services.intent_router import classify_intent
from app.services.pipeline_service import run_pipeline
from app.utils.sse import sse_format

logger = logging.getLogger(__name__)


class ConfigRequiredError(Exception):
    """Raised when required API keys are missing."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"Missing config: {', '.join(missing)}")


async def start_chat(
    message: str, db, user_id: int
) -> dict:
    """Classify intent and either start a pipeline or return a chat reply.

    Returns dict with either:
      - {"type": "pipeline", "task_id": int} — a pipeline task was created
      - {"type": "chat", "reply": str} — no pipeline, just an AI reply
    """
    intent = await classify_intent(message)
    action = intent["action"]
    params = intent["params"]
    reply = intent["reply"]

    # Chat action: no pipeline needed
    if action == "chat":
        return {"type": "chat", "reply": reply}

    # Future actions not yet implemented
    if action not in ("customer_acquisition",):
        return {
            "type": "chat",
            "reply": f"{reply}\n\n该功能正在开发中，敬请期待。",
        }

    # customer_acquisition: return confirm params (user confirms before pipeline)
    missing = []
    if not settings.serper_api_key:
        missing.append("serper_api_key")
    if not settings.replicate_api_token:
        missing.append("replicate_api_token")
    if missing:
        raise ConfigRequiredError(missing)

    return {"type": "confirm", "params": params, "reply": reply}


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


async def stream_task_progress(
    task_id: int, db
) -> AsyncGenerator[str, None]:
    """Poll task_logs from DB and push SSE events.

    This can be called for a new task or to reconnect to a running task.
    """
    last_log_id = 0

    # Emit thinking
    yield sse_format("thinking", {})

    # Initial result callout
    task = await db.get(Task, task_id)
    if task is None:
        yield sse_format("done", {"taskId": task_id})
        return

    # Fast path: if task is already done/failed/cancelled, skip polling
    if task.status in ("completed", "failed", "cancelled"):
        # Still emit existing logs
        result = await db.execute(
            select(TaskLog)
            .where(TaskLog.task_id == task_id)
            .order_by(TaskLog.id)
        )
        for log in result.scalars().all():
            yield sse_format(
                "step_update",
                {
                    "taskId": task_id,
                    "step": log.step_number,
                    "name": log.step_name,
                    "status": log.status,
                    "progress": log.progress,
                    "message": log.message,
                },
            )
        summary = task.result_summary or {}
        if task.status == "completed":
            yield sse_format(
                "result",
                {
                    "task_id": task_id,
                    "type": "callout",
                    "callout": {
                        "icon": "search",
                        "title": "客户搜索完成",
                        "stats": [
                            f"找到 {summary.get('found', 0)} 家潜在客户",
                            f"平均匹配度 {summary.get('avgScore', 0):.0f}%",
                        ],
                        "actions": [
                            {"label": "查看客户列表", "variant": "outlined", "type": "view-list"},
                            {"label": "导出 Excel", "variant": "filled", "type": "download-excel"},
                        ],
                    },
                },
            )
        elif task.status == "cancelled":
            yield sse_format(
                "result",
                {
                    "task_id": task_id,
                    "type": "callout",
                    "callout": {
                        "icon": "alert-circle",
                        "title": "任务已取消",
                        "summary": "该任务已被用户手动停止",
                        "stats": [],
                        "actions": [],
                    },
                },
            )
        else:
            yield sse_format(
                "result",
                {
                    "task_id": task_id,
                    "type": "callout",
                    "callout": {
                        "icon": "alert-circle",
                        "title": "搜索失败",
                        "summary": summary.get("error", "未知错误"),
                        "stats": [],
                        "actions": [],
                    },
                },
            )
        yield sse_format("done", {"taskId": task_id})
        return

    params = task.params or {}
    yield sse_format(
        "result",
        {
            "task_id": task_id,
            "type": "callout",
            "callout": {
                "icon": "search",
                "title": "开始客户搜索",
                "summary": f"正在搜索{params.get('country', '')}的{params.get('industry', '')}...",
                "stats": [f"目标: {params.get('num', 20)} 家客户"],
                "actions": [
                    {"label": "查看客户列表", "variant": "outlined", "type": "view-list"},
                    {"label": "导出 Excel", "variant": "filled", "type": "download-excel"},
                ],
            },
        },
    )

    yield sse_format(
        "pipeline_started",
        {
            "taskId": task_id,
            "type": task.type,
            "params": task.params,
        },
    )

    # Poll loop
    last_log_time = time.monotonic()
    while True:
        # Fetch new logs
        result = await db.execute(
            select(TaskLog)
            .where(TaskLog.task_id == task_id, TaskLog.id > last_log_id)
            .order_by(TaskLog.id)
        )
        logs = result.scalars().all()

        if logs:
            last_log_time = time.monotonic()

        for log in logs:
            last_log_id = log.id
            yield sse_format(
                "step_update",
                {
                    "taskId": task_id,
                    "step": log.step_number,
                    "name": log.step_name,
                    "status": log.status,
                    "progress": log.progress,
                    "message": log.message,
                },
            )

        # Check if task is done
        await db.refresh(task)
        if task.status == "cancelled":
            yield sse_format("task_cancelled", {"taskId": task_id})
            yield sse_format(
                "result",
                {
                    "task_id": task_id,
                    "type": "callout",
                    "callout": {
                        "icon": "alert-circle",
                        "title": "任务已取消",
                        "summary": "该任务已被用户手动停止",
                        "stats": [],
                        "actions": [],
                    },
                },
            )
            yield sse_format("done", {"taskId": task_id})
            break

        if task.status in ("completed", "failed"):
            summary = task.result_summary or {}

            if task.status == "completed":
                yield sse_format(
                    "result",
                    {
                        "task_id": task_id,
                        "type": "callout",
                        "callout": {
                            "icon": "search",
                            "title": "客户搜索完成",
                            "stats": [
                                f"找到 {summary.get('found', 0)} 家潜在客户",
                                f"平均匹配度 {summary.get('avgScore', 0):.0f}%",
                            ],
                            "actions": [
                                {
                                    "label": "查看客户列表",
                                    "variant": "outlined",
                                    "type": "view-list",
                                },
                                {
                                    "label": "导出 Excel",
                                    "variant": "filled",
                                    "type": "download-excel",
                                },
                            ],
                        },
                    },
                )
            else:
                yield sse_format(
                    "result",
                    {
                        "task_id": task_id,
                        "type": "callout",
                        "callout": {
                            "icon": "alert-circle",
                            "title": "搜索失败",
                            "summary": summary.get("error", "未知错误"),
                            "stats": [],
                            "actions": [],
                        },
                    },
                )

            yield sse_format("done", {"taskId": task_id})
            break

        # Heartbeat timeout: if no new logs for 5 minutes, emit stale event
        if time.monotonic() - last_log_time > task_manager.HEARTBEAT_TIMEOUT:
            logger.warning("SSE stale timeout for task %d", task_id)
            yield sse_format("task_stale", {"taskId": task_id})
            yield sse_format(
                "result",
                {
                    "task_id": task_id,
                    "type": "callout",
                    "callout": {
                        "icon": "alert-circle",
                        "title": "任务超时",
                        "summary": "任务长时间未更新，已自动标记为失败",
                        "stats": [],
                        "actions": [],
                    },
                },
            )
            yield sse_format("done", {"taskId": task_id})
            break

        await asyncio.sleep(0.5)


async def config_error_stream(missing: list[str]) -> AsyncGenerator[str, None]:
    """SSE stream for config-required error."""
    yield sse_format("thinking", {})
    yield sse_format(
        "config_required",
        {
            "missing_fields": missing,
            "suggestion": "请先在设置页面配置 API 密钥后再使用搜索功能。",
        },
    )
    yield sse_format("done", {})


async def confirm_params_stream(params: dict, reply: str) -> AsyncGenerator[str, None]:
    """SSE stream for parameter confirmation (before pipeline starts)."""
    yield sse_format("thinking", {})
    yield sse_format(
        "confirm_params",
        {
            "industry": params.get("industry", ""),
            "country": params.get("country", ""),
            "keywords": params.get("keywords", []),
            "num": params.get("num", 20),
            "reply": reply,
        },
    )
    yield sse_format("done", {})


async def start_pipeline(
    params: dict, db, user_id: int
) -> dict:
    """Create a task and launch the pipeline after user confirms params.

    Returns {"type": "pipeline", "task_id": int}.
    """
    intent = {
        "action": "customer_acquisition",
        "params": params,
        "reply": "",
    }

    task = Task(
        user_id=user_id,
        type="customer-acquisition",
        status="running",
        params=params,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    pipeline_task = asyncio.create_task(
        run_pipeline(task.id, user_id, intent)
    )
    task_manager.register_task(task.id, pipeline_task)

    return {"type": "pipeline", "task_id": task.id}


async def chat_reply_stream(reply: str) -> AsyncGenerator[str, None]:
    """SSE stream for a simple chat reply (no pipeline)."""
    yield sse_format("thinking", {})
    yield sse_format(
        "result",
        {
            "type": "callout",
            "callout": {
                "icon": "message-circle",
                "title": "",
                "summary": reply,
                "stats": [],
                "actions": [],
            },
        },
    )
    yield sse_format("done", {})
