"""Rule-based completeness scoring for company profiles."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CompletenessResult:
    score: int = 0  # 0-100
    breakdown: dict[str, int] = field(default_factory=dict)
    missing_items: list[str] = field(default_factory=list)


RULES: dict[str, int] = {
    "company_name": 10,
    "industry": 10,
    "main_products": 15,
    "main_services": 10,
    "target_customers": 10,
    "core_advantages": 15,
    "case_studies": 10,
    "certifications": 10,
    "contacts": 5,
    "downloads": 5,
}

_TOTAL = sum(RULES.values())  # 100


def _has_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return len(value.strip()) > 0
    if isinstance(value, (list, tuple)):
        return len(value) > 0
    if isinstance(value, dict):
        return len(value) > 0
    return True


def _check_item(profile: dict, key: str, check_fn) -> bool:
    """Check a profile item using a custom check function."""
    value = profile.get(key)
    return check_fn(value)


def calculate_completeness(profile: dict) -> CompletenessResult:
    """Calculate rule-based completeness score (0-100).

    This is purely rule-based — AI does NOT participate in scoring.
    AI can provide suggestions for missing items (missing_suggestions).
    """
    breakdown: dict[str, int] = {}
    missing_items: list[str] = []

    # company_name
    name = profile.get("company_name", "")
    if name and len(name.strip()) >= 2:
        breakdown["company_name"] = RULES["company_name"]
    else:
        breakdown["company_name"] = 0
        missing_items.append("company_name")

    # industry
    industry = profile.get("industry", "")
    if industry and len(industry.strip()) >= 2:
        breakdown["industry"] = RULES["industry"]
    else:
        breakdown["industry"] = 0
        missing_items.append("industry")

    # main_products (check products list)
    products = profile.get("products", [])
    if isinstance(products, list) and len(products) > 0:
        breakdown["main_products"] = RULES["main_products"]
    else:
        breakdown["main_products"] = 0
        missing_items.append("main_products")

    # main_services (check services field or cooperation_models)
    services = profile.get("services", profile.get("cooperation_models", []))
    if isinstance(services, list) and len(services) > 0:
        breakdown["main_services"] = RULES["main_services"]
    else:
        breakdown["main_services"] = 0
        missing_items.append("main_services")

    # target_customers (check target_customer_types)
    target = profile.get("target_customer_types", [])
    if isinstance(target, list) and len(target) > 0:
        breakdown["target_customers"] = RULES["target_customers"]
    else:
        breakdown["target_customers"] = 0
        missing_items.append("target_customers")

    # core_advantages (check core_competencies or unique_selling_points)
    advantages = profile.get("core_competencies", [])
    usp = profile.get("unique_selling_points", [])
    if (isinstance(advantages, list) and len(advantages) > 0) or (isinstance(usp, list) and len(usp) > 0):
        breakdown["core_advantages"] = RULES["core_advantages"]
    else:
        breakdown["core_advantages"] = 0
        missing_items.append("core_advantages")

    # case_studies
    cases = profile.get("case_studies", [])
    if isinstance(cases, list) and len(cases) > 0:
        # Partial score based on case quality
        score = RULES["case_studies"]
        good_cases = [c for c in cases if isinstance(c, dict) and c.get("project")]
        if len(good_cases) < 3:
            score = max(3, int(score * len(good_cases) / 3))
        breakdown["case_studies"] = score
        if score < RULES["case_studies"]:
            missing_items.append("case_studies (需要更多案例)")
    else:
        breakdown["case_studies"] = 0
        missing_items.append("case_studies")

    # certifications
    certs = profile.get("certifications", [])
    if isinstance(certs, list) and len(certs) > 0:
        breakdown["certifications"] = RULES["certifications"]
    else:
        breakdown["certifications"] = 0
        missing_items.append("certifications")

    # contacts (check english_profile or profile-level contact info)
    contacts_found = (
        profile.get("contact_email")
        or profile.get("contact_phone")
        or profile.get("location")
        or (profile.get("english_profile") or {}).get("contact_email")
    )
    if contacts_found:
        breakdown["contacts"] = RULES["contacts"]
    else:
        breakdown["contacts"] = 0
        missing_items.append("contacts")

    # downloads (check metadata for source_documents)
    metadata = profile.get("metadata", {})
    source_docs = metadata.get("source_documents", []) if isinstance(metadata, dict) else []
    if isinstance(source_docs, list) and len(source_docs) > 0:
        breakdown["downloads"] = RULES["downloads"]
    else:
        breakdown["downloads"] = 0
        missing_items.append("downloads")

    total_score = sum(breakdown.values())

    return CompletenessResult(
        score=min(total_score, _TOTAL),
        breakdown=breakdown,
        missing_items=missing_items,
    )
