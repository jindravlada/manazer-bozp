from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.ai_oponentni.constants import (
    AI_PEER_REVIEW_DIALOG_TITLE,
    AI_PEER_REVIEW_IMPORT_INTRO_PACKAGES,
    AI_PEER_REVIEW_PACKAGE_TYPE_LABELS,
)
from core.ai_oponentni.proposal_package_types import AiProposalPackage
from core.widgets.dialog_utils import create_save_cancel_box


class AiPeerReviewPackageImportDialog(QDialog):
    """Seznam návrhových balíků AI s možností přijmout / zamítnout."""

    def __init__(
        self,
        parent=None,
        *,
        packages: list[AiProposalPackage],
        ai_model: str = "",
        intro_text: str | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(AI_PEER_REVIEW_DIALOG_TITLE)
        self.resize(900, 520)
        self._packages = list(packages)
        self._ai_model = ai_model

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(intro_text or AI_PEER_REVIEW_IMPORT_INTRO_PACKAGES))

        toolbar = QHBoxLayout()
        self.select_all_btn = QPushButton("Označit vše")
        self.clear_all_btn = QPushButton("Zrušit označení")
        toolbar.addWidget(self.select_all_btn)
        toolbar.addWidget(self.clear_all_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.table = QTableWidget(len(self._packages), 8)
        self.table.setHorizontalHeaderLabels(
            [
                "Přijmout",
                "Typ",
                "Událost",
                "Posouzení",
                "Exist. opatření",
                "Potřebná opatření",
                "Právní vazby",
                "Zdůvodnění",
            ],
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)

        self._checkboxes: list[QCheckBox] = []
        for row_index, package in enumerate(self._packages):
            checkbox = QCheckBox()
            checkbox.setChecked(False)
            self._checkboxes.append(checkbox)
            cell = QTableWidgetItem()
            cell.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(row_index, 0, cell)
            self.table.setCellWidget(row_index, 0, checkbox)
            self.table.setItem(
                row_index,
                1,
                QTableWidgetItem(
                    AI_PEER_REVIEW_PACKAGE_TYPE_LABELS.get(
                        package.package_type,
                        package.package_type,
                    ),
                ),
            )
            self.table.setItem(row_index, 2, QTableWidgetItem(package.event_name))
            self.table.setItem(
                row_index,
                3,
                QTableWidgetItem(str(package.assessment_count)),
            )
            self.table.setItem(
                row_index,
                4,
                QTableWidgetItem(str(package.existing_measure_count)),
            )
            self.table.setItem(
                row_index,
                5,
                QTableWidgetItem(str(package.required_measure_count)),
            )
            self.table.setItem(
                row_index,
                6,
                QTableWidgetItem(str(package.legal_link_count)),
            )
            self.table.setItem(row_index, 7, QTableWidgetItem(package.reasoning or "—"))

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

    def get_accepted_and_rejected(self) -> tuple[list[AiProposalPackage], list[AiProposalPackage]]:
        accepted: list[AiProposalPackage] = []
        rejected: list[AiProposalPackage] = []
        for checkbox, package in zip(self._checkboxes, self._packages):
            if checkbox.isChecked():
                accepted.append(package)
            else:
                rejected.append(package)
        return accepted, rejected
