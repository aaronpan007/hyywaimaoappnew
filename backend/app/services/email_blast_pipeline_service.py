"""Email-blast pipeline: send prepared outreach emails.

Phase 1 implements a dry-run capable pipeline that reads pending email drafts
from PostgreSQL and streams progress through the existing task log mechanism.
Real Resend sending is wired in a later phase.
"""

import asyncio
import logging
import random
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

if sys.platform == "win32":
    import tzdata  # noqa: F401 — provide IANA timezone data on Windows

import httpx
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models.lead import Lead
from app.models.outreach_email import OutreachEmail
from app.models.task import Task, TaskLog
from app.models.user_settings import UserSettings
from app.services import task_manager

logger = logging.getLogger(__name__)

# Country name/ISO code → IANA timezone. Uses zoneinfo for automatic DST handling.
_COUNTRY_TO_TZ: dict[str, str] = {
    # --- North America ---
    "united states": "America/New_York", "us": "America/New_York", "usa": "America/New_York", "美国": "America/New_York",
    "canada": "America/Toronto", "加拿大": "America/Toronto",
    "mexico": "America/Mexico_City", "墨西哥": "America/Mexico_City",
    "guatemala": "America/Guatemala", "危地马拉": "America/Guatemala",
    "costa rica": "America/Costa_Rica", "哥斯达黎加": "America/Costa_Rica",
    "panama": "America/Panama", "巴拿马": "America/Panama",
    "cuba": "America/Havana", "古巴": "America/Havana",
    "jamaica": "America/Jamaica", "牙买加": "America/Jamaica",
    "dominican republic": "America/Santo_Domingo", "多米尼加": "America/Santo_Domingo",
    # --- South America ---
    "brazil": "America/Sao_Paulo", "巴西": "America/Sao_Paulo",
    "argentina": "America/Buenos_Aires", "阿根廷": "America/Buenos_Aires",
    "chile": "America/Santiago", "智利": "America/Santiago",
    "colombia": "America/Bogota", "哥伦比亚": "America/Bogota",
    "peru": "America/Lima", "秘鲁": "America/Lima",
    "ecuador": "America/Guayaquil", "厄瓜多尔": "America/Guayaquil",
    "venezuela": "America/Caracas", "委内瑞拉": "America/Caracas",
    # --- Western Europe ---
    "united kingdom": "Europe/London", "uk": "Europe/London", "英国": "Europe/London",
    "ireland": "Europe/Dublin", "爱尔兰": "Europe/Dublin",
    "germany": "Europe/Berlin", "德国": "Europe/Berlin",
    "france": "Europe/Paris", "法国": "Europe/Paris",
    "italy": "Europe/Rome", "意大利": "Europe/Rome",
    "spain": "Europe/Madrid", "西班牙": "Europe/Madrid",
    "netherlands": "Europe/Amsterdam", "荷兰": "Europe/Amsterdam",
    "belgium": "Europe/Brussels", "比利时": "Europe/Brussels",
    "switzerland": "Europe/Zurich", "瑞士": "Europe/Zurich",
    "austria": "Europe/Vienna", "奥地利": "Europe/Vienna",
    "portugal": "Europe/Lisbon", "葡萄牙": "Europe/Lisbon",
    "sweden": "Europe/Stockholm", "瑞典": "Europe/Stockholm",
    "norway": "Europe/Oslo", "挪威": "Europe/Oslo",
    "denmark": "Europe/Copenhagen", "丹麦": "Europe/Copenhagen",
    "finland": "Europe/Helsinki", "芬兰": "Europe/Helsinki",
    "poland": "Europe/Warsaw", "波兰": "Europe/Warsaw",
    "czech republic": "Europe/Prague", "czech": "Europe/Prague", "捷克": "Europe/Prague",
    "greece": "Europe/Athens", "希腊": "Europe/Athens",
    # --- Eastern Europe ---
    "russia": "Europe/Moscow", "俄罗斯": "Europe/Moscow",
    "turkey": "Europe/Istanbul", "土耳其": "Europe/Istanbul",
    "ukraine": "Europe/Kyiv", "乌克兰": "Europe/Kyiv",
    "romania": "Europe/Bucharest", "罗马尼亚": "Europe/Bucharest",
    "hungary": "Europe/Budapest", "匈牙利": "Europe/Budapest",
    # --- Middle East ---
    "uae": "Asia/Dubai", "united arab emirates": "Asia/Dubai", "阿联酋": "Asia/Dubai",
    "saudi arabia": "Asia/Riyadh", "沙特": "Asia/Riyadh", "沙特阿拉伯": "Asia/Riyadh",
    "israel": "Asia/Jerusalem", "以色列": "Asia/Jerusalem",
    "iraq": "Asia/Baghdad", "伊拉克": "Asia/Baghdad",
    "iran": "Asia/Tehran", "伊朗": "Asia/Tehran",
    "qatar": "Asia/Qatar", "卡塔尔": "Asia/Qatar",
    "kuwait": "Asia/Kuwait", "科威特": "Asia/Kuwait",
    "jordan": "Asia/Amman", "约旦": "Asia/Amman",
    "lebanon": "Asia/Beirut", "黎巴嫩": "Asia/Beirut",
    "oman": "Asia/Muscat", "阿曼": "Asia/Muscat",
    "bahrain": "Asia/Bahrain", "巴林": "Asia/Bahrain",
    # --- East Asia ---
    "china": "Asia/Shanghai", "中国": "Asia/Shanghai",
    "japan": "Asia/Tokyo", "日本": "Asia/Tokyo",
    "south korea": "Asia/Seoul", "korea": "Asia/Seoul", "韩国": "Asia/Seoul",
    "taiwan": "Asia/Taipei", "台湾": "Asia/Taipei",
    "hong kong": "Asia/Hong_Kong", "香港": "Asia/Hong_Kong",
    "macau": "Asia/Macau", "澳门": "Asia/Macau",
    "mongolia": "Asia/Ulaanbaatar", "蒙古": "Asia/Ulaanbaatar",
    # --- Southeast Asia ---
    "singapore": "Asia/Singapore", "新加坡": "Asia/Singapore",
    "thailand": "Asia/Bangkok", "泰国": "Asia/Bangkok",
    "vietnam": "Asia/Ho_Chi_Minh", "越南": "Asia/Ho_Chi_Minh",
    "malaysia": "Asia/Kuala_Lumpur", "马来西亚": "Asia/Kuala_Lumpur",
    "indonesia": "Asia/Jakarta", "印尼": "Asia/Jakarta", "印度尼西亚": "Asia/Jakarta",
    "philippines": "Asia/Manila", "菲律宾": "Asia/Manila",
    "myanmar": "Asia/Yangon", "缅甸": "Asia/Yangon",
    "cambodia": "Asia/Phnom_Penh", "柬埔寨": "Asia/Phnom_Penh",
    "laos": "Asia/Vientiane", "老挝": "Asia/Vientiane",
    # --- South Asia ---
    "india": "Asia/Kolkata", "印度": "Asia/Kolkata",
    "pakistan": "Asia/Karachi", "巴基斯坦": "Asia/Karachi",
    "bangladesh": "Asia/Dhaka", "孟加拉": "Asia/Dhaka", "孟加拉国": "Asia/Dhaka",
    "sri lanka": "Asia/Colombo", "斯里兰卡": "Asia/Colombo",
    "nepal": "Asia/Kathmandu", "尼泊尔": "Asia/Kathmandu",
    # --- Oceania ---
    "australia": "Australia/Sydney", "澳大利亚": "Australia/Sydney", "澳洲": "Australia/Sydney",
    "new zealand": "Pacific/Auckland", "新西兰": "Pacific/Auckland",
    # --- Africa ---
    "south africa": "Africa/Johannesburg", "南非": "Africa/Johannesburg",
    "egypt": "Africa/Cairo", "埃及": "Africa/Cairo",
    "nigeria": "Africa/Lagos", "尼日利亚": "Africa/Lagos",
    "kenya": "Africa/Nairobi", "肯尼亚": "Africa/Nairobi",
    "morocco": "Africa/Casablanca", "摩洛哥": "Africa/Casablanca",
    "ethiopia": "Africa/Addis_Ababa", "埃塞俄比亚": "Africa/Addis_Ababa",
    "tanzania": "Africa/Dar_es_Salaam", "坦桑尼亚": "Africa/Dar_es_Salaam",
    "ghana": "Africa/Accra", "加纳": "Africa/Accra",
}


@dataclass
class EmailBlastCandidate:
    lead: Lead
    email: OutreachEmail | None
    reason: str = ""


def _normalize_mail_domain(domain: str) -> str:
    return (domain or "").strip().lstrip("@")


def _compose_from_email(user_settings: UserSettings | None) -> str:
    if user_settings is None:
        return ""
    domain = _normalize_mail_domain(settings.mail_domain)
    prefix = (user_settings.from_email_prefix or "").strip().strip("@")
    sender = (user_settings.sender_name or "").strip()
    if not domain or not prefix:
        return ""
    address = f"{prefix}@{domain}"
    return f"{sender} <{address}>" if sender else address


def _classify_candidate(lead: Lead, email: OutreachEmail | None) -> str:
    if not (lead.email or "").strip():
        return "missing_email"
    if email is None:
        return "missing_draft"
    if email.send_status in {"sent", "delivered"}:
        return "already_sent"
    if not (email.email_subject or "").strip():
        return "missing_subject"
    if not (email.email_body or "").strip():
        return "missing_body"
    if email.send_status not in {"draft", "failed"}:
        return "not_sendable"
    return "sendable"


def _strip_markdown(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{2}(.+?)\*{2}", r"\1", text)
    text = re.sub(r"_{2}(.+?)_{2}", r"\1", text)
    text = re.sub(r"~~(.+?)~~", r"\1", text)
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[\s]*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_valid_email(email: str) -> bool:
    if not email:
        return False
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


def _classify_resend_error(status_code: int, message: str) -> str:
    if status_code == 401:
        return f"API Key 无效: {message}"
    if status_code == 403:
        return f"域名未验证或权限不足: {message}"
    if status_code == 422:
        return f"请求参数错误: {message}"
    if status_code == 429:
        return f"API 限流，发送频率过高: {message}"
    return f"Resend API 错误 (HTTP {status_code}): {message}"


def _extract_email_address(from_field: str) -> str:
    match = re.match(r"^.+?<([^>]+)>", from_field.strip())
    return match.group(1).strip() if match else from_field.strip()


def _get_country_tz(country: str) -> str | None:
    """Resolve country name (English or Chinese) to an IANA timezone string."""
    if not country:
        return None
    text = country.strip().lower()
    # Exact match
    if text in _COUNTRY_TO_TZ:
        return _COUNTRY_TO_TZ[text]
    # Substring match (longer key first for accuracy)
    for key, tz in sorted(_COUNTRY_TO_TZ.items(), key=lambda item: len(item[0]), reverse=True):
        if key in text or text in key:
            return tz
    # Word-level match
    words = re.findall(r"\w+", text)
    for word in words:
        if word in _COUNTRY_TO_TZ:
            return _COUNTRY_TO_TZ[word]
    return None


def _should_send_now(country: str) -> tuple[bool, str]:
    if not country or country.strip() in {"", "未知", "N/A", "n/a"}:
        return True, "国家未知，立即发送"
    tz_name = _get_country_tz(country)
    if not tz_name:
        return True, "国家未知，立即发送"
    try:
        tz = ZoneInfo(tz_name)
        local_time = datetime.now(timezone.utc).astimezone(tz)
    except Exception:
        return True, "国家未知，立即发送"
    if local_time.weekday() >= 5:
        return False, f"非工作日 (当地时间 {local_time.strftime('%Y-%m-%d %H:%M')})"
    if not 9 <= local_time.hour < 17:
        return False, f"不在当地工作时间 (当地时间 {local_time.strftime('%Y-%m-%d %H:%M')})"
    return True, f"工作时间 (当地时间 {local_time.strftime('%Y-%m-%d %H:%M')})"


async def _check_resend_environment(from_email: str) -> tuple[bool, str]:
    """Check Resend API key and sender domain before real sending."""
    if not settings.resend_api_key:
        return False, "RESEND_API_KEY 未配置"
    bare_from = _extract_email_address(from_email)
    if not _is_valid_email(bare_from):
        return False, f"发件人邮箱格式不正确: {from_email}"

    headers = {"Authorization": f"Bearer {settings.resend_api_key}"}
    api_key_ok = False
    async with httpx.AsyncClient(timeout=10) as client:
        for endpoint in ("domains", "audiences"):
            try:
                response = await client.get(f"https://api.resend.com/{endpoint}", headers=headers)
            except Exception:
                continue
            if response.status_code < 400:
                api_key_ok = True
                break
            if response.status_code == 401:
                try:
                    data = response.json()
                    message = data.get("message") or response.text
                except Exception:
                    message = response.text[:200]
                # Sending-access restricted keys return 401 for GET endpoints
                if "restricted" in message.lower():
                    api_key_ok = True
                    break
                return False, f"API Key 无效: {message}"
            if response.status_code == 403 and endpoint == "domains":
                continue

        if not api_key_ok:
            return False, "Resend API 连接失败或权限不足"

        domain = bare_from.split("@")[-1]
        if domain == "resend.dev":
            return True, "Resend 测试发件域名，无需域名验证"

        try:
            response = await client.get("https://api.resend.com/domains", headers=headers)
        except Exception as exc:
            return True, f"API Key 有效，但无法检查域名状态，请手动确认 {domain} 已验证: {exc}"
        if response.status_code in (401, 403):
            return True, f"API Key 无权查询域名状态，请手动确认 {domain} 已在 Resend 中验证"
        if response.status_code >= 400:
            return True, f"无法检查域名状态: HTTP {response.status_code}"

        domains = response.json().get("data", [])
        for item in domains:
            if (item.get("name") or "").lower() == domain.lower():
                status = item.get("status") or ""
                if status in {"verified", "success"}:
                    return True, f"域名 {domain} 已验证"
                return False, f"域名 {domain} 已添加但未验证，请先完成 DNS 验证"
        return False, f"域名 {domain} 未在 Resend 中找到，请先添加并验证域名"


async def _send_via_resend(
    *,
    email_record: OutreachEmail,
    lead: Lead,
    from_email: str,
    reply_to: str,
    task_id: int,
) -> dict:
    to_email = (lead.email or "").strip()
    if not _is_valid_email(to_email):
        return {"success": False, "message_id": None, "error": "邮箱格式无效"}

    subject = (email_record.email_subject or "").strip()
    body = _strip_markdown(email_record.email_body or "")
    if not subject:
        return {"success": False, "message_id": None, "error": "邮件主题为空"}
    if not body:
        return {"success": False, "message_id": None, "error": "邮件正文为空"}

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": body,
    }
    if reply_to and _is_valid_email(reply_to):
        payload["reply_to"] = reply_to

    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
        "Idempotency-Key": f"outreach-email-{email_record.id}-{task_id}",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                json=payload,
                headers=headers,
            )
        if response.status_code >= 400:
            try:
                data = response.json()
                message = data.get("message") or data.get("error", {}).get("message") or response.text
            except Exception:
                message = response.text[:300]
            return {
                "success": False,
                "message_id": None,
                "error": _classify_resend_error(response.status_code, message),
            }
        data = response.json()
        return {"success": True, "message_id": data.get("id"), "error": None}
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
        return {"success": False, "message_id": None, "error": f"网络错误: {exc}"}
    except Exception as exc:
        return {"success": False, "message_id": None, "error": f"未知错误: {exc}"}


async def _create_task_log(
    task_id: int,
    step: int,
    name: str,
    status: str = "pending",
    message: str = "",
    progress: int = 0,
) -> None:
    async with async_session_factory() as db:
        log = TaskLog(
            task_id=task_id,
            step_number=step,
            step_name=name,
            status=status,
            message=message,
            progress=progress,
        )
        db.add(log)
        await db.commit()


async def _update_task_log(
    task_id: int,
    step: int,
    status: str | None = None,
    message: str | None = None,
    progress: int | None = None,
) -> None:
    async with async_session_factory() as db:
        result = await db.execute(
            select(TaskLog).where(TaskLog.task_id == task_id, TaskLog.step_number == step)
        )
        log = result.scalar_one_or_none()
        if log:
            if status is not None:
                log.status = status
            if message is not None:
                log.message = message
            if progress is not None:
                log.progress = progress
            await db.commit()


async def _mark_task_done(task_id: int, status: str, result_summary: dict) -> None:
    async with async_session_factory() as db:
        task = await db.get(Task, task_id)
        if task:
            task.status = status
            task.result_summary = result_summary
            task.ended_at = datetime.now(timezone.utc)
            await db.commit()
        task_manager.remove_task(task_id)


async def _get_latest_email_for_lead(db, lead_id: int) -> OutreachEmail | None:
    result = await db.execute(
        select(OutreachEmail)
        .where(OutreachEmail.lead_id == lead_id)
        .order_by(OutreachEmail.created_at.desc(), OutreachEmail.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _load_candidates(user_id: int, lead_ids: list[int]) -> list[EmailBlastCandidate]:
    async with async_session_factory() as db:
        task_ids_query = select(Task.id).where(Task.user_id == user_id)
        query = select(Lead).where(Lead.task_id.in_(task_ids_query))
        if lead_ids:
            query = query.where(Lead.id.in_(lead_ids))
        result = await db.execute(query.order_by(Lead.match_score.desc(), Lead.id.asc()))
        leads = result.scalars().all()

        candidates: list[EmailBlastCandidate] = []
        for lead in leads:
            latest_email = await _get_latest_email_for_lead(db, lead.id)
            reason = _classify_candidate(lead, latest_email)
            candidates.append(EmailBlastCandidate(lead=lead, email=latest_email, reason=reason))
        return candidates


def _summarize_candidates(candidates: list[EmailBlastCandidate]) -> dict:
    summary = {
        "selected": len(candidates),
        "sendable": 0,
        "alreadySent": 0,
        "missingEmail": 0,
        "missingDraft": 0,
        "missingContent": 0,
        "notSendable": 0,
        "retryable": 0,
    }
    for candidate in candidates:
        reason = candidate.reason
        if reason == "sendable":
            summary["sendable"] += 1
            if candidate.email and candidate.email.send_status == "failed":
                summary["retryable"] += 1
        elif reason == "already_sent":
            summary["alreadySent"] += 1
        elif reason == "missing_email":
            summary["missingEmail"] += 1
        elif reason == "missing_draft":
            summary["missingDraft"] += 1
        elif reason in {"missing_subject", "missing_body"}:
            summary["missingContent"] += 1
        else:
            summary["notSendable"] += 1
    return summary


async def _load_user_settings(user_id: int) -> UserSettings | None:
    async with async_session_factory() as db:
        result = await db.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        return result.scalar_one_or_none()


async def _update_email_status(
    email_id: int,
    status: str,
    error_message: str = "",
    sent_at: datetime | None = None,
    resend_message_id: str | None = None,
    last_event: str | None = None,
) -> None:
    async with async_session_factory() as db:
        email = await db.get(OutreachEmail, email_id)
        if email is None:
            return
        email.send_status = status
        email.error_message = error_message
        email.last_send_attempt_at = datetime.now(timezone.utc)
        if resend_message_id is not None:
            email.resend_message_id = resend_message_id
        if last_event is not None:
            email.last_event = last_event
        if sent_at is not None:
            email.sent_at = sent_at
        await db.commit()


async def run_email_blast_pipeline(task_id: int, user_id: int, intent: dict) -> None:
    """Run email-blast in the background."""
    params = intent.get("params", {}) if isinstance(intent, dict) else {}
    lead_ids = [int(v) for v in (params.get("lead_ids") or [])]
    delay_min = max(0, int(params.get("delay_min") or 60))
    delay_max = max(delay_min, int(params.get("delay_max") or 120))
    daily_limit = max(0, int(params.get("daily_limit") or 50))
    dry_run = False
    send_mode = str(params.get("send_mode") or "auto")
    if send_mode not in {"immediate", "auto"}:
        send_mode = "immediate"

    try:
        await _create_task_log(task_id, 1, "发送预检查", "running", "正在检查发件配置...", 0)
        user_settings = await _load_user_settings(user_id)
        from_email = _compose_from_email(user_settings)
        missing_config = []
        if not settings.resend_api_key:
            missing_config.append("RESEND_API_KEY")
        if user_settings is None or not (user_settings.sender_name or "").strip():
            missing_config.append("发件人名称")
        if user_settings is None or not (user_settings.from_email_prefix or "").strip():
            missing_config.append("发件邮箱前缀")
        if user_settings is None or not user_settings.confirmed_at:
            missing_config.append("邮箱配置确认")
        if not _normalize_mail_domain(settings.mail_domain):
            missing_config.append("MAIL_DOMAIN")

        if missing_config:
            await _update_task_log(
                task_id,
                1,
                "failed",
                f"缺少发件配置：{', '.join(missing_config)}",
                0,
            )
            await _mark_task_done(task_id, "failed", {"error": f"缺少发件配置：{', '.join(missing_config)}"})
            return

        config_message = "配置检查通过"
        if missing_config:
            config_message = f"仍缺少：{', '.join(missing_config)}"
        else:
            resend_ok, resend_message = await _check_resend_environment(from_email)
            if not resend_ok:
                await _update_task_log(task_id, 1, "failed", resend_message, 0)
                await _mark_task_done(task_id, "failed", {"error": resend_message})
                return
            config_message = "配置检查通过"
        await _update_task_log(task_id, 1, "completed", config_message, 100)
        task_manager.update_heartbeat(task_id)

        await _create_task_log(task_id, 2, "读取待发送", "running", "正在读取选中客户的开发信...", 0)
        candidates = await _load_candidates(user_id, lead_ids)
        candidate_summary = _summarize_candidates(candidates)
        sendable = [candidate for candidate in candidates if candidate.reason == "sendable"]
        await _update_task_log(
            task_id,
            2,
            "completed",
            f"已读取 {candidate_summary['selected']} 个客户，可发送 {candidate_summary['sendable']} 封",
            100,
        )
        task_manager.update_heartbeat(task_id)

        if not candidates:
            await _mark_task_done(task_id, "failed", {"error": "没有找到可访问的客户"})
            return
        if not sendable:
            result_summary = {
                **candidate_summary,
                "sent": 0,
                "failed": 0,
                "skipped": candidate_summary["selected"],
                "dryRun": False,
                "fromEmail": from_email,
            }
            await _mark_task_done(task_id, "failed", {"error": "选中的客户暂无可发送开发信", **result_summary})
            return

        if send_mode == "auto":
            send_message = "正在按客户当地工作时间，通过 Resend 发送开发信..."
        else:
            send_message = "正在通过 Resend 发送开发信..."
        await _create_task_log(task_id, 3, "发送邮件", "running", send_message, 0)

        limited_sendable = sendable[:daily_limit] if daily_limit > 0 else sendable
        skipped_by_limit = max(0, len(sendable) - len(limited_sendable))
        skipped_by_time_window = 0
        sent_count = 0
        failed_count = 0

        for index, candidate in enumerate(limited_sendable):
            async with async_session_factory() as db:
                task = await db.get(Task, task_id)
                if task and task.cancelled:
                    await _update_task_log(
                        task_id,
                        3,
                        "cancelled",
                        f"已取消，已发送 {sent_count}/{len(limited_sendable)}",
                        int(sent_count / max(1, len(limited_sendable)) * 100),
                    )
                    await _mark_task_done(task_id, "cancelled", {"sent": sent_count, "dryRun": False})
                    return

            company = candidate.lead.company_name or candidate.lead.email
            email_record = candidate.email
            if email_record is None:
                failed_count += 1
                continue

            attempted = index + 1
            progress = int(attempted / max(1, len(limited_sendable)) * 100)

            if send_mode == "auto":
                should_send, window_reason = _should_send_now(candidate.lead.country or "")
                if not should_send:
                    skipped_by_time_window += 1
                    await _update_task_log(
                        task_id,
                        3,
                        "running",
                        f"[{attempted}/{len(limited_sendable)}] 跳过当地时间窗口 — {company}: {window_reason}",
                        progress,
                    )
                    task_manager.update_heartbeat(task_id)
                    continue

            await _update_email_status(email_record.id, "sending", last_event="email.sending")
            send_result = await _send_via_resend(
                email_record=email_record,
                lead=candidate.lead,
                from_email=from_email,
                reply_to=(user_settings.reply_to_email if user_settings else ""),
                task_id=task_id,
            )
            if not send_result["success"] and "网络错误" in (send_result.get("error") or ""):
                await asyncio.sleep(1)
                send_result = await _send_via_resend(
                    email_record=email_record,
                    lead=candidate.lead,
                    from_email=from_email,
                    reply_to=(user_settings.reply_to_email if user_settings else ""),
                    task_id=task_id,
                )

            if send_result["success"]:
                sent_count += 1
                message_id = send_result.get("message_id") or ""
                await _update_email_status(
                    email_record.id,
                    "sent",
                    error_message=f"Resend ID: {message_id}" if message_id else "",
                    sent_at=datetime.now(timezone.utc),
                    resend_message_id=message_id,
                    last_event="email.sent",
                )
            else:
                failed_count += 1
                await _update_email_status(
                    email_record.id,
                    "failed",
                    error_message=send_result.get("error") or "发送失败",
                    last_event="email.failed",
                )

            result_text = "成功" if send_result["success"] else "失败"
            await _update_task_log(
                task_id,
                3,
                "running",
                f"[{attempted}/{len(limited_sendable)}] {result_text} — {company}",
                progress,
            )
            task_manager.update_heartbeat(task_id)

            if index < len(limited_sendable) - 1:
                await asyncio.sleep(random.randint(delay_min, delay_max))

        await _update_task_log(
            task_id,
            3,
            "completed",
            f"发送完成：成功 {sent_count} 封，失败 {failed_count} 封",
            100,
        )
        task_manager.update_heartbeat(task_id)

        status_message = "发送状态已逐封写回数据库..."
        await _create_task_log(task_id, 4, "状态回写", "running", status_message, 0)
        skipped_count = candidate_summary["selected"] - sent_count - failed_count
        result_summary = {
            **candidate_summary,
            "sent": sent_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "skippedByDailyLimit": skipped_by_limit,
            "skippedByTimeWindow": skipped_by_time_window,
            "dryRun": False,
            "sendMode": send_mode,
            "fromEmail": from_email,
            "delayMin": delay_min,
            "delayMax": delay_max,
            "dailyLimit": daily_limit,
            "leadIds": lead_ids,
        }
        await _update_task_log(
            task_id,
            4,
            "completed",
            f"完成：成功 {sent_count} 封，失败 {failed_count} 封，跳过 {skipped_count} 封",
            100,
        )
        await _mark_task_done(task_id, "completed", result_summary)

    except Exception as exc:
        logger.exception("Email-blast pipeline failed for task %d", task_id)
        try:
            await _create_task_log(task_id, 1, "failed", f"Pipeline 错误: {str(exc)[:200]}", 0)
            await _mark_task_done(task_id, "failed", {"error": str(exc)[:300]})
        except Exception:
            pass
