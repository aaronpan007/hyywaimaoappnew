"""Playwright-based website scraper for company information.

Runs synchronously in its own thread (via asyncio.to_thread from pipeline).
Extracts emails, phones, LinkedIn, about/products text from company websites.
"""

import asyncio
import logging
import random
import re
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Regex patterns
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?\(?\d{2,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,4}"
)
LINKEDIN_PATTERN = re.compile(r"linkedin\.com/company/[\w\-]+")

BLOCKED_EMAILS = {
    "noreply", "no-reply", "admin@example", "test@", "example@",
    "webmaster@", "postmaster@", "abuse@", "spam@", "null@",
}

# Navigation link patterns (multilingual)
NAV_PATTERNS = [
    re.compile(r"(?:about|关于我们|会社概要|회사소개)", re.I),
    re.compile(r"(?:contact|联系我们|お問い合わせ|문의)", re.I),
    re.compile(r"(?:products?|services?|产品|サービス|제품)", re.I),
]

# Pre-installed Chromium path
_CHROMIUM_PATH = (
    Path.home() / "AppData" / "Local" / "ms-playwright" / "chromium-1208"
    / "chrome-win64" / "chrome.exe"
)


def _find_chromium() -> str | None:
    if _CHROMIUM_PATH.exists():
        return str(_CHROMIUM_PATH)
    return None


def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url


def _clean_text(text: str) -> str:
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", text, flags=re.I)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_emails(text: str) -> list[str]:
    emails = set(EMAIL_PATTERN.findall(text))
    valid = []
    for email in emails:
        email_lower = email.lower()
        if any(blocked in email_lower for blocked in BLOCKED_EMAILS):
            continue
        if email_lower.endswith(".png") or email_lower.endswith(".jpg"):
            continue
        valid.append(email)
    return list(valid)


def _extract_phones(text: str) -> list[str]:
    phones = PHONE_PATTERN.findall(text)
    seen: set[str] = set()
    valid = []
    for phone in phones:
        digits = re.sub(r"\D", "", phone)
        if len(digits) < 7:
            continue
        if digits in seen:
            continue
        seen.add(digits)
        valid.append(phone.strip())
    return valid[:5]


def _extract_linkedin(text: str, url: str) -> str:
    matches = LINKEDIN_PATTERN.findall(text)
    if matches:
        return f"https://www.{matches[0]}"
    url_matches = LINKEDIN_PATTERN.findall(url)
    if url_matches:
        return f"https://www.{url_matches[0]}"
    return ""


async def _scrape_single_company(page, company: dict, timeout_ms: int) -> dict:
    """Scrape a single company website. Returns updated company dict."""
    url = company.get("website", "")
    if not url:
        company["_scrape_status"] = "failed"
        return company

    domain = company.get("_domain", _extract_domain(url))

    scrape_state = {
        "scrape_status": "failed",
        "homepage_text": "",
        "about_text": "",
        "products_services": "",
        "location": "",
        "description": company.get("_snippet", ""),
        "emails": [],
        "phones": [],
        "linkedin": "",
        "errors": [],
    }

    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        if response and response.status >= 400:
            scrape_state["errors"].append(f"HTTP {response.status}")
            company["_scrape_status"] = "failed"
            return company

        # Get title
        title = await page.title()
        if title:
            company["company_name"] = title

        # Get homepage text
        body_text = await page.evaluate(
            "() => document.body ? document.body.innerText : ''"
        )
        scrape_state["homepage_text"] = _clean_text(body_text)[:3000]

        # Extract contact info from homepage
        all_text = body_text + " " + url
        scrape_state["emails"] = _extract_emails(all_text)
        scrape_state["phones"] = _extract_phones(body_text)
        scrape_state["linkedin"] = _extract_linkedin(body_text, url)

        # Extract meta description
        meta_desc = await page.evaluate(
            """() => {
                const meta = document.querySelector('meta[name="description"]');
                return meta ? meta.content : '';
            }"""
        )
        if meta_desc:
            scrape_state["description"] = meta_desc

        # Extract location
        location = await page.evaluate(
            """() => {
                const schema = document.querySelector('[itemtype*="Organization"] [itemprop="address"]');
                if (schema) return schema.textContent;
                const footer = document.querySelector('footer');
                if (footer) {
                    const match = footer.innerText.match(/[\\w\\s,]+(?:Street|St|Ave|Avenue|Blvd|Boulevard|Road|Rd|Drive|Dr|Suite|Ste|Floor|Fl)\\s*[\\w\\s,]+[\\d]{5}/i);
                    if (match) return match[0].trim();
                }
                return '';
            }"""
        )
        if location:
            scrape_state["location"] = location.strip()

        # Find navigation links
        nav_links = await page.evaluate(
            """() => {
                const links = Array.from(document.querySelectorAll('a[href]'));
                return links.map(a => ({
                    href: a.href,
                    text: a.textContent.trim().toLowerCase()
                })).filter(l => l.text.length > 0 && l.text.length < 50);
            }"""
        )

        # Navigate to About/Contact/Products pages
        pages_scraped = 0
        max_pages = 3

        for nav_re in NAV_PATTERNS:
            if pages_scraped >= max_pages:
                break

            matched_links = [l for l in nav_links if nav_re.search(l["text"])]
            if not matched_links:
                continue

            link = matched_links[0]
            page_name = link["text"][:30]

            try:
                resp = await page.goto(
                    link["href"], wait_until="domcontentloaded", timeout=timeout_ms
                )

                if resp and resp.status < 400:
                    page_text = await page.evaluate(
                        "() => document.body ? document.body.innerText : ''"
                    )
                    page_text = _clean_text(page_text)[:3000]

                    if nav_re == NAV_PATTERNS[0]:  # About
                        scrape_state["about_text"] = page_text
                    elif nav_re == NAV_PATTERNS[1]:  # Contact
                        new_emails = _extract_emails(page_text)
                        new_phones = _extract_phones(page_text)
                        scrape_state["emails"] = list(
                            set(scrape_state["emails"] + new_emails)
                        )
                        scrape_state["phones"] = list(
                            set(scrape_state["phones"] + new_phones)
                        )
                        linkedin = _extract_linkedin(page_text, link["href"])
                        if linkedin:
                            scrape_state["linkedin"] = linkedin
                        scrape_state["about_text"] = (
                            scrape_state["about_text"] or page_text
                        )
                    elif nav_re == NAV_PATTERNS[2]:  # Products
                        scrape_state["products_services"] = page_text[:2000]

                    pages_scraped += 1
                    await asyncio.sleep(random.uniform(2, 5))

            except Exception as e:
                scrape_state["errors"].append(f"Nav to '{page_name}': {str(e)[:100]}")
                continue

        # Determine scrape status
        if pages_scraped >= 2:
            scrape_state["scrape_status"] = "full"
        else:
            scrape_state["scrape_status"] = "partial"

    except Exception as e:
        scrape_state["errors"].append(str(e)[:200])
        logger.warning("Failed to scrape %s: %s", url, str(e)[:200])

    # Merge scraped data into company dict
    company["email"] = ", ".join(scrape_state["emails"])[:200]
    company["phone"] = ", ".join(scrape_state["phones"])[:200]
    company["_scrape_status"] = scrape_state["scrape_status"]
    company["_description"] = scrape_state["description"]
    company["_about_text"] = scrape_state["about_text"]
    company["_products_services"] = scrape_state["products_services"]
    company["_location"] = scrape_state["location"]
    company["_linkedin"] = scrape_state["linkedin"]
    company["_homepage_text"] = scrape_state["homepage_text"]

    return company


async def _scrape_all_async(companies: list[dict], timeout_s: int = 30) -> list[dict]:
    """Async internal: scrape all companies with Playwright."""
    from playwright.async_api import async_playwright

    timeout_ms = timeout_s * 1000

    async with async_playwright() as p:
        launch_kwargs = {"headless": True}
        chromium = _find_chromium()
        if chromium:
            launch_kwargs["executable_path"] = chromium

        browser = await p.chromium.launch(**launch_kwargs)

        for i, company in enumerate(companies):
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            companies[i] = await _scrape_single_company(page, company, timeout_ms)
            logger.info(
                "Scraped %d/%d: %s -> %s",
                i + 1,
                len(companies),
                company.get("_domain", ""),
                companies[i].get("_scrape_status", "unknown"),
            )

            await context.close()

            if i < len(companies) - 1:
                await asyncio.sleep(random.uniform(2, 5))

        await browser.close()

    return companies


def scrape_companies_sync(companies: list[dict], timeout_s: int = 30) -> list[dict]:
    """Synchronous entry point — runs its own event loop.

    Called via asyncio.to_thread() from the async pipeline.
    """
    return asyncio.run(_scrape_all_async(companies, timeout_s))
