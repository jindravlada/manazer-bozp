from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.performance_evaluation_explanation_dialog import (
    PerformanceEvaluationExplanationDialog,
)
from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.audity.sluzby.audit_annual_export_context_service import (
    audit_annual_export_context_service,
)
from moduly.audity.sluzby.audit_annual_report_service import audit_annual_report_service
from moduly.audity.sluzby.audit_service import audit_service
from moduly.audity.sluzby.rocni_zprava_auditu_service import rocni_zprava_auditu_service


class RocniZpravaAudituDialog(QDialog):
    """Dialog pro vytvoření roční zprávy z interních auditů."""

    def __init__(self, parent=None, *, year: int | None = None):
        super().__init__(parent)

        self.setWindowTitle("Roční zpráva z auditů")
        self.resize(720, 620)

        layout = QVBoxLayout(self)

        year_group = QGroupBox("Vyber rok")
        year_form = QFormLayout(year_group)
        self.year_combo = QComboBox()
        self._populate_years(year)
        year_form.addRow("Rok:", self.year_combo)
        self.zpracoval_selector = ThpWorkerSelector(include_empty=True)
        year_form.addRow("Zpracoval:", self.zpracoval_selector)
        layout.addWidget(year_group)

        manual_group = QGroupBox("Obsah zprávy")
        manual_layout = QVBoxLayout(manual_group)

        self.silne_stranky_edit = QTextEdit()
        self.silne_stranky_edit.setPlaceholderText(
            "Silné stránky systému řízení – každý řádek jako samostatná položka."
        )
        self.silne_stranky_edit.setMinimumHeight(80)
        manual_layout.addWidget(self.silne_stranky_edit)

        self.top_priority_edit = QTextEdit()
        self.top_priority_edit.setPlaceholderText(
            "TOP priority na příští rok – hlavní cíle systému řízení."
        )
        self.top_priority_edit.setMinimumHeight(80)
        manual_layout.addWidget(self.top_priority_edit)

        self.doporuceni_edit = QTextEdit()
        self.doporuceni_edit.setPlaceholderText(
            "Doporučení auditora."
        )
        self.doporuceni_edit.setMinimumHeight(80)
        manual_layout.addWidget(self.doporuceni_edit)

        layout.addWidget(manual_group)

        self.explanation_btn = QPushButton("🧠 Vysvětlení hodnocení")
        self.explanation_btn.clicked.connect(self._show_rating_explanation)
        layout.addWidget(self.explanation_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setText("Vytvořit")
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn is not None:
            cancel_btn.setText("Zrušit")
        buttons.accepted.connect(self._create_report)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.year_combo.currentIndexChanged.connect(self._load_year_content)
        self._load_year_content()

    def selected_year(self) -> int:
        return int(self.year_combo.currentData())

    def _populate_years(self, selected_year: int | None) -> None:
        current_year = date.today().year
        years = {current_year}
        for audit in audit_service.get_all():
            if audit.year is not None:
                years.add(audit.year)
            if audit.audit_date is not None:
                years.add(audit.audit_date.year)

        if selected_year is not None:
            years.add(selected_year)

        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        for year in sorted(years, reverse=True):
            self.year_combo.addItem(str(year), year)
        if selected_year is not None:
            index = self.year_combo.findData(selected_year)
            if index >= 0:
                self.year_combo.setCurrentIndex(index)
        self.year_combo.blockSignals(False)

    def _load_year_content(self) -> None:
        year = self.selected_year()
        report = audit_annual_report_service.get_for_year(year)
        if report is None:
            self.silne_stranky_edit.clear()
            self.top_priority_edit.clear()
            self.doporuceni_edit.clear()
            worker_id = audit_annual_report_service.get_last_preparer_worker_id()
        else:
            self.silne_stranky_edit.setPlainText(report.silne_stranky or "")
            self.top_priority_edit.setPlainText(report.top_priority or "")
            self.doporuceni_edit.setPlainText(report.doporuceni_specialisty or "")
            worker_id = audit_annual_report_service.resolve_preparer_worker_id(report)
        self.zpracoval_selector.set_person_id(worker_id)

    def _show_rating_explanation(self) -> None:
        year = self.selected_year()
        try:
            explanation = audit_annual_export_context_service.build_evaluation_explanation(year)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Vysvětlení hodnocení",
                f"Hodnocení se nepodařilo vypočítat.\n\n{exc}",
            )
            return

        dialog = PerformanceEvaluationExplanationDialog(self, explanation=explanation)
        dialog.exec()

    def _create_report(self) -> None:
        year = self.selected_year()
        audit_annual_report_service.save_for_year(
            year,
            silne_stranky=self.silne_stranky_edit.toPlainText(),
            top_priority=self.top_priority_edit.toPlainText(),
            doporuceni_specialisty=self.doporuceni_edit.toPlainText(),
            zpracoval_worker_id=self.zpracoval_selector.current_person_id(),
        )
        try:
            rocni_zprava_auditu_service.open_for_year(year)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Roční zpráva z auditů",
                f"Zprávu se nepodařilo vygenerovat.\n\n{exc}",
            )
            return
        self.accept()
