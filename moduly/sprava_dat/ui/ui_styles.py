"""Společné styly pro Správu dat a další moduly."""

# Výchozí text aplikace je 14px (core/theme/app_style.py).
SECTION_HEADING_BASE_FONT_SIZE_PX = 14
SECTION_HEADING_FONT_SIZE_PX = SECTION_HEADING_BASE_FONT_SIZE_PX + 3
SECTION_HEADING_MARGIN_TOP_PX = 10
SECTION_HEADING_TITLE_LEFT_PX = 10
SECTION_HEADING_TITLE_PADDING_PX = 6

CARD_GROUP_STYLE = f"""
QGroupBox {{
    font-weight: 700;
    font-size: {SECTION_HEADING_FONT_SIZE_PX}px;
    margin-top: {SECTION_HEADING_MARGIN_TOP_PX}px;
    padding-top: {SECTION_HEADING_MARGIN_TOP_PX}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: {SECTION_HEADING_TITLE_LEFT_PX}px;
    padding: 0 {SECTION_HEADING_TITLE_PADDING_PX}px;
}}
"""

CONTENT_OVERVIEW_EMPTY = "Přehled obsahu není k dispozici."


def apply_card_group_style(group) -> None:
    """Aplikuje jednotný styl hlavního nadpisu sekce (QGroupBox)."""
    group.setStyleSheet(CARD_GROUP_STYLE)
