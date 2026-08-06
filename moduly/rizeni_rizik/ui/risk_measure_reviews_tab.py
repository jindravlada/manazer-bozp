from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import exec_maximized
from core.widgets.filter_bar import FilterBar
from core.widgets.table_utils import configure_table_columns
from moduly.rizeni_rizik.constants import (
    RISK_MEASURE_REVIEW_DEFAULT_STATUS_FILTER,
    RISK_MEASURE_REVIEW_DIALOG_TITLE,
    RISK_MEASURE_REVIEW_EXECUTE_DIALOG_TITLE,
    RISK_MEASURE_REVIEW_FILTER_ALL,
    RISK_MEASURE_REVIEW_STATUS_ARCHIVED,
    RISK_MEASURE_REVIEW_STATUS_COMPLETED,
    RISK_MEASURE_REVIEW_STATUS_DRAFT,
    RISK_MEASURE_REVIEW_STATUS_LABELS,
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
        self.edit_btn.setEnabled(False)
        self.execute_btn.setEnabled(False)
        self.archive_btn.setEnabled(False)
        self.restore_btn.setEnabled(False)
        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.execute_btn)
        toolbar.addWidget(self.archive_btn)
        toolbar.addWidget(self.restore_btn)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Stav:"))
        self.status_filter = QComboBox()
        self.status_filter.addItem(
            RISK_MEASURE_REVIEW_STATUS_LABELS[RISK_MEASURE_REVIEW_STATUS_DRAFT],
            RISK_MEASURE_REVIEW_STATUS_DRAFT,
        )
        self.status_filter.addItem(
            RISK_MEASURE_REVIEW_STATUS_LABELS[RISK_MEASURE_REVIEW_STATUS_COMPLETED],
            RISK_MEASURE_REVIEW_STATUS_COMPLETED,
        )
        self.status_filter.addItem(
            RISK_MEASURE_REVIEW_STATUS_LABELS[RISK_MEASURE_REVIEW_STATUS_ARCHIVED],
            RISK_MEASURE_REVIEW_STATUS_ARCHIVED,
        )
        self.status_filter.addItem(RISK_MEASURE_REVIEW_FILTER_ALL, RISK_MEASURE_REVIEW_FILTER_ALL)
        default_index = self.status_filter.findData(RISK_MEASURE_REVIEW_DEFAULT_STATUS_FILTER)
        if default_index >= 0:
            self.status_filter.setCurrentIndex(default_index)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        toolbar.addWidget(self.status_filter)

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
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_context_menu)
        self.table.selectionModel().selectionChanged.connect(self._refresh_action_buttons)

        self.refresh()

    def _selected_row_count(self) -> int:
        return len(self.table.selectionModel().selectedRows())

    def _refresh_action_buttons(self, *_args) -> None:
        review = self._selected_review()
        single = review is not None
        self.edit_btn.setEnabled(single)
        self.execute_btn.setEnabled(single and review.archived_at is None)
        self.archive_btn.setEnabled(single and review.archived_at is None)
        self.restore_btn.setEnabled(single and review.archived_at is not None)

    def _show_table_context_menu(self, position) -> None:
        index = self.table.indexAt(position)
        if index.isValid():
            self.table.selectRow(index.row())
            self._refresh_action_buttons()

        review = self._selected_review()
        single = review is not None
        if not single and not index.isValid():
            return

        menu = QMenu(self)
        edit_action = menu.addAction("Upravit", self.edit_selected_review)
        edit_action.setEnabled(single)
        execute_action = menu.addAction("Provést přezkoumání", self.execute_selected_review)
        execute_action.setEnabled(single and review is not None and review.archived_at is None)
        archive_action = menu.addAction("Archivovat", self.archive_selected_review)
        archive_action.setEnabled(single and review is not None and review.archived_at is None)
        restore_action = menu.addAction("Obnovit", self.restore_selected_review)
        restore_action.setEnabled(single and review is not None and review.archived_at is not None)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def new_review(self) -> None:
        dialog = RiskMeasureReviewDialog(self)
        dialog.exec()
        self.refresh()

    def edit_selected_review(self) -> None:
        review = self._selected_review()
        if review is None:
            return
        dialog = RiskMeasureReviewDialog(self, review=review)
        dialog.exec()
        self.refresh()

    def execute_selected_review(self) -> None:
        review = self._selected_review()
        if review is None:
            return
        if review.archived_at is not None:
            QMessageBox.information(
                self,
                RISK_MEASURE_REVIEW_EXECUTE_DIALOG_TITLE,
                "Archivované přezkoumání nelze provádět. Nejprve jej obnovte.",
            )
            return
        dialog = RiskMeasureReviewExecutionDialog(self, review=review)
        exec_maximized(dialog)
        self.refresh()

    def archive_selected_review(self) -> None:
        review = self._selected_review()
        if review is None:
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
        if self._selected_row_count() != 1:
            return None
        review_id = self.table.selected_review_id()
        if review_id is None:
            return None
        return risk_measure_review_service.get_by_id(review_id)

    def refresh(self) -> None:
        reviews = risk_measure_review_service.get_all(include_archived=True)
        mode = self.status_filter.currentData()
        if mode != RISK_MEASURE_REVIEW_FILTER_ALL:
            reviews = [review for review in reviews if review.status == mode]
        self.table.load_reviews(reviews)
        configure_table_columns(self.table, "risk_measure_reviews")
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.text_filter.update_count()
        self._refresh_action_buttons()
