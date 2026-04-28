"""Phase 2: Scrape company websites for contact information using Playwright."""

import argparse
import asyncio
import json
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils import load_env, read_json, write_json, print_progress, print_error, extract_domain

try:
    from playwright.async_api import async_playwright
except ImportError:
    print_error("playwright not installed. Run: pip install playwright")
    sys.exit(1)

# Path to pre-installed Chromium (avoids needing headless shell)
_CHROMIUM_PATHS = [
    Path.home() / "AppData" / "Local" / "ms-playwright" / "chromium-1208" / "chrome-win64" / "chrome.exe",
]

def find_chromium():
    for p in _CHROMIUM_PATHS:
        if Path(p).exists():
            return str(p)
    return None

# Regex patterns
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[\s\-.]?)?\(?\d{2,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,4}"
)
LINKEDIN_PATTERN = re.compile(r"linkedin\.com/company/[\w\-]+")

# Social media patterns for footer extraction
SOCIAL_PATTERNS = {
    "facebook": re.compile(r"(?:facebook\.com|fb\.com)/[\w.\-]+", re.I),
    "instagram": re.compile(r"instagram\.com/[\w.\-]+", re.I),
    "twitter": re.compile(r"(?:twitter\.com|x\.com)/[\w.\-]+", re.I),
    "youtube": re.compile(r"youtube\.com/(?:channel/|c/|@)?[\w.\-]+", re.I),
}

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


def clean_text(text):
    """Extract and clean visible text from HTML content."""
    # Remove scripts, styles, and tags
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", text, flags=re.I)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_emails(text):
    """Extract valid emails from text, filtering out generic ones."""
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


def extract_phones(text):
    """Extract phone numbers from text."""
    phones = PHONE_PATTERN.findall(text)
    # Deduplicate and filter short matches
    seen = set()
    valid = []
    for phone in phones:
        digits = re.sub(r"\D", "", phone)
        if len(digits) < 7:
            continue
        if digits in seen:
            continue
        seen.add(digits)
        valid.append(phone.strip())
    return valid[:5]  # Max 5 phones


def extract_linkedin(text, url):
    """Extract LinkedIn company URL from text or page URL."""
    # Check page text
    matches = LINKEDIN_PATTERN.findall(text)
    if matches:
        return f"https://www.{matches[0]}"
    # Check page URL
    url_matches = LINKEDIN_PATTERN.findall(url)
    if url_matches:
        return f"https://www.{url_matches[0]}"
    return ""


def extract_social_links(html_text, page_url):
    """Extract social media links from page HTML source."""
    links = {}
    for platform, pattern in SOCIAL_PATTERNS.items():
        matches = pattern.findall(html_text)
        if matches:
            # Deduplicate and clean
            seen = set()
            clean = []
            for m in matches:
                m_lower = m.lower()
                if m_lower not in seen and len(m) > 5:
                    seen.add(m_lower)
                    # Ensure full URL
                    if not m_lower.startswith("http"):
                        m = f"https://{m}"
                    clean.append(m)
            if clean:
                links[platform] = clean[0]  # Take first match
    return links


async def scrape_facebook_page(page, fb_url, timeout_ms):
    """Visit a Facebook page and extract contact info (email, phone)."""
    emails = []
    phones = []
    try:
        print_progress("SCRAPE", f"    Visiting Facebook: {fb_url[:60]}...")
        response = await page.goto(fb_url, wait_until="domcontentloaded", timeout=timeout_ms)
        if response and response.status < 400:
            body_text = await page.evaluate("() => document.body ? document.body.innerText : ''")
            text = clean_text(body_text)
            emails = extract_emails(text + " " + fb_url)
            phones = extract_phones(text)
            await asyncio.sleep(random.uniform(1, 2))
    except Exception as e:
        print_progress("SCRAPE", f"    Facebook scrape error: {str(e)[:80]}")
    return emails, phones


async def scrape_company(page, company, timeout_ms):
    """Scrape a single company website. Merges findings into the existing record."""
    url = company.get("website", company.get("url", ""))
    rank = company.get("rank", 0) or company.get("_rank", 0)
    domain = company.get("_domain", extract_domain(url))

    # Internal scrape state (not part of unified schema)
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
        "pages_visited": [],
        "scrape_errors": [],
    }

    try:
        # Load homepage
        print_progress("SCRAPE", f"  [{rank}] Loading {url}")
        response = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        if response and response.status >= 400:
            scrape_state["scrape_errors"].append(f"HTTP {response.status}")
            scrape_state["scrape_status"] = "failed"
            return company, scrape_state

        # Get homepage title
        title = await page.title()
        if title:
            company["company_name"] = title

        # Get homepage text
        body_text = await page.evaluate("() => document.body ? document.body.innerText : ''")
        scrape_state["homepage_text"] = clean_text(body_text)[:3000]

        # Extract contact info from homepage
        all_text = body_text + " " + url
        scrape_state["emails"] = extract_emails(all_text)
        scrape_state["phones"] = extract_phones(body_text)
        scrape_state["linkedin"] = extract_linkedin(body_text, url)

        # Extract social media links from raw HTML (footer area)
        raw_html = await page.evaluate("() => document.documentElement.outerHTML")
        social_links = extract_social_links(raw_html, url)
        scrape_state["social_links"] = social_links

        # Extract meta description
        meta_desc = await page.evaluate(
            """() => {
                const meta = document.querySelector('meta[name="description"]');
                return meta ? meta.content : '';
            }"""
        )
        if meta_desc:
            scrape_state["description"] = meta_desc

        # Extract location from schema or text
        location = await page.evaluate(
            """() => {
                // Try schema.org
                const schema = document.querySelector('[itemtype*="Organization"] [itemprop="address"]');
                if (schema) return schema.textContent;
                // Try common footer patterns
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

        # Find and click navigation links
        nav_links = await page.evaluate(
            """() => {
                const links = Array.from(document.querySelectorAll('a[href]'));
                return links.map(a => ({
                    href: a.href,
                    text: a.textContent.trim().toLowerCase()
                })).filter(l => l.text.length > 0 && l.text.length < 50);
            }"""
        )

        pages_scraped = 0
        max_pages = 3  # About + Contact + Products

        for nav_re in NAV_PATTERNS:
            if pages_scraped >= max_pages:
                break

            matched_links = [l for l in nav_links if nav_re.search(l["text"])]
            if not matched_links:
                continue

            # Pick the first matching link
            link = matched_links[0]
            page_name = link["text"][:30]

            try:
                print_progress("SCRAPE", f"  [{rank}] Navigating to '{page_name}'")
                resp = await page.goto(link["href"], wait_until="domcontentloaded", timeout=timeout_ms)

                if resp and resp.status < 400:
                    page_text = await page.evaluate("() => document.body ? document.body.innerText : ''")
                    page_text = clean_text(page_text)[:3000]
                    scrape_state["pages_visited"].append(page_name)

                    # Categorize page content
                    if nav_re == NAV_PATTERNS[0]:  # About
                        scrape_state["about_text"] = page_text
                    elif nav_re == NAV_PATTERNS[1]:  # Contact
                        # Extract more contact info from contact page
                        new_emails = extract_emails(page_text)
                        new_phones = extract_phones(page_text)
                        scrape_state["emails"] = list(set(scrape_state["emails"] + new_emails))
                        scrape_state["phones"] = list(set(scrape_state["phones"] + new_phones))
                        linkedin = extract_linkedin(page_text, link["href"])
                        if linkedin:
                            scrape_state["linkedin"] = linkedin
                        scrape_state["about_text"] = scrape_state["about_text"] or page_text
                    elif nav_re == NAV_PATTERNS[2]:  # Products
                        scrape_state["products_services"] = page_text[:2000]

                    pages_scraped += 1
                    # Random delay between page navigations
                    await asyncio.sleep(random.uniform(2, 5))

            except Exception as e:
                scrape_state["scrape_errors"].append(f"Nav to '{page_name}': {str(e)[:100]}")
                continue

        # Determine scrape status
        if pages_scraped >= 2:
            scrape_state["scrape_status"] = "full"
        elif pages_scraped >= 1:
            scrape_state["scrape_status"] = "partial"
        else:
            scrape_state["scrape_status"] = "partial"  # Homepage only

        # If no emails found on main site, try Facebook page
        if not scrape_state["emails"] and social_links.get("facebook"):
            try:
                fb_emails, fb_phones = await scrape_facebook_page(page, social_links["facebook"], timeout_ms)
                if fb_emails:
                    scrape_state["emails"] = list(set(scrape_state["emails"] + fb_emails))
                    print_progress("SCRAPE", f"  [{rank}] Found {len(fb_emails)} email(s) from Facebook")
                if fb_phones:
                    scrape_state["phones"] = list(set(scrape_state["phones"] + fb_phones))
            except Exception:
                pass

    except Exception as e:
        error_msg = str(e)[:200]
        scrape_state["scrape_errors"].append(error_msg)
        print_error(f"  [{rank}] Failed to scrape {url}: {error_msg}")

    return company, scrape_state


async def main_async():
    parser = argparse.ArgumentParser(description="Phase 2: Scrape company websites")
    parser.add_argument("--input", required=True, help="Input JSON from Phase 1")
    parser.add_argument("--output", default="scraped_results.json", help="Output JSON file")
    parser.add_argument("--timeout", type=int, default=30, help="Page load timeout in seconds")
    parser.add_argument("--max-concurrent", type=int, default=3, help="Max concurrent browsers")
    args = parser.parse_args()

    load_env()

    # Read input
    search_data = read_json(args.input)
    companies = search_data.get("companies", [])
    print_progress("SCRAPE", f"Loaded {len(companies)} companies from {args.input}")

    timeout_ms = args.timeout * 1000
    status_counts = {"full": 0, "partial": 0, "failed": 0}
    start_time = time.time()

    async with async_playwright() as p:
        launch_kwargs = {"headless": True}
        chromium = find_chromium()
        if chromium:
            launch_kwargs["executable_path"] = chromium
        else:
            print_progress("SCRAPE", "Using default Playwright chromium (may need headless shell)")
        browser = await p.chromium.launch(**launch_kwargs)

        for i, company in enumerate(companies):
            # Launch a new context for each company (isolation)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            updated_company, scrape_state = await scrape_company(page, company, timeout_ms)

            # Merge scraped fields into the unified record
            updated_company["email"] = ", ".join(scrape_state["emails"])[:200]
            updated_company["phone"] = ", ".join(scrape_state["phones"])[:200]
            updated_company["_scrape_status"] = scrape_state["scrape_status"]
            updated_company["_description"] = scrape_state["description"]
            updated_company["_about_text"] = scrape_state["about_text"]
            updated_company["_products_services"] = scrape_state["products_services"]
            updated_company["_location"] = scrape_state["location"]
            updated_company["_linkedin"] = scrape_state["linkedin"]
            updated_company["_homepage_text"] = scrape_state["homepage_text"]
            updated_company["_scrape_errors"] = scrape_state["scrape_errors"]
            updated_company["_social_links"] = scrape_state.get("social_links", {})

            companies[i] = updated_company

            status = scrape_state["scrape_status"]
            emails = len(scrape_state["emails"])
            phones = len(scrape_state["phones"])
            domain = updated_company.get("_domain", "")
            elapsed = time.time() - start_time
            eta = elapsed / (i + 1) * (len(companies) - i - 1) if i + 1 < len(companies) else 0
            print_progress("SCRAPE", f"  [{i+1}/{len(companies)}] {domain} -> {status} (emails:{emails}, phones:{phones}) | elapsed {elapsed:.0f}s, ETA {eta:.0f}s")
            status_counts[status] = status_counts.get(status, 0) + 1

            await context.close()

            # Delay between companies
            if i < len(companies) - 1:
                await asyncio.sleep(random.uniform(2, 5))

        await browser.close()

    output = {
        "metadata": {
            "total_input": len(companies),
            "successfully_scraped": status_counts["full"],
            "partially_scraped": status_counts["partial"],
            "failed": status_counts["failed"],
        },
        "companies": companies,
    }

    write_json(args.output, output)

    print_progress("SCRAPE", f"Done. Full:{status_counts['full']}, Partial:{status_counts['partial']}, Failed:{status_counts['failed']}")
    print_progress("SCRAPE", f"Results saved to {args.output}")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
