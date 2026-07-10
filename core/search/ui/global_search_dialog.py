"""Dialog globálního vyhledávání."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.search import global_search_service
from core.search.constants import MIN_QUERY_LENGTH
from core.search.global_search_result import GlobalSearchResult
from core.search.global_search_service import GlobalSearchService

logger = logging.getLogger(__name__)

_RESULT_ROLE = Qt.ItemDataRole.UserRole


class GlobalSearchDialog(QDialog):
    STATUS_QUERY_TOO_SHORT = "Zadejte alespoň 2 znaky."
    STATUS_EMPTY = "Pro zadaný text nebyly nalezeny žádné výsledky."
    STATUS_OPEN_FAILED = "Výsledek nelze otevřít."
    STATUS_OPEN_UNSUPPORTED = "Tento typ výsledku zatím nelze otevřít."
    STATUS_OPEN_ERROR = "Chyba při otevírání výsledku."

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        search_service: GlobalSearchService | None = None,
        host=None,
        initial_query: str = "",
    ) -> None:
        super().__init__(parent)
        self._service = search_service or global_search_service
        self._host = host if host is not None else parent

        self.setWindowTitle("Globální vyhledávání")
        self.setMinimumSize(640, 480)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Hledat napříč moduly…")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._on_query_changed)
        self._search_edit.returnPressed.connect(self._on_search_submitted)

        self._results_list = QListWidget()
        self._results_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._results_list.itemDoubleClicked.connect(self._on_result_item_activated)
        self._results_list.itemActivated.connect(self._on_result_item_activated)

        self._status_label = QLabel(self.STATUS_QUERY_TOO_SHORT)

        self._button_box = QDialogButtonBox()
        self._open_button = self._button_box.addButton("Otevřít", QDialogButtonBox.ButtonRole.ActionRole)
        self._close_button = self._button_box.addButton("Zavřít", QDialogButtonBox.ButtonRole.RejectRole)
        self._open_button.clicked.connect(self._open_selected_result)
        self._close_button.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._search_edit)
        layout.addWidget(self._results_list, stretch=1)
        layout.addWidget(self._status_label)
        layout.addWidget(self._button_box)

        if initial_query.strip():
            self._search_edit.setText(initial_query.strip())
            self._run_search(initial_query.strip())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._search_edit.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
            return

        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self._search_edit.hasFocus():
                self._on_search_submitted()
                event.accept()
                return
            if self._results_list.hasFocus() or self._results_list.currentItem() is not None:
                self._open_selected_result()
                event.accept()
                return

        super().keyPressEvent(event)

    def _on_search_submitted(self) -> None:
        query = self._search_edit.text().strip()
        if not query:
            self._clear_results()
            self._status_label.setText(self.STATUS_QUERY_TOO_SHORT)
            return
        self._run_search(query)

    def _on_query_changed(self, text: str) -> None:
        query = text.strip()
        if not query:
            self._clear_results()
            self._status_label.setText(self.STATUS_QUERY_TOO_SHORT)
            return
        if len(query) < MIN_QUERY_LENGTH:
            self._clear_results()
            self._status_label.setText(self.STATUS_QUERY_TOO_SHORT)
            return
        self._run_search(query)

    def _run_search(self, query: str) -> None:
        if len(query.strip()) < MIN_QUERY_LENGTH:
            self._clear_results()
            self._status_label.setText(self.STATUS_QUERY_TOO_SHORT)
            return

        results = self._service.search(query)
        self._show_results(results)
        if not results:
            self._status_label.setText(self.STATUS_EMPTY)
        else:
            self._status_label.setText(f"Nalezeno: {len(results)}")

    def _clear_results(self) -> None:
        self._results_list.clear()

    def _show_results(self, results: list[GlobalSearchResult]) -> None:
        self._clear_results()
        if not results:
            return

        group_counts: dict[str, int] = {}
        for result in results:
            group_counts[result.group_label] = group_counts.get(result.group_label, 0) + 1

        previous_group = None
        for result in results:
            if result.group_label and result.group_label != previous_group:
                previous_group = result.group_label
                count = group_counts.get(result.group_label, 0)
                header = QListWidgetItem(f"{result.group_label} ({count})")
                header.setFlags(Qt.ItemFlag.NoItemFlags)
                header_font = header.font()
                header_font.setBold(True)
                header.setFont(header_font)
                self._results_list.addItem(header)

            item = QListWidgetItem()
            item.setData(_RESULT_ROLE, result)
            widget = self._build_result_widget(result)
            item.setSizeHint(widget.sizeHint())
            self._results_list.addItem(item)
            self._results_list.setItemWidget(item, widget)

        first_result = self._first_result_item()
        if first_result is not None:
            self._results_list.setCurrentItem(first_result)

    @staticmethod
    def _build_result_widget(result: GlobalSearchResult) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        title = QLabel(result.title or "—")
        title_font = QFont(title.font())
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        if result.subtitle:
            subtitle = QLabel(result.subtitle)
            subtitle.setWordWrap(True)
            layout.addWidget(subtitle)

        return widget

    def _first_result_item(self) -> QListWidgetItem | None:
        for row in range(self._results_list.count()):
            item = self._results_list.item(row)
            if item is not None and isinstance(item.data(_RESULT_ROLE), GlobalSearchResult):
                return item
        return None

    def _selected_result(self) -> GlobalSearchResult | None:
        item = self._results_list.currentItem()
        if item is None:
            return None
        result = item.data(_RESULT_ROLE)
        if isinstance(result, GlobalSearchResult):
            return result
        return None

    def _open_selected_result(self) -> None:
        result = self._selected_result()
        if result is not None:
            self._open_result(result)

    def _on_result_item_activated(self, item: QListWidgetItem) -> None:
        result = item.data(_RESULT_ROLE)
        if isinstance(result, GlobalSearchResult):
            self._open_result(result)

    def _open_result(self, result: GlobalSearchResult) -> None:
        try:
            if not self._service.can_open_result(result):
                self._status_label.setText(self.STATUS_OPEN_UNSUPPORTED)
                return

            if self._service.open_result(result, self._host):
                self.accept()
                return

            self._status_label.setText(self.STATUS_OPEN_FAILED)
        except Exception:
            logger.exception(
                "Failed to open search result %s/%s from dialog",
                result.entity_type,
                result.entity_id,
            )
            self._status_label.setText(self.STATUS_OPEN_ERROR)

    def result_items(self) -> list[GlobalSearchResult]:
        items: list[GlobalSearchResult] = []
        for row in range(self._results_list.count()):
            item = self._results_list.item(row)
            if item is None:
                continue
            result = item.data(_RESULT_ROLE)
            if isinstance(result, GlobalSearchResult):
                items.append(result)
        return items
