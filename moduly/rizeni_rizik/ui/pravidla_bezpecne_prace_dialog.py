"""Dialog kritérií pro generování Pravidel bezpečné práce."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QVBoxLayout,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.exposed_group_selector import ExposedGroupSelector
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    hazard_identification_service,
)
from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
    pravidla_bezpecne_prace_service,
)

DIALOG_TITLE = "Pravidla bezpečné práce"


class PravidlaBezpecnePraceDialog(QDialog):
    """Výběr ohrožené skupiny a hierarchie pracoviště pro generování PBP."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(DIALOG_TITLE)
        self.resize(480, 260)
        self._last_result: list | None = None
        self._last_export_path: Path | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.endangered_group = ExposedGroupSelector(self)
        self.operation = QComboBox()
        self.workplace = QComboBox()
        self.workplace_part = QComboBox()

        form.addRow("Ohrožená skupina *:", self.endangered_group)
        form.addRow("Provoz *:", self.operation)
        form.addRow("Pracoviště:", self.workplace)
        form.addRow("Část pracoviště:", self.workplace_part)
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        generate_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if generate_btn is not None:
            generate_btn.setText("Generovat")
        if close_btn is not None:
            close_btn.setText("Zavřít")
        buttons.accepted.connect(self._generate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.operation.currentIndexChanged.connect(self._on_operation_changed)
        self.workplace.currentIndexChanged.connect(self._on_workplace_changed)

        self._reload_operations()
        self._reset_workplaces()
        self._reset_workplace_parts()

    @property
    def last_result(self) -> list | None:
        return self._last_result

    @property
    def last_export_path(self) -> Path | None:
        return self._last_export_path

    def _generate(self) -> None:
        endangered_group_id = self.endangered_group.current_group_id()
        operation_id = self.operation.currentData()

        if endangered_group_id is None:
            QMessageBox.warning(self, DIALOG_TITLE, "Vyberte ohroženou skupinu.")
            return
        if operation_id is None:
            QMessageBox.warning(self, DIALOG_TITLE, "Vyberte provoz.")
            return

        workplace_id = self.workplace.currentData()
        workplace_part_id = self.workplace_part.currentData()
        if workplace_id is None:
            workplace_part_id = None

        self._last_result = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=endangered_group_id,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
        )

        if not self._last_result:
            self._last_export_path = None
            QMessageBox.information(
                self,
                DIALOG_TITLE,
                "Nebyla nalezena žádná platná pravidla bezpečné práce "
                "pro zadaný výběr.",
            )
            return

        self._last_export_path = pravidla_bezpecne_prace_service.open_document(
            endangered_group_id=endangered_group_id,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
            rules=self._last_result,
        )

        warnings = pravidla_bezpecne_prace_service.quality_warnings(self._last_result)
        if warnings:
            QMessageBox.information(
                self,
                DIALOG_TITLE,
                "Byla nalezena opatření, která nejsou formulována\n"
                "jako pravidla bezpečné práce pro zaměstnance.\n\n"
                "Doporučujeme upravit jejich znění.\n\n"
                f"Počet nalezených pravidel:\n{len(self._last_result)}\n\n"
                f"Nevhodně formulovaných:\n{len(warnings)}",
            )

        self.accept()

    def _on_operation_changed(self) -> None:
        self._reload_workplaces(self.operation.currentData())
        self._reset_workplace_parts()

    def _on_workplace_changed(self) -> None:
        self._reload_workplace_parts(self.workplace.currentData())

    def _reload_operations(self) -> None:
        self._populate_combo(
            self.operation,
            hazard_identification_service.get_active_operations(include_inactive=False),
            required=True,
        )

    def _reload_workplaces(self, operation_id: int | None) -> None:
        workplaces = hazard_identification_service.get_workplaces_for_operation(
            operation_id,
            include_inactive=False,
        )
        self._populate_combo(self.workplace, workplaces, required=False)
        self.workplace.setEnabled(operation_id is not None)

    def _reload_workplace_parts(self, workplace_id: int | None) -> None:
        parts = hazard_identification_service.get_workplace_parts_for_workplace(
            workplace_id,
            include_inactive=False,
        )
        self._populate_combo(self.workplace_part, parts, required=False)
        self.workplace_part.setEnabled(workplace_id is not None)

    def _reset_workplaces(self) -> None:
        self._populate_combo(self.workplace, [], required=False)
        self.workplace.setEnabled(False)

    def _reset_workplace_parts(self) -> None:
        self._populate_combo(self.workplace_part, [], required=False)
        self.workplace_part.setEnabled(False)

    @staticmethod
    def _populate_combo(combo: QComboBox, items, *, required: bool) -> None:
        combo.blockSignals(True)
        combo.clear()
        if not required:
            combo.addItem("", None)
        for item in items:
            combo.addItem(item.name, item.id)
        if required:
            combo.setCurrentIndex(-1)
        else:
            combo.setCurrentIndex(0)
        combo.blockSignals(False)
