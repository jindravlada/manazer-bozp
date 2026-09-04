from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.kniha_urazu.sluzby.accident_dpn_care import (
    CARE_EXAM_DATE,
    CARE_EXAM_REASON,
    CARE_EXAM_REQUIRED,
    CARE_EXAM_RESULT,
    CARE_RETURN_DATE,
    CARE_RETURN_MODE,
    EXAM_REQUIRED_NO,
    EXAM_REQUIRED_YES,
    EXAM_RESULTS,
    RETURN_MODES,
    empty_dpn_care_return,
    exam_details_relevant,
    normalize_dpn_care_return,
    return_date_relevant,
)
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

OVERVIEW_SOURCE_HINT = (
    "Stav vychází z Ohlašovací povinnosti. Splnění evidujte tam – "
    "tato sekce je jen přehled a stejný úkon se zadává jen jednou."
)

EXAM_NO_HEALTH_HINT = (
    "Uvádějte jen, zda a proč byla prohlídka vyžadována. "
    "Diagnózy a jiné zdravotní údaje se sem nezadávají."
)


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

        care_group = self._build_care_return_section()
        self.section_groups.append(care_group)
        sections_layout.addWidget(care_group)

        mira_group = QGroupBox(SECTION_MIRA_ODPOVEDNOSTI)
        mira_layout = QVBoxLayout(mira_group)
        placeholder = QLabel(SECTION_PLACEHOLDER)
        placeholder.setObjectName("MutedText")
        placeholder.setWordWrap(True)
        mira_layout.addWidget(placeholder)
        self.section_groups.append(mira_group)
        sections_layout.addWidget(mira_group)

        layout.addWidget(self.info_panel)
        layout.addWidget(self.sections_widget)
        layout.addStretch()

        self._dpn_ended = False
        self.set_dpn_ended(False)

    def _build_zou_update_section(self) -> QGroupBox:
        group = QGroupBox(SECTION_AKTUALIZACE_ZAZNAMU)
        form = QFormLayout(group)

        self.overview_hint = QLabel(OVERVIEW_SOURCE_HINT)
        self.overview_hint.setObjectName("MutedText")
        self.overview_hint.setWordWrap(True)
        form.addRow(self.overview_hint)

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

        for widget in (
            self.portal_suip_done,
            self.portal_suip_date,
            self.signed_record_done,
            self.signed_record_date,
        ):
            widget.setEnabled(False)
        return group

    def _build_care_return_section(self) -> QGroupBox:
        group = QGroupBox(SECTION_PECE_NAVRA)
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        exam_group = QGroupBox("Mimořádná pracovnělékařská prohlídka")
        self._exam_form = QFormLayout(exam_group)

        exam_hint = QLabel(EXAM_NO_HEALTH_HINT)
        exam_hint.setObjectName("MutedText")
        exam_hint.setWordWrap(True)
        self._exam_form.addRow(exam_hint)

        self.exam_required_ano = QRadioButton("Ano")
        self.exam_required_ne = QRadioButton("Ne")
        self.exam_required_group = QButtonGroup(self)
        self.exam_required_group.addButton(self.exam_required_ano)
        self.exam_required_group.addButton(self.exam_required_ne)

        exam_required_row = QWidget()
        exam_required_layout = QHBoxLayout(exam_required_row)
        exam_required_layout.setContentsMargins(0, 0, 0, 0)
        exam_required_layout.setSpacing(8)
        exam_required_layout.addWidget(self.exam_required_ano)
        exam_required_layout.addWidget(self.exam_required_ne)
        exam_required_layout.addStretch()
        self._exam_form.addRow("Prohlídka vyžadována:", exam_required_row)

        self.exam_reason = QTextEdit()
        self.exam_reason.setFixedHeight(60)
        self._exam_form.addRow("Důvod:", self.exam_reason)

        self.exam_date = NullableDateEdit()
        self._exam_form.addRow("Datum prohlídky:", self.exam_date)

        self.exam_result = QComboBox()
        self.exam_result.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.exam_result.addItem("", "")
        for label in EXAM_RESULTS:
            self.exam_result.addItem(label, label)
        self._exam_form.addRow("Výsledek:", self.exam_result)

        return_group = QGroupBox("Návrat do práce")
        self._return_form = QFormLayout(return_group)

        self.return_date = NullableDateEdit()
        self._return_form.addRow("Datum skutečného návratu do práce:", self.return_date)

        self.return_mode = QComboBox()
        self.return_mode.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.return_mode.addItem("", "")
        for label in RETURN_MODES:
            self.return_mode.addItem(label, label)
        self._return_form.addRow("Způsob návratu:", self.return_mode)

        layout.addWidget(exam_group)
        layout.addWidget(return_group)

        self.exam_required_ano.toggled.connect(self._refresh_care_relevance)
        self.exam_required_ne.toggled.connect(self._refresh_care_relevance)
        self.return_mode.currentIndexChanged.connect(self._refresh_care_relevance)
        return group

    def set_dpn_ended(self, ended: bool) -> None:
        self._dpn_ended = bool(ended)
        self.info_panel.setVisible(not self._dpn_ended)
        self.sections_widget.setVisible(self._dpn_ended)
        self.sections_widget.setEnabled(self._dpn_ended)
        for widget in (
            self.portal_suip_done,
            self.portal_suip_date,
            self.signed_record_done,
            self.signed_record_date,
        ):
            widget.setEnabled(False)
        self._refresh_care_relevance()

    def set_from_dpn_do(self, dpn_do) -> None:
        self.set_dpn_ended(is_dpn_ended(dpn_do))

    def is_content_active(self) -> bool:
        return self._dpn_ended

    def _exam_required_value(self) -> str:
        if self.exam_required_ano.isChecked():
            return EXAM_REQUIRED_YES
        if self.exam_required_ne.isChecked():
            return EXAM_REQUIRED_NO
        return ""

    def _combo_value(self, combo: QComboBox) -> str:
        data = combo.currentData()
        if isinstance(data, str) and data:
            return data
        return (combo.currentText() or "").strip()

    def _set_combo_value(self, combo: QComboBox, value: str) -> None:
        text = (value or "").strip()
        for index in range(combo.count()):
            if combo.itemData(index) == text or combo.itemText(index) == text:
                combo.setCurrentIndex(index)
                return
        combo.setCurrentIndex(0)

    def _refresh_care_relevance(self, *_args) -> None:
        state = self.get_dpn_care_return()
        exam_needed = exam_details_relevant(state)
        show_return_date = return_date_relevant(state)
        active = self._dpn_ended

        self.exam_reason.setEnabled(active and exam_needed)
        self.exam_date.setEnabled(active and exam_needed)
        self.exam_result.setEnabled(active and exam_needed)
        self.return_date.setEnabled(active and show_return_date)

        self._exam_form.setRowVisible(self.exam_reason, exam_needed)
        self._exam_form.setRowVisible(self.exam_date, exam_needed)
        self._exam_form.setRowVisible(self.exam_result, exam_needed)
        self._return_form.setRowVisible(self.return_date, show_return_date)

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

    def get_dpn_care_return(self) -> dict:
        return normalize_dpn_care_return(
            {
                CARE_EXAM_REQUIRED: self._exam_required_value(),
                CARE_EXAM_REASON: self.exam_reason.toPlainText(),
                CARE_EXAM_DATE: self.exam_date.get_date(),
                CARE_EXAM_RESULT: self._combo_value(self.exam_result),
                CARE_RETURN_DATE: self.return_date.get_date(),
                CARE_RETURN_MODE: self._combo_value(self.return_mode),
            }
        )

    def load_dpn_care_return(self, state: dict | None) -> None:
        data = normalize_dpn_care_return(state) if state else empty_dpn_care_return()
        self.exam_required_ano.blockSignals(True)
        self.exam_required_ne.blockSignals(True)
        self.return_mode.blockSignals(True)
        self.exam_required_ano.setChecked(data[CARE_EXAM_REQUIRED] == EXAM_REQUIRED_YES)
        self.exam_required_ne.setChecked(data[CARE_EXAM_REQUIRED] == EXAM_REQUIRED_NO)
        self.exam_reason.setPlainText(data[CARE_EXAM_REASON])
        self.exam_date.set_date_value(parse_saved_date(data[CARE_EXAM_DATE]))
        self._set_combo_value(self.exam_result, data[CARE_EXAM_RESULT])
        self.return_date.set_date_value(parse_saved_date(data[CARE_RETURN_DATE]))
        self._set_combo_value(self.return_mode, data[CARE_RETURN_MODE])
        self.exam_required_ano.blockSignals(False)
        self.exam_required_ne.blockSignals(False)
        self.return_mode.blockSignals(False)
        self._refresh_care_relevance()
