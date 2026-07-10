CARD_GROUP_STYLE = """
QGroupBox {
    font-weight: 700;
    font-size: 13px;
    margin-top: 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
"""

CONTENT_OVERVIEW_EMPTY = "Přehled obsahu není k dispozici."


def apply_card_group_style(group) -> None:
    group.setStyleSheet(CARD_GROUP_STYLE)
