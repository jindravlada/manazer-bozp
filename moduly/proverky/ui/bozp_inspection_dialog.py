from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.nullable_date_edit import NullableDateEdit
from core.widgets.workplace_selector import WorkplaceSelector
from moduly.proverky.constants import (
    DEFAULT_INSPECTION_STATUS,
    VALID_INSPECTION_STATUSES,
)


class BozpInspectionDialog(QDialog):
    """Kostra dialogu prověrky BOZP — bez ukládání a business logiky."""

    def __init__(self, parent=None, inspection=None):
        super().__init__(parent)

        self.inspection = inspection

        self.setWindowTitle("Prověrka BOZP")
        self.resize(860, 720)

        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._spis_tab(), "Spis")
        self.tabs.addTab(self._placeholder_tab("Komise"), "Komise")
        self.tabs.addTab(self._placeholder_tab("Průběh prověrky"), "Průběh prověrky")
        self.tabs.addTab(self._placeholder_tab("Zjištění"), "Zjištění")
        self.tabs.addTab(self._placeholder_tab("Úkoly"), "Úkoly")
        self.tabs.addTab(self._placeholder_tab("Přílohy"), "Přílohy")
        self.tabs.addTab(self._placeholder_tab("Závěr"), "Závěr")
        layout.addWidget(self.tabs)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._init_defaults()

    def _spis_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        self.number_label = QLabel("—")

        self.inspection_date_edit = NullableDateEdit()

        self.workplace_selector = WorkplaceSelector()

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Např. Veřejná prověrka BOZP/PO")

        self.status_combo = QComboBox()
        self.status_combo.addItems(sorted(VALID_INSPECTION_STATUSES))

        self.summary_edit = QTextEdit()
        self.summary_edit.setPlaceholderText("Stručný popis nebo poznámka ke spisu")
        self.summary_edit.setMinimumHeight(90)

        form.addRow("Číslo:", self.number_label)
        form.addRow("Datum prověrky:", self.inspection_date_edit)
        form.addRow("Pracoviště:", self.workplace_selector)
        form.addRow("Název:", self.title_edit)
        form.addRow("Stav:", self.status_combo)
        form.addRow("Poznámka ke spisu:", self.summary_edit)

        return tab

    def _placeholder_tab(self, title: str) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info = QLabel(
            f"Záložka „{title}“ bude doplněna v další fázi vývoje.\n"
            "Modul zatím pracuje pouze jako kostra bez ukládání dat."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch()
        return tab

    def _init_defaults(self) -> None:
        self.status_combo.setCurrentText(DEFAULT_INSPECTION_STATUS)
        self.inspection_date_edit.set_date_value(date.today())

        if self.inspection is None:
            return

        self.number_label.setText(getattr(self.inspection, "number", None) or "—")
        title = getattr(self.inspection, "title", None)
        if title:
            self.title_edit.setText(title)
        status = getattr(self.inspection, "status", None)
        if status:
            self.status_combo.setCurrentText(status)
        summary = getattr(self.inspection, "summary", None)
        if summary:
            self.summary_edit.setPlainText(summary)
