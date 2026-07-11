from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.code_selector import CodeSelector
from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.kniha_urazu.services.ciselnik_service import kniha_urazu_ciselnik_service
from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
    DPN_KIND_MISMATCH_MESSAGE,
    dpn_calendar_days,
    is_dpn_kind_mismatch,
)


REQUIRED_STYLE = "border: 2px solid #d32f2f; background: #fff6f6;"
NORMAL_STYLE = ""


class TabZamestnanec(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.jmeno_prijmeni = QLineEdit()

        self.pohlavi_muz = QRadioButton("Muž")
        self.pohlavi_zena = QRadioButton("Žena")
        self.pohlavi_group = QButtonGroup(self)
        self.pohlavi_group.addButton(self.pohlavi_muz)
        self.pohlavi_group.addButton(self.pohlavi_zena)

        pohlavi_layout = QHBoxLayout()
        pohlavi_layout.addWidget(self.pohlavi_muz)
        pohlavi_layout.addWidget(self.pohlavi_zena)
        pohlavi_layout.addStretch()

        self.datum_narozeni = NullableDateEdit()
        self.osobni_cislo = QLineEdit()

        self.statni_obcanstvi = CodeSelector(kniha_urazu_ciselnik_service.statni_obcanstvi())
        self.statni_obcanstvi.set_value("Česko")

        self.adresa_pobytu = QTextEdit()
        self.adresa_pobytu.setFixedHeight(72)

        self.adresa_dorucovani = QTextEdit()
        self.adresa_dorucovani.setFixedHeight(60)

        dorucovani_box = QFrame()
        dorucovani_box.setStyleSheet(
            "QFrame { background: #f4f4f4; border: 1px solid #d0d0d0; border-radius: 6px; }"
            "QLabel { color: #666; }"
        )
        dorucovani_layout = QVBoxLayout(dorucovani_box)
        dorucovani_layout.setContentsMargins(8, 6, 8, 8)
        dorucovani_info = QLabel("Jen pokud je odlišná od adresy místa pobytu.")
        dorucovani_layout.addWidget(dorucovani_info)
        dorucovani_layout.addWidget(self.adresa_dorucovani)

        self.telefon_email = QLineEdit()

        self.zdravotni_pojistovna = CodeSelector(kniha_urazu_ciselnik_service.zdravotni_pojistovny())

        self.vztah_k_zamestnavateli = CodeSelector(kniha_urazu_ciselnik_service.vztahy_k_zamestnavateli())

        self.den_vzniku_pravniho_vztahu = NullableDateEdit()

        self.druh_vykonavane_prace = CodeSelector(kniha_urazu_ciselnik_service.cz_isco())
        self.druh_vykonavane_prace.set_value("")

        self.dpn_od = NullableDateEdit()
        self.dpn_do = NullableDateEdit()
        self.dpn_od.dateChanged.connect(self._refresh_dpn_duration)
        self.dpn_do.dateChanged.connect(self._refresh_dpn_duration)

        self._current_druh_urazu = ""

        self.dpn_duration_label = QLabel()
        self.dpn_duration_label.setObjectName("InfoText")

        self.dpn_kind_warning_label = QLabel()
        self.dpn_kind_warning_label.setObjectName("WarningText")
        self.dpn_kind_warning_label.setWordWrap(True)
        self.dpn_kind_warning_label.setStyleSheet("color: #b45309;")
        self.dpn_kind_warning_label.setVisible(False)

        self._refresh_dpn_duration()

        self._required_widgets = {
            "Jméno a příjmení": self.jmeno_prijmeni,
            "Pohlaví": self.pohlavi_muz,
            "Datum narození": self.datum_narozeni,
            "Státní občanství": self.statni_obcanstvi,
            "Adresa místa pobytu": self.adresa_pobytu,
            "Zdravotní pojišťovna": self.zdravotni_pojistovna,
            "Vztah k zaměstnavateli": self.vztah_k_zamestnavateli,
            "Den vzniku právního vztahu": self.den_vzniku_pravniho_vztahu,
            "Druh vykonávané práce": self.druh_vykonavane_prace,
        }

        self._add_required_row(form, "Jméno a příjmení:", self.jmeno_prijmeni)
        self._add_required_row(form, "Pohlaví:", pohlavi_layout)
        self._add_required_row(form, "Datum narození:", self.datum_narozeni)
        form.addRow("Osobní číslo:", self.osobni_cislo)
        self._add_required_row(form, "Státní občanství:", self.statni_obcanstvi)
        self._add_required_row(form, "Adresa místa pobytu:", self.adresa_pobytu)
        form.addRow("Adresa pro doručování:", dorucovani_box)
        form.addRow("Telefon/email:", self.telefon_email)
        self._add_required_row(form, "Zdravotní pojišťovna:", self.zdravotni_pojistovna)
        self._add_required_row(form, "Vztah k zaměstnavateli:", self.vztah_k_zamestnavateli)
        self._add_required_row(form, "Den vzniku právního vztahu:", self.den_vzniku_pravniho_vztahu)
        self._add_required_row(form, "Druh vykonávané práce:", self.druh_vykonavane_prace)
        form.addRow("DPN následkem úrazu od:", self.dpn_od)
        form.addRow("DPN následkem úrazu do:", self.dpn_do)
        form.addRow("", self.dpn_duration_label)
        form.addRow("", self.dpn_kind_warning_label)

        layout.addLayout(form)
        layout.addStretch()

    def _add_required_row(self, form: QFormLayout, label_text: str, widget_or_layout):
        label = QLabel(f"<b>{label_text}</b>")
        form.addRow(label, widget_or_layout)

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

    def _pohlavi(self) -> str:
        if self.pohlavi_muz.isChecked():
            return "Muž"
        if self.pohlavi_zena.isChecked():
            return "Žena"
        return ""

    def _set_pohlavi(self, value: str):
        value = (value or "").strip().lower()
        self.pohlavi_muz.setChecked(value in ["muž", "muz", "m"])
        self.pohlavi_zena.setChecked(value in ["žena", "zena", "ž", "z"])

    def _is_empty(self, widget) -> bool:
        if isinstance(widget, QLineEdit):
            return not widget.text().strip()
        if isinstance(widget, QTextEdit):
            return not widget.toPlainText().strip()
        if isinstance(widget, NullableDateEdit):
            return not widget.has_date()
        if isinstance(widget, CodeSelector):
            return not widget.value().strip()
        if widget is self.pohlavi_muz:
            return not self._pohlavi()
        return False

    def _mark_error(self, widget, error: bool):
        style = REQUIRED_STYLE if error else NORMAL_STYLE

        if widget is self.pohlavi_muz:
            self.pohlavi_muz.setStyleSheet(style)
            self.pohlavi_zena.setStyleSheet(style)
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
                if widget is self.pohlavi_muz:
                    self.pohlavi_muz.setFocus()
                else:
                    widget.setFocus()
                return

    def get_data(self) -> dict:
        return {
            "jmeno_prijmeni": self.jmeno_prijmeni.text().strip(),
            "pohlavi": self._pohlavi(),
            "datum_narozeni": self.datum_narozeni.get_date(),
            "osobni_cislo": self.osobni_cislo.text().strip(),
            "statni_obcanstvi": self.statni_obcanstvi.value(),
            "adresa_pobytu": self.adresa_pobytu.toPlainText().strip(),
            "adresa_dorucovani": self.adresa_dorucovani.toPlainText().strip(),
            "telefon_email": self.telefon_email.text().strip(),
            "zdravotni_pojistovna": self.zdravotni_pojistovna.value(),
            "vztah_k_zamestnavateli": self.vztah_k_zamestnavateli.value(),
            "vztah_k_zamestnavateli_detail": "",
            "den_vzniku_pravniho_vztahu": self.den_vzniku_pravniho_vztahu.get_date(),
            "druh_vykonavane_prace": self.druh_vykonavane_prace.value(),
            "cz_isco_kod": "",
            "cz_isco_nazev": "",
            "dpn_od": self.dpn_od.get_date(),
            "dpn_do": self.dpn_do.get_date(),
        }

    def load_data(self, accident):
        self.jmeno_prijmeni.setText(accident.jmeno_prijmeni or "")
        self._set_pohlavi(accident.pohlavi)
        self.datum_narozeni.set_date_value(accident.datum_narozeni)
        self.osobni_cislo.setText(accident.osobni_cislo or "")
        self.statni_obcanstvi.set_value(accident.statni_obcanstvi or "Česko")
        self.adresa_pobytu.setPlainText(accident.adresa_pobytu or "")
        self.adresa_dorucovani.setPlainText(accident.adresa_dorucovani or "")
        self.telefon_email.setText(accident.telefon_email or "")
        self.zdravotni_pojistovna.set_value(accident.zdravotni_pojistovna or "")
        self.vztah_k_zamestnavateli.set_value(accident.vztah_k_zamestnavateli or "")
        self.den_vzniku_pravniho_vztahu.set_date_value(accident.den_vzniku_pravniho_vztahu)
        self.druh_vykonavane_prace.set_value(accident.druh_vykonavane_prace or "")
        self.dpn_od.set_date_value(accident.dpn_od)
        self.dpn_do.set_date_value(accident.dpn_do)
        self._refresh_dpn_duration()
        self.refresh_dpn_kind_warning(getattr(accident, "druh_urazu", "") or "")
