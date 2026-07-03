"""Dialog globálního vyhledávání."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.search import global_search_service
from core.search.constants import MIN_QUERY_LENGTH
from core.search.global_search_service import GlobalSearchService
from core.search.search_result import SearchResult

logger = logging.getLogger(__name__)

_RESULT_ROLE = Qt.ItemDataRole.UserRole


class GlobalSearchDialog(QDialog):
    STATUS_QUERY_TOO_SHORT = "Zadejte alespoň 2 znaky."
    STATUS_EMPTY = "Nic nenalezeno."
    STATUS_OPEN_FAILED = "Výsledek nelze otevřít."
    STATUS_OPEN_UNSUPPORTED = "Tento typ výsledku zatím nelze otevřít."
    STATUS_OPEN_ERROR = "Chyba při otevírání výsledku."

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        search_service: GlobalSearchService | None = None,
        host=None,
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

        self._results_list = QListWidget()
        self._results_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._results_list.itemDoubleClicked.connect(self._on_result_item_activated)
        self._results_list.itemActivated.connect(self._on_result_item_activated)

        self._status_label = QLabel(self.STATUS_QUERY_TOO_SHORT)

        layout = QVBoxLayout(self)
        layout.addWidget(self._search_edit)
        layout.addWidget(self._results_list, stretch=1)
        layout.addWidget(self._status_label)

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
                event.accept()
                return

        super().keyPressEvent(event)

    def _on_query_changed(self, text: str) -> None:
        query = text.strip()
        if len(query) < MIN_QUERY_LENGTH:
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

    def _show_results(self, results: list[SearchResult]) -> None:
        self._clear_results()
        previous_module = None

        for result in results:
            if result.module_label and result.module_label != previous_module:
                previous_module = result.module_label
                header = QListWidgetItem(previous_module)
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

    @staticmethod
    def _build_result_widget(result: SearchResult) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        module_label = QLabel(result.module_label or "—")
        module_font = QFont(module_label.font())
        module_font.setBold(True)
        module_label.setFont(module_font)
        layout.addWidget(module_label)

        title = QLabel(result.title or "—")
        layout.addWidget(title)

        if result.subtitle:
            subtitle = QLabel(result.subtitle)
            subtitle.setWordWrap(True)
            layout.addWidget(subtitle)

        if result.description:
            description = QLabel(result.description)
            description.setWordWrap(True)
            layout.addWidget(description)

        return widget

    def _on_result_item_activated(self, item: QListWidgetItem) -> None:
        result = item.data(_RESULT_ROLE)
        if isinstance(result, SearchResult):
            self._open_result(result)

    def _open_result(self, result: SearchResult) -> None:
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
                result.source_type,
                result.source_id,
            )
            self._status_label.setText(self.STATUS_OPEN_ERROR)

    def result_items(self) -> list[SearchResult]:
        items: list[SearchResult] = []
        for row in range(self._results_list.count()):
            item = self._results_list.item(row)
            if item is None:
                continue
            result = item.data(_RESULT_ROLE)
            if isinstance(result, SearchResult):
                items.append(result)
        return items
