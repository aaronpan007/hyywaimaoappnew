"""Chat service: start background pipelines and stream task progress from DB."""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.models.company_profile import CompanyProfile
from app.models.conversation import ConversationMessage
from app.models.task import Task, TaskLog
from app.models.user_settings import UserSettings
from app.services import task_manager
from app.services.conversation_service import create_conversation, save_message
from app.services.intent_router import classify_intent
from app.services.pipeline_service import run_pipeline
from app.services.profile_pipeline_service import extract_url, run_profile_pipeline, run_profile_quick_edit, run_supplement_pipeline
from app.services.profile_service import get_current_profile
from app.utils.sse import sse_format

logger = logging.getLogger(__name__)


class ConfigRequiredError(Exception):
    """Raised when required API keys are missing."""

    def __init__(self, missing: list[str]):
        self.missing = missing
        super().__init__(f"Missing config: {', '.join(missing)}")


def _is_generic_profile_request(message: str, params: dict) -> bool:
    """Return True when the user asks for a profile but provides no usable material."""
    if params.get("url") or params.get("images") or params.get("files"):
        return False

    text = (message or "").strip()
    if len(text) > 40:
        return False

    generic_terms = [
        "帮我",
        "请",
        "建立",
        "创建",
        "生成",
        "整理",
        "采集",
        "一个",
        "一下",
        "公司画像",
        "企业画像",
        "公司资料",
        "企业档案",
        "公司档案",
        "公司简介",
        "company profile",
    ]
    reduced = text.lower()
    for term in generic_terms:
        reduced = reduced.replace(term.lower(), "")
    reduced = reduced.strip(" ，。,.!！?？：:")
    return len(reduced) < 4


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
SSE_KEEPALIVE_INTERVAL = 15


async def start_chat(
    message: str,
    db,
    user_id: int,
    images: list[str] | None = None,
    files: list[dict] | None = None,
    conversation_id: int | None = None,
    mode: str | None = None,
) -> dict:
    """Classify a chat message and either return chat, confirm, or pipeline."""
    chat_mode = (mode or "general").strip()

    # Create conversation if not provided
    conv_id = conversation_id
    if conv_id is None:
        title = message[:20] + "..." if len(message) > 20 else message
        conv = await create_conversation(db, user_id, title, mode=chat_mode)
        conv_id = conv.id

    # Save user message
    await save_message(db, conv_id, role="user", content=message)

    pending_email_settings = await _get_pending_email_settings_state(db, conv_id, user_id)
    if pending_email_settings:
        result = await _handle_email_settings_answer(db, user_id, conv_id, message, pending_email_settings)
        return result

    intent = await classify_intent(message)
    action = intent["action"]
    params = intent["params"] if isinstance(intent.get("params"), dict) else {}
    reply = intent.get("reply", "")

    if chat_mode == "company-profile":
        action = "company_profile"
        params.setdefault("profile_mode", "update")
        reply = "好的，正在根据现有公司画像补充或修改资料..."

    # Pass uploaded images to pipeline params if present
    if images:
        params["images"] = images
        # Images only make sense for the profile pipeline; force company_profile
        # so they don't get dropped by the "chat" early return.
        action = "company_profile"
        params["profile_mode"] = "update"
        reply = "好的，正在为您补充公司画像资料..."

    # Pass uploaded files for email-craft pipeline
    if files:
        params["files"] = files

    if action == "chat":
        return {"type": "chat", "reply": reply, "conversation_id": conv_id}

    if action == "company_profile":
        if not settings.replicate_api_token:
            raise ConfigRequiredError(["replicate_api_token"])
        params.setdefault("source_text", message)
        params.setdefault("url", extract_url(message))
        if _is_generic_profile_request(message, params):
            return {
                "type": "chat",
                "reply": (
                    "可以，我先帮您准备公司画像采集。请直接发公司官网 URL，"
                    "或补充公司名称/所在地/行业、主营产品、核心优势、资质认证、典型案例、合作模式、目标客户等资料；"
                    "我会按 company-profile skill 的完整度标准整理成后续客户匹配和开发信可直接调用的销售能力档案。"
                ),
                "conversation_id": conv_id,
            }
        profile_mode = params.get("profile_mode", "create")
        if profile_mode == "update":
            current = await get_current_profile(db, user_id)
            if current is not None:
                params["existing_profile"] = current.profile_data
                params["existing_profile_id"] = current.id
            else:
                params["profile_mode"] = "create"
        result = await start_profile_pipeline(params, db, user_id)
        result["conversation_id"] = conv_id
        return result

    if action == "email_craft":
        if not settings.replicate_api_token:
            raise ConfigRequiredError(["replicate_api_token"])
        # Check company profile
        from sqlalchemy import select
        result = await db.execute(
            select(CompanyProfile).where(
                CompanyProfile.user_id == user_id,
                CompanyProfile.is_current == True,
            )
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            return {
                "type": "chat",
                "reply": "请先通过公司画像功能建立公司资料，然后再生成开发信。",
                "conversation_id": conv_id,
            }

        # Check for manually extracted lead from the message
        extracted_lead = params.get("extracted_lead")
        if isinstance(extracted_lead, dict) and extracted_lead.get("company_name"):
            # Save as a lead under a "manual" task, then auto-start pipeline
            from app.models.task import Task
            from app.models.lead import Lead as LeadModel

            manual_task = Task(
                user_id=user_id,
                type="manual",
                status="completed",
                params={"source": "chat_message"},
            )
            db.add(manual_task)
            await db.commit()
            await db.refresh(manual_task)

            lead = LeadModel(
                task_id=manual_task.id,
                company_name=extracted_lead.get("company_name", ""),
                website=extracted_lead.get("website", ""),
                country=extracted_lead.get("country", ""),
                industry=extracted_lead.get("industry", ""),
                company_role=extracted_lead.get("company_role", ""),
                contact_name=extracted_lead.get("contact_name", ""),
                email=extracted_lead.get("email", ""),
                phone=extracted_lead.get("phone", ""),
                match_score=0,
            )
            db.add(lead)
            await db.commit()
            await db.refresh(lead)

            # Auto-start pipeline with this single lead
            pipeline_params = {
                "language": params.get("language", "en"),
                "lead_count": 1,
                "lead_ids": [lead.id],
            }
            result = await start_email_craft_pipeline(pipeline_params, db, user_id)
            result["conversation_id"] = conv_id
            return result

        # Check if files are attached (user uploaded in chat input)
        uploaded_files = params.get("files") or []
        if uploaded_files:
            from app.services.lead_service import create_leads_from_files

            import_task_id, saved_count = await create_leads_from_files(db, user_id, uploaded_files)
            if saved_count == 0:
                return {
                    "type": "chat",
                    "reply": "未能从上传的文件中解析出有效的客户信息。请检查文件格式（支持 .xlsx/.csv/.docx）。",
                    "conversation_id": conv_id,
                }
            pipeline_params = {
                "language": params.get("language", "en"),
                "lead_count": saved_count,
                "source_task_id": import_task_id,
            }
            result = await start_email_craft_pipeline(pipeline_params, db, user_id)
            result["conversation_id"] = conv_id
            return result

        # Normal flow: check leads count
        lead_count = await _count_user_leads(db, user_id)
        if lead_count == 0:
            return {
                "type": "chat",
                "reply": "暂无客户线索。请先通过客户搜索功能获取线索，或上传客户资料后再生成开发信。您也可以直接告诉我客户的公司名和联系方式，我来帮您生成开发信。",
                "conversation_id": conv_id,
            }
        language = params.get("language", "en")
        # Return confirm card directing to customer list
        return {
            "type": "confirm",
            "params": {
                "confirm_type": "email_craft",
                "lead_count": lead_count,
                "language": language,
            },
            "reply": reply,
            "conversation_id": conv_id,
        }

    if action == "email_blast":
        missing_settings = await _get_missing_email_settings(db, user_id)
        if missing_settings:
            step = missing_settings[0]
            return {
                "type": "email_settings_prompt",
                "reply": _email_settings_prompt_text(step),
                "state": {
                    "step": step,
                    "missing": missing_settings,
                    "pending_action": "email_blast",
                },
                "conversation_id": conv_id,
            }
        return {
            "type": "callout",
            "callout": {
                "icon": "send",
                "title": "请选择要发送的客户",
                "summary": "发送邮件前，请先前往「客户名单」勾选要发送的客户。系统会在发送前展示确认弹窗，避免误发。",
                "stats": [],
                "actions": [
                    {"label": "前往客户名单", "variant": "filled", "type": "go-customer-list"},
                ],
            },
            "conversation_id": conv_id,
        }

    if action not in ("customer_acquisition",):
        return {
            "type": "chat",
            "reply": f"{reply}\n\n该功能正在开发中，敬请期待。",
            "conversation_id": conv_id,
        }

    missing = []
    if not settings.serper_api_key:
        missing.append("serper_api_key")
    if not settings.replicate_api_token:
        missing.append("replicate_api_token")
    if missing:
        raise ConfigRequiredError(missing)

    return {"type": "confirm", "params": params, "reply": reply, "conversation_id": conv_id}


async def _get_user_settings(db, user_id: int) -> UserSettings | None:
    result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
    return result.scalar_one_or_none()


async def _ensure_user_settings(db, user_id: int) -> UserSettings:
    user_settings = await _get_user_settings(db, user_id)
    if user_settings is None:
        user_settings = UserSettings(user_id=user_id)
        db.add(user_settings)
        await db.flush()
    return user_settings


async def _get_missing_email_settings(db, user_id: int) -> list[str]:
    user_settings = await _get_user_settings(db, user_id)
    missing = []
    if user_settings is None or not (user_settings.sender_name or "").strip():
        missing.append("sender_name")
    if user_settings is None or not (user_settings.from_email_prefix or "").strip():
        missing.append("from_email_prefix")
    return missing


def _email_settings_prompt_text(step: str) -> str:
    if step == "sender_name":
        return "发送邮件需要先配置发件信息。请问客户收到邮件时看到的发件人名称是什么？例如：张经理、Lisa from GMLight。"
    if step == "reply_to_email":
        return "好的。客户回复邮件时，您希望收到哪个邮箱？也可以输入“跳过”，不单独设置回复邮箱。"
    if step == "from_email_prefix":
        domain = settings.mail_domain.strip().lstrip("@") or "clientconnet.com"
        return f"最后，请设置发件邮箱前缀。比如输入 sales，系统会生成 sales@{domain}。"
    return "请补充邮箱发送配置。"


def _is_valid_email_address(value: str) -> bool:
    import re

    return bool(re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", value.strip()))


def _clean_email_prefix(value: str) -> str:
    import re

    text = value.strip()
    if "@" in text:
        text = text.split("@", 1)[0]
    text = re.sub(r"[^a-zA-Z0-9._-]", "", text).strip("._-")
    return text.lower()


async def _get_pending_email_settings_state(db, conversation_id: int, user_id: int) -> dict | None:
    result = await db.execute(
        select(ConversationMessage)
        .where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.role == "assistant",
            ConversationMessage.message_type == "email_settings_prompt",
        )
        .order_by(ConversationMessage.sort_order.desc())
        .limit(1)
    )
    message = result.scalar_one_or_none()
    if message is None or not isinstance(message.extra_data, dict):
        return None
    if message.extra_data.get("status") != "pending":
        return None
    if message.extra_data.get("pending_action") == "email_blast":
        missing = await _get_missing_email_settings(db, user_id)
        if not missing:
            message.extra_data = {**message.extra_data, "status": "completed"}
            await db.commit()
            return None
    return message.extra_data


async def _handle_email_settings_answer(
    db,
    user_id: int,
    conversation_id: int,
    answer: str,
    state: dict,
) -> dict:
    step = state.get("step")
    user_settings = await _ensure_user_settings(db, user_id)
    value = answer.strip()

    if step == "sender_name":
        if len(value) < 2:
            return {
                "type": "email_settings_prompt",
                "reply": "发件人名称有点短，请输入客户能识别的名称，例如：张经理、Lisa from GMLight。",
                "state": {**state, "step": "sender_name", "status": "pending"},
                "conversation_id": conversation_id,
            }
        user_settings.sender_name = value
    elif step == "reply_to_email":
        if value in {"", "跳过", "不填", "无", "none", "None", "skip"}:
            user_settings.reply_to_email = ""
        elif not _is_valid_email_address(value):
            return {
                "type": "email_settings_prompt",
                "reply": "这个邮箱格式看起来不太对，请输入一个有效邮箱，例如 name@example.com。",
                "state": {**state, "step": "reply_to_email", "status": "pending"},
                "conversation_id": conversation_id,
            }
        else:
            user_settings.reply_to_email = value
    elif step == "from_email_prefix":
        prefix = _clean_email_prefix(value)
        if not prefix:
            return {
                "type": "email_settings_prompt",
                "reply": "发件邮箱前缀不能为空。请只输入邮箱 @ 前面的部分，例如 sales 或 lisa。",
                "state": {**state, "step": "from_email_prefix", "status": "pending"},
                "conversation_id": conversation_id,
            }
        user_settings.from_email_prefix = prefix

    await db.commit()
    await db.refresh(user_settings)

    missing = await _get_missing_email_settings(db, user_id)
    if missing:
        next_step = missing[0]
        return {
            "type": "email_settings_prompt",
            "reply": _email_settings_prompt_text(next_step),
            "state": {
                **state,
                "step": next_step,
                "missing": missing,
                "status": "pending",
            },
            "conversation_id": conversation_id,
        }

    user_settings.confirmed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user_settings)
    await _complete_pending_email_settings_state(db, conversation_id)

    domain = settings.mail_domain.strip().lstrip("@")
    from_email = f"{user_settings.from_email_prefix}@{domain}" if domain else user_settings.from_email_prefix
    callout = {
        "icon": "settings",
        "title": "邮箱配置完成",
        "summary": "现在可以继续选择客户并发送开发信。",
        "stats": [
            f"发件人：{user_settings.sender_name}",
            *([f"回复邮箱：{user_settings.reply_to_email}"] if (user_settings.reply_to_email or "").strip() else []),
            f"发件邮箱：{from_email}",
        ],
        "actions": [
            {"label": "前往客户名单", "variant": "filled", "type": "go-customer-list"},
        ],
    }
    return {"type": "callout", "callout": callout, "conversation_id": conversation_id}


async def _complete_pending_email_settings_state(db, conversation_id: int) -> None:
    result = await db.execute(
        select(ConversationMessage)
        .where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.role == "assistant",
            ConversationMessage.message_type == "email_settings_prompt",
        )
        .order_by(ConversationMessage.sort_order.desc())
        .limit(1)
    )
    message = result.scalar_one_or_none()
    if message is None or not isinstance(message.extra_data, dict):
        return
    message.extra_data = {**message.extra_data, "status": "completed"}
    await db.commit()


def _task_start_callout(task: Task) -> dict:
    params = task.params or {}
    if task.type == "company-profile":
        profile_mode = params.get("profile_mode", "create")
        if profile_mode == "update":
            has_url = bool(params.get("url"))
            if not has_url:
                ep = params.get("existing_profile") or {}
                ep_name = ep.get("company_name", "") if isinstance(ep, dict) else ""
                return {
                    "icon": "building2",
                    "title": "正在修改公司画像",
                    "summary": "根据您的修改意见更新画像",
                    "stats": [f"画像: {ep_name}"] if ep_name else [],
                    "actions": [
                        {"label": "查看公司画像", "variant": "outlined", "type": "view-profile"},
                    ],
                }
            return {
                "icon": "building2",
                "title": "正在补充公司画像",
                "summary": "在现有画像基础上增量更新资料",
                "stats": [f"官网: {params.get('url') or '未提供'}"],
                "actions": [
                    {"label": "查看公司画像", "variant": "outlined", "type": "view-profile"},
                ],
            }
        return {
            "icon": "building2",
            "title": "开始公司画像采集",
            "summary": "正在整理您的公司资料并生成销售能力档案",
            "stats": [f"官网: {params.get('url') or '未提供'}"],
            "actions": [
                {"label": "查看公司画像", "variant": "outlined", "type": "view-profile"},
            ],
        }

    if task.type == "email-craft":
        lead_count = params.get("lead_count", 0)
        language = params.get("language", "en")
        lang_text = "中文" if language == "cn" else "英文"
        return {
            "icon": "pen-line",
            "title": "正在生成开发信",
            "summary": f"正在为 {lead_count} 条线索生成{lang_text}开发信...",
            "stats": [f"线索: {lead_count} 条", f"语言: {lang_text}"],
            "actions": [],
        }

    if task.type == "email-blast":
        params = task.params or {}
        selected = len(params.get("lead_ids") or [])
        return {
            "icon": "send",
            "title": "正在发送邮件",
            "summary": "正在批量发送开发信...",
            "stats": [
                f"已选: {selected} 个客户",
            ],
            "actions": [],
        }

    return {
        "icon": "search",
        "title": "开始客户搜索",
        "summary": f"正在搜索{params.get('country', '')}的{params.get('industry', '')}...",
        "stats": [f"目标: {params.get('num', 20)} 家客户"],
        "actions": [
            {"label": "查看客户列表", "variant": "outlined", "type": "view-list"},
            {"label": "导出 Excel", "variant": "filled", "type": "download-excel"},
        ],
    }


def _task_completed_callout(task: Task) -> dict:
    summary = task.result_summary or {}
    if task.type == "company-profile":
        completeness = float(summary.get("completeness") or 0)
        if completeness > 1:
            completeness = completeness / 100
        completeness = max(0.0, min(completeness, 1.0))
        profile_mode = summary.get("profileMode", "create")
        title = "公司画像已更新" if profile_mode == "update" else "公司画像已生成"
        return {
            "icon": "building2",
            "title": title,
            "summary": summary.get("companyName") or "企业能力档案已保存",
            "stats": [
                f"产品线 {summary.get('products', 0)} 个",
                f"案例 {summary.get('cases', 0)} 个",
                f"完整度 {completeness:.0%}",
            ],
            "actions": [
                {"label": "查看公司画像", "variant": "filled", "type": "view-profile"},
            ],
        }

    if task.type == "email-craft":
        generated = summary.get("generated", 0)
        failed = summary.get("failed", 0)
        from_upload = summary.get("fromUpload", 0)
        stats = [f"成功生成 {generated} 封开发信"]
        if failed > 0:
            stats.append(f"失败 {failed} 封")
        if from_upload > 0:
            stats.append(f"含 {from_upload} 条上传线索")
        return {
            "icon": "pen-line",
            "title": "开发信生成完成",
            "stats": stats,
            "actions": [
                {"label": "查看邮件", "variant": "outlined", "type": "view-emails"},
                {"label": "导出 Excel", "variant": "filled", "type": "download-emails"},
            ],
        }

    if task.type == "email-blast":
        sent = summary.get("sent", 0)
        failed = summary.get("failed", 0)
        skipped = summary.get("skipped", 0)
        return {
            "icon": "send",
            "title": "批量发送完成",
            "stats": [
                f"成功 {sent} 封",
                f"失败 {failed} 封",
                f"跳过 {skipped} 封",
            ],
            "actions": [
                {"label": "前往客户名单", "variant": "filled", "type": "go-customer-list"},
            ],
        }

    return {
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
    }


def _task_cancelled_callout() -> dict:
    return {
        "icon": "alert-circle",
        "title": "任务已取消",
        "summary": "该任务已被用户手动停止",
        "stats": [],
        "actions": [],
    }


def _task_failed_callout(task: Task) -> dict:
    summary = task.result_summary or {}
    if task.type == "company-profile":
        title = "画像采集失败"
    elif task.type == "email-craft":
        title = "开发信生成失败"
    elif task.type == "email-blast":
        title = "邮件发送失败"
    else:
        title = "搜索失败"
    return {
        "icon": "alert-circle",
        "title": title,
        "summary": summary.get("error", "未知错误"),
        "stats": [],
        "actions": [],
    }


def _timeline_title(task_type: str) -> str:
    if task_type == "customer-acquisition":
        return "客户搜索"
    if task_type == "company-profile":
        return "公司画像"
    if task_type == "email-craft":
        return "开发信撰写"
    if task_type == "email-blast":
        return "邮件发送"
    return task_type


def _task_timeline_data(task: Task, logs: list[TaskLog]) -> dict:
    status = task.status
    if status not in ("completed", "failed", "cancelled"):
        status = "running"
    return {
        "taskType": task.type,
        "title": _timeline_title(task.type),
        "status": status,
        "steps": [
            {
                "number": log.step_number,
                "name": log.step_name,
                "status": log.status,
                "message": log.message,
                "progress": log.progress,
            }
            for log in logs
        ],
    }


async def _save_task_history_once(
    db,
    conversation_id: int | None,
    task: Task,
    logs: list[TaskLog],
    callout: dict,
) -> None:
    if conversation_id is None:
        return

    marker = f"task:{task.id}"
    result = await db.execute(
        select(ConversationMessage.id).where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.role == "assistant",
            ConversationMessage.content.in_([f"{marker}:timeline", f"{marker}:callout"]),
        )
    )
    existing = set(result.scalars().all())
    if existing:
        return

    await save_message(
        db,
        conversation_id,
        role="assistant",
        content=f"{marker}:timeline",
        message_type="timeline",
        extra_data=_task_timeline_data(task, logs),
    )
    saved_callout = {**callout, "taskId": task.id}
    await save_message(
        db,
        conversation_id,
        role="assistant",
        content=f"{marker}:callout",
        message_type="callout",
        extra_data=saved_callout,
    )


async def stream_task_progress(task_id: int, db, conversation_id: int | None = None) -> AsyncGenerator[str, None]:
    """Poll task_logs from DB and push SSE events."""
    yield sse_format("thinking", {})

    task = await db.get(Task, task_id)
    if task is None:
        yield sse_format("done", {"taskId": task_id, "conversationId": conversation_id})
        return

    if task.status in ("completed", "failed", "cancelled"):
        result = await db.execute(
            select(TaskLog)
            .where(TaskLog.task_id == task_id)
            .order_by(TaskLog.step_number, TaskLog.id)
        )
        final_logs = list(result.scalars().all())
        for log in final_logs:
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

        if task.status == "completed":
            callout = _task_completed_callout(task)
        elif task.status == "cancelled":
            callout = _task_cancelled_callout()
        else:
            callout = _task_failed_callout(task)

        await _save_task_history_once(db, conversation_id, task, final_logs, callout)

        yield sse_format(
            "result",
            {"task_id": task_id, "type": "callout", "callout": callout},
        )
        yield sse_format("done", {"taskId": task_id, "conversationId": conversation_id})
        return

    yield sse_format(
        "result",
        {"task_id": task_id, "type": "callout", "callout": _task_start_callout(task)},
    )
    yield sse_format(
        "pipeline_started",
        {
            "taskId": task_id,
            "type": task.type,
            "params": task.params,
        },
    )

    seen_log_snapshots: dict[int, tuple[str, str, str, int]] = {}
    last_log_time = time.monotonic()
    last_keepalive_time = time.monotonic()
    while True:
        result = await db.execute(
            select(TaskLog)
            .where(TaskLog.task_id == task_id)
            .order_by(TaskLog.step_number, TaskLog.id)
            .execution_options(populate_existing=True)
        )
        logs = result.scalars().all()

        emitted_update = False
        for log in logs:
            snapshot = (log.step_name, log.status, log.message, log.progress)
            if seen_log_snapshots.get(log.id) == snapshot:
                continue
            seen_log_snapshots[log.id] = snapshot
            emitted_update = True
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

        if emitted_update:
            last_log_time = time.monotonic()
            last_keepalive_time = time.monotonic()

        await db.refresh(task)
        if task.status == "cancelled":
            yield sse_format("task_cancelled", {"taskId": task_id})
            yield sse_format(
                "result",
                {
                    "task_id": task_id,
                    "type": "callout",
                    "callout": _task_cancelled_callout(),
                },
            )
            yield sse_format("done", {"taskId": task_id, "conversationId": conversation_id})
            break

        if task.status in ("completed", "failed"):
            result = await db.execute(
                select(TaskLog)
                .where(TaskLog.task_id == task_id)
                .order_by(TaskLog.step_number, TaskLog.id)
            )
            final_logs = list(result.scalars().all())
            callout = (
                _task_completed_callout(task)
                if task.status == "completed"
                else _task_failed_callout(task)
            )
            await _save_task_history_once(db, conversation_id, task, final_logs, callout)
            yield sse_format(
                "result",
                {"task_id": task_id, "type": "callout", "callout": callout},
            )
            yield sse_format("done", {"taskId": task_id, "conversationId": conversation_id})
            break

        if time.monotonic() - last_log_time > task_manager.HEARTBEAT_TIMEOUT:
            logger.warning("SSE stale timeout for task %d", task_id)
            yield sse_format("task_stale", {"taskId": task_id})
            stale_task = task
            stale_task.result_summary = {"error": "任务长时间未更新，已自动标记为失败"}
            yield sse_format(
                "result",
                {
                    "task_id": task_id,
                    "type": "callout",
                    "callout": _task_failed_callout(stale_task),
                },
            )
            yield sse_format("done", {"taskId": task_id, "conversationId": conversation_id})
            break

        if time.monotonic() - last_keepalive_time > SSE_KEEPALIVE_INTERVAL:
            last_keepalive_time = time.monotonic()
            yield ": keepalive\n\n"

        await asyncio.sleep(0.5)


async def config_error_stream(missing: list[str], conversation_id: int | None = None) -> AsyncGenerator[str, None]:
    """SSE stream for config-required error."""
    yield sse_format("thinking", {})
    yield sse_format(
        "config_required",
        {
            "missing_fields": missing,
            "suggestion": "请先在设置页面配置 API 密钥后再使用该功能。",
        },
    )
    done_data: dict = {}
    if conversation_id is not None:
        done_data["conversationId"] = conversation_id
    yield sse_format("done", done_data)


async def confirm_params_stream(
    params: dict,
    reply: str,
    conversation_id: int | None = None,
    db=None,
) -> AsyncGenerator[str, None]:
    """SSE stream for customer acquisition parameter confirmation."""
    yield sse_format("thinking", {})
    confirm_data = {
        "industry": params.get("industry", ""),
        "country": params.get("country", ""),
        "keywords": params.get("keywords", []),
        "num": params.get("num", 20),
        "reply": reply,
    }
    yield sse_format("confirm_params", confirm_data)
    if conversation_id is not None and db is not None:
        await save_message(
            db,
            conversation_id,
            role="assistant",
            content=reply,
            message_type="confirm_params",
            extra_data=confirm_data,
        )
    done_data: dict = {}
    if conversation_id is not None:
        done_data["conversationId"] = conversation_id
    yield sse_format("done", done_data)


async def start_pipeline(params: dict, db, user_id: int) -> dict:
    """Create a customer-acquisition task after user confirms params."""
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

    pipeline_task = asyncio.create_task(run_pipeline(task.id, user_id, intent))
    task_manager.register_task(task.id, pipeline_task)

    return {"type": "pipeline", "task_id": task.id}


async def start_profile_pipeline(params: dict, db, user_id: int) -> dict:
    """Create a company-profile task and launch its independent pipeline."""
    intent = {
        "action": "company_profile",
        "params": params,
        "reply": "",
    }
    task = Task(
        user_id=user_id,
        type="company-profile",
        status="running",
        params=params,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    profile_mode = params.get("profile_mode", "create")
    has_url = bool(params.get("url"))
    if profile_mode == "update" and not has_url:
        pipeline_func = run_profile_quick_edit
    elif profile_mode == "update":
        pipeline_func = run_supplement_pipeline
    else:
        pipeline_func = run_profile_pipeline
    pipeline_task = asyncio.create_task(pipeline_func(task.id, user_id, intent))
    task_manager.register_task(task.id, pipeline_task)

    return {"type": "pipeline", "task_id": task.id}


async def chat_reply_stream(reply: str, conversation_id: int | None = None, db=None) -> AsyncGenerator[str, None]:
    """SSE stream for a simple chat reply."""
    yield sse_format("thinking", {})
    callout = {
        "icon": "message-circle",
        "title": "",
        "summary": reply,
        "stats": [],
        "actions": [],
    }
    yield sse_format(
        "result",
        {"type": "callout", "callout": callout},
    )
    # Save assistant message to DB
    if conversation_id is not None and db is not None:
        await save_message(db, conversation_id, role="assistant", content=reply, message_type="callout", extra_data=callout)
    done_data: dict = {}
    if conversation_id is not None:
        done_data["conversationId"] = conversation_id
    yield sse_format("done", done_data)


async def callout_reply_stream(callout: dict, conversation_id: int | None = None, db=None) -> AsyncGenerator[str, None]:
    """SSE stream for a direct assistant callout."""
    yield sse_format("thinking", {})
    yield sse_format("result", {"type": "callout", "callout": callout})
    if conversation_id is not None and db is not None:
        await save_message(
            db,
            conversation_id,
            role="assistant",
            content=callout.get("summary", ""),
            message_type="callout",
            extra_data=callout,
        )
    done_data: dict = {}
    if conversation_id is not None:
        done_data["conversationId"] = conversation_id
    yield sse_format("done", done_data)


async def email_settings_prompt_stream(
    reply: str,
    state: dict,
    conversation_id: int | None = None,
    db=None,
) -> AsyncGenerator[str, None]:
    """SSE stream for one step of email settings collection."""
    yield sse_format("thinking", {})
    yield sse_format(
        "result",
        {
            "type": "callout",
            "callout": {
                "icon": "settings",
                "title": "邮箱配置",
                "summary": reply,
                "stats": [],
                "actions": [],
            },
        },
    )
    if conversation_id is not None and db is not None:
        await save_message(
            db,
            conversation_id,
            role="assistant",
            content=reply,
            message_type="email_settings_prompt",
            extra_data={**state, "status": "pending"},
        )
    done_data: dict = {}
    if conversation_id is not None:
        done_data["conversationId"] = conversation_id
    yield sse_format("done", done_data)


# ─── Email-craft specific functions ──────────────────────────────────

async def _count_user_leads(db, user_id: int) -> int:
    """Count total leads for a user across all their tasks."""
    from app.models.lead import Lead
    from sqlalchemy import select, func

    task_ids_query = select(Task.id).where(Task.user_id == user_id)
    result = await db.execute(
        select(func.count()).select_from(Lead).where(Lead.task_id.in_(task_ids_query))
    )
    return result.scalar() or 0


async def confirm_email_craft_stream(
    params: dict,
    reply: str,
    conversation_id: int | None = None,
    db=None,
) -> AsyncGenerator[str, None]:
    """SSE stream for email-craft confirmation card."""
    yield sse_format("thinking", {})
    confirm_data = {
        "confirm_type": "email_craft",
        "lead_count": params.get("lead_count", 0),
        "language": params.get("language", "en"),
        "reply": reply,
    }
    yield sse_format("confirm_params", confirm_data)
    if conversation_id is not None and db is not None:
        await save_message(
            db,
            conversation_id,
            role="assistant",
            content=reply,
            message_type="confirm_email_craft",
            extra_data={
                "confirmType": "email_craft",
                "leadCount": params.get("lead_count", 0),
                "language": params.get("language", "en"),
                "reply": reply,
            },
        )
    done_data: dict = {}
    if conversation_id is not None:
        done_data["conversationId"] = conversation_id
    yield sse_format("done", done_data)


async def start_email_craft_pipeline(params: dict, db, user_id: int) -> dict:
    """Create an email-craft task and launch its pipeline."""
    from app.services.email_craft_pipeline_service import run_email_craft_pipeline

    intent = {
        "action": "email_craft",
        "params": params,
        "reply": "",
    }
    task = Task(
        user_id=user_id,
        type="email-craft",
        status="running",
        params={
            "language": params.get("language", "en"),
            "lead_count": params.get("lead_count", 0),
            "lead_ids": params.get("lead_ids") or [],
            "source_task_id": params.get("source_task_id"),
        },
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    pipeline_task = asyncio.create_task(run_email_craft_pipeline(task.id, user_id, intent))
    task_manager.register_task(task.id, pipeline_task)

    return {"type": "pipeline", "task_id": task.id}


async def start_email_blast_pipeline(params: dict, db, user_id: int) -> dict:
    """Create an email-blast task and launch its pipeline."""
    from app.services.email_blast_pipeline_service import run_email_blast_pipeline

    intent = {
        "action": "email_blast",
        "params": params,
        "reply": "",
    }
    task = Task(
        user_id=user_id,
        type="email-blast",
        status="running",
        params={
            "lead_ids": params.get("lead_ids") or [],
            "delay_min": params.get("delay_min", 60),
            "delay_max": params.get("delay_max", 120),
            "daily_limit": params.get("daily_limit", 50),
            "dry_run": False,
            "send_mode": params.get("send_mode", "auto"),
        },
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    pipeline_task = asyncio.create_task(run_email_blast_pipeline(task.id, user_id, intent))
    task_manager.register_task(task.id, pipeline_task)

    return {"type": "pipeline", "task_id": task.id}
