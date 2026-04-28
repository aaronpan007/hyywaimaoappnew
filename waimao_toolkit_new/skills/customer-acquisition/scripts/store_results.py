"""Phase 4: Store analyzed results to Feishu via lark-cli, DingTalk, or export CSV."""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import load_env, read_json, print_progress, print_error

# lark-cli record-batch-create field order (must match Feishu base table)
FEISHU_FIELDS = [
    "公司名称", "网站", "国家/地区", "行业", "公司角色",
    "联系人", "邮箱", "电话",
    "AI分析摘要", "业务匹配点", "开发建议",
    "邮件已发送", "发送时间", "备注",
]

# Mapping from flat record keys to Feishu field names
FIELD_MAPPING = [
    ("company_name", "公司名称"),
    ("website", "网站"),
    ("country", "国家/地区"),
    ("industry", "行业"),
    ("company_role", "公司角色"),
    ("contact_name", "联系人"),
    ("email", "邮箱"),
    ("phone", "电话"),
    ("ai_summary", "AI分析摘要"),
    ("business_match_points", "业务匹配点"),
    ("outreach_content", "开发建议"),
    ("email_sent", "邮件已发送"),
    ("sent_time", "发送时间"),
    ("notes", "备注"),
]


def _get_lark_cli_cmd():
    """Get the Node.js command to run lark-cli, bypassing the .CMD wrapper."""
    npm_dir = os.path.join(os.environ.get("APPDATA", ""), "npm")
    run_js = os.path.join(npm_dir, "node_modules", "@larksuite", "cli", "scripts", "run.js")
    if os.path.isfile(run_js):
        return ["node", run_js]
    return None


def _run_lark_cli(args, timeout=30, stdin_data=None):
    """Run a lark-cli command via Node.js directly, bypassing .CMD issues."""
    cmd = _get_lark_cli_cmd()
    if not cmd:
        raise FileNotFoundError("lark-cli not found")
    full_cmd = cmd + args
    # Force UTF-8 encoding on Windows to handle Chinese characters
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    return subprocess.run(full_cmd, input=stdin_data, capture_output=True, timeout=timeout,
                         encoding="utf-8", errors="replace", env=env)


def check_lark_cli():
    """Check if lark-cli is installed and authenticated."""
    try:
        result = _run_lark_cli(["--version"], timeout=10)
        if result.returncode != 0:
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

    try:
        result = _run_lark_cli(["auth", "status"], timeout=10)
        if result.returncode != 0:
            return False
        data = json.loads(result.stdout)
        identity = data.get("identity", "")
        if identity not in ("user", "bot"):
            return False
    except (json.JSONDecodeError, subprocess.TimeoutExpired):
        return False

    return True


def record_to_row(record):
    """Convert a flat record dict to a row array matching FEISHU_FIELDS order."""
    row = []
    for key, _ in FIELD_MAPPING:
        value = record.get(key, "")
        if isinstance(value, bool):
            row.append(value)
        elif isinstance(value, str):
            row.append(value if value else None)
        else:
            row.append(value if value else None)
    return row


def store_to_feishu(records, dry_run=False):
    """Store records to Feishu multi-dimensional table via lark-cli."""
    config_path = Path(__file__).parent / "config.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print_error(f"Failed to read config.json: {e}")
        return False

    app_token = config.get("base_token", "")
    table_id = config.get("table_id", "")

    if not app_token or not table_id:
        print_error("base_token or table_id not set in config.json")
        return False

    if not check_lark_cli():
        print_error("lark-cli not installed or not authenticated. Run: lark-cli auth login --recommend")
        return False

    # Check auth identity to decide --as flag
    try:
        result = _run_lark_cli(["auth", "status"], timeout=10)
        auth_data = json.loads(result.stdout)
        identity = auth_data.get("identity", "user")
    except Exception:
        identity = "user"

    print_progress("STORE", f"Using lark-cli with identity: {identity}")

    # Build batch rows
    rows = [record_to_row(r) for r in records]

    if dry_run:
        for i, record in enumerate(records):
            name = record.get("company_name", f"Record {i+1}")[:40]
            print_progress("STORE", f"  [Feishu DRY-RUN {i+1}] {name}")
        print_progress("STORE", f"  Batch JSON: fields={len(FEISHU_FIELDS)}, rows={len(rows)}")
        return True

    # Send records one by one using +record-batch-create shortcut
    success_count = 0
    for i, row in enumerate(rows):
        # Truncate long values to stay within command line limits (~8KB on Windows)
        truncated_row = []
        for val in row:
            if isinstance(val, str) and len(val) > 4000:
                val = val[:4000] + "..."
            truncated_row.append(val)

        record_json = json.dumps({"fields": FEISHU_FIELDS, "rows": [truncated_row]}, ensure_ascii=False)
        name = records[i].get("company_name", f"Record {i+1}")[:40]

        # Retry up to 2 times with backoff for rate limits
        for attempt in range(3):
            try:
                result = _run_lark_cli([
                    "base", "+record-batch-create",
                    "--as", identity,
                    "--base-token", app_token,
                    "--table-id", table_id,
                    "--json", record_json,
                ], timeout=30)

                output = result.stdout.strip()

                if not output:
                    stderr = result.stderr.strip()[:200]
                    print_error(f"  [{i+1}] No output for {name} (rc={result.returncode}, stderr={stderr})")
                    break

                try:
                    resp_data = json.loads(output)
                except json.JSONDecodeError:
                    print_error(f"  [{i+1}] Non-JSON output for {name}: {output[:100]}")
                    break

                if resp_data.get("ok"):
                    rids = resp_data.get("data", {}).get("record_id_list", [])
                    rid = rids[0] if rids else "?"
                    print_progress("STORE", f"  [Feishu {i+1}/{len(records)}] OK: {name} -> {rid}")
                    success_count += 1
                    break
                else:
                    error = resp_data.get("error", {})
                    code = error.get("code", "")
                    msg = error.get("message", output[:150])
                    if code in (800004135, 99991668, 99991672) and attempt < 2:
                        wait = 2 ** (attempt + 1)
                        print_progress("STORE", f"  [{i+1}] Rate limited, retrying in {wait}s...")
                        time.sleep(wait)
                        continue
                    print_error(f"  [Feishu {i+1}/{len(records)}] Failed: {msg} (code: {code})")
                    break

            except subprocess.TimeoutExpired:
                print_error(f"  [Feishu {i+1}/{len(records)}] Timeout: {name}")
                break
            except Exception as e:
                print_error(f"  [Feishu {i+1}/{len(records)}] Error: {str(e)[:200]}")
                break

        # Rate limit: wait between records
        if i < len(rows) - 1:
            time.sleep(1)

    print_progress("STORE", f"Feishu: {success_count}/{len(records)} records stored")
    return success_count > 0


def store_to_dingtalk(records, dry_run=False):
    """Store records to DingTalk smart table via dws CLI."""
    base_id = os.environ.get("DINGTALK_BASE_ID")
    table_id = os.environ.get("DINGTALK_TABLE_ID")

    if not base_id or not table_id:
        print_error("DINGTALK_BASE_ID or DINGTALK_TABLE_ID not set in .env")
        return False

    try:
        subprocess.run(["dws", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_error("dws CLI not found. Install it first: https://open.dingtalk.com/")
        return False

    fields_json = json.dumps({
        "公司名称": "",
        "网站": "",
        "国家/地区": "",
        "行业": "",
        "公司角色": "",
        "联系人": "",
        "邮箱": "",
        "电话": "",
        "AI分析摘要": "",
        "业务匹配点": "",
        "开发建议": "",
        "邮件已发送": False,
        "发送时间": "",
        "备注": "",
    }, ensure_ascii=False)

    for i, record in enumerate(records):
        if dry_run:
            print_progress("STORE", f"  [DingTalk DRY-RUN {i+1}] {record.get('company_name', 'N/A')}")
            continue

        cmd = [
            "dws", "aitable", "record", "create",
            "--base-id", base_id,
            "--table-id", table_id,
            "--fields", fields_json,
            "--yes",
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                print_progress("STORE", f"  [DingTalk {i+1}] Stored: {record.get('company_name', 'N/A')}")
            else:
                print_error(f"  [DingTalk {i+1}] Failed: {result.stderr.strip()[:200]}")
        except subprocess.TimeoutExpired:
            print_error(f"  [DingTalk {i+1}] Timeout")
        except Exception as e:
            print_error(f"  [DingTalk {i+1}] Error: {str(e)[:200]}")

    return True


def export_csv(records, filepath):
    """Fallback: export records to CSV file."""
    if not records:
        print_error("No records to export.")
        return

    fieldnames = [
        "company_name", "website", "country", "industry", "company_role",
        "contact_name", "email", "phone",
        "ai_summary", "business_match_points", "outreach_content",
        "email_sent", "sent_time", "notes",
    ]

    headers_cn = [
        "公司名称", "网站", "国家/地区", "行业", "公司角色",
        "联系人", "邮箱", "电话",
        "AI分析摘要", "业务匹配点", "开发建议",
        "邮件已发送", "发送时间", "备注",
    ]

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writerow(dict(zip(fieldnames, headers_cn)))
        writer.writerows(records)

    print_progress("STORE", f"Exported {len(records)} records to CSV: {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Phase 4: Store results to Feishu/DingTalk/CSV")
    parser.add_argument("--input", required=True, help="Input JSON from Phase 3")
    parser.add_argument("--platform", choices=["feishu", "dingtalk", "csv"], default="csv",
                        help="Target platform (default: csv)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run without actually storing")
    parser.add_argument("--csv-output", default="customer_acquisition_results.csv", help="CSV output path")
    args = parser.parse_args()

    load_env()

    data = read_json(args.input)
    records = data.get("companies", [])

    print_progress("STORE", f"Loaded {len(records)} records from {args.input}")

    if args.platform == "feishu":
        success = store_to_feishu(records, dry_run=args.dry_run)
        if not success:
            print_progress("STORE", "Feishu storage failed. Falling back to CSV export.")
            export_csv(records, args.csv_output)

    elif args.platform == "dingtalk":
        success = store_to_dingtalk(records, dry_run=args.dry_run)
        if not success:
            print_progress("STORE", "DingTalk storage failed. Falling back to CSV export.")
            export_csv(records, args.csv_output)

    else:
        export_csv(records, args.csv_output)

    print_progress("STORE", "Done.")


if __name__ == "__main__":
    main()
