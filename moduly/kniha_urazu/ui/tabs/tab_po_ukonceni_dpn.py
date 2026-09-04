from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from moduly.kniha_urazu.sluzby.accident_reporting_obligations import is_dpn_ended


TAB_PO_UKONCENI_DPN = "Po ukončení DPN"

DPN_NOT_ENDED_MESSAGE = (
    "DPN dosud nebyla ukončena. Povinnosti po ukončení DPN zatím nejsou aktivní."
)

SECTION_AKTUALIZACE_ZAZNAMU = "Aktualizace záznamu o pracovním úrazu"
SECTION_PECE_NAVRA = "Péče a návrat do práce"
SECTION_MIRA_ODPOVEDNOSTI = "Míra odpovědnosti zaměstnavatele"

SECTION_TITLES = (
    SECTION_AKTUALIZACE_ZAZNAMU,
    SECTION_PECE_NAVRA,
    SECTION_MIRA_ODPOVEDNOSTI,
)

SECTION_PLACEHOLDER = "Obsah této sekce bude doplněn v dalších krocích."


class TabPoUkonceniDpn(QWidget):
    """Poslední záložka spisu úrazu – základ fáze po ukončení DPN."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        self.info_panel = QFrame()
        self.info_panel.setStyleSheet(
            "QFrame { background: #f4f4f4; border: 1px solid #d0d0d0; border-radius: 6px; }"
        )
        info_layout = QVBoxLayout(self.info_panel)
        info_layout.setContentsMargins(10, 8, 10, 8)

        self.info_label = QLabel(DPN_NOT_ENDED_MESSAGE)
        self.info_label.setObjectName("InfoText")
        self.info_label.setWordWrap(True)
        info_layout.addWidget(self.info_label)

        self.sections_widget = QWidget()
        sections_layout = QVBoxLayout(self.sections_widget)
        sections_layout.setContentsMargins(0, 0, 0, 0)
        sections_layout.setSpacing(10)

        self.section_groups: list[QGroupBox] = []
        for title in SECTION_TITLES:
            group = QGroupBox(title)
            group_layout = QVBoxLayout(group)
            placeholder = QLabel(SECTION_PLACEHOLDER)
            placeholder.setObjectName("MutedText")
            placeholder.setWordWrap(True)
            group_layout.addWidget(placeholder)
            self.section_groups.append(group)
            sections_layout.addWidget(group)

        layout.addWidget(self.info_panel)
        layout.addWidget(self.sections_widget)
        layout.addStretch()

        self._dpn_ended = False
        self.set_dpn_ended(False)

    def set_dpn_ended(self, ended: bool) -> None:
        self._dpn_ended = bool(ended)
        self.info_panel.setVisible(not self._dpn_ended)
        self.sections_widget.setVisible(self._dpn_ended)
        self.sections_widget.setEnabled(self._dpn_ended)

    def set_from_dpn_do(self, dpn_do) -> None:
        self.set_dpn_ended(is_dpn_ended(dpn_do))

    def is_content_active(self) -> bool:
        return self._dpn_ended
