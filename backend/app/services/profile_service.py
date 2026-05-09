from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_profile import CompanyProfile
from app.models.user_settings import UserSettings
from app.schemas.profile import CompanyProfileResponse
from app.services.settings_service import ensure_recommended_email_settings
from app.utils.db_sequences import sync_company_profiles_id_sequence


def _get(profile: dict, snake: str, camel: str | None = None, default: Any = "") -> Any:
    camel = camel or "".join(
        word.capitalize() if i > 0 else word
        for i, word in enumerate(snake.split("_"))
    )
    return profile.get(snake, profile.get(camel, default))


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return fallback


def _label_of(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return (
            value.get("name")
            or value.get("model")
            or value.get("competency")
            or value.get("customer_type")
            or value.get("type")
            or value.get("project")
            or ""
        )
    return _text(value)


def _join(value: Any) -> str:
    return "、".join(item for item in (_label_of(v) for v in _as_list(value)) if item)


def _profile_data_to_response(cp: CompanyProfile) -> CompanyProfileResponse:
    profile = cp.profile_data if isinstance(cp.profile_data, dict) else {}
    competencies = _get(profile, "core_competencies", "competencies", [])

    return CompanyProfileResponse(
        id=cp.id,
        company_name=cp.company_name or _get(profile, "company_name", "companyName", ""),
        one_line_intro=_get(profile, "one_line_intro", "oneLineIntro", ""),
        full_intro=_get(profile, "full_intro", "fullIntro", ""),
        location=_get(profile, "location", default=""),
        industry=_get(profile, "industry", default=""),
        website=_get(profile, "website", default=""),
        established=_get(profile, "established", default=""),
        scale=_get(profile, "scale", default=""),
        employees=_get(profile, "employees", default=""),
        certifications=_get(profile, "certifications", default=[]),
        cooperation_models=_get(profile, "cooperation_models", "cooperationModels", []),
        products=_get(profile, "products", default=[]),
        competencies=competencies,
        target_customer_types=_get(profile, "target_customer_types", "targetCustomerTypes", []),
        case_studies=_get(profile, "case_studies", "caseStudies", []),
        unique_selling_points=_get(profile, "unique_selling_points", "uniqueSellingPoints", []),
        customer_matching_guide=_get(profile, "customer_matching_guide", "customerMatchingGuide", []),
        boundaries=_get(profile, "boundaries", default={}) or {},
        metadata=_get(profile, "metadata", default={}) or {},
        profile_data=profile,
        profile_markdown=cp.profile_markdown,
        collected_at=str(cp.created_at),
        is_current=cp.is_current,
    )


async def get_current_profile(
    db: AsyncSession, user_id: int
) -> CompanyProfileResponse | None:
    result = await db.execute(
        select(CompanyProfile)
        .where(CompanyProfile.user_id == user_id, CompanyProfile.is_current == True)  # noqa: E712
        .order_by(CompanyProfile.updated_at.desc())
        .limit(1)
    )
    cp = result.scalar_one_or_none()
    if cp is None:
        return None
    return _profile_data_to_response(cp)


async def create_profile(
    db: AsyncSession, user_id: int, profile_data: dict
) -> CompanyProfileResponse:
    await db.execute(
        update(CompanyProfile)
        .where(CompanyProfile.user_id == user_id, CompanyProfile.is_current == True)  # noqa: E712
        .values(is_current=False)
    )

    company_name = _get(profile_data, "company_name", "companyName", "")
    await sync_company_profiles_id_sequence(db)
    cp = CompanyProfile(
        user_id=user_id,
        company_name=company_name,
        profile_data=profile_data,
        profile_markdown=profile_data.get("markdown", ""),
        is_current=True,
    )
    db.add(cp)
    await db.commit()
    await db.refresh(cp)
    await ensure_recommended_email_settings(db, user_id, cp.id, profile_data)
    return _profile_data_to_response(cp)


async def update_profile(
    db: AsyncSession, profile_id: int, profile_data: dict
) -> CompanyProfileResponse | None:
    result = await db.execute(
        select(CompanyProfile).where(CompanyProfile.id == profile_id)
    )
    cp = result.scalar_one_or_none()
    if cp is None:
        return None

    cp.company_name = _get(profile_data, "company_name", "companyName", "")
    cp.profile_data = profile_data
    cp.profile_markdown = profile_data.get("markdown", cp.profile_markdown)

    await db.commit()
    await db.refresh(cp)
    await ensure_recommended_email_settings(db, cp.user_id, cp.id, profile_data)
    return _profile_data_to_response(cp)


async def clear_current_profile(db: AsyncSession, user_id: int) -> bool:
    result = await db.execute(
        select(CompanyProfile.id)
        .where(CompanyProfile.user_id == user_id, CompanyProfile.is_current == True)  # noqa: E712
    )
    profile_ids = list(result.scalars().all())
    if not profile_ids:
        return False

    settings_result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    user_settings = settings_result.scalar_one_or_none()
    if user_settings is not None and user_settings.profile_id in profile_ids:
        was_only_recommended = user_settings.confirmed_at is None
        user_settings.profile_id = None
        if was_only_recommended:
            user_settings.sender_name = ""
            user_settings.from_email_prefix = ""
            user_settings.reply_to_email = ""

    await db.execute(
        delete(CompanyProfile)
        .where(CompanyProfile.user_id == user_id, CompanyProfile.id.in_(profile_ids))
    )
    await db.commit()
    return True


async def export_current_profile_docx(db: AsyncSession, user_id: int) -> tuple[bytes, str] | None:
    result = await db.execute(
        select(CompanyProfile)
        .where(CompanyProfile.user_id == user_id, CompanyProfile.is_current == True)  # noqa: E712
        .order_by(CompanyProfile.updated_at.desc())
        .limit(1)
    )
    cp = result.scalar_one_or_none()
    if cp is None:
        return None

    profile = cp.profile_data if isinstance(cp.profile_data, dict) else {}
    title = profile.get("company_name") or cp.company_name or "公司画像"
    meta = profile.get("metadata", {}) if isinstance(profile.get("metadata"), dict) else {}

    blocks: list[tuple[str, str]] = [
        ("title", f"{title} - 公司画像"),
        ("meta", f"更新时间：{meta.get('updated_at') or cp.updated_at}"),
        ("h1", "公司概况"),
        ("p", profile.get("one_line_intro") or ""),
        ("p", profile.get("full_intro") or ""),
    ]
    for label, value in [
        ("行业", profile.get("industry", "")),
        ("地区", profile.get("location", "")),
        ("官网", profile.get("website", "")),
        ("成立时间", profile.get("established", "")),
        ("规模", profile.get("scale") or profile.get("employees") or ""),
    ]:
        blocks.append(("bullet", f"{label}：{_text(value, '-')}"))

    blocks.append(("h1", "主营产品与服务"))
    for product in _as_list(profile.get("products")):
        if isinstance(product, dict):
            blocks.extend(
                [
                    ("h2", product.get("name", "未命名产品")),
                    ("p", product.get("description", "")),
                    ("bullet", f"适合客户：{product.get('target_customers', '')}"),
                    ("bullet", f"关键卖点：{_join(product.get('key_selling_points'))}"),
                ]
            )
        else:
            blocks.append(("bullet", _text(product)))

    blocks.append(("h1", "核心竞争力"))
    for item in _as_list(profile.get("core_competencies")):
        if isinstance(item, dict):
            blocks.append(("h2", item.get("competency", "核心能力")))
            blocks.append(("p", item.get("description", "")))
            if item.get("evidence"):
                blocks.append(("bullet", f"证据：{item.get('evidence')}"))
        else:
            blocks.append(("bullet", _text(item)))

    blocks.append(("h1", "适合开发的客户类型"))
    for item in _as_list(profile.get("target_customer_types")):
        if isinstance(item, dict):
            blocks.append(("h2", item.get("type", "客户类型")))
            blocks.append(("bullet", f"为什么适合：{item.get('why_suitable', '')}"))
            blocks.append(("bullet", f"开发信重点：{_join(item.get('pitch_focus'))}"))

    blocks.append(("h1", "成功案例"))
    cases = _as_list(profile.get("case_studies"))
    if not cases:
        blocks.append(("p", "暂无明确可用案例。"))
    for case in cases:
        if not isinstance(case, dict):
            blocks.append(("bullet", _text(case)))
            continue
        blocks.append(("h2", case.get("project", "未命名案例")))
        for label, key in [
            ("英文项目名", "project_en"),
            ("客户类型", "client_type"),
            ("行业", "industry"),
            ("国家/地区", "country"),
            ("使用产品", "products_used"),
            ("规模", "area_or_quantity"),
            ("解决问题", "problem_solved"),
            ("结果", "result"),
            ("一句话亮点", "key_highlight"),
        ]:
            value = _join(case.get(key)) if isinstance(case.get(key), list) else _text(case.get(key))
            blocks.append(("bullet", f"{label}：{value}"))

    blocks.append(("h1", "资质与合作模式"))
    blocks.append(("p", f"资质认证：{_join(profile.get('certifications')) or '-'}"))
    for item in _as_list(profile.get("cooperation_models")):
        if isinstance(item, dict):
            blocks.append(("bullet", f"{item.get('model', '')}：{item.get('description', '')}；客户价值：{item.get('customer_value', '')}"))
        else:
            blocks.append(("bullet", _text(item)))

    blocks.append(("h1", "独特卖点"))
    for item in _as_list(profile.get("unique_selling_points")):
        blocks.append(("bullet", _text(item) or _label_of(item)))

    blocks.append(("h1", "客户匹配建议"))
    for item in _as_list(profile.get("customer_matching_guide")):
        if isinstance(item, dict):
            blocks.append(("h2", item.get("customer_type", "客户类型")))
            blocks.append(("bullet", f"优先强调：{_join(item.get('priority_points'))}"))
            blocks.append(("bullet", f"避免话题：{_join(item.get('avoid_topics'))}"))

    boundaries = profile.get("boundaries", {}) if isinstance(profile.get("boundaries"), dict) else {}
    blocks.extend(
        [
            ("h1", "信息边界"),
            ("bullet", f"可以说：{_join(boundaries.get('claims_we_can_make'))}"),
            ("bullet", f"不能乱说：{_join(boundaries.get('claims_we_cannot_make'))}"),
            ("bullet", f"敏感话题：{_join(boundaries.get('sensitive_topics'))}"),
        ]
    )

    english = profile.get("english_profile")
    if isinstance(english, dict) and any(english.values()):
        blocks.extend(
            [
                ("h1", "English Version For Outreach"),
                ("p", english.get("one_line_intro", "")),
                ("p", english.get("full_intro", "")),
            ]
        )

    blocks.extend(
        [
            ("h1", "来源与备注"),
            ("p", f"来源页面：{_join(meta.get('source_urls')) or '-'}"),
            ("p", f"备注：{meta.get('notes', '')}"),
        ]
    )

    content = _build_simple_docx(blocks)
    filename = f"{title}_公司画像.docx".replace("/", "-").replace("\\", "-")
    return content, filename


def _paragraph_xml(kind: str, text: str) -> str:
    if not text:
        text = ""
    escaped = escape(str(text))
    style = {
        "title": '<w:pStyle w:val="Title"/><w:jc w:val="center"/>',
        "meta": '<w:jc w:val="center"/>',
        "h1": '<w:pStyle w:val="Heading1"/>',
        "h2": '<w:pStyle w:val="Heading2"/>',
        "bullet": "",
        "p": "",
    }.get(kind, "")
    prefix = "• " if kind == "bullet" else ""
    return (
        "<w:p>"
        f"<w:pPr>{style}</w:pPr>"
        "<w:r><w:rPr><w:rFonts w:eastAsia=\"Microsoft YaHei\" w:ascii=\"Arial\"/>"
        "<w:sz w:val=\"21\"/></w:rPr>"
        f"<w:t xml:space=\"preserve\">{escape(prefix)}{escaped}</w:t>"
        "</w:r></w:p>"
    )


def _build_simple_docx(blocks: list[tuple[str, str]]) -> bytes:
    document_body = "".join(_paragraph_xml(kind, text) for kind, text in blocks)
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {document_body}
    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>
  </w:body>
</w:document>"""
    styles_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:rPr><w:b/><w:sz w:val="28"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>
</w:styles>"""
    rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    document_rels_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""
    content_types_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""

    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types_xml)
        docx.writestr("_rels/.rels", rels_xml)
        docx.writestr("word/document.xml", document_xml)
        docx.writestr("word/styles.xml", styles_xml)
        docx.writestr("word/_rels/document.xml.rels", document_rels_xml)
    return buffer.getvalue()
