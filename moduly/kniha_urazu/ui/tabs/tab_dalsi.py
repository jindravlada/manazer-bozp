from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


REQUIRED_STYLE = "border: 2px solid #d32f2f; background: #fff6f6;"
NORMAL_STYLE = ""


class TabDalsiUdaje(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.kontrola_alkohol_ano = QRadioButton("ANO")
        self.kontrola_alkohol_ne = QRadioButton("NE")
        self.kontrola_alkohol_group = QButtonGroup(self)
        self.kontrola_alkohol_group.addButton(self.kontrola_alkohol_ano)
        self.kontrola_alkohol_group.addButton(self.kontrola_alkohol_ne)

        alkohol_layout = QHBoxLayout()
        alkohol_layout.addWidget(self.kontrola_alkohol_ano)
        alkohol_layout.addWidget(self.kontrola_alkohol_ne)
        alkohol_layout.addStretch()

        self.vysledek_kontroly_alkohol_pozitivni = QRadioButton("Pozitivní")
        self.vysledek_kontroly_alkohol_negativni = QRadioButton("Negativní")
        self.vysledek_kontroly_alkohol_group = QButtonGroup(self)
        self.vysledek_kontroly_alkohol_group.addButton(self.vysledek_kontroly_alkohol_pozitivni)
        self.vysledek_kontroly_alkohol_group.addButton(self.vysledek_kontroly_alkohol_negativni)

        alkohol_result_layout = QHBoxLayout()
        alkohol_result_layout.addWidget(self.vysledek_kontroly_alkohol_pozitivni)
        alkohol_result_layout.addWidget(self.vysledek_kontroly_alkohol_negativni)
        alkohol_result_layout.addStretch()

        self.mnozstvi_alkohol = QLineEdit()
        self.mnozstvi_alkohol.setPlaceholderText("Množství v promile ‰")

        self.kontrola_alkohol_duvod_neprovedeni = QLineEdit()
        self.kontrola_alkohol_duvod_neprovedeni.setPlaceholderText("Zadejte důvod neprovedení kontroly")

        self.kontrola_navykove_latky_ano = QRadioButton("ANO")
        self.kontrola_navykove_latky_ne = QRadioButton("NE")
        self.kontrola_navykove_latky_ne.setChecked(True)
        self.kontrola_navykove_latky_group = QButtonGroup(self)
        self.kontrola_navykove_latky_group.addButton(self.kontrola_navykove_latky_ano)
        self.kontrola_navykove_latky_group.addButton(self.kontrola_navykove_latky_ne)

        nl_layout = QHBoxLayout()
        nl_layout.addWidget(self.kontrola_navykove_latky_ano)
        nl_layout.addWidget(self.kontrola_navykove_latky_ne)
        nl_layout.addStretch()

        self.vysledek_kontroly_navykove_latky_pozitivni = QRadioButton("Pozitivní")
        self.vysledek_kontroly_navykove_latky_negativni = QRadioButton("Negativní")
        self.vysledek_kontroly_navykove_latky_group = QButtonGroup(self)
        self.vysledek_kontroly_navykove_latky_group.addButton(self.vysledek_kontroly_navykove_latky_pozitivni)
        self.vysledek_kontroly_navykove_latky_group.addButton(self.vysledek_kontroly_navykove_latky_negativni)

        nl_result_layout = QHBoxLayout()
        nl_result_layout.addWidget(self.vysledek_kontroly_navykove_latky_pozitivni)
        nl_result_layout.addWidget(self.vysledek_kontroly_navykove_latky_negativni)
        nl_result_layout.addStretch()

        self.navykove_latky_popis = QLineEdit()
        self.navykove_latky_popis.setPlaceholderText("Uveďte zjištěné návykové látky")

        self.kontrola_navykove_latky_duvod_neprovedeni = QLineEdit()
        self.kontrola_navykove_latky_duvod_neprovedeni.setPlaceholderText("Zadejte důvod neprovedení kontroly")

        self.porusene_predpisy = QTextEdit()
        self.porusene_predpisy.setFixedHeight(90)

        self.opatreni = QTextEdit()
        self.opatreni.setFixedHeight(90)

        self._required_widgets = {
            "Kontrola přítomnosti alkoholu": self.kontrola_alkohol_ano,
            "Předpisy, které byly porušeny a kým": self.porusene_predpisy,
            "Přijatá opatření k zabránění opakování úrazu": self.opatreni,
        }

        self._add_required_row(form, "Kontrola přítomnosti alkoholu:", alkohol_layout)
        form.addRow("Výsledek kontroly alkoholu:", alkohol_result_layout)
        form.addRow("Množství v promile (‰):", self.mnozstvi_alkohol)
        form.addRow("Důvod neprovedení kontroly alkoholu:", self.kontrola_alkohol_duvod_neprovedeni)

        form.addRow("Kontrola návykových látek:", nl_layout)
        form.addRow("Výsledek kontroly NL:", nl_result_layout)
        form.addRow("Zjištěné návykové látky:", self.navykove_latky_popis)
        form.addRow("Důvod neprovedení kontroly NL:", self.kontrola_navykove_latky_duvod_neprovedeni)

        self._add_required_row(form, "Předpisy, které byly porušeny a kým:", self.porusene_predpisy)
        self._add_required_row(form, "Přijatá opatření k zabránění opakování úrazu:", self.opatreni)

        layout.addLayout(form)
        layout.addStretch()

        for widget in [
            self.kontrola_alkohol_ano,
            self.kontrola_alkohol_ne,
            self.vysledek_kontroly_alkohol_pozitivni,
            self.vysledek_kontroly_alkohol_negativni,
            self.kontrola_navykove_latky_ano,
            self.kontrola_navykove_latky_ne,
            self.vysledek_kontroly_navykove_latky_pozitivni,
            self.vysledek_kontroly_navykove_latky_negativni,
        ]:
            widget.toggled.connect(self._refresh_visibility)

        self._refresh_visibility()

    def _add_required_row(self, form: QFormLayout, label_text: str, widget_or_layout):
        label = QLabel(f"<b>{label_text}</b>")
        form.addRow(label, widget_or_layout)

    def _radio_value(self, yes_button: QRadioButton, no_button: QRadioButton) -> str:
        if yes_button.isChecked():
            return "ANO"
        if no_button.isChecked():
            return "NE"
        return ""

    def _radio_result(self, positive_button: QRadioButton, negative_button: QRadioButton) -> str:
        if positive_button.isChecked():
            return "Pozitivní"
        if negative_button.isChecked():
            return "Negativní"
        return ""

    def _set_radio_value(self, value: str, yes_button: QRadioButton, no_button: QRadioButton, default_no: bool = False):
        value = (value or "").strip().upper()
        yes_button.setChecked(value == "ANO")
        no_button.setChecked(value == "NE" or (default_no and not value))

    def _set_radio_result(self, value: str, positive_button: QRadioButton, negative_button: QRadioButton):
        value = (value or "").strip().lower()
        positive_button.setChecked(value == "pozitivní" or value == "pozitivni")
        negative_button.setChecked(value == "negativní" or value == "negativni")

    def _refresh_visibility(self):
        alkohol = self._radio_value(self.kontrola_alkohol_ano, self.kontrola_alkohol_ne)
        alkohol_pozitivni = self.vysledek_kontroly_alkohol_pozitivni.isChecked()

        self.vysledek_kontroly_alkohol_pozitivni.setVisible(alkohol == "ANO")
        self.vysledek_kontroly_alkohol_negativni.setVisible(alkohol == "ANO")
        self.mnozstvi_alkohol.setVisible(alkohol == "ANO" and alkohol_pozitivni)
        self.kontrola_alkohol_duvod_neprovedeni.setVisible(alkohol == "NE")

        nl = self._radio_value(self.kontrola_navykove_latky_ano, self.kontrola_navykove_latky_ne)
        nl_pozitivni = self.vysledek_kontroly_navykove_latky_pozitivni.isChecked()

        self.vysledek_kontroly_navykove_latky_pozitivni.setVisible(nl == "ANO")
        self.vysledek_kontroly_navykove_latky_negativni.setVisible(nl == "ANO")
        self.navykove_latky_popis.setVisible(nl == "ANO" and nl_pozitivni)
        self.kontrola_navykove_latky_duvod_neprovedeni.setVisible(nl == "NE")

    def _is_empty(self, widget) -> bool:
        if widget is self.kontrola_alkohol_ano:
            return not self._radio_value(self.kontrola_alkohol_ano, self.kontrola_alkohol_ne)
        if isinstance(widget, QTextEdit):
            return not widget.toPlainText().strip()
        return False

    def _mark_error(self, widget, error: bool):
        style = REQUIRED_STYLE if error else NORMAL_STYLE
        if widget is self.kontrola_alkohol_ano:
            self.kontrola_alkohol_ano.setStyleSheet(style)
            self.kontrola_alkohol_ne.setStyleSheet(style)
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
                widget.setFocus()
                return

    def get_data(self) -> dict:
        return {
            "kontrola_alkohol": self._radio_value(self.kontrola_alkohol_ano, self.kontrola_alkohol_ne),
            "kontrola_alkohol_duvod_neprovedeni": self.kontrola_alkohol_duvod_neprovedeni.text().strip(),
            "vysledek_kontroly_alkohol": self._radio_result(self.vysledek_kontroly_alkohol_pozitivni, self.vysledek_kontroly_alkohol_negativni),
            "mnozstvi_alkohol": self.mnozstvi_alkohol.text().strip(),
            "kontrola_navykove_latky": self._radio_value(self.kontrola_navykove_latky_ano, self.kontrola_navykove_latky_ne),
            "kontrola_navykove_latky_duvod_neprovedeni": self.kontrola_navykove_latky_duvod_neprovedeni.text().strip(),
            "vysledek_kontroly_navykove_latky": self._radio_result(self.vysledek_kontroly_navykove_latky_pozitivni, self.vysledek_kontroly_navykove_latky_negativni),
            "navykove_latky_popis": self.navykove_latky_popis.text().strip(),
            "porusene_predpisy": self.porusene_predpisy.toPlainText().strip(),
            "opatreni": self.opatreni.toPlainText().strip(),
        }

    def load_data(self, accident):
        self._set_radio_value(accident.kontrola_alkohol, self.kontrola_alkohol_ano, self.kontrola_alkohol_ne)
        self.kontrola_alkohol_duvod_neprovedeni.setText(accident.kontrola_alkohol_duvod_neprovedeni or "")
        self._set_radio_result(accident.vysledek_kontroly_alkohol, self.vysledek_kontroly_alkohol_pozitivni, self.vysledek_kontroly_alkohol_negativni)
        self.mnozstvi_alkohol.setText(accident.mnozstvi_alkohol or "")

        self._set_radio_value(accident.kontrola_navykove_latky, self.kontrola_navykove_latky_ano, self.kontrola_navykove_latky_ne, default_no=True)
        self.kontrola_navykove_latky_duvod_neprovedeni.setText(accident.kontrola_navykove_latky_duvod_neprovedeni or "")
        self._set_radio_result(accident.vysledek_kontroly_navykove_latky, self.vysledek_kontroly_navykove_latky_pozitivni, self.vysledek_kontroly_navykove_latky_negativni)
        self.navykove_latky_popis.setText(accident.navykove_latky_popis or "")

        self.porusene_predpisy.setPlainText(accident.porusene_predpisy or "")
        self.opatreni.setPlainText(accident.opatreni or "")

        self._refresh_visibility()
