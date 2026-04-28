"""AI email generation for Email Craft Skill — core logic."""

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    load_env, read_json, print_progress, print_error,
    build_profile_section, parse_ai_response, load_reference_emails,
)

try:
    import replicate
except ImportError:
    print_error("replicate not installed. Run: pip install replicate")
    sys.exit(1)

# ---------------------------------------------------------------------------
# System prompt — 3-layer structure
# ---------------------------------------------------------------------------

_BASE_SYSTEM_PROMPT = """你是一位经验丰富的B2B商务开发专家，擅长撰写高转化率的定制化开发信（cold email）。你的每一封邮件都必须让人感觉"这家公司认真研究过我们"。

## 严格规则（7条）

1. **开头自然且有针对性** — 先用 1 句简短自然的寒暄或引入（如提及对方最近的项目、行业动态、或"I came across your work on..."），让收件人感到这不是群发邮件。禁止使用 "Hope you are well"、"Hope this email finds you well" 等空洞模板开场白。寒暄要简短（1句话），不要占太多篇幅，快速过渡到正题。

2. **中间说明匹配理由** — 不要罗列产品目录。要从客户需求 × 我司能力的交叉分析出发，具体说明为什么双方值得合作，解决客户的什么痛点。

3. **案例必须相关** — 根据客户的行业、地区、项目类型，从我司案例中选择最相关的 1-2 个。不要堆砌不相关的案例。简要说明案例与客户的关联性。

4. **语气专业自然** — 像有经验的商务人士直接沟通。不要使用营销话术、感叹号轰炸、过度热情的语气。简洁、自信、专业。

5. **CTA 要轻量** — 以询问兴趣、提议简短通话、分享案例资料为主。不要硬性推销、不要催促、不要用 "Don't miss this opportunity" 之类的话术。

6. **禁止编造** — 只使用客户数据中已有的信息。不要编造客户的近期项目、业务规模、联系方式等。

7. **长度控制** — 英文邮件 150-300 词，中文邮件 200-400 字。宁可太短也不要太长。

## 输出格式

严格输出 JSON 格式，不要在 JSON 外附加任何文字：
{"email_subject": "邮件主题", "email_body": "邮件正文"}

邮件正文不要包含 Subject 行，只需纯正文内容。

## 邮件正文格式要求

email_body 必须是**纯文本**，严禁包含任何 Markdown 格式标记：
- 禁止 `**粗体**`、`*斜体*`、`~~删除线~~`
- 禁止 `## 标题`、`### 子标题`
- 禁止 `- 列表项`、`1. 有序列表`
- 禁止 `[链接文字](URL)`、`![图片](URL)`
- 禁止 `> 引用`、`--- 分割线`
- 如需强调，用大写或重复标点（如 "15,000 sqm" 而非 "**15,000 sqm**"）
- 如需分段，用空行分隔即可"""


def build_system_prompt(language, references=None):
    """Build the full system prompt with language and reference style injection."""
    parts = [_BASE_SYSTEM_PROMPT]

    # Language requirement
    if language == "cn":
        parts.append("\n## 语言要求\n请用中文撰写邮件。")
    else:
        parts.append("\n## 语言要求\nPlease write the email in English.")

    # Reference email styles
    if references:
        lang_refs = [r for r in references if r["language"] == language]
        if not lang_refs:
            lang_refs = [r for r in references if r["language"] != language]
        lang_refs = lang_refs[:3]

        if lang_refs:
            parts.append("\n## 参考邮件风格")
            parts.append("请学习以下邮件的写作风格（语气、结构、节奏），但不要复制内容：")
            for i, ref in enumerate(lang_refs, 1):
                parts.append(f"\n--- 参考邮件 {i} ({ref['filename']}) ---")
                parts.append(ref["content"][:2000])

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Smart case selection
# ---------------------------------------------------------------------------

def select_relevant_cases(customer, all_cases, max_cases=3):
    """Select the most relevant case studies for a specific customer.

    Scoring:
      - Same country: +100
      - Same industry overlap: +50
      - Same customer type: +30
      - International case (not China): +10
    """
    if not all_cases:
        return []

    customer_country = (customer.get("country") or "").lower()
    customer_industry = (customer.get("industry") or "").lower()
    customer_role = (customer.get("company_role") or "").lower()

    scored = []
    for case in all_cases:
        score = 0

        # Country match
        case_country = (case.get("country") or "").lower()
        if customer_country and case_country:
            if customer_country in case_country or case_country in customer_country:
                score += 100

        # Industry match
        case_industry = (case.get("industry") or "").lower()
        if customer_industry and case_industry:
            # Check for any keyword overlap
            ind_words = set(re.findall(r"\w+", customer_industry))
            case_words = set(re.findall(r"\w+", case_industry))
            if ind_words & case_words:
                score += 50

        # Customer type match
        case_client_type = (case.get("client_type") or "").lower()
        if customer_role and case_client_type:
            role_words = set(re.findall(r"\w+", customer_role))
            type_words = set(re.findall(r"\w+", case_client_type))
            if role_words & type_words:
                score += 30

        # International bonus
        if case_country and case_country not in ("中国", "china", "chinese"):
            score += 10

        scored.append((score, case))

    # Sort by score descending, take top N
    scored.sort(key=lambda x: x[0], reverse=True)
    return [case for _, case in scored[:max_cases]]


# ---------------------------------------------------------------------------
# User prompt construction
# ---------------------------------------------------------------------------

def build_user_prompt(customer, profile, selected_cases=None):
    """Build the user prompt for AI email generation."""
    lines = []

    # Customer info section
    lines.append("=== 客户信息 ===")
    lines.append(f"公司名称: {customer.get('company_name', 'N/A')}")
    lines.append(f"网站: {customer.get('website', 'N/A')}")
    lines.append(f"国家/地区: {customer.get('country', 'N/A')}")
    lines.append(f"行业: {customer.get('industry', 'N/A')}")
    lines.append(f"公司角色: {customer.get('company_role', 'N/A')}")
    lines.append(f"联系人: {customer.get('contact_name', 'N/A')}")
    lines.append(f"邮箱: {customer.get('email', 'N/A')}")

    ai_summary = customer.get("ai_summary", "").strip()
    if ai_summary:
        lines.append(f"\nAI分析摘要:\n{ai_summary}")

    match_points = customer.get("business_match_points", "").strip()
    if match_points:
        lines.append(f"\n业务匹配点:\n{match_points}")

    outreach = customer.get("outreach_content", "").strip()
    if outreach:
        lines.append(f"\n开发建议:\n{outreach}")

    # My company info — with smart case selection
    if profile:
        lines.append("")
        if selected_cases is not None:
            lines.append(build_profile_section(profile, cases_override=selected_cases))
        else:
            lines.append(build_profile_section(profile))

    lines.append("")
    lines.append("请根据以上信息，为这家客户撰写一封个性化开发信。")
    lines.append("严格遵守7条规则，输出 JSON 格式。")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AI call
# ---------------------------------------------------------------------------

def generate_email_for_customer(customer, profile, system_prompt, max_retries=2):
    """Generate a personalized email for a single customer.

    Returns {"email_subject": "...", "email_body": "..."} or None on failure.
    """
    # Smart case selection
    all_cases = [cs for cs in profile.get("case_studies", []) if cs.get("usable_in_outreach")]
    selected_cases = select_relevant_cases(customer, all_cases, max_cases=3)

    user_prompt = build_user_prompt(customer, profile, selected_cases)

    for attempt in range(max_retries + 1):
        try:
            output = replicate.run(
                "openai/gpt-5.2",
                input={
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )

            # Replicate returns response as string or list of tokens
            if isinstance(output, list):
                response_text = "".join(output)
            else:
                response_text = str(output)

            result = parse_ai_response(response_text)

            if result is None or "email_body" not in result:
                print_error(f"  Failed to parse AI response (attempt {attempt + 1})")
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                # Return raw response as body
                return {
                    "email_subject": result.get("email_subject", "") if result else "",
                    "email_body": response_text[:2000] if response_text else "",
                    "_parse_error": True,
                }

            # Validate
            subject = result.get("email_subject", "").strip()
            body = result.get("email_body", "").strip()
            if not body:
                print_error(f"  Empty email body (attempt {attempt + 1})")
                if attempt < max_retries:
                    time.sleep(2)
                    continue

            return {"email_subject": subject, "email_body": body}

        except Exception as e:
            print_error(f"  Replicate API error (attempt {attempt + 1}): {str(e)[:200]}")
            if attempt < max_retries:
                time.sleep(3)
                continue
            return None

    return None


# ---------------------------------------------------------------------------
# Batch generation
# ---------------------------------------------------------------------------

def generate_emails(customers, profile, language="en", references=None):
    """Generate emails for a list of customers.

    Args:
        customers: list of customer dicts
        profile: company profile dict
        language: "en" or "cn"
        references: list of reference email dicts

    Returns list of result dicts:
      {"record_id": str, "company_name": str, "email_subject": str, "email_body": str, "success": bool, "error": str}
    """
    system_prompt = build_system_prompt(language, references)
    results = []

    for i, customer in enumerate(customers):
        company_name = customer.get("company_name", "Unknown")
        record_id = customer.get("_record_id", "")
        print_progress("GENERATE", f"[{i+1}/{len(customers)}] Generating for {company_name}...")

        result = generate_email_for_customer(customer, profile, system_prompt)

        if result:
            results.append({
                "record_id": record_id,
                "company_name": company_name,
                "email_subject": result.get("email_subject", ""),
                "email_body": result.get("email_body", ""),
                "success": True,
                "error": "",
            })
            print_progress("GENERATE", f"    -> OK: subject={result.get('email_subject', '')[:50]}")
        else:
            results.append({
                "record_id": record_id,
                "company_name": company_name,
                "email_subject": "",
                "email_body": "",
                "success": False,
                "error": "AI generation failed after retries",
            })
            print_error(f"    -> FAILED for {company_name}")

        # Rate limiting
        if i < len(customers) - 1:
            time.sleep(1)

    success_count = sum(1 for r in results if r["success"])
    print_progress("GENERATE", f"Done. {success_count}/{len(customers)} emails generated successfully.")
    return results
