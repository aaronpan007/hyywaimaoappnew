"""Timezone-aware sending window logic."""

from datetime import datetime, timezone, timedelta
import re


# Country/region to UTC offset mapping (approximate, using standard time)
# For daylight saving, we use the more common offset
COUNTRY_TIMEZONES = {
    # North America
    "united states": -5, "us": -5, "usa": -5, "美国": -5,
    "canada": -5, "加拿大": -5,
    "mexico": -6, "墨西哥": -6,

    # South America
    "brazil": -3, "巴西": -3,
    "argentina": -3, "阿根廷": -3,
    "chile": -4, "智利": -4,
    "colombia": -5, "哥伦比亚": -5,
    "peru": -5, "秘鲁": -5,

    # Europe
    "united kingdom": 0, "uk": 0, "英国": 0,
    "germany": 1, "deutschland": 1, "德国": 1,
    "france": 1, "法国": 1,
    "italy": 1, "意大利": 1,
    "spain": 1, "西班牙": 1,
    "netherlands": 1, "荷兰": 1,
    "belgium": 1, "比利时": 1,
    "switzerland": 1, "瑞士": 1,
    "austria": 1, "奥地利": 1,
    "sweden": 1, "瑞典": 1,
    "norway": 1, "挪威": 1,
    "denmark": 1, "丹麦": 1,
    "finland": 2, "芬兰": 2,
    "poland": 1, "波兰": 1,
    "ireland": 0, "爱尔兰": 0,
    "portugal": 0, "葡萄牙": 0,
    "russia": 3, "俄罗斯": 3,

    # Asia
    "china": 8, "中国": 8, "中国大陆": 8,
    "japan": 9, "日本": 9,
    "south korea": 9, "korea": 9, "韩国": 9,
    "india": 5.5, "印度": 5.5,
    "singapore": 8, "新加坡": 8,
    "thailand": 7, "泰国": 7,
    "vietnam": 7, "越南": 7,
    "malaysia": 8, "马来西亚": 8,
    "indonesia": 7, "印尼": 7, "印度尼西亚": 7,
    "philippines": 8, "菲律宾": 8,
    "taiwan": 8, "台湾": 8,
    "hong kong": 8, "香港": 8,

    # Middle East
    "uae": 4, "united arab emirates": 4, "阿联酋": 4,
    "saudi arabia": 3, "沙特": 3, "沙特阿拉伯": 3,
    "israel": 2, "以色列": 2,
    "turkey": 3, "土耳其": 3,

    # Oceania
    "australia": 10, "澳大利亚": 10, "澳洲": 10,
    "new zealand": 12, "新西兰": 12,

    # Africa
    "south africa": 2, "南非": 2,
    "nigeria": 1, "尼日利亚": 1,
    "egypt": 2, "埃及": 2,
    "kenya": 3, "肯尼亚": 3,
}

# Default UTC offset for unknown countries
DEFAULT_OFFSET = 0


def get_utc_offset(country_str):
    """Get UTC offset for a country string.

    Handles fuzzy matching: the country string can contain extra text
    (e.g., "United States (CA)" or "US-Texas").
    """
    if not country_str:
        return DEFAULT_OFFSET

    country_lower = country_str.strip().lower()

    # Try exact match first
    if country_lower in COUNTRY_TIMEZONES:
        return COUNTRY_TIMEZONES[country_lower]

    # Try substring match (e.g., "United States (CA)" contains "united states")
    for key, offset in COUNTRY_TIMEZONES.items():
        if key in country_lower or country_lower in key:
            return offset

    # Try matching individual words
    words = re.findall(r'\w+', country_lower)
    for word in words:
        if word in COUNTRY_TIMEZONES:
            return COUNTRY_TIMEZONES[word]

    return DEFAULT_OFFSET


def get_local_hour(country_str):
    """Get the current local hour (0-23) for a given country."""
    utc_now = datetime.now(timezone.utc)
    offset_hours = get_utc_offset(country_str)
    local_time = utc_now + timedelta(hours=offset_hours)
    return local_time.hour


def get_local_time(country_str):
    """Get the current local time string for a given country."""
    utc_now = datetime.now(timezone.utc)
    offset_hours = get_utc_offset(country_str)
    local_time = utc_now + timedelta(hours=offset_hours)
    return local_time.strftime("%Y-%m-%d %H:%M")


def is_working_hours(country_str):
    """Check if it's working hours (9:00-17:00) in the given country."""
    hour = get_local_hour(country_str)
    return 9 <= hour < 17


def is_working_day(country_str):
    """Check if it's a working day (Mon-Fri) in the given country.

    Note: This uses UTC to determine the day, which may be off by one
    near midnight in timezones far from UTC. Good enough for email scheduling.
    """
    utc_now = datetime.now(timezone.utc)
    offset_hours = get_utc_offset(country_str)
    local_time = utc_now + timedelta(hours=offset_hours)
    return local_time.weekday() < 5  # Mon=0, Sun=6


def should_send_now(country_str):
    """Determine if we should send an email now based on timezone.

    Returns:
        (bool, str): (should_send, reason)
    """
    if not country_str or country_str.strip() in ("", "未知", "N/A", "n/a"):
        # Unknown country: send immediately
        return True, "国家未知，立即发送"

    if not is_working_day(country_str):
        local_time = get_local_time(country_str)
        return False, f"非工作日 (当地时间 {local_time})"

    if not is_working_hours(country_str):
        hour = get_local_hour(country_str)
        local_time = get_local_time(country_str)
        if hour < 9:
            return False, f"当地时间过早 {local_time} (建议 9:00 后发送)"
        else:
            return False, f"当地时间过晚 {local_time} (建议 17:00 前发送)"

    return True, f"工作时间 (当地时间 {get_local_time(country_str)})"


def get_best_send_time(country_str):
    """Get the next best send time for a given country.

    Returns a string describing when to send.
    """
    if not country_str or country_str.strip() in ("", "未知", "N/A", "n/a"):
        return "立即发送（国家未知）"

    if is_working_day(country_str) and is_working_hours(country_str):
        return f"现在 (当地时间 {get_local_time(country_str)})"

    utc_now = datetime.now(timezone.utc)
    offset_hours = get_utc_offset(country_str)

    # Find next Monday 9:00 local time
    local_time = utc_now + timedelta(hours=offset_hours)
    days_until_monday = (7 - local_time.weekday()) % 7
    if days_until_monday == 0 and not is_working_day(country_str):
        days_until_monday = 7

    # Calculate next working day 9:00 AM local
    next_send = local_time.replace(hour=9, minute=0, second=0, microsecond=0)
    next_send += timedelta(days=days_until_monday)

    return f"下次工作日 {next_send.strftime('%A %H:%M')} 当地时间"
