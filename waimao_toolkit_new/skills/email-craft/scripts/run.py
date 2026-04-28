"""Email Craft Skill — main orchestrator (CLI entry point).

Generates personalized cold emails for customers from Feishu table.

Usage:
  python run.py --language en --all
  python run.py --language en --select recXXX,recYYY
  python run.py --dry-run --language en --select recXXX
  python run.py --setup
  python run.py --setup KEY=VALUE
  python run.py --check-auth
  python run.py --get-auth-url
  python run.py --show-config
  python run.py --save-feishu-link "https://xxx.feishu.cn/base/..."
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Import shared setup_env module
_SHARED_DIR = Path(__file__).resolve().parents[2] / "_shared"  # scripts -> email-craft -> skills -> _shared
sys.path.insert(0, str(_SHARED_DIR))
from setup_env import check_setup, write_env_var, get_auth_url  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    load_env, read_json, print_progress, print_error,
    check_lark_auth, parse_feishu_link, load_config, save_config,
    detect_ca_config, sync_config, load_reference_emails, ensure_fields,
    get_current_config, add_to_history,
    DEFAULT_PROFILE_PATH, PROJECT_ROOT,
)
from read_feishu import read_records, print_records_table
from generate_emails import generate_emails
from write_feishu import batch_write_emails
from csv_io import read_csv_records, write_csv_emails, print_csv_records_table


# ---------------------------------------------------------------------------
# Identity resolution
# ---------------------------------------------------------------------------

def get_identity():
    """Get the current lark-cli identity."""
    from utils import _run_lark_cli
    result = _run_lark_cli(["auth", "status"], timeout=10)
    if result and result.returncode == 0:
        try:
            return json.loads(result.stdout).get("identity", "user")
        except (json.JSONDecodeError, TypeError):
            pass
    return "user"


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------

def resolve_config(args):
    """Resolve base_token and table_id from args, config files, or CA config.

    Returns (base_token, table_id, config_dict) or exits on failure.
    Priority:
      1. Explicit --base-token + --table-id
      2. Explicit --feishu-link
      3. email-craft config.json
      4. customer-acquisition config.json (auto-detect within 24h)
    """
    # 1. Explicit --base-token + --table-id
    if args.base_token and args.table_id:
        config = load_config()
        config["current"]["base_token"] = args.base_token
        config["current"]["table_id"] = args.table_id
        save_config(config)
        return args.base_token, args.table_id, config

    # 2. Explicit --feishu-link
    if args.feishu_link:
        parsed, error = parse_feishu_link(args.feishu_link)
        if error:
            print_error(error)
            sys.exit(1)
        config = load_config()
        config["current"].update(parsed)
        config["current"]["last_used"] = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_config(config)
        return parsed["base_token"], parsed["table_id"], config

    # 3. email-craft config.json
    config = load_config()
    current = get_current_config(config)
    if current.get("base_token") and current.get("table_id"):
        return current["base_token"], current["table_id"], config

    # 4. Auto-detect CA config
    ca_config, msg = detect_ca_config()
    if ca_config:
        print_progress("CONFIG", f"Auto-detected customer-acquisition table: {ca_config.get('table_name', '')}")
        config = sync_config(ca_config)
        current = get_current_config(config)
        return current["base_token"], current["table_id"], config

    # Failed
    print_error("No Feishu table configured.")
    print_error("Please provide one of:")
    print_error("  --feishu-link LINK")
    print_error("  --base-token TOKEN --table-id ID")
    print_error(f"Or use --save-feishu-link to save a table for future use.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Profile loading
# ---------------------------------------------------------------------------

def load_profile(args):
    """Load company profile from specified path or auto-detect."""
    profile_path = args.profile
    if not profile_path and DEFAULT_PROFILE_PATH.exists():
        profile_path = str(DEFAULT_PROFILE_PATH)

    if not profile_path:
        print_error("No company profile found. Run company-profile skill first.")
        sys.exit(1)

    try:
        profile = read_json(profile_path)
        if not profile.get("company_name"):
            print_error(f"Profile missing 'company_name': {profile_path}")
            sys.exit(1)
        print_progress("PROFILE", f"Loaded: {profile.get('company_name', '')}")
        return profile
    except Exception as e:
        print_error(f"Failed to load profile: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def print_summary(results, written_count, dry_run, source="Feishu table"):
    """Print a summary of email generation results."""
    total = len(results)
    success = sum(1 for r in results if r["success"])
    failed = total - success

    print(f"\n{'='*60}")
    print(f"  EMAIL CRAFT — SUMMARY")
    print(f"{'='*60}")
    print(f"  Generated: {success}/{total}")
    print(f"  Failed:    {failed}")
    if not dry_run:
        print(f"  Written:   {written_count}/{success}")
    else:
        print(f"  Mode:      DRY RUN (nothing written)")
    print(f"{'='*60}")

    # Show first 3 successful emails
    shown = 0
    for r in results:
        if not r["success"]:
            continue
        if shown >= 3:
            break
        shown += 1
        print(f"\n--- Email {shown}: {r['company_name']} ---")
        print(f"Subject: {r['email_subject']}")
        body_preview = r['email_body'][:200]
        if len(r['email_body']) > 200:
            body_preview += "..."
        print(f"Body:\n{body_preview}")
        print()

    if total > 3:
        print(f"  ... and {success - 3} more emails in {source}.")


# ---------------------------------------------------------------------------
# Industry keyword extraction
# ---------------------------------------------------------------------------

def extract_industry_keyword(records, fallback_name=""):
    """Extract the most common industry value from records as a label keyword.

    Takes the most frequent non-empty 'industry' field, truncated to 10 chars.
    Falls back to table_name if no industry data found.
    """
    industries = []
    for r in records:
        val = r.get("industry", "").strip()
        if val:
            industries.append(val)

    if industries:
        counter = Counter(industries)
        keyword = counter.most_common(1)[0][0]
        return keyword[:10]

    return fallback_name[:10] if fallback_name else ""


# ---------------------------------------------------------------------------
# CSV flow (Feishu bypass)
# ---------------------------------------------------------------------------

def _run_csv_flow(args):
    """Run email generation using CSV as data source instead of Feishu."""
    csv_path = args.csv
    if not os.path.isfile(csv_path):
        print_error(f"CSV file not found: {csv_path}")
        sys.exit(1)

    # 1. Load env (needed for REPLICATE_API_TOKEN)
    load_env()

    # 2. Load profile
    profile = load_profile(args)

    # 3. Load reference emails
    references = load_reference_emails()
    if references:
        print_progress("REFS", f"Loaded {len(references)} reference email(s)")
        for ref in references:
            print_progress("REFS", f"  - {ref['filename']} ({ref['language']})")

    # 4. Read records from CSV
    skip_with_draft = not args.regenerate
    try:
        all_records = read_csv_records(csv_path, skip_with_draft=skip_with_draft)
    except FileNotFoundError:
        print_error(f"CSV file not found: {csv_path}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Failed to read CSV: {e}")
        sys.exit(1)

    if not all_records:
        print_progress("READ", "No records found (all may already have email drafts).")
        sys.exit(0)

    print_progress("CSV", f"Loaded {len(all_records)} record(s) from {csv_path}")

    # 5. Customer selection
    target_records = None

    if args.select:
        select_ids = set(args.select.split(","))
        target_records = [r for r in all_records if r["_record_id"] in select_ids]
        if not target_records:
            print_error("None of the specified record IDs found in CSV.")
            sys.exit(1)
        print_progress("SELECT", f"Selected {len(target_records)} record(s) via --select")

    elif args.regenerate:
        regen_ids = set(args.regenerate.split(","))
        # Read all records (including those with drafts) for regeneration
        all_with_drafts = read_csv_records(csv_path, skip_with_draft=False)
        target_records = [r for r in all_with_drafts if r["_record_id"] in regen_ids]
        if not target_records:
            print_error("None of the specified record IDs found in CSV.")
            sys.exit(1)
        print_progress("REGEN", f"Regenerating {len(target_records)} record(s)")

    elif args.all:
        target_records = all_records
        print_progress("SELECT", f"Processing all {len(target_records)} record(s)")

    else:
        # Interactive mode: print list and exit
        print_csv_records_table(all_records)
        print("No --all or --select specified. Exiting after showing customer list.")
        print("Use --all to generate for all, or --select 0,1,2 for specific rows.")
        sys.exit(0)

    # 6. Generate emails
    print(f"\nGenerating {len(target_records)} email(s) in {args.language}...")
    results = generate_emails(target_records, profile, language=args.language, references=references)

    # 7. Write back to CSV
    if args.dry_run:
        written_count = 0
        print("\n[DRY RUN] Emails generated but NOT written to CSV.")
    else:
        written_count = write_csv_emails(csv_path, results, dry_run=False)
        print_progress("WRITE", f"Wrote {written_count} email(s) to {csv_path}")

    # 8. Print summary
    print_summary(results, written_count, args.dry_run, source="CSV")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Email Craft Skill — personalized cold email generation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py --language en --all
  python run.py --language en --select recXXX,recYYY
  python run.py --dry-run --language en --select recXXX
  python run.py --regenerate recXXX,recYYY --language en
  python run.py --check-auth
  python run.py --show-config
  python run.py --save-feishu-link "https://xxx.feishu.cn/base/TOKEN?table=ID"
        """,
    )

    # Data source
    data_src = parser.add_argument_group("Data source")
    data_src.add_argument("--csv", metavar="FILE", help="Read customers from CSV file (bypasses Feishu)")
    data_src.add_argument("--feishu-link", metavar="LINK", help="Feishu table link")
    data_src.add_argument("--base-token", metavar="TOKEN", help="Base token (overrides config)")
    data_src.add_argument("--table-id", metavar="ID", help="Table ID (overrides config)")
    data_src.add_argument("--label", metavar="LABEL", help="Table label for history (e.g. '美国吊顶公司')")

    # Options
    opts = parser.add_argument_group("Options")
    opts.add_argument("--language", choices=["en", "cn"], default="en",
                      help="Email language (default: en)")
    opts.add_argument("--profile", metavar="PATH", help="Path to profile.json")
    opts.add_argument("--dry-run", action="store_true",
                      help="Generate emails but don't write to Feishu")
    opts.add_argument("--all", action="store_true",
                      help="Generate for all customers without email drafts")
    opts.add_argument("--select", metavar="rec1,rec2",
                      help="Generate for specific record IDs (comma-separated)")
    opts.add_argument("--regenerate", metavar="rec1,rec2",
                      help="Regenerate for specific record IDs (ignore existing drafts)")

    # Utilities
    utils_grp = parser.add_argument_group("Utilities")
    utils_grp.add_argument("--setup", nargs="*", metavar="KEY=VALUE",
                           help="Check env vars (--setup) or write values (--setup KEY=VALUE)")
    utils_grp.add_argument("--check-auth", action="store_true", help="Check lark-cli auth status")
    utils_grp.add_argument("--get-auth-url", action="store_true", help="Get Feishu device-flow auth URL (non-blocking)")
    utils_grp.add_argument("--show-config", action="store_true", help="Show current config")
    utils_grp.add_argument("--save-feishu-link", metavar="LINK", help="Save a Feishu table link")

    args = parser.parse_args()

    # ===================================================================
    # Utility modes
    # ===================================================================

    if args.setup is not None:
        _SKILL_DIR = Path(__file__).resolve().parents[1]  # scripts -> email-craft
        if args.setup:
            for kv in args.setup:
                k, _, v = kv.partition("=")
                if k and v:
                    write_env_var(PROJECT_ROOT, k.strip(), v.strip())
        result = check_setup(PROJECT_ROOT, "email-craft", skill_dir=_SKILL_DIR)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result["status"] == "ok" else 1)

    if args.check_auth:
        ok, msg = check_lark_auth()
        if ok:
            print(f"OK: {msg}")
        else:
            print(f"NOT OK: {msg}")
        sys.exit(0 if ok else 1)

    if args.get_auth_url:
        result = get_auth_url()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("ok"):
            print(f"\n请在浏览器中打开上面的链接完成授权（有效期 {result.get('expires_in', 600)} 秒）")
            print("授权完成后，运行 --check-auth 确认状态")
        sys.exit(0 if result.get("ok") else 1)

    if args.show_config:
        config = load_config()
        current = get_current_config(config)
        history = config.get("history", [])

        if current.get("base_token"):
            print(f"Current table: {current.get('table_name', '(unnamed)')}")
            print(f"  base_token: {current['base_token']}")
            print(f"  table_id:   {current['table_id']}")
            if current.get("table_link"):
                print(f"  link:       {current['table_link']}")
            if current.get("label"):
                print(f"  label:      {current['label']}")
            if current.get("source"):
                print(f"  source:     {current['source']}")
            if current.get("last_used"):
                print(f"  last_used:  {current['last_used']}")

            if history:
                print(f"\nTable history ({len(history)} entries):")
                for i, h in enumerate(history, 1):
                    label = h.get("label", h.get("table_name", ""))
                    print(f"  #{i}  {label}  ({h.get('table_id', '')[:16]}..., {h.get('last_used', '')})")
        else:
            print("No Feishu table configured yet.")
            # Check CA config
            ca_config, msg = detect_ca_config()
            if ca_config:
                print(f"\nAuto-detectable: {ca_config.get('table_name', '')}")
                print(f"  base_token: {ca_config['base_token']}")
                print(f"  table_id:   {ca_config['table_id']}")
                print(f"  (run without --feishu-link to auto-use)")
            else:
                print(f"CA config: {msg}")
        sys.exit(0)

    if args.save_feishu_link:
        parsed, error = parse_feishu_link(args.save_feishu_link)
        if error:
            print(f"ERROR: {error}")
            sys.exit(1)
        config = load_config()
        config["current"].update(parsed)
        config["current"]["last_used"] = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_config(config)
        print(f"OK: Feishu table link saved.")
        print(f"  base_token: {parsed['base_token']}")
        print(f"  table_id:   {parsed['table_id']}")
        sys.exit(0)

    # ===================================================================
    # CSV flow (bypasses Feishu entirely)
    # ===================================================================

    if args.csv:
        _run_csv_flow(args)
        return

    # ===================================================================
    # Main flow (Feishu)
    # ===================================================================

    # 1. Load env
    load_env()

    # 2. Check auth
    auth_ok, auth_msg = check_lark_auth()
    if not auth_ok:
        print_error(f"Feishu auth failed: {auth_msg}")
        print_error("Run: lark-cli auth login --recommend")
        sys.exit(1)
    identity = get_identity()
    print_progress("AUTH", f"OK: {auth_msg}")

    # 3. Resolve config
    base_token, table_id, config = resolve_config(args)
    current = get_current_config(config)
    print_progress("CONFIG", f"Table: {current.get('table_name', '(unnamed)')}")

    # 4. Ensure fields exist
    ensure_fields(base_token, table_id, identity)

    # 5. Load profile
    profile = load_profile(args)

    # 6. Load reference emails
    references = load_reference_emails()
    if references:
        print_progress("REFS", f"Loaded {len(references)} reference email(s)")
        for ref in references:
            print_progress("REFS", f"  - {ref['filename']} ({ref['language']})")

    # 7. Read records
    skip_with_draft = not args.regenerate  # --regenerate mode: don't skip
    all_records = read_records(base_token, table_id, identity, skip_with_draft=skip_with_draft)

    if not all_records:
        print_progress("READ", "No records found (all may already have email drafts).")
        sys.exit(0)

    # 7b. Save to history with label
    if args.label:
        keyword = args.label.strip()
    else:
        keyword = extract_industry_keyword(all_records, current.get("table_name", ""))
    today = datetime.now().strftime("%Y-%m-%d")
    label = f"{keyword}_{today}" if keyword else today
    add_to_history(config, label=label)
    print_progress("HISTORY", f"Table saved to history: {label}")

    # 8. Customer selection
    target_records = None

    if args.select:
        # Specific record IDs
        select_ids = set(args.select.split(","))
        target_records = [r for r in all_records if r["_record_id"] in select_ids]
        if not target_records:
            print_error(f"None of the specified record IDs found in the table.")
            sys.exit(1)
        print_progress("SELECT", f"Selected {len(target_records)} record(s) via --select")

    elif args.regenerate:
        # Regenerate specific record IDs
        regen_ids = set(args.regenerate.split(","))
        target_records = [r for r in all_records if r["_record_id"] in regen_ids]
        if not target_records:
            # Also try reading with skip_with_draft=False to find the records
            all_with_drafts = read_records(base_token, table_id, identity, skip_with_draft=False)
            target_records = [r for r in all_with_drafts if r["_record_id"] in regen_ids]
        if not target_records:
            print_error(f"None of the specified record IDs found in the table.")
            sys.exit(1)
        print_progress("REGEN", f"Regenerating {len(target_records)} record(s)")

    elif args.all:
        # All records without drafts
        target_records = all_records
        print_progress("SELECT", f"Processing all {len(target_records)} record(s)")

    else:
        # Interactive mode: print list and exit (Claude will handle selection)
        print_records_table(all_records)
        print("\nNo --all or --select specified. Exiting after showing customer list.")
        print("Use --all to generate for all, or --select rec1,rec2 for specific records.")
        sys.exit(0)

    # 9. Generate emails
    print(f"\nGenerating {len(target_records)} email(s) in {args.language}...")
    results = generate_emails(target_records, profile, language=args.language, references=references)

    # 10. Write to Feishu
    if args.dry_run:
        written_count = 0
        print("\n[DRY RUN] Emails generated but NOT written to Feishu.")
    else:
        written_count, _ = batch_write_emails(base_token, table_id, results, identity)

    # 11. Print summary
    print_summary(results, written_count, args.dry_run)


if __name__ == "__main__":
    main()
