from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.navigation.source_navigator import source_navigator
from core.shared.constants import ENTITY_ACCIDENT, ENTITY_AUDITY
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.vysetrovani_mu.constants import (
    DEFAULT_EVENT_CHARACTER,
    DEFAULT_MU_STATUS,
    DEFAULT_SOURCE_TYPE,
    EVENT_CHARACTERS,
    MU_STATUS_DOKONCENO,
    MU_STATUS_ODLOZENO,
    MU_STATUS_PROBIHA,
    SOURCE_TYPE_ACCIDENT,
    SOURCE_TYPE_AUDIT,
    SOURCE_TYPE_CONTROL,
    SOURCE_TYPE_LABELS,
    SOURCE_TYPES,
)
from moduly.vysetrovani_mu.ui.mu_findings_widget import MuFindingsWidget
from moduly.vysetrovani_mu.ui.mu_investigation_source_panel import MuInvestigationSourcePanel
from moduly.vysetrovani_mu.ui.mu_source_selector_widget import MuSourceSelectorWidget


class MuInvestigationDialog(QDialog):
    _SOURCE_ENTITY_TYPES = {
        SOURCE_TYPE_ACCIDENT: ENTITY_ACCIDENT,
        SOURCE_TYPE_AUDIT: ENTITY_AUDITY,
    }

    def __init__(self, parent=None, investigation=None):
        super().__init__(parent)

        self.investigation = investigation

        self.setWindowTitle("Vyšetřování mimořádné události")
        self.resize(860, 720)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._basic_tab(), "Spis")
        self.findings_widget = MuFindingsWidget()
        self.tabs.addTab(self.findings_widget, "Zjištění")
        self.tabs.addTab(self._conclusion_tab(), "Závěr")
        layout.addWidget(self.tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        investigation_id = investigation.id if investigation is not None else None
        self.findings_widget.set_investigation_id(investigation_id)

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
            self.conclusion_edit.setPlainText(investigation.conclusion or "")

        self._update_source_panel()

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

        self.source_type_combo = QComboBox()
        for source_type in SOURCE_TYPES:
            self.source_type_combo.addItem(SOURCE_TYPE_LABELS[source_type], source_type)
        self.source_type_combo.currentIndexChanged.connect(self._on_source_type_changed)

        self.source_selector = MuSourceSelectorWidget()
        self.source_selector.accident_combo.currentIndexChanged.connect(self._update_source_panel)
        self.source_selector.audit_combo.currentIndexChanged.connect(self._update_source_panel)
        self.source_selector.control_combo.currentIndexChanged.connect(self._update_source_panel)
        self.source_selector.text_edit.textChanged.connect(self._update_source_panel)

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

    def _conclusion_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.conclusion_edit = QTextEdit()
        self.conclusion_edit.setPlaceholderText("Závěr vyšetřování")
        self.conclusion_edit.setMinimumHeight(220)

        layout.addWidget(self.conclusion_edit)
        return tab

    def _set_event_character(self, value: str) -> None:
        index = self.event_character_combo.findText(value)
        if index >= 0:
            self.event_character_combo.setCurrentIndex(index)

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

    def _current_source_type(self) -> str:
        return self.source_type_combo.currentData() or DEFAULT_SOURCE_TYPE

    def _source_type_label(self) -> str:
        return SOURCE_TYPE_LABELS.get(self._current_source_type(), self._current_source_type())

    def _source_record_label(self) -> str:
        return self.source_selector.current_source_label()

    def _can_open_source_record(self) -> bool:
        source_type = self._current_source_type()
        entity_type = self._SOURCE_ENTITY_TYPES.get(source_type)
        source_id = self.source_selector.current_source_id()
        if entity_type is None or source_id is None:
            return False
        return source_navigator.can_open(entity_type, source_id)

    def _update_source_panel(self) -> None:
        if not self.source_selector.has_binding():
            self.source_panel.setVisible(False)
            return

        self.source_panel.set_content(
            self._source_type_label(),
            self._source_record_label(),
            can_open=self._can_open_source_record(),
        )

    def _open_source_record(self) -> None:
        source_type = self._current_source_type()
        entity_type = self._SOURCE_ENTITY_TYPES.get(source_type)
        source_id = self.source_selector.current_source_id()
        if entity_type is None or source_id is None:
            return

        if not source_navigator.open(entity_type, source_id):
            QMessageBox.warning(
                self,
                "Navigace",
                "Zdrojový záznam se nepodařilo otevřít.",
            )

    def get_data(self) -> dict:
        worker = self.lead_thp_worker_selector.current_person()

        return {
            "title": self.title_edit.text().strip(),
            "event_character": self.event_character_combo.currentText(),
            "source_type": self._current_source_type(),
            "source_id": self.source_selector.current_source_id(),
            "source_label": self.source_selector.current_source_label(),
            "started_at": self.started_at_edit.get_date(),
            "status": self.status_combo.currentText(),
            "lead_thp_worker_id": self.lead_thp_worker_selector.current_person_id(),
            "lead_thp_worker_name": worker.display_name if worker is not None else self.lead_thp_worker_selector.currentText().strip(),
            "short_description": self.short_description_edit.toPlainText().strip(),
            "conclusion": self.conclusion_edit.toPlainText().strip(),
        }
