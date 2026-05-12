"""Playwright-based website scraper for company information.

Runs synchronously in its own thread (via asyncio.to_thread from pipeline).
Extracts emails, phones, LinkedIn, about/products text from company websites.
"""

import asyncio
import logging
import os
import random
import re
import shutil
import sys
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

LOW_VALUE_EMAIL_PREFIXES = {
    "noreply", "no-reply", "do-not-reply", "donotreply", "example", "test",
    "privacy", "abuse", "spam", "webmaster", "postmaster",
    "info-request", "registrar",
}

PREFERRED_EMAIL_PREFIXES = (
    "sales", "export", "exports", "business", "bd", "commercial",
    "contact", "info", "office", "marketing",
)

SOCIAL_DOMAINS = {
    "facebook.com": "facebook",
    "instagram.com": "instagram",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "linkedin.com": "linkedin",
    "x.com": "x",
    "twitter.com": "x",
    "tiktok.com": "tiktok",
    "pinterest.com": "pinterest",
}

V2_PAGE_PRIORITIES = (
    ("home", re.compile(r"^/?(?:index\.html?)?$", re.I)),
    ("contact", re.compile(r"(contact|contact-us|get-in-touch|inquiry|enquiry|support)", re.I)),
    ("about", re.compile(r"(about|about-us|company|who-we-are|profile)", re.I)),
    ("products", re.compile(r"(products?|services?|solutions?|capabilities)", re.I)),
    ("team", re.compile(r"(team|leadership|management|staff|people)", re.I)),
)

# Navigation link patterns (multilingual)
NAV_PATTERNS = [
    re.compile(r"(?:about|关于我们|会社概要|회사소개)", re.I),
    re.compile(r"(?:contact|联系我们|お問い合わせ|문의)", re.I),
    re.compile(r"(?:products?|services?|产品|サービス|제품)", re.I),
]

# Pre-installed Chromium path (platform-aware)
if sys.platform == "win32":
    _CHROMIUM_PATH = (
        Path.home() / "AppData" / "Local" / "ms-playwright" / "chromium-1208"
        / "chrome-win64" / "chrome.exe"
    )
else:
    _CHROMIUM_PATH = (
        Path.home() / ".cache" / "ms-playwright" / "chromium-1208"
        / "chrome-linux" / "chrome"
    )

# System Chromium paths to try (Linux)
_SYSTEM_CHROMIUM_PATHS = [
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/snap/bin/chromium",
]


def _find_chromium() -> str | None:
    # Try Playwright-managed Chromium first
    if _CHROMIUM_PATH.exists():
        return str(_CHROMIUM_PATH)
    # Fall back to system Chromium
    for path in _SYSTEM_CHROMIUM_PATHS:
        if Path(path).exists():
            return path
    # Try shutil.which as last resort
    found = shutil.which("chromium-browser") or shutil.which("chromium")
    if found:
        return found
    return None


def _needs_no_sandbox() -> bool:
    """Linux root or container environments need --no-sandbox."""
    return sys.platform == "linux" and os.getuid() == 0


def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = (parsed.hostname or parsed.netloc).lower()
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


def _normalize_email(email: str) -> str:
    return (email or "").strip().strip(".,;:()[]<>").lower()


def _deobfuscate_email_text(text: str) -> str:
    normalized = text
    replacements = [
        (r"\s*\[\s*at\s*\]\s*", "@"),
        (r"\s*\(\s*at\s*\)\s*", "@"),
        (r"\s+at\s+", "@"),
        (r"\s*\[\s*dot\s*\]\s*", "."),
        (r"\s*\(\s*dot\s*\)\s*", "."),
        (r"\s+dot\s+", "."),
    ]
    for pattern, repl in replacements:
        normalized = re.sub(pattern, repl, normalized, flags=re.I)
    return normalized


def _is_low_value_email(email: str) -> bool:
    email_lower = _normalize_email(email)
    if "@" not in email_lower:
        return True
    prefix, domain = email_lower.split("@", 1)
    if not prefix or not domain or "." not in domain:
        return True
    if any(prefix == blocked or prefix.startswith(f"{blocked}.") for blocked in LOW_VALUE_EMAIL_PREFIXES):
        return True
    if any(token in email_lower for token in ("example.", "yourdomain", "domain.com", "email.com")):
        return True
    if any(token in domain for token in ("sentry", "wixpress.com", "wix.com", "sentry.io")):
        return True
    if re.fullmatch(r"[a-f0-9]{20,}", prefix):
        return True
    if re.search(r"\.(png|jpe?g|gif|svg|webp|css|js)$", email_lower):
        return True
    return False


def _email_score(email: str, company_domain: str) -> int:
    email_lower = _normalize_email(email)
    prefix, domain = email_lower.split("@", 1)
    score = 0
    if company_domain and (domain == company_domain or domain.endswith("." + company_domain)):
        score += 50
    if prefix in PREFERRED_EMAIL_PREFIXES:
        score += 30 + (len(PREFERRED_EMAIL_PREFIXES) - PREFERRED_EMAIL_PREFIXES.index(prefix))
    elif any(prefix.startswith(p + ".") or prefix.startswith(p + "-") for p in PREFERRED_EMAIL_PREFIXES):
        score += 20
    if prefix in ("support", "help"):
        score -= 15
    return score


def _rank_emails(emails: list[str], company_domain: str) -> list[str]:
    seen: set[str] = set()
    valid: list[str] = []
    for raw in emails:
        email = _normalize_email(raw)
        if not email or email in seen or _is_low_value_email(email):
            continue
        seen.add(email)
        valid.append(email)
    return sorted(valid, key=lambda email: _email_score(email, company_domain), reverse=True)


def _extract_emails_v2(text: str, html: str = "", hrefs: list[str] | None = None) -> list[str]:
    source = " ".join([text or "", html or "", _deobfuscate_email_text(text or "")])
    emails = EMAIL_PATTERN.findall(source)
    for href in hrefs or []:
        if href.lower().startswith("mailto:"):
            emails.append(href.split(":", 1)[1].split("?", 1)[0])
    return emails


def _is_same_site_url(url: str, company_domain: str) -> bool:
    domain = _extract_domain(url)
    return bool(domain and company_domain and (domain == company_domain or domain.endswith("." + company_domain)))


def _social_type(url: str) -> str:
    domain = _extract_domain(url)
    for social_domain, social_name in SOCIAL_DOMAINS.items():
        if social_domain in domain:
            return social_name
    return ""


def _looks_like_share_link(url: str) -> bool:
    lowered = url.lower()
    return any(
        token in lowered
        for token in (
            "/share", "sharer", "intent/tweet", "share?url=", "addthis",
            "pinterest.com/pin/create", "linkedin.com/share",
        )
    )


def _extract_contact_name(text: str, emails: list[str]) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    title_words = r"(sales|export|business development|manager|director|president|founder|owner|ceo|coo|vp|leader)"
    generic = {
        "sales team", "contact us", "customer service", "support team",
        "export department", "info", "admin", "office",
    }
    nav_words = {
        "contact", "about", "products", "services", "solutions", "share",
        "facebook", "linkedin", "instagram", "youtube", "twitter", "tiktok",
    }

    for line in lines:
        low = line.lower()
        if len(line) > 180:
            continue
        if re.search(title_words, low, re.I):
            matches = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}\b", line)
            for name in matches:
                name = re.sub(
                    r"^(Sales|Export|Business Development|Manager|Director|President|Founder|Owner|CEO|COO|VP|Leader)\s+",
                    "",
                    name,
                    flags=re.I,
                ).strip()
                lowered_name = name.lower()
                if lowered_name in generic or any(word in lowered_name for word in nav_words):
                    continue
                if len(name) <= 60:
                    return name
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


async def _scrape_all_async(
    companies: list[dict],
    timeout_s: int = 30,
    progress_callback=None,
) -> list[dict]:
    """Async internal: scrape all companies with Playwright."""
    from playwright.async_api import async_playwright

    timeout_ms = timeout_s * 1000

    async with async_playwright() as p:
        launch_kwargs = {"headless": True}
        chromium = _find_chromium()
        if chromium:
            launch_kwargs["executable_path"] = chromium
        if _needs_no_sandbox():
            launch_kwargs["args"] = ["--no-sandbox", "--disable-gpu"]

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
            if progress_callback:
                progress_callback(
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


def scrape_companies_sync(
    companies: list[dict],
    timeout_s: int = 30,
    progress_callback=None,
) -> list[dict]:
    """Synchronous entry point — runs its own event loop.

    Called via asyncio.to_thread() from the async pipeline.
    """
    return asyncio.run(_scrape_all_async(companies, timeout_s, progress_callback))


async def _collect_page_snapshot(page) -> dict:
    title = await page.title()
    body_text = await page.evaluate("() => document.body ? document.body.innerText : ''")
    html = await page.evaluate("() => document.documentElement ? document.documentElement.innerHTML : ''")
    footer_text = await page.evaluate("() => { const f = document.querySelector('footer'); return f ? f.innerText : ''; }")
    links = await page.evaluate(
        """() => Array.from(document.querySelectorAll('a[href]')).map(a => ({
            href: a.href,
            text: (a.textContent || '').trim()
        }))"""
    )
    hrefs = [link.get("href", "") for link in links if link.get("href")]
    return {
        "title": title or "",
        "text": body_text or "",
        "clean_text": _clean_text(body_text or ""),
        "html": html or "",
        "footer_text": footer_text or "",
        "links": links,
        "hrefs": hrefs,
    }


def _pick_v2_pages(home_url: str, links: list[dict], company_domain: str) -> list[tuple[str, str]]:
    picked: list[tuple[str, str]] = [("home", home_url)]
    seen = {home_url.rstrip("/")}
    candidates: list[tuple[int, str, str]] = []

    for link in links:
        href = link.get("href", "")
        text = link.get("text", "")
        if not href or not _is_same_site_url(href, company_domain):
            continue
        clean_href = href.split("#", 1)[0].rstrip("/")
        if clean_href in seen:
            continue
        parsed = urlparse(clean_href)
        haystack = f"{parsed.path} {text}".lower()
        for idx, (page_type, pattern) in enumerate(V2_PAGE_PRIORITIES[1:], start=1):
            if pattern.search(haystack):
                candidates.append((idx, page_type, clean_href))
                break

    for _, page_type, href in sorted(candidates, key=lambda item: item[0]):
        if href in seen:
            continue
        picked.append((page_type, href))
        seen.add(href)
        if len(picked) >= 5:
            break
    return picked


def _extract_social_links(links: list[dict]) -> dict[str, str]:
    socials: dict[str, str] = {}
    for link in links:
        href = link.get("href", "")
        if not href or _looks_like_share_link(href):
            continue
        social = _social_type(href)
        if not social or social in socials:
            continue
        if social == "linkedin" and "/company/" not in href.lower():
            continue
        socials[social] = href.split("?", 1)[0]
    return socials


async def _scrape_social_public_pages(page, social_links: dict[str, str], timeout_ms: int) -> dict:
    texts: list[str] = []
    emails: list[str] = []
    phones: list[str] = []
    for social in ("facebook", "instagram", "youtube"):
        url = social_links.get(social)
        if not url:
            continue
        try:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if resp and resp.status >= 400:
                continue
            snapshot = await _collect_page_snapshot(page)
            text = snapshot["text"]
            texts.append(text[:1500])
            emails.extend(_extract_emails_v2(text, snapshot["html"], snapshot["hrefs"]))
            phones.extend(_extract_phones(text))
            await asyncio.sleep(random.uniform(1, 2))
        except Exception as e:
            logger.info("Skipped social public page %s: %s", url, str(e)[:120])
            continue
    return {
        "text": "\n".join(texts),
        "emails": emails,
        "phones": phones,
    }


async def _scrape_single_company_v2(page, company: dict, timeout_ms: int) -> dict:
    url = company.get("website", "")
    if not url:
        company["_scrape_status"] = "failed"
        return company

    company_domain = company.get("_domain") or _extract_domain(url)
    all_text_parts: list[str] = []
    about_text = ""
    products_text = ""
    location = ""
    description = company.get("_snippet", "")
    emails: list[str] = []
    phones: list[str] = []
    social_links: dict[str, str] = {}
    pages_scraped = 0
    errors: list[str] = []

    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        if resp and resp.status >= 400:
            company["_scrape_status"] = "failed"
            company["_scrape_errors"] = [f"HTTP {resp.status}"]
            return company

        home = await _collect_page_snapshot(page)
        if home["title"]:
            company["company_name"] = home["title"]

        page_targets = _pick_v2_pages(url, home["links"], company_domain)
        social_links.update(_extract_social_links(home["links"]))

        for page_type, page_url in page_targets:
            try:
                if page_type != "home":
                    resp = await page.goto(page_url, wait_until="domcontentloaded", timeout=timeout_ms)
                    if resp and resp.status >= 400:
                        continue
                    snapshot = await _collect_page_snapshot(page)
                else:
                    snapshot = home

                pages_scraped += 1
                text = snapshot["text"]
                clean_text = snapshot["clean_text"]
                all_text_parts.append(clean_text[:3000])
                emails.extend(_extract_emails_v2(text, snapshot["html"], snapshot["hrefs"]))
                emails.extend(_extract_emails_v2(snapshot["footer_text"]))
                phones.extend(_extract_phones(text))
                social_links.update(_extract_social_links(snapshot["links"]))

                if page_type in ("about", "contact", "team") and not about_text:
                    about_text = clean_text[:3000]
                if page_type == "products" and not products_text:
                    products_text = clean_text[:2500]
                if not description:
                    description = clean_text[:300]
                if not location:
                    location_match = re.search(
                        r"[\w\s,.-]+(?:Street|St|Ave|Avenue|Blvd|Boulevard|Road|Rd|Drive|Dr|Suite|Ste|Floor|Fl)\s*[\w\s,.-]{5,80}",
                        text,
                        re.I,
                    )
                    if location_match:
                        location = location_match.group(0).strip()

                if page_type != "home":
                    await asyncio.sleep(random.uniform(1, 2))
            except Exception as e:
                errors.append(f"{page_type}: {str(e)[:120]}")
                continue

        ranked_emails = _rank_emails(emails, company_domain)
        if not ranked_emails or (ranked_emails and _email_score(ranked_emails[0], company_domain) < 20):
            social_data = await _scrape_social_public_pages(page, social_links, timeout_ms)
            emails.extend(social_data["emails"])
            phones.extend(social_data["phones"])
            all_text_parts.append(social_data["text"])
            ranked_emails = _rank_emails(emails, company_domain)

        combined_text = "\n".join(all_text_parts)
        ranked_phones = []
        seen_phone_digits: set[str] = set()
        for phone in phones:
            digits = re.sub(r"\D", "", phone)
            if len(digits) < 7 or digits in seen_phone_digits:
                continue
            seen_phone_digits.add(digits)
            ranked_phones.append(phone)
        contact_name = _extract_contact_name(combined_text, ranked_emails)

        company["email"] = ", ".join(ranked_emails[:3])[:200]
        company["phone"] = ", ".join(ranked_phones[:5])[:200]
        company["contact_name"] = contact_name
        company["_scrape_status"] = "full" if pages_scraped >= 3 else "partial"
        company["_description"] = description
        company["_about_text"] = about_text or (combined_text[:3000] if combined_text else "")
        company["_products_services"] = products_text
        company["_location"] = location
        company["_linkedin"] = social_links.get("linkedin", "")
        company["_social_links"] = social_links
        company["_homepage_text"] = all_text_parts[0][:3000] if all_text_parts else ""
        company["_v2_pages_scraped"] = pages_scraped
        company["_scrape_errors"] = errors
    except Exception as e:
        logger.warning("v2 failed to scrape %s: %s", url, str(e)[:200])
        company["_scrape_status"] = "failed"
        company["_scrape_errors"] = [str(e)[:200]]

    return company


async def _scrape_all_async_v2(
    companies: list[dict],
    timeout_s: int = 30,
    progress_callback=None,
) -> list[dict]:
    from playwright.async_api import async_playwright

    timeout_ms = timeout_s * 1000

    async with async_playwright() as p:
        launch_kwargs = {"headless": True}
        chromium = _find_chromium()
        if chromium:
            launch_kwargs["executable_path"] = chromium
        if _needs_no_sandbox():
            launch_kwargs["args"] = ["--no-sandbox", "--disable-gpu"]

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
            companies[i] = await _scrape_single_company_v2(page, company, timeout_ms)
            logger.info(
                "Scraped v2 %d/%d: %s -> %s",
                i + 1,
                len(companies),
                company.get("_domain", ""),
                companies[i].get("_scrape_status", "unknown"),
            )
            if progress_callback:
                progress_callback(
                    i + 1,
                    len(companies),
                    company.get("_domain", ""),
                    companies[i].get("_scrape_status", "unknown"),
                )
            await context.close()
            if i < len(companies) - 1:
                await asyncio.sleep(random.uniform(1, 3))

        await browser.close()

    return companies


def scrape_companies_sync_v2(
    companies: list[dict],
    timeout_s: int = 30,
    progress_callback=None,
) -> list[dict]:
    """Synchronous v2 scraper entry point. Keeps v1 available unchanged."""
    return asyncio.run(_scrape_all_async_v2(companies, timeout_s, progress_callback))


# ── Reusable pure-function helpers (used by profile_beta2) ──────────────────


def extract_emails_from_text(text: str) -> list[str]:
    """Extract valid email addresses from text, filtering low-value ones."""
    return _extract_emails(text)


def extract_phones_from_text(text: str) -> list[str]:
    """Extract phone numbers from text (deduplicated, min 7 digits)."""
    return _extract_phones(text)


def extract_social_links_from_html(html: str, base_url: str) -> dict[str, str]:
    """Extract social media links from HTML href attributes."""
    href_pattern = re.compile(r'href=["\']([^"\']+)["\']', re.I)
    hrefs = href_pattern.findall(html or "")
    links = [{"href": href, "text": ""} for href in hrefs]
    return _extract_social_links(links)
