import json

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.shared.constants import (
    ENTITY_MU_INVESTIGATION,
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_VYPORADANO,
)
from core.shared.sluzby.finding_service import finding_service
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.thp_worker_selector import ThpWorkerSelector


class MuZaverWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._saved_data: dict = {}
        self._investigation_id: int | None = None
        self._has_saved_prubeh = False
        self._has_saved_hlavni_zjisteni = False
        self._has_saved_uzavreni_vedouci = False
        self._init_widgets()
        self._build_ui()

    def set_investigation_id(self, investigation_id: int | None) -> None:
        self._investigation_id = investigation_id
        self.refresh_measures_summary()

    def set_conclusion(self, text: str) -> None:
        self.zaverecne_shrnuti_edit.setPlainText(text or "")

    def get_conclusion(self) -> str:
        return self.zaverecne_shrnuti_edit.toPlainText().strip()

    def load_json(self, raw_json: str) -> None:
        try:
            self._saved_data = json.loads(raw_json or "{}")
        except Exception:
            self._saved_data = {}
        self._has_saved_prubeh = bool((self._saved_data.get("vysledek_prubeh") or "").strip())
        self._has_saved_hlavni_zjisteni = bool(
            (self._saved_data.get("vysledek_hlavni_zjisteni") or "").strip()
        )
        self._has_saved_uzavreni_vedouci = bool(
            (self._saved_data.get("uzavreni_vedouci") or "").strip()
        )
        self._apply_saved_data()

    def apply_investigation_sources(
        self,
        *,
        short_description: str = "",
        oznameni_popis: str = "",
        lead_thp_worker_id: int | None = None,
        lead_thp_worker_name: str = "",
    ) -> None:
        if not self._has_saved_prubeh:
            prubeh = self._build_prubeh_text(short_description, oznameni_popis)
            if prubeh:
                self.vysledek_prubeh_edit.setPlainText(prubeh)

        if not self._has_saved_hlavni_zjisteni:
            zjisteni = self._build_findings_summary()
            if zjisteni:
                self.vysledek_hlavni_zjisteni_edit.setPlainText(zjisteni)

        if not self._has_saved_uzavreni_vedouci:
            self._set_vedouci_selector(lead_thp_worker_id, lead_thp_worker_name)

    def get_json(self) -> str:
        return json.dumps(self.get_data(), ensure_ascii=False)

    def get_data(self) -> dict:
        return {
            "vysledek_prubeh": self.vysledek_prubeh_edit.toPlainText().strip(),
            "vysledek_hlavni_zjisteni": self.vysledek_hlavni_zjisteni_edit.toPlainText().strip(),
            "vysledek_hlavni_priciny": self.vysledek_hlavni_priciny_edit.toPlainText().strip(),
            "uzavreni_datum": self._date_to_json(self.uzavreni_datum_edit),
            "uzavreni_vedouci": self.uzavreni_vedouci_selector.currentText().strip(),
            "uzavreni_poznamka": self.uzavreni_poznamka_edit.toPlainText().strip(),
        }

    def refresh_measures_summary(self) -> None:
        if self._investigation_id is None:
            self._set_measures_labels(0, 0, 0, 0)
            return

        summary = finding_service.summarize(ENTITY_MU_INVESTIGATION, self._investigation_id)
        findings = finding_service.get_for_entity(ENTITY_MU_INVESTIGATION, self._investigation_id)
        linked_tasks = sum(1 for finding in findings if finding.task_id)

        open_count = int(summary.get(FINDING_STATUS_OTEVRENE, 0))
        resolved_count = int(summary.get(FINDING_STATUS_VYPORADANO, 0))
        total = int(summary.get("total", 0))

        self._set_measures_labels(total, open_count, resolved_count, linked_tasks)

    def _set_measures_labels(
        self,
        total: int,
        open_count: int,
        resolved_count: int,
        linked_tasks: int,
    ) -> None:
        self.measures_total_label.setText(f"Počet zjištění celkem: {total}")
        self.measures_open_label.setText(f"Počet otevřených zjištění: {open_count}")
        self.measures_resolved_label.setText(f"Počet vypořádaných zjištění: {resolved_count}")
        self.measures_tasks_label.setText(f"Počet navázaných úkolů: {linked_tasks}")

    def _init_widgets(self) -> None:
        saved = self._saved_data

        self.vysledek_prubeh_edit = QTextEdit()
        self.vysledek_prubeh_edit.setPlaceholderText("Stručné shrnutí zjištěného průběhu události")
        self.vysledek_prubeh_edit.setMinimumHeight(90)
        self.vysledek_prubeh_edit.setPlainText(saved.get("vysledek_prubeh", ""))

        self.vysledek_hlavni_zjisteni_edit = QTextEdit()
        self.vysledek_hlavni_zjisteni_edit.setPlaceholderText("Hlavní zjištění")
        self.vysledek_hlavni_zjisteni_edit.setMinimumHeight(90)
        self.vysledek_hlavni_zjisteni_edit.setPlainText(saved.get("vysledek_hlavni_zjisteni", ""))

        self.vysledek_hlavni_priciny_edit = QTextEdit()
        self.vysledek_hlavni_priciny_edit.setPlaceholderText(
            "Hlavní příčiny (doplní modul Analýza příčin / Ishikawa+)"
        )
        self.vysledek_hlavni_priciny_edit.setMinimumHeight(90)

        self.measures_total_label = QLabel("Počet zjištění celkem: 0")
        self.measures_open_label = QLabel("Počet otevřených zjištění: 0")
        self.measures_resolved_label = QLabel("Počet vypořádaných zjištění: 0")
        self.measures_tasks_label = QLabel("Počet navázaných úkolů: 0")
        for label in (
            self.measures_total_label,
            self.measures_open_label,
            self.measures_resolved_label,
            self.measures_tasks_label,
        ):
            label.setWordWrap(True)

        self.uzavreni_datum_edit = NullableDateEdit()
        if saved.get("uzavreni_datum"):
            self._set_date_widget(self.uzavreni_datum_edit, saved.get("uzavreni_datum"))

        self.uzavreni_vedouci_selector = ThpWorkerSelector()
        self.uzavreni_vedouci_selector.setEditable(True)
        vedouci = saved.get("uzavreni_vedouci") or ""
        if vedouci:
            index = self.uzavreni_vedouci_selector.findText(vedouci)
            if index >= 0:
                self.uzavreni_vedouci_selector.setCurrentIndex(index)
            else:
                self.uzavreni_vedouci_selector.setEditText(vedouci)

        self.uzavreni_poznamka_edit = QTextEdit()
        self.uzavreni_poznamka_edit.setPlaceholderText("Poznámka k uzavření")
        self.uzavreni_poznamka_edit.setMinimumHeight(90)
        self.uzavreni_poznamka_edit.setPlainText(saved.get("uzavreni_poznamka", ""))

        self.zaverecne_shrnuti_edit = QTextEdit()
        self.zaverecne_shrnuti_edit.setPlaceholderText("Závěrečné shrnutí vyšetřování")
        self.zaverecne_shrnuti_edit.setMinimumHeight(120)

    def _apply_saved_data(self) -> None:
        saved = self._saved_data
        self.vysledek_prubeh_edit.setPlainText(saved.get("vysledek_prubeh", ""))
        self.vysledek_hlavni_zjisteni_edit.setPlainText(saved.get("vysledek_hlavni_zjisteni", ""))
        self.vysledek_hlavni_priciny_edit.setPlainText(saved.get("vysledek_hlavni_priciny", "") or "")

        self._set_date_widget(self.uzavreni_datum_edit, saved.get("uzavreni_datum"))
        if self._has_saved_uzavreni_vedouci:
            self._set_vedouci_selector_text(saved.get("uzavreni_vedouci") or "")
        else:
            self.uzavreni_vedouci_selector.setCurrentIndex(-1)
            self.uzavreni_vedouci_selector.setEditText("")

        self.uzavreni_poznamka_edit.setPlainText(saved.get("uzavreni_poznamka", ""))
        self.refresh_measures_summary()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)

        vysledek_group = QGroupBox("Výsledek šetření")
        vysledek_form = QFormLayout(vysledek_group)
        vysledek_form.addRow("Průběh události:", self.vysledek_prubeh_edit)
        vysledek_form.addRow("Hlavní zjištění:", self.vysledek_hlavni_zjisteni_edit)
        vysledek_form.addRow("Hlavní příčiny:", self.vysledek_hlavni_priciny_edit)
        layout.addWidget(vysledek_group)

        opatreni_group = QGroupBox("Vyhodnocení opatření")
        opatreni_layout = QVBoxLayout(opatreni_group)
        info = QLabel("Údaje jsou odvozeny ze zjištění vyšetřování.")
        info.setWordWrap(True)
        opatreni_layout.addWidget(info)
        opatreni_layout.addWidget(self.measures_total_label)
        opatreni_layout.addWidget(self.measures_open_label)
        opatreni_layout.addWidget(self.measures_resolved_label)
        opatreni_layout.addWidget(self.measures_tasks_label)
        layout.addWidget(opatreni_group)

        uzavreni_group = QGroupBox("Uzavření vyšetřování")
        uzavreni_form = QFormLayout(uzavreni_group)
        uzavreni_form.addRow("Datum uzavření:", self.uzavreni_datum_edit)
        uzavreni_form.addRow("Uzavřel / vedoucí šetření:", self.uzavreni_vedouci_selector)
        uzavreni_form.addRow("Poznámka k uzavření:", self.uzavreni_poznamka_edit)
        layout.addWidget(uzavreni_group)

        shrnuti_group = QGroupBox("Závěrečné shrnutí")
        shrnuti_layout = QVBoxLayout(shrnuti_group)
        shrnuti_layout.addWidget(self.zaverecne_shrnuti_edit)
        layout.addWidget(shrnuti_group)

        layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _build_prubeh_text(self, short_description: str, oznameni_popis: str) -> str:
        parts = []
        short = (short_description or "").strip()
        popis = (oznameni_popis or "").strip()
        if short:
            parts.append(short)
        if popis and popis not in short:
            parts.append(popis)
        return "\n\n".join(parts)

    def _build_findings_summary(self) -> str:
        if self._investigation_id is None:
            return ""

        findings = finding_service.get_for_entity(ENTITY_MU_INVESTIGATION, self._investigation_id)
        lines = []
        for index, finding in enumerate(findings, start=1):
            description = (finding.description or "").strip()
            if not description:
                continue
            reference = (finding.reference_label or "").strip()
            prefix = f"{index}. "
            if reference:
                prefix = f"{index}. [{reference}] "
            lines.append(f"{prefix}{description}")
        return "\n\n".join(lines)

    def _set_vedouci_selector(
        self,
        lead_thp_worker_id: int | None,
        lead_thp_worker_name: str,
    ) -> None:
        if lead_thp_worker_id:
            self.uzavreni_vedouci_selector.set_person_id(lead_thp_worker_id)
            return
        if lead_thp_worker_name.strip():
            self._set_vedouci_selector_text(lead_thp_worker_name.strip())

    def _set_vedouci_selector_text(self, vedouci: str) -> None:
        if not vedouci:
            self.uzavreni_vedouci_selector.setCurrentIndex(-1)
            self.uzavreni_vedouci_selector.setEditText("")
            return
        index = self.uzavreni_vedouci_selector.findText(vedouci)
        if index >= 0:
            self.uzavreni_vedouci_selector.setCurrentIndex(index)
        else:
            self.uzavreni_vedouci_selector.setEditText(vedouci)

    def _date_to_json(self, widget) -> str:
        value = widget.get_date() if hasattr(widget, "get_date") else None
        if value is None:
            return ""
        return value.isoformat()

    def _set_date_widget(self, widget, value) -> None:
        if not value:
            if hasattr(widget, "clear_date"):
                widget.clear_date()
            return
        if isinstance(value, str) and hasattr(widget, "set_date_iso"):
            widget.set_date_iso(value)
        elif hasattr(widget, "set_date_value"):
            widget.set_date_value(value)
