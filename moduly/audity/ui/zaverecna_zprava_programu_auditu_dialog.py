"""Dialog pro vytvoření závěrečné zprávy programu interních auditů."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
)

from core.widgets.thp_worker_selector import ThpWorkerSelector
from moduly.audity.sluzby.audit_program_final_report_service import (
    audit_program_final_report_service,
)
from moduly.audity.sluzby.audit_program_service import audit_program_service
from moduly.audity.sluzby.zaverecna_zprava_programu_auditu_service import (
    zaverecna_zprava_programu_auditu_service,
)


class ZaverecnaZpravaProgramuAudituDialog(QDialog):
    def __init__(self, parent=None, *, program_id: int | None = None):
        super().__init__(parent)

        self.setWindowTitle("Závěrečná zpráva programu")
        self.resize(720, 680)

        layout = QVBoxLayout(self)

        selection_group = QGroupBox("Vyber auditní program")
        selection_form = QFormLayout(selection_group)
        self.program_combo = QComboBox()
        selection_form.addRow("Auditní program:", self.program_combo)
        self.zpracoval_selector = ThpWorkerSelector(include_empty=True)
        selection_form.addRow("Zpracoval:", self.zpracoval_selector)
        layout.addWidget(selection_group)

        manual_group = QGroupBox("Obsah zprávy")
        manual_layout = QVBoxLayout(manual_group)

        self.silne_stranky_edit = QTextEdit()
        self.silne_stranky_edit.setPlaceholderText(
            "Silné stránky systému – každý řádek jako samostatná položka."
        )
        self.silne_stranky_edit.setMinimumHeight(80)
        manual_layout.addWidget(self.silne_stranky_edit)

        self.hlavni_slabiny_edit = QTextEdit()
        self.hlavni_slabiny_edit.setPlaceholderText(
            "Hlavní slabiny systému – každý řádek jako samostatná položka."
        )
        self.hlavni_slabiny_edit.setMinimumHeight(80)
        manual_layout.addWidget(self.hlavni_slabiny_edit)

        self.doporuceni_edit = QTextEdit()
        self.doporuceni_edit.setPlaceholderText(
            "Doporučení pro nový program auditů."
        )
        self.doporuceni_edit.setMinimumHeight(80)
        manual_layout.addWidget(self.doporuceni_edit)

        layout.addWidget(manual_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_btn is not None:
            ok_btn.setText("Vytvořit zprávu")
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn is not None:
            cancel_btn.setText("Zrušit")
        buttons.accepted.connect(self._create_report)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.program_combo.currentIndexChanged.connect(self._load_program_content)
        self._populate_programs(program_id)

    def selected_program_id(self) -> int | None:
        value = self.program_combo.currentData()
        return int(value) if value is not None else None

    def _populate_programs(self, selected_program_id: int | None) -> None:
        programs = audit_program_service.list_programs()
        self.program_combo.blockSignals(True)
        self.program_combo.clear()
        if not programs:
            self.program_combo.addItem("— chybí auditní program —", None)
            self.program_combo.setEnabled(False)
        else:
            self.program_combo.setEnabled(True)
            for program in programs:
                self.program_combo.addItem(program.name, program.id)
            if selected_program_id is not None:
                index = self.program_combo.findData(selected_program_id)
                if index >= 0:
                    self.program_combo.setCurrentIndex(index)
        self.program_combo.blockSignals(False)
        self._load_program_content()

    def _load_program_content(self) -> None:
        program_id = self.selected_program_id()
        if program_id is None:
            self.silne_stranky_edit.clear()
            self.hlavni_slabiny_edit.clear()
            self.doporuceni_edit.clear()
            self.zpracoval_selector.set_person_id(
                audit_program_final_report_service.get_last_preparer_worker_id()
            )
            return

        report = audit_program_final_report_service.get_for_program(program_id)
        if report is None:
            self.silne_stranky_edit.clear()
            self.hlavni_slabiny_edit.clear()
            self.doporuceni_edit.clear()
            worker_id = audit_program_final_report_service.get_last_preparer_worker_id()
        else:
            self.silne_stranky_edit.setPlainText(report.silne_stranky or "")
            self.hlavni_slabiny_edit.setPlainText(report.hlavni_slabiny or "")
            self.doporuceni_edit.setPlainText(report.doporuceni_novy_program or "")
            worker_id = audit_program_final_report_service.resolve_preparer_worker_id(report)
        self.zpracoval_selector.set_person_id(worker_id)

    def _create_report(self) -> None:
        program_id = self.selected_program_id()
        if program_id is None:
            QMessageBox.warning(
                self,
                "Závěrečná zpráva programu",
                "Pro vytvoření závěrečné zprávy je nutné vybrat auditní program.",
            )
            return
        try:
            audit_program_final_report_service.save_for_program(
                program_id,
                silne_stranky=self.silne_stranky_edit.toPlainText(),
                hlavni_slabiny=self.hlavni_slabiny_edit.toPlainText(),
                doporuceni_novy_program=self.doporuceni_edit.toPlainText(),
                zpracoval_worker_id=self.zpracoval_selector.current_person_id(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Závěrečná zpráva programu", str(exc))
            return
        try:
            zaverecna_zprava_programu_auditu_service.open_for_program(program_id)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Závěrečná zpráva programu",
                f"Zprávu se nepodařilo vygenerovat.\n\n{exc}",
            )
            return
        self.accept()
