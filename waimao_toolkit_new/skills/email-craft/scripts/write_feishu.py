"""Write generated emails back to Feishu table."""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import _run_lark_cli, print_progress, print_error


def write_email_to_feishu(base_token, table_id, record_id, subject, body, identity, dry_run=False):
    """Write email subject and body to a single Feishu record.

    Args:
        base_token: Feishu base token
        table_id: Feishu table ID
        record_id: Record ID to update
        subject: Email subject
        body: Email body
        identity: 'user' or 'bot'
        dry_run: If True, skip actual write

    Returns (success, error_message).
    """
    if dry_run:
        print_progress("WRITE", f"[DRY-RUN] Would write to {record_id}")
        return True, ""

    # Windows command line length limit: truncate if needed
    # --json content is the main contributor to length
    max_json_len = 6000
    body_truncated = body
    if len(body) > max_json_len:
        body_truncated = body[:max_json_len] + "\n\n[... truncated due to length limit ...]"
        print_progress("WRITE", f"  Body truncated: {len(body)} -> {len(body_truncated)} chars")

    update_data = {
        "邮件主题": subject,
        "开发信": body_truncated,
    }
    update_json = json.dumps(update_data, ensure_ascii=False)

    result = _run_lark_cli([
        "base", "+record-upsert",
        "--base-token", base_token,
        "--table-id", table_id,
        "--record-id", record_id,
        "--as", identity,
        "--json", update_json,
    ], timeout=30)

    if not result or result.returncode != 0:
        stderr = (result.stderr or "")[:300] if result else "no response"
        return False, stderr

    try:
        data = json.loads(result.stdout)
        if not data.get("ok"):
            err = data.get("error", "unknown error")
            return False, str(err)
    except (json.JSONDecodeError, TypeError):
        return False, f"parse error: {(result.stdout or '')[:200]}"

    return True, ""


def batch_write_emails(base_token, table_id, results, identity, dry_run=False):
    """Write multiple email results to Feishu table.

    Args:
        base_token: Feishu base token
        table_id: Feishu table ID
        results: list of result dicts from generate_emails()
        identity: 'user' or 'bot'
        dry_run: If True, skip actual writes

    Returns (success_count, total_count).
    """
    if not results:
        return 0, 0

    success_count = 0

    for i, result in enumerate(results):
        if not result.get("success"):
            print_progress("WRITE", f"[{i+1}/{len(results)}] SKIP: {result.get('company_name', '')} (generation failed)")
            continue

        company_name = result.get("company_name", "")
        record_id = result.get("record_id", "")
        subject = result.get("email_subject", "")
        body = result.get("email_body", "")

        ok, err = write_email_to_feishu(
            base_token, table_id, record_id, subject, body, identity, dry_run
        )

        if ok:
            success_count += 1
            print_progress("WRITE", f"[{i+1}/{len(results)}] OK: {company_name}")
        else:
            print_progress("WRITE", f"[{i+1}/{len(results)}] FAILED: {company_name} - {err[:100]}")

        # Rate limiting: 1 second between writes
        if i < len(results) - 1:
            time.sleep(1)

    print_progress("WRITE", f"Done. {success_count}/{len(results)} emails written.")
    return success_count, len(results)
