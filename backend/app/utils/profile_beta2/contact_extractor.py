"""Extended contact extraction: emails, phones, social, addresses, forms, PDFs."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.utils.scraper import (
    EMAIL_PATTERN,
    PHONE_PATTERN,
    LINKEDIN_PATTERN,
    BLOCKED_EMAILS,
    LOW_VALUE_EMAIL_PREFIXES,
    SOCIAL_DOMAINS,
    _looks_like_share_link,
    _normalize_email,
    _is_low_value_email,
    _email_score,
)

logger = logging.getLogger(__name__)


@dataclass
class Contacts:
    emails: list[str] = field(default_factory=list)
    ranked_emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    social_links: dict[str, str] = field(default_factory=dict)
    addresses: list[str] = field(default_factory=list)
    whatsapp: str = ""
    wechat: str = ""
    skype: str = ""
    inquiry_form_url: str = ""
    pdf_links: list[str] = field(default_factory=list)
    catalog_links: list[str] = field(default_factory=list)


# Address patterns
_ADDRESS_PATTERNS = [
    re.compile(
        r"[\w\s,.-]+(?:Street|St|Ave|Avenue|Blvd|Boulevard|Road|Rd|Drive|Dr|Suite|Ste|Floor|Fl|Lane|Ln|Way|Court|Ct|Place|Pl)\s*[\w\s,.-]{5,80}",
        re.I,
    ),
    re.compile(
        r"\d{1,5}\s+[\w\s,.-]{10,60}(?:China|USA|UK|Germany|Japan|India|Brazil|Australia|Canada|France|Italy|Spain|Korea|Vietnam|Thailand|Indonesia|Malaysia|Turkey|Mexico|Russia|South Africa|Philippines|UAE|Saudi Arabia)",
        re.I,
    ),
    re.compile(
        r"(?:No\.?|Building|Floor|Room|#)\s*[\d\w]+[\w\s,.\-]{5,60}",
        re.I,
    ),
]

# Instant messaging patterns
_WHATSAPP_PATTERN = re.compile(r"(?:whatsapp|wa\.?me|wa\.?\s*/\s*)\s*:?\s*(?:\+?\s*(\d[\d\s\-.]{6,20})|([\d\s\-.]{8,20}))", re.I)
_WECHAT_PATTERN = re.compile(r"(?:wechat|we\.?chat|微信)\s*[:：]?\s*([\w\-]+)", re.I)
_SKYPE_PATTERN = re.compile(r"(?:skype)\s*[:：]?\s*([\w.,@\-]+)", re.I)


def _extract_addresses(text: str) -> list[str]:
    """Extract physical addresses from text."""
    addresses: list[str] = []
    for pattern in _ADDRESS_PATTERNS:
        for match in pattern.finditer(text):
            addr = match.group(0).strip()
            if len(addr) > 15 and addr not in addresses:
                addresses.append(addr)
    return addresses[:3]


def _extract_messaging(text: str, html: str) -> tuple[str, str, str]:
    """Extract WhatsApp, WeChat, Skype IDs."""
    combined = f"{text}\n{html}"
    whatsapp = ""
    wechat = ""
    skype = ""

    wa_match = _WHATSAPP_PATTERN.search(combined)
    if wa_match:
        whatsapp = wa_match.group(1) or wa_match.group(2) or ""

    wc_match = _WECHAT_PATTERN.search(combined)
    if wc_match:
        wechat = wc_match.group(1).strip()

    sk_match = _SKYPE_PATTERN.search(combined)
    if sk_match:
        skype = sk_match.group(1).strip()

    return whatsapp, wechat, skype


def _extract_inquiry_form(html: str, base_url: str) -> str:
    """Find inquiry/contact form URL from HTML."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        for form in soup.find_all("form"):
            action = form.get("action", "")
            if not action:
                continue
            action_lower = action.lower()
            if any(kw in action_lower for kw in ("inquiry", "contact", "enquiry", "quote", "request")):
                return urljoin(base_url, action)
            # Check form fields for inquiry-related inputs
            for inp in form.find_all(["input", "textarea"]):
                name = (inp.get("name") or "").lower()
                if any(kw in name for kw in ("inquiry", "message", "question", "ask")):
                    return urljoin(base_url, action)
    except Exception:
        pass
    return ""


def _extract_pdf_and_catalog_links(html: str, base_url: str) -> tuple[list[str], list[str]]:
    """Extract PDF and catalog/brochure download links."""
    pdf_links: list[str] = []
    catalog_links: list[str] = []

    try:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True).lower()
            full_url = urljoin(base_url, href)

            if href.lower().endswith(".pdf"):
                pdf_links.append(full_url)
            elif any(kw in text for kw in ("catalog", "brochure", "download", "leaflet", "flyer")):
                catalog_links.append(full_url)
    except Exception:
        pass

    return pdf_links[:20], catalog_links[:20]


def _extract_social_from_html(html: str, base_url: str) -> dict[str, str]:
    """Extract social media links from HTML."""
    socials: dict[str, str] = {}
    try:
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if _looks_like_share_link(href):
                continue
            domain = _extract_domain_from_url(href)
            for social_domain, social_name in SOCIAL_DOMAINS.items():
                if social_domain in domain:
                    if social_name not in socials:
                        if social_name == "linkedin" and "/company/" not in href.lower():
                            continue
                        socials[social_name] = href.split("?", 1)[0]
                    break
    except Exception:
        pass
    return socials


def _extract_domain_from_url(url: str) -> str:
    import re as _re
    match = _re.search(r"https?://([^/]+)", url)
    return (match.group(1) or "").lower() if match else ""


def rank_emails(emails: list[str], company_domain: str) -> list[str]:
    """Rank emails by quality, return deduplicated list."""
    seen: set[str] = set()
    valid: list[str] = []
    for raw in emails:
        email = _normalize_email(raw)
        if not email or email in seen or _is_low_value_email(email):
            continue
        seen.add(email)
        valid.append(email)
    return sorted(valid, key=lambda e: _email_score(e, company_domain), reverse=True)


def extract_contacts(
    pages: list,  # list of objects with .url, .title, .clean_text, .html, .base_url
    company_domain: str,
) -> Contacts:
    """Extract all contact information from fetched pages."""
    all_emails: list[str] = []
    all_phones: list[str] = []
    all_text = ""
    all_html = ""
    all_socials: dict[str, str] = {}
    all_addresses: list[str] = []
    all_pdf_links: list[str] = []
    all_catalog_links: list[str] = []
    inquiry_form_url = ""

    for page in pages:
        text = getattr(page, "clean_text", "") or ""
        html = getattr(page, "html", "") or ""
        url = getattr(page, "url", "") or ""
        base_url = getattr(page, "base_url", url) or url

        all_text += text + "\n"
        # Only include first portion of HTML for social/form extraction (avoid bloat)
        all_html += (html or "")[:5000] + "\n"

        # Extract emails from text and html
        emails = list(set(EMAIL_PATTERN.findall(text + " " + html)))
        for e in emails:
            e_lower = e.lower()
            if any(b in e_lower for b in BLOCKED_EMAILS):
                continue
            if e_lower.endswith((".png", ".jpg")):
                continue
            all_emails.append(e)

        # Extract phones
        phones = PHONE_PATTERN.findall(text)
        seen_digits: set[str] = set()
        for phone in phones:
            digits = re.sub(r"\D", "", phone)
            if len(digits) < 7 or digits in seen_digits:
                continue
            seen_digits.add(digits)
            all_phones.append(phone.strip())

        # Addresses
        addrs = _extract_addresses(text)
        all_addresses.extend(addrs)

        # Social links
        page_socials = _extract_social_from_html(html, base_url)
        all_socials.update(page_socials)

        # PDF and catalog links
        pdfs, catalogs = _extract_pdf_and_catalog_links(html, base_url)
        all_pdf_links.extend(pdfs)
        all_catalog_links.extend(catalogs)

        # Inquiry form
        if not inquiry_form_url:
            inquiry_form_url = _extract_inquiry_form(html, base_url)

    # Messaging
    whatsapp, wechat, skype = _extract_messaging(all_text, all_html)

    # Rank emails
    ranked = rank_emails(all_emails, company_domain)

    # Deduplicate phones
    seen_phones: set[str] = set()
    unique_phones: list[str] = []
    for phone in all_phones[:10]:
        if phone not in seen_phones:
            seen_phones.add(phone)
            unique_phones.append(phone)

    # Deduplicate PDF/catalog
    unique_pdfs = list(dict.fromkeys(all_pdf_links))[:20]
    unique_catalogs = list(dict.fromkeys(all_catalog_links))[:20]

    return Contacts(
        emails=list(dict.fromkeys(all_emails))[:20],
        ranked_emails=ranked[:10],
        phones=unique_phones,
        social_links=all_socials,
        addresses=all_addresses[:5],
        whatsapp=whatsapp,
        wechat=wechat,
        skype=skype,
        inquiry_form_url=inquiry_form_url,
        pdf_links=unique_pdfs,
        catalog_links=unique_catalogs,
    )
