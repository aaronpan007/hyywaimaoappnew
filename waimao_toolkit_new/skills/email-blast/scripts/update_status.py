"""Update Feishu table with send status after each email."""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from utils import (
    get_feishu_config,
    run_lark_cli,
    print_progress,
)

# Import shared csv_utils
_SHARED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_shared")
sys.path.insert(0, _SHARED_DIR)
from csv_utils import update_csv_status  # noqa: E402


def update_send_status(record_id, success, message_id=None, error=None, email_subject=None):
    """Update a single record's send status in Feishu table.

    This is called immediately after each email send attempt, so the table
    always reflects the latest state even if the batch is interrupted.

    Args:
        record_id: Feishu record ID (recXXX).
        success: Whether the email was sent successfully.
        message_id: Resend message ID (if successful).
        error: Error message (if failed).
        email_subject: Email subject line (written back to table).

    Returns:
        (bool, str): (success, error_message)
    """
    config = get_feishu_config()
    if not config:
        return False, "未找到飞书表格配置"

    base_token = config["base_token"]
    table_id = config["table_id"]
    identity = config["identity"]

    update_data = {}

    if email_subject:
        update_data["邮件主题"] = email_subject

    if success:
        update_data["邮件已发送"] = "是"
        update_data["发送时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if message_id:
            update_data["备注"] = f"Resend ID: {message_id}"
    else:
        update_data["邮件已发送"] = "否"
        update_data["发送时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if error:
            update_data["备注"] = f"发送失败: {error}"

    update_json = json.dumps(update_data, ensure_ascii=False)

    result = run_lark_cli([
        "base", "+record-upsert",
        "--base-token", base_token,
        "--table-id", table_id,
        "--record-id", record_id,
        "--as", identity,
        "--json", update_json,
    ], timeout=30)

    if result is None:
        return False, "lark-cli 无响应"

    if result.returncode != 0:
        stderr = result.stderr.strip() if result.stderr else ""
        stdout = result.stdout.strip() if result.stdout else ""
        err_msg = stderr or stdout or "未知错误"
        return False, f"飞书更新失败: {err_msg[:200]}"

    return True, ""


def make_status_callback():
    """Create a callback function for use with send_emails.send_batch().

    The callback updates Feishu table status after each email.
    """
    def callback(record, result):
        """Called after each email send attempt."""
        record_id = record.get("_record_id", "")
        success = result.get("success", False)
        message_id = result.get("message_id")
        error = result.get("error")
        skipped = result.get("skipped", False)
        email_subject = record.get("email_subject", "")

        if skipped:
            # Don't update status for skipped emails
            return

        ok, err = update_send_status(record_id, success, message_id, error, email_subject)
        if ok:
            print_progress("STATUS", f"  ✅ 状态已更新: {record_id}")
        else:
            print_progress("STATUS", f"  ⚠️ 状态更新失败: {record_id} - {err}")

    return callback


def make_csv_status_callback(csv_path):
    """Create a status callback that writes send status back to a CSV file.

    Used with send_emails.send_batch() when sending from a pipeline CSV.
    Extracts the row index from the record's _record_id field.
    """
    def callback(record, result):
        """Called after each email send attempt."""
        record_id = record.get("_record_id", "")
        success = result.get("success", False)
        message_id = result.get("message_id")
        error = result.get("error")
        skipped = result.get("skipped", False)

        if skipped:
            return

        # Extract row_index from _record_id (format: "csv_N" or "N")
        try:
            row_index = int(record_id.replace("csv_", ""))
        except (ValueError, TypeError):
            print_progress("STATUS", f"  warning: cannot parse row index from {record_id}")
            return

        ok = update_csv_status(csv_path, row_index, success, message_id, error)
        if ok:
            print_progress("STATUS", f"  CSV updated: row {row_index}")
        else:
            print_progress("STATUS", f"  CSV update failed: row {row_index}")

    return callback


def format_send_report(batch_result, source="飞书表格"):
    """Format the batch send result as a readable report."""
    success = batch_result["success_count"]
    fail = batch_result["fail_count"]
    skip = batch_result["skip_count"]
    results = batch_result["results"]

    lines = []
    lines.append("")
    lines.append("📊 发送结果报告")
    lines.append("━" * 50)
    lines.append(f"✅ 成功: {success} 封")
    lines.append(f"❌ 失败: {fail} 封")
    lines.append(f"⏭️  跳过: {skip} 封（不在发送时间窗口）")
    lines.append("")

    # Failed details
    failed = [r for r in results if not r.get("success") and not r.get("skipped")]
    if failed:
        lines.append("失败明细:")
        for r in failed:
            company = r.get("company", "未知")
            email = r.get("email", "")
            error = r.get("error", "未知错误")
            lines.append(f"  {company} ({email}) — {error}")
        lines.append("")

    # Skipped details
    skipped_list = [r for r in results if r.get("skipped")]
    if skipped_list:
        lines.append("跳过明细:")
        for r in skipped_list:
            email = r.get("email", "")
            reason = r.get("error", "")
            lines.append(f"  {email} — {reason}")
        lines.append("")

    lines.append("━" * 50)
    lines.append(f"{source}状态已更新。")

    return "\n".join(lines)
