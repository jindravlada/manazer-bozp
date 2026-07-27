from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout, QWidget

from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.rizeni_rizik.constants import (
    RISK_MEASURE_REVIEW_DIALOG_TITLE,
    RISK_MEASURE_REVIEW_EXECUTE_DIALOG_TITLE,
)
from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
    risk_measure_review_service,
)
from moduly.rizeni_rizik.ui.risk_measure_review_dialog import RiskMeasureReviewDialog
from moduly.rizeni_rizik.ui.risk_measure_review_execution_dialog import (
    RiskMeasureReviewExecutionDialog,
)
from moduly.rizeni_rizik.ui.risk_measure_review_table import RiskMeasureReviewTable


class RiskMeasureReviewsTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nové přezkoumání")
        self.edit_btn = QPushButton("Upravit")
        self.execute_btn = QPushButton("Provést přezkoumání")
        self.archive_btn = QPushButton("Archivovat")
        self.restore_btn = QPushButton("Obnovit")
        self.execute_btn.setEnabled(False)
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.execute_btn)
        toolbar.addWidget(self.archive_btn)
        toolbar.addWidget(self.restore_btn)
        toolbar.addStretch()

        self.table = RiskMeasureReviewTable()
        configure_table_columns(self.table, "risk_measure_reviews")
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat přezkoumání...")

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_review)
        self.edit_btn.clicked.connect(self.edit_selected_review)
        self.execute_btn.clicked.connect(self.execute_selected_review)
        self.archive_btn.clicked.connect(self.archive_selected_review)
        self.restore_btn.clicked.connect(self.restore_selected_review)
        self.table.doubleClicked.connect(self.edit_selected_review)
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.refresh()

    def new_review(self) -> None:
        dialog = RiskMeasureReviewDialog(self)
        dialog.exec()
        self.refresh()

    def edit_selected_review(self) -> None:
        review = self._selected_review()
        if review is None:
            QMessageBox.information(
                self,
                RISK_MEASURE_REVIEW_DIALOG_TITLE,
                "Vyberte přezkoumání.",
            )
            return
        dialog = RiskMeasureReviewDialog(self, review=review)
        dialog.exec()
        self.refresh()

    def execute_selected_review(self) -> None:
        review = self._selected_review()
        if review is None:
            QMessageBox.information(
                self,
                RISK_MEASURE_REVIEW_EXECUTE_DIALOG_TITLE,
                "Vyberte přezkoumání.",
            )
            return
        if review.archived_at is not None:
            QMessageBox.information(
                self,
                RISK_MEASURE_REVIEW_EXECUTE_DIALOG_TITLE,
                "Archivované přezkoumání nelze provádět. Nejprve jej obnovte.",
            )
            return
        dialog = RiskMeasureReviewExecutionDialog(self, review=review)
        dialog.exec()
        self.refresh()

    def archive_selected_review(self) -> None:
        review = self._selected_review()
        if review is None:
            QMessageBox.information(
                self,
                RISK_MEASURE_REVIEW_DIALOG_TITLE,
                "Vyberte přezkoumání.",
            )
            return
        if review.archived_at is not None:
            QMessageBox.information(
                self,
                RISK_MEASURE_REVIEW_DIALOG_TITLE,
                "Přezkoumání je již archivováno.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Archivovat",
            f"Opravdu archivovat přezkoumání {review.review_number}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            risk_measure_review_service.archive(review.id)
            self.refresh()

    def restore_selected_review(self) -> None:
        review = self._selected_review()
        if review is None:
            QMessageBox.information(
                self,
                RISK_MEASURE_REVIEW_DIALOG_TITLE,
                "Vyberte přezkoumání.",
            )
            return
        if review.archived_at is None:
            QMessageBox.information(
                self,
                RISK_MEASURE_REVIEW_DIALOG_TITLE,
                "Přezkoumání není archivováno.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Obnovit",
            f"Opravdu obnovit přezkoumání {review.review_number}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            risk_measure_review_service.restore(review.id)
            self.refresh()

    def _selected_review(self):
        review_id = self.table.selected_review_id()
        if review_id is None:
            return None
        return risk_measure_review_service.get_by_id(review_id)

    def _update_action_buttons(self) -> None:
        review = self._selected_review()
        self.execute_btn.setEnabled(review is not None and review.archived_at is None)

    def refresh(self) -> None:
        reviews = risk_measure_review_service.get_all(include_archived=True)
        self.table.load_reviews(reviews)
        configure_table_columns(self.table, "risk_measure_reviews")
        self.text_filter.update_count()
        self._update_action_buttons()
