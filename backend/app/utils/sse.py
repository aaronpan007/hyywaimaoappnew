import json


def sse_format(event: str, data: dict | None = None) -> str:
    lines = [f"event: {event}"]
    if data is not None:
        lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    lines.append("")
    lines.append("")
    return "\n".join(lines)
