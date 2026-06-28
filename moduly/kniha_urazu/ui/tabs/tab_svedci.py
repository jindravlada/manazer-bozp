from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCompleter,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.person_selector import PersonSelector
from moduly.nastaveni.sluzby.settings_service import settings_service


REQUIRED_STYLE = "border: 2px solid #d32f2f; background: #fff6f6;"
NORMAL_STYLE = ""


class TabSvedci(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.svedci_ano = QRadioButton("ANO")
        self.svedci_ne = QRadioButton("NE")
        self.svedci_ne.setChecked(True)

        self.svedci_group = QButtonGroup(self)
        self.svedci_group.addButton(self.svedci_ano)
        self.svedci_group.addButton(self.svedci_ne)

        svedci_radio_layout = QHBoxLayout()
        svedci_radio_layout.addWidget(self.svedci_ano)
        svedci_radio_layout.addWidget(self.svedci_ne)
        svedci_radio_layout.addStretch()

        self.svedek_input = QLineEdit()
        self.svedek_input.setPlaceholderText("Jméno svědka")
        self._setup_svedek_completer()

        self.btn_add_svedek = QPushButton("Přidat")
        self.btn_remove_svedek = QPushButton("Odebrat")

        add_layout = QHBoxLayout()
        add_layout.addWidget(self.svedek_input, 1)
        add_layout.addWidget(self.btn_add_svedek)
        add_layout.addWidget(self.btn_remove_svedek)

        self.svedci_list = QListWidget()
        self.svedci_list.setMinimumHeight(90)

        self.svedci_info = QLabel("Nebyl zjištěn žádný svědek")
        self.svedci_info.setStyleSheet("color: #666; font-style: italic;")

        self.vyjadreni_svedku = QTextEdit()
        self.vyjadreni_svedku.setFixedHeight(90)

        self.vyjadreni_oo = QTextEdit()
        self.vyjadreni_oo.setFixedHeight(70)

        self.zapsal_jmeno = PersonSelector()
        self.zapsal_jmeno.setEditable(True)
        self.zapsal_jmeno.currentIndexChanged.connect(self._vedouci_changed)

        self.zapsal_pracovni_zarazeni = QLineEdit()
        self.zapsal_pracovni_zarazeni.setReadOnly(True)

        self.poznamka = QTextEdit()
        self.poznamka.setFixedHeight(90)

        self._required_widgets = {
            "Byli přítomni svědci": self.svedci_ne,
            "Jména svědků úrazu": self.svedci_list,
            "Vyjádření svědků a postiženého zaměstnance": self.vyjadreni_svedku,
            "Vyjádření zástupce OO": self.vyjadreni_oo,
            "Vedoucí zaměstnanec postiženého": self.zapsal_jmeno,
            "Pracovní zařazení vedoucího zaměstnance": self.zapsal_pracovni_zarazeni,
        }

        self._add_required_row(form, "Byli přítomni svědci:", svedci_radio_layout)
        form.addRow("", self.svedci_info)
        form.addRow("Jméno svědka:", add_layout)
        form.addRow("Seznam svědků:", self.svedci_list)
        self._add_required_row(form, "Vyjádření svědků a postiženého zaměstnance:", self.vyjadreni_svedku)
        self._add_required_row(form, "Vyjádření zástupce OO:", self.vyjadreni_oo)
        self._add_required_row(form, "Vedoucí zaměstnanec postiženého:", self.zapsal_jmeno)
        self._add_required_row(form, "Pracovní zařazení vedoucího zaměstnance:", self.zapsal_pracovni_zarazeni)
        form.addRow("Interní poznámka:", self.poznamka)

        layout.addLayout(form)
        layout.addStretch()

        self.svedci_ano.toggled.connect(self._refresh_visibility)
        self.svedci_ne.toggled.connect(self._refresh_visibility)
        self.btn_add_svedek.clicked.connect(self.add_svedek)
        self.btn_remove_svedek.clicked.connect(self.remove_svedek)
        self.svedek_input.returnPressed.connect(self.add_svedek)

        self._refresh_visibility()

    def _setup_svedek_completer(self):
        workers = settings_service.get_workers(include_inactive=False)
        values = [worker.display_name for worker in workers]
        completer = QCompleter(values, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.svedek_input.setCompleter(completer)

    def _add_required_row(self, form: QFormLayout, label_text: str, widget_or_layout):
        label = QLabel(f"<b>{label_text}</b>")
        form.addRow(label, widget_or_layout)

    def _svedci_value(self) -> str:
        if self.svedci_ano.isChecked():
            return "ANO"
        if self.svedci_ne.isChecked():
            return "NE"
        return ""

    def _set_svedci_value(self, value: str):
        value = (value or "").strip().upper()
        self.svedci_ano.setChecked(value == "ANO")
        self.svedci_ne.setChecked(value == "NE" or not value)
        self._refresh_visibility()

    def _refresh_visibility(self):
        visible = self.svedci_ano.isChecked()

        self.svedek_input.setVisible(visible)
        self.btn_add_svedek.setVisible(visible)
        self.btn_remove_svedek.setVisible(visible)
        self.svedci_list.setVisible(visible)
        self.svedci_info.setVisible(not visible)

    def add_svedek(self):
        value = self.svedek_input.text().strip()
        if not value:
            return

        values = self._svedci_list_values()
        if value not in values:
            self.svedci_list.addItem(value)

        self.svedek_input.clear()

    def remove_svedek(self):
        for item in self.svedci_list.selectedItems():
            row = self.svedci_list.row(item)
            self.svedci_list.takeItem(row)

    def _svedci_list_values(self) -> list[str]:
        return [self.svedci_list.item(i).text() for i in range(self.svedci_list.count())]

    def _vedouci_changed(self):
        person_id = self.zapsal_jmeno.current_person_id()
        person = settings_service.get_worker_by_id(person_id) if person_id else None

        if person is None:
            self.zapsal_pracovni_zarazeni.clear()
            return

        self.zapsal_pracovni_zarazeni.setText(person.position or "")

    def _is_empty(self, widget) -> bool:
        if widget is self.svedci_ne:
            return not self._svedci_value()
        if widget is self.svedci_list:
            return self.svedci_ano.isChecked() and self.svedci_list.count() == 0
        if isinstance(widget, QTextEdit):
            return not widget.toPlainText().strip()
        if isinstance(widget, QLineEdit):
            return not widget.text().strip()
        if isinstance(widget, PersonSelector):
            return not widget.currentText().strip()
        return False

    def _mark_error(self, widget, error: bool):
        style = REQUIRED_STYLE if error else NORMAL_STYLE

        if widget is self.svedci_ne:
            self.svedci_ano.setStyleSheet(style)
            self.svedci_ne.setStyleSheet(style)
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
        if self.svedci_ne.isChecked():
            svedci = "Nebyl zjištěn žádný svědek"
        else:
            svedci = "; ".join(self._svedci_list_values())

        return {
            "svedci": svedci,
            "vyjadreni_svedku": self.vyjadreni_svedku.toPlainText().strip(),
            "vyjadreni_oo": self.vyjadreni_oo.toPlainText().strip(),
            "zapsal_jmeno": self.zapsal_jmeno.currentText().strip(),
            "zapsal_pracovni_zarazeni": self.zapsal_pracovni_zarazeni.text().strip(),
            "poznamka": self.poznamka.toPlainText().strip(),
        }

    def load_data(self, accident):
        svedci = accident.svedci or ""

        if svedci and svedci != "Nebyl zjištěn žádný svědek":
            self._set_svedci_value("ANO")
            self.svedci_list.clear()
            for item in [part.strip() for part in svedci.split(";") if part.strip()]:
                self.svedci_list.addItem(item)
        else:
            self._set_svedci_value("NE")

        self.vyjadreni_svedku.setPlainText(accident.vyjadreni_svedku or "")
        self.vyjadreni_oo.setPlainText(accident.vyjadreni_oo or "")

        if accident.zapsal_jmeno:
            index = self.zapsal_jmeno.findText(accident.zapsal_jmeno, Qt.MatchFixedString)
            if index >= 0:
                self.zapsal_jmeno.setCurrentIndex(index)
            else:
                self.zapsal_jmeno.setEditText(accident.zapsal_jmeno)

        self.zapsal_pracovni_zarazeni.setText(accident.zapsal_pracovni_zarazeni or "")
        self.poznamka.setPlainText(accident.poznamka or "")

        self._refresh_visibility()
