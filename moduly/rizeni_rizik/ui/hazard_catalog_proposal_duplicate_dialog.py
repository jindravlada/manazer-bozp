from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from moduly.rizeni_rizik.constants_library import (
    CATALOG_AI_PROPOSAL_DUPLICATE_CANCEL,
    CATALOG_AI_PROPOSAL_DUPLICATE_DIALOG_TITLE,
    CATALOG_AI_PROPOSAL_DUPLICATE_EDIT,
    CATALOG_AI_PROPOSAL_DUPLICATE_INTRO,
    CATALOG_AI_PROPOSAL_DUPLICATE_MERGE,
    CATALOG_AI_PROPOSAL_DUPLICATE_SIMILAR_INTRO,
    CATALOG_AI_PROPOSAL_DUPLICATE_SKIP,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
    CATALOG_DUPLICATE_ACTION_CANCEL,
    CATALOG_DUPLICATE_ACTION_EDIT,
    CATALOG_DUPLICATE_ACTION_MERGE,
    CATALOG_DUPLICATE_ACTION_SKIP,
    CATALOG_DUPLICATE_MATCH_SIMILAR,
    CatalogProposalDuplicate,
)


class HazardCatalogProposalDuplicateDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        proposal_name: str,
        duplicate: CatalogProposalDuplicate,
    ):
        super().__init__(parent)
        self.selected_action = CATALOG_DUPLICATE_ACTION_CANCEL

        self.setWindowTitle(CATALOG_AI_PROPOSAL_DUPLICATE_DIALOG_TITLE)
        self.resize(520, 220)

        layout = QVBoxLayout(self)
        intro_text = (
            CATALOG_AI_PROPOSAL_DUPLICATE_SIMILAR_INTRO
            if duplicate.match_type == CATALOG_DUPLICATE_MATCH_SIMILAR
            else CATALOG_AI_PROPOSAL_DUPLICATE_INTRO
        )
        intro = QLabel(
            intro_text.format(
                proposal_name=proposal_name,
                existing_label=duplicate.existing_label,
            )
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        buttons = QDialogButtonBox()
        skip_button = QPushButton(CATALOG_AI_PROPOSAL_DUPLICATE_SKIP)
        merge_button = QPushButton(CATALOG_AI_PROPOSAL_DUPLICATE_MERGE)
        edit_button = QPushButton(CATALOG_AI_PROPOSAL_DUPLICATE_EDIT)
        cancel_button = QPushButton(CATALOG_AI_PROPOSAL_DUPLICATE_CANCEL)
        buttons.addButton(skip_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(merge_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(edit_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(cancel_button, QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(buttons)

        skip_button.clicked.connect(lambda: self._choose(CATALOG_DUPLICATE_ACTION_SKIP))
        merge_button.clicked.connect(lambda: self._choose(CATALOG_DUPLICATE_ACTION_MERGE))
        edit_button.clicked.connect(lambda: self._choose(CATALOG_DUPLICATE_ACTION_EDIT))
        cancel_button.clicked.connect(lambda: self._choose(CATALOG_DUPLICATE_ACTION_CANCEL))

    def _choose(self, action: str) -> None:
        self.selected_action = action
        self.accept()
