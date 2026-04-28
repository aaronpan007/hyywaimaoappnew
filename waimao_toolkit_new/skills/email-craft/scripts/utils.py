"""Shared utilities for Email Craft Skill scripts."""

import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    print_error("python-dotenv not installed. Run: pip install python-dotenv")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent
# parents: [0]=email-craft, [1]=skills, [2]=.claude, [3]=project-root
PROJECT_ROOT = SCRIPTS_DIR.resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"
CONFIG_FILE = SCRIPTS_DIR / "config.json"
REFERENCES_DIR = SCRIPTS_DIR.resolve().parents[1] / "references"
SKILLS_DIR = SCRIPTS_DIR.resolve().parents[1]  # -> .claude/skills
DEFAULT_PROFILE_PATH = SKILLS_DIR / "company-profile" / "profile.json"
CA_CONFIG_FILE = SKILLS_DIR / "customer-acquisition" / "scripts" / "config.json"


# ---------------------------------------------------------------------------
# Basic utilities (from customer-acquisition/scripts/utils.py)
# ---------------------------------------------------------------------------

def load_env():
    """Load environment variables from .env file."""
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
    else:
        print_error(f".env file not found at {ENV_FILE}")
        print_error("Copy .env.example to .env and fill in your API keys.")
        sys.exit(1)


def read_json(filepath):
    """Read and return JSON data from a file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(filepath, data):
    """Write JSON data to a file with pretty formatting."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def print_progress(phase, message):
    """Print structured progress message."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{phase}] {message}", flush=True)


def print_error(message):
    """Print error message to stderr."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [ERROR] {message}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Lark-cli utilities (from customer-acquisition/scripts/run.py)
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
    """Load config.json. Returns dict with 'current' + 'history' keys.

    Automatically migrates old flat format to new format.
    """
    if CONFIG_FILE.exists():
        try:
            raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"current": {}, "history": []}

        # Migrate old flat format: {"base_token": ..., "table_id": ...}
        if "current" not in raw and ("base_token" in raw or "table_id" in raw):
            raw["current"] = {
                k: v for k, v in raw.items()
                if k not in ("current", "history")
            }
            raw["history"] = []
            _save_config_raw(raw)

        if "current" not in raw:
            raw["current"] = {}
        if "history" not in raw:
            raw["history"] = []
        return raw

    return {"current": {}, "history": []}


def _save_config_raw(config):
    """Write config dict directly to config.json."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def save_config(config):
    """Save config dict (with current + history) to config.json."""
    _save_config_raw(config)


def get_current_config(config):
    """Extract the 'current' table entry from config dict."""
    return config.get("current", {})


def add_to_history(config, label=None):
    """Add the current table entry to history with a label.

    Updates config["current"] and appends to config["history"].
    Deduplicates by table_id, keeps at most 20 entries.
    Returns the updated config.
    """
    current = config.get("current", {})
    if not current.get("base_token") or not current.get("table_id"):
        return config

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    # Build the history entry
    entry = {
        "base_token": current.get("base_token", ""),
        "table_id": current.get("table_id", ""),
        "table_link": current.get("table_link", ""),
        "table_name": current.get("table_name", ""),
        "label": label or current.get("table_name", today),
        "source": current.get("source", ""),
        "last_used": timestamp,
    }

    # Update current with label and timestamp
    current["label"] = entry["label"]
    current["last_used"] = timestamp
    config["current"] = current

    # Deduplicate: remove existing entry with same table_id
    history = config.get("history", [])
    history = [h for h in history if h.get("table_id") != entry["table_id"]]
    history.insert(0, entry)
    config["history"] = history[:20]

    _save_config_raw(config)
    return config


# ---------------------------------------------------------------------------
# From analyze_companies.py — profile section builder + AI response parser
# ---------------------------------------------------------------------------

def build_profile_section(profile, my_company="", my_products="", cases_override=None):
    """Build a structured '我司信息' section from profile.json data.

    Args:
        profile: profile dict
        my_company: override company name
        my_products: override products description
        cases_override: if provided, use these specific cases instead of auto-selecting
    """
    company_name = my_company or profile.get("company_name", "")
    one_line_intro = profile.get("one_line_intro", "")

    lines = []
    lines.append("=== 我司信息 ===")
    lines.append(f"公司名称: {company_name}")
    if one_line_intro:
        lines.append(f"一句话介绍: {one_line_intro}")

    # Products
    products = profile.get("products", [])
    if products:
        lines.append("")
        lines.append("--- 产品线 ---")
        for p in products:
            sp = p.get("key_selling_points", [])
            sp_text = "；".join(sp) if sp else ""
            lines.append(f"• {p['name']}")
            if sp_text:
                lines.append(f"  卖点: {sp_text}")

    # Core competencies
    competencies = profile.get("core_competencies", [])
    if competencies:
        lines.append("")
        lines.append("--- 核心竞争力 ---")
        for c in competencies:
            lines.append(f"• {c['competency']}: {c.get('evidence', c.get('description', ''))}")

    # Case studies
    if cases_override is not None:
        cases = cases_override
    else:
        cases = [cs for cs in profile.get("case_studies", []) if cs.get("usable_in_outreach")]
        international = [c for c in cases if c.get("country") and c["country"] not in ("中国",)]
        domestic = [c for c in cases if c.get("country") in ("中国",)]
        cases = (international[:7] + domestic[:3])[:10]

    if cases:
        lines.append("")
        lines.append("--- 代表性案例 ---")
        for cs in cases:
            proj = cs.get("project_en", cs.get("project", ""))
            country = cs.get("country", "")
            prods = ", ".join(cs.get("products_used", []))
            highlight = cs.get("key_highlight", "")
            lines.append(f"• {proj}（{country}）| 产品: {prods} | 亮点: {highlight}")

    # Unique selling points
    usps = profile.get("unique_selling_points", [])
    if usps:
        lines.append("")
        lines.append("--- 独特卖点 ---")
        for u in usps:
            lines.append(f"• {u}")

    # Certifications
    certs = profile.get("certifications", [])
    if certs:
        lines.append("")
        lines.append("--- 资质认证 ---")
        for c in certs:
            lines.append(f"• {c}")

    # Cooperation models
    models = profile.get("cooperation_models", [])
    if models:
        lines.append("")
        lines.append("--- 合作模式 ---")
        for m in models:
            lines.append(f"• {m['model']}: {m.get('description', '')}")

    # Customer matching guide
    guide = profile.get("customer_matching_guide", [])
    if guide:
        lines.append("")
        lines.append("--- 客户匹配指南（请据此判断待分析公司属于哪种类型，并参考对应建议） ---")
        for g in guide:
            pp = "；".join(g.get("priority_points", []))
            lines.append(f"• {g['customer_type']}: 重点强调 {pp}")

    return "\n".join(lines)


def parse_ai_response(response_text):
    """Parse AI response, handling markdown code blocks and raw JSON."""
    text = response_text.strip()

    # Try to extract JSON from markdown code block
    code_block_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if code_block_match:
        text = code_block_match.group(1).strip()

    # Try to parse JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        try:
            return json.loads(text[brace_start:brace_end + 1])
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# Email-craft specific utilities
# ---------------------------------------------------------------------------

def detect_ca_config():
    """Check if customer-acquisition config.json was used within 24 hours.

    Returns (config_dict, None) or (None, message).
    The returned config_dict is a flat dict (base_token, table_id, etc.).
    """
    if not CA_CONFIG_FILE.exists():
        return None, "customer-acquisition config not found"

    try:
        ca_raw = json.loads(CA_CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, "customer-acquisition config is invalid"

    # Handle new format (current + history) or old flat format
    if "current" in ca_raw:
        ca_config = ca_raw["current"]
    else:
        ca_config = ca_raw

    if not ca_config.get("base_token") or not ca_config.get("table_id"):
        return None, "customer-acquisition config has no base_token/table_id"

    last_used = ca_config.get("last_used", "")
    if last_used:
        try:
            used_time = datetime.strptime(last_used, "%Y%m%d_%H%M%S")
            if datetime.now() - used_time > timedelta(hours=24):
                return None, f"customer-acquisition config last used {used_time.strftime('%Y-%m-%d %H:%M')} (over 24h ago)"
        except ValueError:
            pass

    return ca_config, None


def sync_config(ca_config):
    """Sync CA config to email-craft config.json (new current+history format)."""
    config = load_config()
    current = config.get("current", {})
    current["base_token"] = ca_config["base_token"]
    current["table_id"] = ca_config["table_id"]
    if ca_config.get("table_link"):
        current["table_link"] = ca_config["table_link"]
    if ca_config.get("table_name"):
        current["table_name"] = ca_config["table_name"]
    current["source"] = "customer-acquisition"
    current["last_used"] = datetime.now().strftime("%Y%m%d_%H%M%S")
    config["current"] = current
    save_config(config)
    return config


def _contains_chinese(text):
    """Check if text contains Chinese characters."""
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff':
            return True
    return False


def load_reference_emails():
    """Load reference emails from references/ directory.

    Returns list of {"filename", "content", "language"} dicts.
    """
    if not REFERENCES_DIR.exists():
        return []

    refs = []
    for ext in ("*.txt", "*.md", "*.eml"):
        for filepath in sorted(REFERENCES_DIR.glob(ext)):
            try:
                content = filepath.read_text(encoding="utf-8")
                language = "cn" if _contains_chinese(content) else "en"
                refs.append({
                    "filename": filepath.name,
                    "content": content.strip(),
                    "language": language,
                })
            except Exception:
                continue

    return refs


def ensure_fields(base_token, table_id, identity):
    """Ensure '开发信' and '邮件主题' fields exist in the Feishu table.

    Creates them if they don't exist.
    """
    # First, list existing fields
    result = _run_lark_cli([
        "base", "+field-list",
        "--base-token", base_token,
        "--table-id", table_id,
        "--as", identity,
    ], timeout=15)

    if not result or result.returncode != 0:
        print_error("Failed to list existing fields — will try to create anyway")
        existing_fields = set()
    else:
        try:
            data = json.loads(result.stdout)
            fields = data.get("data", {}).get("fields", [])
            existing_fields = {f.get("name", "") for f in fields}
        except (json.JSONDecodeError, TypeError):
            existing_fields = set()

    fields_to_create = []
    if "开发信" not in existing_fields:
        fields_to_create.append("开发信")
    if "邮件主题" not in existing_fields:
        fields_to_create.append("邮件主题")

    for field_name in fields_to_create:
        field_json = json.dumps({"name": field_name, "type": "text"}, ensure_ascii=False)
        result = _run_lark_cli([
            "base", "+field-create",
            "--base-token", base_token,
            "--table-id", table_id,
            "--as", identity,
            "--json", field_json,
        ], timeout=15)

        if result and result.returncode == 0:
            print_progress("SETUP", f"Created field: {field_name}")
        else:
            stderr = (result.stderr or "")[:200] if result else "no response"
            print_error(f"Failed to create field '{field_name}': {stderr}")
