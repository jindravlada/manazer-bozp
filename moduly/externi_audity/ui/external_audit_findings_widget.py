"""Záložka Zjištění externího auditu — Neshody / PKZ / Silné stránky (EA-2)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    typed_date,
    typed_text,
)
from moduly.externi_audity.constants import (
    EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS,
    EXTERNAL_AUDIT_FINDING_STATUS_LABELS,
    EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
    EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
    EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
    EXTERNAL_AUDIT_FINDING_TYPE_LABELS,
    EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
    EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
    EXTERNAL_AUDIT_TYPE_LABELS,
    format_display_date,
)
from moduly.externi_audity.sluzby.external_audit_draft import (
    ExternalAuditDraft,
    FindingDraft,
    new_client_key,
)
from moduly.externi_audity.sluzby.external_audit_service import (
    ExternalAuditError,
    external_audit_service,
)
from moduly.externi_audity.ui.external_audit_finding_dialog import (
    ExternalAuditFindingDialog,
)
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.ui.task_dialog import TaskDialog

FILTER_ALL = "__all__"
TITLE_FINDINGS = "Zjištění"
TASK_TITLE_MAX = 80


def _short_text(value: str, limit: int = TASK_TITLE_MAX) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _task_title_prefix(finding_type: str) -> str:
    if finding_type == EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY:
        return "Externí audit – neshoda"
    return "Externí audit – PKZ"


def _task_description(draft: ExternalAuditDraft, finding: FindingDraft) -> str:
    audit_type = EXTERNAL_AUDIT_TYPE_LABELS.get(
        draft.audit_type, draft.audit_type or "—"
    )
    org = str(draft.organization_name or "").strip() or "—"
    return (
        f"Typ auditu: {audit_type}\n"
        f"Externí organizace: {org}\n\n"
        f"Zjištění:\n{finding.description.strip()}"
    )


class _FindingTypePanel(QWidget):
    """Jeden pohled (Neshody / PKZ / Silné stránky)."""

    def __init__(
        self,
        parent: QWidget,
        *,
        finding_type: str,
        get_draft: Callable[[], ExternalAuditDraft],
        ensure_saved: Callable[[], bool],
        mark_dirty: Callable[[], None],
    ):
        super().__init__(parent)
        self._finding_type = finding_type
        self._is_strength = finding_type == EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH
        self._get_draft = get_draft
        self._ensure_saved = ensure_saved
        self._mark_dirty = mark_dirty
        self._visible_keys: list[str] = []
        self._task_ids: list[int] = []

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.edit_btn = QPushButton("Upravit")
        self.remove_btn = QPushButton("Odebrat")
        for button in (self.add_btn, self.edit_btn, self.remove_btn):
            button.setAutoDefault(False)
            toolbar.addWidget(button)

        if not self._is_strength:
            toolbar.addWidget(QLabel("Stav:"))
            self.status_filter = QComboBox()
            self.status_filter.addItem("Vše", FILTER_ALL)
            for value in (
                EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
                EXTERNAL_AUDIT_FINDING_STATUS_IN_PROGRESS,
                EXTERNAL_AUDIT_FINDING_STATUS_RESOLVED,
            ):
                self.status_filter.addItem(
                    EXTERNAL_AUDIT_FINDING_STATUS_LABELS[value], value
                )
            toolbar.addWidget(self.status_filter)
        else:
            self.status_filter = None

        toolbar.addStretch(1)
        self.count_label = QLabel("Zobrazeno: 0 / 0")
        toolbar.addWidget(self.count_label)
        layout.addLayout(toolbar)

        if self._is_strength:
            self.table = QTableWidget(0, 1)
            self.table.setHorizontalHeaderLabels(["Text silné stránky"])
        else:
            self.table = QTableWidget(0, 5)
            self.table.setHorizontalHeaderLabels(
                [
                    "Text zjištění",
                    "Stav",
                    "Termín vypořádání",
                    "Datum vypořádání",
                    "Úkoly",
                ]
            )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self.edit_selected)
        self.table.itemSelectionChanged.connect(self._on_finding_selection_changed)
        enable_typed_sorting(self.table)
        layout.addWidget(self.table, 1)

        if not self._is_strength:
            tasks_box = QVBoxLayout()
            tasks_toolbar = QHBoxLayout()
            self.new_task_btn = QPushButton("Nový úkol")
            self.open_task_btn = QPushButton("Otevřít úkol")
            self.refresh_tasks_btn = QPushButton("Obnovit")
            for button in (
                self.new_task_btn,
                self.open_task_btn,
                self.refresh_tasks_btn,
            ):
                button.setAutoDefault(False)
                tasks_toolbar.addWidget(button)
            tasks_toolbar.addStretch(1)
            tasks_box.addLayout(tasks_toolbar)

            self.tasks_table = QTableWidget(0, 5)
            self.tasks_table.setHorizontalHeaderLabels(
                ["Název", "Termín", "Stav", "Odpovídá", "Kontrolní termín"]
            )
            self.tasks_table.setSelectionBehavior(
                QTableWidget.SelectionBehavior.SelectRows
            )
            self.tasks_table.setSelectionMode(
                QTableWidget.SelectionMode.SingleSelection
            )
            self.tasks_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self.tasks_table.verticalHeader().setVisible(False)
            self.tasks_table.itemSelectionChanged.connect(self._refresh_task_actions)
            self.tasks_table.doubleClicked.connect(self.open_selected_task)
            enable_typed_sorting(self.tasks_table)
            tasks_box.addWidget(self.tasks_table, 1)
            layout.addLayout(tasks_box, 1)

            self.new_task_btn.clicked.connect(self.create_task)
            self.open_task_btn.clicked.connect(self.open_selected_task)
            self.refresh_tasks_btn.clicked.connect(self.refresh_tasks)
        else:
            self.new_task_btn = None
            self.open_task_btn = None
            self.refresh_tasks_btn = None
            self.tasks_table = None

        self.add_btn.clicked.connect(self.add_finding)
        self.edit_btn.clicked.connect(self.edit_selected)
        self.remove_btn.clicked.connect(self.remove_selected)
        if self.status_filter is not None:
            self.status_filter.currentIndexChanged.connect(self.refresh)

        self._refresh_actions()

    def refresh(self) -> None:
        draft = self._get_draft()
        items = draft.findings_for_type(self._finding_type)
        items = sorted(items, key=lambda item: (item.display_order, item.client_key))
        status_filter = (
            self.status_filter.currentData()
            if self.status_filter is not None
            else FILTER_ALL
        )
        visible = [
            item
            for item in items
            if status_filter == FILTER_ALL or item.status == status_filter
        ]
        self._visible_keys = [item.client_key for item in visible]
        self.count_label.setText(f"Zobrazeno: {len(visible)} / {len(items)}")

        self.table.setRowCount(len(visible))
        for row, item in enumerate(visible):
            stable = int(item.db_id) if item.db_id is not None else (row + 1) * -1
            if self._is_strength:
                cells = [
                    create_typed_item(
                        item.description,
                        typed_text(item.description),
                        stable_id=stable,
                    )
                ]
            else:
                status_label = EXTERNAL_AUDIT_FINDING_STATUS_LABELS.get(
                    item.status, item.status
                )
                task_hint = (
                    f"{len(item.linked_task_ids)}×"
                    if item.linked_task_ids
                    else "—"
                )
                cells = [
                    create_typed_item(
                        item.description,
                        typed_text(item.description),
                        stable_id=stable,
                    ),
                    create_typed_item(
                        status_label, typed_text(status_label), stable_id=stable
                    ),
                    create_typed_item(
                        format_display_date(item.due_date),
                        typed_date(item.due_date),
                        stable_id=stable,
                    ),
                    create_typed_item(
                        format_display_date(item.resolved_at),
                        typed_date(
                            item.resolved_at.date()
                            if item.resolved_at is not None
                            else None
                        ),
                        stable_id=stable,
                    ),
                    create_typed_item(
                        task_hint, typed_text(task_hint), stable_id=stable
                    ),
                ]
            for col, cell in enumerate(cells):
                if col == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, item.client_key)
                self.table.setItem(row, col, cell)
        self.table.resizeColumnsToContents()
        self._refresh_actions()
        if not self._is_strength:
            self.refresh_tasks()

    def selected_key(self) -> str | None:
        rows = self.table.selectionModel().selectedRows()
        if len(rows) != 1:
            return None
        item = self.table.item(rows[0].row(), 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return str(value) if value is not None else None

    def selected_finding(self) -> FindingDraft | None:
        key = self.selected_key()
        if key is None:
            return None
        return self._get_draft().finding_by_key(key)

    def add_finding(self) -> None:
        title = f"Nová {EXTERNAL_AUDIT_FINDING_TYPE_LABELS[self._finding_type].lower()}"
        if self._finding_type == EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH:
            title = "Nová silná stránka"
        elif self._finding_type == EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT:
            title = "Nová PKZ"
        elif self._finding_type == EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY:
            title = "Nová neshoda"

        dialog = ExternalAuditFindingDialog(
            self,
            finding_type=self._finding_type,
            title=title,
            status=(
                None
                if self._is_strength
                else EXTERNAL_AUDIT_FINDING_STATUS_OPEN
            ),
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        if not data:
            return
        draft = self._get_draft()
        order = (len(draft.findings_for_type(self._finding_type)) + 1) * 10
        draft.findings.append(
            FindingDraft(
                client_key=new_client_key(),
                finding_type=data["finding_type"],
                description=data["description"],
                status=data["status"],
                due_date=data["due_date"],
                resolution_text=data["resolution_text"],
                resolved_at=data["resolved_at"],
                display_order=order,
            )
        )
        self._mark_dirty()
        self.refresh()

    def edit_selected(self) -> None:
        finding = self.selected_finding()
        if finding is None:
            return
        dialog = ExternalAuditFindingDialog(
            self,
            finding_type=finding.finding_type,
            title=f"Upravit — {EXTERNAL_AUDIT_FINDING_TYPE_LABELS.get(finding.finding_type, 'zjištění')}",
            description=finding.description,
            status=finding.status,
            due_date=finding.due_date,
            resolution_text=finding.resolution_text,
            resolved_at=finding.resolved_at,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        data = dialog.get_data()
        if not data:
            return
        finding.description = data["description"]
        finding.status = data["status"]
        finding.due_date = data["due_date"]
        finding.resolution_text = data["resolution_text"]
        finding.resolved_at = data["resolved_at"]
        self._mark_dirty()
        self.refresh()

    def remove_selected(self) -> None:
        finding = self.selected_finding()
        if finding is None:
            return
        if finding.db_id is not None:
            QMessageBox.information(
                self,
                TITLE_FINDINGS,
                "Uložené zjištění nelze smazat — jde o historickou evidenci.",
            )
            return
        draft = self._get_draft()
        draft.findings = [
            item for item in draft.findings if item.client_key != finding.client_key
        ]
        self._mark_dirty()
        self.refresh()

    def create_task(self) -> None:
        if self._is_strength:
            return
        finding = self.selected_finding()
        if finding is None:
            return
        finding_type = finding.finding_type
        description = finding.description
        previous_db_id = finding.db_id

        if not self._ensure_saved():
            return

        draft = self._get_draft()
        finding = None
        if previous_db_id is not None:
            finding = next(
                (
                    item
                    for item in draft.findings
                    if item.db_id == previous_db_id
                ),
                None,
            )
        if finding is None:
            matches = [
                item
                for item in draft.findings_for_type(finding_type)
                if item.description == description and item.db_id is not None
            ]
            finding = matches[-1] if matches else None

        if finding is None or finding.db_id is None or draft.audit_id is None:
            QMessageBox.information(
                self,
                TITLE_FINDINGS,
                "Nejdříve uložte externí audit (Uložit), aby bylo možné vytvořit úkol.",
            )
            return

        workplace_id = None
        workplace_ids = {
            int(visit.workplace_id)
            for visit in draft.visits
            if visit.workplace_id
        }
        if len(workplace_ids) == 1:
            workplace_id = next(iter(workplace_ids))

        title = f"{_task_title_prefix(finding.finding_type)}: {_short_text(finding.description)}"
        task_description = _task_description(draft, finding)
        finding_db_id = int(finding.db_id)

        def _create_task(data: dict):
            # TaskDialog.get_data() vrací description="" — předvyplněný text
            # musí jít sem, nikoli do create_kwargs (duplicitní kwargs).
            payload = dict(data)
            payload["description"] = task_description
            try:
                return task_service.create_task(**payload)
            except Exception as exc:  # noqa: BLE001
                QMessageBox.warning(
                    self,
                    TITLE_FINDINGS,
                    f"Úkol se nepodařilo vytvořit.\n\n{exc}",
                )
                return None

        dialog = TaskDialog(self, create_factory=_create_task)
        dialog.title_edit.setPlainText(title)
        if workplace_id is not None:
            dialog.workplace_selector.set_workplace_id(workplace_id)
        dialog._capture_baseline()
        dialog.exec()

        task = dialog.task
        if task is None or getattr(task, "id", None) is None:
            return
        task_id = int(task.id)
        # Vazba po prvním úspěšném vytvoření — nezávisí na Accepted
        # (Uložit → Zavřít musí také navázat).
        already = set(
            external_audit_service.list_finding_task_ids(finding_db_id)
        )
        if task_id not in already:
            try:
                external_audit_service.link_task(finding_db_id, task_id)
            except ExternalAuditError as exc:
                QMessageBox.warning(self, TITLE_FINDINGS, str(exc))
                return
        # Obnovit finding v aktuálním draftu (po případném reloadu)
        current = next(
            (
                item
                for item in self._get_draft().findings
                if item.db_id == finding_db_id
            ),
            None,
        )
        if current is not None and task_id not in current.linked_task_ids:
            current.linked_task_ids.append(task_id)
        self.refresh()

    def open_selected_task(self) -> None:
        task_id = self._selected_task_id()
        if task_id is None:
            return
        task = task_service.get_task_by_id(task_id)
        if task is None:
            QMessageBox.warning(self, TITLE_FINDINGS, "Úkol nebyl nalezen.")
            self.refresh_tasks()
            return
        dialog = TaskDialog(self, task=task)
        dialog.exec()
        self.refresh_tasks()

    def refresh_tasks(self) -> None:
        if self.tasks_table is None:
            return
        finding = self.selected_finding()
        self.tasks_table.setRowCount(0)
        self._task_ids = []
        if finding is None or finding.db_id is None:
            self._refresh_task_actions()
            return

        # Batch přes službu (i pro jedno ID)
        by_finding = external_audit_service.list_tasks_for_findings([int(finding.db_id)])
        tasks = by_finding.get(int(finding.db_id), [])
        finding.linked_task_ids = [int(task.id) for task in tasks]
        self._task_ids = list(finding.linked_task_ids)
        self.tasks_table.setRowCount(len(tasks))
        for row, task in enumerate(tasks):
            status = str(getattr(task, "computed_status", None) or task.status or "")
            due = getattr(task, "due_date", None)
            check_due = getattr(task, "check_due_date", None)
            responsible = str(getattr(task, "responsible_person", None) or "—")
            cells = [
                create_typed_item(
                    task.title or "",
                    typed_text(task.title or ""),
                    stable_id=task.id,
                ),
                create_typed_item(
                    format_display_date(due), typed_date(due), stable_id=task.id
                ),
                create_typed_item(status, typed_text(status), stable_id=task.id),
                create_typed_item(
                    responsible, typed_text(responsible), stable_id=task.id
                ),
                create_typed_item(
                    format_display_date(check_due),
                    typed_date(check_due),
                    stable_id=task.id,
                ),
            ]
            for col, cell in enumerate(cells):
                if col == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, int(task.id))
                self.tasks_table.setItem(row, col, cell)
        self.tasks_table.resizeColumnsToContents()
        # Obnovit sloupec „Úkoly“ v seznamu zjištění
        key = finding.client_key
        if key in self._visible_keys:
            row = self._visible_keys.index(key)
            hint = f"{len(finding.linked_task_ids)}×" if finding.linked_task_ids else "—"
            stable = int(finding.db_id) if finding.db_id is not None else (row + 1) * -1
            cell = create_typed_item(hint, typed_text(hint), stable_id=stable)
            cell.setData(Qt.ItemDataRole.UserRole, key)
            self.table.setItem(row, 4, cell)
        self._refresh_task_actions()

    def _selected_task_id(self) -> int | None:
        if self.tasks_table is None:
            return None
        rows = self.tasks_table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        if row < 0 or row >= len(self._task_ids):
            return None
        return self._task_ids[row]

    def _on_finding_selection_changed(self) -> None:
        self._refresh_actions()
        if not self._is_strength:
            self.refresh_tasks()

    def _refresh_actions(self) -> None:
        finding = self.selected_finding()
        has_selection = finding is not None
        self.edit_btn.setEnabled(has_selection)
        self.remove_btn.setEnabled(
            has_selection and finding is not None and finding.db_id is None
        )
        if self.new_task_btn is not None:
            can_task = (
                has_selection
                and finding is not None
                and finding.db_id is not None
                and self._get_draft().audit_id is not None
            )
            self.new_task_btn.setEnabled(can_task)
        self._refresh_task_actions()

    def _refresh_task_actions(self) -> None:
        if self.open_task_btn is None or self.refresh_tasks_btn is None:
            return
        self.open_task_btn.setEnabled(self._selected_task_id() is not None)
        self.refresh_tasks_btn.setEnabled(True)


class ExternalAuditFindingsWidget(QWidget):
    def __init__(
        self,
        parent=None,
        *,
        get_draft: Callable[[], ExternalAuditDraft],
        ensure_saved: Callable[[], bool],
        mark_dirty: Callable[[], None] | None = None,
    ):
        super().__init__(parent)
        self._get_draft = get_draft
        self._ensure_saved = ensure_saved
        self._mark_dirty = mark_dirty or (lambda: None)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.subtabs = QTabWidget()
        self.nc_panel = _FindingTypePanel(
            self,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            get_draft=get_draft,
            ensure_saved=ensure_saved,
            mark_dirty=self._mark_dirty,
        )
        self.pkz_panel = _FindingTypePanel(
            self,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
            get_draft=get_draft,
            ensure_saved=ensure_saved,
            mark_dirty=self._mark_dirty,
        )
        self.strength_panel = _FindingTypePanel(
            self,
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
            get_draft=get_draft,
            ensure_saved=ensure_saved,
            mark_dirty=self._mark_dirty,
        )
        self.subtabs.addTab(self.nc_panel, "Neshody")
        self.subtabs.addTab(self.pkz_panel, "PKZ")
        self.subtabs.addTab(self.strength_panel, "Silné stránky")
        layout.addWidget(self.subtabs)

    def refresh(self) -> None:
        self.nc_panel.refresh()
        self.pkz_panel.refresh()
        self.strength_panel.refresh()
