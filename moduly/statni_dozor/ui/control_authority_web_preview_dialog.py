"""Dialog náhledu rozdílů webové kontroly a výběru změn katalogu."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.utils.https_url import open_https_url
from core.widgets.dialog_utils import (
    configure_close_button,
    configure_resizable_form_dialog,
)
from core.widgets.table_utils import configure_tree_columns
from moduly.statni_dozor.constants import (
    CATALOG_ROW_KIND_AUTHORITY,
    EMPTY_VALUE,
    WEB_APPLY_ACTION_CREATE,
    WEB_APPLY_ACTION_DEACTIVATE,
    WEB_APPLY_ACTION_REACTIVATE,
    WEB_APPLY_ACTION_UPDATE,
    WEB_APPLY_ERROR_STALE,
    WEB_APPLY_UI_BUTTON_LABEL,
    WEB_APPLY_UI_CONFIRM_APPLY,
    WEB_APPLY_UI_CONFIRM_BODY,
    WEB_APPLY_UI_CONFIRM_CANCEL,
    WEB_APPLY_UI_CONFIRM_TITLE,
    WEB_APPLY_UI_ERASE_TOOLTIP,
    WEB_APPLY_UI_ERROR,
    WEB_APPLY_UI_MISSING_HINT,
    WEB_APPLY_UI_PROTECTED_BATCH_WARNING,
    WEB_APPLY_UI_PROTECTED_NOTICE,
    WEB_APPLY_UI_STALE,
    WEB_CHECK_UI_DIALOG_TITLE,
    WEB_CHECK_UI_EMPTY_FILTER_TEXT,
    WEB_CHECK_UI_EMPTY_WEB_VALUE_TOOLTIP,
    WEB_CHECK_UI_READONLY_NOTICE,
    WEB_CHECK_UI_SHOW_UNCHANGED_LABEL,
    WEB_CHECK_UI_WARNINGS_TITLE,
    WEB_DIFF_STATUS_CHANGED,
    WEB_DIFF_STATUS_INACTIVE_PRESENT,
    WEB_DIFF_STATUS_MISSING_REMOTE,
    WEB_DIFF_STATUS_NEW,
    WEB_DIFF_STATUS_PROTECTED,
    WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE,
    WEB_DIFF_STATUS_UNCHANGED,
)
from moduly.statni_dozor.sluzby.control_authority_web.apply import (
    ControlAuthorityOfficeWebApplySelection,
    ControlAuthorityWebApplyError,
    ControlAuthorityWebApplyResult,
    apply_authority_web_changes,
)
from moduly.statni_dozor.sluzby.control_authority_web.check import (
    ControlAuthorityWebCheckResult,
)
from moduly.statni_dozor.sluzby.control_authority_web.labels import (
    WebApplySelectionSummary,
    format_web_checked_at,
    format_web_diff_value,
    web_apply_confirm_lines,
    web_apply_error_user_message,
    web_apply_parent_action_text,
    web_apply_selection_count_text,
    web_check_headline,
    web_check_summary_lines,
    web_diff_field_label,
    web_diff_status_label,
)

logger = logging.getLogger(__name__)

_ROLE_STATUS = Qt.ItemDataRole.UserRole
_ROLE_FIELD = Qt.ItemDataRole.UserRole + 1
_ROLE_DIFF_INDEX = Qt.ItemDataRole.UserRole + 2
_COL_STATUS = 0
_COL_NAME = 1
_COL_COUNT = 2
_COL_ACTION = 3

_FIELD_CHECK_STATUSES = frozenset(
    {WEB_DIFF_STATUS_CHANGED, WEB_DIFF_STATUS_PROTECTED}
)
_PARENT_CHECK_STATUSES = frozenset(
    {
        WEB_DIFF_STATUS_NEW,
        WEB_DIFF_STATUS_MISSING_REMOTE,
        WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE,
        WEB_DIFF_STATUS_INACTIVE_PRESENT,
    }
)
_PROTECTED_STATUSES = frozenset(
    {WEB_DIFF_STATUS_PROTECTED, WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE}
)


def _office_display_name(diff) -> str:
    if diff.local is not None and str(diff.local.name or "").strip():
        return str(diff.local.name)
    if diff.remote is not None and str(diff.remote.name or "").strip():
        return str(diff.remote.name)
    return EMPTY_VALUE


def _value_tooltip(field: str, value: str | None, *, erase: bool) -> str:
    if erase:
        return WEB_APPLY_UI_ERASE_TOOLTIP
    if value is None or str(value).strip() == "":
        return WEB_CHECK_UI_EMPTY_WEB_VALUE_TOOLTIP if value is None else ""
    text = format_web_diff_value(field, value)
    if text == EMPTY_VALUE:
        return ""
    return text


def _is_erasure(change) -> bool:
    return change.new_value is None


class ControlAuthorityWebApplyConfirmDialog(QDialog):
    """Potvrzení dávky. Výchozí i Escape je Zrušit."""

    def __init__(self, parent: QWidget | None, summary: WebApplySelectionSummary):
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setWindowTitle(WEB_APPLY_UI_CONFIRM_TITLE)
        configure_resizable_form_dialog(
            self, width=520, height=340, min_width=420, min_height=240
        )
        layout = QVBoxLayout(self)
        intro = QLabel(WEB_APPLY_UI_CONFIRM_BODY)
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(intro)
        self.summary_label = QLabel("\n".join(web_apply_confirm_lines(summary)))
        self.summary_label.setTextFormat(Qt.TextFormat.PlainText)
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)
        self.protected_label = QLabel(WEB_APPLY_UI_PROTECTED_BATCH_WARNING)
        self.protected_label.setWordWrap(True)
        self.protected_label.setTextFormat(Qt.TextFormat.PlainText)
        self.protected_label.setObjectName("WarningText")
        self.protected_label.setVisible(summary.protected_records > 0)
        layout.addWidget(self.protected_label)
        layout.addStretch(1)
        self.button_box = QDialogButtonBox()
        self.apply_button = QPushButton(WEB_APPLY_UI_CONFIRM_APPLY)
        self.apply_button.setAutoDefault(False)
        self.apply_button.setDefault(False)
        self.cancel_button = self.button_box.addButton(
            WEB_APPLY_UI_CONFIRM_CANCEL,
            QDialogButtonBox.ButtonRole.RejectRole,
        )
        self.button_box.addButton(
            self.apply_button, QDialogButtonBox.ButtonRole.ActionRole
        )
        self.cancel_button.setDefault(True)
        self.cancel_button.setAutoDefault(True)
        self.button_box.rejected.connect(self.reject)
        self.apply_button.clicked.connect(self.accept)
        layout.addWidget(self.button_box)


class ControlAuthorityWebPreviewDialog(QDialog):
    """Náhled rozdílů s výběrem změn. Zápis jen přes CORE-8E1."""

    def __init__(
        self,
        parent: QWidget | None,
        check_result: ControlAuthorityWebCheckResult,
    ):
        super().__init__(parent)
        self._result = check_result
        self.apply_result: ControlAuthorityWebApplyResult | None = None
        self._syncing_checks = False
        self._applying = False
        self._consumed = False
        self._stale = False
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setWindowTitle(WEB_CHECK_UI_DIALOG_TITLE)
        configure_resizable_form_dialog(
            self, width=920, height=640, min_width=640, min_height=420
        )

        layout = QVBoxLayout(self)
        header = QFormLayout()
        self.authority_label = QLabel(check_result.adapter_info.display_name)
        self.authority_label.setTextFormat(Qt.TextFormat.PlainText)
        self.authority_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        source_row = QWidget(self)
        source_layout = QHBoxLayout(source_row)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_name = check_result.adapter_info.source_name or check_result.source_url
        self.source_label = QLabel(source_name)
        self.source_label.setTextFormat(Qt.TextFormat.PlainText)
        self.source_label.setToolTip(check_result.source_url)
        self.source_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.open_source_button = QPushButton("Otevřít")
        self.open_source_button.setAutoDefault(False)
        self.open_source_button.setDefault(False)
        self.open_source_button.clicked.connect(self._open_source)
        source_layout.addWidget(self.source_label, 1)
        source_layout.addWidget(self.open_source_button)
        self.checked_at_label = QLabel(format_web_checked_at(check_result.fetched_at))
        self.office_count_label = QLabel(str(len(check_result.remote_records)))
        header.addRow(f"{CATALOG_ROW_KIND_AUTHORITY}:", self.authority_label)
        header.addRow("Oficiální zdroj:", source_row)
        header.addRow("Datum a čas kontroly:", self.checked_at_label)
        header.addRow("Počet pracovišť:", self.office_count_label)
        layout.addLayout(header)

        self.readonly_label = QLabel(WEB_CHECK_UI_READONLY_NOTICE)
        self.readonly_label.setTextFormat(Qt.TextFormat.PlainText)
        self.readonly_label.setWordWrap(True)
        self.readonly_label.setObjectName("InfoText")
        layout.addWidget(self.readonly_label)

        self.headline_label = QLabel(web_check_headline(check_result.diffs))
        self.headline_label.setTextFormat(Qt.TextFormat.PlainText)
        self.headline_label.setWordWrap(True)
        layout.addWidget(self.headline_label)

        self.summary_label = QLabel("\n".join(web_check_summary_lines(check_result.diffs)))
        self.summary_label.setTextFormat(Qt.TextFormat.PlainText)
        self.summary_label.setWordWrap(True)
        if not self.summary_label.text():
            self.summary_label.hide()
        layout.addWidget(self.summary_label)

        self.stale_label = QLabel(WEB_APPLY_UI_STALE)
        self.stale_label.setTextFormat(Qt.TextFormat.PlainText)
        self.stale_label.setWordWrap(True)
        self.stale_label.setObjectName("WarningText")
        self.stale_label.hide()
        layout.addWidget(self.stale_label)

        self.show_unchanged = QCheckBox(WEB_CHECK_UI_SHOW_UNCHANGED_LABEL)
        self.show_unchanged.setChecked(False)
        self.show_unchanged.toggled.connect(self._apply_unchanged_filter)
        layout.addWidget(self.show_unchanged)

        self.empty_state_label = QLabel(WEB_CHECK_UI_EMPTY_FILTER_TEXT)
        self.empty_state_label.setTextFormat(Qt.TextFormat.PlainText)
        self.empty_state_label.setWordWrap(True)
        self.empty_state_label.setObjectName("InfoText")
        self.empty_state_label.hide()
        layout.addWidget(self.empty_state_label)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(
            [
                "Stav",
                "Příslušné pracoviště",
                "Počet změn",
                "Doporučení",
            ]
        )
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        configure_tree_columns(self.tree, "control_authority_web_preview")
        layout.addWidget(self.tree, 1)
        self._fill_tree()
        self.tree.itemChanged.connect(self._on_item_changed)

        self.warnings_box = QGroupBox(WEB_CHECK_UI_WARNINGS_TITLE)
        warnings_layout = QVBoxLayout(self.warnings_box)
        warning_text = "\n".join(check_result.warnings)
        self.warnings_label = QLabel(warning_text)
        self.warnings_label.setTextFormat(Qt.TextFormat.PlainText)
        self.warnings_label.setWordWrap(True)
        self.warnings_label.setToolTip(warning_text)
        self.warnings_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        warnings_layout.addWidget(self.warnings_label)
        self.warnings_box.setCheckable(True)
        self.warnings_box.setChecked(True)
        self.warnings_box.setVisible(bool(check_result.warnings))
        layout.addWidget(self.warnings_box)

        self.selection_count_label = QLabel(web_apply_selection_count_text(0))
        self.selection_count_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.selection_count_label)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        configure_close_button(self.close_box)
        self.close_button = self.close_box.button(QDialogButtonBox.StandardButton.Close)
        self.close_button.setDefault(True)
        self.close_button.setAutoDefault(True)
        self.close_box.rejected.connect(self.reject)
        self.apply_button = QPushButton(WEB_APPLY_UI_BUTTON_LABEL)
        self.apply_button.setAutoDefault(False)
        self.apply_button.setDefault(False)
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self._on_apply_clicked)
        footer.addWidget(self.close_box)
        footer.addWidget(self.apply_button)
        layout.addLayout(footer)
        self._apply_unchanged_filter()
        self._update_apply_button()

    def _open_source(self) -> None:
        open_https_url(self._result.source_url, parent=self)

    def _set_checkable(
        self, item: QTreeWidgetItem, checkable: bool, *, tristate: bool = False
    ) -> None:
        flags = item.flags() & ~Qt.ItemFlag.ItemIsEditable
        flags &= ~Qt.ItemFlag.ItemIsUserTristate
        flags &= ~Qt.ItemFlag.ItemIsAutoTristate
        if checkable:
            flags |= Qt.ItemFlag.ItemIsUserCheckable
            if tristate:
                flags |= Qt.ItemFlag.ItemIsUserTristate
            item.setFlags(flags)
            item.setCheckState(_COL_STATUS, Qt.CheckState.Unchecked)
            return
        flags &= ~Qt.ItemFlag.ItemIsUserCheckable
        item.setFlags(flags)

    def _parent_action_text(self, diff) -> str:
        if diff.status in _PROTECTED_STATUSES:
            return WEB_APPLY_UI_PROTECTED_NOTICE
        return web_apply_parent_action_text(diff.status, diff.recommended_action)

    def _fill_tree(self) -> None:
        self.tree.clear()
        for index, diff in enumerate(self._result.diffs):
            parent = QTreeWidgetItem()
            status_text = web_diff_status_label(diff.status)
            name = _office_display_name(diff)
            count = str(len(diff.field_changes))
            action_text = self._parent_action_text(diff)
            parent.setText(_COL_STATUS, status_text)
            parent.setText(_COL_NAME, name)
            parent.setText(_COL_COUNT, count)
            parent.setText(_COL_ACTION, action_text)
            parent.setToolTip(_COL_STATUS, status_text)
            parent.setToolTip(_COL_NAME, name)
            action_tip = action_text
            if diff.status == WEB_DIFF_STATUS_MISSING_REMOTE:
                action_tip = WEB_APPLY_UI_MISSING_HINT
            parent.setToolTip(_COL_ACTION, action_tip)
            parent.setData(0, _ROLE_STATUS, diff.status)
            parent.setData(0, _ROLE_DIFF_INDEX, index)
            if diff.status in _FIELD_CHECK_STATUSES:
                self._set_checkable(parent, True, tristate=True)
            elif diff.status in _PARENT_CHECK_STATUSES:
                self._set_checkable(parent, True)
            else:
                self._set_checkable(parent, False)
            for change in diff.field_changes:
                child = QTreeWidgetItem()
                field_label = web_diff_field_label(change.field)
                old_text = format_web_diff_value(change.field, change.old_value)
                new_text = format_web_diff_value(change.field, change.new_value)
                erase = _is_erasure(change)
                child.setText(_COL_STATUS, field_label)
                child.setText(_COL_NAME, old_text)
                child.setText(_COL_COUNT, new_text)
                child.setText(_COL_ACTION, "")
                child.setToolTip(_COL_STATUS, field_label)
                child.setToolTip(
                    _COL_NAME, _value_tooltip(change.field, change.old_value, erase=False)
                )
                child.setToolTip(
                    _COL_COUNT,
                    _value_tooltip(change.field, change.new_value, erase=erase),
                )
                child.setData(0, _ROLE_FIELD, change.field)
                child.setData(0, _ROLE_DIFF_INDEX, index)
                field_checkable = diff.status in _FIELD_CHECK_STATUSES
                self._set_checkable(child, field_checkable)
                parent.addChild(child)
            self.tree.addTopLevelItem(parent)
            if diff.field_changes:
                parent.setExpanded(True)

    def _apply_unchanged_filter(self) -> None:
        show_unchanged = self.show_unchanged.isChecked()
        visible = 0
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            status = str(item.data(0, _ROLE_STATUS) or "")
            hide = status == WEB_DIFF_STATUS_UNCHANGED and not show_unchanged
            item.setHidden(hide)
            if not hide:
                visible += 1
        if visible == 0:
            self.tree.hide()
            self.empty_state_label.setVisible(True)
            if show_unchanged:
                self.empty_state_label.setText(web_check_headline(self._result.diffs))
            else:
                self.empty_state_label.setText(WEB_CHECK_UI_EMPTY_FILTER_TEXT)
            return
        self.tree.show()
        self.empty_state_label.hide()

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._syncing_checks or column != _COL_STATUS:
            return
        self._syncing_checks = True
        try:
            if item.parent() is None:
                self._sync_parent_to_children(item)
            else:
                self._sync_children_to_parent(item.parent())
        finally:
            self._syncing_checks = False
        self._update_apply_button()

    def _sync_parent_to_children(self, parent: QTreeWidgetItem) -> None:
        status = str(parent.data(0, _ROLE_STATUS) or "")
        if status not in _FIELD_CHECK_STATUSES:
            return
        state = parent.checkState(_COL_STATUS)
        if state == Qt.CheckState.PartiallyChecked:
            parent.setCheckState(_COL_STATUS, Qt.CheckState.Checked)
            state = Qt.CheckState.Checked
        child_state = (
            Qt.CheckState.Checked if state == Qt.CheckState.Checked else Qt.CheckState.Unchecked
        )
        for index in range(parent.childCount()):
            child = parent.child(index)
            if child.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                child.setCheckState(_COL_STATUS, child_state)

    def _sync_children_to_parent(self, parent: QTreeWidgetItem) -> None:
        status = str(parent.data(0, _ROLE_STATUS) or "")
        if status not in _FIELD_CHECK_STATUSES:
            return
        checkable = [
            parent.child(index)
            for index in range(parent.childCount())
            if parent.child(index).flags() & Qt.ItemFlag.ItemIsUserCheckable
        ]
        if not checkable:
            return
        checked = sum(
            1 for child in checkable if child.checkState(_COL_STATUS) == Qt.CheckState.Checked
        )
        if checked == 0:
            parent.setCheckState(_COL_STATUS, Qt.CheckState.Unchecked)
        elif checked == len(checkable):
            parent.setCheckState(_COL_STATUS, Qt.CheckState.Checked)
        else:
            parent.setCheckState(_COL_STATUS, Qt.CheckState.PartiallyChecked)

    def _item_checked(self, item: QTreeWidgetItem) -> bool:
        if not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
            return False
        return item.checkState(_COL_STATUS) == Qt.CheckState.Checked

    def current_selections(
        self, *, confirm_protected: bool = False
    ) -> tuple[ControlAuthorityOfficeWebApplySelection, ...]:
        selections: list[ControlAuthorityOfficeWebApplySelection] = []
        for index, diff in enumerate(self._result.diffs):
            item = self.tree.topLevelItem(index)
            if item is None:
                continue
            status = diff.status
            if status in _FIELD_CHECK_STATUSES:
                fields: list[str] = []
                for child_index, change in enumerate(diff.field_changes):
                    child = item.child(child_index)
                    if child is not None and self._item_checked(child):
                        fields.append(change.field)
                if not fields:
                    continue
                selections.append(
                    ControlAuthorityOfficeWebApplySelection(
                        external_key=str(diff.external_key or ""),
                        local_id=diff.local_id,
                        action=WEB_APPLY_ACTION_UPDATE,
                        selected_fields=frozenset(fields),
                        confirm_protected=bool(
                            confirm_protected and status == WEB_DIFF_STATUS_PROTECTED
                        ),
                    )
                )
                continue
            if not self._item_checked(item):
                continue
            if status == WEB_DIFF_STATUS_NEW:
                selections.append(
                    ControlAuthorityOfficeWebApplySelection(
                        external_key=str(diff.external_key or ""),
                        local_id=None,
                        action=WEB_APPLY_ACTION_CREATE,
                    )
                )
                continue
            if status in {
                WEB_DIFF_STATUS_MISSING_REMOTE,
                WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE,
            }:
                selections.append(
                    ControlAuthorityOfficeWebApplySelection(
                        external_key=str(diff.external_key or ""),
                        local_id=diff.local_id,
                        action=WEB_APPLY_ACTION_DEACTIVATE,
                        confirm_protected=bool(
                            confirm_protected
                            and status == WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE
                        ),
                    )
                )
                continue
            if status == WEB_DIFF_STATUS_INACTIVE_PRESENT:
                selections.append(
                    ControlAuthorityOfficeWebApplySelection(
                        external_key=str(diff.external_key or ""),
                        local_id=diff.local_id,
                        action=WEB_APPLY_ACTION_REACTIVATE,
                    )
                )
        return tuple(selections)

    def selection_summary(
        self, selections: Sequence | None = None
    ) -> WebApplySelectionSummary:
        chosen = (
            tuple(selections) if selections is not None else self.current_selections()
        )
        update_fields = 0
        creates = 0
        deactivates = 0
        reactivates = 0
        protected_records = 0
        erasures = 0
        diffs = {index: diff for index, diff in enumerate(self._result.diffs)}
        by_key = {
            (str(diff.external_key or ""), diff.local_id): diff
            for diff in diffs.values()
        }
        for selection in chosen:
            diff = by_key.get((selection.external_key, selection.local_id))
            if selection.action == WEB_APPLY_ACTION_UPDATE:
                update_fields += len(selection.selected_fields)
                if diff is not None:
                    if diff.status in _PROTECTED_STATUSES:
                        protected_records += 1
                    for change in diff.field_changes:
                        if change.field in selection.selected_fields and _is_erasure(
                            change
                        ):
                            erasures += 1
            elif selection.action == WEB_APPLY_ACTION_CREATE:
                creates += 1
            elif selection.action == WEB_APPLY_ACTION_DEACTIVATE:
                deactivates += 1
                if diff is not None and diff.status in _PROTECTED_STATUSES:
                    protected_records += 1
            elif selection.action == WEB_APPLY_ACTION_REACTIVATE:
                reactivates += 1
        return WebApplySelectionSummary(
            update_fields=update_fields,
            creates=creates,
            deactivates=deactivates,
            reactivates=reactivates,
            protected_records=protected_records,
            erasures=erasures,
        )

    def _update_apply_button(self) -> None:
        if self._consumed or self._stale or self._applying:
            self.apply_button.setEnabled(False)
            if self._stale:
                self.apply_button.hide()
            return
        summary = self.selection_summary()
        self.selection_count_label.setText(web_apply_selection_count_text(summary.total))
        self.apply_button.setEnabled(summary.total > 0)

    def _confirm_apply(self, summary: WebApplySelectionSummary) -> bool:
        dialog = ControlAuthorityWebApplyConfirmDialog(self, summary)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _enter_stale_mode(self) -> None:
        self._stale = True
        self.stale_label.show()
        self.apply_button.setEnabled(False)
        self.apply_button.hide()

    def _on_apply_clicked(self) -> None:
        if self._consumed or self._stale or self._applying:
            return
        selections = self.current_selections(confirm_protected=False)
        if not selections:
            return
        summary = self.selection_summary(selections)
        if not self._confirm_apply(summary):
            return
        selections = self.current_selections(confirm_protected=True)
        if not selections:
            return
        self._applying = True
        self.apply_button.setEnabled(False)
        try:
            result = apply_authority_web_changes(self._result, selections)
        except ControlAuthorityWebApplyError as exc:
            logger.exception("Použití webových změn katalogu selhalo.")
            if exc.code == WEB_APPLY_ERROR_STALE:
                self._applying = False
                self._enter_stale_mode()
                QMessageBox.warning(self, WEB_CHECK_UI_DIALOG_TITLE, WEB_APPLY_UI_STALE)
                return
            QMessageBox.warning(
                self,
                WEB_CHECK_UI_DIALOG_TITLE,
                web_apply_error_user_message(exc),
            )
            self._applying = False
            self._update_apply_button()
            return
        except Exception:
            logger.exception("Použití webových změn katalogu selhalo.")
            QMessageBox.warning(
                self, WEB_CHECK_UI_DIALOG_TITLE, WEB_APPLY_UI_ERROR
            )
            self._applying = False
            self._update_apply_button()
            return
        self._consumed = True
        self.apply_result = result
        self.apply_button.setEnabled(False)
        self.accept()
