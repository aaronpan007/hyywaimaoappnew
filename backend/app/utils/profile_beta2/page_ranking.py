"""Page classification, scoring, and selection."""

from __future__ import annotations

import re

CATEGORIES = [
    "homepage", "about", "products", "services", "projects", "cases",
    "certificates", "downloads", "contact", "factory", "quality",
    "team", "news", "blog", "other",
]

# URL pattern → category (checked in order, first match wins)
_URL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("homepage", re.compile(r"^/?(?:index\.html?)?$", re.I)),
    ("contact", re.compile(r"(?:contact|contact-us|get-in-touch|inquiry|enquiry|support)", re.I)),
    ("about", re.compile(r"(?:about|about-us|company|who-we-are|profile|corporate)", re.I)),
    ("products", re.compile(r"(?:products?|product-category|product-detail|catalogue?)", re.I)),
    ("services", re.compile(r"(?:services?|solutions?)", re.I)),
    ("projects", re.compile(r"(?:projects?|portfolio|applications|gallery)", re.I)),
    ("cases", re.compile(r"(?:cases?|case-studies|success-stories?|references?|clients?)", re.I)),
    ("certificates", re.compile(r"(?:certificate|certification|iso|ce-mark|quality-assurance)", re.I)),
    ("downloads", re.compile(r"(?:download|brochure|resource|document|media-center)", re.I)),
    ("factory", re.compile(r"(?:factory|production|manufacturing|facility|workshop|plant)", re.I)),
    ("quality", re.compile(r"(?:quality|testing|inspection|laboratory|lab-)", re.I)),
    ("team", re.compile(r"(?:team|leadership|management|about-team|our-people)", re.I)),
    ("news", re.compile(r"(?:news|press|event|announcement|media)", re.I)),
    ("blog", re.compile(r"(?:blog|article|post|insight)", re.I)),
]

# Link text patterns (multilingual)
_LINK_TEXT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("about", re.compile(r"(?:about|关于我们|会社概要|회사소개|qui.+sommes)", re.I)),
    ("contact", re.compile(r"(?:contact|联系我们|お問い合わせ|문의|contac)", re.I)),
    ("products", re.compile(r"(?:products?|产品|製品|제품)", re.I)),
    ("services", re.compile(r"(?:services?|服务|서비스)", re.I)),
]

# Low-value URL patterns (apply penalty)
_LOW_VALUE_PATTERNS = [
    (re.compile(r"/tag[s/-]", re.I), -6),
    (re.compile(r"[\?&]page=\d", re.I), -5),
    (re.compile(r"(?:login|register|cart|checkout|privacy|terms|sitemap)", re.I), -10),
]


def classify_url(url: str, link_text: str = "") -> str:
    """Classify a URL into a category."""
    from urllib.parse import urlparse

    path = urlparse(url).path or ""

    # Check URL patterns first
    for cat, pattern in _URL_PATTERNS:
        if pattern.search(path):
            return cat

    # Check link text
    for cat, pattern in _LINK_TEXT_PATTERNS:
        if link_text and pattern.search(link_text):
            return cat

    return "other"


# Score rules by category
_CATEGORY_SCORES: dict[str, float] = {
    "products": 12,
    "cases": 12,
    "projects": 12,
    "certificates": 11,
    "services": 10,
    "downloads": 10,
    "about": 8,
    "factory": 8,
    "quality": 8,
    "contact": 6,
    "homepage": 5,
    "team": 3,
    "news": -2,
    "blog": -3,
    "other": 0,
}

# Diversity groups for selection
_DIVERSITY_GROUPS: dict[str, list[str]] = {
    "about": ["about", "team"],
    "products_services": ["products", "services"],
    "projects_cases": ["projects", "cases"],
    "certificates_downloads": ["certificates", "downloads"],
    "contact": ["contact"],
    "factory_quality": ["factory", "quality"],
}


def score_page(page_url: str, page_title: str, seen_urls: set[str], seen_titles: set[str]) -> float:
    """Score a discovered page for priority."""
    from app.utils.profile_beta2.page_discovery import DiscoveredPage

    # Create a temporary DiscoveredPage for classify_url
    cat = classify_url(page_url, "")
    score = _CATEGORY_SCORES.get(cat, 0)

    # URL-based penalties
    path = page_url
    for pattern, penalty in _LOW_VALUE_PATTERNS:
        if pattern.search(path):
            score += penalty

    # Duplicate penalties
    normalized = page_url.split("#")[0].rstrip("/")
    if normalized in seen_urls:
        score -= 8
    if page_title and page_title.lower().strip() in seen_titles:
        score -= 8

    return score


def select_pages(
    pages: list[dict],
    max_default: int = 8,
    hard_max: int = 12,
) -> list[dict]:
    """Select high-value pages ensuring diversity.

    Each page dict must have: url, title, category, score
    Returns selected list with same dicts.
    """
    if not pages:
        return []

    # Sort by score descending
    sorted_pages = sorted(pages, key=lambda p: p.get("score", 0), reverse=True)

    selected: list[dict] = []
    covered_groups: set[str] = set()
    covered_categories: set[str] = set()

    # First pass: ensure diversity — pick one from each group
    for page in sorted_pages:
        if len(selected) >= max_default:
            break
        cat = page.get("category", "other")
        for group_name, group_cats in _DIVERSITY_GROUPS.items():
            if group_name in covered_groups:
                continue
            if cat in group_cats:
                selected.append(page)
                covered_groups.add(group_name)
                covered_categories.add(cat)
                break

    # Second pass: fill remaining slots by score
    for page in sorted_pages:
        if len(selected) >= max_default:
            break
        cat = page.get("category", "other")
        if page in selected:
            continue
        selected.append(page)
        covered_categories.add(cat)

    # Third pass: if still under max, add more (up to hard_max)
    if len(selected) < hard_max:
        for page in sorted_pages:
            if len(selected) >= hard_max:
                break
            if page not in selected:
                selected.append(page)

    return selected
