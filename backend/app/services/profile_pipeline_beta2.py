"""Beta2 company profile pipeline: sales-intelligence-driven crawling.

10-step pipeline:
  1. Resolve domain (URL variants → accessibility check)
  2. Discover pages (homepage links + Serper + sitemap)
  3. Rank & select pages (category scoring + diversity)
  4. Fetch page content (lightweight httpx + Playwright fallback)
  5. Clean HTML content
  6. Extract contacts & resources
  7. Build evidence pack
  8. AI analysis (Replicate)
  9. Save profile to DB
  10. Done
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime

import httpx
import replicate
from sqlalchemy import select, update

from app.config import settings
from app.database import async_session_factory
from app.models.company_profile import CompanyProfile
from app.models.task import Task, TaskLog
from app.services import task_manager
from app.services.profile_pipeline_service import (
    PROFILE_SYSTEM_PROMPT,
    _merge_profile_data,
    _normalize_completeness,
    _normalize_profile,
    _parse_ai_json,
    _profile_to_markdown,
    extract_url,
)
from app.services.settings_service import ensure_recommended_email_settings
from app.utils.db_sequences import sync_company_profiles_id_sequence
from app.utils.profile_beta2 import (
    completeness,
    contact_extractor,
    content_cleaner,
    domain_resolver,
    evidence_pack,
    page_discovery,
    page_fetcher,
    page_ranking,
)

logger = logging.getLogger(__name__)

if settings.replicate_api_token and not os.environ.get("REPLICATE_API_TOKEN"):
    os.environ["REPLICATE_API_TOKEN"] = settings.replicate_api_token


# Reuse task log helpers from the existing module
async def _create_task_log(db, task_id, step, name, status="running", message="", progress=0):
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
    await db.refresh(log)
    return log


async def _update_task_log(db, task_id, step, status=None, message=None, progress=None):
    result = await db.execute(
        select(TaskLog).where(TaskLog.task_id == task_id, TaskLog.step_number == step)
    )
    log = result.scalar_one_or_none()
    if log is None:
        return
    if status is not None:
        log.status = status
    if message is not None:
        log.message = message
    if progress is not None:
        log.progress = progress
    await db.commit()


def _compact_join(items):
    return ", ".join(str(i) for i in items if i) if items else ""


def _build_beta2_user_prompt(source_text: str, evidence_prompt: str) -> str:
    """Build user prompt for AI analysis using evidence pack."""
    parts = [
        "请根据以下采集到的公司官网和用户提供的资料，构建完整的公司画像。",
    ]
    if source_text:
        parts.append(f"\n## 用户提供的资料\n{source_text[:5000]}")
    parts.append(f"\n{evidence_prompt}")
    return "\n".join(parts)


def _analyze_profile_sync_beta2(source_text: str, evidence_prompt: str) -> dict:
    """Call Replicate AI to analyze the evidence pack and generate profile."""
    user_prompt = _build_beta2_user_prompt(source_text, evidence_prompt)
    client = replicate.Client(
        api_token=settings.replicate_api_token,
        timeout=httpx.Timeout(connect=20.0, read=420.0, write=60.0, pool=20.0),
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            output = client.run(
                settings.replicate_model,
                input={
                    "messages": [
                        {"role": "system", "content": PROFILE_SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                },
            )
            response_text = "".join(output) if isinstance(output, list) else str(output)
            logger.info("Beta2 AI response (%d chars): %s", len(response_text), response_text[:500])
            parsed = _parse_ai_json(response_text)
            if parsed is None:
                logger.warning("Beta2 AI response not valid JSON: %s", response_text[:500])
                if attempt < 2:
                    time.sleep(2)
                    continue
                raise ValueError(f"AI response is not valid JSON: {response_text[:200]}")
            return parsed
        except (httpx.TimeoutException, TimeoutError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            break

    raise RuntimeError(f"AI 整理画像超时：{last_error}")


async def _serper_fallback(domain: str) -> str:
    """When website is inaccessible, get basic info from Serper snippets."""
    if not settings.serper_api_key or not domain:
        return ""

    snippets: list[str] = []
    queries = [f"site:{domain}", domain]

    async with httpx.AsyncClient(timeout=15) as client:
        for q in queries:
            try:
                resp = await client.post(
                    "https://google.serper.dev/search",
                    headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
                    json={"q": q, "num": 5},
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for organic in data.get("organic", []):
                    title = organic.get("title", "")
                    snippet = organic.get("snippet", "")
                    link = organic.get("link", "")
                    if title or snippet:
                        snippets.append(f"- {title}: {snippet} ({link})")
            except Exception:
                continue

    return "\n".join(snippets) if snippets else ""


def _build_timeout_fallback(website: str, source_text: str, evidence: evidence_pack.EvidencePack) -> dict:
    """Build a minimal profile when AI times out."""
    from urllib.parse import urlparse

    hostname = urlparse(website).netloc.replace("www.", "") if website else ""
    company_name = hostname.split(".")[0].upper() if hostname else "未命名公司"

    # Try to get company name from evidence pages
    for page in evidence.pages:
        if page.title and len(page.title) > 2:
            company_name = page.title.split("|")[0].split("-")[0].strip()[:80]
            break

    # Collect basic info from evidence
    industry = ""
    for page in evidence.pages:
        text = page.clean_text[:2000]
        if text:
            # Try to extract industry from headings
            for h in page.headings:
                if any(kw in h.lower() for kw in ("about", "company", "我们")):
                    industry = h
                    break
            if not industry:
                # Take first meaningful sentence
                for line in text.split("\n"):
                    if len(line) > 20 and not line.startswith(("-", "©", "Cookie")):
                        industry = line[:200]
                        break
            break

    return {
        "company_name": company_name,
        "one_line_intro": industry[:200] if industry else "",
        "full_intro": industry if industry else "",
        "location": evidence.contacts.get("addresses", [""])[0] if evidence.contacts.get("addresses") else "",
        "website": website,
        "products": [],
        "core_competencies": [],
        "target_customer_types": [],
        "case_studies": [],
        "certifications": [],
        "cooperation_models": [],
        "unique_selling_points": [],
        "customer_matching_guide": [],
        "boundaries": {"claims_we_can_make": [], "claims_we_cannot_make": [], "sensitive_topics": []},
        "english_profile": {},
        "metadata": {
            "source_urls": [p.url for p in evidence.pages if p.url],
            "profile_completeness": 0.1,
            "notes": "AI 分析超时，已保存基础草稿。请补充资料后重新采集覆盖。",
        },
    }


async def run_profile_pipeline_v2(task_id: int, user_id: int, intent: dict) -> None:
    """Beta2 company profile pipeline with 10-step progress."""
    params = intent.get("params", {})
    source_text = params.get("source_text", "") or ""
    website = params.get("url", "") or extract_url(source_text)

    warnings: list[str] = []
    source_urls: list[str] = []

    try:
        async with async_session_factory() as db:
            # ── Step 1: 识别公司网址 ──
            await _create_task_log(
                db, task_id, step=1, name="识别公司网址",
                status="running", message="正在解析域名...", progress=10,
            )

            if website:
                resolved = await domain_resolver.resolve_domain(website)
                params["url"] = resolved.base_url
                website = resolved.base_url
                source_urls.append(website)

                msg = f"域名解析完成: {resolved.domain}"
                if resolved.access_status != "ok":
                    msg += f" (访问状态: {resolved.access_status})"
                    warnings.append(f"官网访问异常: {resolved.access_status}")
                await _update_task_log(db, task_id, step=1, status="completed", message=msg, progress=100)
            else:
                resolved = domain_resolver.ResolvedDomain(domain="", base_url="", access_status="no_content")
                await _update_task_log(
                    db, task_id, step=1, status="completed",
                    message="未提供网址，将基于用户提供的资料生成画像", progress=100,
                )

            task_manager.update_heartbeat(task_id)

            # ── Step 2: 发现官网关键页面 ──
            await _create_task_log(
                db, task_id, step=2, name="发现官网关键页面",
                status="running", message="正在搜索和发现页面...", progress=10,
            )

            homepage_html = ""
            all_discovered: list[page_discovery.DiscoveredPage] = []

            if resolved.access_status == "ok":
                try:
                    async with httpx.AsyncClient(
                        follow_redirects=True,
                        timeout=httpx.Timeout(connect=5.0, read=12.0, write=5.0, pool=5.0),
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                    ) as client:
                        resp = await client.get(resolved.base_url)
                        homepage_html = resp.text or ""
                except Exception as exc:
                    logger.warning("Failed to fetch homepage for link extraction: %s", exc)

                all_discovered = await page_discovery.discover_pages(
                    base_url=resolved.base_url,
                    domain=resolved.domain,
                    html=homepage_html,
                    serper_api_key=settings.serper_api_key,
                )
                logger.info("Discovered %d pages for %s", len(all_discovered), resolved.domain)
            else:
                # Serper fallback for inaccessible sites
                warnings.append("官网不可访问，使用搜索引擎获取基础信息")
                serper_text = await _serper_fallback(resolved.domain)
                if serper_text:
                    # Create a minimal evidence from Serper snippets
                    from app.utils.profile_beta2.evidence_pack import EvidencePack
                    serper_evidence = EvidencePack(
                        input_url=website,
                        resolved_domain=resolved.domain,
                        crawl_status="partial_success",
                        website_access_status=resolved.access_status,
                        source_quality="partial",
                        pages=[],
                        contacts={},
                        warnings=warnings,
                    )

                    await _update_task_log(
                        db, task_id, step=2, status="completed",
                        message=f"官网不可访问，通过搜索获取到 {len(serper_text.splitlines())} 条信息", progress=100,
                    )

                    # Skip steps 3-7, go directly to AI analysis
                    # Step 8: AI analysis with Serper snippets only
                    await _create_task_log(
                        db, task_id, step=3, name="筛选高价值页面",
                        status="completed", message="跳过（官网不可访问）", progress=100,
                    )
                    await _create_task_log(
                        db, task_id, step=4, name="抓取页面内容",
                        status="completed", message="跳过（官网不可访问）", progress=100,
                    )
                    await _create_task_log(
                        db, task_id, step=5, name="清洗网页信息",
                        status="completed", message="跳过（官网不可访问）", progress=100,
                    )
                    await _create_task_log(
                        db, task_id, step=6, name="提取联系方式",
                        status="completed", message="跳过（官网不可访问）", progress=100,
                    )
                    await _create_task_log(
                        db, task_id, step=7, name="构建证据包",
                        status="completed", message="已构建搜索证据包", progress=100,
                    )

                    # Step 8: AI Analysis
                    await _create_task_log(
                        db, task_id, step=8, name="生成公司画像",
                        status="running", message="AI 正在基于搜索信息生成画像...", progress=10,
                    )
                    task_manager.update_heartbeat(task_id)

                    evidence_prompt = f"## 搜索引擎获取的基础信息\n{serper_text}\n\n注意：官网不可访问，以下信息仅来自搜索引擎摘要，可能不完整。请基于已有信息生成画像，不确定的内容留空。"
                    try:
                        profile = _analyze_profile_sync_beta2(source_text, evidence_prompt)
                    except Exception as exc:
                        error_text = str(exc).lower()
                        if "timeout" not in error_text and "timed out" not in error_text:
                            raise
                        logger.warning("AI analysis timed out, saving fallback: %s", exc)
                        profile = _build_timeout_fallback(website, source_text, serper_evidence)

                    profile = _normalize_profile(profile, website, source_urls)
                    # Add beta2 metadata
                    profile["metadata"]["pipeline_version"] = "beta2"
                    profile["metadata"]["crawl_status"] = "partial_success"
                    profile["metadata"]["website_access_status"] = resolved.access_status

                    await _update_task_log(db, task_id, step=8, status="completed", message="画像生成完成", progress=100)
                    task_manager.update_heartbeat(task_id)

                    # Step 9-10: Save and complete (reuse save logic below)
                    await _save_profile_to_db(
                        db, task_id, user_id, params, profile, website, source_urls, warnings,
                    )
                    return
                else:
                    await _update_task_log(
                        db, task_id, step=2, status="completed",
                        message="官网不可访问且搜索无结果", progress=100,
                    )
                    # Create empty evidence pack and continue with empty data
                    await _create_task_log(db, task_id, step=3, name="筛选高价值页面", status="completed", message="无页面可筛选", progress=100)
                    await _create_task_log(db, task_id, step=4, name="抓取页面内容", status="completed", message="无页面可抓取", progress=100)
                    await _create_task_log(db, task_id, step=5, name="清洗网页信息", status="completed", message="无内容可清洗", progress=100)
                    await _create_task_log(db, task_id, step=6, name="提取联系方式", status="completed", message="无联系方式可提取", progress=100)
                    await _create_task_log(db, task_id, step=7, name="构建证据包", status="completed", message="证据包为空", progress=100)

                    all_discovered = []
                    cleaned_pages = []
                    contacts = contact_extractor.Contacts()

                    # Build empty evidence pack and proceed to AI
                    from app.utils.profile_beta2.evidence_pack import EvidencePack as EP
                    ep = EP(
                        input_url=website,
                        resolved_domain=resolved.domain,
                        crawl_status="failed",
                        website_access_status=resolved.access_status,
                        source_quality="poor",
                        pages=[],
                        contacts={},
                        warnings=warnings,
                    )

                    await _create_task_log(db, task_id, step=8, name="生成公司画像", status="running", message="AI 正在基于已有资料生成画像...", progress=10)
                    task_manager.update_heartbeat(task_id)

                    try:
                        profile = _analyze_profile_sync_beta2(source_text, "（无官网内容可供分析，请仅基于用户提供的资料生成画像）")
                    except Exception as exc:
                        profile = _build_timeout_fallback(website, source_text, ep)

                    profile = _normalize_profile(profile, website, source_urls)
                    profile["metadata"]["pipeline_version"] = "beta2"
                    profile["metadata"]["crawl_status"] = "failed"
                    profile["metadata"]["website_access_status"] = resolved.access_status

                    await _update_task_log(db, task_id, step=8, status="completed", message="画像生成完成", progress=100)
                    await _save_profile_to_db(db, task_id, user_id, params, profile, website, source_urls, warnings)
                    return

            await _update_task_log(
                db, task_id, step=2, status="completed",
                message=f"发现 {len(all_discovered)} 个候选页面", progress=100,
            )
            task_manager.update_heartbeat(task_id)

            # ── Step 3: 筛选高价值页面 ──
            await _create_task_log(
                db, task_id, step=3, name="筛选高价值页面",
                status="running", message="正在评估页面价值...", progress=10,
            )

            seen_urls: set[str] = set()
            seen_titles: set[str] = set()
            scored_pages: list[dict] = []
            for page in all_discovered:
                norm_url = page.url.split("#")[0].rstrip("/")
                score = page_ranking.score_page(norm_url, page.title, seen_urls, seen_titles)
                seen_urls.add(norm_url)
                if page.title:
                    seen_titles.add(page.title.lower().strip())
                category = page_ranking.classify_url(page.url, page.link_text)
                scored_pages.append({
                    "url": page.url,
                    "title": page.title,
                    "link_text": page.link_text,
                    "source": page.source,
                    "category": category,
                    "score": score,
                })

            selected_pages = page_ranking.select_pages(scored_pages)
            logger.info("Selected %d pages out of %d", len(selected_pages), len(scored_pages))
            await _update_task_log(
                db, task_id, step=3, status="completed",
                message=f"已筛选 {len(selected_pages)} 个高价值页面", progress=100,
            )
            task_manager.update_heartbeat(task_id)

            # ── Step 4: 抓取页面内容 ──
            await _create_task_log(
                db, task_id, step=4, name="抓取页面内容",
                status="running", message=f"正在抓取 {len(selected_pages)} 个页面...", progress=10,
            )

            fetched_contents = await page_fetcher.fetch_pages(selected_pages, semaphore_count=3)
            success_count = sum(1 for c in fetched_contents if c.html and not c.error)
            await _update_task_log(
                db, task_id, step=4, status="completed",
                message=f"成功抓取 {success_count}/{len(selected_pages)} 个页面",
                progress=100,
            )
            if success_count < len(selected_pages):
                fail_count = len(selected_pages) - success_count
                warnings.append(f"{fail_count} 个页面抓取失败")
            task_manager.update_heartbeat(task_id)

            # ── Step 5: 清洗网页信息 ──
            await _create_task_log(
                db, task_id, step=5, name="清洗和整理网页信息",
                status="running", message="正在清洗网页内容...", progress=10,
            )

            cleaned_pages: list[dict] = []
            for content in fetched_contents:
                if not content.html:
                    cleaned_pages.append({
                        "url": content.url,
                        "title": content.title,
                        "clean_text": "",
                        "html": "",
                        "headings": [],
                        "fetch_method": content.fetch_method,
                        "status": content.status,
                        "category": "",
                        "score": 0,
                    })
                    continue

                cleaned = content_cleaner.clean_content(content.html, content.url)
                # Enrich with page metadata
                page_meta = next((p for p in selected_pages if p["url"] == content.url), {})
                cleaned_pages.append({
                    "url": content.url,
                    "title": cleaned.title or content.title,
                    "clean_text": cleaned.clean_text,
                    "html": content.html,
                    "headings": cleaned.headings,
                    "meta_description": cleaned.meta_description,
                    "fetch_method": content.fetch_method,
                    "status": content.status,
                    "category": page_meta.get("category", "other"),
                    "score": page_meta.get("score", 0),
                    "base_url": content.url,
                })

            total_chars = sum(len(p["clean_text"]) for p in cleaned_pages)
            await _update_task_log(
                db, task_id, step=5, status="completed",
                message=f"清洗完成，共 {total_chars:,} 字", progress=100,
            )
            task_manager.update_heartbeat(task_id)

            # ── Step 6: 提取联系方式 ──
            await _create_task_log(
                db, task_id, step=6, name="提取联系方式和资料链接",
                status="running", message="正在提取联系方式...", progress=10,
            )

            # Create simple objects for contact_extractor
            class PageData:
                def __init__(self, **kwargs):
                    for k, v in kwargs.items():
                        setattr(self, k, v)

            contact_pages = [PageData(**p) for p in cleaned_pages]
            contacts = contact_extractor.extract_contacts(contact_pages, resolved.domain)

            contact_summary = []
            if contacts.ranked_emails:
                contact_summary.append(f"{len(contacts.ranked_emails)} 个邮箱")
            if contacts.phones:
                contact_summary.append(f"{len(contacts.phones)} 个电话")
            if contacts.social_links:
                contact_summary.append(f"{len(contacts.social_links)} 个社交链接")
            if contacts.pdf_links:
                contact_summary.append(f"{len(contacts.pdf_links)} 个PDF文件")
            if contacts.addresses:
                contact_summary.append(f"{len(contacts.addresses)} 个地址")

            await _update_task_log(
                db, task_id, step=6, status="completed",
                message=f"提取完成：{', '.join(contact_summary) or '无联系方式'}",
                progress=100,
            )
            task_manager.update_heartbeat(task_id)

            # ── Step 7: 构建证据包 ──
            await _create_task_log(
                db, task_id, step=7, name="构建证据包",
                status="running", message="正在构建结构化证据包...", progress=10,
            )

            evidence_contact_pages = [PageData(**p) for p in cleaned_pages]
            ep = evidence_pack.build_evidence_pack(
                input_url=website,
                resolved_domain=resolved.domain,
                website_access_status=resolved.access_status,
                pages=evidence_contact_pages,
                contacts=contacts,
                warnings=warnings,
            )

            await _update_task_log(
                db, task_id, step=7, status="completed",
                message=f"证据包已构建（{len(ep.pages)} 页，状态: {ep.crawl_status}）",
                progress=100,
            )
            task_manager.update_heartbeat(task_id)

            # ── Step 8: 生成公司画像 ──
            await _create_task_log(
                db, task_id, step=8, name="生成公司画像",
                status="running", message="AI 正在分析采集内容...", progress=10,
            )
            task_manager.update_heartbeat(task_id)

            evidence_prompt = ep.to_ai_prompt()
            try:
                profile = _analyze_profile_sync_beta2(source_text, evidence_prompt)
            except Exception as exc:
                error_text = str(exc).lower()
                if "timeout" not in error_text and "timed out" not in error_text:
                    raise
                logger.warning("Beta2 AI analysis timed out, saving fallback: %s", exc)
                profile = _build_timeout_fallback(website, source_text, ep)

            profile = _normalize_profile(profile, website, source_urls)

            # Add beta2-specific metadata
            completeness_result = completeness.calculate_completeness(profile)
            profile["metadata"]["pipeline_version"] = "beta2"
            profile["metadata"]["crawl_status"] = ep.crawl_status
            profile["metadata"]["website_access_status"] = ep.website_access_status
            profile["metadata"]["source_quality"] = ep.source_quality
            profile["metadata"]["completeness_score"] = completeness_result.score
            profile["metadata"]["completeness_breakdown"] = completeness_result.breakdown
            profile["metadata"]["missing_items"] = completeness_result.missing_items
            profile["metadata"]["evidence_pages_count"] = len(ep.pages)
            profile["metadata"]["evidence_warnings"] = ep.warnings
            # Update AI's completeness with our rule-based score (take the max)
            ai_completeness = _normalize_completeness(profile["metadata"].get("profile_completeness", 0))
            rule_completeness = completeness_result.score / 100.0
            profile["metadata"]["profile_completeness"] = max(ai_completeness, rule_completeness)
            profile["metadata"]["notes"] = (
                profile["metadata"].get("notes", "") +
                f"\n[Beta2 Pipeline] 采集页面: {len(ep.pages)}, "
                f"完整度: {completeness_result.score}/100, "
                f"缺失项: {', '.join(completeness_result.missing_items)}"
            )

            await _update_task_log(db, task_id, step=8, status="completed", message="画像生成完成", progress=100)
            task_manager.update_heartbeat(task_id)

            # ── Step 9 & 10: 保存画像 ──
            await _save_profile_to_db(
                db, task_id, user_id, params, profile, website, source_urls, warnings,
            )

    except asyncio.CancelledError:
        logger.info("Beta2 profile pipeline cancelled for task %d", task_id)
        raise
    except Exception as exc:
        logger.exception("Beta2 profile pipeline failed: %s", exc)
        async with async_session_factory() as db:
            task = await db.get(Task, task_id)
            if task:
                task.status = "failed"
                task.ended_at = datetime.now()
                error_text = str(exc)
                if "timed out" in error_text.lower() or "超时" in error_text:
                    error_text = "AI 整理画像超时，请稍后重试。"
                task.result_summary = {"error": error_text[:500]}
                await db.commit()
    finally:
        task_manager.remove_task(task_id)


async def _save_profile_to_db(
    db, task_id: int, user_id: int, params: dict,
    profile: dict, website: str, source_urls: list[str], warnings: list[str],
) -> None:
    """Save profile to DB and update task result (steps 9-10)."""

    await _create_task_log(
        db, task_id, step=9, name="保存画像",
        status="running", message="正在保存公司画像...", progress=30,
    )

    markdown = _profile_to_markdown(profile)
    completeness_val = _normalize_completeness(profile.get("metadata", {}).get("profile_completeness", 0))
    task = await db.get(Task, task_id)

    profile_mode = params.get("profile_mode", "create")
    existing_profile_id = params.get("existing_profile_id")
    existing_profile = params.get("existing_profile")

    if profile_mode == "update" and existing_profile_id:
        existing_profile_dict = existing_profile if isinstance(existing_profile, dict) else {}
        merged_profile = _merge_profile_data(existing_profile_dict, profile)
        merged_profile = _normalize_profile(merged_profile, website, source_urls)
        merged_markdown = _profile_to_markdown(merged_profile)
        merged_completeness = _normalize_completeness(
            merged_profile.get("metadata", {}).get("profile_completeness")
        )

        cp = await db.get(CompanyProfile, existing_profile_id)
        if cp:
            cp.company_name = merged_profile.get("company_name", "")
            cp.profile_data = merged_profile
            cp.profile_markdown = merged_markdown
            cp.task_id = task_id

        task.status = "completed"
        task.ended_at = datetime.now()
        task.result_summary = {
            "companyName": merged_profile.get("company_name", ""),
            "industry": merged_profile.get("industry", ""),
            "products": len(merged_profile.get("products", [])),
            "cases": len(merged_profile.get("case_studies", [])),
            "completeness": merged_completeness,
            "profileId": existing_profile_id,
            "profileMode": "update",
            "pipelineVersion": "beta2",
        }
        await db.commit()
        await ensure_recommended_email_settings(db, user_id, existing_profile_id, merged_profile)

        await _update_task_log(db, task_id, step=9, status="completed", message="公司画像已更新", progress=100)
        await _create_task_log(db, task_id, step=10, name="完成", status="completed", message="全部完成", progress=100)
    else:
        # Create mode: new row
        await db.execute(
            update(CompanyProfile)
            .where(CompanyProfile.user_id == user_id, CompanyProfile.is_current == True)
            .values(is_current=False)
        )
        await sync_company_profiles_id_sequence(db)

        cp = CompanyProfile(
            user_id=user_id,
            task_id=task_id,
            company_name=profile.get("company_name", ""),
            profile_data=profile,
            profile_markdown=markdown,
            is_current=True,
        )
        db.add(cp)

        task.status = "completed"
        task.ended_at = datetime.now()
        task.result_summary = {
            "companyName": profile.get("company_name", ""),
            "industry": profile.get("industry", ""),
            "products": len(profile.get("products", [])),
            "cases": len(profile.get("case_studies", [])),
            "completeness": completeness_val,
            "profileId": None,
            "profileMode": "create",
            "pipelineVersion": "beta2",
        }
        await db.commit()
        await db.refresh(cp)
        await ensure_recommended_email_settings(db, user_id, cp.id, profile)
        task.result_summary = {**(task.result_summary or {}), "profileId": cp.id}
        await db.commit()

        await _update_task_log(db, task_id, step=9, status="completed", message="公司画像已保存", progress=100)
        await _create_task_log(db, task_id, step=10, name="完成", status="completed", message="全部完成", progress=100)

    task_manager.update_heartbeat(task_id)
