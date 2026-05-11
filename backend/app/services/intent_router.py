"""LLM-based intent router: classify user messages into pipeline actions.

Uses Replicate API (configured by REPLICATE_MODEL) to understand user intent and extract
structured parameters. Falls back to regex-based parse_search_intent on failure.
"""

import asyncio
import json
import logging
import os
import re
import time

import replicate

from app.config import settings

# Ensure replicate library can find the token
if settings.replicate_api_token and not os.environ.get("REPLICATE_API_TOKEN"):
    os.environ["REPLICATE_API_TOKEN"] = settings.replicate_api_token

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """你是一个外贸业务助手的意图识别模块。分析用户消息，返回 JSON。

可用动作：
- customer_acquisition: 用户要找客户/公司/供应商/分销商/批发商/制造商（必须包含明确的搜索意图，如"找"、"搜索"、"开发"、"帮我找"）
- company_profile: 用户要整理/补充/修改公司信息/公司画像/公司简介/公司资料（用户提供实际内容时使用）
- view_profile: 用户想查看/了解当前已有的公司信息/公司画像/公司资料（如"我的公司信息是什么"、"看一下公司资料"、"公司画像"、"公司简介是什么"、"我们公司资料"）
- email_craft: 用户要写开发信/生成邮件内容/起草邮件/为具体客户定制邮件；或者用户要求在开发信中加入特定内容（如"开发信里要提白云机场项目"、"邮件里写上我们15年经验"），核心是邮件撰写意图，具体内容要求提取为 user_requirements 参数
- email_blast: 用户要发送开发信/发邮件/批量发邮件/群发邮件/把邮件发出去（重点是"发送/发出去"，触发实际发送动作）
- chat: 闲聊、提问、其他不属于以上动作的对话

重要区分规则：
- "写开发信"、"生成开发信"、"帮我写邮件" → email_craft（写/生成/起草）
- "发邮件"、"发送开发信"、"发开发信"、"把邮件发出去" → email_blast（发送/发出去）
- 如果用户说"发邮件"，核心动作是发送，应识别为 email_blast 而不是 email_craft
- "开发信"搭配"写/生成/起草"时是 email_craft，搭配"发/发送/群发/批量发"时是 email_blast

公司信息相关动作区分：
- "我的公司信息是什么"、"看一下公司资料"、"公司画像"、"公司简介是什么" → view_profile（仅查看，不修改）
- "公司信息修改"、"修改公司资料" 但没有提供任何实际修改内容（无 URL、无具体描述、消息太短） → company_profile，profile_mode="update"，needs_clarification=true
- "我们做过...项目"、"我们公司有...产品"、"我们有...资质"、"我们的产品是..." → company_profile，profile_mode="update"（第一人称表述公司信息 = 补充画像）
- "找客户"、"搜索公司"、"帮我找供应商" → customer_acquisition（明确的搜索意图）
- **区分"找新客户"和"查历史记录"**："帮我找美国客户"= customer_acquisition（找新客户）；"帮我找我们做过的项目"、"找天花客户我们做过白云机场项目"= view_profile（查看历史案例/公司信息）。如果"找"后面跟的是"我们做过/我们合作过/以前的/过去的"，这不是搜索新客户，也不是修改画像，而是查看已有的公司资料，应归为 view_profile。
- **搜索意图优先于第一人称表述**：如果消息中包含明确的搜索新客户意图（如"找美国客户"、"帮我找供应商"、"搜索天花企业"）和第一人称公司描述，核心动作是搜索，应归为 customer_acquisition。仅当消息纯粹是描述公司信息、没有搜索新客户意图时才归为 company_profile。
- **邮件内容注入 = email_craft**：如果用户说"开发信里要提/加/写我们做过XX项目/有XX资质"，核心需求是写邮件时包含这些内容。应归为 email_craft，并将具体要求提取为 params 中的 user_requirements 字段（如 "在邮件中提到白云机场项目案例"）。
- 注意：包含"我们做过"、"我们公司"、"我们有"、"我们的产品"、"我们服务过"、"我们参与"、"我们有资质"等第一人称表述时，用户是在描述自己公司，应归为 company_profile（profile_mode=update），而不是 customer_acquisition。但此规则仅在没有明确搜索新客户或写邮件意图时生效。

返回格式（严格按照此 JSON 结构）：
{
  "action": "动作名称",
  "params": {
    "industry": "宽泛行业/产品大类（英文，如 LED lighting, solar panel, ceiling systems, bearings）",
    "country": "目标国家（英文，如 USA, Germany）",
    "keywords": ["搜索细分词或客户类型关键词1", "搜索细分词或客户类型关键词2"],
    "num": 数量（整数，默认20）,
    "url": "公司网站 URL（仅 company_profile 需要）",
    "profile_mode": "create | update | replace（仅 company_profile 需要）",
    "needs_clarification": true | false（仅 company_profile 使用，当用户说"修改"但没提供具体修改内容时设为 true），
    "user_requirements": "用户对开发信的具体要求（仅 email_craft 使用，如'在邮件中提到白云机场项目案例'）。当用户说'开发信里要提/加/写XX'时，将XX整理为简洁的要求描述。"
  },
  "reply": "一句简短的中文确认回复"
}
- num: 数量（整数，默认 20）
- url: 公司网站 URL（仅 company_profile 需要）
- profile_mode: 仅 company_profile 使用。create=首次建立画像；update=在已有画像上补充/修正/追加/删除资料；replace=用户明确要求重新采集、从头生成、覆盖旧画像。
- needs_clarification: 仅 company_profile 使用。当用户说"修改公司资料"/"公司信息修改"但没有提供具体修改内容时设为 true，系统会提示用户说明要修改什么。
- reply: 一句简短的确认回复（中文，如"好的，正在为您搜索..."）

规则：
1. 中文数字（三、五、十）要转为阿拉伯数字
2. 中文行业名/国家名要转为英文
3. 如果用户消息不明确属于任何动作，设为 chat
4. reply 要简短自然，像是助手的确认回复
5. 只返回 JSON，不要附加其他文字
6. customer_acquisition 的 params 必须包含 industry, country, keywords, num
7. industry 必须是宽泛赛道/产品大类，不要把用户给的细分关键词直接当行业。
   - "铝天花""酒店天花"不是行业，应放入 keywords；industry 应为 "ceiling systems" 或 "building materials"。
   - "轴承企业"可归为 industry="bearings"，具体"滚珠轴承/线性轴承"放入 keywords。
   - "开发三家美国的天花本土企业，铝天花，酒店天花关键词"应返回：
     industry="ceiling systems", country="USA", keywords=["local company", "aluminum ceiling", "hotel ceiling"], num=3
8. keywords 用来承载用户明确说的"关键词"、细分产品、应用场景、客户类型（manufacturer/distributor/wholesaler/local company 等），多个关键词要全部保留并翻译成英文。
9. company_profile 必须判断 profile_mode：用户说"补充、补一下、这些也是案例、加上、修改、修正、再看这个网站、这里还有资料/图片、删除、移除、去掉、剔除、不要这个、帮我删"时返回 update；用户说"重新、从头、覆盖、不要之前的、全部重做"时返回 replace；首次建立公司资料时返回 create。
10. 当 action 为 email_craft 且用户消息中包含具体客户信息（公司名、邮箱、联系人、网站等）时，在 params 中附加 extracted_lead 对象，只填能从消息中明确识别的字段，其余留空字符串：
    "extracted_lead": {"company_name": "公司名", "website": "网站", "country": "国家", "industry": "行业", "company_role": "公司角色", "contact_name": "联系人", "email": "邮箱", "phone": "电话"}
    如果用户没有提到任何具体客户信息，不要加 extracted_lead。只有明确出现公司名时才添加。
11. 第一人称公司表述检测：如果用户消息中包含"我们做过"、"我们公司"、"我们有"、"我们的产品"、"我们服务过"、"我们参与"、"我们有资质"等，说明用户在描述自己公司信息，应归为 company_profile（profile_mode=update），而非 customer_acquisition。但此规则仅在没有明确搜索新客户、写邮件或邮件内容注入意图时生效。
12. email_craft 的 user_requirements：当用户说"开发信里要提XX项目"、"邮件里加上XX"、"邮件中写上我们XX经验"等，action 设为 email_craft，并将具体内容整理为 user_requirements 字段（中文，简洁描述）。如"开发信里要提我们做过白云机场项目"→ user_requirements="在邮件中提到白云机场项目案例"。"""

DEFAULT_CHAT_REPLY = "好的，我是您的外贸业务助手。您可以让我帮您找客户、整理公司信息、写开发信或发送邮件。请问有什么可以帮您的？"


DOMAIN_KEYWORD_RULES = [
    {
        "terms": ["天花", "吊顶", "天花板", "ceiling"],
        "industry": "ceiling systems",
        "keywords": {
            "铝天花": "aluminum ceiling",
            "铝吊顶": "aluminum ceiling",
            "金属天花": "metal ceiling",
            "金属吊顶": "metal ceiling",
            "酒店天花": "hotel ceiling",
            "酒店吊顶": "hotel ceiling",
            "商业天花": "commercial ceiling",
            "建筑天花": "architectural ceiling",
            "天花": "ceiling",
            "吊顶": "ceiling",
        },
    },
    {
        "terms": ["轴承", "bearing"],
        "industry": "bearings",
        "keywords": {
            "滚珠轴承": "ball bearing",
            "线性轴承": "linear bearing",
            "精密轴承": "precision bearing",
            "汽车轴承": "automotive bearing",
            "轴承": "bearing",
        },
    },
]

GENERAL_KEYWORD_MAP = {
    "本土企业": "local company",
    "本土公司": "local company",
    "本地企业": "local company",
    "本地公司": "local company",
    "制造企业": "manufacturer",
    "制造商": "manufacturer",
    "生产商": "manufacturer",
    "厂家": "manufacturer",
    "供应商": "supplier",
    "分销商": "distributor",
    "批发商": "wholesaler",
    "经销商": "dealer",
    "进口商": "importer",
    "采购商": "buyer",
}


def _extract_url(text: str) -> str:
    match = re.search(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+", text or "")
    if match:
        return match.group(0).rstrip(").,;，。")
    domain_match = re.search(
        r"\b(?:www\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+\b",
        text or "",
    )
    if domain_match:
        domain = domain_match.group(0).rstrip(").,;，。")
        return domain if domain.startswith("http") else f"https://{domain}"
    return ""


def _looks_like_email_craft(message: str) -> bool:
    text = (message or "").lower()
    triggers = [
        "写开发信", "撰写开发信", "生成开发信", "开发信撰写",
        "cold email", "outreach email", "email draft", "email craft",
        "给客户写信", "跟进邮件", "批量写邮件", "定制化邮件",
        "写邮件", "生成邮件", "起草邮件", "帮我写信",
        "开发信", "写开发信给", "给客户写",
        # Content injection patterns
        "开发信里要提", "开发信里要加", "开发信里加", "开发信里写",
        "邮件里要提", "邮件里要加", "邮件里加上", "邮件里写",
        "邮件中要提", "邮件中加上", "开发信要提", "开发信中提",
        "加到开发信", "写进开发信", "加到邮件里",
    ]
    return any(trigger in text for trigger in triggers)


def _extract_email_requirements(message: str) -> str:
    """Extract user requirements for email crafting from the message.
    E.g., '开发信里要提我们公司做过白云机场项目' → '在邮件中提到我们公司做过白云机场项目'
    """
    text = (message or "").strip()
    # Remove the trigger phrase and keep the requirement
    triggers = [
        "开发信里要提", "开发信里要加上", "开发信里加", "开发信里写上",
        "邮件里要提", "邮件里要加上", "邮件里加上", "邮件里写上",
        "邮件中要提", "邮件中加上", "开发信要提", "开发信中提",
        "加到开发信里", "写进开发信里", "加到邮件里",
    ]
    for trigger in triggers:
        if trigger in text:
            # Find where the trigger ends and take everything after
            idx = text.index(trigger) + len(trigger)
            requirement = text[idx:].strip().rstrip("。，,.")
            if requirement:
                return f"在邮件中{requirement}"
            break
    return ""


def _looks_like_email_blast(message: str) -> bool:
    text = (message or "").lower()
    triggers = [
        "发邮件", "发送邮件", "发送开发信", "批量发送", "批量发邮件",
        "群发", "群发邮件", "开始发送", "把邮件发出去", "把开发信发出去",
        "email blast", "send emails", "send email", "batch send",
        "send cold emails", "blast emails",
    ]
    if any(trigger in text for trigger in triggers):
        return True
    return "发出去" in text and ("开发信" in text or "邮件" in text)


def _looks_like_view_profile(message: str) -> bool:
    text = (message or "").strip()
    text_lower = text.lower()

    # Past record lookups: "找我们做过的", "查以前的" etc. = viewing existing profile
    # No length limit — these can be longer sentences
    lookup_patterns = [
        "找我们做过", "找我们合作过", "找以前的", "找过去的",
        "找我们的案例", "找我们的项目", "查我们做过",
        "查我们合作过", "看一下我们做过", "看一下我们合作过",
        "我们合作过哪些", "我们做过哪些",
    ]
    if any(p in text_lower for p in lookup_patterns):
        return True

    # Short view requests — must be brief (longer messages with actual content are updates)
    if len(text) > 30:
        return False
    triggers = [
        "我的公司信息", "看一下公司", "查看公司", "公司信息是什么",
        "公司资料是什么", "公司简介是什么", "公司画像是什么",
        "我们公司信息", "我们公司资料", "我们的公司信息",
    ]
    if any(t in text_lower for t in triggers):
        return True
    # Single-phrase view requests (e.g., "公司画像", "公司简介", "公司资料")
    view_phrases = ["公司画像", "公司简介", "公司资料", "企业画像", "企业档案"]
    if any(text_lower == p for p in view_phrases):
        return True
    return False


def _has_search_intent(message: str) -> bool:
    """Check if the message has explicit NEW customer search intent.

    Distinguishes "找新客户" (customer acquisition) from "找我们做过的/找过去的"
    (looking up historical records, which is NOT a search action).
    """
    text = (message or "").lower()
    # "找我们做过的/找我们合作过的/找以前的/找过去的" = looking up past records, not searching
    past_record_patterns = ["找我们做过", "找我们合作过", "找以前的", "找过去的", "找我们的"]
    for p in past_record_patterns:
        if p in text:
            return False
    search_triggers = [
        "找客户", "帮我找", "搜索", "开发客户", "找公司", "找供应商",
        "找买家", "找分销商", "找制造商", "找批发商", "查找客户",
        "找一些", "找几家", "寻找客户", "搜一下",
    ]
    return any(t in text for t in search_triggers)


def _has_email_craft_intent(message: str) -> bool:
    """Check if the message's CORE intent is writing/creating emails or injecting content into emails."""
    text = (message or "").lower()
    craft_triggers = [
        "开发信怎么写", "怎么写开发信", "帮我写开发信", "帮我写邮件",
        "写开发信", "生成开发信", "写邮件", "给我写", "起草开发信",
        "帮我写", "我们要写", "定制化邮件", "批量写邮件",
        # Content injection into emails
        "开发信里要提", "开发信里要加", "开发信里加", "开发信里写",
        "邮件里要提", "邮件里要加", "邮件里加上", "邮件里写",
        "邮件中要提", "邮件中加上", "开发信要提", "开发信中提",
        "加到开发信", "写进开发信", "加到邮件里",
    ]
    return any(t in text for t in craft_triggers)


def _has_first_person_company_reference(message: str) -> bool:
    """Check if the message describes the user's own company using first-person language.

    Returns False when the core intent is clearly customer search or email writing.
    Content injection into emails (开发信里要提...) still returns True because the
    practical solution is to update the company profile.
    """
    if _has_search_intent(message) or _has_email_craft_intent(message):
        return False
    text = (message or "").lower()
    indicators = [
        "我们做过", "我们公司", "我们有", "我们的产品", "我们服务过",
        "我们参与", "我们有资质", "我们生产", "我们主营", "我们供应",
        "我们的优势", "我们的案例", "我们提供", "我们的团队",
        "我们成立于", "我们专注于", "我们拥有", "我们的客户",
    ]
    return any(ind in text for ind in indicators)


def _looks_like_company_profile(message: str) -> bool:
    text = (message or "").lower()
    triggers = [
        "公司画像",
        "企业画像",
        "公司资料",
        "企业档案",
        "公司档案",
        "公司简介",
        "公司profile",
        "company profile",
        "整理公司",
        "建立公司",
        "采集企业",
        "补充",
        "补一下",
        "补资料",
        "加上",
        "追加",
        "更新画像",
        "更新资料",
        "补充资料",
        "补充案例",
        "修改画像",
        "修正",
        "删除",
        "移除",
        "去掉",
        "剔除",
    ]
    return any(trigger.lower() in text for trigger in triggers)


def _postprocess_profile_params(params: dict, source_message: str = "") -> dict:
    if not isinstance(params, dict):
        params = {}
    params.setdefault("source_text", source_message)
    params.setdefault("url", _extract_url(source_message))
    mode = str(params.get("profile_mode") or params.get("mode") or "").strip().lower()
    if mode not in {"create", "update", "replace"}:
        mode = "create"
    params["profile_mode"] = mode
    return params


def _append_unique(values: list[str], value: str) -> None:
    normalized = value.strip()
    if normalized and normalized.lower() not in {v.lower() for v in values}:
        values.append(normalized)


def _postprocess_customer_params(params: dict, source_message: str = "") -> dict:
    """Correct common industry/keyword mix-ups after LLM or regex parsing."""
    if not isinstance(params, dict):
        return params

    industry = str(params.get("industry", "") or "").strip()
    keywords_raw = params.get("keywords", [])
    if isinstance(keywords_raw, str):
        keywords = [k.strip() for k in re.split(r"[,，、;/]+", keywords_raw) if k.strip()]
    elif isinstance(keywords_raw, list):
        keywords = [str(k).strip() for k in keywords_raw if str(k).strip()]
    else:
        keywords = []

    combined = f"{source_message} {industry} {' '.join(keywords)}"
    combined_lower = combined.lower()

    for rule in DOMAIN_KEYWORD_RULES:
        if any(term.lower() in combined_lower for term in rule["terms"]):
            industry = rule["industry"]
            translated_keywords = []
            for kw in keywords:
                translated = rule["keywords"].get(kw)
                translated_keywords.append(translated or kw)
            keywords = translated_keywords

            matched_specific = False
            for cn_term, en_term in rule["keywords"].items():
                is_generic = cn_term in rule["terms"]
                if cn_term in combined and not is_generic:
                    _append_unique(keywords, en_term)
                    matched_specific = True
            if not matched_specific:
                for cn_term, en_term in rule["keywords"].items():
                    if cn_term in combined:
                        _append_unique(keywords, en_term)
            break

    for cn_term, en_term in GENERAL_KEYWORD_MAP.items():
        if cn_term in combined:
            _append_unique(keywords, en_term)

    if industry:
        keywords = [kw for kw in keywords if kw.lower() != industry.lower()]

    params["industry"] = industry
    params["keywords"] = keywords
    return params


def _classify_intent_sync(message: str, api_token: str) -> dict | None:
    """Call Replicate API synchronously. Returns parsed dict or None on failure."""
    try:
        output = replicate.run(
            settings.replicate_model_advanced,
            input={
                "messages": [
                    {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                    {"role": "user", "content": message},
                ],
            },
        )

        if isinstance(output, list):
            response_text = "".join(output)
        else:
            response_text = str(output)

        return _parse_router_response(response_text, message)

    except Exception as e:
        logger.error("LLM intent classification failed: %s", str(e)[:300])
        return None


def _parse_router_response(response_text: str, source_message: str = "") -> dict | None:
    """Parse the LLM response into a structured dict."""
    text = response_text.strip()

    # Try markdown code block
    match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if match:
        text = match.group(1).strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        pass
    else:
        return _normalize_result(result, source_message)

    # Try to find JSON object in the text
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        try:
            result = json.loads(text[brace_start : brace_end + 1])
            return _normalize_result(result, source_message)
        except json.JSONDecodeError:
            pass

    return None


def _normalize_result(result: dict, source_message: str = "") -> dict:
    """Normalize and validate the LLM response."""
    action = result.get("action", "chat")
    # Map common action name variations
    action_map = {
        "customer_acquisition": "customer_acquisition",
        "customer-acquisition": "customer_acquisition",
        "company_profile": "company_profile",
        "company-profile": "company_profile",
        "view_profile": "view_profile",
        "view-profile": "view_profile",
        "email_craft": "email_craft",
        "email-craft": "email_craft",
        "email_blast": "email_blast",
        "email-blast": "email_blast",
        "chat": "chat",
    }
    action = action_map.get(action, "chat")

    params = result.get("params", {})
    if not isinstance(params, dict) or not params:
        # Model may put params at top level instead of nested under "params"
        top_level_keys = {"industry", "country", "keywords", "num", "url"}
        top_level = {k: v for k, v in result.items() if k in top_level_keys}
        if top_level:
            params = top_level
        else:
            params = {}

    # Ensure required fields for customer_acquisition
    if action == "customer_acquisition":
        params.setdefault("industry", params.pop("行业", ""))
        params.setdefault("country", params.pop("国家", ""))
        params.setdefault("keywords", params.pop("关键词", []))
        params.setdefault("num", params.pop("数量", 20))
        if not isinstance(params["keywords"], list):
            params["keywords"] = []
        params["num"] = int(params["num"]) if params["num"] else 20
        # Clamp num to reasonable range
        params["num"] = max(1, min(params["num"], 100))
        params = _postprocess_customer_params(params, source_message)
    elif action == "company_profile":
        params = _postprocess_profile_params(params, source_message)
        # Propagate needs_clarification flag from LLM
        if params.get("needs_clarification"):
            result["_needs_clarification"] = True
    elif action == "view_profile":
        # view_profile doesn't need params processing
        pass
    elif action == "email_craft":
        # Extract language from params
        lang = str(params.get("language") or "en").strip().lower()
        if lang in ("中文", "cn", "chinese", "zh"):
            lang = "cn"
        else:
            lang = "en"
        params["language"] = lang

        # Validate extracted_lead: only keep if company_name is present
        extracted = params.get("extracted_lead")
        if isinstance(extracted, dict) and extracted.get("company_name"):
            # Keep only known fields
            lead_fields = {
                "company_name", "website", "country", "industry",
                "company_role", "contact_name", "email", "phone",
            }
            params["extracted_lead"] = {
                k: str(v or "").strip() for k, v in extracted.items() if k in lead_fields
            }
        else:
            params.pop("extracted_lead", None)
    elif action == "email_blast":
        params["delay_min"] = int(params.get("delay_min") or params.get("delayMin") or 60)
        params["delay_max"] = int(params.get("delay_max") or params.get("delayMax") or 120)
        params["daily_limit"] = int(params.get("daily_limit") or params.get("dailyLimit") or 50)
        params["dry_run"] = False
        params["send_mode"] = str(params.get("send_mode") or params.get("sendMode") or "immediate")

    reply = result.get("reply", "")
    if not reply:
        if action == "customer_acquisition":
            country = params.get("country", "")
            industry = params.get("industry", "")
            num = params.get("num", 20)
            reply = f"好的，正在为您搜索{country}{industry}客户，目标 {num} 家..."
        elif action == "view_profile":
            reply = "好的，正在为您查看公司画像。"
        elif action == "chat":
            reply = DEFAULT_CHAT_REPLY
        else:
            reply = "好的，收到您的请求。"

    final = {
        "action": action,
        "params": params,
        "reply": reply,
    }
    if result.get("_needs_clarification"):
        final["needs_clarification"] = True
    return final


async def classify_intent(message: str) -> dict:
    """Classify user intent using LLM, with regex fallback.

    Returns dict with keys: action, params, reply
    """
    if settings.replicate_api_token:
        try:
            result = await asyncio.to_thread(
                _classify_intent_sync, message, settings.replicate_api_token
            )
            if result is not None:
                logger.info(
                    "LLM intent: action=%s, params=%s",
                    result["action"], result["params"],
                )
                return result
        except Exception as e:
            logger.warning("LLM intent classification error, falling back to regex: %s", e)

    if _looks_like_view_profile(message):
        logger.info("Regex fallback intent: view_profile")
        return {
            "action": "view_profile",
            "params": {},
            "reply": "好的，正在为您查看公司画像。",
        }

    if _has_first_person_company_reference(message):
        # User is describing their own company — treat as profile update
        params = _postprocess_profile_params({"profile_mode": "update"}, message)
        logger.info("Regex fallback intent: company_profile (first-person) params=%s", params)
        return {
            "action": "company_profile",
            "params": params,
            "reply": "好的，我来为您更新公司画像。",
        }

    if _looks_like_company_profile(message):
        params = _postprocess_profile_params({}, message)
        logger.info("Regex fallback intent: company_profile params=%s", params)
        return {
            "action": "company_profile",
            "params": params,
            "reply": "好的，我来为您采集并整理公司画像。",
        }

    if _looks_like_email_blast(message):
        logger.info("Regex fallback intent: email_blast")
        return {
            "action": "email_blast",
            "params": {
                "delay_min": 60,
                "delay_max": 120,
                "daily_limit": 50,
                "dry_run": False,
                "send_mode": "immediate",
            },
            "reply": "好的，我来帮您发送开发信。请先选择要发送的客户。",
        }

    if _looks_like_email_craft(message):
        logger.info("Regex fallback intent: email_craft")
        # Detect language from message
        lang = "en"
        cn_lang_hints = ["中文", "中文邮件", "中文开发信", "用中文"]
        if any(hint in message for hint in cn_lang_hints):
            lang = "cn"
        params: dict = {"language": lang}
        # Extract user requirements (e.g., "开发信里要提白云机场项目")
        user_req = _extract_email_requirements(message)
        if user_req:
            params["user_requirements"] = user_req
        return {
            "action": "email_craft",
            "params": params,
            "reply": "好的，我来为您生成定制化开发信。",
        }

    # Fallback to regex parser
    from app.services.intent_parser import parse_search_intent

    params = parse_search_intent(message)
    params = _postprocess_customer_params(params, message)
    logger.info("Regex fallback intent: params=%s", params)
    return {
        "action": "customer_acquisition",
        "params": params,
        "reply": f"好的，正在为您搜索{params.get('country', '')}的{params.get('industry', '')}客户，目标 {params.get('num', 20)} 家...",
    }
