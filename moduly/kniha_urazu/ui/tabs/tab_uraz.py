from datetime import date

from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.code_selector import CodeSelector
from core.widgets.date_edit import DateEdit
from core.widgets.multi_code_selector import MultiCodeSelector
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.kniha_urazu.services.ciselnik_service import kniha_urazu_ciselnik_service
from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
    ACCIDENT_DATE_DELAY_WARNING,
    DPN_KIND_MISMATCH_MESSAGE,
    accident_kind_info_message,
    dpn_calendar_days,
    is_accident_date_delayed,
    is_dpn_kind_mismatch,
)


REQUIRED_STYLE = "border: 2px solid #d32f2f; background: #fff6f6;"
NORMAL_STYLE = ""


class TabUraz(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._injury_date_is_saved = False
        self._injury_date_baseline: date | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.druh_urazu = CodeSelector([
            "",
            "pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny",
            "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            "závažný pracovní úraz (hospitalizace více než 5 po sobě jdoucích dnů)",
            "smrtelný",
        ])

        self.podezreni_trestny_cin_ano = QRadioButton("ANO")
        self.podezreni_trestny_cin_ne = QRadioButton("NE")
        self.podezreni_trestny_cin_ne.setChecked(True)
        self.podezreni_trestny_cin_group = QButtonGroup(self)
        self.podezreni_trestny_cin_group.addButton(self.podezreni_trestny_cin_ano)
        self.podezreni_trestny_cin_group.addButton(self.podezreni_trestny_cin_ne)

        tc_layout = QHBoxLayout()
        tc_layout.addWidget(self.podezreni_trestny_cin_ano)
        tc_layout.addWidget(self.podezreni_trestny_cin_ne)
        tc_layout.addStretch()

        self.accident_date = DateEdit()
        self.accident_date.dateChanged.connect(self._refresh_accident_date_delay_warning)

        self.accident_date_delay_warning = QLabel()
        self.accident_date_delay_warning.setObjectName("WarningText")
        self.accident_date_delay_warning.setWordWrap(True)
        self.accident_date_delay_warning.setStyleSheet("color: #b45309;")
        self.accident_date_delay_warning.setVisible(False)

        self.accident_time = QLineEdit()
        self.accident_time.setPlaceholderText("HH:MM")

        self.dpn_od = NullableDateEdit()
        self.dpn_do = NullableDateEdit()
        self.dpn_od.dateChanged.connect(self._refresh_dpn_duration)
        self.dpn_do.dateChanged.connect(self._refresh_dpn_duration)

        self._current_druh_urazu = ""

        self.dpn_duration_label = QLabel()
        self.dpn_duration_label.setObjectName("InfoText")

        self.druh_urazu_info_label = QLabel()
        self.druh_urazu_info_label.setObjectName("InfoText")
        self.druh_urazu_info_label.setWordWrap(True)
        self.druh_urazu_info_label.setVisible(False)

        self.dpn_kind_warning_label = QLabel()
        self.dpn_kind_warning_label.setObjectName("WarningText")
        self.dpn_kind_warning_label.setWordWrap(True)
        self.dpn_kind_warning_label.setStyleSheet("color: #b45309;")
        self.dpn_kind_warning_label.setVisible(False)

        self.accident_datetime_row = self._equal_halves_row(
            self._labeled_half("Datum úrazu:", self.accident_date, required=True),
            self._labeled_half("Čas úrazu:", self.accident_time, required=True),
        )
        self.dpn_range_row = self._equal_halves_row(
            self._labeled_half("DPN následkem úrazu od:", self.dpn_od),
            self._labeled_half("DPN následkem úrazu do:", self.dpn_do),
        )

        self.druh_zraneni = MultiCodeSelector(kniha_urazu_ciselnik_service.druh_zraneni())
        self.zranena_cast_tela = MultiCodeSelector(kniha_urazu_ciselnik_service.zranena_cast_tela())

        self.hromadny_uraz_ano = QRadioButton("ANO")
        self.hromadny_uraz_ne = QRadioButton("NE")
        self.hromadny_uraz_ne.setChecked(True)
        self.hromadny_uraz_group = QButtonGroup(self)
        self.hromadny_uraz_group.addButton(self.hromadny_uraz_ano)
        self.hromadny_uraz_group.addButton(self.hromadny_uraz_ne)

        hromadny_layout = QHBoxLayout()
        hromadny_layout.addWidget(self.hromadny_uraz_ano)
        hromadny_layout.addWidget(self.hromadny_uraz_ne)
        hromadny_layout.addStretch()

        self.celkovy_pocet_zranenych = QSpinBox()
        self.celkovy_pocet_zranenych.setMinimum(1)
        self.celkovy_pocet_zranenych.setMaximum(999)
        self.celkovy_pocet_zranenych.setValue(1)

        self.cinnost_pri_urazu = CodeSelector(kniha_urazu_ciselnik_service.cinnost_pri_urazu())
        self.cinnost_pri_urazu.set_value("")

        self.misto_urazu = QTextEdit()
        self.misto_urazu.setFixedHeight(72)

        self.popis_urazoveho_deje = QTextEdit()
        self.popis_urazoveho_deje.setFixedHeight(150)

        self._required_widgets = {
            "Druh úrazu": self.druh_urazu,
            "Datum úrazu": self.accident_date,
            "Čas úrazu": self.accident_time,
            "Druh zranění": self.druh_zraneni,
            "Zraněná část těla": self.zranena_cast_tela,
            "Hromadný úraz": self.hromadny_uraz_ne,
            "Počet zraněných osob celkem": self.celkovy_pocet_zranenych,
            "Činnost, při které k úrazu došlo": self.cinnost_pri_urazu,
            "Místo úrazu": self.misto_urazu,
            "Popis úrazového děje, místa, příčin a okolností": self.popis_urazoveho_deje,
        }

        self._add_required_row(form, "Druh úrazu:", self.druh_urazu)
        form.addRow("Podezření na trestný čin:", tc_layout)
        form.addRow(self.accident_datetime_row)
        form.addRow(self.accident_date_delay_warning)
        form.addRow(self.dpn_range_row)
        form.addRow(self.dpn_duration_label)
        form.addRow(self.druh_urazu_info_label)
        form.addRow(self.dpn_kind_warning_label)
        self._add_required_row(form, "Druh zranění:", self.druh_zraneni)
        self._add_required_row(form, "Zraněná část těla:", self.zranena_cast_tela)
        self._add_required_row(form, "Hromadný úraz:", hromadny_layout)
        self._add_required_row(form, "Počet zraněných osob celkem:", self.celkovy_pocet_zranenych)
        self._add_required_row(form, "Činnost, při které k úrazu došlo:", self.cinnost_pri_urazu)
        self._add_required_row(form, "Místo úrazu:", self.misto_urazu)
        self._add_required_row(form, "Popis úrazového děje, místa, příčin a okolností:", self.popis_urazoveho_deje)

        layout.addLayout(form)
        layout.addStretch()

        self._refresh_dpn_duration()
        self._refresh_accident_date_delay_warning()

    def _add_required_row(self, form: QFormLayout, label_text: str, widget_or_layout):
        label = QLabel(f"<b>{label_text}</b>")
        form.addRow(label, widget_or_layout)

    def _labeled_half(self, label_text: str, widget: QWidget, *, required: bool = False) -> QWidget:
        half = QWidget()
        half.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        form = QFormLayout(half)
        form.setContentsMargins(0, 0, 0, 0)
        label = QLabel(f"<b>{label_text}</b>" if required else label_text)
        form.addRow(label, widget)
        return half

    def _equal_halves_row(self, left: QWidget, right: QWidget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(left, 1)
        layout.addWidget(right, 1)
        return row

    def get_accident_date(self) -> date:
        qdate = self.accident_date.date()
        return date(qdate.year(), qdate.month(), qdate.day())

    def injury_date_changed_from_baseline(self) -> bool:
        if not self._injury_date_is_saved:
            return False
        return self.get_accident_date() != self._injury_date_baseline

    def commit_injury_date_baseline(self) -> None:
        self._injury_date_is_saved = True
        self._injury_date_baseline = self.get_accident_date()
        self._refresh_accident_date_delay_warning()

    def _refresh_accident_date_delay_warning(self, *_args) -> None:
        if self._should_show_accident_date_delay_warning():
            self.accident_date_delay_warning.setText(ACCIDENT_DATE_DELAY_WARNING)
            self.accident_date_delay_warning.setVisible(True)
        else:
            self.accident_date_delay_warning.clear()
            self.accident_date_delay_warning.setVisible(False)

    def _should_show_accident_date_delay_warning(self) -> bool:
        current = self.get_accident_date()
        if not is_accident_date_delayed(current):
            return False
        if not self._injury_date_is_saved:
            return True
        return current != self._injury_date_baseline

    def refresh_date_and_kind_hints(self) -> None:
        self._refresh_accident_date_delay_warning()
        self.refresh_dpn_kind_warning()

    def _refresh_dpn_duration(self) -> None:
        days = dpn_calendar_days(self.dpn_od.get_date(), self.dpn_do.get_date())
        if days is None:
            text = "—"
        else:
            text = f"{days} dní"
        self.dpn_duration_label.setText(f"Pracovní neschopnost celkem: {text}")
        self.refresh_dpn_kind_warning()

    def refresh_dpn_kind_warning(self, druh_urazu: str | None = None) -> None:
        if druh_urazu is not None:
            self._current_druh_urazu = druh_urazu
        days = dpn_calendar_days(self.dpn_od.get_date(), self.dpn_do.get_date())
        if is_dpn_kind_mismatch(self._current_druh_urazu, days):
            self.dpn_kind_warning_label.setText(DPN_KIND_MISMATCH_MESSAGE)
            self.dpn_kind_warning_label.setVisible(True)
        else:
            self.dpn_kind_warning_label.clear()
            self.dpn_kind_warning_label.setVisible(False)
        self._refresh_kind_info()

    def _refresh_kind_info(self) -> None:
        message = accident_kind_info_message(self._current_druh_urazu)
        if message:
            self.druh_urazu_info_label.setText(message)
            self.druh_urazu_info_label.setVisible(True)
        else:
            self.druh_urazu_info_label.clear()
            self.druh_urazu_info_label.setVisible(False)

    def _radio_value(self, yes_button: QRadioButton, no_button: QRadioButton) -> str:
        if yes_button.isChecked():
            return "ANO"
        if no_button.isChecked():
            return "NE"
        return ""

    def _set_radio_value(self, value: str, yes_button: QRadioButton, no_button: QRadioButton, default_no: bool = False):
        value = (value or "").strip().upper()
        yes_button.setChecked(value == "ANO")
        no_button.setChecked(value == "NE" or (default_no and not value))

    def _is_empty(self, widget) -> bool:
        if isinstance(widget, QLineEdit):
            return not widget.text().strip()
        if isinstance(widget, QTextEdit):
            return not widget.toPlainText().strip()
        if isinstance(widget, CodeSelector):
            return not widget.value().strip()
        if isinstance(widget, MultiCodeSelector):
            return not widget.has_value()
        if isinstance(widget, DateEdit):
            return False  # DateEdit má vždy datum
        if isinstance(widget, QSpinBox):
            return widget.value() < 1
        if widget is self.hromadny_uraz_ne:
            return not self._radio_value(self.hromadny_uraz_ano, self.hromadny_uraz_ne)
        return False

    def _mark_error(self, widget, error: bool):
        style = REQUIRED_STYLE if error else NORMAL_STYLE

        if widget is self.hromadny_uraz_ne:
            self.hromadny_uraz_ano.setStyleSheet(style)
            self.hromadny_uraz_ne.setStyleSheet(style)
            return

        widget.setStyleSheet(style)

    def validate(self) -> list[str]:
        errors = []

        for label, widget in self._required_widgets.items():
            error = self._is_empty(widget)
            self._mark_error(widget, error)
            if error:
                errors.append(label)

        return errors

    def focus_first_error(self):
        for widget in self._required_widgets.values():
            if self._is_empty(widget):
                if widget is self.hromadny_uraz_ne:
                    self.hromadny_uraz_ano.setFocus()
                else:
                    widget.setFocus()
                return

    def _format_time_value(self, value) -> str:
        text = str(value or "").strip()
        if not text:
            return ""

        # value může přijít jako "00:00:00.000000", "00:00:00" nebo "00:00"
        parts = text.split(":")
        if len(parts) >= 2:
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"

        return text

    def get_data(self) -> dict:
        return {
            "druh_urazu": self.druh_urazu.value(),
            "podezreni_trestny_cin": self._radio_value(self.podezreni_trestny_cin_ano, self.podezreni_trestny_cin_ne),
            "accident_date": self.get_accident_date(),
            "accident_time": self._format_time_value(self.accident_time.text()),
            "dpn_od": self.dpn_od.get_date(),
            "dpn_do": self.dpn_do.get_date(),
            "druh_zraneni": self.druh_zraneni.value(),
            "zranena_cast_tela": self.zranena_cast_tela.value(),
            "hromadny_uraz": self._radio_value(self.hromadny_uraz_ano, self.hromadny_uraz_ne),
            "celkovy_pocet_zranenych": self.celkovy_pocet_zranenych.value(),
            "cinnost_pri_urazu": self.cinnost_pri_urazu.value(),
            "misto_urazu": self.misto_urazu.toPlainText().strip(),
            "popis_urazoveho_deje": self.popis_urazoveho_deje.toPlainText().strip(),
            "druh_a_rozsah_zraneni": "",
        }

    def load_data(self, accident):
        self._injury_date_is_saved = getattr(accident, "id", None) is not None
        self._injury_date_baseline = getattr(accident, "accident_date", None)

        self.druh_urazu.set_value(accident.druh_urazu or "")
        self._set_radio_value(accident.podezreni_trestny_cin, self.podezreni_trestny_cin_ano, self.podezreni_trestny_cin_ne, default_no=True)

        if accident.accident_date:
            self.accident_date.set_date_iso(accident.accident_date.isoformat())

        self.accident_time.setText(self._format_time_value(accident.accident_time))
        self.dpn_od.set_date_value(accident.dpn_od)
        self.dpn_do.set_date_value(accident.dpn_do)
        self.druh_zraneni.set_value(accident.druh_zraneni or "")
        self.zranena_cast_tela.set_value(accident.zranena_cast_tela or "")
        self._set_radio_value(accident.hromadny_uraz, self.hromadny_uraz_ano, self.hromadny_uraz_ne, default_no=True)
        self.celkovy_pocet_zranenych.setValue(int(accident.celkovy_pocet_zranenych or 1))
        self.cinnost_pri_urazu.set_value(accident.cinnost_pri_urazu or "")
        self.misto_urazu.setPlainText(accident.misto_urazu or "")
        self.popis_urazoveho_deje.setPlainText(accident.popis_urazoveho_deje or "")
        self._refresh_dpn_duration()
        self.refresh_dpn_kind_warning(getattr(accident, "druh_urazu", "") or "")
        self.refresh_date_and_kind_hints()
