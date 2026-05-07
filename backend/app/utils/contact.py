"""Utilities for keeping contact data safe for outreach."""

import re


def clean_contact_name(value: str) -> str:
    """Keep contact_name conservative: only explicit individual names survive."""
    if not value:
        return ""

    name = str(value).strip()
    if not name:
        return ""

    # Convert "Toru Yamazaki (President)" to "Toru Yamazaki"; title-only
    # values are still rejected by the keyword checks below.
    name = re.sub(r"\s*[（(][^（）()]*[）)]\s*$", "", name).strip()
    lowered = name.lower()
    invalid_text = [
        "info",
        "sales",
        "support",
        "contact",
        "team",
        "department",
        "dept",
        "office",
        "service",
        "customer",
        "marketing",
        "overseas",
        "general",
        "admin",
        "company",
        "manager",
        "director",
        "president",
        "ceo",
        "unknown",
        "not available",
        "not found",
        "n/a",
        "none",
        "信息不足",
        "无法",
        "建议",
        "联系",
        "部门",
        "团队",
        "销售",
        "采购",
        "负责人",
        "邮箱",
    ]
    if any(token in lowered for token in invalid_text):
        return ""

    if "@" in name or "http" in name.lower():
        return ""
    if re.search(r"[/\\|;；、]", name):
        return ""
    if re.search(r"\d", name):
        return ""
    if len(name) > 40:
        return ""
    if re.fullmatch(r"[A-Z]{3,}", name):
        return ""

    return name
