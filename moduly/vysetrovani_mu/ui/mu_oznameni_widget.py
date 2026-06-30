from datetime import date

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.vysetrovani_mu.sluzby.mu_oznameni_opatreni import format_checked_okamzita_opatreni
from moduly.vysetrovani_mu.sluzby.mu_source_context import MuSourceContext, resolve_mu_source_context


class MuOznameniWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._source_type = ""
        self._source_id: int | None = None
        self._source_label = ""
        self._investigation_number = ""
        self._loaded_from_record = False

        self._build_ui()

    def set_context(
        self,
        source_type: str,
        source_id: int | None,
        source_label: str = "",
        investigation_number: str = "",
    ) -> None:
        self._source_type = source_type or ""
        self._source_id = source_id
        self._source_label = source_label or ""
        self._investigation_number = investigation_number or ""

        context = self._resolve_context()
        self._apply_source_context(context)

        if not self._loaded_from_record:
            self._apply_source_defaults(context)

    def load_from_investigation(self, investigation) -> None:
        self._loaded_from_record = True

        self.oznameni_kdo.setText(investigation.oznameni_kdo or "")
        komu = investigation.oznameni_komu or ""
        if komu:
            index = self.oznameni_komu.findText(komu)
            if index >= 0:
                self.oznameni_komu.setCurrentIndex(index)
            else:
                self.oznameni_komu.setEditText(komu)

        if investigation.oznameni_datum:
            self.oznameni_datum.set_date_value(investigation.oznameni_datum)
        else:
            self.oznameni_datum.clear_date()

        self.oznameni_cas.setText(investigation.oznameni_cas or "")

        if investigation.oznameni_bezodkladne == "NE":
            self.oznameni_bezodkladne_ne.setChecked(True)
        else:
            self.oznameni_bezodkladne_ano.setChecked(True)

        self.oznameni_duvod_pozde.setPlainText(investigation.oznameni_duvod_pozde or "")
        self.oznameni_popis.setPlainText(investigation.oznameni_popis or "")

        pairs = [
            (self.op_prvni_pomoc, investigation.opatreni_prvni_pomoc),
            (self.op_zzs, investigation.opatreni_zzs),
            (self.op_policie, investigation.opatreni_policie),
            (self.op_hzs, investigation.opatreni_hzs),
            (self.op_zastavena_cinnost, investigation.opatreni_zastavena_cinnost),
            (self.op_zajisteno_misto, investigation.opatreni_zajisteno_misto),
            (self.op_zabraneno_manipulaci, investigation.opatreni_zabraneno_manipulaci),
            (self.op_informovan_nadrizeny, investigation.opatreni_informovan_nadrizeny),
            (self.op_informovan_bozp, investigation.opatreni_informovan_bozp),
        ]
        for checkbox, value in pairs:
            checkbox.setChecked((value or "") == "ANO")

        if investigation.oznameni_bozp_datum:
            self.oznameni_bozp_datum.set_date_value(investigation.oznameni_bozp_datum)
        else:
            self.oznameni_bozp_datum.clear_date()

        self.oznameni_bozp_cas.setText(investigation.oznameni_bozp_cas or "")
        self.op_informovany_dalsi.setChecked((investigation.opatreni_informovany_dalsi or "") == "ANO")

        if investigation.dalsi_postup:
            self.dalsi_postup.setCurrentText(investigation.dalsi_postup)
        self.dalsi_postup_jiny.setPlainText(getattr(investigation, "dalsi_postup_jiny", "") or "")
        self._refresh_jiny_postup()

    def get_data(self) -> dict:
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
            "opatreni_policie": "ANO" if self.op_policie.isChecked() else "",
            "opatreni_hzs": "ANO" if self.op_hzs.isChecked() else "",
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

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        tab = QWidget()
        scroll.setWidget(tab)

        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)

        cil = QLabel(
            "<b>Cíl:</b> ochránit zdraví osob, zajistit potřebnou pomoc a neznehodnotit důkazy potřebné pro šetření mimořádné události."
        )
        cil.setWordWrap(True)
        layout.addWidget(cil)

        layout.addWidget(QLabel("1. Základní údaje"))
        g1 = QGroupBox()
        f1 = QFormLayout(g1)

        self.event_number_label = QLabel("")
        self.oznameni_kdo = QLineEdit()
        self.oznameni_komu = ThpWorkerSelector()
        self.oznameni_komu.setEditable(True)
        self.oznameni_datum = NullableDateEdit()
        self.oznameni_cas = QLineEdit()
        self.oznameni_cas.setPlaceholderText("např. 14:35")

        self.oznameni_bezodkladne_ano = QRadioButton("ANO")
        self.oznameni_bezodkladne_ne = QRadioButton("NE")
        self.oznameni_bezodkladne_ano.setChecked(True)

        rb_layout = QHBoxLayout()
        rb_layout.addWidget(self.oznameni_bezodkladne_ano)
        rb_layout.addWidget(self.oznameni_bezodkladne_ne)
        rb_layout.addStretch()

        self.oznameni_duvod_pozde = QTextEdit()
        self.oznameni_duvod_pozde.setFixedHeight(70)
        self.oznameni_duvod_pozde.setPlaceholderText("Důvod")
        self.oznameni_bezodkladne_ano.toggled.connect(self._refresh_duvod)
        self.oznameni_bezodkladne_ne.toggled.connect(self._refresh_duvod)

        f1.addRow("Číslo události:", self.event_number_label)
        f1.addRow("Kdo událost oznámil:", self.oznameni_kdo)
        f1.addRow("Komu byla událost oznámena:", self.oznameni_komu)
        f1.addRow("Datum oznámení:", self.oznameni_datum)
        f1.addRow("Čas oznámení:", self.oznameni_cas)
        f1.addRow("Oznámeno bezodkladně:", rb_layout)
        f1.addRow("Důvod pozdního oznámení:", self.oznameni_duvod_pozde)
        layout.addWidget(g1)

        layout.addWidget(QLabel("2. Dotčená osoba"))
        g2 = QGroupBox()
        f2 = QFormLayout(g2)
        self.affected_person_label = QLabel("")
        self.affected_person_label.setWordWrap(True)
        f2.addRow(self.affected_person_label)
        layout.addWidget(g2)

        layout.addWidget(QLabel("3. Událost"))
        g3 = QGroupBox()
        f3 = QFormLayout(g3)
        self.source_record_label = QLabel("")
        self.source_record_label.setWordWrap(True)
        self.oznameni_popis = QTextEdit()
        self.oznameni_popis.setFixedHeight(95)
        f3.addRow("Údaje ze zdrojového záznamu:", self.source_record_label)
        f3.addRow("Stručný popis události:", self.oznameni_popis)
        layout.addWidget(g3)

        layout.addWidget(QLabel("4. Okamžitá opatření"))
        g4 = QGroupBox()
        v4 = QVBoxLayout(g4)

        self.op_prvni_pomoc = QCheckBox("Poskytnuta první pomoc")
        self.op_zzs = QCheckBox("Přivolána ZZS")
        self.op_policie = QCheckBox("Přivolána Policie ČR")
        self.op_hzs = QCheckBox("Přivolán Hasičský záchranný sbor")
        self.op_zastavena_cinnost = QCheckBox("Zastavena nebezpečná činnost")
        self.op_zajisteno_misto = QCheckBox("Zajištěno místo události")
        self.op_zabraneno_manipulaci = QCheckBox("Zabráněno manipulaci s předměty")
        self.op_informovan_nadrizeny = QCheckBox("Informován nadřízený")
        self.op_informovan_bozp = QCheckBox("Informován BOZP")

        for checkbox in (
            self.op_prvni_pomoc,
            self.op_zzs,
            self.op_policie,
            self.op_hzs,
            self.op_zastavena_cinnost,
            self.op_zajisteno_misto,
            self.op_zabraneno_manipulaci,
            self.op_informovan_nadrizeny,
            self.op_informovan_bozp,
        ):
            v4.addWidget(checkbox)

        f4 = QFormLayout()
        self.oznameni_bozp_datum = NullableDateEdit()
        self.oznameni_bozp_cas = QLineEdit()
        self.oznameni_bozp_cas.setPlaceholderText("např. 14:35")
        f4.addRow("Datum oznámení BOZP:", self.oznameni_bozp_datum)
        f4.addRow("Čas oznámení BOZP:", self.oznameni_bozp_cas)
        v4.addLayout(f4)

        self.op_informovany_dalsi = QCheckBox("Informovány další osoby podle závažnosti")
        v4.addWidget(self.op_informovany_dalsi)
        layout.addWidget(g4)

        layout.addWidget(QLabel("5. Další postup"))
        g5 = QGroupBox()
        f5 = QFormLayout(g5)
        self.dalsi_postup = QComboBox()
        self.dalsi_postup.setEditable(True)
        self.dalsi_postup.addItems(["", "pokračoval v práci", "odešel k lékaři", "byl odvezen ZZS", "jiný postup"])
        self.dalsi_postup_jiny = QTextEdit()
        self.dalsi_postup_jiny.setFixedHeight(70)
        self.dalsi_postup_jiny.setPlaceholderText("Vyplňte jaký postup byl zvolen.")
        self.dalsi_postup.currentTextChanged.connect(self._refresh_jiny_postup)
        f5.addRow("Další postup:", self.dalsi_postup)
        f5.addRow("Jiný postup:", self.dalsi_postup_jiny)
        layout.addWidget(g5)

        layout.addStretch()
        self._refresh_duvod()
        self._refresh_jiny_postup()

    def _resolve_context(self) -> MuSourceContext:
        context = resolve_mu_source_context(
            self._source_type,
            self._source_id,
            self._source_label,
            self._investigation_number,
        )
        if not context.event_number and self._investigation_number:
            context.event_number = self._investigation_number
        return context

    def _apply_source_context(self, context: MuSourceContext) -> None:
        self.event_number_label.setText(context.event_number or "")
        self.affected_person_label.setText(context.affected_person_html or "")
        self.source_record_label.setText(context.source_record_html or "")

    def _apply_source_defaults(self, context: MuSourceContext) -> None:
        if context.default_oznameni_kdo and not self.oznameni_kdo.text().strip():
            self.oznameni_kdo.setText(context.default_oznameni_kdo)

        if context.default_oznameni_komu:
            komu = context.default_oznameni_komu
            if not self.oznameni_komu.currentText().strip():
                index = self.oznameni_komu.findText(komu)
                if index >= 0:
                    self.oznameni_komu.setCurrentIndex(index)
                else:
                    self.oznameni_komu.setEditText(komu)

        if context.default_oznameni_datum and self.oznameni_datum.get_date() is None:
            self.oznameni_datum.set_date_value(context.default_oznameni_datum)

        if context.default_oznameni_cas and not self.oznameni_cas.text().strip():
            self.oznameni_cas.setText(context.default_oznameni_cas)

        if context.default_oznameni_popis and not self.oznameni_popis.toPlainText().strip():
            self.oznameni_popis.setPlainText(context.default_oznameni_popis)

    def _refresh_duvod(self) -> None:
        self.oznameni_duvod_pozde.setVisible(self.oznameni_bezodkladne_ne.isChecked())

    def _refresh_jiny_postup(self) -> None:
        self.dalsi_postup_jiny.setVisible(self.dalsi_postup.currentText().strip().lower() == "jiný postup")

    def export_okamzita_opatreni(self) -> str:
        """Text zaškrtnutých okamžitých opatření pro tisk/export."""
        return format_checked_okamzita_opatreni(self.get_data())

    def _date_value(self, widget) -> date | None:
        if hasattr(widget, "get_date"):
            return widget.get_date()
        return None
