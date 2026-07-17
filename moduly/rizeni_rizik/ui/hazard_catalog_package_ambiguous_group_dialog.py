"""Dialog výběru cílového posouzení při duplicitní ohrožené skupině (R20g)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from moduly.rizeni_rizik.constants_library import (
    CATALOG_AI_PACKAGE_AMBIGUOUS_GROUP_COLUMN_CONCLUSION,
    CATALOG_AI_PACKAGE_AMBIGUOUS_GROUP_COLUMN_SEVERITY,
    CATALOG_AI_PACKAGE_AMBIGUOUS_GROUP_DIALOG_TITLE,
    CATALOG_AI_PACKAGE_AMBIGUOUS_GROUP_INTRO,
    CATALOG_AI_PACKAGE_AMBIGUOUS_GROUP_USE_BUTTON,
    CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_GROUP_COLUMN,
    CATALOG_AI_PROPOSAL_DUPLICATE_CANCEL,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
    AmbiguousAssessmentCandidate,
)


class HazardCatalogPackageAmbiguousGroupDialog(QDialog):
    """Uživatel zvolí cílové posouzení při více shodách pro stejnou skupinu."""

    def __init__(
        self,
        parent=None,
        *,
        group_name: str,
        candidates: tuple[AmbiguousAssessmentCandidate, ...],
    ):
        super().__init__(parent)
        self.selected_assessment_id: int | None = None

        self.setWindowTitle(CATALOG_AI_PACKAGE_AMBIGUOUS_GROUP_DIALOG_TITLE)
        self.resize(720, 360)

        layout = QVBoxLayout(self)
        intro = QLabel(
            CATALOG_AI_PACKAGE_AMBIGUOUS_GROUP_INTRO.format(group_name=group_name),
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(
            [
                CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_GROUP_COLUMN,
                CATALOG_AI_PACKAGE_AMBIGUOUS_GROUP_COLUMN_SEVERITY,
                CATALOG_AI_PACKAGE_AMBIGUOUS_GROUP_COLUMN_CONCLUSION,
            ],
        )
        self.table.setRowCount(len(candidates))
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        for row_index, candidate in enumerate(candidates):
            groups_item = QTableWidgetItem(candidate.group_names)
            groups_item.setData(Qt.ItemDataRole.UserRole, candidate.assessment_id)
            severity_item = QTableWidgetItem(candidate.severity_label)
            conclusion_item = QTableWidgetItem(candidate.conclusion or "—")
            self.table.setItem(row_index, 0, groups_item)
            self.table.setItem(row_index, 1, severity_item)
            self.table.setItem(row_index, 2, conclusion_item)
        if candidates:
            self.table.selectRow(0)
        layout.addWidget(self.table)

        buttons = QDialogButtonBox()
        use_button = QPushButton(CATALOG_AI_PACKAGE_AMBIGUOUS_GROUP_USE_BUTTON)
        cancel_button = QPushButton(CATALOG_AI_PROPOSAL_DUPLICATE_CANCEL)
        buttons.addButton(use_button, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(buttons)

        use_button.clicked.connect(self._choose_selected)
        cancel_button.clicked.connect(self.reject)

    def _choose_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        assessment_id = item.data(Qt.ItemDataRole.UserRole)
        if assessment_id is None:
            return
        self.selected_assessment_id = int(assessment_id)
        self.accept()
