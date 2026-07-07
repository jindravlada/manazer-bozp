from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QCompleter

from core.widgets.search_combo_box import SearchComboBox
from moduly.pravni_pozadavky.constants import legal_document_regulation_number
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service


class LegalDocumentNameSelector(SearchComboBox):
    """Výběr aktivního právního předpisu podle názvu, čísla nebo zkratky."""

    document_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(allow_custom_value=True)
        self._documents_by_id: dict[int, object] = {}
        self._updating = False
        self.currentTextChanged.connect(self._on_text_changed)
        self.currentIndexChanged.connect(self._on_index_changed)
        self.reload()

    def reload(self, *, selected_id: int | None = None) -> None:
        current_text = self.currentText().strip()
        documents = legal_document_service.list_all(include_inactive=False)

        if selected_id is not None:
            selected_document = legal_document_service.get_by_id(selected_id)
            if (
                selected_document is not None
                and not selected_document.active
                and all(item.id != selected_id for item in documents)
            ):
                documents = [selected_document, *documents]

        self.blockSignals(True)
        self.clear()
        self._documents_by_id = {}

        for document in documents:
            title = document.title.strip()
            if not title:
                title = f"Předpis #{document.id}"
            self._documents_by_id[document.id] = document
            self.addItem(title, document.id)

        completer_values: list[str] = []
        seen: set[str] = set()
        for document in documents:
            for token in self._document_search_tokens(document):
                normalized = token.casefold()
                if normalized in seen:
                    continue
                seen.add(normalized)
                completer_values.append(token)

        completer = QCompleter(completer_values, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(completer)

        if selected_id is not None:
            self.set_document_id(selected_id)
        elif current_text:
            self.setCurrentText(current_text)
        self.blockSignals(False)

    def current_document_id(self) -> int | None:
        text = self.currentText().strip()
        if not text:
            return None

        for index in range(self.count()):
            if self.itemText(index).strip() == text:
                document_id = self.itemData(index)
                if document_id is not None:
                    return int(document_id)

        document = self.find_document_by_text(text)
        return document.id if document is not None else None

    def current_document(self):
        document_id = self.current_document_id()
        if document_id is None:
            return None
        return self._documents_by_id.get(document_id) or legal_document_service.get_by_id(document_id)

    def set_document_id(self, document_id: int | None) -> None:
        if document_id is None:
            self.setCurrentText("")
            return

        document = self._documents_by_id.get(document_id)
        if document is None:
            document = legal_document_service.get_by_id(document_id)
        if document is None:
            self.setCurrentText("")
            return

        self._updating = True
        try:
            self.setCurrentText(document.title.strip())
        finally:
            self._updating = False

    def set_document_id_without_signal(self, document_id: int | None) -> None:
        self.blockSignals(True)
        try:
            self.set_document_id(document_id)
        finally:
            self.blockSignals(False)

    def find_document_by_text(self, text: str):
        normalized = text.strip().casefold()
        if not normalized:
            return None

        for document in self._documents_by_id.values():
            for token in self._document_search_tokens(document):
                if token.casefold() == normalized:
                    return document
        return None

    def regulation_number_for_current_document(self) -> str:
        document = self.current_document()
        if document is None:
            return ""
        return legal_document_regulation_number(document)

    def _document_search_tokens(self, document) -> list[str]:
        tokens: list[str] = []
        for value in (
            getattr(document, "title", ""),
            getattr(document, "short_title", ""),
            getattr(document, "number", ""),
            legal_document_regulation_number(document),
        ):
            cleaned = (value or "").strip()
            if cleaned:
                tokens.append(cleaned)
        return tokens

    def _on_text_changed(self, _text: str) -> None:
        if self._updating:
            return
        self.document_changed.emit()

    def _on_index_changed(self, _index: int) -> None:
        if self._updating:
            return
        self.document_changed.emit()

    def apply_search_text(self, text: str) -> None:
        self.setCurrentText(text)
        self.document_changed.emit()
