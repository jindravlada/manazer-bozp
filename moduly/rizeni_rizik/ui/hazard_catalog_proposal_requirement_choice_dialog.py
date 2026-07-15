from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from moduly.rizeni_rizik.constants_library import (
    CATALOG_AI_PROPOSAL_DUPLICATE_CANCEL,
    CATALOG_AI_PROPOSAL_DUPLICATE_SKIP,
    CATALOG_AI_PROPOSAL_MANUAL_REQUIREMENT_INTRO,
    CATALOG_AI_PROPOSAL_REQUIREMENT_CHOICE_DIALOG_TITLE,
    CATALOG_AI_PROPOSAL_REQUIREMENT_CHOICE_INTRO,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
    CATALOG_DUPLICATE_ACTION_CANCEL,
    CATALOG_DUPLICATE_ACTION_SKIP,
)


class HazardCatalogProposalRequirementChoiceDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        proposal_name: str,
        candidates: tuple[tuple[int, str], ...],
        intro_text: str | None = None,
    ):
        super().__init__(parent)
        self.selected_requirement_id: int | None = None
        self.selected_action = CATALOG_DUPLICATE_ACTION_CANCEL

        self.setWindowTitle(CATALOG_AI_PROPOSAL_REQUIREMENT_CHOICE_DIALOG_TITLE)
        self.resize(560, 320)

        layout = QVBoxLayout(self)
        intro = QLabel(
            (intro_text or CATALOG_AI_PROPOSAL_REQUIREMENT_CHOICE_INTRO).format(
                proposal_name=proposal_name,
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.list_widget = QListWidget()
        for requirement_id, label in candidates:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, requirement_id)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        buttons = QDialogButtonBox()
        choose_button = QPushButton("Použít vybraný")
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
        item = self.list_widget.currentItem()
        if item is None:
            return
        self.selected_requirement_id = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def _choose_action(self, action: str) -> None:
        self.selected_action = action
        self.accept()
