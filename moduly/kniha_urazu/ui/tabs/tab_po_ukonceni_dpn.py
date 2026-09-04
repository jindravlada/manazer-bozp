from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
    DPN_RECORD_UPDATE_PORTAL_DATE,
    DPN_RECORD_UPDATE_PORTAL_DONE,
    DPN_RECORD_UPDATE_SIGNED_DATE,
    DPN_RECORD_UPDATE_SIGNED_DONE,
    empty_dpn_record_update,
    is_dpn_ended,
    normalize_dpn_record_update,
    parse_saved_date,
)


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
        update_group = self._build_zou_update_section()
        self.section_groups.append(update_group)
        sections_layout.addWidget(update_group)

        for title in (SECTION_PECE_NAVRA, SECTION_MIRA_ODPOVEDNOSTI):
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

    def _build_zou_update_section(self) -> QGroupBox:
        group = QGroupBox(SECTION_AKTUALIZACE_ZAZNAMU)
        form = QFormLayout(group)

        self.portal_suip_done = QCheckBox("provedeno")
        self.portal_suip_date = NullableDateEdit()
        portal_row = QWidget()
        portal_layout = QHBoxLayout(portal_row)
        portal_layout.setContentsMargins(0, 0, 0, 0)
        portal_layout.setSpacing(8)
        portal_layout.addWidget(self.portal_suip_done)
        portal_layout.addWidget(QLabel("datum provedení:"))
        portal_layout.addWidget(self.portal_suip_date, 1)

        self.signed_record_done = QCheckBox("zajištěn")
        self.signed_record_date = NullableDateEdit()
        signed_row = QWidget()
        signed_layout = QHBoxLayout(signed_row)
        signed_layout.setContentsMargins(0, 0, 0, 0)
        signed_layout.setSpacing(8)
        signed_layout.addWidget(self.signed_record_done)
        signed_layout.addWidget(QLabel("datum:"))
        signed_layout.addWidget(self.signed_record_date, 1)

        form.addRow("Aktualizace na Portálu SÚIP:", portal_row)
        form.addRow("Podepsaný aktualizovaný záznam:", signed_row)
        return group

    def set_dpn_ended(self, ended: bool) -> None:
        self._dpn_ended = bool(ended)
        self.info_panel.setVisible(not self._dpn_ended)
        self.sections_widget.setVisible(self._dpn_ended)
        self.sections_widget.setEnabled(self._dpn_ended)

    def set_from_dpn_do(self, dpn_do) -> None:
        self.set_dpn_ended(is_dpn_ended(dpn_do))

    def is_content_active(self) -> bool:
        return self._dpn_ended

    def get_dpn_record_update(self) -> dict:
        return normalize_dpn_record_update(
            {
                DPN_RECORD_UPDATE_PORTAL_DONE: self.portal_suip_done.isChecked(),
                DPN_RECORD_UPDATE_PORTAL_DATE: self.portal_suip_date.get_date(),
                DPN_RECORD_UPDATE_SIGNED_DONE: self.signed_record_done.isChecked(),
                DPN_RECORD_UPDATE_SIGNED_DATE: self.signed_record_date.get_date(),
            }
        )

    def load_dpn_record_update(self, state: dict | None) -> None:
        data = normalize_dpn_record_update(state) if state else empty_dpn_record_update()
        self.portal_suip_done.setChecked(bool(data[DPN_RECORD_UPDATE_PORTAL_DONE]))
        self.portal_suip_date.set_date_value(parse_saved_date(data[DPN_RECORD_UPDATE_PORTAL_DATE]))
        self.signed_record_done.setChecked(bool(data[DPN_RECORD_UPDATE_SIGNED_DONE]))
        self.signed_record_date.set_date_value(parse_saved_date(data[DPN_RECORD_UPDATE_SIGNED_DATE]))
