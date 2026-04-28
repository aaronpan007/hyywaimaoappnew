import re


def generate_prefixes(company_name: str) -> list[str]:
    """Generate email prefix suggestions from company name.

    Phase 1 simple version — strip special chars, lowercase.
    Phase 2 TODO: add pypinyin for Chinese company names.
    """
    cleaned = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]", "", company_name)
    prefixes = set()

    if cleaned:
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

    return sorted(prefixes)[:5] if prefixes else [cleaned.lower() if cleaned else "prefix"]
