"""Záložka Úkoly – nevyhovující body k rozhodnutí + založené úkoly."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QPalette
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_empty,
    typed_int,
    typed_status,
    typed_text,
)
from moduly.rizeni_rizik.constants import (
    RISK_MEASURE_REVIEW_CREATE_TASK_LABEL,
    RISK_MEASURE_REVIEW_ITEM_RESOLUTION_LABELS,
    RISK_MEASURE_REVIEW_ITEM_RESOLUTION_MEASURE_REVISION,
    RISK_MEASURE_REVIEW_ITEM_RESOLUTION_TASK,
    RISK_MEASURE_REVIEW_ITEM_RESOLUTION_UNRESOLVED,
    RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
    RISK_MEASURE_REVIEW_NON_COMPLIANT_EMPTY,
    RISK_MEASURE_REVIEW_OPEN_REVISION_LABEL,
    RISK_MEASURE_REVIEW_RESOLUTION_REVISION_OPTION,
    RISK_MEASURE_REVIEW_RESOLUTION_TASK_OPTION,
    RISK_MEASURE_REVIEW_TASKS_TITLE,
)
from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
    RiskMeasureReviewChecklistRow,
    RiskMeasureReviewError,
    risk_measure_review_service,
)
from moduly.rizeni_rizik.ui.hazard_identification_dialog import HazardIdentificationDialog
from moduly.rizeni_rizik.ui.risk_measure_review_item_photos_dialog import (
    RiskMeasureReviewItemPhotosDialog,
)
from moduly.ukoly.sluzby.task_service import task_service
from moduly.ukoly.task_display import task_description_table_text
from moduly.ukoly.ui.task_dialog import TaskDialog

_TASK_STATUS_ORDER = (
    "Aktivní",
    "Splněno - čeká na kontrolu",
    "Ukončeno",
    "Zrušeno",
)

_ROW_BG_EVEN = QColor("#ffffff")
_ROW_BG_ODD = QColor("#f0f0f0")


def _task_status_sort(status: str):
    try:
        return typed_status(_TASK_STATUS_ORDER.index(status), label=status or "")
    except ValueError:
        return typed_status(len(_TASK_STATUS_ORDER), label=status or "")


def _text_or_empty(display: str):
    if not display or display == "—":
        return typed_empty()
    return typed_text(display)


def _photo_label(count: int) -> str:
    if count <= 0:
        return "📷 žádné"
    return f"📷 ({count})"


class RiskMeasureReviewNonCompliantPointWidget(QFrame):
    """Jeden nevyhovující bod – rozhodnutí o způsobu řešení."""

    def __init__(
        self,
        row: RiskMeasureReviewChecklistRow,
        *,
        row_index: int = 0,
        review_id: int | None = None,
        on_changed=None,
        persist_checklist=None,
        parent=None,
    ):
        super().__init__(parent)
        self.row = row
        self.review_id = review_id
        self._on_changed = on_changed
        self._persist_checklist = persist_checklist
        self.setObjectName("riskMeasureReviewNonCompliantPoint")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAutoFillBackground(True)
        color = _ROW_BG_ODD if int(row_index) % 2 else _ROW_BG_EVEN
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, color)
        palette.setColor(QPalette.ColorRole.Base, color)
        self.setPalette(palette)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel(row.measure_title or "—")
        title.setWordWrap(True)
        title.setToolTip(row.measure_title or "")
        title_font = QFont(title.font())
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        if row.note:
            note_label = QLabel(f"Poznámka: {row.note}")
            note_label.setWordWrap(True)
            layout.addWidget(note_label)

        meta = QHBoxLayout()
        self.photo_btn = QPushButton(_photo_label(row.photo_count))
        self.photo_btn.setFlat(True)
        self.photo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.photo_btn.clicked.connect(self._open_photos)
        meta.addWidget(self.photo_btn)
        meta.addStretch(1)
        self.status_label = QLabel(
            RISK_MEASURE_REVIEW_ITEM_RESOLUTION_LABELS.get(
                row.resolution,
                RISK_MEASURE_REVIEW_ITEM_RESOLUTION_LABELS[
                    RISK_MEASURE_REVIEW_ITEM_RESOLUTION_UNRESOLVED
                ],
            )
        )
        meta.addWidget(self.status_label)
        layout.addLayout(meta)

        choice_row = QHBoxLayout()
        self.task_radio = QRadioButton(RISK_MEASURE_REVIEW_RESOLUTION_TASK_OPTION)
        self.revision_radio = QRadioButton(RISK_MEASURE_REVIEW_RESOLUTION_REVISION_OPTION)
        self._choice_group = QButtonGroup(self)
        self._choice_group.setExclusive(True)
        self._choice_group.addButton(self.task_radio)
        self._choice_group.addButton(self.revision_radio)
        if row.resolution == RISK_MEASURE_REVIEW_ITEM_RESOLUTION_TASK:
            self.task_radio.setChecked(True)
        elif row.resolution == RISK_MEASURE_REVIEW_ITEM_RESOLUTION_MEASURE_REVISION:
            self.revision_radio.setChecked(True)
        self.task_radio.toggled.connect(self._update_action_buttons)
        self.revision_radio.toggled.connect(self._update_action_buttons)
        choice_row.addWidget(self.task_radio)
        choice_row.addWidget(self.revision_radio)
        choice_row.addStretch(1)
        layout.addLayout(choice_row)

        actions = QHBoxLayout()
        self.create_task_btn = QPushButton(RISK_MEASURE_REVIEW_CREATE_TASK_LABEL)
        self.open_revision_btn = QPushButton(RISK_MEASURE_REVIEW_OPEN_REVISION_LABEL)
        self.create_task_btn.clicked.connect(self._create_task)
        self.open_revision_btn.clicked.connect(self._open_revision)
        actions.addWidget(self.create_task_btn)
        actions.addWidget(self.open_revision_btn)
        actions.addStretch(1)
        layout.addLayout(actions)
        self._update_action_buttons()

    def _update_action_buttons(self, *_args) -> None:
        self.create_task_btn.setEnabled(self.task_radio.isChecked())
        self.open_revision_btn.setEnabled(self.revision_radio.isChecked())

    def _ensure_persisted(self) -> bool:
        if callable(self._persist_checklist):
            return bool(self._persist_checklist())
        return True

    def _open_photos(self) -> None:
        dialog = RiskMeasureReviewItemPhotosDialog(self, item_id=self.row.item_id)
        dialog.exec()
        count = dialog.photo_count()
        self.photo_btn.setText(_photo_label(count))
        if callable(self._on_changed):
            self._on_changed()

    def _create_task(self) -> None:
        if not self.task_radio.isChecked():
            return
        if not self._ensure_persisted():
            return
        if self.review_id is None:
            QMessageBox.warning(self, RISK_MEASURE_REVIEW_TASKS_TITLE, "Revize není uložená.")
            return

        def _create_task(data: dict):
            try:
                return risk_measure_review_service.create_task_for_checklist_item(
                    int(self.review_id),
                    self.row.item_id,
                    title=data["title"],
                    description=data.get("description") or "",
                    due_date=data.get("due_date"),
                    remind_from=data.get("remind_from"),
                    responsible_person_id=data.get("responsible_person_id"),
                    workplace_id=data.get("workplace_id"),
                )
            except RiskMeasureReviewError as error:
                QMessageBox.warning(self, RISK_MEASURE_REVIEW_TASKS_TITLE, str(error))
                return None

        dialog = TaskDialog(self, create_factory=_create_task)
        title_parts = [self.row.measure_title or ""]
        if self.row.note:
            title_parts.append(self.row.note)
        dialog.title_edit.setPlainText("\n".join(part for part in title_parts if part).strip())
        dialog._capture_baseline()
        dialog.exec()
        if callable(self._on_changed):
            self._on_changed()

    def _open_revision(self) -> None:
        if not self.revision_radio.isChecked():
            return
        if not self._ensure_persisted():
            return
        try:
            context = risk_measure_review_service.resolve_context_for_measure(
                self.row.follow_up_measure_id
            )
            risk_measure_review_service.mark_measure_revision_for_item(self.row.item_id)
        except RiskMeasureReviewError as error:
            QMessageBox.warning(self, RISK_MEASURE_REVIEW_TASKS_TITLE, str(error))
            return

        dialog = HazardIdentificationDialog(
            self,
            identification=context["identification"],
        )
        dialog.tabs.setCurrentIndex(dialog.risk_assessment_tab_index)
        assessment = context["assessment"]
        dialog.risk_assessments_widget._selected_assessment_id = assessment.id
        exec_maximized(dialog)
        if callable(self._on_changed):
            self._on_changed()


class RiskMeasureReviewTasksWidget(QWidget):
    """Záložka Úkoly – rozhodnutí u nevyhovujících bodů + seznam úkolů."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.review_id: int | None = None
        self._persist_checklist = None
        self._checklist_snapshot: list[dict] = []
        self._point_widgets: list[RiskMeasureReviewNonCompliantPointWidget] = []

        layout = QVBoxLayout(self)

        self.info_label = QLabel("Úkoly lze zobrazit až po uložení revize.")
        self.info_label.setWordWrap(True)

        non_compliant_header = QLabel("Nevyhovující kontrolní body")
        header_font = QFont(non_compliant_header.font())
        header_font.setBold(True)
        non_compliant_header.setFont(header_font)

        self.non_compliant_empty = QLabel(RISK_MEASURE_REVIEW_NON_COMPLIANT_EMPTY)
        self.non_compliant_empty.setWordWrap(True)

        self.points_scroll = QScrollArea()
        self.points_scroll.setWidgetResizable(True)
        self.points_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.points_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.points_host = QWidget()
        self.points_layout = QVBoxLayout(self.points_host)
        self.points_layout.setContentsMargins(0, 0, 0, 0)
        self.points_layout.setSpacing(0)
        self.points_layout.addStretch(1)
        self.points_scroll.setWidget(self.points_host)
        self.points_scroll.setMinimumHeight(160)
        self.points_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        tasks_header = QLabel("Založené úkoly")
        tasks_header.setFont(header_font)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nový úkol")
        self.open_btn = QPushButton("Otevřít úkol")
        self.refresh_btn = QPushButton("Obnovit")
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.open_btn)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addStretch()

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Název",
            "Odpovědná osoba",
            "Termín",
            "Stav",
        ])
        self.table.setColumnHidden(0, True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(26)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for column in (2, 3, 4):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        enable_typed_sorting(self.table)

        self.empty_label = QLabel("Revize zatím nemá žádné úkoly.")
        self.empty_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.info_label)
        layout.addWidget(non_compliant_header)
        layout.addWidget(self.non_compliant_empty)
        layout.addWidget(self.points_scroll, 2)
        layout.addWidget(tasks_header)
        layout.addLayout(toolbar)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.table, 1)

        self.new_btn.clicked.connect(self.create_task)
        self.open_btn.clicked.connect(self.open_selected_task)
        self.refresh_btn.clicked.connect(self.refresh)
        self.table.doubleClicked.connect(self.open_selected_task)

        self._update_state()

    def set_persist_checklist(self, callback) -> None:
        self._persist_checklist = callback

    def set_review_id(self, review_id: int | None) -> None:
        self.review_id = review_id
        self.refresh()
        self._update_state()

    def sync_from_checklist_updates(self, updates: list[dict]) -> None:
        """Obnoví seznam nevyhovujících bodů podle aktuálního stavu checklistu."""
        self._checklist_snapshot = list(updates or [])
        self._reload_non_compliant_points()

    def refresh(self) -> None:
        self._reload_non_compliant_points()
        self._reload_tasks_table()

    def _reload_non_compliant_points(self) -> None:
        while self.points_layout.count():
            item = self.points_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._point_widgets = []

        rows: list[RiskMeasureReviewChecklistRow] = []
        if self.review_id is not None:
            db_rows = {
                row.item_id: row
                for row in risk_measure_review_service.list_checklist_rows(self.review_id)
            }
            if self._checklist_snapshot:
                for update in self._checklist_snapshot:
                    item_id = int(update.get("item_id") or 0)
                    result = str(update.get("result") or "")
                    if result != RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT:
                        continue
                    base = db_rows.get(item_id)
                    if base is None:
                        continue
                    rows.append(
                        RiskMeasureReviewChecklistRow(
                            item_id=base.item_id,
                            follow_up_measure_id=base.follow_up_measure_id,
                            measure_title=base.measure_title,
                            result=RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
                            note=str(update.get("note") or base.note or "").strip(),
                            photo_count=int(
                                update.get("photo_count", base.photo_count) or 0
                            ),
                            has_photo=bool(
                                update.get("has_photo", base.has_photo)
                            ),
                            sort_order=base.sort_order,
                            resolution=base.resolution,
                        )
                    )
            else:
                rows = risk_measure_review_service.list_non_compliant_rows(self.review_id)

        self.non_compliant_empty.setVisible(not rows)
        self.points_scroll.setVisible(bool(rows))
        for index, row in enumerate(rows):
            point = RiskMeasureReviewNonCompliantPointWidget(
                row,
                row_index=index,
                review_id=self.review_id,
                on_changed=self.refresh,
                persist_checklist=self._persist_checklist,
                parent=self.points_host,
            )
            self._point_widgets.append(point)
            self.points_layout.addWidget(point)
        self.points_layout.addStretch(1)

    def _reload_tasks_table(self) -> None:
        tasks = []
        if self.review_id is not None:
            tasks = risk_measure_review_service.get_tasks_for_review(self.review_id)

        self.empty_label.setVisible(not tasks)
        self.table.setVisible(bool(tasks))
        self.empty_label.setText(
            "Revize zatím nemá žádné úkoly."
            if self.review_id is not None
            else "Úkoly lze zobrazit až po uložení revize."
        )

        with sorting_paused(self.table):
            self.table.setRowCount(len(tasks))
            for row, task in enumerate(tasks):
                record_id = int(task.id)
                responsible = task.responsible_person or "—"
                due_display = "" if task.due_date is None else task.due_date.strftime("%d.%m.%Y")
                status = task.computed_status
                cells = [
                    create_typed_item(
                        str(task.id),
                        typed_int(task.id),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        task_description_table_text(task),
                        typed_text(task_description_table_text(task)),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        responsible,
                        _text_or_empty(responsible),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        due_display,
                        typed_date(task.due_date) if task.due_date is not None else typed_empty(),
                        stable_id=record_id,
                    ),
                    create_typed_item(
                        status,
                        _task_status_sort(status),
                        stable_id=record_id,
                    ),
                ]
                for column, item in enumerate(cells):
                    self.table.setItem(row, column, item)

    def create_task(self) -> None:
        if self.review_id is None:
            QMessageBox.information(
                self,
                RISK_MEASURE_REVIEW_TASKS_TITLE,
                "Úkol lze založit až po uložení revize.",
            )
            return

        def _create_task(data: dict):
            try:
                return risk_measure_review_service.create_task_for_review(
                    self.review_id,
                    title=data["title"],
                    description=data.get("description") or "",
                    due_date=data.get("due_date"),
                    remind_from=data.get("remind_from"),
                    responsible_person_id=data.get("responsible_person_id"),
                    workplace_id=data.get("workplace_id"),
                )
            except RiskMeasureReviewError as error:
                QMessageBox.warning(self, RISK_MEASURE_REVIEW_TASKS_TITLE, str(error))
                return None

        dialog = TaskDialog(self, create_factory=_create_task)
        dialog.exec()
        self.refresh()

    def _update_state(self) -> None:
        enabled = self.review_id is not None
        self.info_label.setVisible(not enabled)
        self.new_btn.setEnabled(enabled)
        self.open_btn.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)

    def _selected_task_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.table.item(selected[0].row(), 0)
        return int(item.text()) if item else None

    def open_selected_task(self) -> None:
        task_id = self._selected_task_id()
        if task_id is None:
            QMessageBox.information(self, RISK_MEASURE_REVIEW_TASKS_TITLE, "Vyberte úkol.")
            return

        task = task_service.get_task_by_id(task_id)
        if task is None:
            QMessageBox.warning(self, RISK_MEASURE_REVIEW_TASKS_TITLE, "Úkol nebyl nalezen.")
            self.refresh()
            return

        dialog = TaskDialog(self, task=task)
        dialog.exec()
        self.refresh()
