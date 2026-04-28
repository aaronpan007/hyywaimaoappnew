"""Environment pre-check for email-blast skill."""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

from utils import print_progress, load_env

# Load .env into environment before any checks
load_env()


def check_resend_api_key():
    """Check if RESEND_API_KEY is valid by calling Resend API.

    Tries /domains first (full access key), falls back to /audiences
    (sending access key). Either endpoint succeeding means the key is valid.
    """
    api_key = os.environ.get("RESEND_API_KEY", "")
    if not api_key:
        return False, "RESEND_API_KEY 未配置，请在 .env 中设置（见 references/resend-guide.md）"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "email-blast-skill/1.0",
    }

    # Try /domains endpoint first (requires full access)
    for endpoint in ["domains", "audiences"]:
        req = urllib.request.Request(
            f"https://api.resend.com/{endpoint}",
            headers=headers,
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if endpoint == "domains":
                    return True, f"API Key 有效（完整权限），已验证 {len(data.get('data', []))} 个域名"
                else:
                    return True, "API Key 有效（发送权限）"
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            try:
                err = json.loads(body)
                msg = err.get("message", err.get("error", {}).get("message", str(e)))
            except (json.JSONDecodeError, AttributeError):
                msg = body[:200]
            if e.code == 401 and "restricted to only send emails" in msg:
                # Sending-only key — valid for our use case
                return True, "API Key 有效（发送权限）"
            if e.code == 401:
                return False, f"API Key 无效: {msg}"
            if e.code == 403:
                # Permission denied — try next endpoint
                continue
            # Other 403/other on one endpoint — try the next
            continue
        except Exception as e:
            continue

    return False, "Resend API 连接失败"


def check_from_email():
    """Check if FROM_EMAIL is configured."""
    from_email = os.environ.get("FROM_EMAIL", "")
    if not from_email:
        return False, "FROM_EMAIL 未配置"
    # Basic format check
    if "@" not in from_email:
        return False, f"FROM_EMAIL 格式不正确: {from_email}"
    return True, f"发件人: {from_email}"


def check_domain_verification():
    """Check if the FROM_EMAIL domain is verified in Resend."""
    api_key = os.environ.get("RESEND_API_KEY", "")
    from_email = os.environ.get("FROM_EMAIL", "")

    if not api_key or not from_email:
        return None, "跳过（API Key 或 FROM_EMAIL 未配置）"

    domain = from_email.split("@")[-1]

    # onboarding@resend.dev is a built-in test sender, no domain verification needed
    if domain == "resend.dev":
        return True, f"测试发件人 {from_email}（无需域名验证，仅可发给已验证的收件人）"

    # Try to check domain status via /domains endpoint
    req = urllib.request.Request(
        "https://api.resend.com/domains",
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "email-blast-skill/1.0",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            domains = data.get("data", [])

            verified = False
            for d in domains:
                if d.get("name", "").lower() == domain.lower():
                    if d.get("status") == "not_started":
                        return False, f"域名 {domain} 已添加但未验证，请在 Resend 控制台完成 DNS 验证"
                    verified = True
                    break

            if verified:
                return True, f"域名 {domain} 已验证"
            return False, f"域名 {domain} 未在 Resend 中找到，请先添加并验证域名"
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            # Sending access key can't check domains — just warn
            return None, f"API Key 无权查询域名状态，请手动确认 {domain} 已在 Resend 中验证"
        return None, f"无法检查域名状态: HTTP {e.code}"
    except Exception as e:
        return None, f"无法检查域名状态: {e}"


def get_domain_dns_status():
    """Query Resend API for detailed DNS record status of the FROM_EMAIL domain.

    Returns dict with keys:
      - found (bool): domain exists in Resend
      - status (str): overall domain status (e.g. "verified", "not_started")
      - records (dict): per-record status, e.g.
          {"spf": True, "dkim": True, "dmarc": False}
      - missing (list): names of missing/unverified records
    Or None if the check can't be performed (e.g. sending-only API key).
    """
    api_key = os.environ.get("RESEND_API_KEY", "")
    from_email = os.environ.get("FROM_EMAIL", "")

    if not api_key or not from_email:
        return None

    domain = from_email.split("@")[-1]

    if domain == "resend.dev":
        return {"found": True, "status": "test", "records": {}, "missing": []}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "email-blast-skill/1.0",
    }

    # Step 1: Get domain ID from /domains list
    try:
        req = urllib.request.Request(
            "https://api.resend.com/domains",
            headers=headers,
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            domains = data.get("data", [])
            domain_id = None
            for d in domains:
                if d.get("name", "").lower() == domain.lower():
                    domain_id = d.get("id")
                    break
            if not domain_id:
                return {"found": False, "status": "not_found", "records": {}, "missing": ["domain"]}
    except (urllib.error.HTTPError, urllib.error.URLError, Exception):
        return None

    # Step 2: Get detailed domain info with records
    try:
        req = urllib.request.Request(
            f"https://api.resend.com/domains/{domain_id}",
            headers=headers,
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, Exception):
        return None

    overall_status = data.get("status", "unknown")
    records_list = data.get("records", [])

    # Parse per-record status
    records_status = {}
    for rec in records_list:
        name = rec.get("name", "").lower()
        status = rec.get("status", "")
        is_ok = status == "verified"
        if "spf" in name:
            records_status["spf"] = is_ok
        elif "dkim" in name:
            records_status["dkim"] = is_ok
        elif "dmarc" in name:
            records_status["dmarc"] = is_ok

    missing = [k.upper() for k, v in records_status.items() if not v]

    return {
        "found": True,
        "status": overall_status,
        "records": records_status,
        "missing": missing,
    }


def check_feishu_connection():
    """Check if Feishu table connection works."""
    from utils import get_feishu_config, run_lark_cli

    config = get_feishu_config()
    if not config:
        return False, "未找到飞书表格配置（config.json 或环境变量）"

    result = run_lark_cli([
        "base", "+field-list",
        "--base-token", config["base_token"],
        "--table-id", config["table_id"],
        "--as", config["identity"],
    ], timeout=15)

    if result is None:
        return False, "lark-cli 未安装或无法执行"
    if result.returncode != 0:
        return False, f"飞书表格访问失败: {result.stderr[:200] if result.stderr else result.stdout[:200]}"

    return True, "飞书表格连接正常"


def check_reply_to_email():
    """Check if REPLY_TO_EMAIL is configured.

    This is a soft check — the system works without it, but replies
    will go to the FROM_EMAIL address by default.
    """
    reply_to = os.environ.get("REPLY_TO_EMAIL", "")
    if not reply_to:
        return None, "REPLY_TO_EMAIL 未配置（客户回复将发到 FROM_EMAIL 地址）"
    if "@" not in reply_to:
        return None, f"REPLY_TO_EMAIL 格式不正确: {reply_to}"
    return True, f"回复邮箱: {reply_to}"


def run_check():
    """Run all pre-checks and print results."""
    print("🔍 环境预检")
    print("=" * 50)

    checks = [
        ("Resend API Key", check_resend_api_key),
        ("发件人邮箱", check_from_email),
        ("域名验证", check_domain_verification),
        ("回复邮箱", check_reply_to_email),
        ("飞书表格连接", check_feishu_connection),
    ]

    all_passed = True
    domain_failed = False
    from_email_failed = False

    for name, check_fn in checks:
        ok, msg = check_fn()
        if ok is True:
            print(f"  ✅ {name}: {msg}")
        elif ok is None:
            print(f"  ⚠️  {name}: {msg}")
        else:
            print(f"  ❌ {name}: {msg}")
            all_passed = False
            if name == "域名验证":
                domain_failed = True
            if name == "发件人邮箱":
                from_email_failed = True

    # Print guidance for common failures
    if domain_failed or from_email_failed:
        print()
        _print_domain_setup_guide()

    print("=" * 50)
    if all_passed:
        print("✅ 所有检查通过，可以开始发送。")
        return True
    else:
        print("❌ 部分检查未通过，请先解决上述问题再发送邮件。")
        return False


def _print_domain_setup_guide():
    """Print guidance for domain verification and FROM_EMAIL setup."""
    script_dir = Path(__file__).resolve().parent
    resend_guide = script_dir.parent / "references" / "resend-guide.md"
    guide_path = resend_guide if resend_guide.exists() else "references/resend-guide.md"

    print("📋 域名验证 & 发件人配置指引:")
    print("-" * 50)
    print()
    print("1. 在 Resend 控制台添加并验证发件域名:")
    print("   a. 登录 https://resend.com/domains")
    print("   b. 点击 'Add Domain'，输入你的域名")
    print("   c. 按提示在域名 DNS 中添加 Resend 要求的记录")
    print("   ⚠️  必须添加 SPF + DKIM + DMARC 三条记录，缺少 DMARC 会被 Google/Yahoo 拒收")
    print("   d. 等待 DNS 生效后点击 'Verify DNS'")
    print()
    print("2. 配置 FROM_EMAIL（发送前必须配置）:")
    print("   格式: 品牌名 <前缀@你的域名>")
    print("   示例: Acme Corp <sales@yourdomain.com>")
    print(f"   运行: python run.py --setup FROM_EMAIL=\"Brand <sales@yourdomain.com>\"")
    print()
    print(f"3. 详细步骤请参考: {guide_path}")
    print()
    print("4. 配置完成后，重新运行 --check-env 确认")
    print("-" * 50)


if __name__ == "__main__":
    passed = run_check()
    sys.exit(0 if passed else 1)
