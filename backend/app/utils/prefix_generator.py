import re

from pypinyin import slug as pypinyin_slug


def _has_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _to_pinyin(text: str) -> str:
    """Convert Chinese characters to pinyin, keep non-Chinese as-is."""
    return pypinyin_slug(text, separator="")


def generate_prefixes(company_name: str) -> list[str]:
    """Generate email prefix suggestions from company name.

    Chinese characters are converted to pinyin via pypinyin.
    English/numeric parts are preserved as-is.
    """
    cleaned = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "", company_name)
    prefixes = set()

    if not cleaned:
        return ["prefix"]

    if _has_chinese(cleaned):
        pinyin_full = _to_pinyin(cleaned).lower()
        prefixes.add(pinyin_full)

        pinyin_parts = pypinyin_slug(cleaned, separator=".").lower()
        # Filter out single-char segments from pypinyin (e.g. "P.R.A.N.C.E")
        if not all(len(seg) == 1 and seg.isalpha() for seg in pinyin_parts.split(".")):
            prefixes.add(pinyin_parts)

        pinyin_underscore = pypinyin_slug(cleaned, separator="_").lower()
        if not all(len(seg) == 1 and seg.isalpha() for seg in pinyin_underscore.split("_")):
            prefixes.add(pinyin_underscore)

        # Also add English-only parts (if any mixed content)
        english_parts = re.sub(r"[\u4e00-\u9fff]", "", cleaned)
        if english_parts and len(english_parts) >= 2:
            prefixes.add(english_parts.lower())
            # Split by uppercase boundaries only if mixed case (camelCase), not all-caps
            if re.search(r"[a-z]", english_parts):
                words = re.split(r"(?=[A-Z])", english_parts)
                words = [w.lower() for w in words if w]
                if len(words) > 1:
                    prefixes.add(".".join(words))
    else:
        lower = cleaned.lower()
        prefixes.add(lower)

        parts = re.split(r"(?=[A-Z])", cleaned)
        parts = [p for p in parts if p]
        if len(parts) > 1:
            prefixes.add("".join(parts).lower())
            prefixes.add("_".join(parts).lower())
            prefixes.add(".".join(parts).lower())

        words = re.split(r"(?=[A-Z])", cleaned)
        words = [w.lower() for w in words if w]
        if len(words) > 1:
            for word in words:
                if len(word) >= 3:
                    prefixes.add(word)

    return sorted(prefixes)[:5] if prefixes else [cleaned.lower()]
