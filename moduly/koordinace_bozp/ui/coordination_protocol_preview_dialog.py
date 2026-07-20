from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    add_work_dialog_footer,
    configure_resizable_form_dialog,
    create_close_box,
)
from moduly.koordinace_bozp.sluzby.coordination_lifecycle_service import (
    protocol_version_mark,
)
from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
    CoordinationProtocolBuilderError,
    ProtocolBuildResult,
    coordination_protocol_builder,
)
from moduly.koordinace_bozp.sluzby.coordination_protocol_document import (
    BLOCK_KIND_BLANK,
    BLOCK_KIND_BULLET,
    BLOCK_KIND_HEADING,
    BLOCK_KIND_INDENTED,
    BLOCK_KIND_NUMBERED_HEADING,
    BLOCK_KIND_PARAGRAPH,
    BLOCK_KIND_PBP_RULE,
    BLOCK_KIND_SIGNATURE_LINE,
    BLOCK_KIND_SUBTITLE,
    BLOCK_KIND_TITLE,
    BLOCK_STYLE_BULLET,
    BLOCK_STYLE_EMPLOYER_ABBR,
    BLOCK_STYLE_HEADING,
    BLOCK_STYLE_LABEL,
    BLOCK_STYLE_TITLE,
    document_blocks_from_dict,
)
from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
    CoordinationProtocolOdtRendererError,
    coordination_protocol_odt_renderer,
)


class CoordinationProtocolPreviewDialog(QDialog):
    """Read-only náhled koordinačního protokolu (BUILDER-COORD-1)."""

    def __init__(self, parent=None, *, coordination_id: int):
        super().__init__(parent)
        self.coordination_id = coordination_id
        self._build_result: ProtocolBuildResult | None = None
        self.setWindowTitle("Náhled koordinačního protokolu")
        configure_resizable_form_dialog(
            self,
            width=820,
            height=700,
            min_width=560,
            min_height=420,
        )

        layout = QVBoxLayout(self)
        self.status_label = QLabel()
        font = QFont(self.status_label.font())
        font.setBold(True)
        font.setPointSize(font.pointSize() + 1)
        self.status_label.setFont(font)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(8, 8, 8, 8)
        self.body_layout.setSpacing(4)
        scroll.setWidget(self.body)
        layout.addWidget(scroll, 1)

        self.export_btn = QPushButton("Export ODT")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_odt)
        buttons = create_close_box(self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        add_work_dialog_footer(
            layout,
            work_widgets=[self.export_btn],
            buttons=buttons,
        )

        self._load()

    def _load(self) -> None:
        try:
            result = coordination_protocol_builder.build(self.coordination_id)
        except CoordinationProtocolBuilderError as error:
            self._build_result = None
            self.export_btn.setEnabled(False)
            self.status_label.setText(str(error))
            return
        self._build_result = result
        self.export_btn.setEnabled(True)
        self._render(result)

    def export_odt(self) -> None:
        """Exportuje ODT z již sestavených dat náhledu (bez nového sestavení)."""
        if self._build_result is None:
            QMessageBox.warning(
                self,
                "Export ODT",
                "Protokol není připraven k exportu.",
            )
            return
        basics = (self._build_result.protocol_data or {}).get("basics") or {}
        number = basics.get("coordination_number") or "protokol"
        suggested = f"KoordinacniProtokol-{number}.odt"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export ODT",
            suggested,
            "ODT (*.odt)",
        )
        if not path:
            return
        try:
            exported = coordination_protocol_odt_renderer.render_from_result(
                path,
                self._build_result,
            )
        except CoordinationProtocolOdtRendererError as error:
            QMessageBox.warning(self, "Export ODT", str(error))
            return
        QMessageBox.information(
            self,
            "Export ODT",
            f"Soubor byl uložen:\n{exported}",
        )

    def _render(self, result: ProtocolBuildResult) -> None:
        while self.body_layout.count():
            item = self.body_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        warning_count = result.summary.warnings_total
        if warning_count == 0:
            status_text = "Připraveno bez upozornění"
            self.status_label.setStyleSheet("color: #2e7d32;")
        else:
            status_text = f"Protokol obsahuje {warning_count} upozornění"
            self.status_label.setStyleSheet("color: #ef6c00;")
        basics = (result.protocol_data or {}).get("basics") or {}
        version_mark = protocol_version_mark(basics.get("status"))
        if version_mark:
            status_text = f"{version_mark} – {status_text}"
        self.status_label.setText(status_text)

        blocks = document_blocks_from_dict(
            (result.protocol_data or {}).get("document")
        )
        self._render_document(blocks)
        self.body_layout.addStretch(1)

    def _render_document(self, blocks) -> None:
        for block in blocks:
            if block.kind == BLOCK_KIND_BLANK:
                self.body_layout.addSpacing(8)
                continue
            label = QLabel()
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            font = QFont(label.font())
            use_rich = bool(block.runs) and any(is_bold for _, is_bold in block.runs)
            if use_rich:
                label.setTextFormat(Qt.TextFormat.RichText)
                label.setText(self._rich_text_from_runs(block.runs))
            else:
                label.setTextFormat(Qt.TextFormat.PlainText)
                label.setText(self._label_text(block))
            if block.kind == BLOCK_KIND_TITLE or block.style == BLOCK_STYLE_TITLE:
                font.setPointSize(font.pointSize() + 3)
                font.setBold(True)
                label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            elif block.kind in (
                BLOCK_KIND_HEADING,
                BLOCK_KIND_NUMBERED_HEADING,
            ) or block.style == BLOCK_STYLE_HEADING:
                font.setBold(True)
            elif block.kind == BLOCK_KIND_SUBTITLE:
                font.setBold(True)
                label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            elif (
                not use_rich
                and (
                    block.bold
                    or block.style
                    in (
                        BLOCK_STYLE_EMPLOYER_ABBR,
                        BLOCK_STYLE_LABEL,
                    )
                )
            ):
                font.setBold(True)
            elif block.kind == BLOCK_KIND_BULLET or block.style == BLOCK_STYLE_BULLET:
                label.setContentsMargins(16, 0, 0, 0)
            elif block.kind == BLOCK_KIND_INDENTED:
                label.setContentsMargins(32, 0, 0, 0)
            elif block.kind == BLOCK_KIND_SIGNATURE_LINE:
                label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            label.setFont(font)
            self.body_layout.addWidget(label)

    @staticmethod
    def _escape_html(value: str) -> str:
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    @classmethod
    def _rich_text_from_runs(cls, runs) -> str:
        parts = []
        for text, is_bold in runs:
            escaped = cls._escape_html(text)
            if is_bold:
                parts.append(f"<b>{escaped}</b>")
            else:
                parts.append(escaped)
        return "".join(parts)

    @staticmethod
    def _label_text(block) -> str:
        text = (block.text or "").strip()
        if block.kind == BLOCK_KIND_NUMBERED_HEADING:
            return f"{block.level}. {text}" if text else f"{block.level}."
        if block.kind == BLOCK_KIND_BULLET:
            return f"• {text}" if text else "•"
        if block.kind == BLOCK_KIND_INDENTED:
            return text
        if block.runs:
            return "".join(str(item[0]) for item in block.runs)
        if block.kind in (
            BLOCK_KIND_PARAGRAPH,
            BLOCK_KIND_HEADING,
            BLOCK_KIND_SIGNATURE_LINE,
            BLOCK_KIND_TITLE,
            BLOCK_KIND_SUBTITLE,
            BLOCK_KIND_PBP_RULE,
        ):
            return text
        return text
