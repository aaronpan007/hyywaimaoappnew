#!/usr/bin/env python3
"""Email Blast Skill — Main orchestrator (CLI entry point).

Usage:
    python run.py --check-env                  # Pre-flight environment check
    python run.py --list-pending               # List pending emails
    python run.py --list-pending --include-failed  # Include previously failed
    python run.py --stats                      # Today's send statistics
    python run.py --dry-run                    # Preview mode (no actual sending)
    python run.py --retry-failed               # Retry failed emails
    python run.py --select recXXX,recYYY       # Send specific records
    python run.py --all                        # Send all pending
    python run.py --csv path/to/file.csv       # Send from CSV file

    # Sending parameters:
    python run.py --all --batch-size 10 --delay-min 60 --delay-max 120 --daily-limit 50
    python run.py --all --send-mode immediate  # Ignore timezone
    python run.py --all --no-random            # Fixed delay (no randomization)
"""

import argparse
import csv
import os
import sys
import json

# Import shared setup_env module
_SHARED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_shared")
sys.path.insert(0, _SHARED_DIR)
from setup_env import check_setup, write_env_var  # noqa: E402

# Ensure scripts directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import print_progress, get_feishu_config, save_feishu_config, get_ec_table_history, parse_feishu_link
from check_env import run_check
from read_pending import read_pending_records, format_pending_preview, get_today_sent_count
from send_emails import send_batch, validate_email
from update_status import make_status_callback, make_csv_status_callback, format_send_report


def cmd_check_env(args):
    """Run environment pre-check."""
    run_check()


def cmd_list_tables(args):
    """List available tables from email-craft history."""
    tables = get_ec_table_history()

    if not tables:
        print("📭 没有找到可用的发信表格。")
        print("   请先使用 email-craft 生成开发信，或使用 --feishu-link 指定表格。")
        return

    print("📋 可用的发信表格（来自 email-craft）:")
    print("━" * 60)
    for i, t in enumerate(tables, 1):
        label = t.get("label", t.get("table_name", "(unnamed)"))
        table_id = t.get("table_id", "")[:16]
        last_used = t.get("last_used", "")
        # Format last_used for display
        if last_used and len(last_used) == 15 and "_" in last_used:
            try:
                from datetime import datetime
                dt = datetime.strptime(last_used, "%Y%m%d_%H%M%S")
                last_used = dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass
        source = t.get("source", "")
        print(f"  #{i:<3} {label:<30} ({table_id}..., {last_used})")
    print("━" * 60)
    print(f"\n使用 --table N 选择表格，或 --feishu-link LINK 指定其他表格。")


def cmd_list_pending(args):
    """List pending emails."""
    select_ids = None
    if args.select:
        select_ids = [s.strip() for s in args.select.split(",")]

    records = read_pending_records(
        select_ids=select_ids,
        include_failed=args.include_failed,
    )

    print(format_pending_preview(records))
    return records


def cmd_stats(args):
    """Show today's sending statistics."""
    today_count = get_today_sent_count()
    pending = read_pending_records()

    print("")
    print("📊 今日发送统计")
    print("━" * 40)
    print(f"  今日已发送: {today_count} 封")
    print(f"  待发送: {len(pending)} 封")
    print(f"  每日上限: {args.daily_limit} 封")
    print(f"  剩余额度: {max(0, args.daily_limit - today_count)} 封")
    print("━" * 40)


def cmd_send(args):
    """Execute email sending."""
    # Determine which records to send
    if args.retry_failed:
        print_progress("SEND", "重发之前失败的邮件...")
        records = read_pending_records(include_failed=True)
        # Filter to only previously failed records
        records = [r for r in records if "发送失败" in r.get("notes", "")]
        if not records:
            print("📭 没有需要重发的失败记录。")
            return
    elif args.pipeline_csv:
        records = load_pipeline_csv(args.pipeline_csv)
        if not records:
            print("Pipeline CSV 中没有待发送的邮件。")
            return
    elif args.csv:
        records = load_csv(args.csv)
        if not records:
            print("CSV 文件为空或格式不正确。")
            return
    elif args.select:
        select_ids = [s.strip() for s in args.select.split(",")]
        records = read_pending_records(select_ids=select_ids)
    else:
        records = read_pending_records()

    if not records:
        print("📭 没有待发送的邮件。请先使用 email-craft 生成开发信。")
        return

    # Show preview
    print(format_pending_preview(records))

    if args.dry_run:
        print("\n🔍 预演模式 — 不会实际发送邮件\n")

    # Determine delay parameters
    delay_min = args.delay_min
    delay_max = args.delay_max
    if args.no_random:
        delay_min = args.delay_min
        delay_max = args.delay_min  # Same min and max = no randomization

    # Determine send mode
    send_mode = args.send_mode

    # Create status callback
    if args.dry_run:
        status_callback = None
    elif args.pipeline_csv:
        status_callback = make_csv_status_callback(args.pipeline_csv)
    else:
        status_callback = make_status_callback()

    # Execute batch send
    batch_result = send_batch(
        records=records,
        dry_run=args.dry_run,
        delay_min=delay_min,
        delay_max=delay_max,
        daily_limit=args.daily_limit,
        send_mode=send_mode,
        on_status_update=status_callback,
    )

    # Print report
    source = "CSV" if args.pipeline_csv else "飞书表格"
    print(format_send_report(batch_result, source=source))

    # Save result summary
    if not args.dry_run:
        result_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "last_send_result.json")
        # Don't save email bodies in result (too large), just summary
        summary = {
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "success_count": batch_result["success_count"],
            "fail_count": batch_result["fail_count"],
            "skip_count": batch_result["skip_count"],
            "results": [
                {
                    "record_id": r.get("record_id"),
                    "email": r.get("email"),
                    "company": r.get("company"),
                    "success": r.get("success"),
                    "message_id": r.get("message_id"),
                    "error": r.get("error"),
                    "skipped": r.get("skipped", False),
                }
                for r in batch_result["results"]
            ],
        }
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"\n💾 发送记录已保存: {result_path}")


def load_csv(csv_path):
    """Load email records from a CSV file.

    Required columns: email, subject, body
    Optional columns: company_name, contact_name, country
    """
    records = []
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                email = row.get("email", "").strip()
                subject = row.get("subject", "").strip()
                body = row.get("body", "").strip()

                if not email or not subject or not body:
                    print(f"⚠️ 跳过第 {i+2} 行: 邮箱/主题/正文不完整")
                    continue

                if not validate_email(email):
                    print(f"⚠️ 跳过第 {i+2} 行: 邮箱格式无效 ({email})")
                    continue

                records.append({
                    "_record_id": f"csv_{i}",
                    "email": email,
                    "email_subject": subject,
                    "email_draft": body,
                    "company_name": row.get("company_name", "").strip(),
                    "contact_name": row.get("contact_name", "").strip(),
                    "country": row.get("country", "").strip(),
                })
    except FileNotFoundError:
        print(f"❌ 文件不存在: {csv_path}")
    except Exception as e:
        print(f"❌ 读取 CSV 失败: {e}")

    print_progress("CSV", f"从 {csv_path} 加载了 {len(records)} 条记录")
    return records


def load_pipeline_csv(csv_path):
    """Load email records from a pipeline CSV (customer-acquisition → email-craft format).

    Required columns: email, email_subject (邮件主题), email_draft (开发信)
    Optional columns: company_name, contact_name, country

    Uses the shared csv_utils module for schema-aware reading.
    """
    _SHARED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_shared")
    if _SHARED_DIR not in sys.path:
        sys.path.insert(0, _SHARED_DIR)
    from csv_utils import read_pipeline_csv

    records = []
    try:
        all_rows = read_pipeline_csv(csv_path, skip_with_draft=False)
    except FileNotFoundError:
        print(f"CSV file not found: {csv_path}")
        return records
    except Exception as e:
        print(f"Failed to read pipeline CSV: {e}")
        return records

    for row in all_rows:
        email = row.get("email", "").strip()
        subject = row.get("email_subject", "").strip()
        draft = row.get("email_draft", "").strip()

        # Filter: must have email + subject + draft + not already sent
        if not email or not subject or not draft:
            continue

        # Skip already successfully sent
        if row.get("email_sent", "").strip() == "是":
            continue

        if not validate_email(email):
            print(f"  skipping row {row['_row_index']}: invalid email ({email})")
            continue

        records.append({
            "_record_id": str(row["_row_index"]),
            "email": email,
            "email_subject": subject,
            "email_draft": draft,
            "company_name": row.get("company_name", "").strip(),
            "contact_name": row.get("contact_name", "").strip(),
            "country": row.get("country", "").strip(),
        })

    print_progress("PIPELINE-CSV", f"从 {csv_path} 加载了 {len(records)} 条待发记录")
    return records


def main():
    parser = argparse.ArgumentParser(
        description="Email Blast Skill — 开发信批量发送与状态更新",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Mode selection
    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--check-env", action="store_true", help="环境预检")

    # Environment setup (not in mutually exclusive group — takes priority)
    parser.add_argument("--setup", nargs="*", metavar="KEY=VALUE",
                        help="检查环境变量 (--setup) 或写入值 (--setup KEY=VALUE)")
    mode.add_argument("--list-pending", action="store_true", help="列出待发送邮件")
    mode.add_argument("--list-tables", action="store_true", help="列出 email-craft 可用的发信表格")
    mode.add_argument("--stats", action="store_true", help="今日发送统计")
    mode.add_argument("--retry-failed", action="store_true", help="重发失败的邮件")
    mode.add_argument("--csv", type=str, help="从 CSV 文件发送")
    mode.add_argument("--pipeline-csv", type=str, help="从 pipeline CSV 发送（customer-acquisition → email-craft 导出的 CSV）")

    # Record selection
    parser.add_argument("--select", type=str, help="指定记录ID (逗号分隔, 如 recXXX,recYYY)")
    parser.add_argument("--all", action="store_true", help="发送所有待发送邮件")
    parser.add_argument("--include-failed", action="store_true", help="包含之前失败的记录")

    # Table selection (for choosing from email-craft history or direct link)
    parser.add_argument("--table", type=int, metavar="N", help="从 email-craft 历史中选择第 N 个表格")
    parser.add_argument("--feishu-link", type=str, metavar="LINK", help="直接指定飞书表格链接")

    # Sending parameters
    parser.add_argument("--batch-size", type=int, default=10, help="每批多少封 (默认: 10)")
    parser.add_argument("--delay-min", type=int, default=60, help="最小间隔秒数 (默认: 60)")
    parser.add_argument("--delay-max", type=int, default=120, help="最大间隔秒数 (默认: 120)")
    parser.add_argument("--daily-limit", type=int, default=50, help="每日发送上限 (默认: 50)")
    parser.add_argument("--send-mode", type=str, default="auto",
                       choices=["auto", "immediate"],
                       help="发送模式: auto=时区感知, immediate=立即发送")
    parser.add_argument("--no-random", action="store_true", help="禁用随机延迟")
    parser.add_argument("--dry-run", action="store_true", help="预演模式，不实际发送")

    args = parser.parse_args()

    # Route to appropriate command
    if args.setup is not None:
        from utils import PROJECT_DIR, SKILL_DIR
        if args.setup:
            for kv in args.setup:
                k, _, v = kv.partition("=")
                if k and v:
                    write_env_var(PROJECT_DIR, k.strip(), v.strip())
        result = check_setup(PROJECT_DIR, "email-blast", skill_dir=SKILL_DIR)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["status"] == "ok" else 1)

    if args.check_env:
        cmd_check_env(args)
    elif args.list_tables:
        cmd_list_tables(args)
    elif args.list_pending:
        cmd_list_pending(args)
    elif args.stats:
        cmd_stats(args)
    elif args.table or args.feishu_link:
        # Table selection mode: resolve table first, then proceed
        if args.table:
            # Select from email-craft history
            tables = get_ec_table_history()
            idx = args.table - 1  # 1-based to 0-based
            if idx < 0 or idx >= len(tables):
                print(f"❌ 无效的表格序号: {args.table} (共 {len(tables)} 个表格)")
                print("   运行 --list-tables 查看可用表格。")
                sys.exit(1)
            selected = tables[idx]
            label = selected.get("label", selected.get("table_name", ""))
            print(f"📋 已选择表格: {label}")
            save_feishu_config(selected["base_token"], selected["table_id"])
        elif args.feishu_link:
            # Parse feishu link directly
            parsed, error = parse_feishu_link(args.feishu_link)
            if error:
                print(f"❌ {error}")
                sys.exit(1)
            print(f"📋 已选择表格: {parsed['table_id']}")
            save_feishu_config(parsed["base_token"], parsed["table_id"])

        # After selecting table, show pending or send based on other args
        if args.dry_run or args.select or args.all or args.retry_failed:
            cmd_send(args)
        else:
            cmd_list_pending(args)
    elif args.select or args.all or args.retry_failed or args.csv or args.pipeline_csv or args.dry_run:
        cmd_send(args)
    else:
        # Default: list pending
        cmd_list_pending(args)


if __name__ == "__main__":
    main()
