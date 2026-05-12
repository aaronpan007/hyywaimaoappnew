"""Lightweight page fetching with Playwright fallback."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PageContent:
    url: str
    title: str = ""
    html: str = ""
    status: int = 0
    fetch_method: str = "unknown"  # lightweight | playwright
    error: str = ""


async def fetch_page_lightweight(url: str, timeout: int = 12) -> PageContent:
    """Fetch a page using httpx only (lightweight, no browser)."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(connect=5.0, read=timeout, write=5.0, pool=5.0),
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
        ) as client:
            resp = await client.get(url)
            return PageContent(
                url=str(resp.url),
                html=resp.text or "",
                status=resp.status_code,
                fetch_method="lightweight",
            )
    except httpx.TimeoutException:
        return PageContent(url=url, status=0, fetch_method="lightweight", error="timeout")
    except Exception as exc:
        return PageContent(url=url, status=0, fetch_method="lightweight", error=str(exc)[:200])


def should_use_playwright(content: PageContent) -> bool:
    """Check if lightweight fetch produced usable content."""
    if content.error or content.status >= 400:
        return True
    html = content.html
    if not html or len(html) < 200:
        return True

    # Check for JS-rendered content markers
    lower = html.lower()
    js_markers = [
        "loading...", "please enable javascript", "javascript is required",
        "enable js", "require javascript", "enable javascript",
    ]
    if any(marker in lower for marker in js_markers):
        return True

    # Check body content quality
    from bs4 import BeautifulSoup
    try:
        soup = BeautifulSoup(html, "html.parser")
        body = soup.find("body")
        if body:
            body_text = body.get_text(strip=True)
            # Very short body → JS-rendered
            if len(body_text) < 200:
                return True
            # Body starts with "loading" (without dots) → SPA with gallery/image content
            if body_text[:50].lower().startswith("loading"):
                return True
            # Check for near-empty main content area
            # (large HTML but very little actual text = hidden behind JS)
            main = soup.find("main") or soup.find("article") or soup.find(id=re.compile(r"content|main", re.I))
            if main:
                main_text = main.get_text(strip=True)
                if len(main_text) < 200 and len(html) > 10000:
                    return True
    except Exception:
        pass

    return False


async def _fetch_playwright(url: str, timeout_s: int = 10) -> PageContent:
    """Fetch a page using Playwright (headless browser)."""
    from app.utils.scraper import _find_chromium, _needs_no_sandbox

    try:
        from playwright.async_api import async_playwright

        launch_kwargs = {"headless": True}
        chromium = _find_chromium()
        if chromium:
            launch_kwargs["executable_path"] = chromium
        if _needs_no_sandbox():
            launch_kwargs["args"] = ["--no-sandbox", "--disable-gpu"]

        async with async_playwright() as p:
            browser = await p.chromium.launch(**launch_kwargs)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)

            if resp and resp.status >= 400:
                await browser.close()
                return PageContent(url=url, status=resp.status, fetch_method="playwright", error=f"HTTP {resp.status}")

            html = await page.evaluate("() => document.documentElement ? document.documentElement.innerHTML : ''")
            title = await page.title()

            await browser.close()
            return PageContent(
                url=url,
                title=title or "",
                html=html or "",
                status=(resp.status if resp else 0),
                fetch_method="playwright",
            )
    except Exception as exc:
        return PageContent(url=url, status=0, fetch_method="playwright", error=str(exc)[:200])


async def _fetch_playwright_batch(urls: list[str], timeout_s: int = 10) -> list[PageContent]:
    """Fetch multiple URLs in a single browser instance (efficient batch mode)."""
    from app.utils.scraper import _find_chromium, _needs_no_sandbox

    results: list[PageContent] = []

    try:
        from playwright.async_api import async_playwright

        launch_kwargs = {"headless": True}
        chromium = _find_chromium()
        if chromium:
            launch_kwargs["executable_path"] = chromium
        if _needs_no_sandbox():
            launch_kwargs["args"] = ["--no-sandbox", "--disable-gpu"]

        async with async_playwright() as p:
            browser = await p.chromium.launch(**launch_kwargs)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )

            for url in urls:
                try:
                    page = await context.new_page()
                    resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_s * 1000)
                    status = resp.status if resp else 0
                    html = ""
                    title = ""
                    if resp and resp.status < 400:
                        # Wait briefly for JS-rendered content (galleries, lazy images)
                        await page.wait_for_timeout(2000)
                        html = await page.evaluate("() => document.documentElement ? document.documentElement.innerHTML : ''")
                        title = await page.title()
                    await page.close()
                    results.append(PageContent(
                        url=url, title=title or "", html=html or "",
                        status=status, fetch_method="playwright",
                    ))
                except Exception as exc:
                    results.append(PageContent(url=url, status=0, fetch_method="playwright", error=str(exc)[:200]))
                    try:
                        await page.close()
                    except Exception:
                        pass

            await context.close()
            await browser.close()
    except Exception as exc:
        # Browser launch failed — return empty results
        for url in urls:
            results.append(PageContent(url=url, status=0, fetch_method="playwright", error=f"Browser error: {str(exc)[:150]}"))

    return results


async def fetch_page_with_fallback(url: str) -> PageContent:
    """Fetch with lightweight first, Playwright fallback if needed."""
    # Step 1: lightweight
    content = await fetch_page_lightweight(url)

    # Step 2: check if Playwright is needed
    if should_use_playwright(content):
        logger.info("Lightweight fetch insufficient for %s, trying Playwright", url[:80])
        pw_content = await _fetch_playwright(url)
        if pw_content.html and not pw_content.error:
            return pw_content
        # If PW also fails, return lightweight result anyway
        if not content.html:
            return pw_content  # Return PW failure info

    return content


async def fetch_pages(pages: list[dict], semaphore_count: int = 3) -> list[PageContent]:
    """Fetch multiple pages with smart strategy.

    1. Probe first page with httpx to detect if site needs JS rendering
    2. If JS needed → batch Playwright (one browser, multiple tabs)
    3. If static → parallel httpx with per-page PW fallback
    """
    if not pages:
        return []

    urls = [p.get("url", "") for p in pages]

    # Phase 1: Probe — fetch first page to detect JS requirement
    probe_url = urls[0]
    probe_content = await fetch_page_lightweight(probe_url)
    site_needs_js = should_use_playwright(probe_content)

    if site_needs_js:
        logger.info("Site requires JS rendering, switching to batch Playwright for %d pages", len(urls))
        results = await _fetch_playwright_batch(urls)
        # Restore titles from page metadata
        for i, result in enumerate(results):
            if i < len(pages):
                result.title = result.title or pages[i].get("title", "")
        return results

    # Phase 2: Static site — use httpx with per-page PW fallback
    logger.info("Site is static, using httpx with per-page fallback")
    semaphore = asyncio.Semaphore(semaphore_count)

    async def _fetch_one(page_dict: dict) -> PageContent:
        async with semaphore:
            url = page_dict.get("url", "")
            if not url:
                return PageContent(url="", error="empty_url")
            try:
                content = await fetch_page_with_fallback(url)
                content.title = content.title or page_dict.get("title", "")
                return content
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s", url[:80], exc)
                return PageContent(url=url, error=str(exc)[:200])

    tasks = [_fetch_one(p) for p in pages]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    final: list[PageContent] = []
    for result in raw_results:
        if isinstance(result, Exception):
            final.append(PageContent(url="", error=str(result)[:200]))
        else:
            final.append(result)

    return final
