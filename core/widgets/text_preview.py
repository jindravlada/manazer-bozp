DEFAULT_TEXT_PREVIEW_LENGTH = 100
TEXT_PREVIEW_SUFFIX = "..."


def truncate_text_preview(
    text: str,
    *,
    max_length: int = DEFAULT_TEXT_PREVIEW_LENGTH,
    suffix: str = TEXT_PREVIEW_SUFFIX,
) -> str:
    normalized = " ".join((text or "").split())
    if not normalized:
        return ""
    if len(normalized) <= max_length:
        return normalized
    return f"{normalized[:max_length]}{suffix}"
