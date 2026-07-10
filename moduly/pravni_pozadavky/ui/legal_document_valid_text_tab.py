from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from moduly.pravni_pozadavky.sluzby.legal_document_valid_text_service import (
    legal_document_valid_text_service,
)


class LegalDocumentValidTextTab(QWidget):
    """Read-only náhled platného znění vybrané verze předpisu."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        document_id: int | None = None,
        version_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.document_id = document_id
        self.version_id = version_id
        self._loaded = False
        self._paragraph_anchors: dict[str, str] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("🔍 Hledat v předpisu:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Text nebo číslo paragrafu, např. 101 nebo § 101")
        self.search_input.returnPressed.connect(self._find_next)
        search_row.addWidget(self.search_input, 1)

        self.find_button = QPushButton("Najít")
        self.find_button.clicked.connect(self._find_next)
        search_row.addWidget(self.find_button)

        self.case_sensitive_checkbox = QCheckBox("Rozlišovat velikost písmen")
        search_row.addWidget(self.case_sensitive_checkbox)
        self.whole_word_checkbox = QCheckBox("Pouze celé slovo")
        search_row.addWidget(self.whole_word_checkbox)
        layout.addLayout(search_row)

        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(False)
        self.text_browser.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        layout.addWidget(self.text_browser, 1)

    def refresh(self) -> None:
        if self.version_id is None:
            self._loaded = False
            self._paragraph_anchors = {}
            self.text_browser.setHtml(
                "<p><i>Platné znění bude dostupné po uložení verze předpisu.</i></p>"
            )
            return
        if not self._loaded:
            self._load_content()

    def _load_content(self) -> None:
        if self.version_id is None:
            return

        document = legal_document_valid_text_service.compose_version(self.version_id)
        self._paragraph_anchors = dict(document.paragraph_anchors)
        if not document.html.strip():
            self.text_browser.setHtml("<p><i>Verze zatím neobsahuje žádná ustanovení.</i></p>")
        else:
            self.text_browser.setHtml(document.html)
        self._loaded = True

    def _find_flags(self) -> QTextDocument.FindFlag:
        flags = QTextDocument.FindFlag(0)
        if self.case_sensitive_checkbox.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        if self.whole_word_checkbox.isChecked():
            flags |= QTextDocument.FindFlag.FindWholeWords
        return flags

    def _find_next(self) -> None:
        if not self._loaded:
            self.refresh()
        if self.version_id is None:
            return

        query = self.search_input.text().strip()
        if not query:
            return

        paragraph = legal_document_valid_text_service.parse_paragraph_query(query)
        if paragraph is not None:
            anchor = self._paragraph_anchors.get(paragraph)
            if anchor:
                self.text_browser.scrollToAnchor(anchor)
                cursor = self.text_browser.textCursor()
                cursor.setPosition(0)
                self.text_browser.setTextCursor(cursor)
                search_term = f"§ {paragraph}"
                if not self.text_browser.find(search_term, self._find_flags()):
                    self.text_browser.find(search_term, self._find_flags())
                return

        if not self.text_browser.find(query, self._find_flags()):
            cursor = self.text_browser.textCursor()
            cursor.setPosition(0)
            self.text_browser.setTextCursor(cursor)
            self.text_browser.find(query, self._find_flags())
