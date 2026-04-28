"""Send emails via Resend API."""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime

from utils import get_env, print_progress


def extract_email_address(from_field):
    """Extract bare email from 'Name <email>' or 'email' format."""
    if not from_field:
        return ""
    from_field = from_field.strip()
    m = re.match(r'^(.+?)\s*<([^>]+)>', from_field)
    if m:
        return m.group(2).strip()
    return from_field


def strip_markdown(text):
    """Strip markdown formatting from text, leaving plain content.

    Handles: bold, italic, strikethrough, headers, links, images,
    blockquotes, horizontal rules, list markers.
    """
    if not text:
        return text
    # Remove images: ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)
    # Remove links: [text](url) → text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove headers: ## Title → Title
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # Remove bold+italic: ***text*** or ___text___
    text = re.sub(r'\*{3}(.+?)\*{3}', r'\1', text)
    text = re.sub(r'_{3}(.+?)_{3}', r'\1', text)
    # Remove bold: **text** or __text__
    text = re.sub(r'\*{2}(.+?)\*{2}', r'\1', text)
    text = re.sub(r'_{2}(.+?)_{2}', r'\1', text)
    # Remove italic: *text* or _text_
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
    text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'\1', text)
    # Remove strikethrough: ~~text~~
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    # Remove blockquotes: > text
    text = re.sub(r'^>\s?', '', text, flags=re.MULTILINE)
    # Remove horizontal rules: --- or *** or ___
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Remove unordered list markers: - item or * item
    text = re.sub(r'^[\s]*[-*+]\s+', '', text, flags=re.MULTILINE)
    # Remove ordered list markers: 1. item
    text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)
    # Remove code blocks: ```...```
    text = re.sub(r'```[\s\S]*?```', '', text)
    # Remove inline code: `text`
    text = re.sub(r'`(.+?)`', r'\1', text)
    # Collapse excessive blank lines (3+ → 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def validate_email(email):
    """Basic email format validation. Accepts 'Name <email>' or plain 'email'."""
    if not email or not isinstance(email, str):
        return False
    bare = extract_email_address(email)
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, bare))


def send_single_email(to_email, subject, body, from_email=None, reply_to=None):
    """Send a single email via Resend API.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        body: Email body (plain text or HTML).
        from_email: Sender email (defaults to FROM_EMAIL env var).
        reply_to: Optional reply-to address.

    Returns:
        dict with keys: success, message_id, error
    """
    api_key = get_env("RESEND_API_KEY")
    if not from_email:
        from_email = get_env("FROM_EMAIL")

    # Validate inputs
    if not validate_email(to_email):
        return {"success": False, "message_id": None, "error": "邮箱格式无效"}

    if not validate_email(from_email):
        return {"success": False, "message_id": None, "error": f"发件人邮箱格式无效: {from_email}"}

    if not subject.strip():
        return {"success": False, "message_id": None, "error": "邮件主题为空"}

    if not body.strip():
        return {"success": False, "message_id": None, "error": "邮件正文为空"}

    # Determine if body is HTML
    is_html = bool(re.search(r'<\w+.*?>', body[:200]))

    # Strip markdown formatting from plain text bodies
    if not is_html:
        body = strip_markdown(body)

    payload = {
        "from": from_email,
        "to": [to_email.strip()],
        "subject": subject.strip(),
    }

    if is_html:
        payload["html"] = body
    else:
        payload["text"] = body

    if reply_to and validate_email(reply_to):
        payload["reply_to"] = reply_to

    # Call Resend API
    url = "https://api.resend.com/emails"
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "email-blast-skill/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            message_id = resp_data.get("id")
            print_progress("SEND", f"  → {to_email} ✓ (message_id: {message_id})")
            return {"success": True, "message_id": message_id, "error": None}

    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(body_text)
            error_msg = err.get("message", err.get("error", {}).get("message", str(e)))
        except (json.JSONDecodeError, AttributeError):
            error_msg = body_text[:300]

        # Classify common errors
        status_code = e.code
        if status_code == 403:
            classified = f"域名未验证或权限不足: {error_msg}"
        elif status_code == 422:
            classified = f"请求参数错误: {error_msg}"
        elif status_code == 429:
            classified = f"API 限流，发送频率过高: {error_msg}"
        elif status_code == 401:
            classified = f"API Key 无效: {error_msg}"
        else:
            classified = f"Resend API 错误 (HTTP {status_code}): {error_msg}"

        print_progress("SEND", f"  → {to_email} ✗ ({classified})")
        return {"success": False, "message_id": None, "error": classified}

    except urllib.error.URLError as e:
        error_msg = f"网络错误: {e.reason}"
        print_progress("SEND", f"  → {to_email} ✗ ({error_msg})")
        return {"success": False, "message_id": None, "error": error_msg}

    except Exception as e:
        error_msg = f"未知错误: {e}"
        print_progress("SEND", f"  → {to_email} ✗ ({error_msg})")
        return {"success": False, "message_id": None, "error": error_msg}


def send_batch(records, from_email=None, dry_run=False,
               delay_min=60, delay_max=120, daily_limit=50,
               send_mode="auto", on_status_update=None, reply_to=None):
    """Send a batch of emails with rate limiting and status tracking.

    Args:
        records: List of record dicts (from read_pending.py).
            Each must have: _record_id, email, email_subject, email_draft.
            Optional: country (for timezone-aware sending).
        from_email: Sender email override.
        dry_run: If True, simulate sending without actually calling Resend.
        delay_min: Minimum delay between emails in seconds.
        delay_max: Maximum delay between emails in seconds.
        daily_limit: Maximum emails to send today (0 = no limit).
        send_mode: "auto" (timezone-aware), "immediate" (send now).
        on_status_update: Callback function(record, result) called after each send attempt.
        reply_to: Reply-to email address (defaults to REPLY_TO_EMAIL env var).

    Returns:
        dict with keys: success_count, fail_count, skip_count, results
    """
    if reply_to is None:
        reply_to = os.environ.get("REPLY_TO_EMAIL", "")
    import time
    import random

    # Pre-flight: check domain DNS stability
    if not dry_run:
        from check_env import get_domain_dns_status
        dns_status = get_domain_dns_status()
        if dns_status is not None:
            if dns_status.get("missing"):
                missing_names = ", ".join(dns_status["missing"])
                print_progress("SEND", f"⚠️ 域名 DNS 记录未全部验证: {missing_names}")
                print_progress("SEND", "等待 DNS 记录生效...")

                # Poll every 30s, up to 5 minutes
                max_wait = 300
                poll_interval = 30
                waited = 0
                while waited < max_wait:
                    time.sleep(poll_interval)
                    waited += poll_interval
                    dns_status = get_domain_dns_status()
                    if dns_status is None or not dns_status.get("missing"):
                        print_progress("SEND", f"✅ DNS 记录全部验证通过（等待 {waited}s）")
                        break
                    remaining_missing = ", ".join(dns_status["missing"])
                    print_progress("SEND", f"  ... 仍缺少 {remaining_missing}（已等 {waited}s，最多 {max_wait}s）")
                else:
                    print_progress("SEND", f"⚠️ 等待 {max_wait}s 后仍有未验证记录，尝试继续发送")
            else:
                print_progress("SEND", f"✅ 域名 DNS 检查通过 (SPF/DKIM/DMARC)")

    results = []
    success_count = 0
    fail_count = 0
    skip_count = 0
    today_sent = 0

    if daily_limit > 0:
        from read_pending import get_today_sent_count
        today_sent = get_today_sent_count()
        remaining = daily_limit - today_sent
        if remaining <= 0:
            print_progress("SEND", f"⚠️ 已达每日上限 ({daily_limit} 封)，今日不再发送")
            return {
                "success_count": 0, "fail_count": 0,
                "skip_count": len(records), "results": [],
            }
        if remaining < len(records):
            print_progress("SEND", f"⚠️ 今日剩余额度 {remaining} 封，仅发送前 {remaining} 封")
            records = records[:remaining]

    total = len(records)
    print_progress("SEND", f"开始发送 {total} 封邮件 (dry_run={dry_run}, mode={send_mode})")
    print_progress("SEND", f"策略: 间隔 {delay_min}-{delay_max}s, 每日上限 {daily_limit}")
    if reply_to:
        print_progress("SEND", f"回复邮箱: {reply_to}")

    for i, record in enumerate(records):
        idx = i + 1
        email = record.get("email", "")
        subject = record.get("email_subject", "")
        body = record.get("email_draft", "")
        record_id = record.get("_record_id", "")
        country = record.get("country", "")

        # Timezone check for auto mode
        if send_mode == "auto" and country and not dry_run:
            from timezone import should_send_now
            can_send, reason = should_send_now(country)
            if not can_send:
                print_progress("SEND", f"  → {email} ⏭️ 跳过 ({reason})")
                results.append({
                    "record_id": record_id, "email": email,
                    "success": False, "skipped": True,
                    "error": reason,
                })
                skip_count += 1
                continue

        print_progress("SEND", f"📤 发送中... [{idx}/{total}]")

        if dry_run:
            print_progress("SEND", f"  → {email} [DRY-RUN] (would send)")
            result = {
                "success": True, "message_id": f"dry_run_{record_id}",
                "error": None, "dry_run": True,
            }
        else:
            # Retry once on failure
            result = send_single_email(email, subject, body, from_email, reply_to=reply_to)
            if not result["success"]:
                # Classify if retryable
                if "网络" in result.get("error", "") or "超时" in result.get("error", ""):
                    print_progress("SEND", f"  ⏳ 网络错误，1秒后重试...")
                    time.sleep(1)
                    result = send_single_email(email, subject, body, from_email, reply_to=reply_to)

        # Track result
        if result.get("success"):
            success_count += 1
        elif result.get("skipped"):
            skip_count += 1
        else:
            fail_count += 1

        result["record_id"] = record_id
        result["email"] = email
        result["company"] = record.get("company_name", "")
        results.append(result)

        # Update status immediately after each email
        if on_status_update and not dry_run:
            on_status_update(record, result)

        # Delay between emails (except after the last one, and skip in dry-run)
        if i < total - 1 and not dry_run:
            delay = random.randint(delay_min, delay_max)
            print_progress("SEND", f"  等待 {delay} 秒...")
            waited = 0
            while waited < delay:
                step = min(30, delay - waited)
                time.sleep(step)
                waited += step
                remaining = delay - waited
                if remaining > 0:
                    print_progress("SEND", f"  ... 继续等待 {remaining}s")

    print_progress("SEND", f"发送完成: 成功 {success_count}, 失败 {fail_count}, 跳过 {skip_count}")
    return {
        "success_count": success_count,
        "fail_count": fail_count,
        "skip_count": skip_count,
        "results": results,
    }
