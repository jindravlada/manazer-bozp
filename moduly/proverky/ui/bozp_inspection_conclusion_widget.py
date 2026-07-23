from datetime import date

from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.nullable_date_edit import NullableDateEdit
from moduly.proverky.constants import (
    INSPECTION_COMPLETION_CONFIRM_MESSAGE,
    INSPECTION_DETAILED_REPORT_BUTTON_LABEL,
    INSPECTION_DETAILED_REPORT_DIALOG_TITLE,
    INSPECTION_PROTOCOL_BUTTON_LABEL,
    INSPECTION_PROTOCOL_DIALOG_TITLE,
)
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
from moduly.proverky.sluzby.protokol_proverky_service import protokol_proverky_service


class BozpInspectionConclusionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.inspection = None
        self._on_complete = None

        layout = QVBoxLayout(self)

        self.info_label = QLabel("Závěr prověrky bude dostupný až po uložení prověrky.")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        summary_group = QGroupBox("Souhrn")
        summary_form = QFormLayout(summary_group)
        self.findings_total_label = QLabel("0")
        self.findings_open_label = QLabel("0")
        self.tasks_total_label = QLabel("0")
        self.tasks_active_label = QLabel("0")
        summary_form.addRow("Zjištění celkem:", self.findings_total_label)
        summary_form.addRow("Otevřená zjištění:", self.findings_open_label)
        summary_form.addRow("Úkoly celkem:", self.tasks_total_label)
        summary_form.addRow("Aktivní úkoly:", self.tasks_active_label)
        layout.addWidget(summary_group)

        strengths_group = QGroupBox("Silné stránky systému")
        strengths_layout = QVBoxLayout(strengths_group)
        self.silne_stranky_edit = QTextEdit()
        self.silne_stranky_edit.setPlaceholderText(
            "Každý řádek bude ve zprávě uveden jako samostatná silná stránka."
        )
        self.silne_stranky_edit.setMinimumHeight(90)
        strengths_layout.addWidget(self.silne_stranky_edit)
        layout.addWidget(strengths_group)

        recommendation_group = QGroupBox("Doporučení vedoucího prověrky")
        recommendation_layout = QVBoxLayout(recommendation_group)
        self.doporuceni_edit = QTextEdit()
        self.doporuceni_edit.setPlaceholderText(
            "Shrňte hlavní doporučení pro kontrolované pracoviště."
        )
        self.doporuceni_edit.setMinimumHeight(90)
        recommendation_layout.addWidget(self.doporuceni_edit)
        layout.addWidget(recommendation_group)

        completion_group = QGroupBox("Dokončení prověrky")
        completion_form = QFormLayout(completion_group)
        self.status_label = QLabel("—")
        self.status_label.setObjectName("InfoText")
        self.finished_at_edit = NullableDateEdit()
        completion_form.addRow("Stav prověrky:", self.status_label)
        completion_form.addRow("Datum ukončení:", self.finished_at_edit)
        layout.addWidget(completion_group)

        self.complete_btn = QPushButton("Dokončit prověrku")
        self.complete_btn.clicked.connect(self._complete_inspection)
        layout.addWidget(self.complete_btn)

        self.protocol_btn = QPushButton(INSPECTION_PROTOCOL_BUTTON_LABEL)
        self.protocol_btn.clicked.connect(self._export_protocol)
        layout.addWidget(self.protocol_btn)

        self.detailed_report_btn = QPushButton(INSPECTION_DETAILED_REPORT_BUTTON_LABEL)
        self.detailed_report_btn.clicked.connect(self._export_detailed_report)
        layout.addWidget(self.detailed_report_btn)

        layout.addStretch()

        self._update_state()

    def set_complete_handler(self, handler) -> None:
        self._on_complete = handler

    def load_inspection(self, inspection) -> None:
        self.inspection = inspection
        self.refresh()

    def refresh(self) -> None:
        inspection_id = self.inspection.id if self.inspection is not None else None
        self._update_state()

        if inspection_id is None:
            self.status_label.setText("—")
            self.finished_at_edit.clear_date()
            self.silne_stranky_edit.clear()
            self.doporuceni_edit.clear()
            self.findings_total_label.setText("0")
            self.findings_open_label.setText("0")
            self.tasks_total_label.setText("0")
            self.tasks_active_label.setText("0")
            return

        summary = bozp_inspection_service.get_conclusion_summary(inspection_id)
        self.findings_total_label.setText(str(summary["findings_total"]))
        self.findings_open_label.setText(str(summary["findings_open"]))
        self.tasks_total_label.setText(str(summary["tasks_total"]))
        self.tasks_active_label.setText(str(summary["tasks_active"]))

        started_at = getattr(self.inspection, "started_at", None)
        finished_at = getattr(self.inspection, "finished_at", None)
        status = bozp_inspection_service.derive_status(started_at, finished_at)
        self.status_label.setText(status)

        if finished_at is not None:
            self.finished_at_edit.set_date_value(finished_at)
        else:
            self.finished_at_edit.clear_date()

        self.silne_stranky_edit.setPlainText(getattr(self.inspection, "silne_stranky", "") or "")
        self.doporuceni_edit.setPlainText(getattr(self.inspection, "doporuceni_vedouciho", "") or "")

        self.complete_btn.setEnabled(finished_at is None)

    def get_data(self) -> dict:
        return {
            "finished_at": self.finished_at_edit.get_date(),
            "silne_stranky": self.silne_stranky_edit.toPlainText().strip(),
            "doporuceni_vedouciho": self.doporuceni_edit.toPlainText().strip(),
        }

    def _update_state(self) -> None:
        enabled = self.inspection is not None and self.inspection.id is not None
        self.info_label.setVisible(not enabled)
        self.protocol_btn.setEnabled(enabled)
        self.detailed_report_btn.setEnabled(enabled)

    def _export_protocol(self) -> None:
        if self.inspection is None or self.inspection.id is None:
            QMessageBox.information(
                self,
                INSPECTION_PROTOCOL_DIALOG_TITLE,
                "Prověrku je nutné nejdříve uložit.",
            )
            return

        warning = protokol_proverky_service.incomplete_warning(self.inspection)
        if warning:
            QMessageBox.warning(self, INSPECTION_PROTOCOL_DIALOG_TITLE, warning)

        try:
            protokol_proverky_service.open_for_inspection(self.inspection)
        except Exception as exc:
            QMessageBox.warning(
                self,
                INSPECTION_PROTOCOL_DIALOG_TITLE,
                f"Protokol se nepodařilo vygenerovat.\n\n{exc}",
            )

    def _export_detailed_report(self) -> None:
        if self.inspection is None or self.inspection.id is None:
            QMessageBox.information(
                self,
                INSPECTION_DETAILED_REPORT_DIALOG_TITLE,
                "Prověrku je nutné nejdříve uložit.",
            )
            return

        warning = protokol_proverky_service.incomplete_warning(
            self.inspection, detailed=True
        )
        if warning:
            QMessageBox.warning(self, INSPECTION_DETAILED_REPORT_DIALOG_TITLE, warning)

        try:
            protokol_proverky_service.open_detailed_report_for_inspection(self.inspection)
        except Exception as exc:
            QMessageBox.warning(
                self,
                INSPECTION_DETAILED_REPORT_DIALOG_TITLE,
                f"Podrobnou zprávu se nepodařilo vygenerovat.\n\n{exc}",
            )

    def _complete_inspection(self) -> None:
        if self.inspection is None or self.inspection.id is None:
            QMessageBox.information(self, "Závěr", "Prověrku je nutné nejdříve uložit.")
            return

        inspection_id = self.inspection.id
        blockers = bozp_inspection_service.get_completion_blockers(inspection_id)
        if blockers.has_blockers():
            answer = QMessageBox.question(
                self,
                "Dokončení prověrky",
                INSPECTION_COMPLETION_CONFIRM_MESSAGE,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return

        finished_at = self.finished_at_edit.get_date()
        if finished_at is None:
            finished_at = date.today()
            self.finished_at_edit.set_date_value(finished_at)

        try:
            bozp_inspection_service.validate_date_order(
                getattr(self.inspection, "started_at", None),
                finished_at,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Dokončení prověrky", str(exc))
            return

        if self._on_complete is None:
            return

        saved = self._on_complete(finished_at=finished_at)
        if saved:
            self.refresh()
