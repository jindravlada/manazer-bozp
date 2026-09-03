"""Read-only dialog náhledu rozdílů webové kontroly katalogu."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.utils.https_url import open_https_url
from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_close_box,
)
from core.widgets.table_utils import configure_tree_columns
from moduly.statni_dozor.constants import (
    CATALOG_ROW_KIND_AUTHORITY,
    EMPTY_VALUE,
    WEB_CHECK_UI_DIALOG_TITLE,
    WEB_CHECK_UI_EMPTY_FILTER_TEXT,
    WEB_CHECK_UI_EMPTY_WEB_VALUE_TOOLTIP,
    WEB_CHECK_UI_READONLY_NOTICE,
    WEB_CHECK_UI_SHOW_UNCHANGED_LABEL,
    WEB_CHECK_UI_WARNINGS_TITLE,
    WEB_DIFF_STATUS_UNCHANGED,
)
from moduly.statni_dozor.sluzby.control_authority_web.check import (
    ControlAuthorityWebCheckResult,
)
from moduly.statni_dozor.sluzby.control_authority_web.labels import (
    format_web_checked_at,
    format_web_diff_value,
    web_check_headline,
    web_check_summary_lines,
    web_diff_action_label,
    web_diff_field_label,
    web_diff_status_label,
)

_ROLE_STATUS = Qt.ItemDataRole.UserRole
_ROLE_FIELD = Qt.ItemDataRole.UserRole + 1
_COL_STATUS = 0
_COL_NAME = 1
_COL_COUNT = 2
_COL_ACTION = 3


def _office_display_name(diff) -> str:
    if diff.local is not None and str(diff.local.name or "").strip():
        return str(diff.local.name)
    if diff.remote is not None and str(diff.remote.name or "").strip():
        return str(diff.remote.name)
    return EMPTY_VALUE


def _value_tooltip(field: str, value: str | None, *, web_empty: bool) -> str:
    if web_empty:
        return WEB_CHECK_UI_EMPTY_WEB_VALUE_TOOLTIP
    text = format_web_diff_value(field, value)
    if text == EMPTY_VALUE:
        return ""
    return text


class ControlAuthorityWebPreviewDialog(QDialog):
    """Read-only přehled rozdílů. Nic do katalogu nezapisuje."""

    def __init__(
        self,
        parent: QWidget | None,
        check_result: ControlAuthorityWebCheckResult,
    ):
        super().__init__(parent)
        self._result = check_result
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

        self.close_box = create_close_box(self)
        self.close_box.rejected.connect(self.reject)
        layout.addWidget(self.close_box)
        self._apply_unchanged_filter()

    def _open_source(self) -> None:
        open_https_url(self._result.source_url, parent=self)

    def _fill_tree(self) -> None:
        self.tree.clear()
        for diff in self._result.diffs:
            parent = QTreeWidgetItem()
            status_text = web_diff_status_label(diff.status)
            name = _office_display_name(diff)
            count = str(len(diff.field_changes))
            action_text = web_diff_action_label(diff.recommended_action)
            parent.setText(_COL_STATUS, status_text)
            parent.setText(_COL_NAME, name)
            parent.setText(_COL_COUNT, count)
            parent.setText(_COL_ACTION, action_text)
            parent.setToolTip(_COL_STATUS, status_text)
            parent.setToolTip(_COL_NAME, name)
            parent.setToolTip(_COL_ACTION, action_text)
            parent.setData(0, _ROLE_STATUS, diff.status)
            parent.setFlags(parent.flags() & ~Qt.ItemFlag.ItemIsEditable)
            for change in diff.field_changes:
                child = QTreeWidgetItem()
                field_label = web_diff_field_label(change.field)
                old_text = format_web_diff_value(change.field, change.old_value)
                new_text = format_web_diff_value(change.field, change.new_value)
                web_empty = change.new_value is None or str(change.new_value).strip() == ""
                child.setText(_COL_STATUS, field_label)
                child.setText(_COL_NAME, old_text)
                child.setText(_COL_COUNT, new_text)
                child.setText(_COL_ACTION, "")
                child.setToolTip(_COL_STATUS, field_label)
                child.setToolTip(
                    _COL_NAME, _value_tooltip(change.field, change.old_value, web_empty=False)
                )
                child.setToolTip(
                    _COL_COUNT,
                    _value_tooltip(change.field, change.new_value, web_empty=web_empty),
                )
                child.setData(0, _ROLE_FIELD, change.field)
                child.setFlags(child.flags() & ~Qt.ItemFlag.ItemIsEditable)
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
