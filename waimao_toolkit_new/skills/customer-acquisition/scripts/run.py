"""One-click orchestrator for Customer Acquisition Skill.

Modes:
  Pipeline:  python run.py --industry "LED" --country "USA" --num 30
  Setup env: python run.py --setup
  Setup env: python run.py --setup KEY=VALUE
  Check auth: python run.py --check-auth
  Get auth:   python run.py --get-auth-url
  Show config: python run.py --show-config
  Save link:  python run.py --save-feishu-link "https://xxx.feishu.cn/base/..."
  New table:  python run.py --create-table "客户获取列表"
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Import shared setup_env module
_SHARED_DIR = Path(__file__).resolve().parents[2] / "_shared"  # scripts -> customer-acquisition -> skills -> _shared
sys.path.insert(0, str(_SHARED_DIR))
from setup_env import check_setup, write_env_var, get_auth_url  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPTS_DIR.resolve().parents[4]
ENV_FILE = PROJECT_ROOT / ".env"
CONFIG_FILE = SCRIPTS_DIR / "config.json"

PHASE_SCRIPTS = {
    1: SCRIPTS_DIR / "search_companies.py",
    2: SCRIPTS_DIR / "scrape_websites.py",
    3: SCRIPTS_DIR / "analyze_companies.py",
    4: SCRIPTS_DIR / "store_results.py",
}

OUTPUT_DIR = SCRIPTS_DIR / "output"
DEFAULT_PROFILE_PATH = SCRIPTS_DIR.resolve().parents[1] / "company-profile" / "profile.json"

# Feishu table field names (must match store_results.py)
FEISHU_FIELDS = [
    "公司名称", "网站", "国家/地区", "行业", "公司角色",
    "联系人", "邮箱", "电话",
    "AI分析摘要", "业务匹配点", "开发建议",
    "邮件已发送", "发送时间",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text):
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")[:40]


def get_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------------------
# Feishu / lark-cli utilities
# ---------------------------------------------------------------------------

def _get_lark_cli_cmd():
    """Get the Node.js command to run lark-cli, bypassing the .CMD wrapper."""
    npm_dir = os.path.join(os.environ.get("APPDATA", ""), "npm")
    run_js = os.path.join(npm_dir, "node_modules", "@larksuite", "cli", "scripts", "run.js")
    if os.path.isfile(run_js):
        return ["node", run_js]
    return None


def _run_lark_cli(args, timeout=30):
    """Run a lark-cli command. Returns subprocess.CompletedProcess or None."""
    cmd = _get_lark_cli_cmd()
    if not cmd:
        return None
    full_cmd = cmd + args
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    try:
        return subprocess.run(
            full_cmd, capture_output=True, timeout=timeout,
            encoding="utf-8", errors="replace", env=env,
        )
    except (subprocess.TimeoutExpired, Exception):
        return None


def check_lark_auth():
    """Check if lark-cli is installed and authenticated.

    Returns (ok: bool, message: str).
    """
    cmd = _get_lark_cli_cmd()
    if not cmd:
        return False, "lark-cli not installed"

    result = _run_lark_cli(["--version"], timeout=10)
    if not result or result.returncode != 0:
        return False, "lark-cli not found"

    result = _run_lark_cli(["auth", "status"], timeout=10)
    if not result or result.returncode != 0:
        return False, "not_authenticated"

    try:
        data = json.loads(result.stdout)
        identity = data.get("identity", "")
        if identity in ("user", "bot"):
            return True, f"authenticated as {identity}"
        return False, f"unexpected identity: {identity}"
    except (json.JSONDecodeError, TypeError):
        return False, "failed to parse auth status"


def parse_feishu_link(link):
    """Parse a feishu base table link to extract base_token and table_id.

    Accepted formats:
      https://xxx.feishu.cn/base/BASE_TOKEN?table=TABLE_ID&view=VIEW_ID
      https://xxx.feishu.cn/base/BASE_TOKEN?table=TABLE_ID

    Returns (dict, None) on success or (None, error_message) on failure.
    """
    base_match = re.search(r"feishu\.\w+/base/([a-zA-Z0-9]+)", link)
    if not base_match:
        return None, "无法识别飞书链接格式。请提供多维表格链接，如 https://xxx.feishu.cn/base/TOKEN?table=ID"

    base_token = base_match.group(1)

    table_match = re.search(r"[?&]table=([a-zA-Z0-9]+)", link)
    if not table_match:
        return None, "链接中未找到 table 参数。请提供完整的表格链接（包含 ?table=ID）"

    table_id = table_match.group(1)

    return {
        "base_token": base_token,
        "table_id": table_id,
        "table_link": link,
    }, None


def load_config():
    """Load config.json. Returns dict (empty if missing/invalid)."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_config(config):
    """Save dict to config.json."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def create_feishu_table(table_name="客户获取列表"):
    """Create a new feishu base and table via lark-cli.

    Returns (config_dict, None) on success or (None, error_message) on failure.
    """
    # 1. Check auth
    auth_ok, msg = check_lark_auth()
    if not auth_ok:
        return None, f"飞书未授权: {msg}。请先运行: lark-cli auth login --recommend"

    # 2. Get identity
    result = _run_lark_cli(["auth", "status"], timeout=10)
    identity = "user"
    if result and result.returncode == 0:
        try:
            identity = json.loads(result.stdout).get("identity", "user")
        except (json.JSONDecodeError, TypeError):
            pass

    # 3. Create a new base
    result = _run_lark_cli([
        "base", "+base-create",
        "--name", table_name,
        "--as", identity,
        "--time-zone", "Asia/Shanghai",
    ], timeout=30)

    if not result or result.returncode != 0:
        stderr = (result.stderr or "")[:300] if result else "no response"
        return None, f"创建飞书多维表格失败: {stderr}。建议在飞书中手动创建一个多维表格，然后把链接粘贴过来。"

    try:
        data = json.loads(result.stdout)
        if not data.get("ok"):
            err = data.get("error", data)
            return None, f"创建失败: {err}"
        base_token = data.get("data", {}).get("base", {}).get("base_token", "")
        base_url = data.get("data", {}).get("base", {}).get("url", "")
    except (json.JSONDecodeError, TypeError):
        return None, f"解析创建结果失败: {(result.stdout or '')[:200]}。建议手动创建表格后粘贴链接。"

    if not base_token:
        return None, "未能获取 base_token。建议手动创建表格后粘贴链接。"

    # 4. Create table (base +base-create already creates a default table; delete it first)
    list_result = _run_lark_cli([
        "base", "+table-list", "--base-token", base_token, "--as", identity,
    ], timeout=15)
    if list_result and list_result.returncode == 0:
        try:
            tables = json.loads(list_result.stdout).get("data", {}).get("tables", [])
            for t in tables:
                _run_lark_cli([
                    "base", "+table-delete", "--base-token", base_token,
                    "--table-id", t["id"], "--as", identity, "--yes",
                ], timeout=10)
        except Exception:
            pass

    # 5. Create table with correct field types
    table_fields = []
    field_types = {
        "邮件已发送": "checkbox",
    }
    for fname in FEISHU_FIELDS:
        table_fields.append({"name": fname, "type": field_types.get(fname, "text")})
    fields_json = json.dumps(table_fields, ensure_ascii=False)

    result = _run_lark_cli([
        "base", "+table-create",
        "--base-token", base_token,
        "--name", "客户数据",
        "--fields", fields_json,
        "--as", identity,
    ], timeout=30)

    if not result or result.returncode != 0:
        stderr = (result.stderr or "")[:300] if result else "no response"
        return None, f"Base 已创建 (token={base_token})，但创建数据表失败: {stderr}。请在 Base 中手动创建表格后粘贴链接。"

    try:
        data = json.loads(result.stdout)
        if not data.get("ok"):
            err = data.get("error", data)
            return None, f"创建数据表失败: {err}"
        table_id = data.get("data", {}).get("table_id", "")
    except (json.JSONDecodeError, TypeError):
        return None, f"解析结果失败: {(result.stdout or '')[:200]}"

    if not table_id:
        return None, "未能获取 table_id。Base 已创建，请手动创建表格后粘贴链接。"

    return {
        "base_token": base_token,
        "table_id": table_id,
        "table_name": table_name,
        "table_link": f"{base_url}?table={table_id}" if base_url else "",
    }, None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_prerequisites():
    """Check API keys and tools. Returns list of errors."""
    errors = []

    if not ENV_FILE.exists():
        errors.append(f".env not found at {ENV_FILE}")
    else:
        try:
            from dotenv import load_dotenv
            load_dotenv(ENV_FILE)
        except ImportError:
            errors.append("python-dotenv not installed. Run: pip install python-dotenv")

    if not os.environ.get("SERPER_API_KEY"):
        errors.append("SERPER_API_KEY not set in .env")
    if not os.environ.get("REPLICATE_API_TOKEN"):
        errors.append("REPLICATE_API_TOKEN not set in .env")

    for pkg in ["requests", "replicate", "playwright"]:
        try:
            __import__(pkg)
        except ImportError:
            errors.append(f"{pkg} not installed. Run: pip install {pkg}")

    return errors


def validate_feishu_config():
    """Check config.json has valid feishu credentials. Returns list of errors."""
    config = load_config()
    errors = []
    if not config.get("base_token"):
        errors.append("base_token is empty in config.json — use --save-feishu-link or --create-table")
    if not config.get("table_id"):
        errors.append("table_id is empty in config.json — use --save-feishu-link or --create-table")
    return errors


# ---------------------------------------------------------------------------
# Intermediate file helpers
# ---------------------------------------------------------------------------

def find_latest_file(slug, phase):
    pattern = str(OUTPUT_DIR / f"ca_{slug}_*_phase{phase}.json")
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None


def phase_filename(slug, phase):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return str(OUTPUT_DIR / f"ca_{slug}_{get_timestamp()}_phase{phase}.json")


def find_resume_file(slug, from_phase):
    if from_phase == 1:
        return None
    f = find_latest_file(slug, from_phase - 1)
    if f:
        return f
    # Fallback: any matching phase file
    all_files = sorted(glob.glob(str(OUTPUT_DIR / f"ca_*_phase{from_phase - 1}.json")))
    return all_files[-1] if all_files else None


# ---------------------------------------------------------------------------
# Phase runners
# ---------------------------------------------------------------------------

def run_phase(phase, cmd_args, label):
    """Run a phase script as a subprocess. Returns True on success."""
    script = PHASE_SCRIPTS[phase]
    if not script.exists():
        print(f"[ERROR] Script not found: {script}")
        return False

    cmd = [sys.executable, str(script)] + cmd_args
    print(f"\n{'='*60}")
    print(f"  Phase {phase}: {label}")
    print(f"{'='*60}")

    start = time.time()
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    try:
        result = subprocess.run(cmd, timeout=600, env=env)
    except subprocess.TimeoutExpired:
        print(f"[ERROR] Phase {phase} timed out after 600s")
        return False
    except Exception as e:
        print(f"[ERROR] Phase {phase} failed: {e}")
        return False

    elapsed = time.time() - start

    if result.returncode != 0:
        print(f"[ERROR] Phase {phase} exited with code {result.returncode} ({elapsed:.0f}s)")
        return False

    print(f"[OK] Phase {phase} completed in {elapsed:.0f}s")
    return True


# ---------------------------------------------------------------------------
# Post-Phase-3 filter: sort by quality, take top N
# ---------------------------------------------------------------------------

OVER_FETCH_RATIO = 3  # Search 3x the user's requested count


def filter_and_rank(filepath, target_num, target_country=""):
    """After Phase 3, rank companies by quality and keep top target_num.

    Returns (filtered_filepath, kept_count, total_count).
    """
    data = json.loads(Path(filepath).read_text(encoding="utf-8"))
    companies = data.get("companies", [])
    total = len(companies)

    if total <= target_num:
        return filepath, total, total

    # Score each company
    match_score_map = {"High": 3, "Medium": 2, "Low": 1, "": 0}

    def score(c):
        s = 0
        # Confidence score (0-100)
        s += c.get("_confidence_score", 0) or 0
        # Market match level
        s += match_score_map.get(c.get("_market_match", ""), 0) * 15
        # Country match bonus
        country = c.get("country", "").lower()
        if target_country and target_country.lower() in country:
            s += 20
        # Has contact info bonus
        if c.get("email"):
            s += 10
        if c.get("phone"):
            s += 5
        # Not a listing/directory site
        role = c.get("company_role", "").lower()
        if any(w in role for w in ["服务商", "平台", "目录"]):
            s -= 50
        return s

    ranked = sorted(companies, key=score, reverse=True)
    kept = ranked[:target_num]

    # Write filtered output
    filtered_path = filepath.replace(".json", "_filtered.json")
    data["companies"] = kept
    data["metadata"]["filter_applied"] = True
    data["metadata"]["filtered_from"] = total
    data["metadata"]["filtered_to"] = len(kept)
    Path(filtered_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[FILTER] Ranked {total} companies, kept top {len(kept)}")
    for i, c in enumerate(kept, 1):
        name = c.get("company_name", "")[:40]
        match = c.get("_market_match", "")
        conf = c.get("_confidence_score", 0)
        email = "Y" if c.get("email") else "N"
        print(f"  {i}. {name:<42} match:{match:<6} conf:{conf:<3} email:{email}")

    return filtered_path, len(kept), total


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------

def print_summary(filepath):
    """Print a concise results table from the final JSON output."""
    try:
        data = json.loads(Path(filepath).read_text(encoding="utf-8"))
        companies = data.get("companies", [])
    except Exception:
        return

    if not companies:
        print("\nNo results to display.")
        return

    # Count stats
    with_email = sum(1 for c in companies if c.get("email"))
    with_phone = sum(1 for c in companies if c.get("phone"))
    high_match = sum(1 for c in companies if c.get("_market_match") == "High")
    medium_match = sum(1 for c in companies if c.get("_market_match") == "Medium")

    print(f"\n{'='*60}")
    print(f"  RESULTS: {len(companies)} companies")
    print(f"  Email found: {with_email}  |  Phone found: {with_phone}")
    print(f"  High match: {high_match}  |  Medium match: {medium_match}")
    print(f"{'='*60}")

    # Table
    print(f"\n{'#':<4} {'Company':<40} {'Email':<30} {'Match':<8} {'Role':<15}")
    print(f"{'-'*4} {'-'*40} {'-'*30} {'-'*8} {'-'*15}")
    for i, c in enumerate(companies[:30], 1):
        name = c.get("company_name", "")[:38]
        email = c.get("email", "")[:28]
        match = (c.get("_market_match") or "")[:6]
        role = c.get("company_role", "")[:13]
        print(f"  {i:<4} {name:<40} {email:<30} {match:<8} {role:<15}")

    if len(companies) > 30:
        print(f"  ... and {len(companies) - 30} more")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Customer Acquisition Skill — one-click orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Pipeline examples:
  python run.py --industry "LED" --country "USA" --keywords "wholesale" --num 30
  python run.py --industry "LED" --country "USA" --platform feishu --keep-intermediate
  python run.py --from-phase 3 --industry "LED" --country "USA" --num 30

Feishu utility examples:
  python run.py --check-auth
  python run.py --show-config
  python run.py --save-feishu-link "https://xxx.feishu.cn/base/TOKEN?table=ID"
  python run.py --create-table "客户获取列表"
        """,
    )

    # --- Pipeline args ---
    pipeline = parser.add_argument_group("Pipeline")
    pipeline.add_argument("--industry", help="Target industry (e.g. 'LED')")
    pipeline.add_argument("--country", help="Target country (e.g. 'USA')")
    pipeline.add_argument("--keywords", default="", help="Comma-separated role keywords")
    pipeline.add_argument("--num", type=int, default=30, help="Target number of companies")
    pipeline.add_argument("--my-company", default="", help="Your company name (overrides profile)")
    pipeline.add_argument("--my-products", default="", help="Your products description (overrides profile)")
    pipeline.add_argument("--my-profile", default="", help="Path to company-profile skill's profile.json (enriches AI analysis)")
    pipeline.add_argument("--platform", choices=["feishu", "csv"], default="csv")
    pipeline.add_argument("--from-phase", type=int, choices=[1, 2, 3, 4], default=1)
    pipeline.add_argument("--to-phase", type=int, choices=[1, 2, 3, 4], default=4)
    pipeline.add_argument("--dry-run", action="store_true")
    pipeline.add_argument("--keep-intermediate", action="store_true")

    # --- Setup args ---
    setup_grp = parser.add_argument_group("Environment setup")
    setup_grp.add_argument("--setup", nargs="*", metavar="KEY=VALUE",
                           help="Check env vars (--setup) or write values (--setup KEY=VALUE)")

    # --- Feishu utility args ---
    feishu_grp = parser.add_argument_group("Feishu utilities")
    feishu_grp.add_argument("--check-auth", action="store_true", help="Check lark-cli auth status")
    feishu_grp.add_argument("--get-auth-url", action="store_true", help="Get Feishu device-flow auth URL (non-blocking)")
    feishu_grp.add_argument("--show-config", action="store_true", help="Show saved feishu config")
    feishu_grp.add_argument("--save-feishu-link", metavar="LINK", help="Parse & save a feishu table link")
    feishu_grp.add_argument("--create-table", metavar="NAME", help="Create a new feishu table")

    args = parser.parse_args()

    # ===================================================================
    # Utility modes (exit after execution)
    # ===================================================================

    if args.setup is not None:
        _SKILL_DIR = SCRIPTS_DIR.parent
        if args.setup:
            for kv in args.setup:
                k, _, v = kv.partition("=")
                if k and v:
                    write_env_var(PROJECT_ROOT, k.strip(), v.strip())
        result = check_setup(PROJECT_ROOT, "customer-acquisition", skill_dir=_SKILL_DIR)
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
        if config.get("base_token"):
            print(f"Configured table: {config.get('table_name', '(unnamed)')}")
            print(f"  base_token: {config['base_token']}")
            print(f"  table_id:   {config['table_id']}")
            if config.get("table_link"):
                print(f"  link:       {config['table_link']}")
            if config.get("last_used"):
                print(f"  last_used:  {config['last_used']}")
        else:
            print("No feishu table configured yet.")
            print("Use --save-feishu-link or --create-table to set up.")
        sys.exit(0)

    if args.save_feishu_link:
        parsed, error = parse_feishu_link(args.save_feishu_link)
        if error:
            print(f"ERROR: {error}")
            sys.exit(1)
        config = load_config()
        config.update(parsed)
        config["last_used"] = get_timestamp()
        save_config(config)
        print(f"OK: Feishu table link saved.")
        print(f"  base_token: {parsed['base_token']}")
        print(f"  table_id:   {parsed['table_id']}")
        sys.exit(0)

    if args.create_table:
        config, error = create_feishu_table(args.create_table)
        if error:
            print(f"ERROR: {error}")
            sys.exit(1)
        config["last_used"] = get_timestamp()
        save_config(config)
        print(f"OK: New feishu table created.")
        print(f"  base_token: {config['base_token']}")
        print(f"  table_id:   {config['table_id']}")
        print(f"  table_name: {config['table_name']}")
        sys.exit(0)

    # ===================================================================
    # Pipeline mode
    # ===================================================================

    if not args.industry or not args.country:
        parser.error("--industry and --country are required for pipeline mode")

    slug = slugify(f"{args.industry}_{args.country}_{args.keywords}")
    search_num = args.num * OVER_FETCH_RATIO if args.from_phase <= 1 else args.num

    # Auto-detect company profile
    profile_path = args.my_profile
    if not profile_path and DEFAULT_PROFILE_PATH.exists():
        profile_path = str(DEFAULT_PROFILE_PATH)

    print(f"Customer Acquisition Skill")
    print(f"  Industry: {args.industry}")
    print(f"  Country:  {args.country}")
    print(f"  Keywords: {args.keywords or '(none)'}")
    print(f"  Target:   {args.num} companies (searching {search_num} for quality filtering)")
    print(f"  Platform: {args.platform}")
    print(f"  Phases:   {args.from_phase} -> {args.to_phase}")
    if profile_path:
        print(f"  Profile:  {profile_path}")

    # Validate prerequisites
    errors = validate_prerequisites()
    if errors:
        print("\nPrerequisite check FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    print("\nPrerequisites OK")

    # For feishu, also check auth and config
    if args.platform == "feishu":
        auth_ok, auth_msg = check_lark_auth()
        if not auth_ok:
            print(f"\nFeishu auth FAILED: {auth_msg}")
            print("Run: lark-cli auth login --recommend")
            print("Or use --platform csv to skip feishu.")
            sys.exit(1)
        print(f"Feishu auth OK: {auth_msg}")

        config_errors = validate_feishu_config()
        if config_errors:
            print(f"\nFeishu config issue:")
            for e in config_errors:
                print(f"  - {e}")
            print("Use --save-feishu-link or --create-table to configure.")
            sys.exit(1)
        print(f"Feishu table configured: {load_config().get('table_name', '')}")

    if args.dry_run:
        print("\nDry run complete. All checks passed.")
        sys.exit(0)

    # Resume logic
    current_input = None
    if args.from_phase > 1:
        current_input = find_resume_file(slug, args.from_phase)
        if current_input:
            print(f"[RESUME] Input: {current_input}")
        else:
            print(f"[ERROR] Cannot resume: no Phase {args.from_phase - 1} output found.")
            sys.exit(1)

    # Run phases
    start_time = time.time()

    for phase in range(args.from_phase, args.to_phase + 1):
        output_file = phase_filename(slug, phase)

        if phase == 1:
            success = run_phase(phase, [
                "--industry", args.industry,
                "--country", args.country,
                "--keywords", args.keywords,
                "--num", str(search_num),
                "--output", output_file,
            ], f"Search Companies ({search_num} for quality filtering)")

            if success:
                try:
                    data = json.loads(Path(output_file).read_text(encoding="utf-8"))
                    actual = data.get("metadata", {}).get("actual_count", 0)
                    if actual == 0:
                        print("[ERROR] Phase 1 found 0 companies. Aborting.")
                        sys.exit(1)
                    if actual < args.num:
                        print(f"[WARN] Found only {actual}/{args.num} target companies. Continuing with available results.")
                except Exception:
                    pass

        elif phase == 2:
            success = run_phase(phase, [
                "--input", current_input or output_file,
                "--output", output_file,
                "--timeout", "30",
            ], "Scrape Websites")

        elif phase == 3:
            cmd = [
                "--input", current_input or output_file,
                "--output", output_file,
            ]
            if args.my_company:
                cmd += ["--my-company", args.my_company]
            if args.my_products:
                cmd += ["--my-products", args.my_products]
            if profile_path:
                cmd += ["--my-profile", profile_path]
            success = run_phase(phase, cmd, "AI Analysis")

            # After AI analysis, filter and rank to user's target count
            if success:
                filtered_path, kept, total = filter_and_rank(output_file, args.num, args.country)
                if filtered_path != output_file:
                    output_file = filtered_path

        elif phase == 4:
            csv_path = str(OUTPUT_DIR / f"ca_{slug}_{get_timestamp()}.csv")
            success = run_phase(phase, [
                "--input", current_input or output_file,
                "--platform", args.platform,
                "--csv-output", csv_path,
            ], "Store Results")

            # Update last_used in config
            if success and args.platform == "feishu":
                config = load_config()
                config["last_used"] = get_timestamp()
                save_config(config)

        if not success:
            print(f"\n[ABORT] Phase {phase} failed.")
            sys.exit(1)

        current_input = output_file

    # Done
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  Pipeline complete! ({elapsed:.0f}s)")
    if args.platform == "csv":
        csv_files = sorted(glob.glob(str(OUTPUT_DIR / f"ca_{slug}_*.csv")))
        if csv_files:
            print(f"  CSV: {csv_files[-1]}")
    print(f"  Data: {current_input}")
    print(f"{'='*60}")

    print_summary(current_input)

    # Cleanup intermediate files
    if not args.keep_intermediate:
        try:
            shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
            print("\nIntermediate files cleaned up.")
        except Exception:
            pass


if __name__ == "__main__":
    main()
