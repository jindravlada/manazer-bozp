"""Dialog kritérií pro generování Pravidel bezpečné práce."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.multi_exposed_group_selector import MultiExposedGroupSelector
from core.widgets.multi_responsibility_role_selector import (
    MultiResponsibilityRoleSelector,
)
from moduly.nastaveni.ui.responsibility_roles_management_dialog import (
    ResponsibilityRolesManagementDialog,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    hazard_identification_service,
)
from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
    pravidla_bezpecne_prace_service,
)

DIALOG_TITLE = "Pravidla bezpečné práce"

# Zpětná kompatibilita pro starší testy.
MODE_PROFESSION = "profession"
MODE_GROUP = "group"


class PravidlaBezpecnePraceDialog(QDialog):
    """Výběr rolí a ohrožených skupin + hierarchie pracoviště pro PBP."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(DIALOG_TITLE)
        self.resize(560, 560)
        self._last_result: list | None = None
        self._last_export_path: Path | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()

        roles_box = QWidget()
        roles_layout = QVBoxLayout(roles_box)
        roles_layout.setContentsMargins(0, 0, 0, 0)
        roles_toolbar = QHBoxLayout()
        manage_roles_btn = QPushButton("Správa…")
        manage_roles_btn.clicked.connect(self._manage_roles)
        roles_toolbar.addStretch()
        roles_toolbar.addWidget(manage_roles_btn)
        self.roles = MultiResponsibilityRoleSelector(self)
        roles_layout.addLayout(roles_toolbar)
        roles_layout.addWidget(self.roles)

        groups_box = QWidget()
        groups_layout = QVBoxLayout(groups_box)
        groups_layout.setContentsMargins(0, 0, 0, 0)
        self.groups = MultiExposedGroupSelector(self)
        groups_layout.addWidget(self.groups)

        self.operation = QComboBox()
        self.workplace = QComboBox()
        self.workplace_part = QComboBox()

        form.addRow("Profese / role:", roles_box)
        form.addRow("Ohrožené skupiny:", groups_box)
        form.addRow("Provoz *:", self.operation)
        form.addRow("Pracoviště:", self.workplace)
        form.addRow("Část pracoviště:", self.workplace_part)
        layout.addLayout(form)

        hint = QLabel(
            "Vyberte alespoň jednu profesi/roli nebo ohroženou skupinu. "
            "Obě sekce lze kombinovat."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

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

    # Kompatibilita se staršími testy (dříve QListWidget).
    @property
    def roles_list(self):
        return self.roles.list_widget

    @property
    def groups_list(self):
        return self.groups.list_widget

    def selected_role_ids(self) -> list[int]:
        return self.roles.selected_role_ids()

    def selected_group_ids(self) -> list[int]:
        return self.groups.selected_group_ids()

    def set_selected_role_ids(self, role_ids: list[int] | tuple[int, ...] | None) -> None:
        self.roles.set_role_ids(role_ids)

    def set_selected_group_ids(
        self,
        group_ids: list[int] | tuple[int, ...] | None,
    ) -> None:
        self.groups.set_group_ids(group_ids)

    def _manage_roles(self) -> None:
        current = self.selected_role_ids()
        dialog = ResponsibilityRolesManagementDialog(self)
        dialog.exec()
        self.roles.reload(preserve_ids=current)

    def _generate(self) -> None:
        operation_id = self.operation.currentData()
        if operation_id is None:
            QMessageBox.warning(self, DIALOG_TITLE, "Vyberte provoz.")
            return

        workplace_id = self.workplace.currentData()
        workplace_part_id = self.workplace_part.currentData()
        if workplace_id is None:
            workplace_part_id = None

        role_ids = self.selected_role_ids()
        group_ids = self.selected_group_ids()
        if not role_ids and not group_ids:
            QMessageBox.warning(
                self,
                DIALOG_TITLE,
                "Vyberte alespoň jednu profesi, roli nebo ohroženou skupinu.",
            )
            return

        self._last_result = pravidla_bezpecne_prace_service.generate(
            role_ids=role_ids or None,
            endangered_group_ids=group_ids or None,
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
            role_ids=role_ids or None,
            endangered_group_ids=group_ids or None,
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
