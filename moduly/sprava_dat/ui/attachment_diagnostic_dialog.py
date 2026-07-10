from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from core.services.attachment_backup_diagnostic_service import (
    AttachmentBackupDiagnostic,
    attachment_backup_diagnostic_service,
)
from core.widgets.dialog_utils import configure_resizable_form_dialog


class AttachmentDiagnosticDialog(QDialog):
    """Dialog s výsledky read-only kontroly příloh."""

    def __init__(
        self,
        parent=None,
        *,
        diagnostic: AttachmentBackupDiagnostic | None = None,
    ):
        super().__init__(parent)

        self.setWindowTitle("Kontrola příloh")
        configure_resizable_form_dialog(self, width=720, height=520, min_width=560, min_height=420)

        layout = QVBoxLayout(self)

        self.report_view = QTextEdit()
        self.report_view.setReadOnly(True)
        self.report_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        report_font = QFont(self.report_view.font())
        report_font.setStyleHint(QFont.StyleHint.Monospace)
        report_font.setFamily("Monospace")
        self.report_view.setFont(report_font)
        layout.addWidget(self.report_view, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close_btn = QPushButton("Zavřít")
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        result = diagnostic or attachment_backup_diagnostic_service.diagnose_workspace()
        self.report_view.setPlainText(
            attachment_backup_diagnostic_service.format_workspace_report(result)
        )
