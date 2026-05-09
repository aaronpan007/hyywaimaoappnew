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
- customer_acquisition: 用户要找客户/公司/供应商/分销商/批发商/制造商
- company_profile: 用户要整理公司信息/公司画像/公司简介/公司资料
- email_craft: 用户要写开发信/生成邮件内容/起草邮件/为具体客户定制邮件（重点是"写/生成/起草"，尚未发送）
- email_blast: 用户要发送开发信/发邮件/批量发邮件/群发邮件/把邮件发出去（重点是"发送/发出去"，触发实际发送动作）
- chat: 闲聊、提问、其他不属于以上动作的对话

重要区分规则：
- "写开发信"、"生成开发信"、"帮我写邮件" → email_craft（写/生成/起草）
- "发邮件"、"发送开发信"、"发开发信"、"把邮件发出去" → email_blast（发送/发出去）
- 如果用户说"发邮件"，核心动作是发送，应识别为 email_blast 而不是 email_craft
- "开发信"搭配"写/生成/起草"时是 email_craft，搭配"发/发送/群发/批量发"时是 email_blast

返回格式（严格按照此 JSON 结构）：
{
  "action": "动作名称",
  "params": {
    "industry": "宽泛行业/产品大类（英文，如 LED lighting, solar panel, ceiling systems, bearings）",
    "country": "目标国家（英文，如 USA, Germany）",
    "keywords": ["搜索细分词或客户类型关键词1", "搜索细分词或客户类型关键词2"],
    "num": 数量（整数，默认20）,
    "url": "公司网站 URL（仅 company_profile 需要）",
    "profile_mode": "create | update | replace（仅 company_profile 需要）"
  },
  "reply": "一句简短的中文确认回复"
}
- num: 数量（整数，默认 20）
- url: 公司网站 URL（仅 company_profile 需要）
- profile_mode: 仅 company_profile 使用。create=首次建立画像；update=在已有画像上补充/修正/追加/删除资料；replace=用户明确要求重新采集、从头生成、覆盖旧画像。
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
    如果用户没有提到任何具体客户信息，不要加 extracted_lead。只有明确出现公司名时才添加。"""

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
    ]
    return any(trigger in text for trigger in triggers)


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
            settings.replicate_model,
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
        elif action == "chat":
            reply = DEFAULT_CHAT_REPLY
        else:
            reply = "好的，收到您的请求。"

    return {
        "action": action,
        "params": params,
        "reply": reply,
    }


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
        return {
            "action": "email_craft",
            "params": {"language": lang},
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
