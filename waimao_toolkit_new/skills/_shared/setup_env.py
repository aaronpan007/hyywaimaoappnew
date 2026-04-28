"""Shared environment variable setup module.

Provides a unified flow for checking env status, detecting missing/placeholder
values, and writing values into the project root .env file.

Usage from each skill's run.py:
    from setup_env import check_setup, write_env_var
    result = check_setup(PROJECT_ROOT, "customer-acquisition")
    write_env_var(PROJECT_ROOT, "SERPER_API_KEY", "abc123")
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Placeholder detection patterns
# ---------------------------------------------------------------------------

_PLACEHOLDER_PATTERNS = [
    re.compile(r"^your_\w+_here$", re.IGNORECASE),
    re.compile(r"^Brand Name$", re.IGNORECASE),
    re.compile(r"^yourdomain\.com$", re.IGNORECASE),
    re.compile(r"^your_reply_email@gmail\.com$", re.IGNORECASE),
    re.compile(r"^changeme$", re.IGNORECASE),
    re.compile(r"^TODO$", re.IGNORECASE),
    re.compile(r"^xxx$", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# Hint registry — maps env var key -> human-readable guidance
# ---------------------------------------------------------------------------

SKILL_HINTS = {
    "SERPER_API_KEY": "Google 搜索 API，搜索目标公司。从 https://serper.dev 免费获取（2500次/月）",
    "REPLICATE_API_TOKEN": "AI 模型调用，分析匹配度 + 生成开发信。从 https://replicate.com/account/api-tokens 获取",
    "RESEND_API_KEY": "邮件发送 API。从 https://resend.com/api-keys 获取（Sending access 权限）。详见 references/resend-guide.md",
    "FROM_EMAIL": "发件人邮箱。域名须在 Resend 完成 DNS 验证。⚠ 阶段A跳过此项，等company-profile建好后再配置。禁止用域名自动拼品牌名（域名≠公司名）",
    "REPLY_TO_EMAIL": "客户回复接收地址。未设置则发到 FROM_EMAIL（可选）",
}


def _get_lark_cli_cmd() -> list[str] | None:
    """Get the Node.js command to run lark-cli, bypassing the .CMD wrapper."""
    npm_dir = os.path.join(os.environ.get("APPDATA", ""), "npm")
    run_js = os.path.join(npm_dir, "node_modules", "@larksuite", "cli", "scripts", "run.js")
    if os.path.isfile(run_js):
        return ["node", run_js]
    return None


def get_auth_url() -> dict:
    """Get a Feishu verification URL for device-flow auth (non-blocking).

    Calls ``lark-cli auth login --recommend --no-wait`` which returns
    immediately with a verification URL the user can open in a browser.

    Returns:
        {"ok": True, "verification_url": "...", "device_code": "...", "expires_in": N}
        {"ok": False, "error": "..."}
    """
    cmd = _get_lark_cli_cmd()
    if not cmd:
        return {"ok": False, "error": "lark-cli not installed. Run: npm install -g @larksuite/cli"}

    full_cmd = cmd + ["auth", "login", "--recommend", "--no-wait"]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    try:
        result = subprocess.run(
            full_cmd, capture_output=True, timeout=15,
            encoding="utf-8", errors="replace", env=env,
        )
    except (subprocess.TimeoutExpired, Exception) as e:
        return {"ok": False, "error": f"lark-cli 执行失败: {e}"}

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        return {"ok": False, "error": stderr or stdout or "unknown error"}

    try:
        data = json.loads(result.stdout)
        url = data.get("verification_url", "")
        if url:
            return {
                "ok": True,
                "verification_url": url,
                "device_code": data.get("device_code", ""),
                "expires_in": data.get("expires_in", 600),
            }
        return {"ok": False, "error": f"no verification_url in response: {result.stdout[:200]}"}
    except (json.JSONDecodeError, TypeError):
        return {"ok": False, "error": f"无法解析 lark-cli 输出: {result.stdout[:200]}"}


def _is_placeholder(value: str) -> bool:
    """Return True if *value* looks like an unfilled placeholder."""
    v = value.strip()
    if not v:
        return True
    return any(p.match(v) for p in _PLACEHOLDER_PATTERNS)


def _find_example_file(skill_dir: Path, project_root: Path) -> Path | None:
    """Locate the .env.example file for a skill.

    Priority:
      1. <skill_dir>/.env.example
      2. <project_root>/.env.example
    """
    candidate = skill_dir / ".env.example"
    if candidate.exists():
        return candidate
    candidate = project_root / ".env.example"
    if candidate.exists():
        return candidate
    return None


def _parse_example(example_path: Path) -> list[dict]:
    """Parse .env.example into a list of variable descriptors.

    Each entry: {"key": str, "description": str, "default": str}
    """
    entries = []
    for line in example_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, default = line.partition("=")
        key = key.strip()
        default = default.strip()
        if key:
            entries.append({
                "key": key,
                "description": SKILL_HINTS.get(key, ""),
                "default": default,
            })
    return entries


def _read_env(env_file: Path) -> dict[str, str]:
    """Read current .env values into a dict. Missing file → empty dict."""
    values: dict[str, str] = {}
    if not env_file.exists():
        return values
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key:
            values[key] = value.strip()
    return values


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_setup(project_root: Path, skill_name: str, skill_dir: Path | None = None) -> dict:
    """Check env variable status for a skill.

    Args:
        project_root: Directory containing .env file.
        skill_name: Name of the skill (used for fallback path discovery).
        skill_dir: Explicit path to the skill directory. If None, derived
                   as project_root / ".claude" / "skills" / skill_name.

    Returns a JSON-serialisable dict:
      {"status": "ok", "env_file": "...", "missing_vars": []}
      {"status": "incomplete", "env_file": "...", "missing_vars": [
        {"key": "...", "status": "missing"|"placeholder",
         "description": "...", "hint": "...", "current_value": "..."}
      ]}
    """
    if skill_dir is None:
        skill_dir = project_root / ".claude" / "skills" / skill_name
    env_file = project_root / ".env"

    example_path = _find_example_file(skill_dir, project_root)
    if example_path is None:
        return {
            "status": "ok",
            "env_file": str(env_file),
            "missing_vars": [],
            "note": f"No .env.example found for {skill_name}",
        }

    required = _parse_example(example_path)
    if not required:
        return {
            "status": "ok",
            "env_file": str(env_file),
            "missing_vars": [],
        }

    current = _read_env(env_file)
    missing: list[dict] = []

    for entry in required:
        key = entry["key"]
        value = current.get(key, "")

        if not value:
            missing.append({
                "key": key,
                "status": "missing",
                "description": entry["description"],
                "hint": SKILL_HINTS.get(key, ""),
                "current_value": "",
            })
        elif _is_placeholder(value):
            missing.append({
                "key": key,
                "status": "placeholder",
                "description": entry["description"],
                "hint": SKILL_HINTS.get(key, ""),
                "current_value": value,
            })

    return {
        "status": "ok" if not missing else "incomplete",
        "env_file": str(env_file),
        "missing_vars": missing,
    }


def write_env_var(project_root: Path, key: str, value: str) -> None:
    """Write or update a single environment variable in .env.

    Creates the file if it doesn't exist. Preserves comments and other
    variables. Trailing whitespace on the value is stripped.
    """
    env_file = project_root / ".env"
    env_file.parent.mkdir(parents=True, exist_ok=True)

    key = key.strip()
    value = value.strip()

    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    found = False
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        line_key, _, _ = stripped.partition("=")
        if line_key.strip() == key:
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)

    if not found:
        if new_lines and new_lines[-1] != "":
            new_lines.append("")
        new_lines.append(f"{key}={value}")

    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
