from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_header_settings import configure_and_persist_table_columns
from core.widgets.table_row_actions import install_table_row_actions
from core.widgets.table_selection import (
    current_table_row,
    refresh_and_restore_selection,
)
from moduly.koordinace_bozp.constants import COORD_HEADER_MEASURES, TAB_MEASURES
from moduly.koordinace_bozp.sluzby.coordination_measure_service import (
    CoordinationMeasureError,
    coordination_measure_service,
)
from moduly.koordinace_bozp.ui.coordination_measure_dialog import (
    CoordinationMeasureDialog,
)
from moduly.koordinace_bozp.ui.coordination_measure_table import (
    CoordinationMeasureTable,
)
from moduly.koordinace_bozp.ui.coordination_tab_edit_policy import (
    CoordinationTabEditPolicyMixin,
)


class CoordinationMeasuresTab(CoordinationTabEditPolicyMixin, QWidget):
    """Záložka organizačních opatření (COORD-009)."""

    def __init__(self, parent=None, coordination_id: int | None = None):
        super().__init__(parent)
        self.coordination_id = coordination_id
        self._content_editable = True
        self._before_mutate = None

        layout = QVBoxLayout(self)
        self.unavailable_label = QLabel(
            "Organizační opatření lze spravovat po uložení koordinace."
        )
        self.unavailable_label.setWordWrap(True)
        layout.addWidget(self.unavailable_label)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat")
        self.edit_btn = QPushButton("Upravit")
        self.up_btn = QPushButton("Nahoru")
        self.down_btn = QPushButton("Dolů")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.up_btn)
        toolbar.addWidget(self.down_btn)
        toolbar.addWidget(self.activate_btn)
        toolbar.addWidget(self.deactivate_btn)
        toolbar.addStretch()
        content_layout.addLayout(toolbar)

        self.table = CoordinationMeasureTable()
        configure_and_persist_table_columns(self.table, "coordination_measures", COORD_HEADER_MEASURES)
        content_layout.addWidget(self.table)
        layout.addWidget(self.content)

        self.add_btn.clicked.connect(self.add_measure)
        self.edit_btn.clicked.connect(self.edit_selected_measure)
        self.up_btn.clicked.connect(self.move_selected_up)
        self.down_btn.clicked.connect(self.move_selected_down)
        self.activate_btn.clicked.connect(self.activate_selected_measure)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_measure)
        self.table.doubleClicked.connect(self.edit_selected_measure)
        install_table_row_actions(
            self.table,
            on_edit=self.edit_selected_measure,
            on_deactivate=self.deactivate_selected_measure,
            can_edit=lambda: self.edit_btn.isEnabled(),
            can_deactivate=lambda: self.deactivate_btn.isEnabled(),
        )
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.set_coordination_id(coordination_id)

    def set_coordination_id(self, coordination_id: int | None) -> None:
        self.coordination_id = coordination_id
        available = coordination_id is not None
        self.unavailable_label.setVisible(not available)
        self.content.setVisible(available)
        if available:
            self.refresh()
        else:
            self.table.setRowCount(0)
            self._update_action_buttons()

    def refresh(
        self,
        *,
        select_id: int | None = None,
        fallback_row: int | None = None,
        preserve_scroll: bool = False,
        ensure_visible: bool = False,
    ) -> None:
        if self.coordination_id is None:
            return
        scroll_value = (
            self.table.verticalScrollBar().value() if preserve_scroll else None
        )
        record_id = (
            select_id
            if select_id is not None
            else self.table.selected_measure_id()
        )
        measures = coordination_measure_service.list_for_coordination(
            self.coordination_id,
            include_inactive=True,
        )
        self.table.load_measures(measures)
        configure_and_persist_table_columns(
            self.table, "coordination_measures", COORD_HEADER_MEASURES
        )
        refresh_and_restore_selection(
            self.table,
            record_id,
            fallback_row=fallback_row,
            scroll=ensure_visible and not preserve_scroll,
            preserve_scroll_value=scroll_value,
            focus=True,
        )
        self._update_action_buttons()

    def add_measure(self) -> None:
        if self.coordination_id is None or not self.allow_mutate():
            return
        dialog = CoordinationMeasureDialog(self)
        if not dialog.exec():
            return
        try:
            created = coordination_measure_service.add(
                self.coordination_id,
                **dialog.get_data(),
            )
        except CoordinationMeasureError as error:
            QMessageBox.warning(self, TAB_MEASURES, str(error))
            return
        self.refresh(select_id=created.id, ensure_visible=True)

    def edit_selected_measure(self) -> None:
        if not self.allow_mutate():
            return
        measure = self._selected_measure()
        if measure is None:
            QMessageBox.information(self, TAB_MEASURES, "Vyberte opatření.")
            return
        dialog = CoordinationMeasureDialog(self, measure=measure)
        if not dialog.exec():
            return
        try:
            coordination_measure_service.update(measure.id, **dialog.get_data())
        except CoordinationMeasureError as error:
            QMessageBox.warning(self, TAB_MEASURES, str(error))
            return
        self.refresh(select_id=measure.id, preserve_scroll=True)

    def move_selected_up(self) -> None:
        if not self.allow_mutate():
            return
        measure = self._selected_measure()
        if measure is None:
            return
        if coordination_measure_service.move_up(measure.id):
            self.refresh(select_id=measure.id, ensure_visible=True)

    def move_selected_down(self) -> None:
        if not self.allow_mutate():
            return
        measure = self._selected_measure()
        if measure is None:
            return
        if coordination_measure_service.move_down(measure.id):
            self.refresh(select_id=measure.id, ensure_visible=True)

    def activate_selected_measure(self) -> None:
        if not self.allow_mutate():
            return
        measure = self._selected_measure()
        if measure is None:
            QMessageBox.information(self, TAB_MEASURES, "Vyberte opatření.")
            return
        if measure.active:
            QMessageBox.information(self, TAB_MEASURES, "Opatření je již aktivní.")
            return
        answer = QMessageBox.question(
            self,
            "Aktivovat",
            f"Opravdu aktivovat opatření „{measure.title}“?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            coordination_measure_service.activate(measure.id)
            self.refresh(select_id=measure.id, ensure_visible=True)

    def deactivate_selected_measure(self) -> None:
        if not self.allow_mutate():
            return
        measure = self._selected_measure()
        if measure is None:
            QMessageBox.information(self, TAB_MEASURES, "Vyberte opatření.")
            return
        if not measure.active:
            QMessageBox.information(self, TAB_MEASURES, "Opatření je již neaktivní.")
            return
        answer = QMessageBox.question(
            self,
            "Deaktivovat",
            f"Opravdu deaktivovat opatření „{measure.title}“?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            row = current_table_row(self.table)
            coordination_measure_service.deactivate(measure.id)
            self.refresh(
                select_id=measure.id,
                fallback_row=row,
                ensure_visible=True,
            )

    def _selected_measure(self):
        measure_id = self.table.selected_measure_id()
        if measure_id is None:
            return None
        return coordination_measure_service.get_by_id(measure_id)

    def _update_action_buttons(self) -> None:
        if not getattr(self, "_content_editable", True):
            self.add_btn.setEnabled(False)
            self.edit_btn.setEnabled(False)
            self.up_btn.setEnabled(False)
            self.down_btn.setEnabled(False)
            self.activate_btn.setEnabled(False)
            self.deactivate_btn.setEnabled(False)
            return
        measure = self._selected_measure()
        has_selection = measure is not None
        self.edit_btn.setEnabled(has_selection)
        self.up_btn.setEnabled(has_selection)
        self.down_btn.setEnabled(has_selection)
        if not has_selection:
            self.activate_btn.setEnabled(False)
            self.deactivate_btn.setEnabled(False)
            return
        self.activate_btn.setEnabled(not measure.active)
        self.deactivate_btn.setEnabled(measure.active)
