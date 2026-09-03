"""Záložka katalogu kontrolních orgánů v Nastavení."""

from __future__ import annotations

import logging

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from core.widgets.filter_bar import FilterBar
from core.widgets.long_operation_dialog import LongOperationDialog
from core.widgets.long_operation_runner import (
    LongOperationCancelled,
    LongOperationContext,
    LongOperationRunner,
)
from core.widgets.table_utils import configure_tree_columns
from moduly.statni_dozor.constants import (
    AUTHORITY_NOT_FOUND_MESSAGE,
    AUTHORITY_ORIGIN_LABELS,
    CATALOG_DEACTIVATE_AUTHORITY_TITLE,
    CATALOG_DEACTIVATE_OFFICE_TITLE,
    CATALOG_EMPTY_TEXT,
    CATALOG_FILTER_EMPTY_TEXT,
    CATALOG_HAS_ACTIVE_OFFICES_TOOLTIP,
    CATALOG_LOAD_ERROR_TEXT,
    CATALOG_NEW_AUTHORITY_LABEL,
    CATALOG_NEW_OFFICE_LABEL,
    CATALOG_ROW_KIND_AUTHORITY,
    CATALOG_ROW_KIND_OFFICE,
    CATALOG_SHOW_INACTIVE_LABEL,
    EMPTY_VALUE,
    OFFICE_ACTIVE_UNDER_INACTIVE_AUTHORITY_MESSAGE,
    OFFICE_CATALOG_TOOLTIP,
    OFFICE_NOT_FOUND_MESSAGE,
    WEB_APPLY_UI_REFRESH_FAILED,
    WEB_CHECK_UI_BUTTON_LABEL,
    WEB_CHECK_UI_DIALOG_TITLE,
    WEB_CHECK_UI_ERROR_OTHER,
    WEB_CHECK_UI_PROGRESS_TEXT,
    WEB_CHECK_UI_TOOLTIP_NO_SELECTION,
    WEB_CHECK_UI_TOOLTIP_SUPPORTED,
    WEB_CHECK_UI_TOOLTIP_UNSUPPORTED,
)
from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
    ControlAuthorityCatalogError,
    control_authority_catalog_service,
)
from moduly.statni_dozor.sluzby.control_authority_web.check import (
    ControlAuthorityWebCheckError,
    ControlAuthorityWebCheckResult,
    check_authority_web,
    has_web_adapter,
)
from moduly.statni_dozor.sluzby.control_authority_web.labels import (
    web_apply_success_message,
    web_check_error_user_message,
)
from moduly.statni_dozor.ui.control_authority_dialog import ControlAuthorityDialog
from moduly.statni_dozor.ui.control_authority_office_dialog import (
    ControlAuthorityOfficeDialog,
)
from moduly.statni_dozor.ui.control_authority_web_preview_dialog import (
    ControlAuthorityWebPreviewDialog,
)

logger = logging.getLogger(__name__)

_OVERLAY_ALPHA = 110
_ROLE_ID = Qt.ItemDataRole.UserRole
_ROLE_KIND = Qt.ItemDataRole.UserRole + 1
_ROLE_SEARCH = Qt.ItemDataRole.UserRole + 2
_ROLE_ACTIVE = Qt.ItemDataRole.UserRole + 3
_COL_NAME = 0
_COL_KIND = 1
_COL_ADDRESS = 2
_COL_CONTACT = 3
_COL_ORIGIN = 4
_COL_ACTIVE = 5


def _run_control_authority_web_check(
    context: LongOperationContext, snapshot: object
) -> ControlAuthorityWebCheckResult:
    """Worker webové kontroly. Nesmí sahat na Qt widgety."""
    context.set_phase(WEB_CHECK_UI_PROGRESS_TEXT, indeterminate=True)
    try:
        result = check_authority_web(str(snapshot))
        context.check_cancel()
        return result
    except LongOperationCancelled:
        raise
    except ControlAuthorityWebCheckError as exc:
        raise RuntimeError(web_check_error_user_message(exc)) from exc
    except Exception as exc:
        raise RuntimeError(WEB_CHECK_UI_ERROR_OTHER) from exc


class _ParentDimOverlay(QWidget):
    def __init__(self, host: QWidget):
        super().__init__(host)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._sync_geometry()
        host.installEventFilter(self)
        self.raise_()
        self.show()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self.parentWidget() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.LayoutRequest,
        ):
            self._sync_geometry()
        return False

    def _sync_geometry(self) -> None:
        parent = self.parentWidget()
        if parent is not None:
            self.setGeometry(parent.rect())

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, _OVERLAY_ALPHA))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        event.accept()


def _join_parts(*parts: str | None) -> str:
    return " · ".join(part.strip() for part in parts if part and part.strip())


def _origin_label(origin: str | None) -> str:
    return AUTHORITY_ORIGIN_LABELS.get(origin or "", EMPTY_VALUE)


def _origin_tooltip(record) -> str:
    parts = [_origin_label(record.origin)]
    if record.source_url:
        parts.append(record.source_url)
    if record.external_key:
        parts.append(record.external_key)
    checked = record.last_checked_at
    if checked is not None:
        parts.append(checked.strftime("%d. %m. %Y %H:%M"))
    return "\n".join(part for part in parts if part)


def _active_label(active: bool) -> str:
    return "Ano" if active else "Ne"


class ControlAuthorityCatalogTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._catalog = control_authority_catalog_service
        self._has_active_authority = False
        self._load_error = False
        self._web_check_runner = LongOperationRunner(self)
        self._web_check_progress: LongOperationDialog | None = None
        self._web_check_runner.succeeded.connect(self._on_web_check_succeeded)
        self._web_check_runner.failed.connect(self._on_web_check_failed)
        self._web_check_runner.cancelled.connect(self._on_web_check_cancelled)
        self._web_check_runner.finished.connect(self._on_web_check_finished)

        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()

        self.new_authority_button = QPushButton(CATALOG_NEW_AUTHORITY_LABEL)
        self.new_authority_button.clicked.connect(self.add_authority)
        self.new_office_button = QPushButton(CATALOG_NEW_OFFICE_LABEL)
        self.new_office_button.clicked.connect(self.add_office)
        self.edit_button = QPushButton("Upravit")
        self.edit_button.clicked.connect(self.edit_selected)
        self.edit_button.setEnabled(False)
        self.toggle_active_button = QPushButton("Deaktivovat")
        self.toggle_active_button.clicked.connect(self.toggle_selected_active)
        self.toggle_active_button.setEnabled(False)
        self.web_check_button = QPushButton(WEB_CHECK_UI_BUTTON_LABEL)
        self.web_check_button.clicked.connect(self.start_web_check)
        self.web_check_button.setEnabled(False)
        self.web_check_button.setToolTip(WEB_CHECK_UI_TOOLTIP_NO_SELECTION)
        self.show_inactive = QCheckBox(CATALOG_SHOW_INACTIVE_LABEL)
        self.show_inactive.toggled.connect(lambda *_args: self.refresh())

        toolbar.addWidget(self.new_authority_button)
        toolbar.addWidget(self.new_office_button)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.toggle_active_button)
        toolbar.addWidget(self.web_check_button)
        toolbar.addStretch()
        toolbar.addWidget(self.show_inactive)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(6)
        self.tree.setHeaderLabels(
            ["Název", "Druh", "Adresa / územní působnost", "Kontakt", "Původ", "Aktivní"]
        )
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setRootIsDecorated(True)
        self.tree.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.tree.itemDoubleClicked.connect(self.edit_selected)
        self.tree.itemSelectionChanged.connect(self.update_buttons)
        configure_tree_columns(self.tree, "control_authority_catalog")

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.hide()
        self.filter_bar = FilterBar(apply_fn=self._apply_tree_filter)

        layout.addLayout(toolbar)
        layout.addWidget(self.filter_bar)
        layout.addWidget(self.status_label)
        layout.addWidget(self.tree, 1)

        self.refresh()

    def _exec_dialog(self, dialog: QWidget) -> int:
        host = self.window() if self.window() is not None else self
        overlay = _ParentDimOverlay(host)
        try:
            return dialog.exec()
        finally:
            overlay.hide()
            overlay.deleteLater()

    def _selected_item(self) -> QTreeWidgetItem | None:
        items = self.tree.selectedItems()
        if len(items) != 1:
            return None
        return items[0]

    def _selected(self) -> tuple[str | None, int | None]:
        item = self._selected_item()
        if item is None:
            return None, None
        kind = item.data(0, _ROLE_KIND)
        record_id = item.data(0, _ROLE_ID)
        if kind not in {"authority", "office"} or record_id is None:
            return None, None
        return str(kind), int(record_id)

    def _preselected_authority_id(self) -> int | None:
        kind, record_id = self._selected()
        if kind == "authority" and record_id is not None:
            authority = self._catalog.get_authority(record_id)
            if authority is not None and authority.active:
                return int(authority.id)
            return None
        if kind == "office" and record_id is not None:
            office = self._catalog.get_office(record_id)
            if office is None:
                return None
            parent = self._catalog.get_authority(int(office.authority_id))
            if parent is not None and parent.active:
                return int(parent.id)
        return None

    def _apply_tree_filter(self, text: str) -> tuple[int, int]:
        needle = (text or "").strip().lower()
        total = 0
        visible = 0
        for index in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(index)
            total += 1
            parent_search = str(parent.data(0, _ROLE_SEARCH) or "")
            parent_match = (not needle) or needle in parent_search
            child_visible = False
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                total += 1
                child_search = str(child.data(0, _ROLE_SEARCH) or "")
                child_match = (not needle) or needle in child_search
                show_child = parent_match or child_match
                child.setHidden(not show_child)
                if show_child:
                    visible += 1
                    child_visible = True
            show_parent = parent_match or child_visible
            parent.setHidden(not show_parent)
            if show_parent:
                visible += 1
                if needle and child_visible:
                    parent.setExpanded(True)
        if self._load_error:
            self.status_label.setText(CATALOG_LOAD_ERROR_TEXT)
            self.status_label.show()
        elif total == 0:
            self.status_label.setText(CATALOG_EMPTY_TEXT)
            self.status_label.show()
        elif visible == 0:
            self.status_label.setText(CATALOG_FILTER_EMPTY_TEXT)
            self.status_label.show()
        else:
            self.status_label.hide()
        return visible, total

    def _set_item_texts(
        self,
        item: QTreeWidgetItem,
        *,
        name: str,
        kind: str,
        address: str,
        contact: str,
        origin: str,
        active: str,
        name_tooltip: str,
        kind_tooltip: str,
        address_tooltip: str,
        contact_tooltip: str,
        origin_tooltip: str,
    ) -> None:
        values = (name, kind, address, contact, origin, active)
        tooltips = (
            name_tooltip,
            kind_tooltip,
            address_tooltip,
            contact_tooltip,
            origin_tooltip,
            active,
        )
        for column, value in enumerate(values):
            item.setText(column, value)
            item.setToolTip(column, tooltips[column])
            item.setTextAlignment(column, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def refresh(self, select: tuple[str, int] | None = None) -> None:
        previous_select = self._selected()
        if isinstance(select, tuple) and len(select) == 2:
            previous_select = select
        expanded_ids: set[int] = set()
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.isExpanded() and item.data(0, _ROLE_KIND) == "authority":
                record_id = item.data(0, _ROLE_ID)
                if record_id:
                    expanded_ids.add(int(record_id))
            iterator += 1

        search_text = self.filter_bar.search_edit.text()
        show_inactive = self.show_inactive.isChecked()
        self.tree.clear()
        self._load_error = False
        self._has_active_authority = False
        by_id: dict[int, QTreeWidgetItem] = {}
        try:
            authorities = self._catalog.list_authorities(include_inactive=show_inactive)
            self._has_active_authority = any(
                item.active
                for item in self._catalog.list_authorities(include_inactive=True)
            )
            for authority in authorities:
                offices = self._catalog.list_offices(
                    authority_id=int(authority.id),
                    include_inactive=show_inactive,
                )
                contact = ""
                address = authority.website or ""
                origin = _origin_label(authority.origin)
                origin_tip = _origin_tooltip(authority)
                parent_item = QTreeWidgetItem()
                self._set_item_texts(
                    parent_item,
                    name=authority.name,
                    kind=CATALOG_ROW_KIND_AUTHORITY,
                    address=address,
                    contact=contact,
                    origin=origin,
                    active=_active_label(authority.active),
                    name_tooltip=authority.name,
                    kind_tooltip=CATALOG_ROW_KIND_AUTHORITY,
                    address_tooltip=address,
                    contact_tooltip=contact,
                    origin_tooltip=origin_tip,
                )
                search = " ".join(
                    part
                    for part in (
                        authority.name,
                        authority.abbreviation,
                        authority.code,
                    )
                    if part
                ).lower()
                parent_item.setData(0, _ROLE_ID, int(authority.id))
                parent_item.setData(0, _ROLE_KIND, "authority")
                parent_item.setData(0, _ROLE_SEARCH, search)
                parent_item.setData(0, _ROLE_ACTIVE, bool(authority.active))
                for office in offices:
                    contact = _join_parts(office.phone, office.email)
                    address = _join_parts(office.address, office.territorial_scope)
                    office_origin = _origin_label(office.origin)
                    office_origin_tip = _origin_tooltip(office)
                    contact_tip = _join_parts(office.phone, office.email) or EMPTY_VALUE
                    child = QTreeWidgetItem()
                    self._set_item_texts(
                        child,
                        name=office.name,
                        kind=CATALOG_ROW_KIND_OFFICE,
                        address=address,
                        contact=contact,
                        origin=office_origin,
                        active=_active_label(office.active),
                        name_tooltip=office.name,
                        kind_tooltip=OFFICE_CATALOG_TOOLTIP,
                        address_tooltip=address,
                        contact_tooltip=contact_tip,
                        origin_tooltip=office_origin_tip,
                    )
                    child_search = " ".join(
                        part
                        for part in (
                            office.name,
                            office.abbreviation,
                            office.address,
                            office.territorial_scope,
                            office.phone,
                            office.email,
                        )
                        if part
                    ).lower()
                    child.setData(0, _ROLE_ID, int(office.id))
                    child.setData(0, _ROLE_KIND, "office")
                    child.setData(0, _ROLE_SEARCH, child_search)
                    child.setData(0, _ROLE_ACTIVE, bool(office.active))
                    parent_item.addChild(child)
                self.tree.addTopLevelItem(parent_item)
                by_id[int(authority.id)] = parent_item
        except Exception:
            logger.exception("Načtení katalogu kontrolních orgánů selhalo.")
            self._load_error = True
            self.tree.clear()

        if expanded_ids:
            for authority_id, item in by_id.items():
                item.setExpanded(authority_id in expanded_ids)
        else:
            self.tree.expandAll()

        self.filter_bar.search_edit.setText(search_text)
        self.filter_bar.update_count()

        if previous_select[0] and previous_select[1] is not None:
            self._restore_selection(previous_select[0], previous_select[1])
        self.update_buttons()

    def _restore_selection(self, kind: str, record_id: int) -> None:
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if (
                item.data(0, _ROLE_KIND) == kind
                and item.data(0, _ROLE_ID) == record_id
                and not item.isHidden()
            ):
                self.tree.setCurrentItem(item)
                return
            iterator += 1

    def update_buttons(self) -> None:
        try:
            self._update_catalog_action_buttons()
        finally:
            self._update_web_check_button()

    def _update_catalog_action_buttons(self) -> None:
        kind, record_id = self._selected()
        self.edit_button.setEnabled(kind is not None)
        self.new_office_button.setEnabled(False)
        self.new_office_button.setToolTip("")
        self.toggle_active_button.setEnabled(False)
        self.toggle_active_button.setText("Deaktivovat")
        self.toggle_active_button.setToolTip("")

        if self._load_error:
            return

        if kind is None:
            self.new_office_button.setEnabled(self._has_active_authority)
            return

        if kind == "authority" and record_id is not None:
            authority = self._catalog.get_authority(record_id)
            if authority is None:
                return
            if authority.active:
                self.new_office_button.setEnabled(True)
                active_children = self._catalog.list_offices(
                    authority_id=int(authority.id), include_inactive=False
                )
                self.toggle_active_button.setText("Deaktivovat")
                if active_children:
                    self.toggle_active_button.setEnabled(False)
                    self.toggle_active_button.setToolTip(CATALOG_HAS_ACTIVE_OFFICES_TOOLTIP)
                else:
                    self.toggle_active_button.setEnabled(True)
            else:
                self.new_office_button.setEnabled(False)
                self.new_office_button.setToolTip(
                    OFFICE_ACTIVE_UNDER_INACTIVE_AUTHORITY_MESSAGE
                )
                self.toggle_active_button.setText("Aktivovat")
                self.toggle_active_button.setEnabled(True)
            return

        if kind == "office" and record_id is not None:
            office = self._catalog.get_office(record_id)
            if office is None:
                return
            parent = self._catalog.get_authority(int(office.authority_id))
            parent_active = parent is not None and parent.active
            self.new_office_button.setEnabled(parent_active)
            if office.active:
                self.toggle_active_button.setText("Deaktivovat")
                self.toggle_active_button.setEnabled(True)
            else:
                self.toggle_active_button.setText("Aktivovat")
                if parent_active:
                    self.toggle_active_button.setEnabled(True)
                else:
                    self.toggle_active_button.setEnabled(False)
                    self.toggle_active_button.setToolTip(
                        OFFICE_ACTIVE_UNDER_INACTIVE_AUTHORITY_MESSAGE
                    )

    def _selected_web_authority(self):
        kind, record_id = self._selected()
        if kind == "authority" and record_id is not None:
            return self._catalog.get_authority(record_id)
        if kind == "office" and record_id is not None:
            office = self._catalog.get_office(record_id)
            if office is None:
                return None
            return self._catalog.get_authority(int(office.authority_id))
        return None

    def _update_web_check_button(self) -> None:
        if not hasattr(self, "web_check_button"):
            return
        if self._web_check_runner.is_running() or self._load_error:
            self.web_check_button.setEnabled(False)
            return
        kind, _record_id = self._selected()
        if kind is None:
            self.web_check_button.setEnabled(False)
            self.web_check_button.setToolTip(WEB_CHECK_UI_TOOLTIP_NO_SELECTION)
            return
        authority = self._selected_web_authority()
        code = str(getattr(authority, "code", "") or "")
        if authority is None or not has_web_adapter(code):
            self.web_check_button.setEnabled(False)
            self.web_check_button.setToolTip(WEB_CHECK_UI_TOOLTIP_UNSUPPORTED)
            return
        self.web_check_button.setEnabled(True)
        self.web_check_button.setToolTip(WEB_CHECK_UI_TOOLTIP_SUPPORTED)

    def _web_check_ui_alive(self) -> bool:
        try:
            self.objectName()
            self.web_check_button.objectName()
        except RuntimeError:
            return False
        return True

    def _ensure_web_check_progress(self) -> LongOperationDialog:
        dialog = self._web_check_progress
        if dialog is not None:
            try:
                dialog.objectName()
                return dialog
            except RuntimeError:
                self._web_check_progress = None
        dialog = LongOperationDialog(
            self,
            title=WEB_CHECK_UI_DIALOG_TITLE,
            runner=self._web_check_runner,
            close_on_success=True,
        )
        self._web_check_progress = dialog
        return dialog

    def start_web_check(self) -> None:
        if self._web_check_runner.is_running():
            return
        authority = self._selected_web_authority()
        code = str(getattr(authority, "code", "") or "").strip()
        if authority is None or not has_web_adapter(code):
            return
        self._ensure_web_check_progress()
        started = self._web_check_runner.start(
            _run_control_authority_web_check,
            code,
            blocked_widgets=(self.web_check_button,),
        )
        if not started:
            return
        self.web_check_button.setEnabled(False)

    def _on_web_check_succeeded(self, result: object) -> None:
        if not self._web_check_ui_alive():
            return
        if not isinstance(result, ControlAuthorityWebCheckResult):
            logger.error("Webová kontrola vrátila neočekávaný výsledek.")
            QMessageBox.warning(
                self, WEB_CHECK_UI_DIALOG_TITLE, WEB_CHECK_UI_ERROR_OTHER
            )
            return
        dialog = ControlAuthorityWebPreviewDialog(self, result)
        self._exec_dialog(dialog)
        self._handle_web_apply_outcome(dialog)

    def _handle_web_apply_outcome(self, dialog: ControlAuthorityWebPreviewDialog) -> None:
        if not self._web_check_ui_alive():
            return
        result = getattr(dialog, "apply_result", None)
        if result is None:
            return
        authority = self._selected_web_authority()
        select = None
        if authority is not None:
            select = ("authority", int(authority.id))
        else:
            kind, record_id = self._selected()
            if kind is not None and record_id is not None:
                select = (kind, record_id)
        try:
            self.refresh(select=select)
            if self._load_error:
                raise RuntimeError("Obnovení stromu katalogu selhalo.")
        except Exception:
            logger.exception("Obnovení katalogu po použití webových změn selhalo.")
            QMessageBox.warning(
                self, WEB_CHECK_UI_DIALOG_TITLE, WEB_APPLY_UI_REFRESH_FAILED
            )
            return
        QMessageBox.information(
            self,
            WEB_CHECK_UI_DIALOG_TITLE,
            web_apply_success_message(result),
        )

    def _on_web_check_failed(self, message: str) -> None:
        if not self._web_check_ui_alive():
            return
        logger.error("Webová kontrola katalogu selhala.")
        QMessageBox.warning(
            self,
            WEB_CHECK_UI_DIALOG_TITLE,
            str(message or WEB_CHECK_UI_ERROR_OTHER),
        )

    def _on_web_check_cancelled(self) -> None:
        return

    def _on_web_check_finished(self) -> None:
        if not self._web_check_ui_alive():
            return
        self.update_buttons()

    def add_authority(self) -> None:
        dialog = ControlAuthorityDialog(
            self, on_catalog_changed=self._on_catalog_changed
        )
        self._exec_dialog(dialog)

    def add_office(self) -> None:
        if not self.new_office_button.isEnabled():
            return
        dialog = ControlAuthorityOfficeDialog(
            self,
            preselected_authority_id=self._preselected_authority_id(),
            on_catalog_changed=self._on_catalog_changed,
        )
        self._exec_dialog(dialog)

    def edit_selected(self, *_args) -> None:
        kind, record_id = self._selected()
        if kind is None or record_id is None:
            return
        if kind == "authority":
            authority = self._catalog.get_authority(record_id)
            if authority is None:
                QMessageBox.warning(
                    self,
                    CATALOG_ROW_KIND_AUTHORITY,
                    AUTHORITY_NOT_FOUND_MESSAGE,
                )
                self.refresh()
                return
            dialog = ControlAuthorityDialog(
                self,
                authority=authority,
                on_catalog_changed=self._on_catalog_changed,
            )
            self._exec_dialog(dialog)
            return
        office = self._catalog.get_office(record_id)
        if office is None:
            QMessageBox.warning(self, CATALOG_ROW_KIND_OFFICE, OFFICE_NOT_FOUND_MESSAGE)
            self.refresh()
            return
        dialog = ControlAuthorityOfficeDialog(
            self,
            office=office,
            on_catalog_changed=self._on_catalog_changed,
        )
        self._exec_dialog(dialog)

    def _on_catalog_changed(self, *, kind: str, record_id: int) -> None:
        self.refresh(select=(kind, record_id))

    def toggle_selected_active(self) -> None:
        kind, record_id = self._selected()
        if kind is None or record_id is None:
            return
        if kind == "authority":
            authority = self._catalog.get_authority(record_id)
            if authority is None:
                self.refresh()
                return
            if authority.active:
                answer = QMessageBox.question(
                    self,
                    CATALOG_DEACTIVATE_AUTHORITY_TITLE,
                    f"Opravdu deaktivovat kontrolní orgán {authority.name}?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if answer != QMessageBox.Yes:
                    return
                try:
                    self._catalog.deactivate_authority(record_id)
                except ControlAuthorityCatalogError as exc:
                    QMessageBox.warning(self, CATALOG_ROW_KIND_AUTHORITY, str(exc))
                    return
            else:
                self._catalog.reactivate_authority(record_id)
            self.refresh(select=("authority", record_id))
            return

        office = self._catalog.get_office(record_id)
        if office is None:
            self.refresh()
            return
        if office.active:
            answer = QMessageBox.question(
                self,
                CATALOG_DEACTIVATE_OFFICE_TITLE,
                f"Opravdu deaktivovat příslušné pracoviště {office.name}?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            self._catalog.deactivate_office(record_id)
        else:
            try:
                self._catalog.reactivate_office(record_id)
            except ControlAuthorityCatalogError as exc:
                QMessageBox.warning(self, CATALOG_ROW_KIND_OFFICE, str(exc))
                return
        self.refresh(select=("office", record_id))
