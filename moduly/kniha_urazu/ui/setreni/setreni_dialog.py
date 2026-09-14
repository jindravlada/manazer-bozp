import json
import unicodedata
from datetime import datetime, timedelta, time, date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QRadioButton,
    QFileDialog,
    QCompleter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QAbstractItemView,
)


from core.widgets.dialog_utils import create_save_cancel_box, configure_form_tab_navigation
from moduly.kniha_urazu.ui.setreni.accident_findings_widget import AccidentFindingsWidget
from moduly.kniha_urazu.sluzby.accident_case_closure import (
    AccidentCaseClosureCheck,
    CASE_CLOSED_LABEL,
    CASE_CLOSED_NO,
    CASE_CLOSED_YES,
    CLOSURE_BLOCKED_TITLE,
    CLOSURE_DATE_LABEL,
    evaluate_accident_case_closure,
    is_saved_case_closed,
)
from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
    CSSZ_STATUS_DONE,
    CSSZ_STATUS_OPTIONAL,
    CSSZ_STATUS_REQUIRED,
    OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
    OBLIGATION_AKTUALIZACE_OO,
    OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
    OBLIGATION_CSSZ_USSZ_NEMOCENSKE,
    OBLIGATION_OIP_OBU_OHLASENI,
    OBLIGATION_OO_OHLASENI,
    OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU,
    OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU,
    OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI,
    METHOD_PORTAL_SUIP,
    POST_DPN_OBLIGATION_KEYS,
    SECTION_AKTUALIZACE_PO_DPN,
    SECTION_NEMOCENSKE,
    SECTION_ODESLANI,
    SECTION_OHLASENI,
    SECTION_PREDANI,
    SECTION_ZAKONNA_POJISTOVNA,
    SECTION_ZAZNAM,
    INVESTIGATION_BEFORE_ACCIDENT_WARNING,
    ZAKONNA_AKTUALIZACE_STATUS_DONE,
    ZAKONNA_AKTUALIZACE_STATUS_WAITING,
    ZAKONNA_HLASENI_STATUS_DONE,
    ZAKONNA_HLASENI_STATUS_WAITING,
    ZAKONNA_POJISTOVNA_KEYS,
    ZAKONNA_TOGETHER_CHECKBOX_LABEL,
    cssz_row_ui_state,
    is_dpn_ended,
    is_fatal_accident,
    is_investigation_before_accident,
    is_row_visible,
    is_serious_or_fatal_accident,
    has_pn_over_3_days,
    obligation_default_deadline,
    obligation_definitions_for_accident,
    obligation_key_from_row,
    obligation_notification_date,
    oip_notice_uses_fixed_portal_suip,
    record_duty_keys_hidden_for_generation,
    requires_accident_record,
    requires_police_obligation,
    resolve_record_duty_generation,
    row_status,
    zakonna_row_ui_state,
    zakonna_together_checkbox_default,
)
from moduly.kniha_urazu.sluzby.accident_service import accident_service
from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
from core.services.attachment_service import attachment_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.ui.task_dialog import TaskDialog
from core.widgets.search_combo_box import SearchComboBox


class SetreniDialog(QDialog):
    """Administrativní karta pracovního úrazu (ohlášení, záznam o úrazu, ukončení)."""

    def __init__(self, parent=None, accident=None, *, focus_obligation_key=None):
        super().__init__(parent)

        self.accident = accident
        self.open_mu_after_close = False
        self._focus_obligation_key = (focus_obligation_key or "").strip() or None
        self.investigation = investigation_service.get_or_create(accident.id) if accident is not None else None
        self._zajisteni_saved_data = {}
        if self.investigation is not None and getattr(self.investigation, "zajisteni_dukazu_json", ""):
            try:
                self._zajisteni_saved_data = json.loads(self.investigation.zajisteni_dukazu_json or "{}")
            except Exception:
                self._zajisteni_saved_data = {}

        number = accident.number if accident is not None else ""
        self.setWindowTitle(f"Administrace úrazu {number}".strip())

        layout = QVBoxLayout(self)

        mu_info = QLabel("Vyšetřování úrazu probíhá v modulu Vyšetřování MU.")
        mu_info.setWordWrap(True)
        layout.addWidget(mu_info)

        mu_row = QHBoxLayout()
        self.open_mu_btn = QPushButton("Otevřít Vyšetřování MU")
        self.open_mu_btn.clicked.connect(self._open_mu_investigation)
        mu_row.addWidget(self.open_mu_btn)
        mu_row.addStretch()
        layout.addLayout(mu_row)

        self._init_ohlasovaci_povinnosti_widgets()
        layout.addWidget(self._tab_ohlasovaci_povinnosti(), 1)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        configure_form_tab_navigation(self)
        self._focus_obligation_row(self._focus_obligation_key)

    def accept(self):
        self._save_administrativa()
        super().accept()

    def _save_administrativa(self) -> None:
        if self.accident is None:
            return
        self._apply_case_closure_guard()
        merged = dict(self._zajisteni_saved_data)
        merged.update(self._administrativa_save_data())
        investigation_service.save_zajisteni_dukazu(
            self.accident.id,
            json.dumps(merged, ensure_ascii=False),
        )
        closed = merged.get("admin_pripad_uzavren") == CASE_CLOSED_YES
        if getattr(self.accident, "closed", False) != closed:
            updated = accident_service.update_accident(self.accident.id, closed=closed)
            if updated is not None:
                self.accident = updated
        from moduly.kniha_urazu.sluzby.accident_reporting_task_service import (
            accident_reporting_task_service,
        )

        accident_reporting_task_service.sync_for_accident(
            self.accident,
            saved_data=merged,
        )
        self._zajisteni_saved_data = merged

    def _was_case_closed(self) -> bool:
        return is_saved_case_closed(self._zajisteni_saved_data, self.accident)

    def _evaluate_case_closure(self) -> AccidentCaseClosureCheck:
        merged = dict(self._zajisteni_saved_data)
        merged.update(self._administrativa_save_data())
        return evaluate_accident_case_closure(
            self.accident,
            saved_data=merged,
            today=date.today(),
        )

    def _connect_case_closure_guard(self) -> None:
        if not hasattr(self, "admin_pripad_uzavren"):
            return
        for child in self.admin_pripad_uzavren.findChildren(QRadioButton):
            if child.text() == CASE_CLOSED_YES:
                child.toggled.connect(self._on_case_closed_toggled)

    def _on_case_closed_toggled(self, checked: bool) -> None:
        if not checked:
            return
        if self._was_case_closed():
            return
        self._apply_case_closure_guard(show_message=True)

    def _apply_case_closure_guard(self, *, show_message: bool = True) -> None:
        if self._radio_choice_value(self.admin_pripad_uzavren) != CASE_CLOSED_YES:
            return
        if self._was_case_closed():
            return
        check = self._evaluate_case_closure()
        if check.allowed:
            return
        self._set_radio_choice(self.admin_pripad_uzavren, CASE_CLOSED_NO)
        if show_message and check.message:
            QMessageBox.warning(self, CLOSURE_BLOCKED_TITLE, check.message)

    def _open_mu_investigation(self) -> None:
        if self.accident is None:
            return
        self.open_mu_after_close = True
        self.accept()

    def _administrativa_save_data(self):
        return {
            "admin_setreni_jmeno": self.admin_setreni_jmeno.currentText().strip() if hasattr(self.admin_setreni_jmeno, "currentText") else "",
            "admin_setreni_funkce": self.admin_setreni_funkce.text().strip(),
            "admin_zahajeni": self._date_to_json(self.admin_zahajeni),
            "admin_duvod_pozde": self.admin_duvod_pozde.text().strip(),
            "admin_ukonceni": self._date_to_json(self.admin_ukonceni),
            "admin_pripad_uzavren": self._radio_choice_value(self.admin_pripad_uzavren),
            "admin_ohlaseni": self._admin_rows_data(self.admin_ohlaseni_rows),
            "admin_zaslani": self._admin_rows_data(self._admin_all_zaslani_rows()),
        }

    def _admin_all_zaslani_rows(self):
        return (
            list(getattr(self, "admin_zaznam_rows", []))
            + list(getattr(self, "admin_odeslani_rows", []))
            +             list(getattr(self, "admin_predani_rows", []))
            + list(getattr(self, "admin_dpn_rows", []))
            + list(getattr(self, "admin_zakonna_rows", []))
            + list(getattr(self, "admin_nemocenske_rows", []))
        )

    def _date_value(self, widget):
        if hasattr(widget, "get_date"):
            return widget.get_date()
        return None

    def _oznameni_data(self):
        return {
            "oznameni_kdo": self.oznameni_kdo.text().strip(),
            "oznameni_komu": self.oznameni_komu.currentText().strip(),
            "oznameni_datum": self._date_value(self.oznameni_datum),
            "oznameni_cas": self.oznameni_cas.text().strip(),
            "oznameni_bezodkladne": "ANO" if self.oznameni_bezodkladne_ano.isChecked() else "NE",
            "oznameni_duvod_pozde": self.oznameni_duvod_pozde.toPlainText().strip(),
            "oznameni_popis": self.oznameni_popis.toPlainText().strip(),
            "opatreni_prvni_pomoc": "ANO" if self.op_prvni_pomoc.isChecked() else "",
            "opatreni_zzs": "ANO" if self.op_zzs.isChecked() else "",
            "opatreni_zastavena_cinnost": "ANO" if self.op_zastavena_cinnost.isChecked() else "",
            "opatreni_zajisteno_misto": "ANO" if self.op_zajisteno_misto.isChecked() else "",
            "opatreni_zabraneno_manipulaci": "ANO" if self.op_zabraneno_manipulaci.isChecked() else "",
            "opatreni_informovan_nadrizeny": "ANO" if self.op_informovan_nadrizeny.isChecked() else "",
            "opatreni_informovan_bozp": "ANO" if self.op_informovan_bozp.isChecked() else "",
            "oznameni_bozp_datum": self._date_value(self.oznameni_bozp_datum),
            "oznameni_bozp_cas": self.oznameni_bozp_cas.text().strip(),
            "opatreni_informovany_dalsi": "ANO" if self.op_informovany_dalsi.isChecked() else "",
            "dalsi_postup": self.dalsi_postup.currentText().strip(),
            "dalsi_postup_jiny": self.dalsi_postup_jiny.toPlainText().strip(),
        }

    def _tab_oznameni(self):
        from PySide6.QtWidgets import (
            QWidget, QVBoxLayout, QGroupBox, QFormLayout, QLabel, QLineEdit,
            QTextEdit, QCheckBox, QComboBox, QRadioButton, QHBoxLayout, QScrollArea
        )

        from core.widgets.attachment_widget import AttachmentWidget
        from core.widgets.nullable_date_edit import NullableDateEdit
        from core.widgets.thp_worker_selector import ThpWorkerSelector

        outer = QWidget()
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer_layout.addWidget(scroll)

        tab = QWidget()
        scroll.setWidget(tab)

        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)

        a = self.accident
        inv = self.investigation

        cil = QLabel(
            "<b>Cíl:</b> ochránit zdraví osob, zajistit potřebnou pomoc a neznehodnotit důkazy potřebné pro šetření pracovního úrazu."
        )
        cil.setWordWrap(True)
        layout.addWidget(cil)

        layout.addWidget(QLabel("1. Základní údaje"))
        g1 = QGroupBox()
        f1 = QFormLayout(g1)

        cislo = QLabel(a.number if a else "")
        self.oznameni_kdo = QLineEdit()
        if inv and inv.oznameni_kdo:
            self.oznameni_kdo.setText(inv.oznameni_kdo)
        elif a and a.employee_name:
            self.oznameni_kdo.setText(a.employee_name)

        self.oznameni_komu = ThpWorkerSelector()
        self.oznameni_komu.setEditable(True)
        komu = inv.oznameni_komu if inv and inv.oznameni_komu else ""
        if not komu and a and a.zapsal_jmeno:
            komu = a.zapsal_jmeno
        if komu:
            index = self.oznameni_komu.findText(komu)
            if index >= 0:
                self.oznameni_komu.setCurrentIndex(index)
            else:
                self.oznameni_komu.setEditText(komu)

        self.oznameni_datum = NullableDateEdit()
        if inv and inv.oznameni_datum:
            self.oznameni_datum.set_date_value(inv.oznameni_datum)
        elif a and a.accident_date:
            self.oznameni_datum.set_date_value(a.accident_date)

        self.oznameni_cas = QLineEdit()
        self.oznameni_cas.setPlaceholderText("např. 14:35")
        if inv and inv.oznameni_cas:
            self.oznameni_cas.setText(inv.oznameni_cas)
        elif a and a.accident_time:
            self.oznameni_cas.setText(a.accident_time)

        self.oznameni_datum.dateChanged.connect(self._refresh_dukazy_casove_rozdily)
        self.oznameni_cas.textChanged.connect(self._refresh_dukazy_casove_rozdily)

        self.oznameni_bezodkladne_ano = QRadioButton("ANO")
        self.oznameni_bezodkladne_ne = QRadioButton("NE")
        if inv and inv.oznameni_bezodkladne == "NE":
            self.oznameni_bezodkladne_ne.setChecked(True)
        else:
            self.oznameni_bezodkladne_ano.setChecked(True)

        rb_layout = QHBoxLayout()
        rb_layout.addWidget(self.oznameni_bezodkladne_ano)
        rb_layout.addWidget(self.oznameni_bezodkladne_ne)
        rb_layout.addStretch()

        self.oznameni_duvod_pozde = QTextEdit()
        self.oznameni_duvod_pozde.setFixedHeight(70)
        self.oznameni_duvod_pozde.setPlaceholderText("Důvod")
        self.oznameni_duvod_pozde.setPlainText(inv.oznameni_duvod_pozde if inv else "")

        def refresh_duvod():
            self.oznameni_duvod_pozde.setVisible(self.oznameni_bezodkladne_ne.isChecked())

        self.oznameni_bezodkladne_ano.toggled.connect(refresh_duvod)
        self.oznameni_bezodkladne_ne.toggled.connect(refresh_duvod)
        refresh_duvod()

        f1.addRow("Číslo úrazu:", cislo)
        f1.addRow("Kdo úraz oznámil:", self.oznameni_kdo)
        f1.addRow("Komu byl úraz oznámen:", self.oznameni_komu)
        f1.addRow("Datum oznámení:", self.oznameni_datum)
        f1.addRow("Čas oznámení:", self.oznameni_cas)
        f1.addRow("Oznámeno bezodkladně:", rb_layout)
        f1.addRow("Důvod pozdního oznámení:", self.oznameni_duvod_pozde)
        layout.addWidget(g1)

        layout.addWidget(QLabel("2. Postižený zaměstnanec"))
        g2 = QGroupBox()
        f2 = QFormLayout(g2)
        zam_text = (
            f"<b>Postižený zaměstnanec:</b> {a.employee_name or ''}<br>"
            f"<b>Pracovní pozice:</b> {a.druh_vykonavane_prace or ''}<br>"
            f"<b>Pracoviště:</b> {(a.workplace_name or a.pracoviste or '')}"
        ) if a else ""
        zam = QLabel(zam_text)
        zam.setWordWrap(True)
        f2.addRow(zam)
        layout.addWidget(g2)

        layout.addWidget(QLabel("3. Údaje o úrazu"))
        g3 = QGroupBox()
        f3 = QFormLayout(g3)
        datum_urazu = a.accident_date.strftime("%d.%m.%Y") if a and a.accident_date else ""
        uraz_text = (
            f"<b>Datum úrazu:</b> {datum_urazu}<br>"
            f"<b>Čas úrazu:</b> {a.accident_time or ''}<br>"
            f"<b>Místo úrazu:</b> {a.misto_urazu or ''}<br>"
            f"<b>Druh zranění:</b> {a.druh_zraneni or ''}"
        ) if a else ""
        udaje = QLabel(uraz_text)
        udaje.setWordWrap(True)

        self.oznameni_popis = QTextEdit()
        self.oznameni_popis.setFixedHeight(95)
        if inv and inv.oznameni_popis:
            self.oznameni_popis.setPlainText(inv.oznameni_popis)
        elif a and a.popis_urazoveho_deje:
            self.oznameni_popis.setPlainText(a.popis_urazoveho_deje)

        f3.addRow("Údaje z karty úrazu:", udaje)
        f3.addRow("Stručný popis události:", self.oznameni_popis)
        layout.addWidget(g3)

        layout.addWidget(QLabel("4. Okamžitá opatření"))
        g4 = QGroupBox()
        v4 = QVBoxLayout(g4)

        self.op_prvni_pomoc = QCheckBox("Poskytnuta první pomoc")
        self.op_zzs = QCheckBox("Přivolána ZZS")
        self.op_zastavena_cinnost = QCheckBox("Zastavena nebezpečná činnost")
        self.op_zajisteno_misto = QCheckBox("Zajištěno místo úrazu")
        self.op_zabraneno_manipulaci = QCheckBox("Zabráněno manipulaci s předměty")
        self.op_informovan_nadrizeny = QCheckBox("Informován nadřízený")
        self.op_informovan_bozp = QCheckBox("Informován BOZP")

        pairs = [
            (self.op_prvni_pomoc, inv.opatreni_prvni_pomoc if inv else ""),
            (self.op_zzs, inv.opatreni_zzs if inv else ""),
            (self.op_zastavena_cinnost, inv.opatreni_zastavena_cinnost if inv else ""),
            (self.op_zajisteno_misto, inv.opatreni_zajisteno_misto if inv else ""),
            (self.op_zabraneno_manipulaci, inv.opatreni_zabraneno_manipulaci if inv else ""),
            (self.op_informovan_nadrizeny, inv.opatreni_informovan_nadrizeny if inv else ""),
            (self.op_informovan_bozp, inv.opatreni_informovan_bozp if inv else ""),
        ]
        for checkbox, value in pairs:
            checkbox.setChecked(value == "ANO")
            v4.addWidget(checkbox)

        f4 = QFormLayout()
        self.oznameni_bozp_datum = NullableDateEdit()
        if inv and inv.oznameni_bozp_datum:
            self.oznameni_bozp_datum.set_date_value(inv.oznameni_bozp_datum)

        self.oznameni_bozp_cas = QLineEdit()
        self.oznameni_bozp_cas.setPlaceholderText("např. 14:35")
        self.oznameni_bozp_cas.setText(inv.oznameni_bozp_cas if inv else "")

        f4.addRow("Datum oznámení BOZP:", self.oznameni_bozp_datum)
        f4.addRow("Čas oznámení BOZP:", self.oznameni_bozp_cas)
        v4.addLayout(f4)

        self.op_informovany_dalsi = QCheckBox("Informovány další osoby podle závažnosti")
        self.op_informovany_dalsi.setChecked((inv.opatreni_informovany_dalsi if inv else "") == "ANO")
        v4.addWidget(self.op_informovany_dalsi)

        layout.addWidget(g4)

        layout.addWidget(QLabel("5. Další postup"))
        g5 = QGroupBox()
        f5 = QFormLayout(g5)
        self.dalsi_postup = QComboBox()
        self.dalsi_postup.setEditable(True)
        self.dalsi_postup.addItems(["", "pokračoval v práci", "odešel k lékaři", "byl odvezen ZZS", "jiný postup"])
        if inv and inv.dalsi_postup:
            self.dalsi_postup.setCurrentText(inv.dalsi_postup)

        self.dalsi_postup_jiny = QTextEdit()
        self.dalsi_postup_jiny.setFixedHeight(70)
        self.dalsi_postup_jiny.setPlaceholderText("Vyplňte jaký postup byl zvolen.")
        if inv and hasattr(inv, "dalsi_postup_jiny"):
            self.dalsi_postup_jiny.setPlainText(inv.dalsi_postup_jiny or "")

        def refresh_jiny_postup():
            self.dalsi_postup_jiny.setVisible(self.dalsi_postup.currentText().strip().lower() == "jiný postup")

        self.dalsi_postup.currentTextChanged.connect(refresh_jiny_postup)

        f5.addRow("Další postup:", self.dalsi_postup)
        f5.addRow("Jiný postup:", self.dalsi_postup_jiny)
        refresh_jiny_postup()
        layout.addWidget(g5)

        layout.addWidget(QLabel("6. Přílohy oznámení"))
        g6 = QGroupBox()
        v6 = QVBoxLayout(g6)
        entity_id = a.id if a else None
        prilohy = AttachmentWidget(entity_type="accident", entity_id=entity_id)
        v6.addWidget(prilohy)
        layout.addWidget(g6)

        layout.addStretch()
        return outer

    def _tab_prehled(self):
        tab = QWidget()
        form = QFormLayout(tab)

        accident = self.accident

        self.uraz_cislo = QLineEdit(accident.number if accident else "")
        self.zraneny = QLineEdit(accident.employee_name if accident else "")
        self.datum_urazu = QLineEdit(
            accident.accident_date.strftime("%d.%m.%Y") if accident and accident.accident_date else ""
        )
        self.pracoviste = QLineEdit((accident.workplace_name or accident.pracoviste) if accident else "")
        self.misto_urazu = QTextEdit(accident.misto_urazu if accident else "")
        self.misto_urazu.setFixedHeight(70)

        for widget in [
            self.uraz_cislo,
            self.zraneny,
            self.datum_urazu,
            self.pracoviste,
        ]:
            widget.setReadOnly(True)

        form.addRow("Číslo úrazu:", self.uraz_cislo)
        form.addRow("Zraněný:", self.zraneny)
        form.addRow("Datum úrazu:", self.datum_urazu)
        form.addRow("Pracoviště:", self.pracoviste)
        form.addRow("Místo úrazu:", self.misto_urazu)

        info = QLabel("Toto je první návrh šetření. Budeme jej dál upravovat záložku po záložce.")
        info.setStyleSheet("color: #666; font-style: italic;")
        form.addRow("", info)

        return tab

    def _simple_tab(self, placeholder: str):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        text = QTextEdit()
        text.setPlaceholderText(placeholder)
        layout.addWidget(text)
        return tab


    def _new_date_edit(self, placeholder="např. 05.06.1982"):
        from core.widgets.nullable_date_edit import NullableDateEdit
        w = NullableDateEdit()
        if hasattr(w, "setPlaceholderText"):
            w.setPlaceholderText(placeholder)
        return w

    def _radio_choice(self, labels):
        box = QWidget()
        layout = QHBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        for text in labels:
            layout.addWidget(QRadioButton(text))
        layout.addStretch()
        return box

    def _radio_choice_value(self, box):
        for child in box.findChildren(QRadioButton):
            if child.isChecked():
                return child.text()
        return ""

    def _set_radio_choice(self, box, value):
        buttons = box.findChildren(QRadioButton)
        if not value:
            for child in buttons:
                child.setAutoExclusive(False)
                child.setChecked(False)
                child.setAutoExclusive(True)
            return
        for child in buttons:
            if child.text() == value:
                child.setChecked(True)
                return

    def _date_to_json(self, widget):
        value = self._date_value(widget)
        if value is None:
            return ""
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)

    def _set_date_widget(self, widget, value):
        if not value:
            return
        if isinstance(value, str) and hasattr(widget, "set_date_iso"):
            widget.set_date_iso(value)
        elif hasattr(widget, "set_date_value"):
            widget.set_date_value(value)

    def _refresh_admin_zahajeni_warning(self, *_args) -> None:
        if not hasattr(self, "admin_zahajeni_warning"):
            return
        investigation_date = self._date_value(self.admin_zahajeni) if hasattr(self, "admin_zahajeni") else None
        accident_date = getattr(self.accident, "accident_date", None) if self.accident is not None else None
        if is_investigation_before_accident(investigation_date, accident_date):
            self.admin_zahajeni_warning.setText(INVESTIGATION_BEFORE_ACCIDENT_WARNING)
            self.admin_zahajeni_warning.setVisible(True)
        else:
            self.admin_zahajeni_warning.clear()
            self.admin_zahajeni_warning.setVisible(False)

    def _slug(self, text):
        text = text.replace(":", "").strip()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(ch for ch in text if not unicodedata.combining(ch))
        parts = []
        capitalize_next = True
        for ch in text:
            if ch.isalnum():
                parts.append(ch.upper() if capitalize_next else ch)
                capitalize_next = False
            else:
                capitalize_next = True
        return "".join(parts) or "Foto"

    def _accident_number_slug(self):
        number = self.accident.number if self.accident is not None else ""
        return str(number).replace("/", "-").replace("\\", "-").strip() or "bez-cisla"

    def _zajisteni_dukazu_data(self):
        return {
            "datum": self._date_to_json(self.dukazy_datum),
            "cas": self.dukazy_cas.text().strip(),
            "provedl": self.dukazy_provedl.currentText().strip() if hasattr(self.dukazy_provedl, "currentText") else "",
            "pocet_svedku": self.dukazy_pocet_svedku.value(),
            "svedci": [w.text().strip() for w in self.dukazy_svedek_widgets],
            "svedci_oddeleni": self.dukazy_svedci_oddeleni.isChecked(),
            "vyjadreni_obsahuje_udaje": self.dukazy_vyjadreni_obsahuje_udaje.isChecked(),
            "vyjadreni_vracena": self.dukazy_vyjadreni_vracena.isChecked(),
            "rozhovor_po_vyjadreni": self.dukazy_rozhovor_po_vyjadreni.isChecked(),
            "presne_misto": self.dukazy_presne_misto_text.toPlainText().strip(),
            "stav_povrchu": self.dukazy_stav_povrchu_text.toPlainText().strip(),
            "osvetleni_viditelnost": self.dukazy_osvetleni_viditelnost_text.toPlainText().strip(),
            "pocasi_podminky": self.dukazy_pocasi_podminky_text.toPlainText().strip(),
            "prekazky_znaceni_okoli": self.dukazy_prekazky_znaceni_okoli_text.toPlainText().strip(),
            "stav_zarizeni_nastroju_oopp": self.dukazy_stav_zarizeni_nastroju_oopp_text.toPlainText().strip(),
            "chemikalie_skvrny": self.dukazy_chemikalie_skvrny_text.toPlainText().strip(),
            "sirsi_okoli": self.dukazy_sirsi_okoli_text.toPlainText().strip(),
            "fotky": dict(self.dukazy_photo_paths),
            "nacrt_porizen": self.dukazy_nacrt_porizen.isChecked(),
            "datum_fotek": self._date_to_json(self.dukazy_datum_fotek),
            "cas_fotek": self.dukazy_cas_fotek.text().strip(),
            "caszarizeni_fotodokumentace": self._radio_choice_value(self.caszarizeni_fotodokumentace),
            "caszarizeni_reference_source": self.caszarizeni_reference_source.currentText().strip(),
            "caszarizeni_srovnani_cas": self.caszarizeni_srovnani_cas.text().strip(),
            "caszarizeni_visible_rows": getattr(self, "caszarizeni_visible_rows", 1),
            "caszarizeni_rows": [
                {
                    "zarizeni": getattr(self, f"caszarizeni_{i}_zarizeni").text().strip(),
                    "cas_zarizeni": getattr(self, f"caszarizeni_{i}_cas_zarizeni").text().strip(),
                    "cas_mobil": getattr(self, f"caszarizeni_{i}_cas_mobil").text().strip(),
                    "rozdil": getattr(self, f"caszarizeni_{i}_rozdil").text().strip(),
                    "srovnany_cas": getattr(self, f"caszarizeni_{i}_srovnany_cas").text().strip(),
                    "foto": getattr(self, f"caszarizeni_{i}_foto").text().strip(),
                }
                for i in range(1, 11)
            ],
            "kamerovy_zaznam": self._radio_choice_value(self.dukazy_kamerovy_zaznam_ano_ne),
            "dochazka_datum": self._date_to_json(self.dukazy_dochazka_datum),
            "dochazka_cas": self.dukazy_dochazka_cas.text().strip(),
            "pracovni_postup": self._radio_choice_value(self.dukazy_pracovni_postup_ano_ne),
            "provozni_dokumentace": self.dukazy_provozni_dokumentace_text.toPlainText().strip(),
            "provozni_zaznamy": self.dukazy_provozni_zaznamy_text.toPlainText().strip(),
            "poznamka": self.dukazy_poznamka.toPlainText().strip(),
            "ohledani_zapsal": self.ohledani_zapsal.currentText().strip() if hasattr(self.ohledani_zapsal, "currentText") else "",
            "ohledani_provoz": self.ohledani_provoz.currentText().strip() if hasattr(self.ohledani_provoz, "currentText") else self.ohledani_provoz.text().strip(),
            "ohledani_provedli": self.ohledani_provedli.toPlainText().strip(),
            "ohledani_zahajeni": self.ohledani_zahajeni.text().strip(),
            "ohledani_ukonceni": self.ohledani_ukonceni.text().strip(),
            "ohledani_popis_mista": self.ohledani_popis_mista.toPlainText().strip(),
            "ohledani_priloha": self.ohledani_priloha.text().strip(),
            "dodrz_pracovni_doba": self._radio_choice_value(self.dodrz_pracovni_doba),
            "dodrz_prescasy": self._radio_choice_value(self.dodrz_prescasy),
            "dodrz_prescasy_detail": self.dodrz_prescasy_detail.toPlainText().strip(),
            "dodrz_predpisy_cinnost": self.dodrz_predpisy_cinnost.toPlainText().strip(),
            "dodrz_oopp_rows": [
                {
                    "typ": row["typ"].text().strip(),
                    "datum": self._date_to_json(row["datum"]),
                    "platnost": row["platnost"].text().strip(),
                    "poznamka": row["poznamka"].text().strip(),
                }
                for row in self.dodrz_oopp_rows
            ],
            "dodrz_skoleni_rows": [
                {
                    "typ": row["typ"].text().strip(),
                    "datum": self._date_to_json(row["datum"]),
                    "osnova": self._radio_choice_value(row["osnova"]),
                    "poznamka": row["poznamka"].text().strip(),
                }
                for row in self.dodrz_skoleni_rows
            ],
            "dodrz_lekar_typ": self.dodrz_lekar_typ.currentText().strip(),
            "dodrz_lekar_datum": self._date_to_json(self.dodrz_lekar_datum),
            "dodrz_lekar_platnost": self._date_to_json(self.dodrz_lekar_platnost),
            "dodrz_kvalifikace_splnuje": self._radio_choice_value(self.dodrz_kvalifikace_splnuje),
            "dodrz_kvalifikace_poznamka": self.dodrz_kvalifikace_poznamka.toPlainText().strip(),
            "dodrz_kontroly_reviz_zavady": self.dodrz_kontroly_reviz_zavady.toPlainText().strip(),
            "dodrz_zkousky_rows": [
                {
                    "typ": row["typ"].text().strip(),
                    "datum": self._date_to_json(row["datum"]),
                    "platnost": self._date_to_json(row["platnost"]),
                    "poznamka": row["poznamka"].text().strip(),
                }
                for row in self.dodrz_zkousky_rows
            ],
            "dodrz_ostatni_1": self.dodrz_ostatni_1.toPlainText().strip(),
            "dodrz_oopp_pouzity": self._radio_choice_value(self.dodrz_oopp_pouzity),
            "dodrz_stav_oopp": self.dodrz_stav_oopp.toPlainText().strip(),
            "dodrz_vyjadreni_oopp": self.dodrz_vyjadreni_oopp.toPlainText().strip(),
            "dodrz_kontrola_oopp_rows": [
                {
                    "datum": self._date_to_json(row["datum"]),
                    "kontroloval": self._widget_text(row["kontroloval"]),
                    "vysledek": row["vysledek"].text().strip(),
                }
                for row in self.dodrz_kontrola_oopp_rows
            ],
            "dodrz_kontrola_predpisu_rows": [
                {
                    "datum": self._date_to_json(row["datum"]),
                    "kontroloval": self._widget_text(row["kontroloval"]),
                    "vysledek": row["vysledek"].text().strip(),
                }
                for row in self.dodrz_kontrola_predpisu_rows
            ],
            "dodrz_poruseni_predpisu": self.dodrz_poruseni_predpisu.toPlainText().strip(),
            "dodrz_ostatni_2": self.dodrz_ostatni_2.toPlainText().strip(),
            "dodrz_priloha": self.dodrz_priloha.text().strip(),
            "analyza_shrnuti_skutecneho_stavu": self.analyza_shrnuti_skutecneho_stavu.toPlainText().strip(),
            "analyza_zjistene_skutecnosti": self.analyza_zjistene_skutecnosti.toPlainText().strip(),
            "analyza_prvotni_pricina": self.analyza_prvotni_pricina.toPlainText().strip(),
            "analyza_faktory": {
                key: {
                    "checkboxes": {subkey: checkbox.isChecked() for subkey, checkbox in group["checkboxes"].items()},
                    "praxe": group.get("praxe").currentText().strip() if group.get("praxe") is not None else "",
                    "aktualizace_rizik": group.get("aktualizace_rizik").toPlainText().strip() if group.get("aktualizace_rizik") is not None else "",
                    "popis": group["popis"].toPlainText().strip(),
                }
                for key, group in self.analyza_faktory.items()
            },
            "analyza_klasifikace_rows": [
                {
                    "faktor": row["faktor"].text().strip(),
                    "kategorie": row["kategorie"].text().strip(),
                    "typ": row["typ"].currentText().strip(),
                }
                for row in getattr(self, "analyza_klasifikace_rows", [])
            ],
            "analyza_proc_1": self.analyza_proc_1.toPlainText().strip(),
            "analyza_proc_2": self.analyza_proc_2.toPlainText().strip(),
            "analyza_proc_3": self.analyza_proc_3.toPlainText().strip(),
            "analyza_proc_4": self.analyza_proc_4.toPlainText().strip(),
            "analyza_proc_5": self.analyza_proc_5.toPlainText().strip(),
            "analyza_bezprostredni_pricina": self.analyza_bezprostredni_pricina.toPlainText().strip(),
            "analyza_korenova_pricina": self.analyza_korenova_pricina.toPlainText().strip(),
            "analyza_prispivajici_priciny": self.analyza_prispivajici_priciny.toPlainText().strip(),
            "analyza_overeni_korenove_priciny": {key: cb.isChecked() for key, cb in self.analyza_overeni_korenove_priciny.items()},
            "analyza_poznamka_bozp": self.analyza_poznamka_bozp.toPlainText().strip(),
            "soulad_podklady": {key: cb.isChecked() for key, cb in self.soulad_podklady.items()},
            "soulad_nesrovnalosti": {key: cb.isChecked() for key, cb in self.soulad_nesrovnalosti.items()},
            "soulad_popis_nesrovnalosti": self.soulad_popis_nesrovnalosti.toPlainText().strip(),
            "soulad_vyhodnoceni": self.soulad_vyhodnoceni.toPlainText().strip(),
            "soulad_vzniklo_poskozeni": self._radio_choice_value(self.soulad_vzniklo_poskozeni),
            "soulad_pri_plneni": self._radio_choice_value(self.soulad_pri_plneni),
            "soulad_nahle_pusobeni": self._radio_choice_value(self.soulad_nahle_pusobeni),
            "soulad_mimo_praci": self._radio_choice_value(self.soulad_mimo_praci),
            "soulad_stanovisko_bozp": self.soulad_stanovisko_bozp.currentText().strip(),
            "soulad_oduvodneni": self.soulad_oduvodneni.toPlainText().strip(),
            "admin_setreni_jmeno": self.admin_setreni_jmeno.currentText().strip() if hasattr(self.admin_setreni_jmeno, "currentText") else "",
            "admin_setreni_funkce": self.admin_setreni_funkce.text().strip(),
            "admin_zahajeni": self._date_to_json(self.admin_zahajeni),
            "admin_duvod_pozde": self.admin_duvod_pozde.text().strip(),
            "admin_ukonceni": self._date_to_json(self.admin_ukonceni),
            "admin_pripad_uzavren": self._radio_choice_value(self.admin_pripad_uzavren),
            "admin_ohlaseni": self._admin_rows_data(self.admin_ohlaseni_rows),
            "admin_zaslani": self._admin_rows_data(self._admin_all_zaslani_rows()),
        }

    def _admin_all_zaslani_rows(self):
        return (
            list(getattr(self, "admin_zaznam_rows", []))
            + list(getattr(self, "admin_odeslani_rows", []))
            +             list(getattr(self, "admin_predani_rows", []))
            + list(getattr(self, "admin_dpn_rows", []))
            + list(getattr(self, "admin_zakonna_rows", []))
            + list(getattr(self, "admin_nemocenske_rows", []))
        )

    def _refresh_svedci_rows(self):
        if self.dukazy_svedci_form is None:
            return
        existing = [w.text() for w in self.dukazy_svedek_widgets]
        saved = self._zajisteni_saved_data.get("svedci", []) or []
        while len(self.dukazy_svedek_widgets) > 0:
            row = self.dukazy_svedci_form.rowCount() - 1
            self.dukazy_svedci_form.removeRow(row)
            self.dukazy_svedek_widgets.pop()
        for idx in range(self.dukazy_pocet_svedku.value()):
            value = existing[idx] if idx < len(existing) else (saved[idx] if idx < len(saved) else "")
            edit = QLineEdit(value)
            self.dukazy_svedek_widgets.append(edit)
            self.dukazy_svedci_form.addRow(f"Svědek {idx + 1}:", edit)

    def _init_zajisteni_dukazu_widgets(self):
        from core.widgets.thp_worker_selector import ThpWorkerSelector

        saved = self._zajisteni_saved_data
        a = self.accident

        self.dukazy_datum = self._new_date_edit()
        if saved.get("datum"):
            self._set_date_widget(self.dukazy_datum, saved.get("datum"))
        elif a and a.accident_date:
            self._set_date_widget(self.dukazy_datum, a.accident_date)

        self.dukazy_cas = QLineEdit()
        self.dukazy_cas.setPlaceholderText("např. 14:35")
        if saved.get("cas"):
            self.dukazy_cas.setText(saved.get("cas"))
        elif a and a.accident_time:
            self.dukazy_cas.setText(a.accident_time)

        self.dukazy_provedl = ThpWorkerSelector()
        self.dukazy_provedl.setEditable(True)
        provedl = saved.get("provedl") or ""
        if not provedl and a and a.zapsal_jmeno:
            provedl = a.zapsal_jmeno
        if provedl:
            index = self.dukazy_provedl.findText(provedl)
            if index >= 0:
                self.dukazy_provedl.setCurrentIndex(index)
            else:
                self.dukazy_provedl.setEditText(provedl)

        self.dukazy_pocet_svedku = QSpinBox()
        self.dukazy_pocet_svedku.setRange(0, 20)
        if "pocet_svedku" in saved:
            self.dukazy_pocet_svedku.setValue(int(saved.get("pocet_svedku") or 0))
        else:
            self.dukazy_pocet_svedku.setValue(0)
        self.dukazy_svedci_form = None
        self.dukazy_svedek_widgets = []

        self.dukazy_svedci_oddeleni = QCheckBox("Oddělit svědky a předat formulář k písemnému vyjádření")
        self.dukazy_vyjadreni_obsahuje_udaje = QCheckBox("Vyjádření obsahují datum, čas, jméno a podpis")
        self.dukazy_vyjadreni_vracena = QCheckBox("Vráceny formuláře s vyjádřením od všech svědků (včetně postiženého)")
        self.dukazy_rozhovor_po_vyjadreni = QCheckBox("Doplňující rozhovor byl veden až po prvotním písemném vyjádření")
        self.dukazy_svedci_oddeleni.setChecked(bool(saved.get("svedci_oddeleni", False)))
        self.dukazy_vyjadreni_obsahuje_udaje.setChecked(bool(saved.get("vyjadreni_obsahuje_udaje", False)))
        self.dukazy_vyjadreni_vracena.setChecked(bool(saved.get("vyjadreni_vracena", False)))
        self.dukazy_rozhovor_po_vyjadreni.setChecked(bool(saved.get("rozhovor_po_vyjadreni", False)))

        self.dukazy_presne_misto_text = QTextEdit()
        self.dukazy_stav_povrchu_text = QTextEdit()
        self.dukazy_osvetleni_viditelnost_text = QTextEdit()
        self.dukazy_pocasi_podminky_text = QTextEdit()
        self.dukazy_prekazky_znaceni_okoli_text = QTextEdit()
        self.dukazy_stav_zarizeni_nastroju_oopp_text = QTextEdit()
        self.dukazy_chemikalie_skvrny_text = QTextEdit()
        self.dukazy_sirsi_okoli_text = QTextEdit()
        for key, widget in {
            "presne_misto": self.dukazy_presne_misto_text,
            "stav_povrchu": self.dukazy_stav_povrchu_text,
            "osvetleni_viditelnost": self.dukazy_osvetleni_viditelnost_text,
            "pocasi_podminky": self.dukazy_pocasi_podminky_text,
            "prekazky_znaceni_okoli": self.dukazy_prekazky_znaceni_okoli_text,
            "stav_zarizeni_nastroju_oopp": self.dukazy_stav_zarizeni_nastroju_oopp_text,
            "chemikalie_skvrny": self.dukazy_chemikalie_skvrny_text,
            "sirsi_okoli": self.dukazy_sirsi_okoli_text,
        }.items():
            widget.setPlainText(saved.get(key, ""))

        self.dukazy_photo_statuses = {}
        self.dukazy_photo_paths = dict(saved.get("fotky", {}) or {})

        self.dukazy_nacrt_porizen = QCheckBox(
            "Náčrt místa: rozměry, vzdálenosti, výšky, úhly, umístění a poloha důležitých předmětů"
        )
        self.dukazy_nacrt_porizen.setChecked(bool(saved.get("nacrt_porizen", False)))
        self.dukazy_datum_fotek = self._new_date_edit()
        if saved.get("datum_fotek"):
            self._set_date_widget(self.dukazy_datum_fotek, saved.get("datum_fotek"))
        elif a and a.accident_date:
            self._set_date_widget(self.dukazy_datum_fotek, a.accident_date)
        self.dukazy_cas_fotek = QLineEdit()
        self.dukazy_cas_fotek.setPlaceholderText("čas pořízení fotek / videa")
        if saved.get("cas_fotek"):
            self.dukazy_cas_fotek.setText(saved.get("cas_fotek"))
        elif a and a.accident_time:
            self.dukazy_cas_fotek.setText(a.accident_time)

        if "cas_fotek" in saved and saved.get("cas_fotek"):
            self._dukazy_cas_fotek_manual = saved.get("cas_fotek") != self.dukazy_cas.text()
        else:
            self._dukazy_cas_fotek_manual = False
        self._dukazy_syncing_cas_fotek = False
        self.dukazy_cas.textChanged.connect(self._sync_dukazy_cas_fotek_from_provedeni)
        self.dukazy_cas_fotek.textChanged.connect(self._on_dukazy_cas_fotek_user_edit)

        self.caszarizeni_fotodokumentace = self._radio_choice(["Pořízena", "Nepořízena"])
        self._set_radio_choice(self.caszarizeni_fotodokumentace, saved.get("caszarizeni_fotodokumentace", ""))
        self.caszarizeni_reference_source = QComboBox()
        self.caszarizeni_reference_source.addItem("Mobil / referenční čas v řádcích")
        self._saved_caszarizeni_reference_source = saved.get("caszarizeni_reference_source", "")
        self.caszarizeni_srovnani_cas = QLineEdit()
        self.caszarizeni_srovnani_cas.setPlaceholderText("např. 14:35")
        self.caszarizeni_srovnani_cas.setText(saved.get("caszarizeni_srovnani_cas", ""))
        self.caszarizeni_rows = []
        cas_rows = saved.get("caszarizeni_rows", []) or []
        for i in range(1, 11):
            data = cas_rows[i - 1] if i <= len(cas_rows) else {}
            setattr(self, f"caszarizeni_{i}_zarizeni", QLineEdit(data.get("zarizeni", "")))
            setattr(self, f"caszarizeni_{i}_cas_zarizeni", QLineEdit(data.get("cas_zarizeni", "")))
            setattr(self, f"caszarizeni_{i}_cas_mobil", QLineEdit(data.get("cas_mobil", "")))
            setattr(self, f"caszarizeni_{i}_rozdil", QLineEdit(data.get("rozdil", "")))
            setattr(self, f"caszarizeni_{i}_srovnany_cas", QLineEdit(data.get("srovnany_cas", "")))
            setattr(self, f"caszarizeni_{i}_foto", QLineEdit(data.get("foto", "")))
            getattr(self, f"caszarizeni_{i}_rozdil").setReadOnly(True)
            getattr(self, f"caszarizeni_{i}_srovnany_cas").setReadOnly(True)
            getattr(self, f"caszarizeni_{i}_foto").setReadOnly(True)

        if self._saved_caszarizeni_reference_source:
            self.caszarizeni_reference_source.addItem(self._saved_caszarizeni_reference_source)
            self.caszarizeni_reference_source.setCurrentText(self._saved_caszarizeni_reference_source)

        self.dukazy_kamerovy_zaznam_ano_ne = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.dukazy_kamerovy_zaznam_ano_ne, saved.get("kamerovy_zaznam", ""))
        self.dukazy_dochazka_datum = self._new_date_edit()
        if saved.get("dochazka_datum"):
            self._set_date_widget(self.dukazy_dochazka_datum, saved.get("dochazka_datum"))
        self.dukazy_dochazka_cas = QLineEdit()
        self.dukazy_dochazka_cas.setPlaceholderText("např. 06:00")
        self.dukazy_dochazka_cas.setText(saved.get("dochazka_cas", ""))
        self.dukazy_pracovni_postup_ano_ne = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.dukazy_pracovni_postup_ano_ne, saved.get("pracovni_postup", ""))
        self.dukazy_provozni_dokumentace_text = QTextEdit()
        self.dukazy_provozni_dokumentace_text.setPlainText(saved.get("provozni_dokumentace", ""))
        self.dukazy_provozni_zaznamy_text = QTextEdit()
        self.dukazy_provozni_zaznamy_text.setPlainText(saved.get("provozni_zaznamy", ""))
        self.dukazy_poznamka = QTextEdit()
        self.dukazy_poznamka.setPlainText(saved.get("poznamka", ""))

        self.dukazy_rozdil_oznameni_label = QLabel("Oznámení úrazu: nelze spočítat")
        self.dukazy_rozdil_zajisteni_label = QLabel("Zajištění důkazů: nelze spočítat")
        self.dukazy_rozdil_foto_label = QLabel("Fotodokumentace: nelze spočítat")
        self.dukazy_casova_upozorneni_label = QLabel("")
        for lbl in (
            self.dukazy_rozdil_oznameni_label,
            self.dukazy_rozdil_zajisteni_label,
            self.dukazy_rozdil_foto_label,
            self.dukazy_casova_upozorneni_label,
        ):
            lbl.setWordWrap(True)
            lbl.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.dukazy_casova_upozorneni_label.setVisible(False)

        self.dukazy_datum.dateChanged.connect(self._refresh_dukazy_casove_rozdily)
        self.dukazy_datum_fotek.dateChanged.connect(self._refresh_dukazy_casove_rozdily)
        self.dukazy_cas.textChanged.connect(self._refresh_dukazy_casove_rozdily)
        self.dukazy_cas_fotek.textChanged.connect(self._refresh_dukazy_casove_rozdily)

    def _casove_rozdily_labels_ready(self):
        return all(
            hasattr(self, name)
            for name in (
                "dukazy_rozdil_oznameni_label",
                "dukazy_rozdil_zajisteni_label",
                "dukazy_rozdil_foto_label",
            )
        )

    def _datetime_from_date_and_time(self, date_value, time_text):
        if date_value is None:
            return None
        seconds = self._parse_time_minutes(time_text)
        if seconds is None:
            return None
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return datetime.combine(date_value, time(h, m, s))

    def _casovy_rozdil_barva(self, minutes):
        if minutes < 0:
            return "#c62828"
        if minutes <= 60:
            return "#2e7d32"
        if minutes <= 180:
            return "#b8860b"
        if minutes <= 480:
            return "#ef6c00"
        return "#c62828"

    def _format_od_urazu_rozdil(self, accident_dt, target_dt, pred_urazem_text=None):
        if accident_dt is None or target_dt is None:
            return None
        total_seconds = int((target_dt - accident_dt).total_seconds())
        if total_seconds < 0:
            return (pred_urazem_text or "Čas je před vznikem úrazu.", "#c62828")
        total_minutes = total_seconds // 60
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        if h and m:
            body = f"{h} h {m} min"
        elif h:
            body = f"{h} h"
        else:
            body = f"{m} min"
        return (f"+{body} od úrazu", self._casovy_rozdil_barva(total_minutes))

    def _set_casovy_rozdil_label(self, label, prefix, formatted):
        if formatted is None:
            label.setText(f"{prefix}: nelze spočítat")
            label.setStyleSheet("")
            return
        text, color = formatted
        label.setText(f"{prefix}: {text}")
        label.setStyleSheet(f"color: {color};")

    def _refresh_dukazy_casove_rozdily(self, *_args):
        if not self._casove_rozdily_labels_ready():
            return
        if not hasattr(self, "dukazy_datum") or not hasattr(self, "dukazy_cas"):
            return
        a = self.accident
        accident_dt = None
        if a and a.accident_date and (a.accident_time or "").strip():
            accident_dt = self._datetime_from_date_and_time(a.accident_date, a.accident_time)

        zajisteni_dt = self._datetime_from_date_and_time(
            self._date_value(self.dukazy_datum),
            self.dukazy_cas.text(),
        )
        foto_dt = self._datetime_from_date_and_time(
            self._date_value(self.dukazy_datum_fotek),
            self.dukazy_cas_fotek.text(),
        )
        oznameni_dt = None
        if hasattr(self, "oznameni_datum") and hasattr(self, "oznameni_cas"):
            oznameni_dt = self._datetime_from_date_and_time(
                self._date_value(self.oznameni_datum),
                self.oznameni_cas.text(),
            )

        oznameni_rozdil = self._format_od_urazu_rozdil(
            accident_dt, oznameni_dt, "Čas oznámení je před vznikem úrazu."
        )
        zajisteni_rozdil = self._format_od_urazu_rozdil(
            accident_dt, zajisteni_dt, "Zajištění důkazů je před vznikem úrazu."
        )
        foto_rozdil = self._format_od_urazu_rozdil(
            accident_dt, foto_dt, "Fotodokumentace je před vznikem úrazu."
        )

        self._set_casovy_rozdil_label(self.dukazy_rozdil_oznameni_label, "Oznámení úrazu", oznameni_rozdil)
        self._set_casovy_rozdil_label(self.dukazy_rozdil_zajisteni_label, "Zajištění důkazů", zajisteni_rozdil)
        self._set_casovy_rozdil_label(self.dukazy_rozdil_foto_label, "Fotodokumentace", foto_rozdil)

        if hasattr(self, "dukazy_casova_upozorneni_label"):
            if zajisteni_dt and foto_dt and foto_dt < zajisteni_dt:
                self.dukazy_casova_upozorneni_label.setText(
                    "Fotodokumentace byla pořízena před zajištěním důkazů. Zkontrolujte správnost údajů."
                )
                self.dukazy_casova_upozorneni_label.setStyleSheet("color: #b8860b;")
                self.dukazy_casova_upozorneni_label.setVisible(True)
            else:
                self.dukazy_casova_upozorneni_label.setText("")
                self.dukazy_casova_upozorneni_label.setStyleSheet("")
                self.dukazy_casova_upozorneni_label.setVisible(False)

    def _sync_dukazy_cas_fotek_from_provedeni(self, text):
        if self._dukazy_cas_fotek_manual:
            return
        self._dukazy_syncing_cas_fotek = True
        self.dukazy_cas_fotek.setText(text)
        self._dukazy_syncing_cas_fotek = False

    def _on_dukazy_cas_fotek_user_edit(self, _text):
        if self._dukazy_syncing_cas_fotek:
            return
        self._dukazy_cas_fotek_manual = True

    def _init_ohledani_mista_widgets(self):
        from core.widgets.thp_worker_selector import ThpWorkerSelector
        from core.widgets.workplace_selector import WorkplaceSelector

        saved = self._zajisteni_saved_data

        self.ohledani_zapsal = ThpWorkerSelector()
        self.ohledani_zapsal.setEditable(True)
        if saved.get("ohledani_zapsal"):
            self.ohledani_zapsal.setCurrentText(saved.get("ohledani_zapsal", ""))

        self.ohledani_provoz = WorkplaceSelector()
        self.ohledani_provoz.setEditable(True)
        if saved.get("ohledani_provoz"):
            self.ohledani_provoz.setCurrentText(saved.get("ohledani_provoz", ""))
        self.ohledani_provedli = QTextEdit()
        self.ohledani_provedli.setPlainText(saved.get("ohledani_provedli", ""))
        self.ohledani_zahajeni = QLineEdit(saved.get("ohledani_zahajeni", ""))
        self.ohledani_ukonceni = QLineEdit(saved.get("ohledani_ukonceni", ""))
        self.ohledani_popis_mista = QTextEdit()
        self.ohledani_popis_mista.setPlainText(saved.get("ohledani_popis_mista", ""))
        self.ohledani_priloha = QLineEdit(saved.get("ohledani_priloha", ""))
        self.ohledani_priloha.setReadOnly(True)

    def _photo_row(self, form_layout, label):
        row = QHBoxLayout()
        btn = QPushButton("Vložit fotku")
        status = QLabel("Nepřiloženo")
        photo_keys = {
            "Celkový pohled na místo:": "CelkovyPohled",
            "Přístupová trasa:": "PristupovaTrasa",
            "Směr pohybu postiženého:": "SmerPohybu",
            "Detail místa úrazu:": "DetailMista",
            "Detail možné příčiny:": "DetailMoznePriciny",
            "Použité zařízení / nástroj:": "ZarizeniNastroj",
            "OOPP, zejména obuv u pádů:": "OOPP",
            "Značení nebo jeho absence:": "Znaceni",
        }
        key = photo_keys.get(label, self._slug(label))
        saved_name = self.dukazy_photo_paths.get(key, "")
        if saved_name:
            status.setText(f"Přiloženo: {saved_name}")
        self.dukazy_photo_statuses[key] = status
        btn.clicked.connect(lambda checked=False, st=status, item_key=key: self._select_photo(st, item_key))
        row.addWidget(btn)
        row.addWidget(status)
        row.addStretch()
        form_layout.addRow(label, row)

    def _select_photo(self, status_label, item_key):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyberte fotografii",
            "",
            "Obrázky (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff);;Všechny soubory (*)",
        )
        if not file_path:
            return

        source = Path(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"Foto-{item_key}-{self._accident_number_slug()}_{timestamp}{source.suffix.lower()}"
        attachment = None
        if self.accident is not None:
            attachment = attachment_service.add_file_as("accident", self.accident.id, str(source), new_name)
        final_name = attachment.filename if attachment is not None else new_name
        self.dukazy_photo_paths[item_key] = final_name
        status_label.setText(f"Přiloženo: {final_name}")

    def _register_caszarizeni_rows(self, rows):
        self.caszarizeni_rows = rows
        saved_visible = int(self._zajisteni_saved_data.get("caszarizeni_visible_rows", 1) or 1)
        self.caszarizeni_visible_rows = max(1, min(saved_visible, len(rows)))
        for idx, widgets in enumerate(rows, start=1):
            visible = idx <= self.caszarizeni_visible_rows
            for widget in widgets:
                widget.setVisible(visible)

    def add_caszarizeni_row(self):
        current = getattr(self, "caszarizeni_visible_rows", 1)
        if current >= len(self.caszarizeni_rows):
            return
        self.caszarizeni_visible_rows = current + 1
        for widget in self.caszarizeni_rows[self.caszarizeni_visible_rows - 1]:
            widget.setVisible(True)

    def add_caszarizeni_photo(self, row):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyberte fotografii času zařízení",
            "",
            "Obrázky (*.jpg *.jpeg *.png *.webp *.bmp *.tif *.tiff);;Všechny soubory (*)",
        )
        if file_path:
            source = Path(file_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            device_name = getattr(self, f"caszarizeni_{row}_zarizeni").text().strip() or f"Zarizeni{row}"
            new_name = f"Foto-CasZarizeni-{self._slug(device_name)}-{self._accident_number_slug()}_{timestamp}{source.suffix.lower()}"
            attachment = None
            if self.accident is not None:
                attachment = attachment_service.add_file_as("accident", self.accident.id, str(source), new_name)
            final_name = attachment.filename if attachment is not None else new_name
            getattr(self, f"caszarizeni_{row}_foto").setText(final_name)


    def _parse_time_minutes(self, text):
        text = (text or "").strip()
        if not text:
            return None
        text = text.replace(".", ":")
        parts = text.split(":")
        try:
            if len(parts) == 1:
                h = int(parts[0])
                m = 0
            else:
                h = int(parts[0])
                m = int(parts[1])
            if h < 0 or h > 23 or m < 0 or m > 59:
                return None
            s=int(parts[2]) if len(parts)>2 else 0
            if s<0 or s>59:return None
            return h*3600+m*60+s
        except Exception:
            return None

    def _format_time_minutes(self, minutes):
        if minutes is None:
            return ""
        minutes = minutes % (24 * 3600)
        h=minutes//3600; m=(minutes%3600)//60; s=minutes%60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _format_time_delta(self, minutes):
        if minutes is None:
            return ""
        sign = "+" if minutes >= 0 else "-"
        minutes=abs(minutes)
        h=minutes//3600; m=(minutes%3600)//60; s=minutes%60
        return f"{sign}{h:02d}:{m:02d}:{s:02d}"

    def _caszarizeni_row_offset(self, row):
        cas_zarizeni = self._parse_time_minutes(getattr(self, f"caszarizeni_{row}_cas_zarizeni").text())
        cas_ref = self._parse_time_minutes(getattr(self, f"caszarizeni_{row}_cas_mobil").text())
        if cas_zarizeni is None or cas_ref is None:
            return None
        return cas_zarizeni - cas_ref

    def _caszarizeni_reference_row(self):
        value = self.caszarizeni_reference_source.currentText().strip() if hasattr(self, "caszarizeni_reference_source") else ""
        if not value or value.startswith("Mobil"):
            return None
        for i in range(1, 11):
            name = getattr(self, f"caszarizeni_{i}_zarizeni").text().strip()
            if name and value == name:
                return i
        return None

    def _refresh_caszarizeni_reference_choices(self):
        if not hasattr(self, "caszarizeni_reference_source"):
            return
        current = self.caszarizeni_reference_source.currentText().strip()
        self.caszarizeni_reference_source.blockSignals(True)
        self.caszarizeni_reference_source.clear()
        self.caszarizeni_reference_source.addItem("Mobil / referenční čas v řádcích")
        for i in range(1, 11):
            name = getattr(self, f"caszarizeni_{i}_zarizeni").text().strip()
            if name:
                self.caszarizeni_reference_source.addItem(name)
        idx = self.caszarizeni_reference_source.findText(current)
        self.caszarizeni_reference_source.setCurrentIndex(idx if idx >= 0 else 0)
        self.caszarizeni_reference_source.blockSignals(False)
        self._recalculate_caszarizeni()

    def _recalculate_caszarizeni(self):
        if not hasattr(self, "caszarizeni_srovnani_cas"):
            return
        srovnani = self._parse_time_minutes(self.caszarizeni_srovnani_cas.text())
        ref_row = self._caszarizeni_reference_row()
        if srovnani is None:
            base_ref_time = None
        elif ref_row is None:
            base_ref_time = srovnani
        else:
            ref_offset = self._caszarizeni_row_offset(ref_row)
            base_ref_time = None if ref_offset is None else srovnani - ref_offset

        for i in range(1, 11):
            offset = self._caszarizeni_row_offset(i)
            getattr(self, f"caszarizeni_{i}_rozdil").setText(self._format_time_delta(offset))
            if base_ref_time is None or offset is None:
                getattr(self, f"caszarizeni_{i}_srovnany_cas").setText("")
            else:
                getattr(self, f"caszarizeni_{i}_srovnany_cas").setText(self._format_time_minutes(base_ref_time + offset))

    def _connect_caszarizeni_calculation(self):
        if not hasattr(self, "caszarizeni_srovnani_cas"):
            return
        self.caszarizeni_srovnani_cas.textChanged.connect(self._recalculate_caszarizeni)
        self.caszarizeni_reference_source.currentTextChanged.connect(self._recalculate_caszarizeni)
        for i in range(1, 11):
            getattr(self, f"caszarizeni_{i}_zarizeni").textChanged.connect(self._refresh_caszarizeni_reference_choices)
            getattr(self, f"caszarizeni_{i}_cas_zarizeni").textChanged.connect(self._recalculate_caszarizeni)
            getattr(self, f"caszarizeni_{i}_cas_mobil").textChanged.connect(self._recalculate_caszarizeni)
        self._refresh_caszarizeni_reference_choices()


    def _init_dodrzovani_predpisu_widgets(self):
        saved = self._zajisteni_saved_data

        self.dodrz_pracovni_doba = self._radio_choice(["Dle grafu", "Mimo graf"])
        self._set_radio_choice(self.dodrz_pracovni_doba, saved.get("dodrz_pracovni_doba", ""))
        self.dodrz_prescasy = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.dodrz_prescasy, saved.get("dodrz_prescasy", ""))
        self.dodrz_prescasy_detail = QTextEdit()
        self.dodrz_prescasy_detail.setPlainText(saved.get("dodrz_prescasy_detail", ""))
        self.dodrz_prescasy_detail.setMinimumHeight(90)

        self.dodrz_predpisy_cinnost = QTextEdit()
        self.dodrz_predpisy_cinnost.setPlainText(saved.get("dodrz_predpisy_cinnost", ""))

        self.dodrz_oopp_rows = []
        for data in (saved.get("dodrz_oopp_rows") or [{}]):
            row = self._make_oopp_row(data)
            self.dodrz_oopp_rows.append(row)

        self.dodrz_skoleni_rows = []
        for data in (saved.get("dodrz_skoleni_rows") or [{}]):
            row = self._make_skoleni_row(data)
            self.dodrz_skoleni_rows.append(row)

        self.dodrz_lekar_typ = QComboBox()
        self.dodrz_lekar_typ.addItems(["Periodická", "Vstupní", "Mimořádná", "Výstupní", "Následná"])
        if saved.get("dodrz_lekar_typ"):
            self.dodrz_lekar_typ.setCurrentText(saved.get("dodrz_lekar_typ"))
        self.dodrz_lekar_datum = self._new_date_edit()
        self.dodrz_lekar_platnost = self._new_date_edit()
        if saved.get("dodrz_lekar_datum"): self._set_date_widget(self.dodrz_lekar_datum, saved.get("dodrz_lekar_datum"))
        if saved.get("dodrz_lekar_platnost"): self._set_date_widget(self.dodrz_lekar_platnost, saved.get("dodrz_lekar_platnost"))

        self.dodrz_kvalifikace_splnuje = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.dodrz_kvalifikace_splnuje, saved.get("dodrz_kvalifikace_splnuje", ""))
        self.dodrz_kvalifikace_poznamka = QTextEdit(); self.dodrz_kvalifikace_poznamka.setPlainText(saved.get("dodrz_kvalifikace_poznamka", ""))
        self.dodrz_kontroly_reviz_zavady = QTextEdit(); self.dodrz_kontroly_reviz_zavady.setPlainText(saved.get("dodrz_kontroly_reviz_zavady", ""))

        self.dodrz_zkousky_rows = []
        for data in (saved.get("dodrz_zkousky_rows") or [{}]):
            row = self._make_zkouska_row(data)
            self.dodrz_zkousky_rows.append(row)

        self.dodrz_ostatni_1 = QTextEdit(); self.dodrz_ostatni_1.setPlainText(saved.get("dodrz_ostatni_1", ""))
        self.dodrz_oopp_pouzity = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.dodrz_oopp_pouzity, saved.get("dodrz_oopp_pouzity", ""))
        self.dodrz_stav_oopp = QTextEdit(); self.dodrz_stav_oopp.setPlainText(saved.get("dodrz_stav_oopp", ""))
        self.dodrz_vyjadreni_oopp = QTextEdit(); self.dodrz_vyjadreni_oopp.setPlainText(saved.get("dodrz_vyjadreni_oopp", ""))

        def make_kontrola_rows(key):
            rows = []
            for data in (saved.get(key) or [{}]):
                row = {"datum": self._new_date_edit(), "kontroloval": self._new_thp_lineedit(data.get("kontroloval", "")), "vysledek": QLineEdit(data.get("vysledek", ""))}
                if data.get("datum"): self._set_date_widget(row["datum"], data.get("datum"))
                rows.append(row)
            return rows
        self.dodrz_kontrola_oopp_rows = make_kontrola_rows("dodrz_kontrola_oopp_rows")
        self.dodrz_kontrola_predpisu_rows = make_kontrola_rows("dodrz_kontrola_predpisu_rows")

        self.dodrz_poruseni_predpisu = QTextEdit(); self.dodrz_poruseni_predpisu.setPlainText(saved.get("dodrz_poruseni_predpisu", ""))
        self.dodrz_ostatni_2 = QTextEdit(); self.dodrz_ostatni_2.setPlainText(saved.get("dodrz_ostatni_2", ""))
        self.dodrz_priloha = QLineEdit(saved.get("dodrz_priloha", "")); self.dodrz_priloha.setReadOnly(True)


    def _thp_names(self):
        try:
            return [w.display_name for w in settings_service.get_workers(include_inactive=False) if getattr(w, "display_name", "")]
        except Exception:
            return []

    def _widget_text(self, widget):
        if hasattr(widget, "currentText"):
            return widget.currentText().strip()
        if hasattr(widget, "text"):
            return widget.text().strip()
        return ""

    def _new_thp_lineedit(self, value=""):
        combo = SearchComboBox(self._thp_names(), self, allow_custom_value=True)
        combo.set_value(value or "")
        return combo

    def _connect_prescasy_detail_visibility(self):
        def refresh():
            self.dodrz_prescasy_detail.setVisible(self._radio_choice_value(self.dodrz_prescasy) == "ANO")
        for button in self.dodrz_prescasy.findChildren(QRadioButton):
            button.toggled.connect(refresh)
        refresh()

    def _make_oopp_row(self, data=None):
        data = data or {}
        row = {"typ": QLineEdit(data.get("typ", "")), "datum": self._new_date_edit(), "platnost": QLineEdit(data.get("platnost", "")), "poznamka": QLineEdit(data.get("poznamka", ""))}
        if data.get("datum"):
            self._set_date_widget(row["datum"], data.get("datum"))
        return row

    def _make_skoleni_row(self, data=None):
        data = data or {}
        row = {"typ": QLineEdit(data.get("typ", "")), "datum": self._new_date_edit(), "osnova": self._radio_choice(["ANO", "NE"]), "poznamka": QLineEdit(data.get("poznamka", ""))}
        if data.get("datum"):
            self._set_date_widget(row["datum"], data.get("datum"))
        self._set_radio_choice(row["osnova"], data.get("osnova", ""))
        return row

    def _make_zkouska_row(self, data=None):
        data = data or {}
        row = {"typ": QLineEdit(data.get("typ", "")), "datum": self._new_date_edit(), "platnost": self._new_date_edit(), "poznamka": QLineEdit(data.get("poznamka", ""))}
        if data.get("datum"):
            self._set_date_widget(row["datum"], data.get("datum"))
        if data.get("platnost"):
            self._set_date_widget(row["platnost"], data.get("platnost"))
        return row

    def add_dodrz_oopp_row(self):
        row = self._make_oopp_row()
        self.dodrz_oopp_rows.append(row)
        if hasattr(self, "dodrz_oopp_layout"):
            self.dodrz_oopp_layout.insertLayout(self.dodrz_oopp_layout.count() - 1, self._row_widgets_layout([row["typ"], row["datum"], row["platnost"], row["poznamka"]]))

    def add_dodrz_skoleni_row(self):
        row = self._make_skoleni_row()
        self.dodrz_skoleni_rows.append(row)
        if hasattr(self, "dodrz_skoleni_layout"):
            self.dodrz_skoleni_layout.insertLayout(self.dodrz_skoleni_layout.count() - 1, self._row_widgets_layout([row["typ"], row["datum"], row["osnova"], row["poznamka"]]))

    def add_dodrz_zkouska_row(self):
        row = self._make_zkouska_row()
        self.dodrz_zkousky_rows.append(row)
        if hasattr(self, "dodrz_zkousky_layout"):
            self.dodrz_zkousky_layout.insertLayout(self.dodrz_zkousky_layout.count() - 1, self._row_widgets_layout([row["typ"], row["datum"], row["platnost"], row["poznamka"]]))

    def _row_widgets_layout(self, widgets):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        for widget in widgets:
            row.addWidget(widget)
        return row

    def _add_textedit_row(self, form, label, widget, height=160):
        widget.setMinimumHeight(height)
        form.addRow(label, widget)



    def _make_analyza_textedit(self, key, placeholder=""):
        widget = QTextEdit()
        widget.setPlainText(self._zajisteni_saved_data.get(key, ""))
        if placeholder:
            widget.setPlaceholderText(placeholder)
        return widget

    def _set_analyza_checkbox_values(self, group_key):
        saved = (self._zajisteni_saved_data.get("analyza_faktory", {}) or {}).get(group_key, {}) or {}
        saved_checks = saved.get("checkboxes", {}) or {}
        group = self.analyza_faktory[group_key]
        for key, checkbox in group["checkboxes"].items():
            checkbox.setChecked(bool(saved_checks.get(key, False)))
        if group.get("praxe") is not None:
            group["praxe"].setCurrentText(saved.get("praxe", ""))
        if group.get("aktualizace_rizik") is not None:
            group["aktualizace_rizik"].setPlainText(saved.get("aktualizace_rizik", ""))
        group["popis"].setPlainText(saved.get("popis", ""))

    def _init_analyza_pricin_widgets(self):
        saved = self._zajisteni_saved_data

        self.analyza_shrnuti_skutecneho_stavu = self._make_analyza_textedit("analyza_shrnuti_skutecneho_stavu")
        self.analyza_zjistene_skutecnosti = self._make_analyza_textedit("analyza_zjistene_skutecnosti")
        self.analyza_prvotni_pricina = self._make_analyza_textedit(
            "analyza_prvotni_pricina",
            "Pracovní hypotéza před provedením vlastní analýzy příčin.",
        )

        faktor_defs = {
            "clovek": {
                "items": [
                    ("nedodrzeni_postupu", "Nedodržení pracovního postupu"),
                    ("nespravne_pouziti_zarizeni", "Nesprávné použití zařízení"),
                    ("nepozornost", "Nepozornost"),
                    ("spech", "Spěch"),
                    ("unava", "Únava"),
                    ("stres", "Stres"),
                    ("zdravotni_indispozice", "Zdravotní indispozice"),
                    ("nedostatecna_kvalifikace", "Nedostatečná kvalifikace"),
                    ("rutina", "Rutina"),
                    ("podceneni_rizika", "Podcenění rizika"),
                    ("pouzivani_telefonu", "Používání telefonu"),
                    ("jine", "Jiné"),
                ],
                "praxe": True,
                "aktualizace_rizik": False,
            },
            "zarizeni_technika": {
                "items": [
                    ("technicka_zavada", "Technická závada"),
                    ("neprovedena_revize", "Neprovedená revize"),
                    ("neprovedena_kontrola", "Neprovedená kontrola"),
                    ("nefunkcni_ochranne_prvky", "Nefunkční ochranné prvky"),
                    ("nespravne_pouziti_zarizeni", "Nesprávné použití zařízení"),
                    ("nevyhovujici_technicky_stav", "Nevyhovující technický stav"),
                ],
                "praxe": False,
                "aktualizace_rizik": False,
            },
            "material": {
                "items": [
                    ("nevhodny_material", "Nevhodný materiál"),
                    ("poskozeny_material", "Poškozený materiál"),
                    ("skryta_vada", "Skrytá vada"),
                    ("nestabilita", "Nestabilita"),
                    ("nevhodne_skladovani", "Nevhodné skladování"),
                ],
                "praxe": False,
                "aktualizace_rizik": False,
            },
            "pracovni_prostredi": {
                "items": [
                    ("osvetleni", "Osvětlení"),
                    ("hluk", "Hluk"),
                    ("prasnost", "Prašnost"),
                    ("teplota", "Teplota"),
                    ("pocasi", "Počasí"),
                    ("poradek_na_pracovisti", "Pořádek na pracovišti"),
                    ("prostorove_podminky", "Prostorové podmínky"),
                    ("komunikace", "Komunikace"),
                ],
                "praxe": False,
                "aktualizace_rizik": False,
            },
            "organizace_prace_rizeni": {
                "items": [
                    ("situace_ve_vyhodnoceni_rizik", "Situace je ve vyhodnocení rizik"),
                    ("nutna_aktualizace_rizik", "Nutná aktualizace vyhodnocení rizik"),
                    ("nedostatecne_opatreni_v_rizicich", "Nedostatečné opatření ve vyhodnocení rizik"),
                    ("casovy_tlak", "Časový tlak"),
                    ("nedostatek_pracovniku", "Nedostatek pracovníků"),
                    ("nejasne_odpovednosti", "Nejasné odpovědnosti"),
                    ("nedostatecna_kontrola_vedoucim", "Nedostatečná kontrola vedoucím"),
                    ("nevyhovujici_organizace_prace", "Nevyhovující organizace práce"),
                ],
                "praxe": False,
                "aktualizace_rizik": True,
            },
            "skoleni_dokumentace": {
                "items": [
                    ("skoleni_neprobehlo", "Školení neproběhlo"),
                    ("skoleni_nebylo_platne", "Školení nebylo platné"),
                    ("skoleni_nebylo_prokazatelne", "Školení nebylo prokazatelné"),
                    ("chybel_pracovni_postup", "Chyběl pracovní postup"),
                    ("postup_nebyl_aktualni", "Postup nebyl aktuální"),
                    ("zamestnanec_nebyl_seznamen", "Zaměstnanec nebyl seznámen"),
                    ("nedostatecne_zaskoleni", "Nedostatečné zaškolení"),
                ],
                "praxe": False,
                "aktualizace_rizik": False,
            },
            "oopp_bezpecnostni_opatreni": {
                "items": [
                    ("oopp_nebyly_predepsany", "OOPP nebyly předepsány"),
                    ("oopp_nebyly_vydany", "OOPP nebyly vydány"),
                    ("oopp_nebyly_pouzity", "OOPP nebyly použity"),
                    ("oopp_pouzity_nespravne", "OOPP byly použity nesprávně"),
                    ("chybela_technicka_ochrana", "Chyběla technická ochrana"),
                    ("chybelo_bezpecnostni_znaceni", "Chybělo bezpečnostní značení"),
                ],
                "praxe": False,
                "aktualizace_rizik": False,
            },
        }

        self.analyza_faktor_defs = faktor_defs
        self.analyza_kategorie_labels = {
            "clovek": "Člověk",
            "zarizeni_technika": "Zařízení a technika",
            "material": "Materiál",
            "pracovni_prostredi": "Pracovní prostředí",
            "organizace_prace_rizeni": "Organizace práce a řízení",
            "skoleni_dokumentace": "Školení a dokumentace",
            "oopp_bezpecnostni_opatreni": "OOPP a bezpečnostní opatření",
        }
        self.analyza_klasifikace_saved_rows = saved.get("analyza_klasifikace_rows", []) or []
        self.analyza_klasifikace_rows = []
        self.analyza_klasifikace_rows_layout = None

        self.analyza_faktory = {}
        for group_key, group_def in faktor_defs.items():
            self.analyza_faktory[group_key] = {
                "checkboxes": {key: QCheckBox(label) for key, label in group_def["items"]},
                "praxe": QComboBox() if group_def.get("praxe") else None,
                "aktualizace_rizik": QTextEdit() if group_def.get("aktualizace_rizik") else None,
                "popis": QTextEdit(),
            }
            if self.analyza_faktory[group_key]["praxe"] is not None:
                self.analyza_faktory[group_key]["praxe"].setEditable(True)
                self.analyza_faktory[group_key]["praxe"].addItems(["", "Nový zaměstnanec", "Zkušený zaměstnanec", "Dlouhodobá praxe", "Krátká praxe", "Nezjištěno"])
            if self.analyza_faktory[group_key]["aktualizace_rizik"] is not None:
                self.analyza_faktory[group_key]["aktualizace_rizik"].setPlaceholderText(
                    "Např. doplnit mechanismus úrazu, upřesnit opatření, aktualizovat registr rizik."
                )
            self._set_analyza_checkbox_values(group_key)

        self.analyza_proc_1 = self._make_analyza_textedit("analyza_proc_1", "Proč došlo k úrazu nebo nebezpečné situaci?")
        self.analyza_proc_2 = self._make_analyza_textedit("analyza_proc_2", "Proč tato situace vznikla?")
        self.analyza_proc_3 = self._make_analyza_textedit("analyza_proc_3", "Proč nebyla zachycena nebo odstraněna dříve?")
        self.analyza_proc_4 = self._make_analyza_textedit("analyza_proc_4", "Proč systém umožnil, aby k tomu došlo?")
        self.analyza_proc_5 = self._make_analyza_textedit(
            "analyza_proc_5",
            "Jaká systémová / kořenová příčina z toho plyne? Odpověď by měla vysvětlovat, co je nutné změnit v systému, aby se obdobná událost neopakovala.",
        )

        self.analyza_bezprostredni_pricina = self._make_analyza_textedit(
            "analyza_bezprostredni_pricina",
            "Výstup lze vygenerovat z klasifikace faktorů nebo upravit ručně.",
        )
        self.analyza_korenova_pricina = self._make_analyza_textedit(
            "analyza_korenova_pricina",
            "Systémová příčina, jejíž odstranění má zabránit opakování obdobného úrazu.",
        )
        self.analyza_prispivajici_priciny = self._make_analyza_textedit(
            "analyza_prispivajici_priciny",
            "Vedlejší / přispívající okolnosti, které se na vzniku úrazu podílely.",
        )
        self.analyza_overeni_korenove_priciny = {}
        saved_overeni = saved.get("analyza_overeni_korenove_priciny", {}) or {}
        for key, label in [
            ("dolozena_dukazy", "Je doložena důkazy"),
            ("vysvetluje_mechanismus", "Vysvětluje mechanismus úrazu"),
            ("overena_v_prubehu", "Byla ověřena v průběhu šetření"),
            ("odstraneni_zabrani_opakovani", "Odstranění příčiny by mělo zabránit opakování"),
        ]:
            cb = QCheckBox(label)
            cb.setChecked(bool(saved_overeni.get(key, False)))
            self.analyza_overeni_korenove_priciny[key] = cb
        self.analyza_poznamka_bozp = self._make_analyza_textedit("analyza_poznamka_bozp")

    def _add_analyza_section(self, layout, title, group_key, subtitle=None, question=None):
        button = QPushButton(f"▸ {title}")
        button.setCheckable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 6, 10, 6)
        content.setVisible(False)

        def toggle(checked):
            content.setVisible(checked)
            button.setText(("▾ " if checked else "▸ ") + title)
        button.toggled.connect(toggle)

        if subtitle and subtitle.strip() != title.strip():
            content_layout.addWidget(QLabel(subtitle))
        if question:
            q = QLabel(question)
            q.setWordWrap(True)
            content_layout.addWidget(q)

        group = self.analyza_faktory[group_key]
        checkbox_group = QGroupBox(title)
        checkbox_layout = QVBoxLayout(checkbox_group)
        for checkbox in group["checkboxes"].values():
            checkbox_layout.addWidget(checkbox)
        content_layout.addWidget(checkbox_group)

        form = QFormLayout()
        if group.get("praxe") is not None:
            form.addRow("Praxe zaměstnance:", group["praxe"])
        if group.get("aktualizace_rizik") is not None:
            group["aktualizace_rizik"].setMinimumHeight(140)
            form.addRow("Popis potřebné aktualizace vyhodnocení rizik:", group["aktualizace_rizik"])
        group["popis"].setMinimumHeight(170)
        form.addRow("Popis zjištění:", group["popis"])
        content_layout.addLayout(form)

        layout.addWidget(button)
        layout.addWidget(content)
        return button, content

    def _analyza_selected_factors(self):
        selected = []
        for group_key, group in self.analyza_faktory.items():
            category = self.analyza_kategorie_labels.get(group_key, group_key)
            for checkbox in group["checkboxes"].values():
                if checkbox.isChecked():
                    selected.append((checkbox.text(), category))
        return selected

    def _clear_analyza_klasifikace_rows(self):
        if self.analyza_klasifikace_rows_layout is None:
            return
        while self.analyza_klasifikace_rows_layout.count():
            item = self.analyza_klasifikace_rows_layout.takeAt(0)
            widget = item.widget()
            layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif layout is not None:
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget() is not None:
                        child.widget().deleteLater()
                layout.deleteLater()
        self.analyza_klasifikace_rows = []

    def _add_analyza_klasifikace_row(self, faktor, kategorie, typ="Bezprostřední"):
        if self.analyza_klasifikace_rows_layout is None:
            return
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)

        faktor_label = QLabel(faktor)
        kategorie_label = QLabel(kategorie)
        typ_combo = QComboBox()
        typ_combo.addItems(["Bezprostřední", "Kořenová", "Přispívající"])
        if typ:
            typ_combo.setCurrentText(typ)

        row_layout.addWidget(faktor_label, 5)
        row_layout.addWidget(kategorie_label, 2)
        row_layout.addWidget(typ_combo, 1)
        self.analyza_klasifikace_rows_layout.addLayout(row_layout)
        self.analyza_klasifikace_rows.append({
            "faktor": faktor_label,
            "kategorie": kategorie_label,
            "typ": typ_combo,
        })

    def load_analyza_marked_factors(self):
        previous_types = {
            (row["faktor"].text().strip(), row["kategorie"].text().strip()): row["typ"].currentText().strip()
            for row in getattr(self, "analyza_klasifikace_rows", [])
        }
        self._clear_analyza_klasifikace_rows()
        for faktor, kategorie in self._analyza_selected_factors():
            typ = previous_types.get((faktor, kategorie), "Bezprostřední")
            self._add_analyza_klasifikace_row(faktor, kategorie, typ)

    def _load_saved_analyza_klasifikace_rows(self):
        if not self.analyza_klasifikace_saved_rows:
            return
        self._clear_analyza_klasifikace_rows()
        for row in self.analyza_klasifikace_saved_rows:
            self._add_analyza_klasifikace_row(
                row.get("faktor", ""),
                row.get("kategorie", ""),
                row.get("typ", "Bezprostřední"),
            )

    def generate_analyza_output(self):
        grouped = {"Bezprostřední": [], "Kořenová": [], "Přispívající": []}
        for row in getattr(self, "analyza_klasifikace_rows", []):
            faktor = row["faktor"].text().strip()
            kategorie = row["kategorie"].text().strip()
            typ = row["typ"].currentText().strip()
            if faktor and typ in grouped:
                grouped[typ].append(f"- {faktor} ({kategorie})")

        self.analyza_bezprostredni_pricina.setPlainText("\n".join(grouped["Bezprostřední"]))
        self.analyza_korenova_pricina.setPlainText("\n".join(grouped["Kořenová"]))
        self.analyza_prispivajici_priciny.setPlainText("\n".join(grouped["Přispívající"]))

    def aktualizovat_analyza_z_podkladu(self):
        """Načte do analýzy stručný souhrn objektivních podkladů k úrazu.

        Účel tlačítka není přenášet dílčí checkboxy a závěry šetření, ale připravit
        technikovi BOZP rychlý přehled skutkového stavu a zajištěných podkladů.
        Vlastní hodnocení příčin zůstává až v části Ishikawa / 5× Proč.
        """
        a = self.accident

        def _text(value):
            return str(value).strip() if value is not None else ""

        def _date_text(value):
            if not value:
                return ""
            try:
                return value.strftime("%d.%m.%Y")
            except Exception:
                return _text(value)

        def _has_text(widget):
            if widget is None:
                return False
            if hasattr(widget, "toPlainText"):
                return bool(widget.toPlainText().strip())
            if hasattr(widget, "text"):
                return bool(widget.text().strip())
            if hasattr(widget, "currentText"):
                return bool(widget.currentText().strip())
            return False

        def _any_checked(items):
            return any(cb.isChecked() for cb in items)

        skutkovy_lines = []
        if a is not None:
            datum = _date_text(getattr(a, "accident_date", None))
            cas = _text(getattr(a, "accident_time", ""))
            zamestnanec = _text(getattr(a, "employee_name", ""))
            misto = _text(getattr(a, "misto_urazu", "")) or _text(getattr(a, "workplace_name", "")) or _text(getattr(a, "pracoviste", ""))
            cinnost = (
                _text(getattr(a, "cinnost", ""))
                or _text(getattr(a, "kod_cinnosti", ""))
                or _text(getattr(a, "druh_cinnosti", ""))
                or _text(getattr(a, "druh_vykonavane_prace", ""))
            )

            veta = ""
            if datum or cas or zamestnanec or misto or cinnost:
                veta = "Dne"
                if datum:
                    veta += f" {datum}"
                if cas:
                    veta += f" v {cas}"
                if zamestnanec:
                    veta += f" došlo k úrazu zaměstnance {zamestnanec}"
                else:
                    veta += " došlo k pracovnímu úrazu"
                if misto:
                    veta += f" na místě: {misto}"
                if cinnost:
                    veta += f" při činnosti: {cinnost}"
                veta += "."
                skutkovy_lines.append(veta)

            popis = (
                _text(getattr(a, "popis_urazoveho_deje", ""))
                or (self.oznameni_popis.toPlainText().strip() if hasattr(self, "oznameni_popis") else "")
            )
            if popis:
                skutkovy_lines.append(f"Popis události dle oznámení: {popis}")

            druh_zraneni = _text(getattr(a, "druh_zraneni", ""))
            zranena_cast = (
                _text(getattr(a, "zranena_cast", ""))
                or _text(getattr(a, "zranena_cast_tela", ""))
                or _text(getattr(a, "zranena_cast_tela_text", ""))
            )
            zraneni_parts = []
            if druh_zraneni:
                zraneni_parts.append(druh_zraneni)
            if zranena_cast:
                zraneni_parts.append(zranena_cast)
            if zraneni_parts:
                skutkovy_lines.append("Zranění: " + "; ".join(zraneni_parts) + ".")

        if skutkovy_lines:
            self.analyza_shrnuti_skutecneho_stavu.setPlainText("\n\n".join(skutkovy_lines))

        zjisteni = []

        pocet_svedku = self.dukazy_pocet_svedku.value() if hasattr(self, "dukazy_pocet_svedku") else 0
        if pocet_svedku > 0:
            if pocet_svedku == 1:
                zjisteni.append("Byl zjištěn 1 svědek.")
            elif 2 <= pocet_svedku <= 4:
                zjisteni.append(f"Byli zjištěni {pocet_svedku} svědci.")
            else:
                zjisteni.append(f"Bylo zjištěno {pocet_svedku} svědků.")

        if hasattr(self, "dukazy_vyjadreni_vracena") and self.dukazy_vyjadreni_vracena.isChecked():
            zjisteni.append("Byla získána písemná vyjádření svědků / poškozeného.")

        if getattr(self, "dukazy_photo_paths", None):
            zjisteni.append("Byla provedena fotodokumentace místa a souvisejících skutečností.")
        elif hasattr(self, "dukazy_datum_fotek") and self._date_to_json(self.dukazy_datum_fotek):
            zjisteni.append("Byla provedena fotodokumentace místa a souvisejících skutečností.")

        if any(_has_text(w) for w in [
            getattr(self, "ohledani_provedli", None),
            getattr(self, "ohledani_zahajeni", None),
            getattr(self, "ohledani_ukonceni", None),
            getattr(self, "ohledani_popis_mista", None),
            getattr(self, "ohledani_priloha", None),
        ]):
            zjisteni.append("Bylo provedeno ohledání místa úrazu.")

        cas_rows = getattr(self, "caszarizeni_visible_rows", 0)
        cas_sync = False
        for i in range(1, cas_rows + 1):
            if _has_text(getattr(self, f"caszarizeni_{i}_zarizeni", None)) and (
                _has_text(getattr(self, f"caszarizeni_{i}_cas_zarizeni", None))
                or _has_text(getattr(self, f"caszarizeni_{i}_cas_mobil", None))
            ):
                cas_sync = True
                break
        if cas_sync:
            zjisteni.append("Byla provedena synchronizace časů zařízení pro časovou osu.")

        dokumenty_widgets = [
            getattr(self, "dukazy_provozni_dokumentace_text", None),
            getattr(self, "dukazy_provozni_zaznamy_text", None),
            getattr(self, "dukazy_poznamka", None),
            getattr(self, "dodrz_priloha", None),
        ]
        if any(_has_text(w) for w in dokumenty_widgets):
            zjisteni.append("Byly zajištěny dokumenty a další důkazní podklady.")

        if any(_has_text(row.get("typ")) for row in getattr(self, "dodrz_oopp_rows", [])) or _has_text(getattr(self, "dodrz_stav_oopp", None)):
            zjisteni.append("Byla provedena kontrola OOPP.")

        if any(_has_text(row.get("typ")) for row in getattr(self, "dodrz_skoleni_rows", [])):
            zjisteni.append("Byla provedena kontrola školení a související dokumentace.")

        if any(_has_text(w) for w in [getattr(self, "dodrz_lekar_typ", None), getattr(self, "dodrz_lekar_datum", None), getattr(self, "dodrz_lekar_platnost", None)]):
            zjisteni.append("Byla provedena kontrola zdravotní způsobilosti.")

        if _has_text(getattr(self, "dodrz_kontroly_reviz_zavady", None)) or any(_has_text(row.get("typ")) for row in getattr(self, "dodrz_zkousky_rows", [])):
            zjisteni.append("Byla provedena kontrola zařízení, revizí nebo odborné způsobilosti.")

        if _has_text(getattr(self, "dodrz_poruseni_predpisu", None)) or _has_text(getattr(self, "dodrz_predpisy_cinnost", None)):
            zjisteni.append("Byla provedena kontrola dodržování předpisů a pracovních postupů.")

        if getattr(self, "soulad_podklady", None) and _any_checked(self.soulad_podklady.values()):
            zjisteni.append("Byla provedena kontrola souladu důkazů.")
        if _has_text(getattr(self, "soulad_vyhodnoceni", None)):
            zjisteni.append("Bylo zpracováno vyhodnocení souladu důkazů.")
        if _has_text(getattr(self, "soulad_popis_nesrovnalosti", None)):
            zjisteni.append("Byly popsány zjištěné nesrovnalosti v podkladech.")

        if zjisteni:
            self.analyza_zjistene_skutecnosti.setPlainText("\n".join(f"- {line}" for line in zjisteni))

        # Prvotní příčina je pracovní hypotéza specialisty BOZP – nepřepisujeme ji automaticky,
        # pokud už ji uživatel vyplnil. Při prázdném poli nabídneme pouze odůvodnění ze souladu důkazů.
        if self.soulad_oduvodneni.toPlainText().strip() and not self.analyza_prvotni_pricina.toPlainText().strip():
            self.analyza_prvotni_pricina.setPlainText(self.soulad_oduvodneni.toPlainText().strip())

    def _init_kontrola_souladu_widgets(self):
        saved = self._zajisteni_saved_data
        self.soulad_podklady = {}
        for key, label in [
            ("vypoved_postizeneho", "Výpověď postiženého"),
            ("vypovedi_svedku", "Výpovědi svědků"),
            ("fotodokumentace", "Fotodokumentace"),
            ("stav_mista", "Stav místa"),
            ("kamerove_zaznamy", "Kamerové záznamy"),
            ("casove_udaje", "Časové údaje"),
            ("lekarska_zprava", "Lékařská zpráva"),
            ("pracovni_postup", "Pracovní postup"),
            ("oopp", "OOPP"),
            ("skoleni", "Školení"),
            ("evidence_prace", "Evidence práce / docházka"),
        ]:
            cb = QCheckBox(label)
            podklady_saved = saved.get("soulad_podklady", {}) or {}
            cb.setChecked(bool(podklady_saved.get(key, saved.get(f"soulad_podklad_{key}", False))))
            self.soulad_podklady[key] = cb

        self.soulad_nesrovnalosti = {}
        for key, label in [
            ("cas", "V čase události"),
            ("misto", "V místě události"),
            ("mechanismus", "V mechanismu úrazu"),
            ("vypovedi", "Ve výpovědích"),
            ("zraneni_popis", "Mezi zraněním a popisem události"),
            ("jine", "Jiné"),
        ]:
            cb = QCheckBox(label)
            nesrovnalosti_saved = saved.get("soulad_nesrovnalosti", {}) or {}
            cb.setChecked(bool(nesrovnalosti_saved.get(key, saved.get(f"soulad_nesrovnalost_{key}", False))))
            self.soulad_nesrovnalosti[key] = cb

        self.soulad_popis_nesrovnalosti = QTextEdit()
        self.soulad_popis_nesrovnalosti.setPlainText(saved.get("soulad_popis_nesrovnalosti", ""))
        self.soulad_vyhodnoceni = QTextEdit()
        self.soulad_vyhodnoceni.setPlainText(saved.get("soulad_vyhodnoceni", ""))

        self.soulad_vzniklo_poskozeni = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.soulad_vzniklo_poskozeni, saved.get("soulad_vzniklo_poskozeni", ""))
        self.soulad_pri_plneni = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.soulad_pri_plneni, saved.get("soulad_pri_plneni", ""))
        self.soulad_nahle_pusobeni = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.soulad_nahle_pusobeni, saved.get("soulad_nahle_pusobeni", ""))
        self.soulad_mimo_praci = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(self.soulad_mimo_praci, saved.get("soulad_mimo_praci", ""))

        self.soulad_stanovisko_bozp = QComboBox()
        self.soulad_stanovisko_bozp.addItems([
            "Jedná se o pracovní úraz",
            "Nejedná se o pracovní úraz",
            "Nelze zatím uzavřít",
        ])
        self.soulad_stanovisko_bozp.setCurrentText(saved.get("soulad_stanovisko_bozp", "Nelze zatím uzavřít"))

        def refresh_stanovisko_bozp():
            hodnoty = [
                self._radio_choice_value(self.soulad_vzniklo_poskozeni),
                self._radio_choice_value(self.soulad_pri_plneni),
                self._radio_choice_value(self.soulad_nahle_pusobeni),
                self._radio_choice_value(self.soulad_mimo_praci),
            ]
            if any(not hodnota for hodnota in hodnoty):
                self.soulad_stanovisko_bozp.setCurrentText("Nelze zatím uzavřít")
            elif hodnoty == ["ANO", "ANO", "ANO", "NE"]:
                self.soulad_stanovisko_bozp.setCurrentText("Jedná se o pracovní úraz")
            else:
                self.soulad_stanovisko_bozp.setCurrentText("Nejedná se o pracovní úraz")

        for skupina in [
            self.soulad_vzniklo_poskozeni,
            self.soulad_pri_plneni,
            self.soulad_nahle_pusobeni,
            self.soulad_mimo_praci,
        ]:
            for button in skupina.findChildren(QRadioButton):
                button.toggled.connect(refresh_stanovisko_bozp)
        refresh_stanovisko_bozp()

        self.soulad_oduvodneni = QTextEdit()
        self.soulad_oduvodneni.setPlainText(saved.get("soulad_oduvodneni", ""))

    def _tab_zajisteni_dukazu(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        intro = QLabel(
            "<b>Cíl:</b> zajistit svědky, místo úrazu, fotodokumentaci a potřebné dokumenty tak, "
            "aby nedošlo ke znehodnocení důkazů nebo sladění výpovědí a mohlo dojít "
            "k řádnému vyšetření okolností a příčin vzniku pracovního úrazu."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        zaklad_group = QGroupBox("Základní údaje")
        zaklad_form = QFormLayout(zaklad_group)
        zaklad_form.addRow("Číslo úrazu:", QLabel(self.accident.number if self.accident else ""))
        zaklad_form.addRow("Datum provedení:", self.dukazy_datum)
        zaklad_form.addRow("Čas provedení:", self.dukazy_cas)
        zaklad_form.addRow("Provedl:", self.dukazy_provedl)

        cas_rozdily_group = QGroupBox("Kontrola časové návaznosti")
        cas_rozdily_layout = QVBoxLayout(cas_rozdily_group)
        cas_rozdily_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        cas_rozdily_layout.addWidget(self.dukazy_rozdil_oznameni_label)
        cas_rozdily_layout.addWidget(self.dukazy_rozdil_zajisteni_label)
        cas_rozdily_layout.addWidget(self.dukazy_rozdil_foto_label)
        cas_rozdily_layout.addWidget(self.dukazy_casova_upozorneni_label)
        cas_rozdily_layout.addStretch()

        top_row = QHBoxLayout()
        top_row.setAlignment(Qt.AlignmentFlag.AlignTop)
        top_row.addWidget(zaklad_group, 1)
        top_row.addWidget(cas_rozdily_group, 1)
        layout.addLayout(top_row)
        self._refresh_dukazy_casove_rozdily()

        svedci_group = QGroupBox("1. Svědci a prvotní vyjádření")
        svedci_outer = QVBoxLayout(svedci_group)
        svedci_form = QFormLayout()
        svedci_form.addRow("Počet zjištěných svědků:", self.dukazy_pocet_svedku)
        self.dukazy_svedci_form = svedci_form
        self._refresh_svedci_rows()
        self.dukazy_pocet_svedku.valueChanged.connect(self._refresh_svedci_rows)
        svedci_outer.addLayout(svedci_form)
        svedci_outer.addWidget(self.dukazy_svedci_oddeleni)
        svedci_outer.addWidget(self.dukazy_vyjadreni_obsahuje_udaje)
        svedci_outer.addWidget(self.dukazy_vyjadreni_vracena)
        svedci_outer.addWidget(self.dukazy_rozhovor_po_vyjadreni)
        layout.addWidget(svedci_group)

        misto_group = QGroupBox("2. Ohledání místa úrazu")
        misto_form = QFormLayout(misto_group)
        for widget in [
            self.dukazy_presne_misto_text,
            self.dukazy_stav_povrchu_text,
            self.dukazy_osvetleni_viditelnost_text,
            self.dukazy_pocasi_podminky_text,
            self.dukazy_prekazky_znaceni_okoli_text,
            self.dukazy_stav_zarizeni_nastroju_oopp_text,
            self.dukazy_chemikalie_skvrny_text,
            self.dukazy_sirsi_okoli_text,
        ]:
            widget.setMinimumHeight(150)
        misto_form.addRow("Přesné místo úrazu:", self.dukazy_presne_misto_text)
        misto_form.addRow("Stav povrchu / podlahy:", self.dukazy_stav_povrchu_text)
        misto_form.addRow("Osvětlení a viditelnost:", self.dukazy_osvetleni_viditelnost_text)
        misto_form.addRow("Počasí nebo vnitřní podmínky:", self.dukazy_pocasi_podminky_text)
        misto_form.addRow("Překážky, značení, širší okolí:", self.dukazy_prekazky_znaceni_okoli_text)
        misto_form.addRow("Stav zařízení, nástrojů a OOPP:", self.dukazy_stav_zarizeni_nastroju_oopp_text)
        misto_form.addRow("Chemikálie, skvrny, nečistoty:", self.dukazy_chemikalie_skvrny_text)
        misto_form.addRow("Širší okolí úrazu:", self.dukazy_sirsi_okoli_text)
        layout.addWidget(misto_group)

        foto_group = QGroupBox("3. Fotodokumentace, video a náčrt")
        foto_layout = QVBoxLayout(foto_group)
        foto_info = QLabel(
            "U každé položky vložte odpovídající fotografii. Po vložení se položka automaticky označí jako splněná "
            "a fotka se uloží do příloh úrazu s jednotným názvem."
        )
        foto_info.setWordWrap(True)
        foto_layout.addWidget(foto_info)
        foto_form_buttons = QFormLayout()
        for label in [
            "Celkový pohled na místo:",
            "Přístupová trasa:",
            "Směr pohybu postiženého:",
            "Detail místa úrazu:",
            "Detail možné příčiny:",
            "Použité zařízení / nástroj:",
            "OOPP, zejména obuv u pádů:",
            "Značení nebo jeho absence:",
        ]:
            self._photo_row(foto_form_buttons, label)
        foto_layout.addLayout(foto_form_buttons)
        foto_layout.addWidget(self.dukazy_nacrt_porizen)
        foto_form = QFormLayout()
        foto_form.addRow("Datum pořízení fotek / videa:", self.dukazy_datum_fotek)
        foto_form.addRow("Čas pořízení fotek / videa:", self.dukazy_cas_fotek)
        foto_layout.addLayout(foto_form)
        layout.addWidget(foto_group)

        cas_group = QGroupBox("Časová synchronizace zařízení")
        cas_layout = QVBoxLayout(cas_group)
        cas_info = QLabel(
            "Zadejte zařízení, jeho zobrazený čas a referenční čas. "
            "Rozdíl se dopočítá automaticky jako čas zařízení vůči referenci. "
            "Jako základ srovnání lze použít mobil nebo libovolné zadané zařízení."
        )
        cas_info.setWordWrap(True)
        cas_layout.addWidget(cas_info)
        cas_form = QFormLayout()
        cas_form.addRow("Fotodokumentace časů zařízení:", self.caszarizeni_fotodokumentace)
        cas_form.addRow("Srovnávat podle:", self.caszarizeni_reference_source)
        cas_form.addRow("Srovnání časové osy – referenční čas:", self.caszarizeni_srovnani_cas)
        cas_layout.addLayout(cas_form)
        cas_layout.addWidget(QLabel(
            "<b>Zařízení | Čas zařízení na fotce | Referenční čas na fotce | Rozdíl | Čas zařízení ve srovnávaném čase | Fotografie času zařízení</b>"
        ))
        rows = []
        for i in range(1, 11):
            row_layout = QHBoxLayout()
            zarizeni = getattr(self, f"caszarizeni_{i}_zarizeni")
            cas_zarizeni = getattr(self, f"caszarizeni_{i}_cas_zarizeni")
            cas_mobil = getattr(self, f"caszarizeni_{i}_cas_mobil")
            rozdil = getattr(self, f"caszarizeni_{i}_rozdil")
            srovnany = getattr(self, f"caszarizeni_{i}_srovnany_cas")
            foto = getattr(self, f"caszarizeni_{i}_foto")
            zarizeni.setPlaceholderText("např. kamera / lokomotiva")
            cas_zarizeni.setPlaceholderText("čas zařízení")
            cas_mobil.setPlaceholderText("referenční čas")
            rozdil.setPlaceholderText("rozdíl")
            srovnany.setPlaceholderText("přepočet")
            foto.setPlaceholderText("příloha")
            btn = QPushButton("Přiložit fotografii")
            btn.clicked.connect(lambda checked=False, row=i: self.add_caszarizeni_photo(row))
            for widget in [zarizeni, cas_zarizeni, cas_mobil, rozdil, srovnany, foto, btn]:
                row_layout.addWidget(widget)
            cas_layout.addLayout(row_layout)
            rows.append([zarizeni, cas_zarizeni, cas_mobil, rozdil, srovnany, foto, btn])
        btn_add = QPushButton("Přidat zařízení")
        btn_add.clicked.connect(self.add_caszarizeni_row)
        cas_layout.addWidget(btn_add)
        self._register_caszarizeni_rows(rows)
        self._connect_caszarizeni_calculation()
        layout.addWidget(cas_group)

        dokumenty_group = QGroupBox("4. Dokumenty a další důkazy")
        dokumenty_form = QFormLayout(dokumenty_group)
        self.dukazy_provozni_dokumentace_text.setMinimumHeight(160)
        self.dukazy_provozni_zaznamy_text.setMinimumHeight(160)
        dokumenty_form.addRow("Kamerový záznam mohl zachytit úrazový děj:", self.dukazy_kamerovy_zaznam_ano_ne)
        dokumenty_form.addRow("Datum nástupu na směnu:", self.dukazy_dochazka_datum)
        dokumenty_form.addRow("Čas nástupu na směnu:", self.dukazy_dochazka_cas)
        dokumenty_form.addRow("Byl vydán pracovní postup / příkaz k práci:", self.dukazy_pracovni_postup_ano_ne)
        dokumenty_form.addRow("Provozní dokumentace, údržba, kniha závad/oprav:", self.dukazy_provozni_dokumentace_text)
        dokumenty_form.addRow("Další provozní záznamy:", self.dukazy_provozni_zaznamy_text)
        layout.addWidget(dokumenty_group)

        poznamky_group = QGroupBox("5. Poznámky, nákresy apod.")
        poznamky_layout = QVBoxLayout(poznamky_group)
        self.dukazy_poznamka.setMinimumHeight(180)
        poznamky_layout.addWidget(self.dukazy_poznamka)
        layout.addWidget(poznamky_group)

        prilohy_group = QGroupBox("6. Přílohy zajištění důkazů")
        prilohy_layout = QVBoxLayout(prilohy_group)
        prilohy_info = QLabel(
            "Zde přiložte podepsaný ručně vyplněný formulář, sken zajištění důkazů, "
            "fotodokumentaci nebo další důkazní soubory. Přílohy se ukládají do uživatelského "
            "adresáře aplikace v .local a jsou připravené pro pozdější migraci spolu s databází."
        )
        prilohy_info.setWordWrap(True)
        prilohy_layout.addWidget(prilohy_info)
        from core.widgets.attachment_widget import AttachmentWidget
        self.dukazy_attachment_widget = AttachmentWidget(
            entity_type="accident",
            entity_id=self.accident.id if self.accident is not None else None,
        )
        prilohy_layout.addWidget(self.dukazy_attachment_widget)
        layout.addWidget(prilohy_group)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def _tab_misto(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        zaklad = QGroupBox("Protokol o ohledání místa úrazu")
        form = QFormLayout(zaklad)
        form.addRow("Číslo úrazu:", QLabel(self.accident.number if self.accident else ""))
        form.addRow("Záznam provedl:", self.ohledani_zapsal)
        form.addRow("Provoz:", self.ohledani_provoz)
        self.ohledani_provedli.setMinimumHeight(170)
        form.addRow("Ohledání místa provedli:", self.ohledani_provedli)
        form.addRow("Čas ohledání - zahájení:", self.ohledani_zahajeni)
        form.addRow("Čas ohledání - ukončení:", self.ohledani_ukonceni)
        layout.addWidget(zaklad)

        vysl = QGroupBox("Výsledek ohledání")
        vf = QFormLayout(vysl)
        self.ohledani_popis_mista.setMinimumHeight(220)
        vf.addRow("Podrobný popis místa:", self.ohledani_popis_mista)
        btn = QPushButton("Přiložit podepsaný protokol o ohledání místa")
        btn.clicked.connect(self.add_ohledani_attachment)
        row = QHBoxLayout()
        row.addWidget(btn)
        row.addWidget(self.ohledani_priloha)
        vf.addRow("", row)
        layout.addWidget(vysl)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def add_ohledani_attachment(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyberte podepsaný protokol o ohledání místa",
            "",
            "Dokumenty a obrázky (*.pdf *.jpg *.jpeg *.png *.odt *.docx);;Všechny soubory (*)",
        )
        if not file_path:
            return

        source = Path(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"Ohledani-{self._accident_number_slug()}_{timestamp}{source.suffix.lower()}"
        attachment = None
        if self.accident is not None:
            attachment = attachment_service.add_file_as("accident", self.accident.id, str(source), new_name)
        final_name = attachment.filename if attachment is not None else new_name
        self.ohledani_priloha.setText(final_name)

    def _tab_svedci(self):
        return self._simple_tab("Vyjádření svědků, rozdělení svědků, vlastní písemná vyjádření...")

    def _tab_dukazy(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        layout.addWidget(QLabel("<b>1. Zaměstnavatel</b>"))

        pracovni_doba = QGroupBox("Pracovní doba")
        f = QFormLayout(pracovni_doba)
        f.addRow("Dodržování pracovní doby:", self.dodrz_pracovni_doba)
        f.addRow("Přesčasy:", self.dodrz_prescasy)
        f.addRow("Detail přesčasové práce:", self.dodrz_prescasy_detail)
        self._connect_prescasy_detail_visibility()
        layout.addWidget(pracovni_doba)

        predpisy = QGroupBox("Platné předpisy")
        pf = QFormLayout(predpisy)
        self.dodrz_predpisy_cinnost.setMinimumHeight(190)
        pf.addRow(self.dodrz_predpisy_cinnost)
        layout.addWidget(predpisy)

        oopp = QGroupBox("Přidělené OOPP")
        of = QVBoxLayout(oopp)
        self.dodrz_oopp_layout = of
        of.addWidget(QLabel("<b>Typ OOPP | Datum vydání | Minimální životnost / platnost | Poznámka</b>"))
        for row in self.dodrz_oopp_rows:
            of.addLayout(self._row_widgets_layout([row["typ"], row["datum"], row["platnost"], row["poznamka"]]))
        btn_oopp = QPushButton("Přidat OOPP")
        btn_oopp.clicked.connect(self.add_dodrz_oopp_row)
        of.addWidget(btn_oopp)
        layout.addWidget(oopp)

        skoleni = QGroupBox("Školení")
        sf = QVBoxLayout(skoleni)
        self.dodrz_skoleni_layout = sf
        sf.addWidget(QLabel("<b>Typ školení | Datum | Činnost v osnově | Poznámka</b>"))
        for row in self.dodrz_skoleni_rows:
            sf.addLayout(self._row_widgets_layout([row["typ"], row["datum"], row["osnova"], row["poznamka"]]))
        btn_skoleni = QPushButton("Přidat školení")
        btn_skoleni.clicked.connect(self.add_dodrz_skoleni_row)
        sf.addWidget(btn_skoleni)
        layout.addWidget(skoleni)

        lekar = QGroupBox("Lékařská prohlídka")
        lf = QFormLayout(lekar)
        lf.addRow("Typ prohlídky:", self.dodrz_lekar_typ)
        lf.addRow("Datum prohlídky:", self.dodrz_lekar_datum)
        lf.addRow("Platnost do:", self.dodrz_lekar_platnost)
        layout.addWidget(lekar)

        kval = QGroupBox("Kvalifikace k pracovní činnosti")
        kf = QFormLayout(kval)
        kf.addRow("Splňuje kvalifikaci:", self.dodrz_kvalifikace_splnuje)
        self._add_textedit_row(kf, "Poznámka:", self.dodrz_kvalifikace_poznamka, 190)
        layout.addWidget(kval)

        kontroly = QGroupBox("Revize a zjevné závady")
        krf = QFormLayout(kontroly)
        self._add_textedit_row(krf, "", self.dodrz_kontroly_reviz_zavady, 190)
        layout.addWidget(kontroly)

        zkousky = QGroupBox("Zkoušky a odborná způsobilost")
        zf = QVBoxLayout(zkousky)
        self.dodrz_zkousky_layout = zf
        zf.addWidget(QLabel("<b>Typ zkoušky | Datum | Platnost do | Poznámka</b>"))
        for row in self.dodrz_zkousky_rows:
            zf.addLayout(self._row_widgets_layout([row["typ"], row["datum"], row["platnost"], row["poznamka"]]))
        btn_zkouska = QPushButton("Přidat zkoušku")
        btn_zkouska.clicked.connect(self.add_dodrz_zkouska_row)
        zf.addWidget(btn_zkouska)
        layout.addWidget(zkousky)

        ostatni1 = QGroupBox("Další záznamy")
        o1f = QFormLayout(ostatni1)
        self._add_textedit_row(o1f, "", self.dodrz_ostatni_1, 190)
        layout.addWidget(ostatni1)

        layout.addWidget(QLabel("<b>2. Zaměstnanec</b>"))

        pouzivani = QGroupBox("Používání OOPP")
        puf = QFormLayout(pouzivani)
        puf.addRow("OOPP byly použity:", self.dodrz_oopp_pouzity)
        self._add_textedit_row(puf, "Stav OOPP:", self.dodrz_stav_oopp, 180)
        layout.addWidget(pouzivani)

        vyj = QGroupBox("Vyjádření zaměstnance")
        vyf = QFormLayout(vyj)
        self._add_textedit_row(vyf, "", self.dodrz_vyjadreni_oopp, 180)
        layout.addWidget(vyj)

        koopp = QGroupBox("Kontrola OOPP")
        kof = QVBoxLayout(koopp)
        kof.addWidget(QLabel("<b>Datum | Kontroloval | Výsledek</b>"))
        for row in self.dodrz_kontrola_oopp_rows:
            kof.addLayout(self._row_widgets_layout([row["datum"], row["kontroloval"], row["vysledek"]]))
        layout.addWidget(koopp)

        kpred = QGroupBox("Kontrola dodržování předpisů")
        kpf = QVBoxLayout(kpred)
        kpf.addWidget(QLabel("<b>Datum | Kontroloval | Výsledek</b>"))
        for row in self.dodrz_kontrola_predpisu_rows:
            kpf.addLayout(self._row_widgets_layout([row["datum"], row["kontroloval"], row["vysledek"]]))
        layout.addWidget(kpred)

        poruseni = QGroupBox("Porušení předpisů")
        prf = QFormLayout(poruseni)
        self._add_textedit_row(prf, "", self.dodrz_poruseni_predpisu, 190)
        layout.addWidget(poruseni)

        ostatni2 = QGroupBox("Další záznamy k OOPP")
        o2f = QFormLayout(ostatni2)
        self._add_textedit_row(o2f, "", self.dodrz_ostatni_2, 190)
        layout.addWidget(ostatni2)

        prilohy = QGroupBox("Přílohy k dodržování předpisů")
        pl = QVBoxLayout(prilohy)
        pl.addWidget(QLabel("Zde přiložte sken nebo dokument vztahující se k této části šetření."))
        row = QHBoxLayout()
        btn = QPushButton("Přiložit sken / dokument k dodržování předpisů")
        btn.clicked.connect(self.add_dodrzovani_attachment)
        row.addWidget(btn)
        row.addWidget(self.dodrz_priloha)
        pl.addLayout(row)
        layout.addWidget(prilohy)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def add_dodrzovani_attachment(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyberte přílohu k dodržování předpisů",
            "",
            "Dokumenty a obrázky (*.pdf *.jpg *.jpeg *.png *.odt *.docx);;Všechny soubory (*)",
        )
        if not file_path:
            return
        source = Path(file_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_name = f"DodrzovaniPredpisu-{self._accident_number_slug()}_{timestamp}{source.suffix.lower()}"
        attachment = None
        if self.accident is not None:
            attachment = attachment_service.add_file_as("accident", self.accident.id, str(source), new_name)
        final_name = attachment.filename if attachment is not None else new_name
        self.dodrz_priloha.setText(final_name)

    def _tab_analyza_pricin(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        layout.addWidget(QLabel("<b>Analýza příčin</b>"))
        postup = QLabel("Postup: podklady → Ishikawa BOZP → 5× Proč → výstup analýzy. Checklisty slouží k označení zjištěných faktorů. Typ příčiny se určuje až ve výstupu analýzy.")
        postup.setWordWrap(True)
        layout.addWidget(postup)

        podklady = QGroupBox("1. Shrnutí podkladů před analýzou")
        podklady_layout = QVBoxLayout(podklady)
        btn_aktualizovat_podklady = QPushButton("Aktualizovat z podkladů")
        btn_aktualizovat_podklady.clicked.connect(self.aktualizovat_analyza_z_podkladu)
        podklady_layout.addWidget(btn_aktualizovat_podklady)
        podklady_form = QFormLayout()
        self._add_textedit_row(podklady_form, "Shrnutí skutkového stavu:", self.analyza_shrnuti_skutecneho_stavu, 170)
        self._add_textedit_row(podklady_form, "Zjištěné skutečnosti:", self.analyza_zjistene_skutecnosti, 170)
        self._add_textedit_row(podklady_form, "Prvotně určená příčina:", self.analyza_prvotni_pricina, 170)
        podklady_layout.addLayout(podklady_form)
        layout.addWidget(podklady)

        ishikawa = QGroupBox("2. Ishikawa BOZP – checklist zjištěných faktorů")
        ishikawa_layout = QVBoxLayout(ishikawa)
        self._add_analyza_section(
            ishikawa_layout,
            "Člověk",
            "clovek",
            question="<b>Otázka při šetření:</b> Udělal někdo něco jinak, než měl?<br>Faktory související přímo s poškozeným nebo jinou osobou",
        )
        self._add_analyza_section(
            ishikawa_layout,
            "Zařízení a technika",
            "zarizeni_technika",
            subtitle="Selhalo zařízení nebo technický systém?",
        )
        self._add_analyza_section(ishikawa_layout, "Materiál", "material", subtitle="Materiál")
        self._add_analyza_section(ishikawa_layout, "Pracovní prostředí", "pracovni_prostredi", subtitle="Pracovní prostředí")
        self._add_analyza_section(ishikawa_layout, "Organizace práce a řízení", "organizace_prace_rizeni", subtitle="Organizace práce a řízení")
        self._add_analyza_section(ishikawa_layout, "Školení a dokumentace", "skoleni_dokumentace", subtitle="Školení a dokumentace")
        self._add_analyza_section(ishikawa_layout, "OOPP a bezpečnostní opatření", "oopp_bezpecnostni_opatreni", subtitle="OOPP a bezpečnostní opatření")
        layout.addWidget(ishikawa)

        proc = QGroupBox("3. 5× Proč – hledání kořenové příčiny")
        proc_form = QFormLayout(proc)
        self._add_textedit_row(proc_form, "Proč č. 1 – bezprostřední událost:", self.analyza_proc_1, 180)
        self._add_textedit_row(proc_form, "Proč č. 2 – vznik situace:", self.analyza_proc_2, 180)
        self._add_textedit_row(proc_form, "Proč č. 3 – selhání zachycení / prevence:", self.analyza_proc_3, 180)
        self._add_textedit_row(proc_form, "Proč č. 4 – systémové umožnění:", self.analyza_proc_4, 180)
        self._add_textedit_row(proc_form, "Proč č. 5 – kořenová příčina:", self.analyza_proc_5, 180)
        layout.addWidget(proc)

        vystup = QGroupBox("4. Výstup analýzy")
        vystup_layout = QVBoxLayout(vystup)
        klasifikace = QGroupBox("Klasifikace zjištěných faktorů")
        klas_layout = QVBoxLayout(klasifikace)
        info = QLabel("Načtěte označené faktory z Ishikawy a u každého ručně určete, zda jde o bezprostřední, přispívající nebo kořenovou příčinu.")
        info.setWordWrap(True)
        klas_layout.addWidget(info)
        btn_nacist_faktory = QPushButton("Načíst označené faktory z analýzy")
        btn_nacist_faktory.clicked.connect(self.load_analyza_marked_factors)
        klas_layout.addWidget(btn_nacist_faktory)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.addWidget(QLabel("<b>Faktor</b>"), 5)
        header_layout.addWidget(QLabel("<b>Kategorie</b>"), 2)
        header_layout.addWidget(QLabel("<b>Typ příčiny</b>"), 1)
        klas_layout.addLayout(header_layout)

        self.analyza_klasifikace_rows_layout = QVBoxLayout()
        klas_layout.addLayout(self.analyza_klasifikace_rows_layout)
        self._load_saved_analyza_klasifikace_rows()

        btn_generovat_vystup = QPushButton("Vygenerovat výstup podle klasifikace")
        btn_generovat_vystup.clicked.connect(self.generate_analyza_output)
        klas_layout.addWidget(btn_generovat_vystup)
        vystup_layout.addWidget(klasifikace)

        vystup_form = QFormLayout()
        self._add_textedit_row(vystup_form, "Bezprostřední příčina:", self.analyza_bezprostredni_pricina, 180)
        self._add_textedit_row(vystup_form, "Kořenová příčina:", self.analyza_korenova_pricina, 180)
        self._add_textedit_row(vystup_form, "Přispívající příčiny:", self.analyza_prispivajici_priciny, 180)
        vystup_layout.addLayout(vystup_form)

        overeni = QGroupBox("Ověření kořenové příčiny")
        overeni_layout = QVBoxLayout(overeni)
        for checkbox in self.analyza_overeni_korenove_priciny.values():
            overeni_layout.addWidget(checkbox)
        vystup_layout.addWidget(overeni)

        poznamka_form = QFormLayout()
        self._add_textedit_row(poznamka_form, "Poznámka specialisty BOZP:", self.analyza_poznamka_bozp, 190)
        vystup_layout.addLayout(poznamka_form)
        layout.addWidget(vystup)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def _tab_analyza(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        layout.addWidget(QLabel("<b>Kontrola souladu důkazů a posouzení pracovního úrazu</b>"))
        layout.addWidget(QLabel("Kontrola souladu důkazů"))

        podklady = QGroupBox("Porovnané podklady")
        pf = QVBoxLayout(podklady)
        for key in [
            "vypoved_postizeneho",
            "vypovedi_svedku",
            "fotodokumentace",
            "stav_mista",
            "kamerove_zaznamy",
            "casove_udaje",
            "lekarska_zprava",
            "pracovni_postup",
            "oopp",
            "skoleni",
            "evidence_prace",
        ]:
            pf.addWidget(self.soulad_podklady[key])
        layout.addWidget(podklady)

        nesrovnalosti = QGroupBox("Zjištěné nesrovnalosti")
        nf = QVBoxLayout(nesrovnalosti)
        for key in ["cas", "misto", "mechanismus", "vypovedi", "zraneni_popis", "jine"]:
            nf.addWidget(self.soulad_nesrovnalosti[key])
        layout.addWidget(nesrovnalosti)

        popis = QGroupBox("Popis zjištěných nesrovnalostí")
        popis_f = QFormLayout(popis)
        self._add_textedit_row(popis_f, "", self.soulad_popis_nesrovnalosti, 180)
        layout.addWidget(popis)

        vyhodnoceni = QGroupBox("Vyhodnocení souladu důkazů")
        vyhodnoceni_f = QFormLayout(vyhodnoceni)
        self._add_textedit_row(vyhodnoceni_f, "", self.soulad_vyhodnoceni, 180)
        layout.addWidget(vyhodnoceni)

        posouzeni = QGroupBox("Posouzení pracovního úrazu")
        form = QFormLayout(posouzeni)
        form.addRow("Vzniklo poškození zdraví:", self.soulad_vzniklo_poskozeni)
        form.addRow("Došlo k němu při plnění pracovních úkolů nebo v přímé souvislosti:", self.soulad_pri_plneni)
        form.addRow("Šlo o náhlé, krátkodobé a zevní působení:", self.soulad_nahle_pusobeni)
        form.addRow("Jedná se o úraz mimo práci nebo cestu do/z práce:", self.soulad_mimo_praci)
        form.addRow("Stanovisko specialisty BOZP:", self.soulad_stanovisko_bozp)
        self._add_textedit_row(form, "Odůvodnění stanoviska:", self.soulad_oduvodneni, 180)
        layout.addWidget(posouzeni)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w

    def _tab_opatreni(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)

        info = QLabel(
            "Evidence nápravných opatření k zamezení opakování pracovního úrazu. "
            "Opatření jsou ukládána do společného Úkolníčku, aby nevznikaly duplicity."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.opatreni_table = QTableWidget()
        self.opatreni_table.setColumnCount(8)
        self.opatreni_table.setHorizontalHeaderLabels([
            "St.", "Pr.", "Opatření", "Odpovídá", "Termín", "Splněno", "Kontrola do", "Kontrola"
        ])
        self.opatreni_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.opatreni_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.opatreni_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.opatreni_table.setWordWrap(False)
        self.opatreni_table.verticalHeader().setVisible(False)
        self.opatreni_table.verticalHeader().setDefaultSectionSize(24)
        self.opatreni_table.verticalHeader().setMinimumSectionSize(24)
        self.opatreni_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.opatreni_table.setAlternatingRowColors(True)
        self.opatreni_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for col, width in {
            0: 34,
            1: 34,
            3: 180,
            4: 105,
            5: 105,
            6: 105,
            7: 105,
        }.items():
            self.opatreni_table.setColumnWidth(col, width)

        self.opatreni_table.doubleClicked.connect(self.edit_opatreni_task)
        layout.addWidget(self.opatreni_table)

        btn_row = QHBoxLayout()
        btn_add = QPushButton("Přidat opatření")
        btn_edit = QPushButton("Upravit")
        btn_delete = QPushButton("Odebrat")
        btn_add.clicked.connect(self.add_opatreni_task)
        btn_edit.clicked.connect(self.edit_opatreni_task)
        btn_delete.clicked.connect(self.delete_opatreni_task)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_edit)
        btn_row.addWidget(btn_delete)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.refresh_opatreni_tasks()
        return tab

    def _opatreni_source_module(self):
        return "kniha_urazu_opatreni"

    def _opatreni_source_record_id(self):
        return self.accident.id if self.accident is not None else None

    def _opatreni_tasks(self):
        accident_id = self._opatreni_source_record_id()
        if accident_id is None:
            return []
        return [
            task for task in task_service.get_all_tasks()
            if task.source_module == self._opatreni_source_module()
            and task.source_record_id == accident_id
            and not task.canceled
        ]

    def _selected_opatreni_task(self):
        if not hasattr(self, "opatreni_table"):
            return None
        row = self.opatreni_table.currentRow()
        if row < 0:
            return None
        item = self.opatreni_table.item(row, 0)
        if item is None:
            return None
        task_id = item.data(Qt.UserRole)
        return task_service.get_task_by_id(task_id) if task_id else None

    def _date_text(self, value):
        return value.strftime("%d.%m.%Y") if value else ""

    def _status_color(self, task):
        if task.computed_status == "Ukončeno":
            return QColor("#1f8f3a")
        if task.computed_status == "Splněno - čeká na kontrolu":
            return QColor("#f0a000")
        if task.due_date and task.due_date < datetime.now().date():
            return QColor("#c9302c")
        return QColor("#f0a000")

    def _priority_color(self, task):
        if task.priority in ["Vysoká", "Kritická"]:
            return QColor("#f0a000")
        return QColor("#1f8f3a")

    def refresh_opatreni_tasks(self):
        if not hasattr(self, "opatreni_table"):
            return

        tasks = self._opatreni_tasks()
        tasks.sort(key=lambda task: (task.completed, task.due_date or datetime.max.date(), task.id))

        self.opatreni_table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            values = [
                "",
                "",
                task.title or "",
                task.responsible_person or "",
                self._date_text(task.due_date),
                self._date_text(task.completed_date),
                self._date_text(task.check_due_date),
                self._date_text(task.checked_date),
            ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                if col == 0:
                    item.setData(Qt.UserRole, task.id)
                    item.setBackground(self._status_color(task))
                elif col == 1:
                    item.setBackground(self._priority_color(task))
                self.opatreni_table.setItem(row, col, item)

        self.opatreni_table.verticalHeader().setDefaultSectionSize(24)
        self.opatreni_table.verticalHeader().setMinimumSectionSize(24)
        for row in range(self.opatreni_table.rowCount()):
            self.opatreni_table.setRowHeight(row, 24)

    def add_opatreni_task(self):
        dialog = TaskDialog(
            self,
            create_kwargs={
                "source_module": self._opatreni_source_module(),
                "source_record_id": self._opatreni_source_record_id(),
            },
        )
        if self.accident is not None:
            if getattr(self.accident, "workplace_id", None):
                dialog.workplace_selector.set_workplace_id(self.accident.workplace_id)
            elif getattr(self.accident, "workplace_name", ""):
                dialog.workplace_selector.setCurrentText(self.accident.workplace_name)
            dialog._capture_baseline()

        dialog.exec()
        self.refresh_opatreni_tasks()

    def edit_opatreni_task(self):
        task = self._selected_opatreni_task()
        if task is None:
            return

        dialog = TaskDialog(self, task=task)
        dialog.exec()
        self.refresh_opatreni_tasks()
    def delete_opatreni_task(self):
        task = self._selected_opatreni_task()
        if task is None:
            return

        reply = QMessageBox.question(
            self,
            "Odebrat opatření",
            "Opravdu odebrat vybrané opatření?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            task_service.cancel_task(task.id)
            self.refresh_opatreni_tasks()



    def _accident_kind_text(self):
        return (getattr(self.accident, "druh_urazu", "") or "").lower()

    def _is_serious_or_fatal_accident(self):
        return is_serious_or_fatal_accident(self.accident)

    def _is_fatal_accident(self):
        return is_fatal_accident(self.accident)

    def _has_pn_over_3_days(self):
        return has_pn_over_3_days(self.accident)

    def _requires_accident_record(self):
        return requires_accident_record(self.accident)

    def _requires_police_obligation(self):
        return requires_police_obligation(self.accident)

    def _add_workdays(self, start_date, days):
        if not start_date:
            return None
        result = start_date
        added = 0
        while added < days:
            result = result + timedelta(days=1)
            if result.weekday() < 5:
                added += 1
        return result

    def _first_day_next_month(self, date_value):
        if not date_value:
            return None
        year = date_value.year + (1 if date_value.month == 12 else 0)
        month = 1 if date_value.month == 12 else date_value.month + 1
        return date_value.replace(year=year, month=month, day=1)

    def _admin_notification_date(self):
        if hasattr(self, "oznameni_datum"):
            value = self._date_value(self.oznameni_datum)
            if value:
                return value
        return obligation_notification_date(self.accident, self._zajisteni_saved_data)

    def _admin_default_deadline(self, row):
        if not isinstance(row, dict):
            row = {"nazev": str(row)}
        return obligation_default_deadline(
            self._admin_notification_date(),
            obligation_key=row.get("key", ""),
            section=row.get("section", ""),
            label=row.get("nazev", ""),
            agenda=row.get("agenda", ""),
        )

    def _admin_row_relevant(self, row):
        return is_row_visible(
            self.accident,
            row,
            saved_data=self._zajisteni_saved_data,
        )

    def _refresh_admin_setreni_funkce(self):
        if not hasattr(self, "admin_setreni_jmeno") or not hasattr(self, "admin_setreni_funkce"):
            return

        worker = self.admin_setreni_jmeno.current_person() if hasattr(self.admin_setreni_jmeno, "current_person") else None

        # Pojistka: při setCurrentText nemusí být vždy nastaveno itemData,
        # proto hledáme THP i podle zobrazeného jména.
        if worker is None:
            selected_name = self.admin_setreni_jmeno.currentText().strip()
            try:
                for item in settings_service.get_workers(include_inactive=False):
                    if getattr(item, "display_name", "").strip() == selected_name:
                        worker = item
                        break
            except Exception:
                worker = None

        position = getattr(worker, "position", "") if worker is not None else ""
        if position:
            self.admin_setreni_funkce.setText(position)

    def _admin_rows_data(self, rows):
        hidden_keys = record_duty_keys_hidden_for_generation(
            resolve_record_duty_generation(self._zajisteni_saved_data)
        )
        data = []
        for row in rows:
            key = row.get("key", "")
            if key in hidden_keys:
                continue
            zpusob = self._radio_choice_value(row["zpusob"])
            if key == OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU:
                zpusob = zpusob or METHOD_PORTAL_SUIP
            elif key == OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL:
                zpusob = zpusob or METHOD_PORTAL_SUIP
            elif key == OBLIGATION_OIP_OBU_OHLASENI and oip_notice_uses_fixed_portal_suip(
                self.accident
            ):
                zpusob = zpusob or METHOD_PORTAL_SUIP
            data.append({
                "key": key,
                "nazev": row.get("nazev", ""),
                "agenda": row.get("agenda", ""),
                "section": row.get("section", ""),
                "predano": row["predano"].isChecked(),
                "kompletni": row.get("kompletni").isChecked() if row.get("kompletni") is not None else False,
                "lhuta": self._date_to_json(row["lhuta"]) if row.get("lhuta") is not None else "",
                "datum": self._date_to_json(row["datum"]),
                "cas": row["cas"].text().strip(),
                "zpusob": zpusob,
                "upresneni": row["upresneni"].text().strip(),
            })
        return data

    def _connect_admin_auto_dates(self):
        # Datum ohlášení bereme automaticky ze záložky Oznámení – Datum oznámení.
        # Z něj se následně dopočítávají zákonné lhůty.
        if hasattr(self, "oznameni_datum"):
            try:
                self.oznameni_datum.dateChanged.connect(self._refresh_admin_dates_from_oznameni)
            except Exception:
                pass
        self._refresh_admin_dates_from_oznameni()

    def _refresh_admin_dates_from_oznameni(self):
        oznameni_date = self._admin_notification_date()
        if not oznameni_date:
            return

        # Ohlášení: pouze dopočítat lhůty. Datum/čas/způsob ohlášení
        # vyplňuje uživatel až po skutečném provedení (ne označovat jako odesláno).
        for row in getattr(self, "admin_ohlaseni_rows", []):
            if row.get("lhuta") is not None:
                deadline = self._admin_default_deadline(row)
                if deadline:
                    self._set_date_widget(row["lhuta"], deadline)

        for row in getattr(self, "admin_zaznam_rows", []):
            if row.get("lhuta") is not None:
                deadline = self._admin_default_deadline(row)
                if deadline:
                    self._set_date_widget(row["lhuta"], deadline)

        for row in getattr(self, "admin_odeslani_rows", []):
            if row.get("lhuta") is not None:
                deadline = self._admin_default_deadline(row)
                if deadline:
                    self._set_date_widget(row["lhuta"], deadline)

        for row in getattr(self, "admin_predani_rows", []):
            if row.get("lhuta") is not None:
                deadline = self._admin_default_deadline(row)
                if deadline:
                    self._set_date_widget(row["lhuta"], deadline)

    def _init_ohlasovaci_povinnosti_widgets(self):
        from core.widgets.thp_worker_selector import ThpWorkerSelector
        saved = self._zajisteni_saved_data

        self.admin_setreni_jmeno = ThpWorkerSelector()
        self.admin_setreni_jmeno.setEditable(True)
        if saved.get("admin_setreni_jmeno"):
            self.admin_setreni_jmeno.setCurrentText(saved.get("admin_setreni_jmeno", ""))
        self.admin_setreni_funkce = QLineEdit(saved.get("admin_setreni_funkce", ""))
        self.admin_setreni_jmeno.currentTextChanged.connect(lambda _text: self._refresh_admin_setreni_funkce())
        self.admin_setreni_jmeno.currentIndexChanged.connect(lambda _index: self._refresh_admin_setreni_funkce())
        if not saved.get("admin_setreni_funkce"):
            self._refresh_admin_setreni_funkce()
        self.admin_zahajeni = self._new_date_edit()
        self.admin_zahajeni_warning = QLabel()
        self.admin_zahajeni_warning.setObjectName("WarningText")
        self.admin_zahajeni_warning.setWordWrap(True)
        self.admin_zahajeni_warning.setStyleSheet("color: #b45309;")
        self.admin_zahajeni_warning.setVisible(False)
        if saved.get("admin_zahajeni"):
            self._set_date_widget(self.admin_zahajeni, saved.get("admin_zahajeni"))
        elif self.accident is not None and getattr(self.accident, "accident_date", None):
            self._set_date_widget(self.admin_zahajeni, self.accident.accident_date)
        self.admin_zahajeni.dateChanged.connect(self._refresh_admin_zahajeni_warning)
        self.admin_duvod_pozde = QLineEdit(saved.get("admin_duvod_pozde", ""))
        self.admin_duvod_pozde.setPlaceholderText("Stručný důvod pozdějšího zahájení šetření.")
        self.admin_ukonceni = self._new_date_edit()
        if saved.get("admin_ukonceni"):
            self._set_date_widget(self.admin_ukonceni, saved.get("admin_ukonceni"))
        self.admin_pripad_uzavren = self._radio_choice(["ANO", "NE"])
        self._set_radio_choice(
            self.admin_pripad_uzavren,
            saved.get("admin_pripad_uzavren", CASE_CLOSED_NO),
        )
        self._connect_case_closure_guard()

        def saved_row(rows, *, key="", name=""):
            for item in rows or []:
                if key and item.get("key") == key:
                    return item
                if key and obligation_key_from_row(item) == key:
                    return item
                if name and item.get("nazev") == name:
                    return item
            return {}

        saved_ohlaseni = saved.get("admin_ohlaseni") or []
        saved_zaslani = saved.get("admin_zaslani") or []

        self.admin_ohlaseni_rows = []
        self.admin_zaznam_rows = []
        self.admin_odeslani_rows = []
        self.admin_predani_rows = []
        self.admin_dpn_rows = []
        self.admin_zakonna_rows = []
        self.admin_nemocenske_rows = []

        for definition in obligation_definitions_for_accident(
            self.accident,
            saved,
        ):
            saved_data = saved_row(
                saved_ohlaseni + saved_zaslani,
                key=definition.key,
                name=definition.label,
            )
            display_name = definition.label
            if definition.key not in {
                OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU,
                OBLIGATION_CSSZ_USSZ_NEMOCENSKE,
            } | POST_DPN_OBLIGATION_KEYS | ZAKONNA_POJISTOVNA_KEYS:
                display_name = (saved_data.get("nazev") or "").strip() or definition.label
            if definition.section == SECTION_OHLASENI:
                agenda = "ohlaseni"
            elif definition.section == SECTION_NEMOCENSKE:
                agenda = "nemocenske"
            else:
                agenda = "zaznam"
            row = self._make_admin_row(
                display_name,
                saved_data,
                agenda=agenda,
                section=definition.section,
                key=definition.key,
            )
            if definition.section == SECTION_OHLASENI:
                self.admin_ohlaseni_rows.append(row)
            elif definition.section == SECTION_ZAZNAM:
                self.admin_zaznam_rows.append(row)
            elif definition.section == SECTION_ODESLANI:
                self.admin_odeslani_rows.append(row)
            elif definition.section == SECTION_NEMOCENSKE:
                self.admin_nemocenske_rows.append(row)
            elif definition.section == SECTION_AKTUALIZACE_PO_DPN:
                self.admin_dpn_rows.append(row)
            elif definition.section == SECTION_ZAKONNA_POJISTOVNA:
                self.admin_zakonna_rows.append(row)
            else:
                self.admin_predani_rows.append(row)

        self._connect_admin_auto_dates()

    def _make_admin_row(self, nazev, data=None, agenda="", section="", key=""):
        data = data or {}

        portal_only_oip_notice = (
            key == OBLIGATION_OIP_OBU_OHLASENI
            and oip_notice_uses_fixed_portal_suip(self.accident)
        )
        post_dpn_portal = key == OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL

        if key == OBLIGATION_CSSZ_USSZ_NEMOCENSKE:
            zpusoby = ["Datová schránka", "E-mail", "Listinná podoba", "Jiný způsob"]
        elif key == OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU or post_dpn_portal:
            zpusoby = [METHOD_PORTAL_SUIP]
        elif portal_only_oip_notice:
            zpusoby = [METHOD_PORTAL_SUIP]
        elif (
            "Portál SÚIP" in nazev
            or "Vyhotovení Záznamu" in nazev
            or "OIP / OBÚ" in nazev
        ):
            zpusoby = [METHOD_PORTAL_SUIP, "Datová schránka", "Jiný způsob"]
        elif (
            "Odborová organizace" in nazev
            or "Postižený zaměstnanec" in nazev
            or "Rodinní příslušníci" in nazev
        ):
            zpusoby = ["Osobně", "E-mail", "Datová schránka", "Listinná podoba", "Jiný způsob"]
        else:
            zpusoby = ["Datová schránka", "E-mail", "Listinná podoba", "Jiný způsob"]

        row = {
            "key": key or data.get("key", ""),
            "nazev": nazev,
            "agenda": agenda,
            "section": section or data.get("section", ""),
            "predano": QCheckBox(),
            "kompletni": None,
            "lhuta": self._new_date_edit(),
            "datum": self._new_date_edit(),
            "cas": QLineEdit(data.get("cas", "")),
            "zpusob": self._radio_choice(zpusoby),
            "upresneni": QLineEdit(data.get("upresneni", "")),
        }
        row["predano"].setChecked(bool(data.get("predano", False)))
        row["cas"].setPlaceholderText("např. 14:35")
        if key == OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI:
            row["upresneni"].setPlaceholderText("číslo pojistné události nebo poznámka")
        elif key == OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU:
            row["upresneni"].setPlaceholderText("poznámka k doplnění ZoÚ")
        else:
            row["upresneni"].setPlaceholderText("Upřesnit způsob odeslání / předání")

        if (
            key == OBLIGATION_CSSZ_USSZ_NEMOCENSKE
            or key in POST_DPN_OBLIGATION_KEYS
            or key in ZAKONNA_POJISTOVNA_KEYS
        ):
            row["lhuta"] = None
        elif "Kooperativa" in nazev or "Zákonná pojišťovna" in nazev:
            row["lhuta"] = None

        if row.get("lhuta") is not None:
            if data.get("lhuta"):
                self._set_date_widget(row["lhuta"], data.get("lhuta"))
            else:
                default_lhuta = self._admin_default_deadline(row)
                if default_lhuta:
                    self._set_date_widget(row["lhuta"], default_lhuta)
            # Lhůty jsou dopočítané z data oznámení, uživatel je ručně neupravuje.
            try:
                row["lhuta"].line_edit.setReadOnly(True)
                row["lhuta"].calendar_button.setVisible(False)
                row["lhuta"].clear_button.setVisible(False)
            except Exception:
                pass

        if data.get("datum"):
            self._set_date_widget(row["datum"], data.get("datum"))

        # Způsob nevybírat automaticky – potvrzuje ho uživatel až po provedení.
        saved_method = (data.get("zpusob") or "").strip()
        if key == OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU or post_dpn_portal:
            self._set_radio_choice(row["zpusob"], METHOD_PORTAL_SUIP)
            row["fixed_sending_method"] = METHOD_PORTAL_SUIP
            if post_dpn_portal:
                row["show_method_upresneni"] = True
                row["upresneni"].setPlaceholderText("číslo podání nebo poznámka k aktualizaci")
        elif portal_only_oip_notice:
            self._set_radio_choice(row["zpusob"], METHOD_PORTAL_SUIP)
            row["fixed_sending_method"] = METHOD_PORTAL_SUIP
            row["show_method_upresneni"] = True
            row["upresneni"].setPlaceholderText("číslo podání nebo poznámka k ohlášení")
        else:
            self._set_radio_choice(row["zpusob"], saved_method)

        # Osobní předání u ohlášení OO: ponechat v UI, ale aktuálně nepřípustné.
        if (
            row.get("key") == OBLIGATION_OO_OHLASENI
            or ("Odborová organizace" in nazev and "ohlášení" in nazev)
        ):
            for child in row["zpusob"].findChildren(QRadioButton):
                if child.text() == "Osobně":
                    child.setEnabled(False)

        # Kooperativa: bez lhůty a bez doplňkových checkboxů, pouze datum/čas odeslání.

        return row

    def _admin_date_value(self, widget):
        if widget is None:
            return None
        try:
            return self._date_value(widget)
        except Exception:
            return None

    def _admin_row_state_dict(self, row):
        sent_date = self._admin_date_value(row.get("datum"))
        deadline = self._admin_date_value(row.get("lhuta"))
        return {
            "key": row.get("key", ""),
            "predano": row["predano"].isChecked(),
            "kompletni": row["kompletni"].isChecked() if row.get("kompletni") is not None else False,
            "datum": sent_date.isoformat() if sent_date else "",
            "lhuta": deadline.isoformat() if deadline else "",
        }

    def _admin_status_label(self, row):
        label = QLabel()
        label.setMinimumHeight(26)
        label.setAlignment(Qt.AlignCenter)

        def refresh():
            state_dict = self._admin_row_state_dict(row)
            if row.get("key") == OBLIGATION_CSSZ_USSZ_NEMOCENSKE:
                cssz_state = cssz_row_ui_state(
                    self.accident,
                    state_dict,
                    today=datetime.now().date(),
                )
                if cssz_state == "done":
                    label.setText(CSSZ_STATUS_DONE)
                    label.setStyleSheet(
                        "font-weight: bold; color: #0b5d1e; background: #d9f0dd; "
                        "border: 1px solid #91c79c; border-radius: 3px;"
                    )
                elif cssz_state == "required":
                    label.setText(CSSZ_STATUS_REQUIRED)
                    label.setStyleSheet(
                        "font-weight: bold; color: #7a4b00; background: #fff3cd; "
                        "border: 1px solid #d6b656; border-radius: 3px;"
                    )
                else:
                    label.setText(CSSZ_STATUS_OPTIONAL)
                    label.setStyleSheet(
                        "font-weight: bold; color: #334155; background: #eef2f6; "
                        "border: 1px solid #c5d0dc; border-radius: 3px;"
                    )
                return

            if row.get("key") in ZAKONNA_POJISTOVNA_KEYS:
                done = zakonna_row_ui_state(state_dict) == "done"
                if row.get("key") == OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI:
                    label.setText(
                        ZAKONNA_HLASENI_STATUS_DONE if done else ZAKONNA_HLASENI_STATUS_WAITING
                    )
                else:
                    label.setText(
                        ZAKONNA_AKTUALIZACE_STATUS_DONE
                        if done
                        else ZAKONNA_AKTUALIZACE_STATUS_WAITING
                    )
                if done:
                    label.setStyleSheet(
                        "font-weight: bold; color: #0b5d1e; background: #d9f0dd; "
                        "border: 1px solid #91c79c; border-radius: 3px;"
                    )
                else:
                    label.setStyleSheet(
                        "font-weight: bold; color: #334155; background: #eef2f6; "
                        "border: 1px solid #c5d0dc; border-radius: 3px;"
                    )
                return

            state = row_status(state_dict, datetime.now().date())
            if state == "done":
                label.setText("✔ Odesláno / předáno")
                label.setStyleSheet("font-weight: bold; color: #0b5d1e; background: #d9f0dd; border: 1px solid #91c79c; border-radius: 3px;")
            elif state == "overdue":
                label.setText("Po termínu")
                label.setStyleSheet("font-weight: bold; color: #842029; background: #f8d7da; border: 1px solid #d39a9f; border-radius: 3px;")
            else:
                label.setText("Nevyřízeno")
                label.setStyleSheet("font-weight: bold; color: #7a4b00; background: #fff3cd; border: 1px solid #d6b656; border-radius: 3px;")

        row["predano"].toggled.connect(refresh)
        if row.get("kompletni") is not None:
            row["kompletni"].toggled.connect(refresh)
        for key in ("datum", "lhuta"):
            widget = row.get(key)
            if widget is not None:
                try:
                    widget.dateChanged.connect(refresh)
                except Exception:
                    pass
        refresh()
        return label

    def _focus_obligation_row(self, obligation_key: str | None) -> None:
        key = (obligation_key or "").strip()
        if not key:
            return
        for row in getattr(self, "admin_dpn_rows", []):
            if row.get("key") != key:
                continue
            widget = row.get("datum")
            if widget is not None:
                widget.setFocus()
            group = row.get("_group")
            scroll = getattr(self, "_ohlaseni_scroll", None)
            if group is not None and scroll is not None:
                scroll.ensureWidgetVisible(group)
            return

    def _admin_row_group(self, row, mode="odeslání"):
        group = QGroupBox(row["nazev"])
        form = QFormLayout(group)
        form.addRow("Stav:", self._admin_status_label(row))
        if row.get("kompletni") is not None:
            form.addRow("", row["kompletni"])
        if row.get("lhuta") is not None:
            form.addRow("Lhůta do:", row["lhuta"])
        form.addRow(f"Datum {mode}:", row["datum"])
        form.addRow(f"Čas {mode}:", row["cas"])
        if row.get("fixed_sending_method"):
            form.addRow(f"Způsob {mode}:", QLabel(row["fixed_sending_method"]))
            if row.get("show_method_upresneni"):
                form.addRow("Upřesnění:", row["upresneni"])
        elif "EZOP" not in row["nazev"]:
            form.addRow(f"Způsob {mode}:", row["zpusob"])
            form.addRow("Upřesnění:", row["upresneni"])
        return group

    def _zakonna_row_by_key(self, key):
        for row in getattr(self, "admin_zakonna_rows", []):
            if row.get("key") == key:
                return row
        return None

    def _init_zakonna_together_checkbox(self):
        checkbox = getattr(self, "zakonna_together_checkbox", None)
        if checkbox is None:
            return
        hlaseni = self._zakonna_row_by_key(OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI)
        aktualizace = self._zakonna_row_by_key(OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU)
        if aktualizace is None or not self._admin_row_relevant(aktualizace):
            return
        dpn_ended = is_dpn_ended(
            getattr(self.accident, "dpn_do", None) if self.accident is not None else None
        )
        checkbox.setChecked(
            zakonna_together_checkbox_default(
                dpn_ended=dpn_ended,
                hlaseni_row=self._admin_row_state_dict(hlaseni) if hlaseni else {},
                aktualizace_row=self._admin_row_state_dict(aktualizace) if aktualizace else {},
            )
        )
        checkbox.toggled.connect(self._sync_zakonna_together)
        if hlaseni is not None and hlaseni.get("datum") is not None:
            try:
                hlaseni["datum"].dateChanged.connect(self._sync_zakonna_together)
            except Exception:
                pass
        self._apply_zakonna_together_enabled()
        if checkbox.isChecked():
            self._copy_zakonna_hlaseni_to_aktualizace()

    def _apply_zakonna_together_enabled(self):
        checkbox = getattr(self, "zakonna_together_checkbox", None)
        aktualizace = self._zakonna_row_by_key(OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU)
        if aktualizace is None:
            return
        together = bool(checkbox is not None and checkbox.isChecked())
        for field in ("datum", "cas"):
            widget = aktualizace.get(field)
            if widget is not None:
                widget.setEnabled(not together)

    def _copy_zakonna_hlaseni_to_aktualizace(self):
        hlaseni = self._zakonna_row_by_key(OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI)
        aktualizace = self._zakonna_row_by_key(OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU)
        if hlaseni is None or aktualizace is None:
            return
        sent = self._admin_date_value(hlaseni.get("datum"))
        if sent is None:
            return
        widget = aktualizace.get("datum")
        if widget is None:
            return
        try:
            widget.blockSignals(True)
            self._set_date_widget(widget, sent)
        finally:
            widget.blockSignals(False)
        cas = hlaseni.get("cas")
        target_cas = aktualizace.get("cas")
        if cas is not None and target_cas is not None:
            target_cas.setText(cas.text())

    def _sync_zakonna_together(self, *_args):
        self._apply_zakonna_together_enabled()
        checkbox = getattr(self, "zakonna_together_checkbox", None)
        if checkbox is not None and checkbox.isChecked():
            self._copy_zakonna_hlaseni_to_aktualizace()


    def _form_templates_dir(self):
        from core.services.storage_service import storage_service
        storage_service.ensure_structure()
        user_dir = storage_service.templates_dir / "setreni"
        if user_dir.exists():
            return user_dir
        return storage_service.bundled_templates_dir() / "setreni"

    def _form_output_filename(self, title, suffix=".odt"):
        number = self._accident_number_slug()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"Formular-{self._slug(title)}-{number}_{stamp}{suffix}"

    def _prepare_odt_form_copy(self, template_path, output_path):
        import html
        import zipfile

        from core.export.odt_engine import (
            is_active_odt_zip_entry,
            strip_active_odt_manifest_entries,
        )

        accident_number = self.accident.number if self.accident is not None else ""
        escaped_number = html.escape(str(accident_number), quote=False)

        with zipfile.ZipFile(template_path, "r") as zin, zipfile.ZipFile(output_path, "w") as zout:

            items = [
                item
                for item in zin.infolist()
                if not is_active_odt_zip_entry(item.filename)
            ]
            stripped_active = len(items) != len(zin.infolist())
            for item in items:
                data = zin.read(item.filename)
                if item.filename == "content.xml":
                    xml = data.decode("utf-8")
                    # Závěrečná zpráva používá šablonové proměnné; běžné formuláře mají jen text "Číslo úrazu:".
                    xml = xml.replace("${cislo_urazu}", escaped_number)
                    xml = xml.replace("Číslo pracovního úrazu    ${cislo_urazu}", f"Číslo pracovního úrazu    {escaped_number}")
                    if "Číslo úrazu:" in xml:
                        xml = xml.replace("Číslo úrazu:", f"Číslo úrazu: {escaped_number}", 1)
                    data = xml.encode("utf-8")
                elif item.filename == "META-INF/manifest.xml" and stripped_active:
                    data = strip_active_odt_manifest_entries(
                        data.decode("utf-8")
                    ).encode("utf-8")
                zout.writestr(item, data)

    def _open_setreni_form(self, template_filename, title):
        from PySide6.QtWidgets import QMessageBox

        from core.export import open_export_file
        from core.services.storage_service import storage_service

        if self.accident is None:
            QMessageBox.information(self, "Formuláře", "Formulář lze vytvořit až po uložení úrazu.")
            return

        template_path = self._form_templates_dir() / template_filename
        if not template_path.exists():
            QMessageBox.warning(self, "Formuláře", f"Šablona nebyla nalezena:\n{template_path}")
            return

        tmp_dir = storage_service.exports_dir / "docasne_formulare"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / self._form_output_filename(title)
        self._prepare_odt_form_copy(template_path, tmp_path)

        stored_name = tmp_path.name
        attachment = attachment_service.add_file_as("accident", self.accident.id, str(tmp_path), stored_name)
        final_path = attachment_service.resolve_path(attachment) if attachment is not None else tmp_path

        open_export_file(final_path, parent=self, title="Formuláře")

    def _tab_formulare(self):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(10, 10, 10, 10)

        info = QLabel(
            "Zde otevřete editovatelné ODT formuláře pro šetření úrazu. "
            "Při otevření se vytvoří kopie formuláře a automaticky se doplní pouze číslo úrazu."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        group = QGroupBox("Formuláře šetření")
        group_layout = QVBoxLayout(group)

        forms = [
            ("CL-Prijeti-Oznameni-Urazu.odt", "Přijetí oznámení pracovního úrazu"),
            ("Form-Zajisteni-Dukazu.odt", "Zajištění důkazů pracovního úrazu"),
            ("Prot-Ohledani-Mista.odt", "Protokol o ohledání místa úrazu"),
            ("Prot-Vyjadreni-Postizeny.odt", "Vyjádření postiženého k pracovnímu úrazu"),
            ("Prot-Vyjadreni-Svedek.odt", "Vyjádření svědka k pracovnímu úrazu"),
            ("CL-Vypovedi.odt", "Postup vedení výpovědí postiženého a svědků"),
            ("Prot-Vypoved.odt", "Výpověď postiženého / svědka k pracovnímu úrazu"),
        ]

        for filename, title in forms:
            btn = QPushButton(title)
            btn.setMinimumHeight(36)
            btn.clicked.connect(lambda checked=False, f=filename, t=title: self._open_setreni_form(f, t))
            group_layout.addWidget(btn)

        layout.addWidget(group)
        layout.addStretch()
        return w

    def _tab_ohlasovaci_povinnosti(self):
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        heading = QLabel("Ohlašovací povinnosti")
        heading.setObjectName("SectionHeading")
        layout.addWidget(heading)
        self._ohlaseni_scroll = scroll

        form = QFormLayout()
        form.addRow("Šetření provedl – jméno:", self.admin_setreni_jmeno)
        form.addRow("Šetření provedl – funkce:", self.admin_setreni_funkce)
        form.addRow("Datum zahájení šetření:", self.admin_zahajeni)
        form.addRow("", self.admin_zahajeni_warning)
        form.addRow("Důvod pozdějšího zahájení:", self.admin_duvod_pozde)
        layout.addLayout(form)
        self._refresh_admin_zahajeni_warning()

        info = QLabel(
            "Zobrazují se pouze povinnosti, které podle zadaných údajů z karty úrazu skutečně vznikají. "
            "Druh úrazu se zde záměrně znovu nezadává."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        visible_ohlaseni_rows = [row for row in self.admin_ohlaseni_rows if self._admin_row_relevant(row)]
        if visible_ohlaseni_rows:
            ohlaseni = QGroupBox("OHLÁŠENÍ")
            ohlaseni_layout = QHBoxLayout(ohlaseni)
            left = QVBoxLayout()
            right = QVBoxLayout()
            for index, row in enumerate(visible_ohlaseni_rows):
                (left if index < (len(visible_ohlaseni_rows) + 1) // 2 else right).addWidget(
                    self._admin_row_group(row, "ohlášení")
                )
            left.addStretch()
            right.addStretch()
            ohlaseni_layout.addLayout(left)
            ohlaseni_layout.addLayout(right)
            layout.addWidget(ohlaseni)

        visible_zaznam_rows = [
            row
            for row in (self.admin_zaznam_rows + self.admin_odeslani_rows)
            if self._admin_row_relevant(row)
        ]
        if visible_zaznam_rows:
            zaznam = QGroupBox("ZÁZNAM O PRACOVNÍM ÚRAZU")
            zaznam_layout = QVBoxLayout(zaznam)
            for row in visible_zaznam_rows:
                if row.get("key") == OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU:
                    mode = "vyhotovení / odeslání"
                elif row.get("section") == SECTION_ZAZNAM:
                    mode = "vyhotovení"
                elif row.get("key") == "ezop":
                    mode = "ohlášení"
                else:
                    mode = "odeslání"
                zaznam_layout.addWidget(self._admin_row_group(row, mode))
            layout.addWidget(zaznam)

        visible_predani_rows = [row for row in self.admin_predani_rows if self._admin_row_relevant(row)]
        if visible_predani_rows:
            predani = QGroupBox("PŘEDÁNÍ KOPIÍ ZÁZNAMU")
            predani_layout = QVBoxLayout(predani)
            for row in visible_predani_rows:
                predani_layout.addWidget(self._admin_row_group(row, "předání"))
            layout.addWidget(predani)

        visible_dpn_rows = [
            row for row in getattr(self, "admin_dpn_rows", []) if self._admin_row_relevant(row)
        ]
        if visible_dpn_rows:
            dpn = QGroupBox("AKTUALIZACE ZÁZNAMU PO UKONČENÍ DPN")
            dpn_layout = QVBoxLayout(dpn)
            for row in visible_dpn_rows:
                key = row.get("key")
                if key == OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL:
                    mode = "aktualizace"
                elif key in {
                    OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
                    OBLIGATION_AKTUALIZACE_OO,
                }:
                    mode = "předání"
                else:
                    mode = "odeslání"
                group = self._admin_row_group(row, mode)
                row["_group"] = group
                dpn_layout.addWidget(group)
            layout.addWidget(dpn)

        visible_zakonna_rows = [
            row
            for row in getattr(self, "admin_zakonna_rows", [])
            if self._admin_row_relevant(row)
        ]
        if visible_zakonna_rows:
            zakonna = QGroupBox("ZÁKONNÁ POJIŠŤOVNA")
            zakonna_layout = QVBoxLayout(zakonna)
            info = QLabel(
                "Agenda pojistné události. Neovlivňuje stav Záznamu o úrazu."
            )
            info.setWordWrap(True)
            info.setObjectName("MutedText")
            zakonna_layout.addWidget(info)
            self.zakonna_together_checkbox = QCheckBox(ZAKONNA_TOGETHER_CHECKBOX_LABEL)
            aktualizace_visible = any(
                row.get("key") == OBLIGATION_ZAKONNA_POJISTOVNA_AKTUALIZACE_ZOU
                for row in visible_zakonna_rows
            )
            self.zakonna_together_checkbox.setVisible(aktualizace_visible)
            zakonna_layout.addWidget(self.zakonna_together_checkbox)
            for row in visible_zakonna_rows:
                if row.get("key") == OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI:
                    mode = "nahlášení"
                else:
                    mode = "doplnění"
                zakonna_layout.addWidget(self._admin_row_group(row, mode))
            self._init_zakonna_together_checkbox()
            layout.addWidget(zakonna)
        else:
            self.zakonna_together_checkbox = None

        visible_nemocenske_rows = [
            row for row in self.admin_nemocenske_rows if self._admin_row_relevant(row)
        ]
        if visible_nemocenske_rows:
            nemocenske = QGroupBox("NEMOCENSKÉ POJIŠTĚNÍ")
            nemocenske_layout = QVBoxLayout(nemocenske)
            for row in visible_nemocenske_rows:
                nemocenske_layout.addWidget(self._admin_row_group(row, "odeslání"))
            layout.addWidget(nemocenske)

        end_form = QFormLayout()
        end_form.addRow(f"{CLOSURE_DATE_LABEL}:", self.admin_ukonceni)
        end_form.addRow(f"{CASE_CLOSED_LABEL}:", self.admin_pripad_uzavren)
        layout.addLayout(end_form)
        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        return w
