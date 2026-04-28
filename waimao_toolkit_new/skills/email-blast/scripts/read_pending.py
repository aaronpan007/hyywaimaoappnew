"""Read pending email records from Feishu table."""

from datetime import datetime
from utils import (
    get_feishu_config,
    run_lark_cli,
    parse_record_list_response,
    extract_field_value,
    FIELD_MAP,
    print_progress,
)


def read_pending_records(select_ids=None, include_failed=False):
    """Read records that are ready to be sent.

    Filters:
    - Has email (邮箱 not empty)
    - Has email draft (开发信 not empty)
    - Has email subject (邮件主题 not empty)
    - email_sent (邮件已发送) is empty or "否"

    Args:
        select_ids: Optional list of record IDs to filter to.
        include_failed: If True, also include records that failed before.

    Returns:
        List of dicts with keys: _record_id, company_name, contact_name, email,
        email_subject, email_draft, country, notes, and other mapped fields.
    """
    config = get_feishu_config()
    if not config:
        print("❌ 未找到飞书表格配置")
        return []

    base_token = config["base_token"]
    table_id = config["table_id"]
    identity = config["identity"]

    print_progress("READ", f"读取飞书表格 (base={base_token[:8]}..., table={table_id[:8]}...)")

    all_records = []
    offset = 0
    page_size = 200
    has_more = True

    while has_more:
        args = [
            "base", "+record-list",
            "--base-token", base_token,
            "--table-id", table_id,
            "--as", identity,
            "--offset", str(offset),
            "--limit", str(page_size),
        ]

        result = run_lark_cli(args, timeout=30)
        if result is None:
            print_progress("READ", "❌ 读取失败: lark-cli 无响应")
            break

        if result.returncode != 0:
            print_progress("READ", f"❌ 读取失败: {result.stderr[:200] if result.stderr else result.stdout[:200]}")
            break

        fields, record_ids, rows, has_more = parse_record_list_response(result.stdout)
        if not fields:
            break

        for i, row in enumerate(rows):
            if i >= len(record_ids):
                break
            record_id = record_ids[i]
            record = {"_record_id": record_id}

            for j, field_name in enumerate(fields):
                if j < len(row):
                    internal_key = FIELD_MAP.get(field_name)
                    if internal_key:
                        record[internal_key] = extract_field_value(row[j])

            # Filter: must have email, subject, and draft
            email = record.get("email", "").strip()
            subject = record.get("email_subject", "").strip()
            draft = record.get("email_draft", "").strip()

            if not email:
                continue
            if not subject:
                continue
            if not draft:
                continue

            # Filter: not already sent (unless include_failed)
            email_sent = record.get("email_sent", "").strip()
            if email_sent in ("是", "yes", "Yes", "YES", "1", "true", "True", True):
                continue

            # Filter: skip if it has a failure note and we're not including failed
            notes = record.get("notes", "").strip()
            if not include_failed and "发送失败" in notes and email_sent in ("否", "no"):
                continue

            # Filter by specific IDs if provided
            if select_ids and record_id not in select_ids:
                continue

            all_records.append(record)

        offset += page_size

        if not has_more:
            break

    print_progress("READ", f"读取完成，共 {len(all_records)} 条待发送记录")
    return all_records


def format_pending_preview(records, max_preview=10):
    """Format pending records for user preview display."""
    if not records:
        return "📭 没有待发送的邮件。请先使用 email-craft 生成开发信。"

    lines = []
    lines.append(f"📋 待发送邮件预览")
    lines.append("━" * 50)
    lines.append(f"共 {len(records)} 封待发送邮件")
    lines.append("")

    for i, rec in enumerate(records[:max_preview], 1):
        company = rec.get("company_name", "未知公司")
        email = rec.get("email", "")
        subject = rec.get("email_subject", "")
        draft = rec.get("email_draft", "")
        preview_text = draft[:100].replace("\n", " ") + "..." if len(draft) > 100 else draft.replace("\n", " ")

        lines.append(f"#{i}  {company} ({email})")
        lines.append(f"    主题: {subject}")
        lines.append(f"    预览: {preview_text}")
        lines.append("")

    if len(records) > max_preview:
        lines.append(f"... 还有 {len(records) - max_preview} 封未显示")
        lines.append("")

    lines.append("━" * 50)
    return "\n".join(lines)


def get_today_sent_count():
    """Count how many emails were sent today (邮件已发送=是 and 发送时间 is today)."""
    config = get_feishu_config()
    if not config:
        return 0

    base_token = config["base_token"]
    table_id = config["table_id"]
    identity = config["identity"]

    today_str = datetime.now().strftime("%Y-%m-%d")
    count = 0

    all_records = []
    offset = 0
    page_size = 200
    has_more = True

    while has_more:
        args = [
            "base", "+record-list",
            "--base-token", base_token,
            "--table-id", table_id,
            "--as", identity,
            "--offset", str(offset),
            "--limit", str(page_size),
        ]
        result = run_lark_cli(args, timeout=30)
        if result is None or result.returncode != 0:
            break

        fields, record_ids, rows, has_more = parse_record_list_response(result.stdout)
        if not fields:
            break

        for i, row in enumerate(rows):
            if i >= len(record_ids):
                break
            record = {}
            for j, field_name in enumerate(fields):
                if j < len(row):
                    key = FIELD_MAP.get(field_name)
                    if key:
                        record[key] = extract_field_value(row[j])

            if record.get("email_sent", "").strip() in ("是", "yes", "Yes", "YES", "1", "true", "True", True):
                sent_time = record.get("sent_time", "").strip()
                if today_str in sent_time:
                    count += 1

        offset += page_size

    return count
