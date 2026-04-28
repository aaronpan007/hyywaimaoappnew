"""Phase 3: Analyze companies using Replicate AI (openai/gpt-5.2)."""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import load_env, read_json, write_json, print_progress, print_error

try:
    import replicate
except ImportError:
    print_error("replicate not installed. Run: pip install replicate")
    sys.exit(1)

SYSTEM_PROMPT = """你是一位资深的B2B业务分析师，专精于国际市场客户开发。你的任务是根据抓取到的公司官网信息，全面评估每家公司的客户价值，并生成可直接用于业务跟进的分析报告。

## 分析要求

1. **基于抓取信息客观评估**，不要编造信息。如果信息不足以判断，明确标注"信息不足"。
2. **市场匹配判断要准确**：如果用户目标市场是美国，而这家公司明显是中国企业且主要面向国内市场，应如实标注地区不匹配。
3. **所有输出必须是合法的 JSON 格式**，不要在 JSON 外附加任何文字。

## 输出 JSON 结构

{
  "company_name": "公司英文名称（从官网提取）",
  "country": "公司所在国家/地区（如 United States, China, Germany 等）",
  "industry_keywords": ["关键词1", "关键词2", "关键词3"],
  "supply_chain_role": "制造商/批发商/品牌商/服务商/渠道商/其他",

  "ai_summary": "（这是一段完整可读的分析摘要，必须包含以下全部7个要点，用编号分段）

【1.公司概况】这家公司是做什么的，主营产品或服务是什么，属于什么行业，处在产业链的什么位置（制造商/批发商/品牌商/服务商/渠道商）。

【2.市场与地区】这家公司服务的市场和区域是什么，是否与用户要求的目标地区匹配。如果目标地区是北美但这家公司主要面向中国国内市场，要明确指出不匹配。

【3.潜在需求】从官网公开信息推断这家公司可能需要什么资源、什么服务、什么供应能力（如原材料采购、OEM代工、海外渠道代理、技术合作等）。

【4.近期动态】这家公司最近有没有动态线索，如新产品发布、参加展会、业务扩张、招聘信息、博客/新闻更新等。这些都可以作为开发信的切入点。如果未发现近期动态，明确说明。

【5.匹配理由】明确说明为什么这家公司值得联系，从行业匹配、地区匹配、产品匹配、潜在合作点等角度分析。如果匹配度低，也要说明原因。

【6.缺失信息】列出分析中缺失的关键信息，如没有找到邮箱、没有明确联系人、没有定价信息、没有明显近期动态等。

【7.置信度评分】给出0-100分的置信度分数，表示对"这是一家值得开发的潜在客户"的信心。100分=非常有价值且信息充分，0分=完全不相关或信息严重不足。",

  "business_match_points": "（简洁明确的业务匹配切入点描述，2-4句话）从价格优势、交期优势、定制能力、过往案例匹配、供应链能力、认证资质等角度分析我司最适合从什么角度切入。这一列决定了后续开发信不会写成泛泛而谈。",

  "market_match": "High/Medium/Low",
  "confidence_score": 75,
  "outreach_suggestion": "开发信切入建议（含邮件主题建议，要具体、可操作）",
  "contact_name": "推测的联系人姓名（如无法判断填空字符串）"
}"""


def load_profile(profile_path):
    """Load and validate a company profile JSON file.

    Returns the profile dict, or None if loading fails.
    """
    try:
        profile = read_json(profile_path)
        if not profile.get("company_name"):
            print_error(f"WARNING: profile.json missing 'company_name' field, ignoring profile.")
            return None
        return profile
    except Exception as e:
        print_error(f"WARNING: Failed to load profile {profile_path}: {e}")
        return None


def build_profile_section(profile, my_company, my_products):
    """Build a structured '我司信息' section from profile.json data.

    CLI args my_company/my_products override profile values when provided.
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

    # Representative case studies (usable_in_outreach=true, max 10)
    cases = [cs for cs in profile.get("case_studies", []) if cs.get("usable_in_outreach")]
    if cases:
        # Pick up to 10 representative cases: prioritize international ones, then well-known clients
        international = [c for c in cases if c.get("country") and c["country"] not in ("中国",)]
        domestic = [c for c in cases if c.get("country") in ("中国",)]
        selected = (international[:7] + domestic[:3])[:10]
        lines.append("")
        lines.append("--- 代表性案例 ---")
        for cs in selected:
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


def build_user_prompt(company, my_company, my_products, profile=None):
    """Build the user prompt for AI analysis."""
    company_section = f"""请分析以下公司信息，评估其作为客户的潜在价值。

=== 待分析公司 ===
公司名称: {company.get('company_name', 'N/A')}
网站: {company.get('website', company.get('url', 'N/A'))}
域名: {company.get('_domain', 'N/A')}

公司简介/描述:
{company.get('_description', 'N/A')}

About页面内容:
{company.get('_about_text', 'N/A')[:3000]}

产品/服务:
{company.get('_products_services', 'N/A')[:2000]}

所在地: {company.get('_location', 'N/A')}
邮箱: {company.get('email', 'N/A')}
电话: {company.get('phone', 'N/A')}
LinkedIn: {company.get('_linkedin', 'N/A')}
社媒链接: {json.dumps(company.get('_social_links', {}), ensure_ascii=False) if company.get('_social_links') else 'N/A'}
"""

    if profile:
        company_section += "\n" + build_profile_section(profile, my_company, my_products)
    elif my_company and my_products:
        company_section += f"""
=== 我司信息 ===
公司名称: {my_company}
主要产品/服务: {my_products}
"""
    else:
        company_section += """
=== 我司信息 ===
未提供，请仅基于公司信息进行客观分析。
"""

    return company_section + "\n请严格按照 JSON 格式返回分析结果。"


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


def analyze_single_company(company, my_company, my_products, max_retries=2, profile=None):
    """Analyze a single company using Replicate API. Returns merged data dict."""
    user_prompt = build_user_prompt(company, my_company, my_products, profile=profile)

    for attempt in range(max_retries + 1):
        try:
            output = replicate.run(
                "openai/gpt-5.2",
                input={
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )

            # Replicate returns the response as a string or list of tokens
            if isinstance(output, list):
                response_text = "".join(output)
            else:
                response_text = str(output)

            analysis = parse_ai_response(response_text)

            if analysis is None:
                print_error(f"  Failed to parse AI response (attempt {attempt + 1})")
                if attempt < max_retries:
                    time.sleep(2)
                    continue
                analysis = {
                    "parse_error": True,
                    "raw_response": response_text[:2000],
                    "ai_summary": response_text[:500],
                    "confidence_score": 0,
                }

            return analysis

        except Exception as e:
            print_error(f"  Replicate API error (attempt {attempt + 1}): {str(e)[:200]}")
            if attempt < max_retries:
                time.sleep(3)
                continue
            return {
                "parse_error": True,
                "error": str(e)[:500],
                "ai_summary": "",
                "confidence_score": 0,
            }


def merge_ai_fields(company, analysis):
    """Merge AI analysis fields into the existing unified record."""
    # Company name — AI may provide a better one
    ai_name = analysis.get("company_name", "")
    if ai_name:
        company["company_name"] = ai_name

    # Country from AI, fallback to scraped location
    country = analysis.get("country", "") or company.get("_location", "")
    if country and len(country) > 50:
        country = country[:50]
    company["country"] = country

    # Industry keywords as comma-separated string
    industry_kw = analysis.get("industry_keywords", [])
    if isinstance(industry_kw, list):
        company["industry"] = ", ".join(str(k) for k in industry_kw[:5])
    else:
        company["industry"] = str(industry_kw)

    # Other AI fields
    company["company_role"] = analysis.get("supply_chain_role", "")
    company["contact_name"] = analysis.get("contact_name", "")
    company["ai_summary"] = analysis.get("ai_summary", "")
    company["business_match_points"] = analysis.get("business_match_points", "")
    company["outreach_content"] = analysis.get("outreach_suggestion", "")

    # Store AI metadata in underscore-prefixed keys
    company["_market_match"] = analysis.get("market_match", "")
    company["_confidence_score"] = analysis.get("confidence_score", 0)

    return company


def main():
    parser = argparse.ArgumentParser(description="Phase 3: AI analysis via Replicate")
    parser.add_argument("--input", required=True, help="Input JSON from Phase 2")
    parser.add_argument("--output", default="analyzed_results.json", help="Output JSON file")
    parser.add_argument("--my-company", default="", help="Your company name (optional, overrides profile)")
    parser.add_argument("--my-products", default="", help="Your products/services description (optional, overrides profile)")
    parser.add_argument("--my-profile", default="", help="Path to company-profile skill's profile.json (optional, enriches AI analysis)")
    parser.add_argument("--max-retries", type=int, default=2, help="Max retries per company")
    args = parser.parse_args()

    load_env()

    api_token = os.environ.get("REPLICATE_API_TOKEN")
    if not api_token:
        print_error("REPLICATE_API_TOKEN not set in .env file.")
        sys.exit(1)

    scraped_data = read_json(args.input)
    companies = scraped_data.get("companies", [])

    # Load profile if provided
    profile = None
    if args.my_profile:
        profile = load_profile(args.my_profile)
        if profile:
            # Auto-fill my_company/my_products from profile if not explicitly provided
            if not args.my_company:
                args.my_company = profile.get("company_name", "")
            if not args.my_products:
                prods = profile.get("products", [])
                args.my_products = "; ".join(p.get("name", "") for p in prods[:3])
            print_progress("ANALYZE", f"Loaded company profile: {profile.get('company_name', '')}")

    # Warn if no company info at all
    if not args.my_company and not args.my_products and not profile:
        print_progress("ANALYZE", "WARNING: --my-company/--my-products not provided and no profile loaded. AI analysis will lack match scoring context.")

    # Filter out failed companies (check _scrape_status from Phase 2)
    viable = [c for c in companies if c.get("_scrape_status") != "failed"]
    skipped = len(companies) - len(viable)

    print_progress("ANALYZE", f"Loaded {len(companies)} companies, {skipped} failed, {len(viable)} to analyze")

    analyzed = []
    start_time = time.time()

    for i, company in enumerate(viable):
        domain = company.get("_domain", "unknown")
        print_progress("ANALYZE", f"  [{i+1}/{len(viable)}] Analyzing {domain}...")

        analysis = analyze_single_company(company, args.my_company, args.my_products, args.max_retries, profile=profile)

        merged = merge_ai_fields(company, analysis)
        analyzed.append(merged)

        confidence = analysis.get("confidence_score", 0)
        match = analysis.get("market_match", "N/A")
        elapsed = time.time() - start_time
        eta = elapsed / (i + 1) * (len(viable) - i - 1) if i + 1 < len(viable) else 0
        print_progress("ANALYZE", f"    -> match:{match}, confidence:{confidence} | elapsed {elapsed:.0f}s, ETA {eta:.0f}s")

        # Rate limiting
        if i < len(viable) - 1:
            time.sleep(1)

    output = {
        "metadata": {
            "total_input": len(companies),
            "analyzed": len(analyzed),
            "skipped_failed": skipped,
            "my_company": args.my_company,
            "my_products": args.my_products,
            "profile_used": bool(profile),
        },
        "companies": analyzed,
    }

    write_json(args.output, output)

    # Summary
    high_match = sum(1 for c in analyzed if c.get("ai_summary", "") and "High" in c.get("ai_summary", ""))
    medium_match = sum(1 for c in analyzed if c.get("ai_summary", "") and "Medium" in c.get("ai_summary", ""))
    low_match = sum(1 for c in analyzed if c.get("ai_summary", "") and "Low" in c.get("ai_summary", ""))

    print_progress("ANALYZE", f"Done. Analyzed {len(analyzed)} companies.")
    print_progress("ANALYZE", f"  High match: {high_match}, Medium: {medium_match}, Low: {low_match}")
    print_progress("ANALYZE", f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
