"""Evidence pack builder: structured data package for AI analysis."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class PageEvidence:
    url: str
    title: str = ""
    page_type: str = "other"
    fetch_method: str = "unknown"
    status: int = 0
    score: float = 0
    headings: list[str] = field(default_factory=list)
    clean_text: str = ""
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    social_links: dict[str, str] = field(default_factory=dict)
    pdf_links: list[str] = field(default_factory=list)
    source_quality: str = "good"  # good | partial | empty


@dataclass
class EvidencePack:
    input_url: str = ""
    resolved_domain: str = ""
    crawl_status: str = "success"  # success | partial_success | failed
    website_access_status: str = ""
    source_quality: str = "good"
    pages: list[PageEvidence] = field(default_factory=list)
    contacts: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_ai_prompt(self) -> str:
        """Convert evidence pack to structured text for AI analysis."""
        sections: list[str] = []

        sections.append(f"## 网站信息\n- 官网: {self.input_url}\n- 解析域名: {self.resolved_domain}\n- 访问状态: {self.website_access_status}\n- 采集状态: {self.crawl_status}")

        if self.contacts.get("ranked_emails"):
            sections.append(f"\n## 联系方式\n- 邮箱: {', '.join(self.contacts['ranked_emails'][:5])}")
        if self.contacts.get("phones"):
            sections.append(f"- 电话: {', '.join(self.contacts['phones'][:5])}")
        if self.contacts.get("addresses"):
            sections.append(f"- 地址: {', '.join(self.contacts['addresses'][:3])}")
        if self.contacts.get("social_links"):
            socials = [f"{k}: {v}" for k, v in self.contacts["social_links"].items()]
            sections.append(f"- 社交媒体: {'; '.join(socials)}")
        if self.contacts.get("whatsapp"):
            sections.append(f"- WhatsApp: {self.contacts['whatsapp']}")
        if self.contacts.get("wechat"):
            sections.append(f"- WeChat: {self.contacts['wechat']}")
        if self.contacts.get("inquiry_form_url"):
            sections.append(f"- 询盘表单: {self.contacts['inquiry_form_url']}")
        if self.contacts.get("pdf_links"):
            sections.append(f"- PDF文件: {', '.join(self.contacts['pdf_links'][:5])}")
        if self.contacts.get("catalog_links"):
            sections.append(f"- 产品目录: {', '.join(self.contacts['catalog_links'][:5])}")

        if self.pages:
            sections.append("\n## 网页内容")
            # Collect all image alt texts for a dedicated gallery section
            gallery_items: list[str] = []
            for i, page in enumerate(self.pages, 1):
                sections.append(f"\n### Page {i}: {page.title or page.url}")
                sections.append(f"- URL: {page.url}")
                sections.append(f"- 类型: {page.page_type}")
                sections.append(f"- 抓取方式: {page.fetch_method}")
                if page.headings:
                    sections.append(f"- 标题层级: {'; '.join(page.headings[:5])}")
                if page.emails:
                    sections.append(f"- 页面邮箱: {', '.join(page.emails)}")
                if page.phones:
                    sections.append(f"- 页面电话: {', '.join(page.phones)}")
                if page.clean_text:
                    # Extract image alt section if present
                    alt_marker = "\n## 项目/案例图片信息\n"
                    alt_idx = page.clean_text.find(alt_marker)
                    if alt_idx >= 0:
                        # Add main text (before alt section) with higher limit
                        main_text = page.clean_text[:alt_idx]
                        sections.append(f"\n内容:\n{main_text[:5000]}")
                        # Collect alt texts separately
                        alt_section = page.clean_text[alt_idx + len(alt_marker):]
                        for line in alt_section.split("\n"):
                            line = line.strip().lstrip("- ")
                            if line and not line.startswith("项目/案例"):
                                gallery_items.append(f"[{page.page_type}] {line}")
                    else:
                        sections.append(f"\n内容:\n{page.clean_text[:5000]}")

            # Add dedicated gallery section (highly visible for AI)
            if gallery_items:
                sections.append("\n## 项目画廊 / 案例图片汇总")
                sections.append("以下是从网站项目/案例页面图片的 alt 文本中提取的项目信息，")
                sections.append("请尽量从中提取 case_studies，每条图片可能对应一个案例：")
                for item in gallery_items:
                    sections.append(f"- {item}")

        if self.warnings:
            sections.append(f"\n## 采集警告\n" + "\n".join(f"- {w}" for w in self.warnings))

        return "\n".join(sections)


def build_evidence_pack(
    input_url: str,
    resolved_domain: str,
    website_access_status: str,
    pages: list,  # list of objects with url, title, clean_text, html, fetch_method, etc.
    contacts,  # Contacts dataclass
    warnings: list[str],
) -> EvidencePack:
    """Build an evidence pack from pipeline results."""
    evidence_pages: list[PageEvidence] = []

    for page in pages:
        clean_text = getattr(page, "clean_text", "") or ""
        html = getattr(page, "html", "") or ""

        # Determine source quality
        if not clean_text or len(clean_text) < 100:
            quality = "empty"
        elif len(clean_text) < 500:
            quality = "partial"
        else:
            quality = "good"

        # Extract page-specific emails/phones
        page_emails: list[str] = []
        page_phones: list[str] = []
        if clean_text:
            import re
            page_emails = list(set(re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", clean_text)))
            page_phones = re.findall(r"(?:\+?\d{1,3}[\s\-.]?)?\(?\d{2,4}\)?[\s\-.]?\d{3,4}[\s\-.]?\d{3,4}", clean_text)[:5]

        evidence_pages.append(PageEvidence(
            url=getattr(page, "url", ""),
            title=getattr(page, "title", ""),
            page_type=getattr(page, "category", "other"),
            fetch_method=getattr(page, "fetch_method", "unknown"),
            status=getattr(page, "status", 0),
            score=getattr(page, "score", 0),
            headings=getattr(page, "headings", []),
            clean_text=clean_text,
            emails=page_emails,
            phones=page_phones,
            source_quality=quality,
        ))

    # Determine overall crawl status
    if not evidence_pages:
        crawl_status = "failed"
    elif all(p.source_quality == "empty" for p in evidence_pages):
        crawl_status = "failed"
    elif any(p.source_quality in ("good", "partial") for p in evidence_pages):
        good_count = sum(1 for p in evidence_pages if p.source_quality == "good")
        crawl_status = "success" if good_count >= 3 else "partial_success"
    else:
        crawl_status = "partial_success"

    # Source quality overall
    good_ratio = sum(1 for p in evidence_pages if p.source_quality == "good") / max(len(evidence_pages), 1)
    source_quality = "good" if good_ratio >= 0.5 else ("partial" if good_ratio > 0 else "poor")

    # Convert contacts to dict for serialization
    contacts_dict = {}
    if hasattr(contacts, "__dict__"):
        contacts_dict = {
            "emails": contacts.emails[:10],
            "ranked_emails": contacts.ranked_emails[:10],
            "phones": contacts.phones[:5],
            "social_links": contacts.social_links,
            "addresses": contacts.addresses[:3],
            "whatsapp": contacts.whatsapp,
            "wechat": contacts.wechat,
            "skype": contacts.skype,
            "inquiry_form_url": contacts.inquiry_form_url,
            "pdf_links": contacts.pdf_links[:10],
            "catalog_links": contacts.catalog_links[:10],
        }

    return EvidencePack(
        input_url=input_url,
        resolved_domain=resolved_domain,
        crawl_status=crawl_status,
        website_access_status=website_access_status,
        source_quality=source_quality,
        pages=evidence_pages,
        contacts=contacts_dict,
        warnings=warnings,
    )
