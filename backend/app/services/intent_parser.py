"""Parse user message into structured search intent.

Extracts industry, country, keywords, and num from natural language input.
Uses regex-based matching (Part B will replace with LLM intent recognition).
"""

import re

# Chinese digit map
_CN_DIGITS: dict[str, int] = {
    "零": 0, "一": 1, "壹": 1, "二": 2, "贰": 2, "两": 2,
    "三": 3, "叁": 3, "四": 4, "肆": 4, "五": 5, "伍": 5,
    "六": 6, "陆": 6, "七": 7, "柒": 7, "八": 8, "捌": 8,
    "九": 9, "玖": 9, "十": 10, "拾": 10,
}


def _chinese_to_number(text: str) -> int | None:
    """Convert Chinese number text to integer. Returns None if not a number.

    Supports: 一/二/三/.../九/十, 两, 一十/二十/三十, 一十一/二十一, etc.
    """
    text = text.strip()
    if not text:
        return None

    result = 0
    current = 0
    for ch in text:
        if ch not in _CN_DIGITS:
            return None
        val = _CN_DIGITS[ch]
        if val == 10:
            # "十" acts as multiplier for the preceding digit
            if current == 0:
                current = 1  # bare "十" = 10
            result += current * 10
            current = 0
        else:
            current = val

    result += current
    return result if result > 0 else None

# Country mappings: Chinese name → English
COUNTRY_MAP: dict[str, str] = {
    "美国": "USA",
    "加拿大": "Canada",
    "墨西哥": "Mexico",
    "巴西": "Brazil",
    "阿根廷": "Argentina",
    "英国": "UK",
    "法国": "France",
    "德国": "Germany",
    "意大利": "Italy",
    "西班牙": "Spain",
    "荷兰": "Netherlands",
    "比利时": "Belgium",
    "瑞士": "Switzerland",
    "奥地利": "Austria",
    "波兰": "Poland",
    "瑞典": "Sweden",
    "挪威": "Norway",
    "丹麦": "Denmark",
    "芬兰": "Finland",
    "俄罗斯": "Russia",
    "土耳其": "Turkey",
    "阿联酋": "UAE",
    "沙特": "Saudi Arabia",
    "沙特阿拉伯": "Saudi Arabia",
    "印度": "India",
    "日本": "Japan",
    "韩国": "South Korea",
    "泰国": "Thailand",
    "越南": "Vietnam",
    "马来西亚": "Malaysia",
    "印度尼西亚": "Indonesia",
    "菲律宾": "Philippines",
    "新加坡": "Singapore",
    "澳大利亚": "Australia",
    "新西兰": "New Zealand",
    "南非": "South Africa",
    "尼日利亚": "Nigeria",
    "埃及": "Egypt",
    "肯尼亚": "Kenya",
    "以色列": "Israel",
}

# English country names (direct lookup)
ENGLISH_COUNTRIES: dict[str, str] = {
    "USA": "USA",
    "US": "USA",
    "United States": "USA",
    "United States of America": "USA",
    "UK": "UK",
    "United Kingdom": "UK",
    "Great Britain": "UK",
    "Germany": "Germany",
    "France": "France",
    "Italy": "Italy",
    "Spain": "Spain",
    "Netherlands": "Netherlands",
    "Belgium": "Belgium",
    "Switzerland": "Switzerland",
    "Austria": "Austria",
    "Poland": "Poland",
    "Sweden": "Sweden",
    "Norway": "Norway",
    "Denmark": "Denmark",
    "Finland": "Finland",
    "Russia": "Russia",
    "Turkey": "Turkey",
    "UAE": "UAE",
    "Saudi Arabia": "Saudi Arabia",
    "India": "India",
    "Japan": "Japan",
    "South Korea": "South Korea",
    "Korea": "South Korea",
    "Thailand": "Thailand",
    "Vietnam": "Vietnam",
    "Malaysia": "Malaysia",
    "Indonesia": "Indonesia",
    "Philippines": "Philippines",
    "Singapore": "Singapore",
    "Australia": "Australia",
    "New Zealand": "New Zealand",
    "South Africa": "South Africa",
    "Nigeria": "Nigeria",
    "Egypt": "Egypt",
    "Kenya": "Kenya",
    "Israel": "Israel",
    "Brazil": "Brazil",
    "Argentina": "Argentina",
    "Mexico": "Mexico",
    "Canada": "Canada",
}

# Keyword mappings: Chinese → English
KEYWORD_MAP: dict[str, str] = {
    "批发商": "wholesale",
    "批发": "wholesale",
    "分销商": "distributor",
    "分销": "distributor",
    "供应商": "supplier",
    "供应": "supplier",
    "制造商": "manufacturer",
    "制造": "manufacturer",
    "进口商": "importer",
    "进口": "importer",
    "采购商": "buyer",
    "采购": "buyer",
    "代理商": "agent",
    "代理": "agent",
    "零售商": "retailer",
    "零售": "retailer",
    "经销商": "dealer",
    "经销商": "dealer",
    "贸易商": "trader",
    "贸易": "trader",
}


def parse_search_intent(message: str) -> dict:
    """Extract {industry, country, keywords, num} from a user message.

    Strategy:
    1. Match and remove country names (Chinese/English)
    2. Match and remove keyword terms
    3. Remaining text becomes the industry
    4. Default num to 20
    """
    text = message.strip()
    found_country = ""
    found_keywords: list[str] = []

    # 1. Try Chinese country names first (longest match first)
    sorted_countries = sorted(COUNTRY_MAP.keys(), key=len, reverse=True)
    for cn_name in sorted_countries:
        if cn_name in text:
            found_country = COUNTRY_MAP[cn_name]
            text = text.replace(cn_name, "", 1)
            break

    # 2. Try English country names (longest match first)
    if not found_country:
        sorted_en = sorted(ENGLISH_COUNTRIES.keys(), key=len, reverse=True)
        for en_name in sorted_en:
            pattern = re.compile(rf"\b{re.escape(en_name)}\b", re.I)
            if pattern.search(text):
                found_country = ENGLISH_COUNTRIES[en_name]
                text = pattern.sub("", text, count=1)
                break

    # 3. Extract keywords (Chinese)
    sorted_keywords = sorted(KEYWORD_MAP.keys(), key=len, reverse=True)
    for cn_kw in sorted_keywords:
        if cn_kw in text:
            found_keywords.append(KEYWORD_MAP[cn_kw])
            text = text.replace(cn_kw, "", 1)

    # 4. Extract English keywords (handle plurals)
    en_kw_patterns = [
        (r"\bwholesalers?\b", "wholesale"),
        (r"\bdistributors?\b", "distributor"),
        (r"\bsuppliers?\b", "supplier"),
        (r"\bmanufacturers?\b", "manufacturer"),
        (r"\bimporter\b", "importer"),
        (r"\bbuyer\b", "buyer"),
        (r"\bagent\b", "agent"),
        (r"\bretailer\b", "retailer"),
        (r"\bdealer\b", "dealer"),
        (r"\btrader\b", "trader"),
    ]
    for pattern, kw in en_kw_patterns:
        if re.search(pattern, text, re.I):
            found_keywords.append(kw)
            text = re.sub(pattern, "", text, count=1, flags=re.I)

    # 5. Extract number (before cleaning fillers)
    num_match = re.search(r"(\d+)\s*(?:家|个|公司|companies?)", message, re.I)
    if num_match:
        num = int(num_match.group(1))
    else:
        num = 20

    # 6. Clean up remaining text → industry
    # Remove common filler words
    fillers = [
        r"\d+\s*(?:家|个|公司|companies?)",
        r"[零一二两三四五六七八九十壹贰叁肆伍陆柒捌玖拾]+\s*(?:家|个|公司)",
        r"帮我", r"找", r"搜索", r"搜", r"查找", r"寻找",
        r"的", r"一些", r"几个", r"一下",
        r"find", r"search", r"look for", r"get me",
        r"please", r"want", r"need", r"some",
        r"companies?", r"business(?:es)?",
        r"\bin\b", r"\bfor\b", r"\bin the\b",
    ]
    for filler in fillers:
        text = re.sub(filler, "", text, flags=re.I)

    # Clean up whitespace and punctuation
    text = re.sub(r"[，。、！？,.\-!?\s]+", " ", text).strip()

    industry = text if text else "electronics"

    # 6. Deduplicate keywords
    seen = set()
    unique_keywords: list[str] = []
    for kw in found_keywords:
        if kw.lower() not in seen:
            seen.add(kw.lower())
            unique_keywords.append(kw)

    # 7. Extract number if mentioned
    # Try Arabic digits first: "3家", "20 companies"
    num_match = re.search(r"(\d+)\s*(?:家|个|公司|companies?)", message, re.I)
    if num_match:
        num = int(num_match.group(1))
    else:
        # Try Chinese number words: "三家", "二十家", "十家"
        cn_match = re.search(
            r"([零一二两三四五六七八九十壹贰叁肆伍陆柒捌玖拾]+)\s*(?:家|个|公司)",
            message,
        )
        if cn_match:
            parsed = _chinese_to_number(cn_match.group(1))
            num = parsed if parsed else 20
        else:
            # Fallback: any bare digit in the message
            num_match = re.search(r"(\d+)", message)
            num = int(num_match.group(1)) if num_match else 20

    return {
        "industry": industry,
        "country": found_country,
        "keywords": unique_keywords,
        "num": num,
    }
