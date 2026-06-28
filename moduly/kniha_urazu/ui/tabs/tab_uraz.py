from datetime import date

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.code_selector import CodeSelector
from core.widgets.date_edit import DateEdit
from core.widgets.multi_code_selector import MultiCodeSelector
from moduly.kniha_urazu.services.ciselnik_service import kniha_urazu_ciselnik_service


REQUIRED_STYLE = "border: 2px solid #d32f2f; background: #fff6f6;"
NORMAL_STYLE = ""


class TabUraz(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

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
        self.accident_time = QLineEdit()
        self.accident_time.setPlaceholderText("HH:MM")

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
        self._add_required_row(form, "Datum úrazu:", self.accident_date)
        self._add_required_row(form, "Čas úrazu:", self.accident_time)
        self._add_required_row(form, "Druh zranění:", self.druh_zraneni)
        self._add_required_row(form, "Zraněná část těla:", self.zranena_cast_tela)
        self._add_required_row(form, "Hromadný úraz:", hromadny_layout)
        self._add_required_row(form, "Počet zraněných osob celkem:", self.celkovy_pocet_zranenych)
        self._add_required_row(form, "Činnost, při které k úrazu došlo:", self.cinnost_pri_urazu)
        self._add_required_row(form, "Místo úrazu:", self.misto_urazu)
        self._add_required_row(form, "Popis úrazového děje, místa, příčin a okolností:", self.popis_urazoveho_deje)

        layout.addLayout(form)
        layout.addStretch()

    def _add_required_row(self, form: QFormLayout, label_text: str, widget_or_layout):
        label = QLabel(f"<b>{label_text}</b>")
        form.addRow(label, widget_or_layout)

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
        qdate = self.accident_date.date()

        return {
            "druh_urazu": self.druh_urazu.value(),
            "podezreni_trestny_cin": self._radio_value(self.podezreni_trestny_cin_ano, self.podezreni_trestny_cin_ne),
            "accident_date": date(qdate.year(), qdate.month(), qdate.day()),
            "accident_time": self._format_time_value(self.accident_time.text()),
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
        self.druh_urazu.set_value(accident.druh_urazu or "")
        self._set_radio_value(accident.podezreni_trestny_cin, self.podezreni_trestny_cin_ano, self.podezreni_trestny_cin_ne, default_no=True)

        if accident.accident_date:
            self.accident_date.set_date_iso(accident.accident_date.isoformat())

        self.accident_time.setText(self._format_time_value(accident.accident_time))
        self.druh_zraneni.set_value(accident.druh_zraneni or "")
        self.zranena_cast_tela.set_value(accident.zranena_cast_tela or "")
        self._set_radio_value(accident.hromadny_uraz, self.hromadny_uraz_ano, self.hromadny_uraz_ne, default_no=True)
        self.celkovy_pocet_zranenych.setValue(int(accident.celkovy_pocet_zranenych or 1))
        self.cinnost_pri_urazu.set_value(accident.cinnost_pri_urazu or "")
        self.misto_urazu.setPlainText(accident.misto_urazu or "")
        self.popis_urazoveho_deje.setPlainText(accident.popis_urazoveho_deje or "")
