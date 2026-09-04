from PySide6.QtCore import Qt
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

from core.widgets.no_wheel_guards import NoWheelSpinBox
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.kniha_urazu.sluzby.accident_dpn_care import (
    CARE_CATEGORY_1_NO_RISK,
    CARE_DPN_OVER_8_WEEKS,
    CARE_EXAM_DATE,
    CARE_EXAM_DEADLINE,
    CARE_EXAM_REASON,
    CARE_EXAM_RESULT,
    CARE_FITNESS_CHANGE_PRESUMED,
    CARE_RETURN_DATE,
    CARE_RETURN_MODE,
    CARE_SEVERE_CONSEQUENCES,
    CARE_UNCONSCIOUSNESS_OR_SEVERE_HARM,
    EXAM_REQUIRED_NO,
    EXAM_REQUIRED_YES,
    EXAM_RESULTS,
    RETURN_MODES,
    empty_dpn_care_return,
    evaluate_dpn_care_return,
    exam_details_relevant,
    exam_required_banner_text,
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
from moduly.kniha_urazu.sluzby.accident_dpn_responsibility import (
    PERCENT_MAX,
    PERCENT_MIN,
    RESP_NOTE,
    RESP_PROPOSED_PERCENT,
    RESP_RECOGNIZED_PERCENT,
    empty_dpn_employer_responsibility,
    normalize_dpn_employer_responsibility,
    reduction_percent,
)


TAB_PO_UKONCENI_DPN = "Po ukončení DPN"

DPN_NOT_ENDED_MESSAGE = (
    "DPN dosud nebyla ukončena. Povinnosti po ukončení DPN zatím nejsou aktivní."
)

SECTION_AKTUALIZACE_ZAZNAMU = "Aktualizace záznamu o pracovním úrazu"
SECTION_PECE_NAVRA = "Péče a návrat do práce"
SECTION_EXAM_EVALUATION = "Vyhodnocení mimořádné pracovnělékařské prohlídky"
SECTION_ROZSAH_NAHRADY = "Rozsah náhrady pracovního úrazu"
SECTION_MIRA_ODPOVEDNOSTI = SECTION_ROZSAH_NAHRADY

SECTION_TITLES = (
    SECTION_AKTUALIZACE_ZAZNAMU,
    SECTION_PECE_NAVRA,
    SECTION_ROZSAH_NAHRADY,
)

OVERVIEW_SOURCE_HINT = (
    "Stav vychází z Ohlašovací povinnosti. Splnění evidujte tam – "
    "tato sekce je jen přehled a stejný úkon se zadává jen jednou."
)

EXAM_NO_HEALTH_HINT = (
    "Označte jen důvody mimořádné prohlídky. "
    "Diagnózy a jiné zdravotní údaje se sem nezadávají."
)

BANNER_STYLE_REQUIRED = (
    "font-weight: bold; color: #842029; background: #f8d7da; "
    "border: 1px solid #d39a9f; border-radius: 3px; padding: 8px;"
)
BANNER_STYLE_NOT_REQUIRED = (
    "font-weight: bold; color: #0b5d1e; background: #d9f0dd; "
    "border: 1px solid #91c79c; border-radius: 3px; padding: 8px;"
)
BANNER_STYLE_DEADLINE = (
    "font-weight: bold; color: #7a4b00; background: #fff3cd; "
    "border: 1px solid #d6b656; border-radius: 3px; padding: 8px;"
)
BANNER_STYLE_DEADLINE_WAIT = (
    "font-weight: bold; color: #5c5c5c; background: #f4f4f4; "
    "border: 1px solid #d0d0d0; border-radius: 3px; padding: 8px;"
)

EXAM_DEADLINE_UNTIL_LABEL = (
    "Mimořádnou pracovnělékařskou prohlídku proveďte nejpozději do:"
)
EXAM_DEADLINE_NEED_RETURN = (
    "Pro stanovení termínu zadejte datum skutečného návratu do práce."
)

RESPONSIBILITY_HINT = (
    "Navržený rozsah náhrady je stanovisko zaměstnavatele před řešením "
    "pojistné události. Skutečně uznaný rozsah je výsledná hodnota použitá "
    "při vypořádání. 100 % znamená plnou náhradu zaměstnanci. "
    "Částky odškodnění se zde neevidují."
)

LABEL_PROPOSED_COMPENSATION = "Navržený rozsah náhrady zaměstnanci:"
LABEL_RECOGNIZED_COMPENSATION = "Skutečně uznaný rozsah náhrady zaměstnanci:"
LABEL_REDUCTION = "Krácení náhrady:"
LABEL_COMPENSATION_NOTE = "Poznámka k rozsahu náhrady:"

PERCENT_EMPTY_VALUE = -1
PERCENT_SUFFIX = " %"


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

        mira_group = self._build_responsibility_section()
        self.section_groups.append(mira_group)
        sections_layout.addWidget(mira_group)

        layout.addWidget(self.info_panel)
        layout.addWidget(self.sections_widget)
        layout.addStretch()

        self._dpn_ended = False
        self._dpn_od = None
        self._dpn_do = None
        self._legacy_exam_reason = ""
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

    def _make_ano_ne_row(self) -> tuple[QWidget, QRadioButton, QRadioButton]:
        ano = QRadioButton("Ano")
        ne = QRadioButton("Ne")
        group = QButtonGroup(self)
        group.addButton(ano)
        group.addButton(ne)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(ano)
        layout.addWidget(ne)
        layout.addStretch()
        ano.toggled.connect(self._refresh_care_relevance)
        ne.toggled.connect(self._refresh_care_relevance)
        return row, ano, ne

    def _build_care_return_section(self) -> QGroupBox:
        group = QGroupBox(SECTION_PECE_NAVRA)
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        exam_group = QGroupBox(SECTION_EXAM_EVALUATION)
        self._exam_form = QFormLayout(exam_group)

        exam_hint = QLabel(EXAM_NO_HEALTH_HINT)
        exam_hint.setObjectName("MutedText")
        exam_hint.setWordWrap(True)
        self._exam_form.addRow(exam_hint)

        self.dpn_over_8_weeks_value = QLabel(EXAM_REQUIRED_NO)
        self._exam_form.addRow("DPN delší než 8 týdnů:", self.dpn_over_8_weeks_value)

        (
            self.category_1_row,
            self.category_1_no_risk_ano,
            self.category_1_no_risk_ne,
        ) = self._make_ano_ne_row()
        self._exam_form.addRow(
            "Práce kategorie 1 bez profesního rizika:",
            self.category_1_row,
        )

        (
            self.severe_consequences_row,
            self.severe_consequences_ano,
            self.severe_consequences_ne,
        ) = self._make_ano_ne_row()
        self._exam_form.addRow("Úraz měl těžké následky:", self.severe_consequences_row)

        (
            self.unconsciousness_row,
            self.unconsciousness_ano,
            self.unconsciousness_ne,
        ) = self._make_ano_ne_row()
        self._exam_form.addRow(
            "V souvislosti s úrazem došlo k bezvědomí nebo jiné těžké újmě na zdraví:",
            self.unconsciousness_row,
        )

        (
            self.fitness_change_row,
            self.fitness_change_ano,
            self.fitness_change_ne,
        ) = self._make_ano_ne_row()
        self._exam_form.addRow(
            "Existuje důvodný předpoklad změny nebo ztráty zdravotní způsobilosti:",
            self.fitness_change_row,
        )

        self.exam_required_banner = QLabel()
        self.exam_required_banner.setObjectName("ExamRequiredBanner")
        self.exam_required_banner.setWordWrap(True)
        self.exam_required_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.exam_required_banner.setMinimumHeight(36)
        self._exam_form.addRow(self.exam_required_banner)

        self._return_date_widget = QWidget()
        self._return_form = QFormLayout(self._return_date_widget)
        self._return_form.setContentsMargins(0, 0, 0, 0)
        self.return_date = NullableDateEdit()
        self._return_form.addRow("Datum skutečného návratu do práce:", self.return_date)

        self._exam_followup_widget = QWidget()
        self._exam_followup_form = QFormLayout(self._exam_followup_widget)
        self._exam_followup_form.setContentsMargins(0, 0, 0, 0)

        self.exam_deadline_panel = QFrame()
        self.exam_deadline_panel.setObjectName("ExamDeadlinePanel")
        self.exam_deadline_label = QLabel()
        self.exam_deadline_label.setObjectName("ExamDeadlineLabel")
        self.exam_deadline_label.setWordWrap(True)
        self.exam_deadline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.exam_deadline_label.setMinimumHeight(36)
        self.exam_deadline_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )
        deadline_layout = QVBoxLayout(self.exam_deadline_panel)
        deadline_layout.setContentsMargins(0, 0, 0, 0)
        deadline_layout.addWidget(self.exam_deadline_label)
        self._exam_followup_form.addRow(self.exam_deadline_panel)

        self.exam_date = NullableDateEdit()
        self._exam_followup_form.addRow("Prohlídka provedena dne:", self.exam_date)

        self.exam_result = QComboBox()
        self.exam_result.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.exam_result.addItem("", "")
        for label in EXAM_RESULTS:
            self.exam_result.addItem(label, label)
        self._exam_followup_form.addRow("Výsledek prohlídky:", self.exam_result)

        self._return_mode_widget = QWidget()
        self._return_mode_form = QFormLayout(self._return_mode_widget)
        self._return_mode_form.setContentsMargins(0, 0, 0, 0)
        self.return_mode = QComboBox()
        self.return_mode.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.return_mode.addItem("", "")
        for label in RETURN_MODES:
            self.return_mode.addItem(label, label)
        self._return_mode_form.addRow("Způsob návratu:", self.return_mode)

        layout.addWidget(exam_group)
        layout.addWidget(self._return_date_widget)
        layout.addWidget(self._exam_followup_widget)
        layout.addWidget(self._return_mode_widget)

        self.return_mode.currentIndexChanged.connect(self._refresh_care_relevance)
        self.return_date.dateChanged.connect(self._refresh_care_relevance)
        return group

    def _build_percent_spin(self) -> NoWheelSpinBox:
        spin = NoWheelSpinBox()
        spin.setRange(PERCENT_EMPTY_VALUE, PERCENT_MAX)
        spin.setSpecialValueText(" ")
        spin.setSuffix(PERCENT_SUFFIX)
        spin.setValue(PERCENT_EMPTY_VALUE)
        spin.setMaximumWidth(120)
        return spin

    def _percent_value(self, spin: NoWheelSpinBox) -> int | None:
        value = spin.value()
        if value < PERCENT_MIN:
            return None
        return value

    def _set_percent_value(self, spin: NoWheelSpinBox, value: int | None) -> None:
        if value is None:
            spin.setValue(PERCENT_EMPTY_VALUE)
            return
        spin.setValue(value)

    def _build_percent_with_reduction(
        self, reduction_label: QLabel
    ) -> tuple[QWidget, NoWheelSpinBox, QLabel]:
        spin = self._build_percent_spin()
        caption = QLabel(LABEL_REDUCTION)
        caption.setObjectName("MutedText")
        reduction_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(spin)
        layout.addWidget(caption)
        layout.addWidget(reduction_label)
        layout.addStretch()
        return row, spin, caption

    def _build_responsibility_section(self) -> QGroupBox:
        group = QGroupBox(SECTION_ROZSAH_NAHRADY)
        form = QFormLayout(group)
        self._responsibility_form = form

        hint = QLabel(RESPONSIBILITY_HINT)
        hint.setObjectName("MutedText")
        hint.setWordWrap(True)
        form.addRow(hint)

        self.proposed_reduction_label = QLabel()
        self.proposed_reduction_label.setObjectName("ProposedReductionLabel")
        self.recognized_reduction_label = QLabel()
        self.recognized_reduction_label.setObjectName("RecognizedReductionLabel")

        proposed_row, self.proposed_percent, self.proposed_reduction_caption = (
            self._build_percent_with_reduction(self.proposed_reduction_label)
        )
        recognized_row, self.recognized_percent, self.recognized_reduction_caption = (
            self._build_percent_with_reduction(self.recognized_reduction_label)
        )
        self.responsibility_note = QTextEdit()
        self.responsibility_note.setFixedHeight(60)

        form.addRow(LABEL_PROPOSED_COMPENSATION, proposed_row)
        form.addRow(LABEL_RECOGNIZED_COMPENSATION, recognized_row)
        form.addRow(LABEL_COMPENSATION_NOTE, self.responsibility_note)

        self.proposed_percent.valueChanged.connect(self._refresh_reduction_display)
        self.recognized_percent.valueChanged.connect(self._refresh_reduction_display)
        self._refresh_reduction_display()
        return group

    def _reduction_text(self, percent: int | None) -> str:
        reduced = reduction_percent(percent)
        if reduced is None:
            return ""
        return f"{reduced}{PERCENT_SUFFIX}"

    def _refresh_reduction_display(self, *_args) -> None:
        proposed = self._percent_value(self.proposed_percent)
        recognized = self._percent_value(self.recognized_percent)
        self.proposed_reduction_label.setText(self._reduction_text(proposed))
        self.recognized_reduction_label.setText(self._reduction_text(recognized))
        show_proposed = proposed is not None
        show_recognized = recognized is not None
        self.proposed_reduction_caption.setVisible(show_proposed)
        self.proposed_reduction_label.setVisible(show_proposed)
        self.recognized_reduction_caption.setVisible(show_recognized)
        self.recognized_reduction_label.setVisible(show_recognized)

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
        self._dpn_do = dpn_do
        self.set_dpn_ended(is_dpn_ended(dpn_do))

    def set_from_dpn_range(self, dpn_od, dpn_do) -> None:
        self._dpn_od = dpn_od
        self.set_from_dpn_do(dpn_do)

    def is_content_active(self) -> bool:
        return self._dpn_ended

    def visible_care_sequence(self) -> tuple[str, ...]:
        """Pořadí viditelných polí návratu a provedení prohlídky."""
        items: list[str] = []
        if self._return_form.isRowVisible(self.return_date):
            items.append("return_date")
        if not self._exam_followup_widget.isHidden():
            items.extend(["exam_deadline", "exam_date", "exam_result"])
        items.append("return_mode")
        return tuple(items)

    def _ano_ne_value(self, ano: QRadioButton, ne: QRadioButton) -> str:
        if ano.isChecked():
            return EXAM_REQUIRED_YES
        if ne.isChecked():
            return EXAM_REQUIRED_NO
        return ""

    def _set_ano_ne_value(
        self, ano: QRadioButton, ne: QRadioButton, value: str
    ) -> None:
        ano.blockSignals(True)
        ne.blockSignals(True)
        ano.setChecked(value == EXAM_REQUIRED_YES)
        ne.setChecked(value == EXAM_REQUIRED_NO)
        ano.blockSignals(False)
        ne.blockSignals(False)

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

    def _raw_dpn_care_return(self) -> dict:
        return {
            CARE_EXAM_REASON: self._legacy_exam_reason,
            CARE_EXAM_DATE: self.exam_date.get_date(),
            CARE_EXAM_RESULT: self._combo_value(self.exam_result),
            CARE_CATEGORY_1_NO_RISK: self._ano_ne_value(
                self.category_1_no_risk_ano, self.category_1_no_risk_ne
            ),
            CARE_SEVERE_CONSEQUENCES: self._ano_ne_value(
                self.severe_consequences_ano, self.severe_consequences_ne
            ),
            CARE_UNCONSCIOUSNESS_OR_SEVERE_HARM: self._ano_ne_value(
                self.unconsciousness_ano, self.unconsciousness_ne
            ),
            CARE_FITNESS_CHANGE_PRESUMED: self._ano_ne_value(
                self.fitness_change_ano, self.fitness_change_ne
            ),
            CARE_RETURN_DATE: self.return_date.get_date(),
            CARE_RETURN_MODE: self._combo_value(self.return_mode),
        }

    def _refresh_care_relevance(self, *_args) -> None:
        state = self.get_dpn_care_return()
        exam_needed = exam_details_relevant(
            state, dpn_od=self._dpn_od, dpn_do=self._dpn_do
        )
        show_return_date = return_date_relevant(state)
        over_8_weeks = state.get(CARE_DPN_OVER_8_WEEKS) == EXAM_REQUIRED_YES
        active = self._dpn_ended

        self.dpn_over_8_weeks_value.setText(
            EXAM_REQUIRED_YES if over_8_weeks else EXAM_REQUIRED_NO
        )
        self.exam_required_banner.setText(exam_required_banner_text(exam_needed))
        self.exam_required_banner.setStyleSheet(
            BANNER_STYLE_REQUIRED if exam_needed else BANNER_STYLE_NOT_REQUIRED
        )

        self._update_exam_deadline_notice(state)
        self._exam_followup_widget.setVisible(exam_needed)
        self._exam_followup_widget.setEnabled(active and exam_needed)

        self.exam_date.setEnabled(active and exam_needed)
        self.exam_result.setEnabled(active and exam_needed)
        self.return_date.setEnabled(active and show_return_date)
        self.category_1_no_risk_ano.setEnabled(active and over_8_weeks)
        self.category_1_no_risk_ne.setEnabled(active and over_8_weeks)

        self._exam_form.setRowVisible(self.category_1_row, over_8_weeks)
        self._return_form.setRowVisible(self.return_date, show_return_date)

    def _update_exam_deadline_notice(self, state: dict) -> None:
        deadline = parse_saved_date(state.get(CARE_EXAM_DEADLINE))
        if deadline is None:
            self.exam_deadline_label.setText(EXAM_DEADLINE_NEED_RETURN)
            self.exam_deadline_label.setStyleSheet(BANNER_STYLE_DEADLINE_WAIT)
            return
        self.exam_deadline_label.setText(
            f"{EXAM_DEADLINE_UNTIL_LABEL}\n{deadline.strftime('%d.%m.%Y')}"
        )
        self.exam_deadline_label.setStyleSheet(BANNER_STYLE_DEADLINE)

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
        return evaluate_dpn_care_return(
            self._raw_dpn_care_return(),
            dpn_od=self._dpn_od,
            dpn_do=self._dpn_do,
        )

    def load_dpn_care_return(self, state: dict | None) -> None:
        data = evaluate_dpn_care_return(
            state if state else empty_dpn_care_return(),
            dpn_od=self._dpn_od,
            dpn_do=self._dpn_do,
        )
        self._legacy_exam_reason = data.get(CARE_EXAM_REASON) or ""
        self.return_mode.blockSignals(True)
        self.return_date.blockSignals(True)
        self._set_ano_ne_value(
            self.category_1_no_risk_ano,
            self.category_1_no_risk_ne,
            data[CARE_CATEGORY_1_NO_RISK],
        )
        self._set_ano_ne_value(
            self.severe_consequences_ano,
            self.severe_consequences_ne,
            data[CARE_SEVERE_CONSEQUENCES],
        )
        self._set_ano_ne_value(
            self.unconsciousness_ano,
            self.unconsciousness_ne,
            data[CARE_UNCONSCIOUSNESS_OR_SEVERE_HARM],
        )
        self._set_ano_ne_value(
            self.fitness_change_ano,
            self.fitness_change_ne,
            data[CARE_FITNESS_CHANGE_PRESUMED],
        )
        self.exam_date.set_date_value(parse_saved_date(data[CARE_EXAM_DATE]))
        self._set_combo_value(self.exam_result, data[CARE_EXAM_RESULT])
        self.return_date.set_date_value(parse_saved_date(data[CARE_RETURN_DATE]))
        self._set_combo_value(self.return_mode, data[CARE_RETURN_MODE])
        self.return_mode.blockSignals(False)
        self.return_date.blockSignals(False)
        self._refresh_care_relevance()

    def get_dpn_employer_responsibility(self) -> dict:
        return normalize_dpn_employer_responsibility(
            {
                RESP_PROPOSED_PERCENT: self._percent_value(self.proposed_percent),
                RESP_RECOGNIZED_PERCENT: self._percent_value(self.recognized_percent),
                RESP_NOTE: self.responsibility_note.toPlainText(),
            }
        )

    def load_dpn_employer_responsibility(self, state: dict | None) -> None:
        data = (
            normalize_dpn_employer_responsibility(state)
            if state
            else empty_dpn_employer_responsibility()
        )
        self._set_percent_value(self.proposed_percent, data[RESP_PROPOSED_PERCENT])
        self._set_percent_value(self.recognized_percent, data[RESP_RECOGNIZED_PERCENT])
        self.responsibility_note.setPlainText(data[RESP_NOTE])
        self._refresh_reduction_display()
