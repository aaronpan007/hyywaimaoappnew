"""Background pipeline for customer acquisition.

Runs as an asyncio.Task, independent of SSE connections.
All progress is written to task_logs table; the SSE layer polls that table.
"""

import asyncio
import json
import logging
import os
import random
import re
import time
from datetime import datetime
from urllib.parse import urlparse

import httpx
import replicate

from app.config import settings

# Ensure replicate library can find the token (pydantic-settings reads .env
# into the Settings object but does NOT set os.environ)
if settings.replicate_api_token and not os.environ.get("REPLICATE_API_TOKEN"):
    os.environ["REPLICATE_API_TOKEN"] = settings.replicate_api_token
from app.database import async_session_factory
from app.models.lead import Lead
from app.models.task import Task, TaskLog
from app.services import task_manager
from app.utils.contact import clean_contact_name
from app.utils.scraper import scrape_companies_sync

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"
RESULTS_PER_PAGE = 10

# ---------------------------------------------------------------------------
# AI Analysis
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """你是一位资深的B2B业务分析师，专精于国际市场客户开发。你的任务是根据抓取到的公司官网信息，全面评估每家公司的客户价值，并生成可直接用于业务跟进的分析报告。

## 分析要求

1. **基于抓取信息客观评估**，不要编造信息。如果信息不足以判断，明确标注"信息不足"。
2. **市场匹配判断要准确**：如果用户目标市场是美国，而这家公司明显是中国企业且主要面向国内市场，应如实标注地区不匹配。
3. **区分客户公司与我司信息**：`待分析公司` 是潜在客户，`我司信息` 只是用于判断业务匹配。严禁把我司名称、我司国家、我司产品当成客户公司的 `company_name`、`country` 或官网信息。
4. **所有输出必须是合法的 JSON 格式**，不要在 JSON 外附加任何文字。

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
  "contact_name": "官网明确出现的个人姓名；如果只是部门、职位、团队、邮箱前缀、建议联系对象、信息不足或推测结果，必须填空字符串。不要填写 Sales Team、Overseas Sales、President、信息不足、建议联系... 等非个人姓名内容"
}"""


def _build_profile_text(profile_data: dict | None) -> str:
    """Build a '我司信息' section from stored profile data."""
    if not profile_data:
        return ""

    lines = ["=== 我司信息 ==="]
    name = profile_data.get("company_name") or profile_data.get("companyName", "")
    if name:
        lines.append(f"公司名称: {name}")

    intro = profile_data.get("one_line_intro") or profile_data.get("oneLineIntro", "")
    if intro:
        lines.append(f"一句话介绍: {intro}")

    products = profile_data.get("products") or profile_data.get("products", [])
    if products:
        lines.append("")
        lines.append("--- 产品线 ---")
        for p in products[:10]:
            if isinstance(p, dict):
                lines.append(f"• {p.get('name', '')}")
                sp = p.get("key_selling_points", [])
                if sp:
                    lines.append(f"  卖点: {'；'.join(sp)}")
            elif isinstance(p, str):
                lines.append(f"• {p}")

    competencies = profile_data.get("core_competencies") or profile_data.get("competencies", [])
    if competencies:
        lines.append("")
        lines.append("--- 核心竞争力 ---")
        for c in competencies[:5]:
            if isinstance(c, dict):
                lines.append(f"• {c.get('competency', '')}: {c.get('evidence', c.get('description', ''))}")
            elif isinstance(c, str):
                lines.append(f"• {c}")

    return "\n".join(lines)


def _analyze_single_company_sync(
    company: dict, profile_data: dict | None, api_token: str
) -> dict:
    """Analyze a single company via Replicate API. Runs synchronously."""
    profile_text = _build_profile_text(profile_data)

    user_prompt = f"""请分析以下公司信息，评估其作为客户的潜在价值。

=== 待分析公司 ===
公司名称: {company.get('company_name', 'N/A')}
网站: {company.get('website', 'N/A')}
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
"""

    if profile_text:
        user_prompt += (
            "\n\n=== 我司信息（仅用于业务匹配，不是待分析客户） ===\n"
            "下面资料属于发起开发的我方公司，只能用于判断合作切入点。"
            "不要把这里的公司名称、所在地、产品写入待分析公司的 company_name/country。\n"
        )
        user_prompt += profile_text.replace("=== 我司信息 ===\n", "")
    else:
        user_prompt += "\n=== 我司信息 ===\n未提供，请仅基于公司信息进行客观分析。"

    user_prompt += "\n请严格按照 JSON 格式返回分析结果。"

    for attempt in range(3):
        try:
            output = replicate.run(
                settings.replicate_model,
                input={
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )

            if isinstance(output, list):
                response_text = "".join(output)
            else:
                response_text = str(output)

            analysis = _parse_ai_response(response_text)
            if analysis is not None:
                return analysis

            logger.warning(
                "Failed to parse AI response for %s (attempt %d)",
                company.get("_domain", ""),
                attempt + 1,
            )
            if attempt < 2:
                time.sleep(2)

        except Exception as e:
            logger.warning(
                "Replicate API error for %s (attempt %d): %s",
                company.get("_domain", ""),
                attempt + 1,
                str(e)[:200],
            )
            if attempt < 2:
                time.sleep(3)

    return {
        "parse_error": True,
        "ai_summary": "",
        "confidence_score": 0,
    }


def _parse_ai_response(response_text: str) -> dict | None:
    """Parse AI response, handling markdown code blocks and raw JSON."""
    text = response_text.strip()

    # Try markdown code block
    match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if match:
        text = match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the text
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        try:
            return json.loads(text[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    return None


def _clean_company_name(name: str) -> str:
    """Clean company name by removing common suffixes and boilerplate."""
    if not name:
        return name
    # Remove common website title suffixes: " - Home", " | Official Site", etc.
    name = re.split(r"\s*[|\-–—]\s*(?:Home|Welcome|Official Site|首页|欢迎|官方网站)\s*$", name, flags=re.IGNORECASE)[0]
    # Remove trailing CMS/platform names: " - WordPress", " | Shopify", etc.
    name = re.split(r"\s*[|\-–—]\s*(?:WordPress|Shopify|Wix|Squarespace|Weebly|GitHub Pages)\s*$", name, flags=re.IGNORECASE)[0]
    # Remove trailing pipe/dash sections that look like taglines (longer than main part)
    parts = re.split(r"\s*[|\-–—]\s+", name)
    if len(parts) > 1:
        main = parts[0].strip()
        rest = " ".join(parts[1:]).strip()
        if len(rest) > len(main) or re.match(r"^(Home|Welcome|首页|欢迎)", rest, re.IGNORECASE):
            name = main
    name = name.strip()
    if len(name) > 80:
        name = name[:80].rstrip()
    return name


def _name_fingerprint(name: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (name or "").lower())


def _domain_fallback_name(company: dict) -> str:
    domain = company.get("_domain", "") or urlparse(company.get("website", "")).netloc
    if domain.startswith("www."):
        domain = domain[4:]
    stem = domain.split(".")[0] if domain else ""
    return stem.replace("-", " ").replace("_", " ").title()


def _looks_like_own_company(value: str, profile_data: dict | None) -> bool:
    if not value or not profile_data:
        return False
    value_fp = _name_fingerprint(value)
    own_names = [
        profile_data.get("company_name"),
        profile_data.get("companyName"),
        profile_data.get("name"),
    ]
    for own_name in own_names:
        own_fp = _name_fingerprint(str(own_name or ""))
        if own_fp and (own_fp in value_fp or value_fp in own_fp):
            return True
    return False


def _country_aliases(country: str) -> list[str]:
    country_lower = (country or "").strip().lower()
    alias_map = {
        "usa": ["usa", "united states", "america", ".us"],
        "united states": ["usa", "united states", "america", ".us"],
        "美国": ["usa", "united states", "america", ".us", "美国"],
        "uk": ["uk", "united kingdom", "britain", ".uk"],
        "united kingdom": ["uk", "united kingdom", "britain", ".uk"],
        "英国": ["uk", "united kingdom", "britain", ".uk", "英国"],
        "canada": ["canada", "canadian", ".ca"],
        "加拿大": ["canada", "canadian", ".ca", "加拿大"],
        "brazil": ["brazil", "brasil", "brazilian", ".br"],
        "brasil": ["brazil", "brasil", "brazilian", ".br"],
        "巴西": ["brazil", "brasil", "brazilian", ".br", "巴西"],
        "china": ["china", "chinese", ".cn"],
        "中国": ["china", "chinese", ".cn", "中国"],
        "japan": ["japan", "japanese", ".jp"],
        "日本": ["japan", "japanese", ".jp", "日本"],
        "south korea": ["south korea", "korea", "korean", ".kr"],
        "韩国": ["south korea", "korea", "korean", ".kr", "韩国"],
    }
    return alias_map.get(country_lower, [country_lower] if country_lower else [])


def _country_matches(value: str, target_country: str) -> bool:
    text = (value or "").lower()
    aliases = _country_aliases(target_country)
    return bool(aliases and any(alias in text for alias in aliases))


def _merge_ai_fields(
    company: dict,
    analysis: dict,
    profile_data: dict | None = None,
) -> dict:
    """Merge AI analysis fields into the company dict."""
    if analysis.get("parse_error"):
        company["parse_error"] = True
        company["_ai_error"] = analysis.get("error", "AI response parse failed")
        return company

    ai_name = analysis.get("company_name", "")
    if ai_name and not _looks_like_own_company(ai_name, profile_data):
        company["company_name"] = _clean_company_name(ai_name)
    else:
        company["company_name"] = _clean_company_name(company.get("company_name", ""))
    if _looks_like_own_company(company.get("company_name", ""), profile_data):
        company["company_name"] = _domain_fallback_name(company)

    country = analysis.get("country", "") or company.get("_location", "")
    if _looks_like_own_company(country, profile_data):
        country = company.get("_location", "")
    if country and len(country) > 50:
        country = country[:50]
    company["country"] = country

    industry_kw = analysis.get("industry_keywords", [])
    if isinstance(industry_kw, list):
        company["industry"] = ", ".join(str(k) for k in industry_kw[:5])
    else:
        company["industry"] = str(industry_kw)

    company["company_role"] = analysis.get("supply_chain_role", "")
    company["contact_name"] = clean_contact_name(analysis.get("contact_name", ""))
    company["ai_summary"] = analysis.get("ai_summary", "")
    company["business_match_points"] = analysis.get("business_match_points", "")
    company["outreach_suggestion"] = analysis.get("outreach_suggestion", "")

    company["_market_match"] = analysis.get("market_match", "")
    company["_confidence_score"] = analysis.get("confidence_score", 0)

    return company


def _matches_target_requirements(company: dict, industry: str, target_country: str) -> bool:
    """Keep only companies that still match the requested country and industry."""
    if target_country:
        country_text = " ".join(
            str(company.get(k, ""))
            for k in ("country", "_location", "_domain", "website")
        ).lower()
        aliases = _country_aliases(target_country)
        if not any(alias in country_text for alias in aliases):
            return False

    if industry:
        haystack = " ".join(
            str(company.get(k, ""))
            for k in (
                "company_name",
                "industry",
                "_description",
                "_about_text",
                "_products_services",
                "ai_summary",
                "business_match_points",
            )
        ).lower()
        tokens = [
            token.lower()
            for token in re.split(r"[\s,;/|()（）\-]+", industry)
            if len(token.strip()) >= 3 or re.search(r"[\u4e00-\u9fff]", token)
        ]
        if tokens and not any(token in haystack for token in tokens):
            return False

    return True


# ---------------------------------------------------------------------------
# Search helpers (ported from toolkit search_companies.py)
# ---------------------------------------------------------------------------

BLOCKED_DOMAINS = {
    # Social media
    "facebook.com", "twitter.com", "x.com", "instagram.com",
    "linkedin.com", "youtube.com", "tiktok.com", "reddit.com",
    # Encyclopedias / reviews / travel
    "wikipedia.org", "yelp.com", "tripadvisor.com",
    # Marketplaces
    "amazon.com", "alibaba.com", "aliexpress.com", "made-in-china.com",
    "globalsources.com", "dhgate.com", "ebay.com", "etsy.com", "walmart.com",
    # Business directories / data providers
    "crunchbase.com", "zoominfo.com", "bloomberg.com",
    "yellowpages.com", "hotfrog.com", "foursquare.com",
    "thomasnet.com", "kompass.com", "tradekorea.com",
    # Other non-company sites
    "pinterest.com", "quora.com", "medium.com",
    # Ranking / listicle sites
    "g2.com", "capterra.com", "softwareadvice.com", "trustpilot.com",
    # Job boards
    "indeed.com", "glassdoor.com", "monster.com", "ziprecruiter.com",
    # Q&A / wiki clones
    "stackexchange.com", "answers.com", "about.com",
}

BLOCKED_DOMAIN_SUFFIXES = (
    # Universities / academic
    ".edu.", ".ac.",  # matches .edu.xx, .ac.uk, etc.
    ".edu/", ".ac/",
    # Government
    ".gov.", ".govt.",
    ".gov/", ".govt/",
    # Military
    ".mil.",
)

# Words commonly found in ranking/directory/listicle site domains
BLOCKED_DOMAIN_KEYWORDS = (
    "top10", "top100", "bestof", "ranking", "ranked",
    "directory", "catalog", "catalogue",
    "businessdirectory", "companylist", "tradeforum",
)

BLOCKED_PATH_PATTERNS = [
    r"/news/", r"/blog/", r"/article/", r"/press-release/",
    r"/wiki/", r"/forum/", r"/review/", r"/coupon/",
    r"/jobs/", r"/career/", r"/wikipedia",
    r"/how-to/", r"/guide/", r"/tips/",
    r"/top-\d+", r"/best-",
]


def _is_company_url(url: str) -> bool:
    url_lower = url.lower()
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
    except Exception:
        return False

    # Block specific domains
    for blocked in BLOCKED_DOMAINS:
        if blocked in domain:
            return False

    # Block domain suffixes (.edu, .gov, etc.)
    for suffix in BLOCKED_DOMAIN_SUFFIXES:
        if suffix in domain:
            return False

    # Block ranking/directory keywords in domain
    for kw in BLOCKED_DOMAIN_KEYWORDS:
        if kw in domain:
            return False

    # Block root-only .edu / .gov TLDs
    root_domain = domain.split(".")[0] + "." + ".".join(domain.split(".")[1:])
    tld_parts = domain.rsplit(".", 1)
    if len(tld_parts) == 2:
        tld = tld_parts[1]
        if tld in ("edu", "gov", "govt", "mil", "ac"):
            return False

    # Block path patterns
    for pattern in BLOCKED_PATH_PATTERNS:
        if re.search(pattern, url_lower):
            return False

    if re.search(r"\.(pdf|jpg|jpeg|png|gif|svg|css|js|zip)(\?|$)", url_lower):
        return False

    return True


def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url


def _generate_queries(industry: str, country: str, keywords: list[str]) -> list[str]:
    """Generate multiple search query combinations."""
    queries = []
    role_terms = {
        "company", "supplier", "manufacturer", "distributor", "wholesaler",
        "dealer", "importer", "buyer", "agent", "retailer", "trader",
        "local company",
    }
    normalized_keywords = [k.strip() for k in keywords if k and k.strip()]
    roles = [k for k in normalized_keywords if k.lower() in role_terms]
    refinements = [k for k in normalized_keywords if k.lower() not in role_terms]

    if not roles:
        roles = ["company", "supplier", "manufacturer"]

    for role in roles:
        queries.append(f"{industry} {role} in {country}")
        if role != "local company":
            queries.append(f"top {industry} {role} {country}")
            queries.append(f"best {industry} {role} {country}")
        for suffix in ["manufacturer", "distributor", "wholesaler", "supplier"]:
            if suffix.lower() not in role.lower():
                queries.append(f"{industry} {suffix} {country}")

    for refinement in refinements:
        queries.append(f"{industry} {refinement} company in {country}")
        queries.append(f"{refinement} {industry} manufacturer {country}")
        queries.append(f"{refinement} {industry} supplier {country}")
        if "hotel" in refinement.lower():
            queries.append(f"{industry} for hotels manufacturer {country}")

    if refinements:
        joined_refinements = " ".join(refinements[:3])
        queries.append(f"{industry} {joined_refinements} company {country}")

    # Deduplicate
    seen: set[str] = set()
    unique = []
    for q in queries:
        q_lower = q.lower().strip()
        if q_lower not in seen:
            seen.add(q_lower)
            unique.append(q.strip())
    return unique


async def _serper_search(query: str, api_key: str) -> list[dict]:
    """Call Serper API and return organic results."""
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "num": RESULTS_PER_PAGE,
        "gl": "us",
        "hl": "en",
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(SERPER_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("organic", [])
    except httpx.HTTPStatusError as e:
        logger.error("Serper API error for query '%s': %s", query, e)
        return []
    except httpx.RequestError as e:
        logger.error("Serper network error for query '%s': %s", query, e)
        return []


# ---------------------------------------------------------------------------
# Filter & Rank (ported from toolkit run.py)
# ---------------------------------------------------------------------------

def _filter_and_rank(
    companies: list[dict], target_num: int, target_country: str
) -> list[dict]:
    """Rank companies by quality and keep top target_num."""
    if len(companies) <= target_num:
        return companies

    match_score_map = {"High": 3, "Medium": 2, "Low": 1, "": 0}

    def score(c: dict) -> float:
        s = 0.0
        s += float(c.get("_confidence_score", 0) or 0)
        s += match_score_map.get(c.get("_market_match", ""), 0) * 15
        country = c.get("country", "").lower()
        if target_country and target_country.lower() in country:
            s += 20
        if c.get("email"):
            s += 10
        if c.get("phone"):
            s += 5
        role = c.get("company_role", "").lower()
        # Penalize non-company roles heavily
        non_company_keywords = ["服务商", "平台", "目录", "协会", "媒体", "出版",
                                "大学", "学院", "研究", "政府", "机构", "非营利", "nonprofit",
                                "university", "college", "institute", "research",
                                "government", "agency", "association", "media", "publisher",
                                "directory", "portal"]
        if any(w in role for w in non_company_keywords):
            s -= 50
        # Penalize companies with no AI summary
        if not c.get("ai_summary"):
            s -= 30
        return s

    ranked = sorted(companies, key=score, reverse=True)
    return ranked[:target_num]


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _create_task_log(
    db,
    task_id: int,
    step: int,
    name: str,
    status: str = "running",
    message: str = "",
    progress: int = 0,
) -> TaskLog:
    log = TaskLog(
        task_id=task_id,
        step_number=step,
        step_name=name,
        status=status,
        message=message,
        progress=progress,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


async def _update_task_log(
    db,
    task_id: int,
    step: int,
    status: str | None = None,
    message: str | None = None,
    progress: int | None = None,
) -> None:
    from sqlalchemy import select

    result = await db.execute(
        select(TaskLog).where(
            TaskLog.task_id == task_id,
            TaskLog.step_number == step,
        )
    )
    log = result.scalar_one_or_none()
    if log is None:
        return
    if status is not None:
        log.status = status
    if message is not None:
        log.message = message
    if progress is not None:
        log.progress = progress
    await db.commit()


async def _update_scrape_progress_log(
    task_id: int,
    completed: int,
    total: int,
    domain: str,
    status: str,
) -> None:
    """Persist per-site scrape progress from the scraper worker thread."""
    progress = int((completed / max(total, 1)) * 95)
    async with async_session_factory() as progress_db:
        await _update_task_log(
            progress_db,
            task_id,
            step=3,
            message=f"已抓取 {completed}/{total}: {domain} ({status})",
            progress=progress,
        )


async def _load_profile(db, user_id: int) -> dict | None:
    """Load the user's current company profile data."""
    from app.models.company_profile import CompanyProfile
    from sqlalchemy import select

    result = await db.execute(
        select(CompanyProfile).where(
            CompanyProfile.user_id == user_id,
            CompanyProfile.is_current == True,  # noqa: E712
        )
    )
    profile = result.scalar_one_or_none()
    if profile and profile.profile_data:
        return profile.profile_data
    return None


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

OVER_FETCH_RATIO = 3


async def run_pipeline(task_id: int, user_id: int, intent: dict) -> None:
    """Run the full customer-acquisition pipeline in the background.

    Args:
        task_id: The Task ID in the database.
        user_id: The user who initiated this pipeline.
        intent: Dict from intent_router with 'params' containing
                industry, country, keywords, num.

    All progress is written to task_logs; this function does NOT yield SSE.
    """
    async with async_session_factory() as db:
        try:
            # Register this pipeline in task_manager
            task_manager.register_task(task_id, asyncio.current_task())

            params = intent["params"] if isinstance(intent.get("params"), dict) else {}
            search_num = params.get("num", 20) * OVER_FETCH_RATIO

            # --- Step 1: Analyze requirements ---
            await _create_task_log(
                db, task_id, step=1,
                name="分析需求",
                status="completed",
                message=f"行业: {params.get('industry', '')}, 地区: {params.get('country', '')}, 目标: {params.get('num', 20)} 家",
                progress=100,
            )
            task_manager.update_heartbeat(task_id)

            # --- Step 2: Serper search ---
            await _create_task_log(
                db, task_id, step=2,
                name="搜索公司数据",
                status="running",
                message="正在生成搜索查询...",
                progress=0,
            )

            queries = _generate_queries(
                params.get("industry", ""), params.get("country", ""), params.get("keywords", [])
            )
            companies: list[dict] = []
            seen_domains: set[str] = set()

            for i, query in enumerate(queries):
                if len(companies) >= search_num:
                    break

                await _update_task_log(
                    db, task_id, step=2,
                    message=f"搜索查询 {i + 1}/{len(queries)}: {query}",
                    progress=int(i / len(queries) * 80),
                )

                results = await _serper_search(query, settings.serper_api_key)

                for result in results:
                    if len(companies) >= search_num:
                        break
                    url = result.get("link", "")
                    if not url or not _is_company_url(url):
                        continue
                    domain = _extract_domain(url)
                    if domain in seen_domains:
                        continue
                    seen_domains.add(domain)
                    companies.append({
                        "company_name": result.get("title", ""),
                        "website": url,
                        "_domain": domain,
                        "_snippet": result.get("snippet", ""),
                        "_query": query,
                    })

                # Rate limiting
                if i < len(queries) - 1 and len(companies) < search_num:
                    await asyncio.sleep(random.uniform(1.0, 2.5))

                task_manager.update_heartbeat(task_id)

            await _update_task_log(
                db, task_id, step=2,
                status="completed",
                message=f"已搜索 {len(companies)} 家公司（共 {len(queries)} 个查询）",
                progress=100,
            )
            task_manager.update_heartbeat(task_id)

            if not companies:
                task = await db.get(Task, task_id)
                task.status = "failed"
                task.ended_at = datetime.now()
                task.result_summary = {"found": 0, "error": "未找到任何公司"}
                await db.commit()
                await _create_task_log(
                    db, task_id, step=3,
                    name="抓取网站信息",
                    status="completed",
                    message="跳过（无搜索结果）",
                    progress=100,
                )
                await _create_task_log(
                    db, task_id, step=4,
                    name="AI 分析匹配",
                    status="completed",
                    message="跳过（无搜索结果）",
                    progress=100,
                )
                await _create_task_log(
                    db, task_id, step=5,
                    name="保存结果",
                    status="completed",
                    message="完成（无结果）",
                    progress=100,
                )
                return

            # --- Step 3: Playwright scraping ---
            await _create_task_log(
                db, task_id, step=3,
                name="抓取网站信息",
                status="running",
                message=f"正在抓取 {len(companies)} 个网站...",
                progress=0,
            )

            loop = asyncio.get_running_loop()

            def scrape_progress_callback(
                completed: int,
                total: int,
                domain: str,
                status: str,
            ) -> None:
                task_manager.update_heartbeat(task_id)
                future = asyncio.run_coroutine_threadsafe(
                    _update_scrape_progress_log(
                        task_id,
                        completed,
                        total,
                        domain,
                        status,
                    ),
                    loop,
                )
                try:
                    future.result(timeout=5)
                except Exception as e:
                    logger.warning(
                        "Failed to persist scrape progress for task %d: %s",
                        task_id,
                        str(e)[:200],
                    )

            companies = await asyncio.to_thread(
                scrape_companies_sync,
                companies,
                30,
                scrape_progress_callback,
            )

            scraped_ok = sum(
                1 for c in companies if c.get("_scrape_status") != "failed"
            )

            viable = [c for c in companies if c.get("_scrape_status") != "failed"]

            # Post-scrape quality filter: drop companies with no useful content
            viable = [
                c for c in viable
                if c.get("_description") or c.get("_about_text") or c.get("_products_services")
            ]
            quality_dropped = scraped_ok - len(viable)

            await _update_task_log(
                db, task_id, step=3,
                status="completed",
                message=f"成功抓取 {scraped_ok}/{len(companies)} 个网站",
                progress=100,
            )
            # Log quality filter result
            if quality_dropped > 0:
                logger.info(
                    "Quality filter dropped %d/%d scraped companies (no useful content)",
                    quality_dropped, scraped_ok,
                )
            task_manager.update_heartbeat(task_id)

            # --- Step 4: AI analysis ---
            await _create_task_log(
                db, task_id, step=4,
                name="AI 分析匹配",
                status="running",
                message="正在加载公司画像...",
                progress=0,
            )

            profile_data = await _load_profile(db, user_id)

            if not viable:
                await _update_task_log(
                    db, task_id, step=4,
                    status="completed",
                    message="无可用网站数据，跳过 AI 分析",
                    progress=100,
                )
                ranked = []
            else:
                for i, company in enumerate(viable):
                    analysis = await asyncio.to_thread(
                        _analyze_single_company_sync,
                        company,
                        profile_data,
                        settings.replicate_api_token,
                    )
                    _merge_ai_fields(company, analysis, profile_data)

                    progress = int((i + 1) / len(viable) * 100)
                    await _update_task_log(
                        db, task_id, step=4,
                        message=f"AI 分析 {i + 1}/{len(viable)}: {company.get('_domain', '')}",
                        progress=progress,
                    )

                    # Rate limiting
                    if i < len(viable) - 1:
                        await asyncio.sleep(1)

                    task_manager.update_heartbeat(task_id)

                analyzed_ok = [
                    c for c in viable
                    if not c.get("parse_error")
                    and _matches_target_requirements(
                        c,
                        params.get("industry", ""),
                        params.get("country", ""),
                    )
                    and (c.get("ai_summary") or c.get("business_match_points") or c.get("outreach_suggestion"))
                ]

                await _update_task_log(
                    db, task_id, step=4,
                    status="completed",
                    message=f"AI 分析完成 {len(analyzed_ok)}/{len(viable)} 家合格客户",
                    progress=100,
                )
                task_manager.update_heartbeat(task_id)

                ranked = _filter_and_rank(analyzed_ok, params.get("num", 20), params.get("country", ""))

            # --- Step 5: Save to DB ---
            await _create_task_log(
                db, task_id, step=5,
                name="保存结果",
                status="running",
                message=f"正在保存 {len(ranked)} 条线索...",
                progress=0,
            )

            total_score = 0
            for i, company in enumerate(ranked):
                lead = Lead(
                    task_id=task_id,
                    company_name=company.get("company_name", ""),
                    website=company.get("website", ""),
                    country=company.get("country", ""),
                    industry=company.get("industry", ""),
                    company_role=company.get("company_role", ""),
                    contact_name=company.get("contact_name", ""),
                    email=company.get("email", ""),
                    phone=company.get("phone", ""),
                    ai_summary=company.get("ai_summary", ""),
                    business_match=company.get("business_match_points", ""),
                    outreach_suggestion=company.get("outreach_suggestion", ""),
                    match_score=float(company.get("_confidence_score", 0)),
                )
                db.add(lead)
                total_score += lead.match_score

            await _update_task_log(
                db, task_id, step=5,
                status="completed",
                message=f"已保存 {len(ranked)} 条线索",
                progress=100,
            )

            # Update task
            task = await db.get(Task, task_id)
            task.status = "completed"
            task.ended_at = datetime.now()
            avg_score = total_score / len(ranked) if ranked else 0
            task.result_summary = {
                "found": len(ranked),
                "searched": len(companies),
                "scraped": scraped_ok,
                "analyzed": len(viable),
                "avgScore": round(avg_score, 1),
                "industry": params.get("industry", ""),
                "country": params.get("country", ""),
            }
            await db.commit()

            logger.info(
                "Pipeline completed: task=%d, found=%d, avgScore=%.1f",
                task_id, len(ranked), avg_score,
            )

        except asyncio.CancelledError:
            logger.info("Pipeline cancelled for task %d", task_id)
            try:
                task = await db.get(Task, task_id)
                if task and task.status == "running":
                    from datetime import timezone
                    task.status = "cancelled"
                    task.ended_at = datetime.now(timezone.utc)
                    task.cancelled = True
                    await db.commit()
            except Exception:
                pass

        except Exception as e:
            logger.exception("Pipeline failed for task %d", task_id)
            try:
                task = await db.get(Task, task_id)
                if task:
                    task.status = "failed"
                    task.ended_at = datetime.now()
                    task.result_summary = {"error": str(e)[:500]}
                    await db.commit()
            except Exception:
                pass

        finally:
            task_manager.remove_task(task_id)
