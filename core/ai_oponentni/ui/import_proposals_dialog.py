from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.ai_oponentni.constants import AI_PEER_REVIEW_DIALOG_TITLE
from core.ai_oponentni.types import AiProposal
from core.widgets.dialog_utils import create_save_cancel_box


class AiPeerReviewImportDialog(QDialog):
    """Seznam návrhů AI s možností převzít / nepřevzít."""

    def __init__(
        self,
        parent=None,
        *,
        proposals: list[AiProposal],
        ai_model: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle(AI_PEER_REVIEW_DIALOG_TITLE)
        self.resize(760, 480)
        self._proposals = list(proposals)
        self._ai_model = ai_model

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Označte návrhy k převzetí do evidence. "
                "Neoznačené návrhy budou evidovány jako zamítnuté."
            )
        )

        toolbar = QHBoxLayout()
        self.select_all_btn = QPushButton("Označit vše")
        self.clear_all_btn = QPushButton("Zrušit označení")
        toolbar.addWidget(self.select_all_btn)
        toolbar.addWidget(self.clear_all_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget(len(self._proposals), 4)
        self.table.setHorizontalHeaderLabels(
            ["Převzít", "Oblast", "Návrh", "Zdůvodnění"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self._checkboxes: list[QCheckBox] = []
        for row_index, proposal in enumerate(self._proposals):
            checkbox = QCheckBox()
            checkbox.setChecked(False)
            self._checkboxes.append(checkbox)
            cell = QTableWidgetItem()
            cell.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row_index, 0, cell)
            self.table.setCellWidget(row_index, 0, checkbox)
            self.table.setItem(row_index, 1, QTableWidgetItem(proposal.area))
            self.table.setItem(row_index, 2, QTableWidgetItem(proposal.name))
            self.table.setItem(row_index, 3, QTableWidgetItem(proposal.reasoning))

        layout.addWidget(self.table)

        buttons = create_save_cancel_box(self)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setText("Potvrdit výběr")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.select_all_btn.clicked.connect(self._select_all)
        self.clear_all_btn.clicked.connect(self._clear_all)

    def _select_all(self) -> None:
        for checkbox in self._checkboxes:
            checkbox.setChecked(True)

    def _clear_all(self) -> None:
        for checkbox in self._checkboxes:
            checkbox.setChecked(False)

    def get_accepted_and_rejected(self) -> tuple[list[AiProposal], list[AiProposal]]:
        accepted: list[AiProposal] = []
        rejected: list[AiProposal] = []
        for checkbox, proposal in zip(self._checkboxes, self._proposals):
            if checkbox.isChecked():
                accepted.append(proposal)
            else:
                rejected.append(proposal)
        return accepted, rejected

    def accept(self) -> None:
        accepted, _rejected = self.get_accepted_and_rejected()
        if not accepted and not self._proposals:
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, "Žádné návrhy k importu.")
            return
        super().accept()
