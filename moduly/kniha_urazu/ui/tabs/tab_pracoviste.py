from PySide6.QtWidgets import (
    QButtonGroup,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.services.ares_service import ares_service
from core.widgets.code_selector import CodeSelector
from core.widgets.multi_code_selector import MultiCodeSelector
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.kniha_urazu.services.ciselnik_service import kniha_urazu_ciselnik_service


REQUIRED_STYLE = "border: 2px solid #d32f2f; background: #fff6f6;"
NORMAL_STYLE = ""


class TabPracoviste(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.workplace = WorkplaceSelector()
        self.charakteristika_pracoviste = CodeSelector(kniha_urazu_ciselnik_service.charakteristika_pracoviste())
        self.charakteristika_pracoviste.set_value("")

        self.zdroj_urazu = MultiCodeSelector(kniha_urazu_ciselnik_service.zdroj_urazu())
        self.pricina_urazu = MultiCodeSelector(kniha_urazu_ciselnik_service.pricina_urazu())

        self.uraz_pracoviste_zamestnavatele_ano = QRadioButton("ANO")
        self.uraz_pracoviste_zamestnavatele_ne = QRadioButton("NE")
        self.uraz_pracoviste_zamestnavatele_ano.setChecked(True)

        self.uraz_pracoviste_zamestnavatele_group = QButtonGroup(self)
        self.uraz_pracoviste_zamestnavatele_group.addButton(self.uraz_pracoviste_zamestnavatele_ano)
        self.uraz_pracoviste_zamestnavatele_group.addButton(self.uraz_pracoviste_zamestnavatele_ne)

        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.uraz_pracoviste_zamestnavatele_ano)
        radio_layout.addWidget(self.uraz_pracoviste_zamestnavatele_ne)
        radio_layout.addStretch()

        self.ico_subjektu = QLineEdit()
        self.btn_ares = QPushButton("Načíst z ARES")
        self.btn_ares.clicked.connect(self.load_from_ares)

        ico_layout = QHBoxLayout()
        ico_layout.addWidget(self.ico_subjektu)
        ico_layout.addWidget(self.btn_ares)

        self.adresa_sidla_subjektu = QTextEdit()
        self.adresa_sidla_subjektu.setFixedHeight(60)

        self.ekonomicka_cinnost_subjektu = CodeSelector([])
        self.adresa_pracoviste = QTextEdit()
        self.adresa_pracoviste.setFixedHeight(60)

        self.okres_pracoviste = CodeSelector(kniha_urazu_ciselnik_service.okresy())
        self.okres_pracoviste.set_value("")

        self.popis_pracoviste = QTextEdit()
        self.popis_pracoviste.setFixedHeight(80)

        self._foreign_widgets = [
            self.ico_subjektu,
            self.btn_ares,
            self.adresa_sidla_subjektu,
            self.ekonomicka_cinnost_subjektu,
            self.adresa_pracoviste,
            self.okres_pracoviste,
            self.popis_pracoviste,
        ]

        self._required_widgets = {
            "Pracoviště": self.workplace,
            "Charakteristika pracoviště": self.charakteristika_pracoviste,
            "Zdroj pracovního úrazu": self.zdroj_urazu,
            "Příčina pracovního úrazu": self.pricina_urazu,
            "Úraz na pracovišti zaměstnavatele": self.uraz_pracoviste_zamestnavatele_ano,
        }

        self._add_required_row(form, "Pracoviště:", self.workplace)
        self._add_required_row(form, "Charakteristika pracoviště:", self.charakteristika_pracoviste)
        self._add_required_row(form, "Zdroj pracovního úrazu:", self.zdroj_urazu)
        self._add_required_row(form, "Příčina pracovního úrazu:", self.pricina_urazu)
        self._add_required_row(form, "Úraz na pracovišti zaměstnavatele:", radio_layout)

        form.addRow(QLabel("<b>Údaje o cizím pracovišti / subjektu</b>"))
        form.addRow("IČO:", ico_layout)
        form.addRow("Adresa sídla:", self.adresa_sidla_subjektu)
        form.addRow("Ekonomická činnost:", self.ekonomicka_cinnost_subjektu)
        form.addRow("Adresa pracoviště:", self.adresa_pracoviste)
        form.addRow("Okres:", self.okres_pracoviste)
        form.addRow("Popis pracoviště:", self.popis_pracoviste)

        layout.addLayout(form)
        layout.addStretch()

        self.uraz_pracoviste_zamestnavatele_ano.toggled.connect(self._refresh_visibility)
        self.uraz_pracoviste_zamestnavatele_ne.toggled.connect(self._refresh_visibility)
        self._refresh_visibility()

    def _add_required_row(self, form: QFormLayout, label_text: str, widget_or_layout):
        label = QLabel(f"<b>{label_text}</b>")
        form.addRow(label, widget_or_layout)

    def _is_foreign_workplace(self) -> bool:
        return self.uraz_pracoviste_zamestnavatele_ne.isChecked()

    def _refresh_visibility(self):
        visible = self._is_foreign_workplace()
        for widget in self._foreign_widgets:
            widget.setVisible(visible)

    def _radio_value(self) -> str:
        if self.uraz_pracoviste_zamestnavatele_ano.isChecked():
            return "ANO"
        if self.uraz_pracoviste_zamestnavatele_ne.isChecked():
            return "NE"
        return ""

    def _set_radio_value(self, value: str):
        value = (value or "").strip().upper()
        self.uraz_pracoviste_zamestnavatele_ano.setChecked(value == "ANO" or not value)
        self.uraz_pracoviste_zamestnavatele_ne.setChecked(value == "NE")
        self._refresh_visibility()

    def _is_empty(self, widget) -> bool:
        if isinstance(widget, WorkplaceSelector):
            return not widget.display_text()
        if isinstance(widget, CodeSelector):
            return not widget.value().strip()
        if isinstance(widget, MultiCodeSelector):
            return not widget.has_value()
        if widget is self.uraz_pracoviste_zamestnavatele_ano:
            return not self._radio_value()
        return False

    def _mark_error(self, widget, error: bool):
        style = REQUIRED_STYLE if error else NORMAL_STYLE
        if widget is self.uraz_pracoviste_zamestnavatele_ano:
            self.uraz_pracoviste_zamestnavatele_ano.setStyleSheet(style)
            self.uraz_pracoviste_zamestnavatele_ne.setStyleSheet(style)
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

    def load_from_ares(self):
        ico = self.ico_subjektu.text().strip()
        if not ico:
            QMessageBox.information(self, "ARES", "Zadejte IČO.")
            return

        try:
            data = ares_service.find_by_ico(ico)
        except Exception as exc:
            QMessageBox.warning(self, "ARES", f"Nepodařilo se načíst data z ARES.\n\n{exc}")
            return

        if not data:
            QMessageBox.information(self, "ARES", "Záznam nebyl nalezen.")
            return

        self.ico_subjektu.setText(data.get("ico", ico))
        self.adresa_sidla_subjektu.setPlainText(data.get("address", ""))

        nace_list = data.get("nace_list") or []
        main = str(data.get("nace") or "").strip()
        if not main and len(nace_list) == 1:
            main = str(nace_list[0]).strip()
        if not main:
            return
        if nace_list:
            self.ekonomicka_cinnost_subjektu.set_values(nace_list)
        self.ekonomicka_cinnost_subjektu.set_value(main)

    def get_data(self) -> dict:
        workplace_name = self.workplace.display_text()

        return {
            "workplace_id": self.workplace.current_workplace_id(),
            "workplace_name": workplace_name,
            "pracoviste": workplace_name,
            "charakteristika_pracoviste": self.charakteristika_pracoviste.value(),
            "zdroj_urazu": self.zdroj_urazu.value(),
            "pricina_urazu": self.pricina_urazu.value(),
            "uraz_pracoviste_zamestnavatele": self._radio_value(),
            "subjekt_registrovan": "",
            "ico_subjektu": self.ico_subjektu.text().strip(),
            "adresa_sidla_subjektu": self.adresa_sidla_subjektu.toPlainText().strip(),
            "ekonomicka_cinnost_subjektu": self.ekonomicka_cinnost_subjektu.value(),
            "ekonomicka_cinnost_pracoviste": self.ekonomicka_cinnost_subjektu.value(),
            "adresa_pracoviste": self.adresa_pracoviste.toPlainText().strip(),
            "okres_pracoviste": self.okres_pracoviste.value(),
            "popis_pracoviste": self.popis_pracoviste.toPlainText().strip(),
        }

    def load_data(self, accident):
        self.workplace.set_workplace(
            accident.workplace_id,
            accident.workplace_name or accident.pracoviste or "",
        )
        self.charakteristika_pracoviste.set_value(accident.charakteristika_pracoviste or "")
        self.zdroj_urazu.set_value(accident.zdroj_urazu or "")
        self.pricina_urazu.set_value(accident.pricina_urazu or "")
        self._set_radio_value(accident.uraz_pracoviste_zamestnavatele or "ANO")
        self.ico_subjektu.setText(accident.ico_subjektu or "")
        self.adresa_sidla_subjektu.setPlainText(accident.adresa_sidla_subjektu or "")
        self.ekonomicka_cinnost_subjektu.set_value(accident.ekonomicka_cinnost_subjektu or accident.ekonomicka_cinnost_pracoviste or "")
        self.adresa_pracoviste.setPlainText(accident.adresa_pracoviste or "")
        self.okres_pracoviste.set_value(accident.okres_pracoviste or "")
        self.popis_pracoviste.setPlainText(accident.popis_pracoviste or "")
        self._refresh_visibility()
