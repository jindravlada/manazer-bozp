"""Panel auditovaného procesu — pracovní karta vybraného kritéria."""

from PySide6.QtWidgets import QVBoxLayout, QWidget

from moduly.audity.ui.audit_knowledge_criterion_widget import AuditKnowledgeCriterionWidget


class AuditProcessKnowledgeWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.criterion_widget = AuditKnowledgeCriterionWidget()
        layout.addWidget(self.criterion_widget)

    def show_criterion(
        self,
        criterion: dict | None,
        *,
        process_id: str = "",
        process_label: str = "",
        process_purpose: str = "",
        criterion_label: str = "",
    ) -> None:
        self.criterion_widget.set_process_purpose(process_purpose)
        self.criterion_widget.set_criterion(
            criterion,
            area_id=process_id,
            area_label=process_label,
            section_label=criterion_label,
        )

    def clear_criterion(self) -> None:
        self.criterion_widget.set_criterion(None)

    def set_audit_id(self, audit_id: int | None) -> None:
        self.criterion_widget.set_audit_id(audit_id)

    def set_on_finding_saved(self, callback) -> None:
        self.criterion_widget.set_on_finding_saved(callback)

    def refresh_findings_display(self) -> None:
        self.criterion_widget.refresh()
