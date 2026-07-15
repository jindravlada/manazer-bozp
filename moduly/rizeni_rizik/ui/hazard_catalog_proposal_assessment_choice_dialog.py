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
    CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_DIALOG_TITLE,
    CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_EVENT_COLUMN,
    CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_GROUP_COLUMN,
    CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_INTRO,
    CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_USE_BUTTON,
    CATALOG_AI_PROPOSAL_ASSESSMENT_CREATE_BUTTON,
    CATALOG_AI_PROPOSAL_ASSESSMENT_CREATE_DIALOG_TITLE,
    CATALOG_AI_PROPOSAL_ASSESSMENT_CREATE_INTRO,
    CATALOG_AI_PROPOSAL_DUPLICATE_CANCEL,
    CATALOG_AI_PROPOSAL_DUPLICATE_SKIP,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
    CATALOG_DUPLICATE_ACTION_CANCEL,
    CATALOG_DUPLICATE_ACTION_CREATE,
    CATALOG_DUPLICATE_ACTION_SKIP,
    CatalogAssessmentCandidate,
)


class HazardCatalogProposalAssessmentChoiceDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        proposal_name: str,
        candidates: tuple[CatalogAssessmentCandidate, ...],
    ):
        super().__init__(parent)
        self.selected_assessment_export_id: str | None = None
        self.selected_action = CATALOG_DUPLICATE_ACTION_CANCEL

        self.setWindowTitle(CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_DIALOG_TITLE)
        self.resize(640, 360)

        layout = QVBoxLayout(self)
        intro = QLabel(CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_INTRO)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(
            [
                CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_EVENT_COLUMN,
                CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_GROUP_COLUMN,
            ],
        )
        self.table.setRowCount(len(candidates))
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for row_index, candidate in enumerate(candidates):
            event_item = QTableWidgetItem(candidate.event_name)
            event_item.setData(Qt.ItemDataRole.UserRole, candidate.export_id)
            group_item = QTableWidgetItem(candidate.group_name)
            self.table.setItem(row_index, 0, event_item)
            self.table.setItem(row_index, 1, group_item)
        if candidates:
            self.table.selectRow(0)
        layout.addWidget(self.table)

        buttons = QDialogButtonBox()
        choose_button = QPushButton(CATALOG_AI_PROPOSAL_ASSESSMENT_CHOICE_USE_BUTTON)
        skip_button = QPushButton(CATALOG_AI_PROPOSAL_DUPLICATE_SKIP)
        cancel_button = QPushButton(CATALOG_AI_PROPOSAL_DUPLICATE_CANCEL)
        buttons.addButton(choose_button, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(skip_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(buttons)

        choose_button.clicked.connect(self._choose_selected)
        skip_button.clicked.connect(lambda: self._choose_action(CATALOG_DUPLICATE_ACTION_SKIP))
        cancel_button.clicked.connect(lambda: self._choose_action(CATALOG_DUPLICATE_ACTION_CANCEL))

    def _choose_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is None:
            return
        self.selected_assessment_export_id = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _choose_action(self, action: str) -> None:
        self.selected_action = action
        self.accept()


class HazardCatalogProposalAssessmentCreateDialog(QDialog):
    def __init__(self, parent=None, *, proposal_name: str):
        super().__init__(parent)
        self.selected_action = CATALOG_DUPLICATE_ACTION_CANCEL

        self.setWindowTitle(CATALOG_AI_PROPOSAL_ASSESSMENT_CREATE_DIALOG_TITLE)
        self.resize(560, 220)

        layout = QVBoxLayout(self)
        intro = QLabel(
            CATALOG_AI_PROPOSAL_ASSESSMENT_CREATE_INTRO.format(
                proposal_name=proposal_name,
            ),
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        buttons = QDialogButtonBox()
        create_button = QPushButton(CATALOG_AI_PROPOSAL_ASSESSMENT_CREATE_BUTTON)
        skip_button = QPushButton(CATALOG_AI_PROPOSAL_DUPLICATE_SKIP)
        cancel_button = QPushButton(CATALOG_AI_PROPOSAL_DUPLICATE_CANCEL)
        buttons.addButton(create_button, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(skip_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(buttons)

        create_button.clicked.connect(lambda: self._choose_action(CATALOG_DUPLICATE_ACTION_CREATE))
        skip_button.clicked.connect(lambda: self._choose_action(CATALOG_DUPLICATE_ACTION_SKIP))
        cancel_button.clicked.connect(lambda: self._choose_action(CATALOG_DUPLICATE_ACTION_CANCEL))

    def _choose_action(self, action: str) -> None:
        self.selected_action = action
        self.accept()
