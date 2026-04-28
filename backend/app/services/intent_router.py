"""LLM-based intent router: classify user messages into pipeline actions.

Uses Replicate API (openai/gpt-5.2) to understand user intent and extract
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
- email_craft: 用户要写开发信/生成邮件/起草邮件
- email_blast: 用户要发送开发信/批量发邮件/群发邮件
- chat: 闲聊、提问、其他不属于以上动作的对话

返回格式（严格按照此 JSON 结构）：
{
  "action": "动作名称",
  "params": {
    "industry": "行业/产品类型（英文，如 LED, solar panel）",
    "country": "目标国家（英文，如 USA, Germany）",
    "keywords": ["关键词1", "关键词2"],
    "num": 数量（整数，默认20）
  },
  "reply": "一句简短的中文确认回复"
}
- num: 数量（整数，默认 20）
- url: 公司网站 URL（仅 company_profile 需要）
- reply: 一句简短的确认回复（中文，如"好的，正在为您搜索..."）

规则：
1. 中文数字（三、五、十）要转为阿拉伯数字
2. 中文行业名/国家名要转为英文
3. 如果用户消息不明确属于任何动作，设为 chat
4. reply 要简短自然，像是助手的确认回复
5. 只返回 JSON，不要附加其他文字
6. customer_acquisition 的 params 必须包含 industry, country, keywords, num"""

DEFAULT_CHAT_REPLY = "好的，我是您的外贸业务助手。您可以让我帮您找客户、整理公司信息、写开发信或发送邮件。请问有什么可以帮您的？"


def _classify_intent_sync(message: str, api_token: str) -> dict | None:
    """Call Replicate API synchronously. Returns parsed dict or None on failure."""
    try:
        output = replicate.run(
            "openai/gpt-5.2",
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

        return _parse_router_response(response_text)

    except Exception as e:
        logger.error("LLM intent classification failed: %s", str(e)[:300])
        return None


def _parse_router_response(response_text: str) -> dict | None:
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
        return _normalize_result(result)

    # Try to find JSON object in the text
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        try:
            result = json.loads(text[brace_start : brace_end + 1])
            return _normalize_result(result)
        except json.JSONDecodeError:
            pass

    return None


def _normalize_result(result: dict) -> dict:
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

    # Fallback to regex parser
    from app.services.intent_parser import parse_search_intent

    params = parse_search_intent(message)
    logger.info("Regex fallback intent: params=%s", params)
    return {
        "action": "customer_acquisition",
        "params": params,
        "reply": f"好的，正在为您搜索{params.get('country', '')}的{params.get('industry', '')}客户，目标 {params.get('num', 20)} 家...",
    }
