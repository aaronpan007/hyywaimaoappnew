"""Multi-source page discovery: homepage links + Serper + sitemap."""

from __future__ import annotations

import logging
import re
import warnings
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredPage:
    url: str
    title: str = ""
    link_text: str = ""
    source: str = "unknown"  # homepage | serper | sitemap | robots


def _normalize_url(url: str) -> str:
    url = url.strip().split("#")[0].rstrip("/")
    if not urlparse(url).scheme:
        url = f"https://{url}"
    return url


def _is_same_domain(url: str, domain: str) -> bool:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    d = domain.lower()
    if d.startswith("www."):
        d = d[4:]
    return hostname == d or hostname.endswith("." + d)


def _extract_homepage_links(base_url: str, html: str, domain: str) -> list[DiscoveredPage]:
    """Extract internal links from the homepage HTML."""
    pages: list[DiscoveredPage] = []
    try:
        soup = BeautifulSoup(html, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            text = (a_tag.get_text() or "").strip()[:100]
            full_url = urljoin(base_url, href)
            normalized = _normalize_url(full_url)
            if not _is_same_domain(normalized, domain):
                continue
            if normalized == _normalize_url(base_url):
                continue
            if any(ext in normalized.lower() for ext in (".jpg", ".png", ".gif", ".pdf", ".zip")):
                continue
            pages.append(DiscoveredPage(url=normalized, link_text=text, source="homepage"))
    except Exception as exc:
        logger.debug("Failed to extract homepage links: %s", exc)
    return pages


async def _fetch_sitemap_pages(base_url: str, domain: str) -> list[DiscoveredPage]:
    """Try sitemap.xml for page URLs."""
    pages: list[DiscoveredPage] = []
    sitemap_url = f"{base_url.rstrip('/')}/sitemap.xml"
    try:
        async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
            resp = await client.get(
                sitemap_url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; Bot/1.0)"},
            )
            if resp.status_code != 200:
                return pages
            soup = BeautifulSoup(resp.text, "html.parser")
            for loc in soup.find_all("loc"):
                text = loc.get_text(strip=True)
                normalized = _normalize_url(text)
                if _is_same_domain(normalized, domain):
                    pages.append(DiscoveredPage(url=normalized, source="sitemap"))
    except Exception as exc:
        logger.debug("Sitemap fetch failed: %s", exc)
    return pages[:50]


async def _serper_site_search(
    domain: str, serper_api_key: str, queries: list[str]
) -> list[DiscoveredPage]:
    """Run Serper site: queries. Returns discovered pages."""
    pages: list[DiscoveredPage] = []
    if not serper_api_key:
        return pages

    async with httpx.AsyncClient(timeout=15) as client:
        for query in queries:
            try:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    headers={
                        "X-API-KEY": serper_api_key,
                        "Content-Type": "application/json",
                    },
                    json={"q": f"site:{domain} {query}", "num": 5},
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for organic in data.get("organic", []):
                    url = _normalize_url(organic.get("link", ""))
                    title = organic.get("title", "")
                    if _is_same_domain(url, domain):
                        pages.append(
                            DiscoveredPage(url=url, title=title, source="serper")
                        )
            except Exception as exc:
                logger.debug("Serper query '%s' failed: %s", query, exc)
    return pages


_BASE_SERPER_QUERIES = [
    "about OR company",
    "products OR services",
    "projects OR cases OR portfolio",
    "contact",
    "certificate OR certification OR download OR brochure",
]

_SUPPLEMENT_QUERIES = {
    "about": "about us OR company profile OR who we are",
    "products": "products catalog OR product list",
    "services": "services OR solutions",
    "projects": "projects OR case studies OR portfolio",
    "cases": "case studies OR success stories OR references",
    "certificates": "certificate OR ISO OR CE certification",
    "downloads": "download OR brochure OR catalog",
    "contact": "contact us OR inquiry OR get in touch",
    "factory": "factory OR production OR manufacturing facility",
    "quality": "quality control OR quality assurance",
}


async def discover_pages(
    base_url: str,
    domain: str,
    html: str,
    serper_api_key: str = "",
) -> list[DiscoveredPage]:
    """Three-phase page discovery."""
    # Phase 1: Homepage links + sitemap + base Serper
    homepage_pages = _extract_homepage_links(base_url, html, domain)
    logger.info("Phase 1: %d homepage links found", len(homepage_pages))

    sitemap_pages = await _fetch_sitemap_pages(base_url, domain)
    logger.info("Phase 1: %d sitemap pages found", len(sitemap_pages))

    serper_pages = await _serper_site_search(domain, serper_api_key, _BASE_SERPER_QUERIES)
    logger.info("Phase 1: %d Serper pages found", len(serper_pages))

    # Phase 2: Dedup and check missing high-value types
    from app.utils.profile_beta2.page_ranking import classify_url

    all_pages = homepage_pages + sitemap_pages + serper_pages

    # Dedup by normalized URL
    seen_urls: set[str] = set()
    deduped: list[DiscoveredPage] = []
    for page in all_pages:
        norm = _normalize_url(page.url)
        if norm in seen_urls:
            continue
        seen_urls.add(norm)
        deduped.append(page)

    # Check which high-value categories are missing
    found_categories: set[str] = set()
    for page in deduped:
        cat = classify_url(page.url, page.link_text)
        found_categories.add(cat)

    high_value = ["about", "products", "services", "projects", "cases", "certificates", "downloads", "contact", "factory", "quality"]
    missing = [cat for cat in high_value if cat not in found_categories]

    # Phase 2: supplement queries for missing categories (max 6)
    if missing and serper_api_key:
        supplement_queries = [_SUPPLEMENT_QUERIES[cat] for cat in missing[:6] if cat in _SUPPLEMENT_QUERIES]
        if supplement_queries:
            supplement_pages = await _serper_site_search(domain, serper_api_key, supplement_queries)
            logger.info("Phase 2: %d supplement pages found", len(supplement_pages))
            for page in supplement_pages:
                norm = _normalize_url(page.url)
                if norm not in seen_urls:
                    seen_urls.add(norm)
                    deduped.append(page)

    return deduped
