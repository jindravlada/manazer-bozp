from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QMessageBox,
    QCompleter,
)

from core.services.ares_service import ares_service
from core.services.cz_nace_service import cz_nace_service
from core.utils.czech_sort import czech_sorted, person_display_name_sort_key
from core.widgets.code_selector import CodeSelector
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.nastaveni.sluzby.settings_service import settings_service


class TabZapisovatelZamestnavatel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.datum_zapisu = NullableDateEdit()

        self.zapisovatel = ThpWorkerSelector()
        self.zapisovatel.setEditable(True)
        self._setup_person_completer()
        self.zapisovatel.currentIndexChanged.connect(self._zapisovatel_changed)
        self.zapisovatel.editTextChanged.connect(self._zapisovatel_text_changed)

        self.podatel_pracovni_zarazeni = QLineEdit()
        self.podatel_email = QLineEdit()
        self.podatel_telefon = QLineEdit()

        for widget in [
            self.podatel_pracovni_zarazeni,
            self.podatel_email,
            self.podatel_telefon,
        ]:
            widget.setReadOnly(True)

        self.zamestnavatel_nazev = QLineEdit()
        self.zamestnavatel_ico = QLineEdit()
        self.zamestnavatel_adresa = QTextEdit()
        self.zamestnavatel_adresa.setFixedHeight(70)
        self.hlavni_cinnost_zamestnavatele = CodeSelector(czech_sorted(cz_nace_service.get_all_displays()))

        for widget in [
            self.zamestnavatel_nazev,
            self.zamestnavatel_ico,
            self.hlavni_cinnost_zamestnavatele,
        ]:
            widget.setEnabled(False)

        self.zamestnavatel_adresa.setReadOnly(True)

        self.vrchni_dozor_oip = QRadioButton("OIP")
        self.vrchni_dozor_obu = QRadioButton("OBÚ")
        self.vrchni_dozor_group = QButtonGroup(self)
        self.vrchni_dozor_group.addButton(self.vrchni_dozor_oip)
        self.vrchni_dozor_group.addButton(self.vrchni_dozor_obu)

        dozor_layout = QHBoxLayout()
        dozor_layout.addWidget(self.vrchni_dozor_oip)
        dozor_layout.addWidget(self.vrchni_dozor_obu)
        dozor_layout.addStretch()

        self.dalsi_zamestnavatel_typ = QComboBox()
        self.dalsi_zamestnavatel_typ.addItems([
            "",
            "Úraz cizího zaměstnance na našem pracovišti",
            "Úraz našeho zaměstnance na cizím pracovišti",
            "Jiné",
        ])

        ico_layout = QHBoxLayout()
        self.dalsi_zamestnavatel_ico = QLineEdit()
        self.btn_load_dalsi_ares = QPushButton("Načíst z ARES")
        self.btn_load_dalsi_ares.clicked.connect(self.load_dalsi_from_ares)
        ico_layout.addWidget(self.dalsi_zamestnavatel_ico)
        ico_layout.addWidget(self.btn_load_dalsi_ares)

        self.dalsi_zamestnavatel_nazev = QLineEdit()
        self.dalsi_zamestnavatel_adresa = QTextEdit()
        self.dalsi_zamestnavatel_adresa.setFixedHeight(70)
        self.dalsi_zamestnavatel_cinnost = CodeSelector(czech_sorted(cz_nace_service.get_all_displays()))
        self.dalsi_zamestnavatel_cinnost.set_value("")
        self.dalsi_zamestnavatel_poznamka = QTextEdit()
        self.dalsi_zamestnavatel_poznamka.setFixedHeight(60)

        form.addRow("Datum zápisu:", self.datum_zapisu)

        form.addRow(QLabel("<b>Zapisovatel</b>"))
        form.addRow("Jméno:", self.zapisovatel)
        form.addRow("Pracovní zařazení:", self.podatel_pracovni_zarazeni)
        form.addRow("E-mail:", self.podatel_email)
        form.addRow("Telefon:", self.podatel_telefon)

        form.addRow(QLabel("<b>Zaměstnavatel</b>"))
        form.addRow("Název:", self.zamestnavatel_nazev)
        form.addRow("IČO:", self.zamestnavatel_ico)
        form.addRow("Adresa:", self.zamestnavatel_adresa)
        form.addRow("Hlavní činnost:", self.hlavni_cinnost_zamestnavatele)
        form.addRow("Vrchní dozor:", dozor_layout)

        form.addRow(QLabel("<b>Další zaměstnavatel</b>"))
        form.addRow("Situace:", self.dalsi_zamestnavatel_typ)
        form.addRow("IČO:", ico_layout)
        form.addRow("Název:", self.dalsi_zamestnavatel_nazev)
        form.addRow("Adresa:", self.dalsi_zamestnavatel_adresa)
        form.addRow("Hlavní/ekonomická činnost:", self.dalsi_zamestnavatel_cinnost)
        form.addRow("Poznámka:", self.dalsi_zamestnavatel_poznamka)

        layout.addLayout(form)
        layout.addStretch()

        self.load_employer_from_settings()

    def showEvent(self, event):
        super().showEvent(event)
        self.load_employer_from_settings()

    def _setup_person_completer(self):
        values = [
            self.zapisovatel.itemText(i)
            for i in range(self.zapisovatel.count())
            if self.zapisovatel.itemText(i)
        ]
        values = czech_sorted(values, key=person_display_name_sort_key)

        completer = QCompleter(values, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.zapisovatel.setCompleter(completer)

    def _zapisovatel_text_changed(self):
        index = self.zapisovatel.findText(self.zapisovatel.currentText(), Qt.MatchFixedString)
        if index >= 0:
            self.zapisovatel.setCurrentIndex(index)

    def _zapisovatel_changed(self):
        person_id = self.zapisovatel.current_person_id()
        person = settings_service.get_worker_by_id(person_id) if person_id else None

        if person is None:
            self.podatel_pracovni_zarazeni.clear()
            self.podatel_email.clear()
            self.podatel_telefon.clear()
            return

        self.podatel_pracovni_zarazeni.setText(person.position or "")
        self.podatel_email.setText(person.email or "")
        self.podatel_telefon.setText(person.phone or "")

    def load_employer_from_settings(self):
        employer = settings_service.get_employer()
        if employer is None:
            self.zamestnavatel_nazev.setText("Není vyplněno v Nastavení")
            self.zamestnavatel_ico.clear()
            self.zamestnavatel_adresa.clear()
            self.hlavni_cinnost_zamestnavatele.set_value("")
            return

        self.zamestnavatel_nazev.setText(getattr(employer, "name", "") or "")
        self.zamestnavatel_ico.setText(getattr(employer, "ico", "") or "")
        self.zamestnavatel_adresa.setPlainText(getattr(employer, "address", "") or "")

        nace = (
            getattr(employer, "nace", "")
            or getattr(employer, "cz_nace", "")
            or getattr(employer, "main_activity", "")
            or ""
        )
        self.hlavni_cinnost_zamestnavatele.set_value(nace)

    def load_dalsi_from_ares(self):
        ico = self.dalsi_zamestnavatel_ico.text().strip()
        if not ico:
            QMessageBox.information(self, "ARES", "Zadejte IČO dalšího zaměstnavatele.")
            return

        try:
            data = ares_service.find_by_ico(ico)
        except Exception as exc:
            QMessageBox.warning(self, "ARES", f"Nepodařilo se načíst data z ARES.\n\n{exc}")
            return

        if not data:
            QMessageBox.information(self, "ARES", "Záznam nebyl nalezen.")
            return

        self.dalsi_zamestnavatel_ico.setText(data.get("ico", ico))
        self.dalsi_zamestnavatel_nazev.setText(data.get("name", ""))
        self.dalsi_zamestnavatel_adresa.setPlainText(data.get("address", ""))

        nace_list = data.get("nace_list") or []
        if nace_list:
            self.dalsi_zamestnavatel_cinnost.set_values(czech_sorted(nace_list))
            self.dalsi_zamestnavatel_cinnost.set_value(data.get("nace", nace_list[0]))
        else:
            self.dalsi_zamestnavatel_cinnost.set_value(data.get("nace", ""))

    def get_vrchni_dozor(self) -> str:
        if self.vrchni_dozor_oip.isChecked():
            return "OIP"
        if self.vrchni_dozor_obu.isChecked():
            return "OBÚ"
        return ""

    def set_vrchni_dozor(self, value: str):
        value = value or ""
        self.vrchni_dozor_oip.setChecked(value == "OIP")
        self.vrchni_dozor_obu.setChecked(value == "OBÚ")

    def get_data(self) -> dict:
        self.load_employer_from_settings()

        return {
            "datum_zapisu": self.datum_zapisu.get_date(),
            "podatel_jmeno": self.zapisovatel.currentText().strip(),
            "podatel_email": self.podatel_email.text().strip(),
            "podatel_telefon": self.podatel_telefon.text().strip(),
            "podatel_pracovni_zarazeni": self.podatel_pracovni_zarazeni.text().strip(),
            "zamestnavatel_nazev": self.zamestnavatel_nazev.text().strip(),
            "zamestnavatel_ico": self.zamestnavatel_ico.text().strip(),
            "zamestnavatel_adresa": self.zamestnavatel_adresa.toPlainText().strip(),
            "vrchni_dozor": self.get_vrchni_dozor(),
            "hlavni_cinnost_zamestnavatele": self.hlavni_cinnost_zamestnavatele.value(),
            "dalsi_zamestnavatel_typ": self.dalsi_zamestnavatel_typ.currentText().strip(),
            "dalsi_zamestnavatel_nazev": self.dalsi_zamestnavatel_nazev.text().strip(),
            "dalsi_zamestnavatel_ico": self.dalsi_zamestnavatel_ico.text().strip(),
            "dalsi_zamestnavatel_adresa": self.dalsi_zamestnavatel_adresa.toPlainText().strip(),
            "dalsi_zamestnavatel_cinnost": self.dalsi_zamestnavatel_cinnost.value(),
            "dalsi_zamestnavatel_poznamka": self.dalsi_zamestnavatel_poznamka.toPlainText().strip(),
        }

    def load_data(self, accident):
        self.datum_zapisu.set_date_value(accident.datum_zapisu)

        if accident.podatel_jmeno:
            index = self.zapisovatel.findText(accident.podatel_jmeno, Qt.MatchFixedString)
            if index >= 0:
                self.zapisovatel.setCurrentIndex(index)
            else:
                self.zapisovatel.setEditText(accident.podatel_jmeno)

        self.podatel_email.setText(accident.podatel_email or "")
        self.podatel_telefon.setText(accident.podatel_telefon or "")
        self.podatel_pracovni_zarazeni.setText(accident.podatel_pracovni_zarazeni or "")

        self.load_employer_from_settings()
        self.set_vrchni_dozor(accident.vrchni_dozor)

        self.dalsi_zamestnavatel_typ.setCurrentText(accident.dalsi_zamestnavatel_typ or "")
        self.dalsi_zamestnavatel_nazev.setText(accident.dalsi_zamestnavatel_nazev or "")
        self.dalsi_zamestnavatel_ico.setText(accident.dalsi_zamestnavatel_ico or "")
        self.dalsi_zamestnavatel_adresa.setPlainText(accident.dalsi_zamestnavatel_adresa or "")
        self.dalsi_zamestnavatel_cinnost.set_value(accident.dalsi_zamestnavatel_cinnost or "")
        self.dalsi_zamestnavatel_poznamka.setPlainText(accident.dalsi_zamestnavatel_poznamka or "")


    def validate(self):
        errors=[]
        # zapisovatel
        if not self.zapisovatel.currentText().strip():
            self.zapisovatel.setStyleSheet("border:2px solid #d32f2f;")
            errors.append("Zapisovatel")
        else:
            self.zapisovatel.setStyleSheet("")
        if not self.get_vrchni_dozor():
            self.vrchni_dozor_oip.setStyleSheet("color:#d32f2f;font-weight:bold;")
            self.vrchni_dozor_obu.setStyleSheet("color:#d32f2f;font-weight:bold;")
            errors.append("Vrchní dozor")
        else:
            self.vrchni_dozor_oip.setStyleSheet("")
            self.vrchni_dozor_obu.setStyleSheet("")
        return errors

    def focus_first_error(self):
        if not self.zapisovatel.currentText().strip():
            self.zapisovatel.setFocus()
            return
        if not self.get_vrchni_dozor():
            self.vrchni_dozor_oip.setFocus()
            return
