from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
)

from moduly.vysetrovani_mu.ui.ishikawa_cause_chain import (
    build_cause_chain_text,
    format_rejected_cause_chain_warning_text,
)
from moduly.vysetrovani_mu.ui.ishikawa_cause_chain_graph import MuIshikawaChainGraphWidget


class MuIshikawaChainDialog(QDialog):
    def __init__(self, parent=None, *, causes: list[dict]):
        super().__init__(parent)

        self.setWindowTitle("Řetězec příčin")

        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        warning_text = format_rejected_cause_chain_warning_text(causes)
        self._warning_label = QLabel(warning_text)
        self._warning_label.setWordWrap(True)
        self._warning_label.setVisible(bool(warning_text))
        if warning_text:
            self._warning_label.setStyleSheet(
                "color: #8a4b00; background: #fff4e5; border: 1px solid #f0c987; "
                "border-radius: 4px; padding: 8px;"
            )

        chain_label = QLabel(build_cause_chain_text(causes))
        chain_label.setWordWrap(False)
        chain_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        chain_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        chain_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        chain_font = chain_label.font()
        chain_font.setFamily("Monospace")
        chain_font.setStyleHint(chain_font.StyleHint.Monospace)
        chain_label.setFont(chain_font)

        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        if warning_text:
            text_layout.addWidget(self._warning_label)
        text_layout.addWidget(chain_label, 1)

        text_scroll = QScrollArea()
        text_scroll.setWidgetResizable(True)
        text_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        text_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        text_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        text_scroll.setWidget(text_container)
        tabs.addTab(text_scroll, "Text")

        self._graph_widget = MuIshikawaChainGraphWidget()
        self._graph_widget.set_causes(causes, warning_text=warning_text)
        tabs.addTab(self._graph_widget, "Graf")
        tabs.currentChanged.connect(
            lambda index: self._graph_widget.refit() if tabs.widget(index) is self._graph_widget else None
        )

        layout.addWidget(tabs)

        footer = QHBoxLayout()
        self.export_pdf_btn = QPushButton("Export do PDF")
        self.export_pdf_btn.clicked.connect(self._export_pdf)
        self.export_pdf_btn.setEnabled(self._graph_widget.can_export_to_pdf())
        footer.addWidget(self.export_pdf_btn)
        footer.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Zavřít")
        buttons.rejected.connect(self.reject)
        footer.addWidget(buttons)
        layout.addLayout(footer)

        self.showMaximized()

    def _export_pdf(self) -> None:
        if not self._graph_widget.can_export_to_pdf():
            QMessageBox.information(
                self,
                "Export do PDF",
                self._graph_widget.export_message()
                or "Graf řetězce příčin nelze exportovat.",
            )
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export do PDF",
            "retezec_pricin.pdf",
            "PDF soubory (*.pdf)",
        )
        if not path:
            return

        if not path.lower().endswith(".pdf"):
            path = f"{path}.pdf"

        if not self._graph_widget.export_to_pdf(path):
            QMessageBox.warning(
                self,
                "Export do PDF",
                "Graf se nepodařilo exportovat do PDF.",
            )
            return

        QMessageBox.information(
            self,
            "Export do PDF",
            f"Graf byl uložen do souboru:\n{path}",
        )
