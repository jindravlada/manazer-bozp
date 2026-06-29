from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

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
    SOURCE_TYPE_LABELS,
    SOURCE_TYPES,
)
from moduly.vysetrovani_mu.ui.mu_findings_widget import MuFindingsWidget


class MuInvestigationDialog(QDialog):
    def __init__(self, parent=None, investigation=None):
        super().__init__(parent)

        self.investigation = investigation

        self.setWindowTitle("Vyšetřování mimořádné události")
        self.resize(860, 680)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._basic_tab(), "Základní údaje")
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
            self.number_label.setText(investigation.number or "—")
            self.title_edit.setText(investigation.title or "")
            self._set_event_character(investigation.event_character or DEFAULT_EVENT_CHARACTER)
            self._set_source_type(investigation.source_type or DEFAULT_SOURCE_TYPE)
            self.source_label_edit.setText(investigation.source_label or "")
            self.started_at_edit.set_date_value(investigation.started_at)
            self.status_combo.setCurrentText(investigation.status or DEFAULT_MU_STATUS)
            self.lead_thp_worker_selector.set_person_id(investigation.lead_thp_worker_id)
            self.short_description_edit.setPlainText(investigation.short_description or "")
            self.conclusion_edit.setPlainText(investigation.conclusion or "")

    def _basic_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        self.number_label = QLabel("—")
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Název vyšetřování")

        self.event_character_combo = QComboBox()
        self.event_character_combo.addItems(EVENT_CHARACTERS)

        self.source_type_combo = QComboBox()
        for source_type in SOURCE_TYPES:
            self.source_type_combo.addItem(SOURCE_TYPE_LABELS[source_type], source_type)

        self.source_label_edit = QLineEdit()
        self.source_label_edit.setPlaceholderText("Textový popis zdroje / podnětu")

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

        form.addRow("Číslo:", self.number_label)
        form.addRow("Název:", self.title_edit)
        form.addRow("Charakter události:", self.event_character_combo)
        form.addRow("Zdroj – typ:", self.source_type_combo)
        form.addRow("Zdroj – text:", self.source_label_edit)
        form.addRow("Datum zahájení:", self.started_at_edit)
        form.addRow("Stav:", self.status_combo)
        form.addRow("Vedoucí šetření:", self.lead_thp_worker_selector)
        form.addRow("Stručný popis:", self.short_description_edit)

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
            self.source_type_combo.setCurrentIndex(index)

    def get_data(self) -> dict:
        worker = self.lead_thp_worker_selector.current_person()

        return {
            "title": self.title_edit.text().strip(),
            "event_character": self.event_character_combo.currentText(),
            "source_type": self.source_type_combo.currentData() or DEFAULT_SOURCE_TYPE,
            "source_id": self.investigation.source_id if self.investigation is not None else None,
            "source_label": self.source_label_edit.text().strip(),
            "started_at": self.started_at_edit.get_date(),
            "status": self.status_combo.currentText(),
            "lead_thp_worker_id": self.lead_thp_worker_selector.current_person_id(),
            "lead_thp_worker_name": worker.display_name if worker is not None else self.lead_thp_worker_selector.currentText().strip(),
            "short_description": self.short_description_edit.toPlainText().strip(),
            "conclusion": self.conclusion_edit.toPlainText().strip(),
        }
