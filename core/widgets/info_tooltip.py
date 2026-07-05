import textwrap
from typing import Protocol

DEFAULT_TOOLTIP_MAX_WIDTH = 60


class _SupportsToolTip(Protocol):
    def setToolTip(self, text: str) -> None: ...


def wrap_tooltip_text(text: str, max_width: int = DEFAULT_TOOLTIP_MAX_WIDTH) -> str:
    if not text:
        return ""

    lines: list[str] = []
    for paragraph in text.split("\n"):
        stripped = paragraph.rstrip()
        if not stripped:
            lines.append("")
            continue

        if len(stripped) <= max_width:
            lines.append(stripped)
            continue

        lines.extend(
            textwrap.wrap(
                stripped,
                width=max_width,
                break_long_words=True,
                break_on_hyphens=True,
            )
        )

    return "\n".join(lines)


def _format_row(label: str, value: str, max_width: int) -> str:
    value = value or "—"
    label_prefix = f"{label:<16} "
    value_width = max(20, max_width - len(label_prefix))

    wrapped_value = textwrap.wrap(
        value,
        width=value_width,
        break_long_words=True,
        break_on_hyphens=True,
    )
    if not wrapped_value:
        return f"{label_prefix}—"

    lines = [f"{label_prefix}{wrapped_value[0]}"]
    indent = " " * len(label_prefix)
    lines.extend(f"{indent}{part}" for part in wrapped_value[1:])
    return "\n".join(lines)


def format_info_card(
    title: str,
    rows: list[tuple[str, str]],
    note: str = "",
    max_width: int = DEFAULT_TOOLTIP_MAX_WIDTH,
) -> str:
    """
    Jednotná textová informační karta pro tooltipy.
    Dlouhé texty se zalamují na více řádků.
    """

    parts = [wrap_tooltip_text(title, max_width), "─" * min(max_width, 42)]

    for label, value in rows:
        parts.append(_format_row(label, value, max_width))

    if note:
        parts.extend(["", "Poznámka:", wrap_tooltip_text(note, max_width)])

    return "\n".join(parts)


def set_widget_tooltip(
    widget: _SupportsToolTip,
    text: str,
    max_width: int = DEFAULT_TOOLTIP_MAX_WIDTH,
) -> None:
    widget.setToolTip(wrap_tooltip_text(text, max_width))
