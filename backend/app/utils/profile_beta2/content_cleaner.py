"""HTML content cleaner: remove noise, extract meaningful text."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Comment

logger = logging.getLogger(__name__)

# Tags to remove entirely
REMOVE_TAGS = {"nav", "footer", "script", "style", "noscript", "iframe", "svg"}

# CSS classes indicating noise (partial match)
REMOVE_CLASSES = [
    "cookie", "popup", "banner", "language", "newsletter",
    "modal", "overlay", "sidebar", "advertisement", "ads-",
    "social", "share", "chat-widget", "live-chat", "popup-",
    "gdpr", "consent", "floating", "sticky",
]

# CSS IDs indicating noise (partial match)
REMOVE_IDS = [
    "cookie", "popup", "modal", "newsletter", "sidebar",
    "advertisement", "social", "share", "chat", "gdpr",
]


@dataclass
class CleanedContent:
    title: str = ""
    headings: list[str] = field(default_factory=list)
    clean_text: str = ""
    meta_description: str = ""
    image_alt_texts: list[str] = field(default_factory=list)


def _has_noise_class(element) -> bool:
    """Check if an element has noise-related classes or IDs."""
    if element.attrs is None:
        return False
    class_str = element.get("class", [])
    if isinstance(class_str, str):
        class_str = class_str.split()
    for cls in class_str:
        cls_lower = cls.lower()
        for noise in REMOVE_CLASSES:
            if noise in cls_lower:
                return True

    elem_id = element.get("id", "")
    if elem_id:
        id_lower = elem_id.lower()
        for noise in REMOVE_IDS:
            if noise in id_lower:
                return True
    return False


def clean_content(html: str, base_url: str = "") -> CleanedContent:
    """Clean HTML and extract structured content."""
    if not html:
        return CleanedContent()

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return CleanedContent()

    # Extract title
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)

    # Extract meta description
    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_desc = meta_tag["content"].strip()

    # Remove unwanted tags
    for tag_name in REMOVE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    # Remove comments
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()

    # Remove elements with noise classes/IDs
    for element in soup.find_all(True):
        if _has_noise_class(element):
            element.decompose()

    # Extract headings (h1-h6)
    headings: list[str] = []
    for heading_tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        text = heading_tag.get_text(strip=True)
        if text and len(text) < 200:
            headings.append(text)

    # Extract image alt texts (valuable for gallery/portfolio/case study pages)
    image_alt_texts: list[str] = []
    for img in soup.find_all("img"):
        alt = img.get("alt", "").strip()
        if alt and len(alt) > 15:
            image_alt_texts.append(alt)

    # Extract clean text from body
    body = soup.find("body")
    if body:
        text = body.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)

    # Clean up whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)

    # Remove very long repeated lines (likely menus or repetitive content)
    if clean_text:
        line_counts: dict[str, int] = {}
        for line in clean_text.splitlines():
            line_counts[line] = line_counts.get(line, 0) + 1
        # Keep lines that appear <= 3 times
        filtered = [
            line for line in clean_text.splitlines()
            if line_counts.get(line, 0) <= 3
        ]
        clean_text = "\n".join(filtered)

    # Append image alt texts as structured content (crucial for gallery/portfolio pages)
    if image_alt_texts:
        alt_section = "\n## 项目/案例图片信息\n" + "\n".join(f"- {alt}" for alt in image_alt_texts)
        clean_text = clean_text + "\n" + alt_section

    return CleanedContent(
        title=title,
        headings=headings[:30],
        clean_text=clean_text[:15000],
        meta_description=meta_desc,
        image_alt_texts=image_alt_texts[:50],
    )
