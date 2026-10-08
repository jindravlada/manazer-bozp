"""Dialog přehledů vypořádání zjištění z dokončených interních auditů."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from core.export import open_export_file
from core.shared.constants import SETTLEMENT_SOURCE_AUDITY
from core.shared.modely.finding_settlement_overview import FindingSettlementOverview
from core.shared.sluzby.finding_settlement_overview_service import (
    FindingSettlementOverviewError,
    finding_settlement_overview_service,
)
from core.widgets.date_edit import DateEdit
from core.widgets.dialog_utils import configure_close_push_button
from moduly.audity.constants import (
    MODULE_NAME,
    SETTLEMENT_OVERVIEW_DIALOG_TITLE,
)
from moduly.audity.sluzby.prehled_vyporadani_export_service import (
    PrehledVyporadaniExportError,
    PrehledVyporadaniItemView,
    PrehledVyporadaniView,
    format_audit_reference,
    format_overview_date,
    period_label_for,
    prehled_vyporadani_export_service,
    presented_date_problem,
    scope_warning,
)

_IMMUTABLE_CONFIRMATION = (
    "Přehled bude uložen jako neměnný historický snímek.\n"
    "Pozdější úpravy zjištění, úkolů ani auditů tento přehled nezmění."
)

DOCUMENT_EXPORT_TITLE = "Přehled vypořádání"


@dataclass(frozen=True)
class SettlementOverviewProfile:
    """Odlišnosti řady Auditů a řady Prověrek nad stejnými dialogy."""

    source_type: str
    module_name: str
    dialog_title: str
    record_column: str
    confirmation: str
    scope_warning: Callable[[int, int], str]
    export_service: object
    plain_reference: bool = False
    document_export_title: str = DOCUMENT_EXPORT_TITLE


AUDIT_SETTLEMENT_PROFILE = SettlementOverviewProfile(
    source_type=SETTLEMENT_SOURCE_AUDITY,
    module_name=MODULE_NAME,
    dialog_title=SETTLEMENT_OVERVIEW_DIALOG_TITLE,
    record_column="Audit",
    confirmation=_IMMUTABLE_CONFIRMATION,
    scope_warning=scope_warning,
    export_service=prehled_vyporadani_export_service,
)


class PrehledVyporadaniDialog(QDialog):
    def __init__(self, parent=None, *, profile: SettlementOverviewProfile | None = None):
        super().__init__(parent)
        self.profile = profile or AUDIT_SETTLEMENT_PROFILE
        self.setWindowTitle(self.profile.dialog_title)
        self.resize(980, 520)

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nový přehled")
        self.detail_btn = QPushButton("Zobrazit")
        self.export_btn = QPushButton("Exportovat")
        self.detail_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.detail_btn)
        toolbar.addWidget(self.export_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.empty_label = QLabel(
            "Zatím není uložen žádný přehled. "
            "První přehled bude Přehled č. 0 – výchozí stav."
        )
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            [
                "Číslo",
                "Datum předložení",
                "Období",
                "Počet zjištění",
                "Poznámka",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 140)
        self.table.setColumnWidth(2, 280)
        self.table.setColumnWidth(3, 130)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._refresh_actions)
        self.table.doubleClicked.connect(self.open_detail)
        layout.addWidget(self.table, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.close_btn = QPushButton()
        configure_close_push_button(self.close_btn)
        self.close_btn.clicked.connect(self.accept)
        footer.addWidget(self.close_btn)
        layout.addLayout(footer)

        self.new_btn.clicked.connect(self.open_create)
        self.detail_btn.clicked.connect(self.open_detail)
        self.export_btn.clicked.connect(self.export_selected)
        self._overviews: list[FindingSettlementOverview] = []
        self.refresh()

    def refresh(self) -> None:
        self._overviews = finding_settlement_overview_service.list_overviews(
            self.profile.source_type
        )
        self.table.setRowCount(len(self._overviews))
        for index, overview in enumerate(self._overviews):
            values = (
                str(overview.sequence_number),
                format_overview_date(overview.presented_at),
                period_label_for(overview),
                str(overview.total_count),
                str(overview.note or ""),
            )
            for column, text in enumerate(values):
                item = QTableWidgetItem(text)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, int(overview.id))
                self.table.setItem(index, column, item)
        self.empty_label.setVisible(not self._overviews)
        self.table.clearSelection()
        self._refresh_actions()

    def selected_overview_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if len(selected) != 1:
            return None
        item = self.table.item(selected[0].row(), 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return None if value is None else int(value)

    def open_create(self) -> None:
        previous = self._overviews[-1] if self._overviews else None
        dialog = PrehledVyporadaniCreateDialog(
            self,
            previous=previous,
            profile=self.profile,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def open_detail(self) -> None:
        overview_id = self.selected_overview_id()
        if overview_id is None:
            return
        dialog = PrehledVyporadaniDetailDialog(
            self,
            overview_id,
            profile=self.profile,
        )
        if dialog.load_error:
            QMessageBox.warning(self, self.profile.module_name, dialog.load_error)
            return
        dialog.exec()

    def export_selected(self) -> None:
        overview_id = self.selected_overview_id()
        if overview_id is None:
            return
        try:
            path = self.profile.export_service.generate(overview_id)
            open_export_file(path, title=self.profile.document_export_title)
        except PrehledVyporadaniExportError as exc:
            QMessageBox.warning(self, self.profile.module_name, str(exc))
        except Exception as exc:
            QMessageBox.warning(
                self,
                self.profile.module_name,
                f"Přehled se nepodařilo exportovat.\n\n{exc}",
            )

    def _refresh_actions(self) -> None:
        single = self.selected_overview_id() is not None
        self.detail_btn.setEnabled(single)
        self.export_btn.setEnabled(single)


class PrehledVyporadaniCreateDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        previous: FindingSettlementOverview | None = None,
        profile: SettlementOverviewProfile | None = None,
    ):
        super().__init__(parent)
        self.profile = profile or AUDIT_SETTLEMENT_PROFILE
        self.previous = previous
        self.created_id: int | None = None
        sequence = 0 if previous is None else int(previous.sequence_number) + 1
        self.sequence_number = sequence
        self.setWindowTitle("Nový přehled vypořádání")
        self.resize(560, 360)

        layout = QVBoxLayout(self)
        if sequence == 0:
            heading = "Přehled č. 0 – výchozí stav"
        else:
            heading = f"Přehled č. {sequence}"
        self.heading_label = QLabel(heading)
        self.heading_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.heading_label)

        form = QFormLayout()
        if previous is not None:
            self.previous_date_label = QLabel(
                format_overview_date(previous.presented_at)
            )
            form.addRow("Datum předchozího přehledu:", self.previous_date_label)
        else:
            self.previous_date_label = None
        self.date_edit = DateEdit()
        if previous is not None and previous.presented_at is not None:
            minimum = _qdate(previous.presented_at)
            self.date_edit.setMinimumDate(minimum)
            if self.date_edit.date() < minimum:
                self.date_edit.setDate(minimum)
        form.addRow("Datum předložení:", self.date_edit)
        self.period_label = QLabel("")
        form.addRow("Období:", self.period_label)
        layout.addLayout(form)

        self.note_edit = QTextEdit()
        self.note_edit.setPlaceholderText("Volitelná poznámka")
        self.note_edit.setMinimumHeight(80)
        layout.addWidget(self.note_edit)

        self.warning_label = QLabel("")
        self.warning_label.setWordWrap(True)
        layout.addWidget(self.warning_label)
        self.refresh_scope_warning()

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_btn = QPushButton("Zrušit")
        self.create_btn = QPushButton("Vytvořit")
        self.cancel_btn.clicked.connect(self.reject)
        self.create_btn.clicked.connect(self._save)
        buttons.addWidget(self.create_btn)
        buttons.addWidget(self.cancel_btn)
        layout.addLayout(buttons)

        self.date_edit.dateChanged.connect(self._update_period)
        self._update_period()

    def presented_date(self) -> date | None:
        value = self.date_edit.date()
        if not value.isValid():
            return None
        return date(value.year(), value.month(), value.day())

    def note_text(self) -> str:
        return self.note_edit.toPlainText().strip()

    def refresh_scope_warning(self) -> str:
        scope = finding_settlement_overview_service.completed_scope(
            self.profile.source_type
        )
        text = self.profile.scope_warning(
            scope.completed_record_count,
            scope.finding_count,
        )
        self.warning_label.setText(text)
        self.warning_label.setVisible(bool(text))
        return text

    def confirmation_message(self) -> str:
        warning = self.warning_label.text().strip()
        if warning:
            return f"{self.profile.confirmation}\n\n{warning}"
        return self.profile.confirmation

    def _update_period(self) -> None:
        presented = self.presented_date()
        if self.previous is None or self.previous.presented_at is None:
            self.period_label.setText(
                f"výchozí stav k {format_overview_date(presented)}"
            )
            return
        self.period_label.setText(
            f"{format_overview_date(self.previous.presented_at)} – "
            f"{format_overview_date(presented)}"
        )

    def _save(self) -> None:
        problem = presented_date_problem(
            self.presented_date(),
            None if self.previous is None else self.previous.presented_at,
        )
        if problem:
            QMessageBox.warning(self, self.profile.module_name, problem)
            return
        self.refresh_scope_warning()
        answer = QMessageBox.question(
            self,
            self.profile.module_name,
            self.confirmation_message(),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            created = finding_settlement_overview_service.create_overview(
                self.profile.source_type,
                presented_at=self.presented_date(),
                note=self.note_text(),
            )
        except FindingSettlementOverviewError as exc:
            QMessageBox.warning(self, self.profile.module_name, str(exc))
            return
        except Exception as exc:
            QMessageBox.warning(
                self,
                self.profile.module_name,
                "Přehled se nepodařilo vytvořit. Uložený seznam přehledů zůstal beze změny."
                f"\n\n{exc}",
            )
            return
        self.created_id = int(created.id)
        self.accept()


class PrehledVyporadaniDetailDialog(QDialog):
    def __init__(
        self,
        parent=None,
        overview_id: int = 0,
        *,
        profile: SettlementOverviewProfile | None = None,
    ):
        super().__init__(parent)
        self.profile = profile or AUDIT_SETTLEMENT_PROFILE
        self.load_error = ""
        self.view: PrehledVyporadaniView | None = None
        try:
            self.view = self.profile.export_service.load_view(int(overview_id))
        except PrehledVyporadaniExportError as exc:
            self.load_error = str(exc)
            self.setWindowTitle(self.profile.dialog_title)
            return

        view = self.view
        self.setWindowTitle(f"Přehled č. {view.sequence_number}")
        self.resize(980, 640)
        layout = QVBoxLayout(self)

        summary = QGroupBox("Souhrn uloženého snímku")
        form = QFormLayout(summary)
        self.number_label = QLabel(str(view.sequence_number))
        self.presented_label = QLabel(view.presented_label)
        self.period_label = QLabel(view.period_label)
        self.total_label = QLabel(str(view.total_count))
        self.settled_label = QLabel(str(view.settled_count))
        self.in_process_label = QLabel(str(view.in_process_count))
        self.open_label = QLabel(str(view.open_count))
        self.types_label = QLabel(_type_summary(view))
        self.types_label.setWordWrap(True)
        self.note_label = QLabel(view.note or "—")
        self.note_label.setWordWrap(True)
        form.addRow("Číslo přehledu:", self.number_label)
        form.addRow("Datum předložení:", self.presented_label)
        form.addRow("Období:", self.period_label)
        form.addRow("Celkový počet zjištění:", self.total_label)
        form.addRow("Vypořádaná:", self.settled_label)
        form.addRow("V procesu:", self.in_process_label)
        form.addRow("Otevřená:", self.open_label)
        form.addRow("Počty podle typů:", self.types_label)
        form.addRow("Poznámka:", self.note_label)
        layout.addWidget(summary)

        self.changes_box = QGroupBox("Změny proti předchozímu přehledu")
        changes = QFormLayout(self.changes_box)
        self.settled_since_label = QLabel(str(view.settled_since_count))
        self.unsettled_label = QLabel(str(view.unsettled_count))
        self.new_label = QLabel(str(view.new_count))
        self.reopened_label = QLabel(str(view.reopened_count))
        changes.addRow("Vypořádaná od posledního přehledu:", self.settled_since_label)
        changes.addRow("Dosud nevypořádaná:", self.unsettled_label)
        changes.addRow("Nová zjištění:", self.new_label)
        changes.addRow("Znovuotevřená zjištění:", self.reopened_label)
        self.changes_box.setVisible(view.shows_changes)
        layout.addWidget(self.changes_box)

        self.table = QTableWidget(len(view.items), 8)
        self.table.setHorizontalHeaderLabels(
            [
                self.profile.record_column,
                "Provoz",
                "Typ",
                "Stav",
                "Vypořádáno",
                "Popis",
                "Úkol",
                "Zařazení",
            ]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        for row, item in enumerate(view.items):
            values = (
                _record_reference(item, self.profile),
                item.workplace_name,
                item.finding_type_label,
                item.status_label,
                item.resolved_at_label,
                item.description_snapshot,
                item.task_label,
                item.categories,
            )
            for column, text in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(text))
        layout.addWidget(self.table, 1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        close_btn = QPushButton()
        configure_close_push_button(close_btn)
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        layout.addLayout(footer)


def _record_reference(
    item: PrehledVyporadaniItemView,
    profile: SettlementOverviewProfile,
) -> str:
    if profile.plain_reference:
        return format_audit_reference(item.source_number, item.source_year)
    return item.audit_label


def _type_summary(view: PrehledVyporadaniView) -> str:
    if not view.type_counts:
        return "—"
    return ", ".join(f"{label}: {count}" for label, count in view.type_counts)


def _qdate(value: date) -> QDate:
    return QDate(value.year, value.month, value.day)
