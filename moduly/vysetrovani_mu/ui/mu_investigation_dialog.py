from datetime import date
import json

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.navigation.source_navigator import ACCIDENT_OPEN_RECORD, source_navigator
from core.shared.constants import ENTITY_ACCIDENT, ENTITY_AUDITY, ENTITY_MU_INVESTIGATION
from core.shared.sluzby.finding_service import finding_service
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.vysetrovani_mu.constants import (
    DEFAULT_EVENT_CHARACTER,
    DEFAULT_MU_STATUS,
    DEFAULT_SOURCE_TYPE,
    EVENT_CHARACTER_URAZ,
    EVENT_CHARACTERS,
    MU_STATUS_DOKONCENO,
    MU_STATUS_ODLOZENO,
    MU_STATUS_PROBIHA,
    SOURCE_TYPE_ACCIDENT,
    SOURCE_TYPE_AUDIT,
    SOURCE_TYPE_CONTROL,
    SOURCE_TYPE_MANUAL,
    SOURCE_TYPE_LABELS,
    SOURCE_TYPES,
)
from moduly.vysetrovani_mu.ui.mu_findings_widget import MuFindingsWidget
from moduly.vysetrovani_mu.ui.mu_investigation_source_panel import MuInvestigationSourcePanel
from moduly.vysetrovani_mu.ui.mu_ohledani_mista_widget import MuOhledaniMistaWidget
from moduly.vysetrovani_mu.ui.mu_oznameni_widget import MuOznameniWidget
from moduly.vysetrovani_mu.ui.mu_source_selector_widget import MuSourceSelectorWidget
from moduly.vysetrovani_mu.ui.mu_casova_osa_widget import MuCasovaOsaWidget
from moduly.vysetrovani_mu.ui.mu_dodrzovani_predpisu_widget import MuDodrzovaniPredpisuWidget
from moduly.vysetrovani_mu.ui.mu_kontrola_souladu_widget import MuKontrolaSouladuWidget
from moduly.vysetrovani_mu.ui.mu_svedci_widget import MuSvedciWidget
from moduly.vysetrovani_mu.ui.mu_zaver_widget import MuZaverWidget
from moduly.vysetrovani_mu.ui.mu_zajisteni_dukazu_widget import MuZajisteniDukazuWidget
from moduly.vysetrovani_mu.sluzby.mu_source_context import resolve_mu_source_context


class MuInvestigationDialog(QDialog):
    _SOURCE_ENTITY_TYPES = {
        SOURCE_TYPE_ACCIDENT: ENTITY_ACCIDENT,
        SOURCE_TYPE_AUDIT: ENTITY_AUDITY,
    }
    _OPEN_BUTTON_LABELS = {
        SOURCE_TYPE_ACCIDENT: "Otevřít zdrojový záznam",
        SOURCE_TYPE_AUDIT: "Otevřít audit",
    }

    def __init__(self, parent=None, investigation=None, *, accident_id: int | None = None):
        super().__init__(parent)

        self.investigation = investigation
        self._preset_accident_id = accident_id
        self._suppress_event_character_source_switch = False

        self.setWindowTitle("Vyšetřování mimořádné události")
        self.resize(860, 720)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._basic_tab(), "Spis")
        self.oznameni_widget = MuOznameniWidget()
        self.tabs.addTab(self.oznameni_widget, "Oznámení")
        self.zajisteni_dukazu_widget = MuZajisteniDukazuWidget()
        self.tabs.addTab(self.zajisteni_dukazu_widget, "Zajištění důkazů")
        self.ohledani_mista_widget = MuOhledaniMistaWidget()
        self.tabs.addTab(self.ohledani_mista_widget, "Ohledání místa")
        self.svedci_widget = MuSvedciWidget()
        self.tabs.addTab(self.svedci_widget, "Svědci")
        self.casova_osa_widget = MuCasovaOsaWidget()
        self.tabs.addTab(self.casova_osa_widget, "Časová osa")
        self.dodrzovani_predpisu_widget = MuDodrzovaniPredpisuWidget()
        self.tabs.addTab(self.dodrzovani_predpisu_widget, "Dodržování předpisů")
        self.kontrola_souladu_widget = MuKontrolaSouladuWidget()
        self.tabs.addTab(self.kontrola_souladu_widget, "Kontrola souladu")
        self.findings_widget = MuFindingsWidget()
        self.tabs.addTab(self.findings_widget, "Zjištění")
        self.zaver_widget = MuZaverWidget()
        self.tabs.addTab(self.zaver_widget, "Závěr")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self.tabs)

        footer = QHBoxLayout()
        self.check_spis_btn = QPushButton("Kontrola spisu")
        self.check_spis_btn.clicked.connect(self._open_investigation_check)
        footer.addWidget(self.check_spis_btn)
        footer.addStretch()
        layout.addLayout(footer)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept_dialog)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.started_at_edit.dateChanged.connect(self._sync_casova_osa_started_at)
        self.oznameni_widget.oznameni_datum.dateChanged.connect(self._sync_casova_osa_oznameni)
        self.oznameni_widget.oznameni_cas.textChanged.connect(self._sync_casova_osa_oznameni)
        self.zajisteni_dukazu_widget.dukazy_datum.dateChanged.connect(self._sync_casova_osa_zajisteni)
        self.zajisteni_dukazu_widget.dukazy_cas.textChanged.connect(self._sync_casova_osa_zajisteni)
        self.zajisteni_dukazu_widget.dukazy_datum_fotek.dateChanged.connect(self._sync_casova_osa_zajisteni)
        self.zajisteni_dukazu_widget.dukazy_cas_fotek.textChanged.connect(self._sync_casova_osa_zajisteni)

        investigation_id = investigation.id if investigation is not None else None
        self.findings_widget.set_investigation_id(investigation_id)
        self.zaver_widget.set_investigation_id(investigation_id)

        if investigation is not None:
            number = investigation.number or "—"
            self.number_header.setText(f"Číslo: {number}")
            self.title_edit.setText(investigation.title or "")
            self._set_event_character(investigation.event_character or DEFAULT_EVENT_CHARACTER)
            self._set_source_type(investigation.source_type or DEFAULT_SOURCE_TYPE)
            self.source_selector.set_source(
                investigation.source_type or DEFAULT_SOURCE_TYPE,
                investigation.source_id,
                investigation.source_label or "",
            )
            self.started_at_edit.set_date_value(investigation.started_at)
            self.status_combo.setCurrentText(investigation.status or DEFAULT_MU_STATUS)
            self.lead_thp_worker_selector.set_person_id(investigation.lead_thp_worker_id)
            self.short_description_edit.setPlainText(investigation.short_description or "")
            self.zaver_widget.set_conclusion(investigation.conclusion or "")
            self.zaver_widget.load_json(getattr(investigation, "zaver_json", "") or "")
            self._refresh_zaver_sources()
            self.ohledani_mista_widget.load_json(getattr(investigation, "ohledani_mista_json", "") or "")
            self.zajisteni_dukazu_widget.load_json(getattr(investigation, "zajisteni_dukazu_json", "") or "")
            self.svedci_widget.load_json(self._svedci_json_for_load(investigation))
            self.casova_osa_widget.load_json(getattr(investigation, "casova_osa_json", "") or "")
            self.dodrzovani_predpisu_widget.load_json(
                getattr(investigation, "dodrzovani_predpisu_json", "") or ""
            )
            self.kontrola_souladu_widget.load_json(getattr(investigation, "kontrola_souladu_json", "") or "")
            self.findings_widget.load_ishikawa_json(getattr(investigation, "ishikawa_json", "") or "")
            self.oznameni_widget.load_from_investigation(investigation)
        elif accident_id is not None:
            self._preset_from_accident(accident_id)
        else:
            self._on_source_type_changed()

        self._refresh_zaver_sources()
        self._refresh_source_dependent_widgets()
        self._update_source_panel()
        self._sync_kontrola_souladu_event_character()
        self._previous_event_character = self.event_character_combo.currentText()

    def _on_event_character_changed(self, new_character: str) -> None:
        self._sync_kontrola_souladu_event_character()

        if self._suppress_event_character_source_switch:
            return

        previous_character = getattr(self, "_previous_event_character", "")
        if (
            previous_character == EVENT_CHARACTER_URAZ
            and new_character != EVENT_CHARACTER_URAZ
            and self._current_source_type() == SOURCE_TYPE_ACCIDENT
        ):
            self._set_source_type(SOURCE_TYPE_MANUAL)
            self._refresh_source_dependent_widgets()
            self._update_source_panel()

        self._previous_event_character = new_character

    def _accept_dialog(self) -> None:
        investigation_id = self.investigation.id if self.investigation is not None else None
        if investigation_id is not None and finding_service.has_unresolved(
            ENTITY_MU_INVESTIGATION,
            investigation_id,
        ):
            QMessageBox.information(
                self,
                "Závěr",
                "Vyšetřování obsahuje otevřená zjištění.",
            )
        self.accept()

    def _on_tab_changed(self, index: int) -> None:
        if self.tabs.widget(index) is self.zaver_widget:
            self._refresh_zaver_sources()
            self.zaver_widget.refresh_measures_summary()

    def _refresh_zaver_sources(self) -> None:
        worker = self.lead_thp_worker_selector.current_person()
        oznameni_data = self.oznameni_widget.get_data()
        self.zaver_widget.apply_investigation_sources(
            short_description=self.short_description_edit.toPlainText(),
            oznameni_popis=oznameni_data.get("oznameni_popis", ""),
            lead_thp_worker_id=self.lead_thp_worker_selector.current_person_id(),
            lead_thp_worker_name=(
                worker.display_name
                if worker is not None
                else self.lead_thp_worker_selector.currentText().strip()
            ),
        )

    def _sync_kontrola_souladu_event_character(self) -> None:
        self.kontrola_souladu_widget.set_event_character(self.event_character_combo.currentText())

    def _basic_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(10)

        self.source_panel = MuInvestigationSourcePanel()
        self.source_panel.open_requested.connect(self._open_source_record)
        layout.addWidget(self.source_panel)

        self.number_header = QLabel("Číslo: —")
        self.number_header.setObjectName("SectionTitle")
        layout.addWidget(self.number_header)

        card = QFrame()
        card.setObjectName("ModulePanel")
        form = QFormLayout(card)
        form.setContentsMargins(12, 12, 12, 12)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Stručný název události")

        self.event_character_combo = QComboBox()
        self.event_character_combo.addItems(EVENT_CHARACTERS)
        self.event_character_combo.currentTextChanged.connect(self._on_event_character_changed)

        self.source_type_combo = QComboBox()
        for source_type in SOURCE_TYPES:
            self.source_type_combo.addItem(SOURCE_TYPE_LABELS[source_type], source_type)
        self.source_type_combo.currentIndexChanged.connect(self._on_source_type_changed)

        self.source_selector = MuSourceSelectorWidget()
        self.source_selector.accident_combo.currentIndexChanged.connect(self._update_source_panel)
        self.source_selector.audit_combo.currentIndexChanged.connect(self._update_source_panel)
        self.source_selector.control_combo.currentIndexChanged.connect(self._update_source_panel)
        self.source_selector.text_edit.textChanged.connect(self._update_source_panel)
        self.source_selector.accident_combo.currentIndexChanged.connect(self._refresh_source_dependent_widgets)
        self.source_selector.audit_combo.currentIndexChanged.connect(self._refresh_source_dependent_widgets)
        self.source_selector.control_combo.currentIndexChanged.connect(self._refresh_source_dependent_widgets)
        self.source_selector.text_edit.textChanged.connect(self._refresh_source_dependent_widgets)

        self.started_at_edit = NullableDateEdit()
        self.started_at_edit.set_date_value(date.today())

        self.status_combo = QComboBox()
        self.status_combo.addItems([
            MU_STATUS_PROBIHA,
            MU_STATUS_DOKONCENO,
            MU_STATUS_ODLOZENO,
        ])
        self.status_combo.setCurrentText(DEFAULT_MU_STATUS)

        self.lead_thp_worker_selector = ThpWorkerSelector()

        self.short_description_edit = QTextEdit()
        self.short_description_edit.setPlaceholderText("Stručný popis události a rozsahu šetření")
        self.short_description_edit.setFixedHeight(110)

        form.addRow("Název události:", self.title_edit)
        form.addRow("Charakter události:", self.event_character_combo)
        form.addRow("Zdroj podnětu:", self.source_type_combo)
        form.addRow("Zdroj:", self.source_selector)
        form.addRow("Šetření zahájeno:", self.started_at_edit)
        form.addRow("Stav:", self.status_combo)
        form.addRow("Vedoucí šetření:", self.lead_thp_worker_selector)
        form.addRow("Stručný popis:", self.short_description_edit)

        layout.addWidget(card, 1)
        return tab

    def _set_event_character(self, value: str) -> None:
        self._suppress_event_character_source_switch = True
        index = self.event_character_combo.findText(value)
        if index >= 0:
            self.event_character_combo.setCurrentIndex(index)
        self._previous_event_character = self.event_character_combo.currentText()
        self._suppress_event_character_source_switch = False

    def _set_source_type(self, source_type: str) -> None:
        index = self.source_type_combo.findData(source_type)
        if index >= 0:
            self.source_type_combo.blockSignals(True)
            self.source_type_combo.setCurrentIndex(index)
            self.source_type_combo.blockSignals(False)
            self.source_selector.set_source_type(source_type)

    def _on_source_type_changed(self) -> None:
        source_type = self.source_type_combo.currentData() or DEFAULT_SOURCE_TYPE
        self.source_selector.set_source_type(source_type)
        self._update_source_panel()
        self._refresh_source_dependent_widgets()

    def _current_source_id(self) -> int | None:
        source_id = self.source_selector.current_source_id()
        if source_id is not None:
            return source_id
        if self.investigation is not None:
            return self.investigation.source_id
        return None

    def _current_source_label(self) -> str:
        label = self.source_selector.current_source_label()
        if label:
            return label
        if self.investigation is not None:
            return (self.investigation.source_label or "").strip()
        return ""

    def _preset_from_accident(self, accident_id: int) -> None:
        from moduly.kniha_urazu.sluzby.accident_service import accident_service

        accident = accident_service.get_by_id(accident_id)
        if accident is None:
            self._on_source_type_changed()
            return

        self._set_event_character(EVENT_CHARACTER_URAZ)
        self._set_source_type(SOURCE_TYPE_ACCIDENT)

        label = accident.number or f"ID {accident.id}"
        name = (accident.employee_name or "").strip()
        if name:
            label = f"{label} — {name}"
        self.source_selector.set_source(SOURCE_TYPE_ACCIDENT, accident_id, label)

        if accident.accident_date is not None and self.started_at_edit.get_date() is None:
            self.started_at_edit.set_date_value(accident.accident_date)

        if not self.title_edit.text().strip():
            popis = (accident.popis_urazoveho_deje or "").strip()
            if popis:
                self.title_edit.setText(popis.splitlines()[0][:250])

    def _refresh_source_dependent_widgets(self) -> None:
        investigation_id = self.investigation.id if self.investigation is not None else None
        investigation_number = self.investigation.number if self.investigation is not None else ""
        source_type = self._current_source_type()
        source_id = self._current_source_id()
        source_label = self.source_selector.current_source_label() or (
            (self.investigation.source_label or "") if self.investigation is not None else ""
        )

        context = resolve_mu_source_context(
            source_type,
            source_id,
            source_label,
            investigation_number,
        )
        if not context.event_number and investigation_number:
            context.event_number = investigation_number

        self.oznameni_widget.set_context(
            source_type,
            source_id,
            source_label,
            investigation_number,
        )
        self.zajisteni_dukazu_widget.set_context(
            investigation_id,
            event_number=context.event_number,
            context=context,
        )
        self.ohledani_mista_widget.set_context(
            investigation_id,
            event_number=context.event_number,
            investigation_number=investigation_number,
        )
        self.svedci_widget.set_context(
            investigation_id,
            event_number=context.event_number,
        )
        self.casova_osa_widget.set_context(
            investigation_id,
            event_number=context.event_number,
            started_at=self.started_at_edit.get_date(),
            source_type=source_type,
            source_id=source_id,
            event_datum=context.event_datum,
            event_cas=context.event_cas,
            **self._casova_osa_oznameni_context(),
        )
        self.casova_osa_widget.set_zajisteni_context(**self._casova_osa_zajisteni_context())
        self.dodrzovani_predpisu_widget.set_context(
            investigation_id,
            event_number=context.event_number,
        )

    def _casova_osa_oznameni_context(self) -> dict:
        oznameni = self.oznameni_widget.get_data()
        return {
            "oznameni_datum": oznameni.get("oznameni_datum"),
            "oznameni_cas": oznameni.get("oznameni_cas") or "",
        }

    def _sync_casova_osa_started_at(self) -> None:
        self.casova_osa_widget.set_started_at(self.started_at_edit.get_date())

    def _sync_casova_osa_oznameni(self) -> None:
        self.casova_osa_widget.set_oznameni_context(**self._casova_osa_oznameni_context())

    def _casova_osa_zajisteni_context(self) -> dict:
        widget = self.zajisteni_dukazu_widget
        return {
            "datum": widget.dukazy_datum.get_date(),
            "cas": widget.dukazy_cas.text().strip(),
            "datum_fotek": widget.dukazy_datum_fotek.get_date(),
            "cas_fotek": widget.dukazy_cas_fotek.text().strip(),
        }

    def _sync_casova_osa_zajisteni(self) -> None:
        self.casova_osa_widget.set_zajisteni_context(**self._casova_osa_zajisteni_context())

    def _svedci_json_for_load(self, investigation) -> str:
        raw = getattr(investigation, "svedci_json", "") or ""
        if raw.strip():
            return raw

        witness_keys = (
            "pocet_svedku",
            "svedci",
            "svedci_oddeleni",
            "vyjadreni_obsahuje_udaje",
            "vyjadreni_vracena",
            "rozhovor_po_vyjadreni",
        )
        try:
            zajisteni_data = json.loads(getattr(investigation, "zajisteni_dukazu_json", "") or "{}")
        except Exception:
            zajisteni_data = {}

        migrated = {key: zajisteni_data[key] for key in witness_keys if key in zajisteni_data}
        if not migrated:
            return raw
        return json.dumps(migrated, ensure_ascii=False)

    def _current_source_type(self) -> str:
        return self.source_type_combo.currentData() or DEFAULT_SOURCE_TYPE

    def _source_type_label(self) -> str:
        return SOURCE_TYPE_LABELS.get(self._current_source_type(), self._current_source_type())

    def _source_record_label(self) -> str:
        label = self.source_selector.current_source_label()
        if label:
            return label
        if self.investigation is not None:
            return (self.investigation.source_label or "").strip()
        return ""

    def _has_source_binding(self) -> bool:
        if self._current_source_type() == SOURCE_TYPE_MANUAL:
            return False

        if self.source_selector.has_binding():
            return True
        if self.investigation is None:
            return False
        source_type = self._current_source_type()
        if source_type in (SOURCE_TYPE_ACCIDENT, SOURCE_TYPE_AUDIT, SOURCE_TYPE_CONTROL):
            return isinstance(self.investigation.source_id, int) and self.investigation.source_id > 0
        return bool((self.investigation.source_label or "").strip())

    def _can_open_source_record(self) -> bool:
        source_type = self._current_source_type()
        entity_type = self._SOURCE_ENTITY_TYPES.get(source_type)
        source_id = self._current_source_id()
        if entity_type is None or source_id is None:
            return False
        return source_navigator.can_open(entity_type, source_id)

    def _update_source_panel(self) -> None:
        if not self._has_source_binding():
            self.source_panel.setVisible(False)
            return

        source_type = self._current_source_type()
        self.source_panel.set_content(
            self._source_type_label(),
            self._source_record_label(),
            can_open=self._can_open_source_record(),
            open_button_text=self._OPEN_BUTTON_LABELS.get(source_type, "Otevřít"),
        )

    def _open_source_record(self) -> None:
        source_type = self._current_source_type()
        entity_type = self._SOURCE_ENTITY_TYPES.get(source_type)
        source_id = self._current_source_id()
        if entity_type is None or source_id is None:
            return

        if entity_type == ENTITY_ACCIDENT:
            opened = source_navigator.open(
                entity_type,
                source_id,
                accident_target=ACCIDENT_OPEN_RECORD,
            )
        else:
            opened = source_navigator.open(entity_type, source_id)

        if not opened:
            QMessageBox.warning(
                self,
                "Navigace",
                "Zdrojový záznam se nepodařilo otevřít.",
            )

    def _open_investigation_check(self) -> None:
        from moduly.vysetrovani_mu.ui.mu_investigation_check_dialog import MuInvestigationCheckDialog

        MuInvestigationCheckDialog(self, snapshot=self.build_check_snapshot()).exec()

    def build_check_snapshot(self) -> dict:
        data = self.get_data()
        context = resolve_mu_source_context(
            self._current_source_type(),
            self._current_source_id(),
            self._current_source_label(),
            self.investigation.number if self.investigation is not None else "",
        )

        investigation_id = self.investigation.id if self.investigation is not None else None
        findings = []
        if investigation_id is not None:
            findings = finding_service.get_for_entity(ENTITY_MU_INVESTIGATION, investigation_id)

        try:
            causes = json.loads(self.findings_widget.get_ishikawa_json() or "[]")
        except Exception:
            causes = []

        def _load_json(raw: str) -> dict:
            try:
                return json.loads(raw or "{}")
            except Exception:
                return {}

        oznameni_keys = (
            "oznameni_kdo",
            "oznameni_komu",
            "oznameni_datum",
            "oznameni_cas",
            "oznameni_bezodkladne",
            "oznameni_duvod_pozde",
            "oznameni_popis",
            "opatreni_prvni_pomoc",
            "opatreni_zzs",
            "opatreni_policie",
            "opatreni_hzs",
            "opatreni_zastavena_cinnost",
            "opatreni_zajisteno_misto",
            "opatreni_zabraneno_manipulaci",
            "opatreni_informovan_nadrizeny",
            "opatreni_informovan_bozp",
            "oznameni_bozp_datum",
            "oznameni_bozp_cas",
            "opatreni_informovany_dalsi",
            "dalsi_postup",
            "dalsi_postup_jiny",
        )

        return {
            "investigation_id": investigation_id,
            "investigation_number": self.investigation.number if self.investigation is not None else "",
            "status": data.get("status"),
            "event_character": data.get("event_character"),
            "source_type": data.get("source_type"),
            "source_id": data.get("source_id"),
            "source_label": data.get("source_label"),
            "started_at": data.get("started_at"),
            "lead_thp_worker_id": data.get("lead_thp_worker_id"),
            "lead_thp_worker_name": data.get("lead_thp_worker_name"),
            "conclusion": data.get("conclusion"),
            "event_datum": context.event_datum,
            "event_cas": context.event_cas,
            "oznameni": {key: data.get(key) for key in oznameni_keys},
            "zajisteni": _load_json(data.get("zajisteni_dukazu_json", "")),
            "svedci": _load_json(data.get("svedci_json", "")),
            "casova_osa": _load_json(data.get("casova_osa_json", "")),
            "zaver": _load_json(data.get("zaver_json", "")),
            "causes": causes if isinstance(causes, list) else [],
            "findings": findings,
        }

    def get_data(self) -> dict:
        worker = self.lead_thp_worker_selector.current_person()

        return {
            "title": self.title_edit.text().strip(),
            "event_character": self.event_character_combo.currentText(),
            "source_type": self._current_source_type(),
            "source_id": self._current_source_id(),
            "source_label": self._current_source_label(),
            "started_at": self.started_at_edit.get_date(),
            "status": self.status_combo.currentText(),
            "lead_thp_worker_id": self.lead_thp_worker_selector.current_person_id(),
            "lead_thp_worker_name": worker.display_name if worker is not None else self.lead_thp_worker_selector.currentText().strip(),
            "short_description": self.short_description_edit.toPlainText().strip(),
            "conclusion": self.zaver_widget.get_conclusion(),
            "ohledani_mista_json": self.ohledani_mista_widget.get_json(),
            "zajisteni_dukazu_json": self.zajisteni_dukazu_widget.get_json(),
            "svedci_json": self.svedci_widget.get_json(),
            "casova_osa_json": self.casova_osa_widget.get_json(),
            "dodrzovani_predpisu_json": self.dodrzovani_predpisu_widget.get_json(),
            "kontrola_souladu_json": self.kontrola_souladu_widget.get_json(),
            "zaver_json": self.zaver_widget.get_json(),
            "ishikawa_json": self.findings_widget.get_ishikawa_json(),
            **self.oznameni_widget.get_data(),
        }

    def exec(self) -> int:
        self.showMaximized()
        return super().exec()
