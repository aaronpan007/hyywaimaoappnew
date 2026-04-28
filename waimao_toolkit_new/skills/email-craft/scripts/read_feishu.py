"""Read customer records from Feishu table for email crafting."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import _run_lark_cli, print_progress, print_error

# Field mapping: Feishu Chinese name -> internal key
FIELD_MAP = {
    "公司名称": "company_name",
    "网站": "website",
    "国家/地区": "country",
    "行业": "industry",
    "公司角色": "company_role",
    "联系人": "contact_name",
    "邮箱": "email",
    "电话": "phone",
    "AI分析摘要": "ai_summary",
    "业务匹配点": "business_match_points",
    "开发建议": "outreach_content",
    "邮件已发送": "email_sent",
    "备注": "notes",
    "开发信": "email_draft",
    "邮件主题": "email_subject",
}

# Reverse map for looking up Feishu field names
FIELD_MAP_REVERSE = {v: k for k, v in FIELD_MAP.items()}


def _extract_field_value(raw_value):
    """Normalize a field value from lark-cli response.

    Values may be arrays like ["text"] or direct strings.
    """
    if isinstance(raw_value, list):
        return raw_value[0] if raw_value else ""
    if isinstance(raw_value, str):
        return raw_value
    if isinstance(raw_value, dict):
        text_val = raw_value.get("text", raw_value.get("value", ""))
        return str(text_val) if text_val else ""
    return str(raw_value) if raw_value else ""


def _auto_detect_view(base_token, table_id, identity):
    """Auto-detect the first view ID for a table."""
    result = _run_lark_cli([
        "base", "+view-list",
        "--base-token", base_token,
        "--table-id", table_id,
        "--as", identity,
    ], timeout=15)

    if result and result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            views = data.get("data", {}).get("views", [])
            if views:
                return views[0].get("id", "")
        except (json.JSONDecodeError, TypeError):
            pass
    return ""


def _parse_record_list_response(result_stdout):
    """Parse the lark-cli +record-list response.

    lark-cli returns a column-oriented format:
      data.fields = ["Field1", "Field2", ...]
      data.record_id_list = ["recXXX", "recYYY", ...]
      data.data = [[val1, val2, ...], [val1, val2, ...], ...]

    Returns (field_names, record_ids, rows, has_more) or None on failure.
    """
    try:
        data = json.loads(result_stdout)
    except json.JSONDecodeError:
        # Try fixing common encoding issues
        try:
            data = json.loads(result_stdout, strict=False)
        except (json.JSONDecodeError, TypeError):
            return None

    if not data.get("ok"):
        return None

    inner = data.get("data", {})

    # Column-oriented format: fields + record_id_list + data[][]
    if "fields" in inner and "data" in inner:
        fields = inner["fields"]
        record_ids = inner.get("record_id_list", [])
        rows = inner["data"]
        has_more = inner.get("has_more", False)
        return fields, record_ids, rows, has_more

    # Row-oriented format: records[] (fallback)
    if "records" in inner:
        records = inner["records"]
        has_more = inner.get("has_more", False)
        return None, None, records, has_more  # handled differently below

    return None, None, [], False


def read_records(base_token, table_id, identity, skip_with_draft=True, view_id=""):
    """Read customer records from Feishu table.

    Args:
        base_token: Feishu base token
        table_id: Feishu table ID
        identity: 'user' or 'bot'
        skip_with_draft: If True, skip records that already have a 邮件主题
        view_id: Optional view ID for record listing

    Returns list of dicts with internal field names + _record_id.
    """
    if not view_id:
        view_id = _auto_detect_view(base_token, table_id, identity)
        if view_id:
            print_progress("READ", f"Auto-detected view: {view_id}")

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
        if view_id:
            args.extend(["--view-id", view_id])

        result = _run_lark_cli(args, timeout=30)

        if not result or result.returncode != 0:
            stderr = (result.stderr or "")[:300] if result else "no response"
            print_error(f"Failed to read records (offset={offset}): {stderr}")
            break

        fields, record_ids, rows, has_more = _parse_record_list_response(result.stdout)

        if fields is not None and record_ids is not None:
            # Column-oriented format
            for i, row in enumerate(rows):
                if not isinstance(row, list):
                    continue
                record_id = record_ids[i] if i < len(record_ids) else ""

                record = {"_record_id": record_id}
                for j, field_name in enumerate(fields):
                    if j < len(row):
                        internal_key = FIELD_MAP.get(field_name)
                        if internal_key:
                            record[internal_key] = _extract_field_value(row[j])

                # Client-side filtering
                email = record.get("email", "").strip()
                if not email:
                    continue

                if skip_with_draft:
                    subject = record.get("email_subject", "").strip()
                    if subject:
                        continue

                all_records.append(record)

        elif isinstance(rows, list):
            # Row-oriented format (fallback for records[])
            for rec in rows:
                if not isinstance(rec, dict):
                    continue
                record_id = rec.get("record_id", "")
                fields_dict = rec.get("fields", {})

                record = {"_record_id": record_id}
                for feishu_name, internal_key in FIELD_MAP.items():
                    if feishu_name in fields_dict:
                        record[internal_key] = _extract_field_value(fields_dict[feishu_name])
                    else:
                        record[internal_key] = ""

                email = record.get("email", "").strip()
                if not email:
                    continue

                if skip_with_draft:
                    subject = record.get("email_subject", "").strip()
                    if subject:
                        continue

                all_records.append(record)
        else:
            break

        offset += page_size

    print_progress("READ", f"Read {len(all_records)} records (total fetched: {offset})")
    return all_records


def print_records_table(records):
    """Print a formatted table of records for user selection."""
    if not records:
        print("\nNo records found matching the criteria.")
        return

    # Header
    print(f"\n{'#':<4} {'Record ID':<18} {'Company':<35} {'Country':<15} {'Industry':<20} {'Email':<35}")
    print(f"{'-'*4} {'-'*18} {'-'*35} {'-'*15} {'-'*20} {'-'*35}")

    for i, rec in enumerate(records, 1):
        rid = rec.get("_record_id", "")[:16]
        name = rec.get("company_name", "")[:33]
        country = rec.get("country", "")[:13]
        industry = rec.get("industry", "")[:18]
        email = rec.get("email", "")[:33]
        print(f"{i:<4} {rid:<18} {name:<35} {country:<15} {industry:<20} {email:<35}")

    if len(records) > 50:
        print(f"  ... and {len(records) - 50} more")
        records = records[:50]

    print(f"\nTotal: {len(records)} records")

    # Also print record IDs for easy --select usage
    print("\nRecord IDs (for --select):")
    id_list = [rec["_record_id"] for rec in records]
    print(",".join(id_list))
