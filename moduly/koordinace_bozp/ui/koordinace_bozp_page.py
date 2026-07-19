from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.widgets.filter_bar import FilterBar
from core.widgets.table_header_settings import configure_and_persist_table_columns
from core.widgets.table_row_actions import install_table_row_actions
from core.widgets.table_selection import (
    current_table_row,
    refresh_and_restore_selection,
)
from moduly.koordinace_bozp.constants import (
    COORD_HEADER_LIST,
    DIALOG_WINDOW_TITLE,
    PBP_FILTER_ALL,
    PBP_FILTER_CURRENT,
    PBP_FILTER_LABELS,
    PBP_FILTER_MISSING,
    PBP_FILTER_NEEDS_UPDATE,
    PBP_FILTER_UNVERIFIABLE,
    STATUS_FILTER_ALL,
    STATUS_FILTERS,
    STATUS_FILTER_LABELS,
    VALIDITY_FILTER_ALL,
    VALIDITY_FILTER_EXPIRED,
    VALIDITY_FILTER_EXPIRING,
    VALIDITY_FILTER_LABELS,
    VALIDITY_FILTER_VALID,
)
from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
    BozpCoordinationError,
    bozp_coordination_service,
)
from moduly.koordinace_bozp.sluzby.coordination_lifecycle_service import (
    LifecycleAction,
    coordination_lifecycle_service,
    is_strict_readonly,
    normalize_coordination_status,
)
from moduly.koordinace_bozp.sluzby.coordination_pbp_freshness import PbpFreshnessCache
from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
from moduly.koordinace_bozp.ui.bozp_coordination_table import BozpCoordinationTable
from moduly.koordinace_bozp.ui.coordination_lifecycle_ui import (
    run_lifecycle_transition,
)


class KoordinaceBozpPage(QWidget):
    """Úvodní stránka modulu – seznam koordinací."""

    def __init__(self):
        super().__init__()
        self._pbp_cache = PbpFreshnessCache()
        self._lifecycle_buttons: list[QPushButton] = []

        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("Nová koordinace")
        self.open_btn = QPushButton("Otevřít")
        self.activate_btn = QPushButton("Aktivovat")
        self.deactivate_btn = QPushButton("Deaktivovat")

        toolbar.addWidget(self.new_btn)
        toolbar.addWidget(self.open_btn)
        toolbar.addWidget(self.activate_btn)
        toolbar.addWidget(self.deactivate_btn)
        self.lifecycle_toolbar = QHBoxLayout()
        toolbar.addLayout(self.lifecycle_toolbar)
        toolbar.addStretch()
        toolbar.addWidget(QLabel("Stav:"))
        self.status_filter = QComboBox()
        for filter_id in STATUS_FILTERS:
            self.status_filter.addItem(STATUS_FILTER_LABELS[filter_id], filter_id)
        toolbar.addWidget(self.status_filter)

        toolbar.addWidget(QLabel("Platnost:"))
        self.validity_filter = QComboBox()
        for filter_id in (
            VALIDITY_FILTER_ALL,
            VALIDITY_FILTER_VALID,
            VALIDITY_FILTER_EXPIRING,
            VALIDITY_FILTER_EXPIRED,
        ):
            self.validity_filter.addItem(VALIDITY_FILTER_LABELS[filter_id], filter_id)
        toolbar.addWidget(self.validity_filter)

        toolbar.addWidget(QLabel("Příloha PBP:"))
        self.pbp_filter = QComboBox()
        for filter_id in (
            PBP_FILTER_ALL,
            PBP_FILTER_CURRENT,
            PBP_FILTER_NEEDS_UPDATE,
            PBP_FILTER_MISSING,
            PBP_FILTER_UNVERIFIABLE,
        ):
            self.pbp_filter.addItem(PBP_FILTER_LABELS[filter_id], filter_id)
        toolbar.addWidget(self.pbp_filter)

        self.table = BozpCoordinationTable()
        configure_and_persist_table_columns(
            self.table, "bozp_coordinations", COORD_HEADER_LIST
        )
        self.text_filter = FilterBar(self.table, placeholder="🔍 Hledat koordinaci...")

        layout.addLayout(toolbar)
        layout.addWidget(self.text_filter)
        layout.addWidget(self.table)

        self.new_btn.clicked.connect(self.new_coordination)
        self.open_btn.clicked.connect(self.open_selected_coordination)
        self.activate_btn.clicked.connect(self.activate_selected_coordination)
        self.deactivate_btn.clicked.connect(self.deactivate_selected_coordination)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.validity_filter.currentIndexChanged.connect(self.refresh)
        self.pbp_filter.currentIndexChanged.connect(self.refresh)
        self.table.doubleClicked.connect(self.open_selected_coordination)
        install_table_row_actions(
            self.table,
            on_edit=self.open_selected_coordination,
            on_deactivate=self.deactivate_selected_coordination,
            can_edit=lambda: self.open_btn.isEnabled(),
            can_deactivate=lambda: self.deactivate_btn.isEnabled(),
        )
        self.table.itemSelectionChanged.connect(self._update_action_buttons)

        self.refresh()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.table.clear_selection()
        self._update_action_buttons()

    def hideEvent(self, event: QHideEvent) -> None:
        self.table.clear_selection()
        super().hideEvent(event)

    def current_validity_filter(self) -> str:
        return self.validity_filter.currentData() or VALIDITY_FILTER_ALL

    def current_pbp_filter(self) -> str:
        return self.pbp_filter.currentData() or PBP_FILTER_ALL

    def current_status_filter(self) -> str:
        return self.status_filter.currentData() or STATUS_FILTER_ALL

    def refresh(
        self,
        *,
        select_id: int | None = None,
        fallback_row: int | None = None,
        preserve_scroll: bool = False,
        ensure_visible: bool = False,
    ) -> None:
        scroll_value = (
            self.table.verticalScrollBar().value() if preserve_scroll else None
        )
        record_id = (
            select_id
            if select_id is not None
            else self.table.selected_coordination_id()
        )
        self._pbp_cache.clear()
        coordinations = bozp_coordination_service.get_all(
            include_inactive=True,
            validity_filter=self.current_validity_filter(),
            pbp_filter=self.current_pbp_filter(),
            status_filter=self.current_status_filter(),
            pbp_cache=self._pbp_cache,
        )
        self.table.load_coordinations(coordinations, pbp_cache=self._pbp_cache)
        configure_and_persist_table_columns(
            self.table, "bozp_coordinations", COORD_HEADER_LIST
        )
        refresh_and_restore_selection(
            self.table,
            record_id,
            fallback_row=fallback_row,
            scroll=ensure_visible and not preserve_scroll,
            preserve_scroll_value=scroll_value,
            focus=True,
        )
        self.text_filter.update_count()
        self._update_action_buttons()

    def new_coordination(self) -> None:
        dialog = BozpCoordinationDialog(self)
        dialog.showMaximized()
        if not dialog.exec():
            return
        try:
            created = bozp_coordination_service.create_coordination(**dialog.get_data())
        except BozpCoordinationError as error:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, str(error))
            return
        self.refresh(select_id=created.id, ensure_visible=True)

    def open_selected_coordination(self) -> None:
        coordination = self._selected_coordination()
        if coordination is None:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Vyberte koordinaci.")
            return
        dialog = BozpCoordinationDialog(self, coordination=coordination)
        dialog.showMaximized()
        if not dialog.exec():
            self.refresh(select_id=coordination.id, preserve_scroll=True)
            return
        if is_strict_readonly((dialog.coordination or coordination).status):
            self.refresh(select_id=coordination.id, preserve_scroll=True)
            return
        try:
            bozp_coordination_service.update_coordination(
                coordination.id,
                **dialog.get_data(),
            )
        except BozpCoordinationError as error:
            QMessageBox.warning(self, DIALOG_WINDOW_TITLE, str(error))
            return
        self.refresh(select_id=coordination.id, preserve_scroll=True)

    def activate_selected_coordination(self) -> None:
        coordination = self._selected_coordination()
        if coordination is None:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Vyberte koordinaci.")
            return
        if coordination.active:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Koordinace je již aktivní.")
            return
        answer = QMessageBox.question(
            self,
            "Aktivovat",
            f"Opravdu aktivovat koordinaci {coordination.coordination_number}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            bozp_coordination_service.activate(coordination.id)
            self.refresh(select_id=coordination.id, ensure_visible=True)

    def deactivate_selected_coordination(self) -> None:
        coordination = self._selected_coordination()
        if coordination is None:
            QMessageBox.information(self, DIALOG_WINDOW_TITLE, "Vyberte koordinaci.")
            return
        if not coordination.active:
            QMessageBox.information(
                self,
                DIALOG_WINDOW_TITLE,
                "Koordinace je již neaktivní.",
            )
            return
        answer = QMessageBox.question(
            self,
            "Deaktivovat",
            f"Opravdu deaktivovat koordinaci {coordination.coordination_number}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            row = current_table_row(self.table)
            bozp_coordination_service.deactivate(coordination.id)
            self.refresh(
                select_id=coordination.id,
                fallback_row=row,
                ensure_visible=True,
            )

    def _selected_coordination(self):
        coordination_id = self.table.selected_coordination_id()
        if coordination_id is None:
            return None
        return bozp_coordination_service.get_by_id(coordination_id)

    def _clear_lifecycle_buttons(self) -> None:
        for button in self._lifecycle_buttons:
            self.lifecycle_toolbar.removeWidget(button)
            button.deleteLater()
        self._lifecycle_buttons.clear()

    def _run_lifecycle_action(self, action: LifecycleAction) -> None:
        coordination = self._selected_coordination()
        if coordination is None:
            return
        updated = run_lifecycle_transition(self, coordination.id, action)
        if updated is None:
            return
        self.refresh(select_id=updated.id, preserve_scroll=True)

    def _update_action_buttons(self) -> None:
        coordination = self._selected_coordination()
        has_selection = coordination is not None
        self.open_btn.setEnabled(has_selection)
        self._clear_lifecycle_buttons()
        if not has_selection:
            self.activate_btn.setEnabled(False)
            self.deactivate_btn.setEnabled(False)
            return
        self.activate_btn.setEnabled(not coordination.active)
        self.deactivate_btn.setEnabled(coordination.active)
        status = normalize_coordination_status(coordination.status)
        for action in coordination_lifecycle_service.list_actions(status):
            button = QPushButton(action.label)
            button.clicked.connect(
                lambda _checked=False, act=action: self._run_lifecycle_action(act)
            )
            self.lifecycle_toolbar.addWidget(button)
            self._lifecycle_buttons.append(button)
