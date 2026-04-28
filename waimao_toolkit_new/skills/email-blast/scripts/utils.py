"""Shared utilities for email-blast skill."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Paths
SKILL_DIR = Path(__file__).parent.parent
SKILLS_DIR = SKILL_DIR.parent  # -> .claude/skills
PROJECT_DIR = SKILL_DIR.parent.parent.parent
ENV_FILE = PROJECT_DIR / ".env"

# Email-craft config path (for cross-skill table discovery)
EC_CONFIG_FILE = SKILLS_DIR / "email-craft" / "scripts" / "config.json"

# Feishu table fields used by this skill
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
    "发送时间": "sent_time",
    "备注": "notes",
    "开发信": "email_draft",
    "邮件主题": "email_subject",
}

# Load environment variables from .env file
def load_env():
    """Load environment variables from .env file."""
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = value

# Load env on import
load_env()


def get_env(key, default=None):
    """Get environment variable with helpful error message."""
    value = os.environ.get(key)
    if not value and default is None:
        print(f"❌ 环境变量 {key} 未配置。请在 .env 文件中设置。")
        sys.exit(1)
    return value or default


def get_lark_cli_cmd():
    """Get the Node.js command to run lark-cli, bypassing the .CMD wrapper."""
    npm_dir = os.path.join(os.environ.get("APPDATA", ""), "npm")
    run_js = os.path.join(npm_dir, "node_modules", "@larksuite", "cli", "scripts", "run.js")
    if os.path.isfile(run_js):
        return ["node", run_js]
    return None


def run_lark_cli(args, timeout=30):
    """Run a lark-cli command. Returns subprocess.CompletedProcess or None."""
    cmd = get_lark_cli_cmd()
    if not cmd:
        print("❌ 未找到 lark-cli，请先安装: npm install -g @larksuite/cli")
        return None
    full_cmd = cmd + args
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    try:
        return subprocess.run(
            full_cmd, capture_output=True, timeout=timeout,
            encoding="utf-8", errors="replace", env=env,
        )
    except subprocess.TimeoutExpired:
        print(f"⚠️ lark-cli 命令超时 ({timeout}s): {' '.join(args[:3])}")
        return None
    except Exception as e:
        print(f"❌ lark-cli 执行错误: {e}")
        return None


def parse_record_list_response(stdout):
    """Parse lark-cli record-list JSON response format.

    lark-cli returns column-oriented JSON:
      data.fields = ["Field1", "Field2", ...]
      data.record_id_list = ["recXXX", "recYYY", ...]
      data.data = [[val1, val2, ...], ...]

    Returns (fields, record_ids, rows, has_more).
    """
    if not stdout:
        return [], [], [], False

    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        # Fallback: try TSV format
        lines = stdout.strip().split("\n")
        if len(lines) < 2:
            return [], [], [], False
        fields = lines[0].split("\t")
        record_ids, rows = [], []
        for line in lines[1:]:
            if not line.strip():
                continue
            cells = line.split("\t")
            if cells:
                record_ids.append(cells[0])
                rows.append(cells[1:])
        return fields, record_ids, rows, len(record_ids) >= 200

    if not data.get("ok"):
        return [], [], [], False

    inner = data.get("data", {})

    # Column-oriented format
    if "fields" in inner and "data" in inner:
        fields = inner["fields"]
        record_ids = inner.get("record_id_list", [])
        rows = inner["data"]
        has_more = inner.get("has_more", False)
        return fields, record_ids, rows, has_more

    return [], [], [], False


def extract_field_value(raw):
    """Extract field value from lark-cli output, handling various formats."""
    if raw is None:
        return ""
    if isinstance(raw, list):
        return ", ".join(str(v) for v in raw if v)
    if isinstance(raw, dict):
        return raw.get("text", raw.get("value", str(raw)))
    if isinstance(raw, bool):
        return "是" if raw else ""
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return ""
        # Try JSON parse (handles arrays like ["value1","value2"])
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return ", ".join(str(v) for v in parsed if v)
            if isinstance(parsed, str):
                return parsed
            return str(parsed)
        except (json.JSONDecodeError, ValueError):
            return raw
    return str(raw)


def print_progress(stage, message):
    """Print a progress message with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{stage}] {message}")


def get_feishu_config():
    """Get Feishu table configuration from config.json or email-craft config.

    Priority:
      1. email-blast local config.json
      2. email-craft config.json (auto-detect)
    """
    # 1. Try local config.json
    config_path = SKILL_DIR / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        # Check if config is recent (within 24 hours)
        if "timestamp" in config:
            try:
                ts = datetime.fromisoformat(config["timestamp"])
                age_hours = (datetime.now() - ts).total_seconds() / 3600
                if age_hours > 24:
                    print("⚠️ 配置文件已超过 24 小时，建议重新确认表格。")
            except ValueError:
                pass
        return config

    # 2. Try email-craft config.json (auto-detect)
    ec_config, msg = detect_ec_config()
    if ec_config:
        print(f"💡 自动检测到 email-craft 表格: {ec_config.get('label', ec_config.get('table_name', ''))}")
        # Save to local config for future use
        save_feishu_config(
            ec_config["base_token"],
            ec_config["table_id"],
        )
        return {
            "base_token": ec_config["base_token"],
            "table_id": ec_config["table_id"],
            "identity": "user",
            "source": "email-craft",
            "label": ec_config.get("label", ""),
        }

    return None


def save_feishu_config(base_token, table_id, identity="user"):
    """Save Feishu table configuration to config.json."""
    config = {
        "base_token": base_token,
        "table_id": table_id,
        "identity": identity,
        "timestamp": datetime.now().isoformat(),
        "last_used": datetime.now().strftime("%Y%m%d_%H%M%S"),
    }
    config_path = SKILL_DIR / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    return config_path


def extract_brand_name(company_name):
    """Extract brand short name from full company name.

    Rules:
    - If parentheses present, prefer content inside: "Co., Ltd (Brand)" → "Brand"
    - Otherwise, take the part before Co./Ltd./Inc./Corp./Group:
      "Acme Corporation" → "Acme", "Acme Co., Ltd" → "Acme"
    - If no suffix found, return the full name trimmed.

    Args:
        company_name: Full company name string.

    Returns:
        Extracted brand name string.
    """
    if not company_name:
        return ""

    name = company_name.strip()

    # Prefer content inside parentheses (usually the brand/trade name)
    import re
    m = re.search(r'\(([^)]+)\)', name)
    if m:
        return m.group(1).strip()

    # Fallback: take text before common corporate suffixes
    suffixes = r'(?:Co\.|Ltd\.|Inc\.|Corp\.|Corporation|Company|Group|Limited)'
    m = re.search(suffixes, name)
    if m:
        return name[:m.start()].strip().rstrip(',')

    return name


def get_company_brand_name():
    """Read company_name from company-profile/profile.json and extract brand name.

    Returns:
        Brand name string, or empty string if profile not found.
    """
    profile_path = SKILL_DIR.parent / "company-profile" / "profile.json"
    if not profile_path.exists():
        return ""
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            profile = json.load(f)
        company_name = profile.get("company_name", "")
        return extract_brand_name(company_name)
    except (json.JSONDecodeError, OSError):
        return ""


# ---------------------------------------------------------------------------
# Email-craft config reading (cross-skill table discovery)
# ---------------------------------------------------------------------------

def detect_ec_config():
    """Check email-craft config.json for recently used tables.

    Returns (config_dict, None) or (None, message).
    The config_dict is a flat dict with base_token, table_id, label, etc.
    """
    if not EC_CONFIG_FILE.exists():
        return None, "email-craft config not found"

    try:
        raw = json.loads(EC_CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None, "email-craft config is invalid"

    # Handle new format (current + history) or old flat format
    if "current" in raw:
        ec_config = raw["current"]
    else:
        ec_config = raw

    if not ec_config.get("base_token") or not ec_config.get("table_id"):
        return None, "email-craft config has no base_token/table_id"

    return ec_config, None


def get_ec_table_history():
    """Get list of tables from email-craft's history.

    Returns list of dicts with base_token, table_id, label, last_used, etc.
    Includes the current entry first if available.
    """
    if not EC_CONFIG_FILE.exists():
        return []

    try:
        raw = json.loads(EC_CONFIG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    entries = []

    # Add current entry if available
    if "current" in raw:
        current = raw["current"]
        if current.get("base_token") and current.get("table_id"):
            entries.append(current)

    # Add history entries (skip if same table_id as current)
    seen_ids = {e.get("table_id") for e in entries if e.get("table_id")}
    for h in raw.get("history", []):
        if h.get("table_id") and h["table_id"] not in seen_ids:
            entries.append(h)
            seen_ids.add(h["table_id"])

    return entries


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
