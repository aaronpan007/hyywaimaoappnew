"""Email-craft pipeline: generate personalized cold emails for each lead.

Ported from waimao_toolkit_new/skills/email-craft/scripts/generate_emails.py.
Runs as an asyncio.Task independent of SSE connections.
"""

import asyncio
import json
import logging
import re
import time
from datetime import datetime

import replicate

from app.config import settings
from app.database import async_session_factory
from app.models.company_profile import CompanyProfile
from app.models.lead import Lead
from app.models.outreach_email import OutreachEmail
from app.models.task import Task, TaskLog
from app.services import task_manager

logger = logging.getLogger(__name__)

# Ensure replicate library can find the token
import os
if settings.replicate_api_token and not os.environ.get("REPLICATE_API_TOKEN"):
    os.environ["REPLICATE_API_TOKEN"] = settings.replicate_api_token


# ---------------------------------------------------------------------------
# System prompt — ported verbatim from toolkit
# ---------------------------------------------------------------------------

_BASE_SYSTEM_PROMPT = """你是一位经验丰富的B2B商务开发专家，擅长撰写高转化率的定制化开发信（cold email）。你的每一封邮件都必须让人感觉"这家公司认真研究过我们"。

## 严格规则（7条）

1. **开头自然且有针对性** — 先用 1 句简短自然的寒暄或引入（如提及对方最近的项目、行业动态、或"I came across your work on..."），让收件人感到这不是群发邮件。禁止使用 "Hope you are well"、"Hope this email finds you well" 等空洞模板开场白。寒暄要简短（1句话），不要占太多篇幅，快速过渡到正题。

2. **中间说明匹配理由** — 不要罗列产品目录。要从客户需求 × 我司能力的交叉分析出发，具体说明为什么双方值得合作，解决客户的什么痛点。

3. **案例必须相关** — 根据客户的行业、地区、项目类型，从我司案例中选择最相关的 1-2 个。不要堆砌不相关的案例。简要说明案例与客户的关联性。

4. **语气专业自然** — 像有经验的商务人士直接沟通。不要使用营销话术、感叹号轰炸、过度热情的语气。简洁、自信、专业。

5. **CTA 要轻量** — 以询问兴趣、提议简短通话、分享案例资料为主。不要硬性推销、不要催促、不要用 "Don't miss this opportunity" 之类的话术。

6. **禁止编造** — 只使用客户数据中已有的信息。不要编造客户的近期项目、业务规模、联系方式等。

7. **长度控制** — 英文邮件 150-300 词，中文邮件 200-400 字。宁可太短也不要太长。

## 输出格式

严格输出 JSON 格式，不要在 JSON 外附加任何文字：
{"email_subject": "邮件主题", "email_body": "邮件正文"}

邮件正文不要包含 Subject 行，只需纯正文内容。

## 邮件正文格式要求

email_body 必须是**纯文本**，严禁包含任何 Markdown 格式标记：
- 禁止 `**粗体**`、`*斜体*`、`~~删除线~~`
- 禁止 `## 标题`、`### 子标题`
- 禁止 `- 列表项`、`1. 有序列表`
- 禁止 `[链接文字](URL)`、`![图片](URL)`
- 禁止 `> 引用`、`--- 分割线`
- 如需强调，用大写或重复标点（如 "15,000 sqm" 而非 "**15,000 sqm**"）
- 如需分段，用空行分隔即可"""


# ---------------------------------------------------------------------------
# Prompt construction — ported from toolkit
# ---------------------------------------------------------------------------

def build_system_prompt(language: str) -> str:
    """Build the full system prompt with language requirement."""
    parts = [_BASE_SYSTEM_PROMPT]
    if language == "cn":
        parts.append(
            "\n## 语言要求\n"
            "请用中文撰写邮件。邮件主题和正文都必须是中文商务表达。"
        )
    else:
        parts.append(
            "\n## Language Requirement\n"
            "Write the email in English only. Both email_subject and email_body must be English. "
            "Do not output Chinese sentences, Chinese section labels, or mixed Chinese-English copy."
        )
    parts.append(
        "\n## 数据使用要求\n"
        "如果客户数据缺少 AI分析摘要、业务匹配点或开发建议，只能基于已提供的客户字段"
        "（公司名、网站、国家/地区、行业、公司角色、联系人、邮箱等）和我司信息进行合理撰写。"
        "不要编造客户项目、近期动态、规模、采购需求或联系人细节；信息不足时用更保守、自然的切入。"
    )
    return "\n".join(parts)


def build_profile_section(profile: dict) -> str:
    """Build a structured '我司信息' section from profile_data dict.

    Ported from toolkit utils.py build_profile_section().
    """
    company_name = profile.get("company_name", "")
    one_line_intro = profile.get("one_line_intro", "")

    lines = []
    lines.append("=== 我司信息 ===")
    lines.append(f"公司名称: {company_name}")
    if one_line_intro:
        lines.append(f"一句话介绍: {one_line_intro}")

    # Products
    products = profile.get("products", [])
    if products:
        lines.append("")
        lines.append("--- 产品线 ---")
        for p in products:
            sp = p.get("key_selling_points", [])
            sp_text = "；".join(sp) if sp else ""
            lines.append(f"• {p['name']}")
            if sp_text:
                lines.append(f"  卖点: {sp_text}")

    # Core competencies
    competencies = profile.get("core_competencies", [])
    if competencies:
        lines.append("")
        lines.append("--- 核心竞争力 ---")
        for c in competencies:
            lines.append(f"• {c['competency']}: {c.get('evidence', c.get('description', ''))}")

    # Case studies — use only usable_in_outreach ones, prioritize international
    cases = [cs for cs in profile.get("case_studies", []) if cs.get("usable_in_outreach")]
    international = [c for c in cases if c.get("country") and c["country"] not in ("中国",)]
    domestic = [c for c in cases if c.get("country") in ("中国",)]
    cases = (international[:7] + domestic[:3])[:10]

    if cases:
        lines.append("")
        lines.append("--- 代表性案例 ---")
        for cs in cases:
            proj = cs.get("project_en", cs.get("project", ""))
            country = cs.get("country", "")
            prods = ", ".join(cs.get("products_used", []))
            highlight = cs.get("key_highlight", "")
            lines.append(f"• {proj}（{country}）| 产品: {prods} | 亮点: {highlight}")

    # Unique selling points
    usps = profile.get("unique_selling_points", [])
    if usps:
        lines.append("")
        lines.append("--- 独特卖点 ---")
        for u in usps:
            lines.append(f"• {u}")

    # Certifications
    certs = profile.get("certifications", [])
    if certs:
        lines.append("")
        lines.append("--- 资质认证 ---")
        for c in certs:
            lines.append(f"• {c}")

    # Cooperation models
    models = profile.get("cooperation_models", [])
    if models:
        lines.append("")
        lines.append("--- 合作模式 ---")
        for m in models:
            lines.append(f"• {m['model']}: {m.get('description', '')}")

    # Customer matching guide
    guide = profile.get("customer_matching_guide", [])
    if guide:
        lines.append("")
        lines.append("--- 客户匹配指南（请据此判断待分析公司属于哪种类型，并参考对应建议） ---")
        for g in guide:
            pp = "；".join(g.get("priority_points", []))
            lines.append(f"• {g['customer_type']}: 重点强调 {pp}")

    return "\n".join(lines)


def select_relevant_cases(customer: dict, all_cases: list, max_cases: int = 3) -> list:
    """Select the most relevant case studies for a specific customer.

    Scoring:
      - Same country: +100
      - Same industry overlap: +50
      - Same customer type: +30
      - International case (not China): +10

    Ported from toolkit.
    """
    if not all_cases:
        return []

    customer_country = (customer.get("country") or "").lower()
    customer_industry = (customer.get("industry") or "").lower()
    customer_role = (customer.get("company_role") or "").lower()

    scored = []
    for case in all_cases:
        score = 0

        case_country = (case.get("country") or "").lower()
        if customer_country and case_country:
            if customer_country in case_country or case_country in customer_country:
                score += 100

        case_industry = (case.get("industry") or "").lower()
        if customer_industry and case_industry:
            ind_words = set(re.findall(r"\w+", customer_industry))
            case_words = set(re.findall(r"\w+", case_industry))
            if ind_words & case_words:
                score += 50

        case_client_type = (case.get("client_type") or "").lower()
        if customer_role and case_client_type:
            role_words = set(re.findall(r"\w+", customer_role))
            type_words = set(re.findall(r"\w+", case_client_type))
            if role_words & type_words:
                score += 30

        if case_country and case_country not in ("中国", "china", "chinese"):
            score += 10

        scored.append((score, case))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [case for _, case in scored[:max_cases]]


def build_user_prompt(customer: dict, profile: dict, selected_cases: list | None = None, language: str = "en") -> str:
    """Build the user prompt for AI email generation.

    Ported from toolkit. Maps Lead model fields to prompt field names.
    """
    lines = []

    # Customer info section
    lines.append("=== 客户信息 ===")
    lines.append(f"公司名称: {customer.get('company_name', 'N/A')}")
    lines.append(f"网站: {customer.get('website', 'N/A')}")
    lines.append(f"国家/地区: {customer.get('country', 'N/A')}")
    lines.append(f"行业: {customer.get('industry', 'N/A')}")
    lines.append(f"公司角色: {customer.get('company_role', 'N/A')}")
    lines.append(f"联系人: {customer.get('contact_name', 'N/A')}")
    lines.append(f"邮箱: {customer.get('email', 'N/A')}")

    ai_summary = customer.get("ai_summary", "").strip()
    if ai_summary:
        lines.append(f"\nAI分析摘要:\n{ai_summary}")

    # Lead.business_match → prompt's business_match_points
    match_points = customer.get("business_match_points", "").strip()
    if match_points:
        lines.append(f"\n业务匹配点:\n{match_points}")

    # Lead.outreach_suggestion → prompt's outreach_content
    outreach = customer.get("outreach_content", "").strip()
    if outreach:
        lines.append(f"\n开发建议:\n{outreach}")

    # My company info — with smart case selection
    if profile:
        lines.append("")
        if selected_cases is not None:
            # Build profile section with case override
            all_usable = [cs for cs in profile.get("case_studies", []) if cs.get("usable_in_outreach")]
            lines.append(_build_profile_section_with_cases(profile, selected_cases, all_usable))
        else:
            lines.append(build_profile_section(profile))

    lines.append("")
    if not (ai_summary or match_points or outreach):
        lines.append("")
        lines.append(
            "注意：该客户缺少 AI分析摘要/业务匹配点/开发建议。请只根据客户表格中已有字段和我司信息写信，"
            "用保守、可信的方式建立联系，不要假装知道客户的具体项目或近期动态。"
        )

    lines.append("请根据以上信息，为这家客户撰写一封个性化开发信。")
    if language == "cn":
        lines.append("语言再次确认：请输出中文邮件。")
    else:
        lines.append("Language reminder: output English email only.")
    lines.append("严格遵守7条规则，输出 JSON 格式。")

    return "\n".join(lines)


def _build_profile_section_with_cases(profile: dict, cases_override: list, all_usable: list) -> str:
    """Build profile section with specific case selection."""
    company_name = profile.get("company_name", "")
    one_line_intro = profile.get("one_line_intro", "")

    lines = []
    lines.append("=== 我司信息 ===")
    lines.append(f"公司名称: {company_name}")
    if one_line_intro:
        lines.append(f"一句话介绍: {one_line_intro}")

    products = profile.get("products", [])
    if products:
        lines.append("")
        lines.append("--- 产品线 ---")
        for p in products:
            sp = p.get("key_selling_points", [])
            sp_text = "；".join(sp) if sp else ""
            lines.append(f"• {p['name']}")
            if sp_text:
                lines.append(f"  卖点: {sp_text}")

    competencies = profile.get("core_competencies", [])
    if competencies:
        lines.append("")
        lines.append("--- 核心竞争力 ---")
        for c in competencies:
            lines.append(f"• {c['competency']}: {c.get('evidence', c.get('description', ''))}")

    # Use overridden cases
    cases = cases_override
    if cases:
        lines.append("")
        lines.append("--- 代表性案例 ---")
        for cs in cases:
            proj = cs.get("project_en", cs.get("project", ""))
            country = cs.get("country", "")
            prods = ", ".join(cs.get("products_used", []))
            highlight = cs.get("key_highlight", "")
            lines.append(f"• {proj}（{country}）| 产品: {prods} | 亮点: {highlight}")

    usps = profile.get("unique_selling_points", [])
    if usps:
        lines.append("")
        lines.append("--- 独特卖点 ---")
        for u in usps:
            lines.append(f"• {u}")

    certs = profile.get("certifications", [])
    if certs:
        lines.append("")
        lines.append("--- 资质认证 ---")
        for c in certs:
            lines.append(f"• {c}")

    models = profile.get("cooperation_models", [])
    if models:
        lines.append("")
        lines.append("--- 合作模式 ---")
        for m in models:
            lines.append(f"• {m['model']}: {m.get('description', '')}")

    guide = profile.get("customer_matching_guide", [])
    if guide:
        lines.append("")
        lines.append("--- 客户匹配指南（请据此判断待分析公司属于哪种类型，并参考对应建议） ---")
        for g in guide:
            pp = "；".join(g.get("priority_points", []))
            lines.append(f"• {g['customer_type']}: 重点强调 {pp}")

    return "\n".join(lines)


def parse_ai_response(response_text: str) -> dict | None:
    """Parse AI response, handling markdown code blocks and raw JSON.

    Ported from toolkit utils.py.
    """
    text = response_text.strip()

    code_block_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if code_block_match:
        text = code_block_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        try:
            return json.loads(text[brace_start : brace_end + 1])
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# AI call (sync, run in thread)
# ---------------------------------------------------------------------------

def _is_language_match(subject: str, body: str, language: str) -> bool:
    text = f"{subject}\n{body}".strip()
    if not text:
        return False
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    if language == "cn":
        return cjk_count >= 8
    return cjk_count == 0


def _generate_one_sync(customer: dict, profile: dict, system_prompt: str, language: str) -> dict | None:
    """Generate a personalized email for a single customer. Synchronous.

    Returns {"email_subject": "...", "email_body": "..."} or None on failure.
    """
    all_cases = [cs for cs in profile.get("case_studies", []) if cs.get("usable_in_outreach")]
    selected_cases = select_relevant_cases(customer, all_cases, max_cases=3)
    user_prompt = build_user_prompt(customer, profile, selected_cases, language)

    for attempt in range(3):  # max_retries=2 → 3 attempts total
        try:
            output = replicate.run(
                settings.replicate_model,
                input={
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )

            if isinstance(output, list):
                response_text = "".join(output)
            else:
                response_text = str(output)

            result = parse_ai_response(response_text)

            if result is None or "email_body" not in result:
                logger.warning("Failed to parse AI response (attempt %d) for %s", attempt + 1, customer.get("company_name"))
                if attempt < 2:
                    time.sleep(2)
                    continue
                return {
                    "email_subject": result.get("email_subject", "") if result else "",
                    "email_body": response_text[:2000] if response_text else "",
                }

            subject = result.get("email_subject", "").strip()
            body = result.get("email_body", "").strip()
            if not body:
                if attempt < 2:
                    time.sleep(2)
                    continue
            if not _is_language_match(subject, body, language):
                logger.warning(
                    "Email language mismatch for %s (expected %s, attempt %d)",
                    customer.get("company_name"),
                    language,
                    attempt + 1,
                )
                if attempt < 2:
                    time.sleep(2)
                    continue
                return None

            return {"email_subject": subject, "email_body": body}

        except Exception as e:
            logger.error("Replicate API error (attempt %d): %s", attempt + 1, str(e)[:200])
            if attempt < 2:
                time.sleep(3)
                continue
            return None

    return None


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _create_task_log(task_id: int, step: int, name: str, status: str = "pending", message: str = "", progress: int = 0):
    async with async_session_factory() as db:
        log = TaskLog(
            task_id=task_id,
            step_number=step,
            step_name=name,
            status=status,
            message=message,
            progress=progress,
        )
        db.add(log)
        await db.commit()


async def _update_task_log(task_id: int, step: int, status: str | None = None, message: str | None = None, progress: int | None = None):
    async with async_session_factory() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(TaskLog).where(TaskLog.task_id == task_id, TaskLog.step_number == step)
        )
        log = result.scalar_one_or_none()
        if log:
            if status is not None:
                log.status = status
            if message is not None:
                log.message = message
            if progress is not None:
                log.progress = progress
            await db.commit()


async def _mark_task_done(task_id: int, status: str, result_summary: dict):
    async with async_session_factory() as db:
        from datetime import datetime, timezone
        task = await db.get(Task, task_id)
        if task:
            task.status = status
            task.result_summary = result_summary
            task.ended_at = datetime.now(timezone.utc)
            await db.commit()
        task_manager.remove_task(task_id)


# ---------------------------------------------------------------------------
# Lead → customer dict mapper
# ---------------------------------------------------------------------------

def _lead_to_customer_dict(lead: Lead) -> dict:
    """Map Lead ORM model to the customer dict format expected by the prompt."""
    return {
        "company_name": lead.company_name,
        "website": lead.website,
        "country": lead.country,
        "industry": lead.industry,
        "company_role": lead.company_role,
        "contact_name": lead.contact_name,
        "email": lead.email,
        "phone": lead.phone,
        "ai_summary": lead.ai_summary,
        "business_match_points": lead.business_match,
        "outreach_content": lead.outreach_suggestion,
        "match_score": lead.match_score,
        "_lead_id": lead.id,
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def run_email_craft_pipeline(task_id: int, user_id: int, intent: dict):
    """Run the email-craft pipeline in background.

    4 steps:
    1. Load company profile
    2. Load leads (DB + uploaded files)
    3. Generate emails one by one (with heartbeat)
    4. Save results to outreach_emails table
    """
    params = intent.get("params", {})
    language = params.get("language", "en")
    lead_ids = params.get("lead_ids") or []
    source_task_id = params.get("source_task_id")

    try:
        # ── Step 1: Load company profile ──
        await _create_task_log(task_id, 1, "加载公司画像", "running", "正在加载公司画像...", 0)

        async with async_session_factory() as db:
            from sqlalchemy import select
            result = await db.execute(
                select(CompanyProfile).where(
                    CompanyProfile.user_id == user_id,
                    CompanyProfile.is_current == True,
                )
            )
            profile_record = result.scalar_one_or_none()

        if profile_record is None:
            await _update_task_log(task_id, 1, "failed", "未找到公司画像，请先建立公司画像", 0)
            await _mark_task_done(task_id, "failed", {"error": "未找到公司画像"})
            return

        profile_data = profile_record.profile_data or {}
        company_name = profile_data.get("company_name", "")

        await _update_task_log(task_id, 1, "completed", f"已加载公司画像: {company_name}", 100)
        task_manager.update_heartbeat(task_id)

        # ── Step 2: Load leads ──
        await _create_task_log(task_id, 2, "加载线索数据", "running", "正在加载线索数据...", 0)

        leads: list[Lead] = []
        async with async_session_factory() as db:
            from sqlalchemy import select
            task_ids_query = select(Task.id).where(Task.user_id == user_id)
            lead_query = select(Lead).where(Lead.task_id.in_(task_ids_query))
            if lead_ids:
                lead_query = lead_query.where(Lead.id.in_(lead_ids))
            elif source_task_id:
                lead_query = lead_query.where(Lead.task_id == source_task_id)

            result = await db.execute(lead_query.order_by(Lead.match_score.desc()))
            db_leads = result.scalars().all()
            leads.extend(db_leads)

        total_leads = len(leads)
        await _update_task_log(task_id, 2, "completed", f"已加载 {total_leads} 条线索", 100)
        task_manager.update_heartbeat(task_id)

        if total_leads == 0:
            await _mark_task_done(task_id, "failed", {"error": "没有可用的线索数据"})
            return

        # ── Step 3: Generate emails ──
        await _create_task_log(task_id, 3, "生成开发信", "running", f"正在为 {total_leads} 条线索生成开发信...", 0)

        system_prompt = build_system_prompt(language)
        success_count = 0
        failed_count = 0

        for i, lead in enumerate(leads):
            # Check cancellation
            async with async_session_factory() as db:
                task = await db.get(Task, task_id)
                if task and task.cancelled:
                    await _update_task_log(task_id, 3, "cancelled",
                                          f"已取消，已完成 {i}/{total_leads}", i)
                    await _mark_task_done(task_id, "cancelled", {"generated": success_count, "failed": failed_count})
                    return

            customer = _lead_to_customer_dict(lead)
            company_name_lead = customer.get("company_name", "Unknown")

            try:
                result = await asyncio.to_thread(
                    _generate_one_sync, customer, profile_data, system_prompt, language
                )
            except Exception as e:
                logger.error("Email generation error for %s: %s", company_name_lead, str(e)[:200])
                result = None

            if result and result.get("email_body"):
                # Save to DB. Rewrite existing drafts, but keep sent-mail history intact.
                async with async_session_factory() as db:
                    latest_email_result = await db.execute(
                        select(OutreachEmail)
                        .where(OutreachEmail.lead_id == lead.id)
                        .order_by(OutreachEmail.created_at.desc())
                        .limit(1)
                    )
                    latest_email = latest_email_result.scalar_one_or_none()
                    if latest_email and latest_email.send_status != "sent":
                        latest_email.task_id = task_id
                        latest_email.email_subject = result.get("email_subject", "")
                        latest_email.email_body = result["email_body"]
                        latest_email.error_message = ""
                    else:
                        email_record = OutreachEmail(
                            lead_id=lead.id,
                            task_id=task_id,
                            email_subject=result.get("email_subject", ""),
                            email_body=result["email_body"],
                            send_status="draft",
                        )
                        db.add(email_record)
                    await db.commit()
                success_count += 1
            else:
                failed_count += 1

            progress = int((i + 1) / total_leads * 100)
            await _update_task_log(task_id, 3, "running",
                                  f"[{i + 1}/{total_leads}] {'成功' if result else '失败'} — {company_name_lead}",
                                  progress)
            task_manager.update_heartbeat(task_id)

            # Rate limiting
            if i < total_leads - 1:
                await asyncio.sleep(1)

        # ── Step 4: Save results ──
        await _create_task_log(task_id, 4, "保存结果", "running", "正在保存生成结果...", 0)

        result_summary = {
            "generated": success_count,
            "failed": failed_count,
            "total": total_leads,
            "language": language,
            "leadIds": lead_ids,
            "sourceTaskId": source_task_id,
        }

        await _update_task_log(task_id, 4, "completed",
                              f"生成完成：成功 {success_count} 封，失败 {failed_count} 封",
                              100)
        await _mark_task_done(task_id, "completed", result_summary)

    except Exception as e:
        logger.error("Email-craft pipeline failed for task %d: %s", task_id, str(e)[:500])
        try:
            await _create_task_log(task_id, 1, "failed", f"Pipeline 错误: {str(e)[:200]}", 0)
            await _mark_task_done(task_id, "failed", {"error": str(e)[:300]})
        except Exception:
            pass
