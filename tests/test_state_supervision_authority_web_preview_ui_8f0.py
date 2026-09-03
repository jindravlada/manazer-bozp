"""STATE-SUPERVISION-AUTHORITY-WEB-PREVIEW-UI-8F0: ruční kontrola a náhled."""

from __future__ import annotations

import importlib
import inspect
import os
import sqlite3
import tempfile
import threading
import unittest
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-web-preview-8f0-"))
_HOME_PATCHER = patch.object(Path, "home", return_value=_HOME)
_HOME_PATCHER.start()

import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()

import core.database.session as session_module

importlib.reload(session_module)
from core.database.database_initializer import initialize_database

initialize_database()

from PySide6.QtCore import QEvent, QEventLoop, Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox, QPushButton
from shiboken6 import delete as shiboken_delete, isValid

from moduly.nastaveni.ui.nastaveni_page import NastaveniPage
from moduly.statni_dozor.constants import (
    CBU_AUTHORITY_CODE,
    DU_AUTHORITY_CODE,
    DU_OFFICES_SOURCE_URL,
    EMPTY_VALUE,
    HZS_AUTHORITY_CODE,
    KHS_AUTHORITY_CODE,
    OFFICE_KIND_HEADQUARTERS,
    OFFICE_KIND_USER_LABELS,
    SUIP_AUTHORITY_CODE,
    WEB_ADAPTER_ERROR_NETWORK,
    WEB_ADAPTER_ERROR_TIMEOUT,
    WEB_ADAPTER_ERROR_UNREADABLE_HTML,
    WEB_CHECK_ERROR_UNSUPPORTED,
    WEB_CHECK_UI_ALL_MATCH_TEXT,
    WEB_CHECK_UI_BUTTON_LABEL,
    WEB_CHECK_UI_DIALOG_TITLE,
    WEB_CHECK_UI_DIFFERENCES_TEXT,
    WEB_CHECK_UI_EMPTY_FILTER_TEXT,
    WEB_CHECK_UI_EMPTY_WEB_VALUE_TOOLTIP,
    WEB_CHECK_UI_ERROR_NETWORK,
    WEB_CHECK_UI_ERROR_OTHER,
    WEB_CHECK_UI_ERROR_STRUCTURE,
    WEB_CHECK_UI_ERROR_UNSUPPORTED,
    WEB_CHECK_UI_READONLY_NOTICE,
    WEB_CHECK_UI_TOOLTIP_NO_SELECTION,
    WEB_CHECK_UI_TOOLTIP_SUPPORTED,
    WEB_CHECK_UI_TOOLTIP_UNSUPPORTED,
    WEB_CHECK_UI_UNKNOWN_STATUS_LABEL,
    WEB_DIFF_ACTION_CREATE,
    WEB_DIFF_ACTION_DEACTIVATE,
    WEB_DIFF_ACTION_NONE,
    WEB_DIFF_ACTION_REACTIVATE,
    WEB_DIFF_ACTION_REVIEW,
    WEB_DIFF_ACTION_UPDATE,
    WEB_DIFF_ACTION_USER_LABELS,
    WEB_DIFF_ERROR_INCOMPLETE,
    WEB_DIFF_FIELD_USER_LABELS,
    WEB_DIFF_STATUS_CHANGED,
    WEB_DIFF_STATUS_IDENTITY_CONFLICT,
    WEB_DIFF_STATUS_INACTIVE_PRESENT,
    WEB_DIFF_STATUS_MISSING_REMOTE,
    WEB_DIFF_STATUS_NEW,
    WEB_DIFF_STATUS_POSSIBLE_DUPLICATE,
    WEB_DIFF_STATUS_PROTECTED,
    WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE,
    WEB_DIFF_STATUS_UNCHANGED,
    WEB_DIFF_STATUS_USER_LABELS,
    WEB_DIFF_SUMMARY_CHANGED,
    WEB_DIFF_SUMMARY_MISSING,
    WEB_DIFF_SUMMARY_NEW,
    WEB_DIFF_SUMMARY_REVIEW,
    WEB_DIFF_SUMMARY_UNCHANGED,
)
from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
    control_authority_catalog_service,
)
from moduly.statni_dozor.sluzby.control_authority_web.check import (
    ControlAuthorityWebAdapterInfo,
    ControlAuthorityWebCheckError,
    ControlAuthorityWebCheckResult,
    has_web_adapter,
    supported_authority_codes,
)
from moduly.statni_dozor.sluzby.control_authority_web.diff_models import (
    ControlAuthorityOfficeCatalogSnapshot,
    ControlAuthorityOfficeDiff,
    ControlAuthorityOfficeFieldChange,
)
from moduly.statni_dozor.sluzby.control_authority_web.labels import (
    format_web_diff_value,
    web_check_error_user_message,
    web_diff_action_label,
    web_diff_field_label,
    web_diff_status_label,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityOfficeWebRecord,
)
from moduly.statni_dozor.ui.control_authority_catalog_tab import (
    ControlAuthorityCatalogTab,
)
from moduly.statni_dozor.ui.control_authority_dialog import ControlAuthorityDialog
from moduly.statni_dozor.ui.control_authority_web_preview_dialog import (
    ControlAuthorityWebPreviewDialog,
)

_HOME_PATCHER.stop()

_CHECK = "moduly.statni_dozor.ui.control_authority_catalog_tab.check_authority_web"
_HAS_ADAPTER = "moduly.statni_dozor.ui.control_authority_catalog_tab.has_web_adapter"
_FIXED_AT = datetime(2026, 9, 3, 8, 15, 0)
_SOURCE_URL = DU_OFFICES_SOURCE_URL
_ADAPTER = ControlAuthorityWebAdapterInfo(
    authority_code=DU_AUTHORITY_CODE,
    display_name="Drážní úřad",
    source_name="Kontakty Drážního úřadu",
    source_url=_SOURCE_URL,
    expected_office_count=3,
)


class _SignalLog:
    def __init__(self, signal) -> None:
        self.items: list[tuple] = []
        self._signal = signal
        signal.connect(self._on)

    def _on(self, *args) -> None:
        self.items.append(args)

    def wait(self, timeout_ms: int = 4000) -> None:
        if self.items:
            return
        loop = QEventLoop()

        def _quit(*_args) -> None:
            loop.quit()

        self._signal.connect(_quit)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(timeout_ms)
        loop.exec()
        self._signal.disconnect(_quit)
        timer.stop()
        if not self.items:
            raise AssertionError("Očekávaný signál nedorazil.")


def _remote(**overrides) -> ControlAuthorityOfficeWebRecord:
    values = {
        "authority_code": DU_AUTHORITY_CODE,
        "external_key": "du:praha",
        "name": "Drážní úřad Praha",
        "address": "Wilsonova 300/8, Praha",
        "phone": "226 523 368",
        "email": "praha@du.gov.cz",
        "website": "https://du.gov.cz/",
        "territorial_scope": "Praha",
        "office_kind": OFFICE_KIND_HEADQUARTERS,
        "source_url": _SOURCE_URL,
        "observed_fields": frozenset(WEB_DIFF_FIELD_USER_LABELS),
    }
    values.update(overrides)
    return ControlAuthorityOfficeWebRecord(**values)


def _local(**overrides) -> ControlAuthorityOfficeCatalogSnapshot:
    values = {
        "id": 11,
        "authority_id": 1,
        "authority_code": DU_AUTHORITY_CODE,
        "external_key": "du:praha",
        "name": "Drážní úřad Praha",
        "address": "Wilsonova 300/8, Praha",
        "phone": "226 523 368",
        "email": "praha@du.gov.cz",
        "website": "https://du.gov.cz/",
        "territorial_scope": "Praha",
        "office_kind": OFFICE_KIND_HEADQUARTERS,
        "source_url": _SOURCE_URL,
        "active": True,
        "origin": "bundled",
        "user_edited_at": None,
        "last_checked_at": None,
    }
    values.update(overrides)
    return ControlAuthorityOfficeCatalogSnapshot(**values)


def _diff(
    *,
    status: str,
    action: str,
    review: bool = False,
    local=None,
    remote=None,
    field_changes=(),
) -> ControlAuthorityOfficeDiff:
    return ControlAuthorityOfficeDiff(
        status=status,
        authority_code=DU_AUTHORITY_CODE,
        external_key=(
            local.external_key
            if local is not None
            else (remote.external_key if remote is not None else None)
        ),
        local_id=None if local is None else local.id,
        local=local,
        remote=remote,
        field_changes=tuple(field_changes),
        recommended_action=action,
        requires_manual_review=review,
        reason="",
    )


def _result(
    diffs: tuple[ControlAuthorityOfficeDiff, ...] = (),
    *,
    warnings: tuple[str, ...] = (),
    remote_records: tuple[ControlAuthorityOfficeWebRecord, ...] | None = None,
) -> ControlAuthorityWebCheckResult:
    records = remote_records
    if records is None:
        records = tuple(item.remote for item in diffs if item.remote is not None)
    return ControlAuthorityWebCheckResult(
        authority_code=DU_AUTHORITY_CODE,
        adapter_info=_ADAPTER,
        fetched_at=_FIXED_AT,
        source_url=_SOURCE_URL,
        remote_records=records,
        diffs=diffs,
        status_counts=(),
        warnings=warnings,
    )


def _catalog_stamps(db_path: Path) -> tuple[list[tuple], list[tuple], list[tuple]]:
    conn = sqlite3.connect(str(db_path))
    try:
        authorities = list(
            conn.execute(
                "SELECT id, code, origin, active, user_edited_at, last_checked_at, "
                "updated_at FROM control_authorities ORDER BY id"
            ).fetchall()
        )
        offices = list(
            conn.execute(
                "SELECT id, authority_id, origin, active, user_edited_at, "
                "last_checked_at, updated_at FROM control_authority_offices ORDER BY id"
            ).fetchall()
        )
        supervisions = list(
            conn.execute(
                "SELECT id, authority_ico, authority_name, authority_office_id, "
                "updated_at FROM state_supervisions ORDER BY id"
            ).fetchall()
        )
        return authorities, offices, supervisions
    finally:
        conn.close()


def _parent_by_status(dialog: ControlAuthorityWebPreviewDialog, status: str):
    for index in range(dialog.tree.topLevelItemCount()):
        item = dialog.tree.topLevelItem(index)
        if item.data(0, Qt.ItemDataRole.UserRole) == status:
            return item
    return None


def _child_by_field(parent, field: str):
    for index in range(parent.childCount()):
        child = parent.child(index)
        if child.data(0, Qt.ItemDataRole.UserRole + 1) == field:
            return child
    return None


class StateSupervisionAuthorityWebPreviewLabels8f0TestCase(unittest.TestCase):
    def test_01_status_field_action_labels(self) -> None:
        for status, label in WEB_DIFF_STATUS_USER_LABELS.items():
            self.assertEqual(web_diff_status_label(status), label)
        for field, label in WEB_DIFF_FIELD_USER_LABELS.items():
            self.assertEqual(web_diff_field_label(field), label)
        for action, label in WEB_DIFF_ACTION_USER_LABELS.items():
            self.assertEqual(web_diff_action_label(action), label)

    def test_02_unknown_status_field_action_do_not_crash(self) -> None:
        with self.assertLogs(
            "moduly.statni_dozor.sluzby.control_authority_web.labels",
            level="WARNING",
        ):
            self.assertEqual(web_diff_status_label("nope"), WEB_CHECK_UI_UNKNOWN_STATUS_LABEL)
            self.assertEqual(web_diff_field_label("mystery"), "Údaj")
            self.assertEqual(web_diff_action_label("explode"), "Vyžaduje posouzení")

    def test_03_error_mapping(self) -> None:
        self.assertEqual(
            web_check_error_user_message(
                ControlAuthorityWebCheckError("x", code=WEB_ADAPTER_ERROR_NETWORK)
            ),
            WEB_CHECK_UI_ERROR_NETWORK,
        )
        self.assertEqual(
            web_check_error_user_message(
                ControlAuthorityWebCheckError("x", code=WEB_ADAPTER_ERROR_TIMEOUT)
            ),
            WEB_CHECK_UI_ERROR_NETWORK,
        )
        self.assertEqual(
            web_check_error_user_message(
                ControlAuthorityWebCheckError("x", code=WEB_DIFF_ERROR_INCOMPLETE)
            ),
            WEB_CHECK_UI_ERROR_STRUCTURE,
        )
        self.assertEqual(
            web_check_error_user_message(
                ControlAuthorityWebCheckError("x", code=WEB_ADAPTER_ERROR_UNREADABLE_HTML)
            ),
            WEB_CHECK_UI_ERROR_STRUCTURE,
        )
        self.assertEqual(
            web_check_error_user_message(
                ControlAuthorityWebCheckError("x", code=WEB_CHECK_ERROR_UNSUPPORTED)
            ),
            WEB_CHECK_UI_ERROR_UNSUPPORTED,
        )
        self.assertEqual(
            web_check_error_user_message(ControlAuthorityWebCheckError("x", code="adapter")),
            WEB_CHECK_UI_ERROR_OTHER,
        )
        wrapped = ControlAuthorityWebCheckError("x", code="adapter")
        wrapped.__cause__ = ControlAuthorityWebCheckError(
            "y", code=WEB_ADAPTER_ERROR_NETWORK
        )
        self.assertEqual(web_check_error_user_message(wrapped), WEB_CHECK_UI_ERROR_NETWORK)

    def test_04_labels_module_has_no_qt(self) -> None:
        from moduly.statni_dozor.sluzby.control_authority_web import labels as labels_mod

        source = inspect.getsource(labels_mod)
        self.assertNotIn("PySide", source)
        self.assertNotIn("PyQt", source)


class StateSupervisionAuthorityWebPreviewUi8f0TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls._home = patch.object(Path, "home", return_value=_HOME)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        self.db = storage_module.storage_service.database_path
        self.catalog = control_authority_catalog_service
        self.marker = uuid.uuid4().hex[:8]
        self.page = NastaveniPage()
        self.tab: ControlAuthorityCatalogTab = self.page.state_supervision_catalog_tab
        self._warn = patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok)
        self.warn_mock = self._warn.start()

    def tearDown(self) -> None:
        self._warn.stop()
        self.page.close()

    def _select_kind(self, kind: str, record_id: int) -> None:
        self.tab._restore_selection(kind, record_id)
        self.tab.update_buttons()

    def _select_code(self, code: str) -> None:
        authority = self.catalog.get_authority_by_code(code)
        assert authority is not None
        self._select_kind("authority", int(authority.id))

    def _run_check(self, fake, *, expect_dialog: bool = True):
        opened: list[object] = []

        def capture(dialog) -> int:
            opened.append(dialog)
            return 0

        finished = _SignalLog(self.tab._web_check_runner.finished)
        with patch(_CHECK, side_effect=fake), patch.object(
            self.tab, "_exec_dialog", side_effect=capture
        ):
            self.tab.web_check_button.click()
            finished.wait()
        if expect_dialog:
            self.assertEqual(len(opened), 1)
            return opened[0]
        self.assertEqual(opened, [])
        return None

    def test_01_button_disabled_without_selection(self) -> None:
        self.tab.tree.clearSelection()
        self.tab.update_buttons()
        self.assertEqual(self.tab.web_check_button.text(), WEB_CHECK_UI_BUTTON_LABEL)
        self.assertFalse(self.tab.web_check_button.isEnabled())
        self.assertEqual(
            self.tab.web_check_button.toolTip(), WEB_CHECK_UI_TOOLTIP_NO_SELECTION
        )

    def test_02_supported_authority_enables_button(self) -> None:
        self._select_code(SUIP_AUTHORITY_CODE)
        self.assertTrue(self.tab.web_check_button.isEnabled())
        self.assertEqual(
            self.tab.web_check_button.toolTip(), WEB_CHECK_UI_TOOLTIP_SUPPORTED
        )
        self.assertTrue(has_web_adapter(SUIP_AUTHORITY_CODE))

    def test_03_office_selection_checks_parent_authority(self) -> None:
        office = self.catalog.get_office_by_external_key("suip:oip-praha")
        assert office is not None
        self._select_kind("office", int(office.id))
        self.assertTrue(self.tab.web_check_button.isEnabled())
        codes: list[str] = []

        def fake(code: str):
            codes.append(code)
            return _result()

        self._run_check(fake, expect_dialog=True)
        self.assertEqual(codes, [SUIP_AUTHORITY_CODE])

    def test_04_manual_authority_without_adapter_disabled(self) -> None:
        created = self.catalog.create_authority(
            code=f"man-{self.marker}",
            name=f"Ruční orgán {self.marker}",
        )
        self.tab.refresh()
        self._select_kind("authority", int(created.id))
        self.assertFalse(self.tab.web_check_button.isEnabled())
        self.assertEqual(
            self.tab.web_check_button.toolTip(), WEB_CHECK_UI_TOOLTIP_UNSUPPORTED
        )
        self.assertFalse(has_web_adapter(created.code))

    def test_05_supported_codes_come_from_8e0(self) -> None:
        source = inspect.getsource(ControlAuthorityCatalogTab)
        module_source = inspect.getsource(
            inspect.getmodule(ControlAuthorityCatalogTab)
        )
        self.assertIn("has_web_adapter", source)
        self.assertIn("check_authority_web", module_source)
        self.assertIn("LongOperationRunner", source)
        for name in (
            "SUIP_AUTHORITY_CODE",
            "DU_AUTHORITY_CODE",
            "CBU_AUTHORITY_CODE",
            "KHS_AUTHORITY_CODE",
            "HZS_AUTHORITY_CODE",
        ):
            self.assertNotIn(name, source)
        self.assertEqual(
            supported_authority_codes(),
            (
                DU_AUTHORITY_CODE,
                SUIP_AUTHORITY_CODE,
                CBU_AUTHORITY_CODE,
                KHS_AUTHORITY_CODE,
                HZS_AUTHORITY_CODE,
            ),
        )
        self._select_code(SUIP_AUTHORITY_CODE)
        with patch(_HAS_ADAPTER, return_value=False):
            self.tab.update_buttons()
            self.assertFalse(self.tab.web_check_button.isEnabled())
        self.tab.update_buttons()
        self.assertTrue(self.tab.web_check_button.isEnabled())

    def test_06_filter_and_expand_do_not_start_check(self) -> None:
        with patch(_CHECK) as check:
            self.tab.filter_bar.search_edit.setText("suip")
            parent = self.tab.tree.topLevelItem(0)
            parent.setExpanded(False)
            parent.setExpanded(True)
            self.tab.filter_bar.search_edit.clear()
            check.assert_not_called()

    def test_07_double_click_opens_editor_not_web_check(self) -> None:
        self._select_code(SUIP_AUTHORITY_CODE)
        item = self.tab.tree.currentItem()
        with patch(_CHECK) as check, patch.object(
            self.tab, "_exec_dialog", return_value=0
        ) as exec_dialog:
            self.tab.tree.itemDoubleClicked.emit(item, 0)
            check.assert_not_called()
            exec_dialog.assert_called_once()
            self.assertIsInstance(exec_dialog.call_args[0][0], ControlAuthorityDialog)

    def test_08_second_start_blocked_while_running(self) -> None:
        self._select_code(DU_AUTHORITY_CODE)
        entered = threading.Event()
        release = threading.Event()
        calls: list[str] = []

        def fake(code: str):
            calls.append(code)
            entered.set()
            release.wait(timeout=5)
            return _result()

        finished = _SignalLog(self.tab._web_check_runner.finished)
        with patch(_CHECK, side_effect=fake), patch.object(
            self.tab, "_exec_dialog", return_value=0
        ):
            self.tab.web_check_button.click()
            self.assertTrue(entered.wait(timeout=2))
            self.assertTrue(self.tab._web_check_runner.is_running())
            self.assertFalse(self.tab.web_check_button.isEnabled())
            self.tab.start_web_check()
            self.tab.web_check_button.click()
            self.assertEqual(calls, [DU_AUTHORITY_CODE])
            release.set()
            finished.wait()
        self.assertEqual(len(calls), 1)

    def test_09_dialog_header_source_and_readonly(self) -> None:
        remote = _remote()
        dialog = ControlAuthorityWebPreviewDialog(
            self.tab,
            _result((_diff(
                status=WEB_DIFF_STATUS_CHANGED,
                action=WEB_DIFF_ACTION_UPDATE,
                local=_local(),
                remote=remote,
                field_changes=(
                    ControlAuthorityOfficeFieldChange("phone", "111", "222"),
                ),
            ),), remote_records=(remote,)),
        )
        self.assertEqual(dialog.windowTitle(), WEB_CHECK_UI_DIALOG_TITLE)
        self.assertEqual(dialog.authority_label.text(), "Drážní úřad")
        self.assertEqual(dialog.source_label.text(), "Kontakty Drážního úřadu")
        self.assertEqual(dialog.checked_at_label.text(), "03. 09. 2026 08:15")
        self.assertEqual(dialog.office_count_label.text(), "1")
        self.assertEqual(dialog.readonly_label.text(), WEB_CHECK_UI_READONLY_NOTICE)
        self.assertEqual(dialog.headline_label.text(), WEB_CHECK_UI_DIFFERENCES_TEXT)
        self.assertNotIn(DU_AUTHORITY_CODE, dialog.authority_label.text())
        self.assertNotIn("du:praha", dialog.tree.topLevelItem(0).text(1))
        with patch(
            "moduly.statni_dozor.ui.control_authority_web_preview_dialog.open_https_url"
        ) as opener:
            dialog.open_source_button.click()
            opener.assert_called_once_with(_SOURCE_URL, parent=dialog)
        dialog.close()

    def test_10_czech_summary_and_unchanged_filter(self) -> None:
        diffs = (
            _diff(
                status=WEB_DIFF_STATUS_UNCHANGED,
                action=WEB_DIFF_ACTION_NONE,
                local=_local(id=1, name="Beze změny", external_key="du:u"),
                remote=_remote(name="Beze změny", external_key="du:u"),
            ),
            _diff(
                status=WEB_DIFF_STATUS_CHANGED,
                action=WEB_DIFF_ACTION_UPDATE,
                local=_local(id=2, name="Změna", external_key="du:c"),
                remote=_remote(name="Změna", external_key="du:c"),
                field_changes=(
                    ControlAuthorityOfficeFieldChange("address", "A", "B"),
                ),
            ),
            _diff(
                status=WEB_DIFF_STATUS_NEW,
                action=WEB_DIFF_ACTION_CREATE,
                remote=_remote(name="Nové", external_key="du:n"),
            ),
            _diff(
                status=WEB_DIFF_STATUS_MISSING_REMOTE,
                action=WEB_DIFF_ACTION_DEACTIVATE,
                local=_local(id=3, name="Chybí", external_key="du:m"),
            ),
            _diff(
                status=WEB_DIFF_STATUS_PROTECTED,
                action=WEB_DIFF_ACTION_REVIEW,
                review=True,
                local=_local(id=4, name="Ruční", external_key="du:p"),
                remote=_remote(name="Ruční", external_key="du:p"),
            ),
            _diff(
                status=WEB_DIFF_STATUS_IDENTITY_CONFLICT,
                action=WEB_DIFF_ACTION_REVIEW,
                review=True,
                local=_local(id=5, name="Konflikt", external_key="du:i"),
                remote=_remote(name="Konflikt", external_key="du:i"),
            ),
        )
        dialog = ControlAuthorityWebPreviewDialog(self.tab, _result(diffs))
        summary = dialog.summary_label.text()
        self.assertIn(f"{WEB_DIFF_SUMMARY_UNCHANGED}: 1", summary)
        self.assertIn(f"{WEB_DIFF_SUMMARY_CHANGED}: 1", summary)
        self.assertIn(f"{WEB_DIFF_SUMMARY_NEW}: 1", summary)
        self.assertIn(f"{WEB_DIFF_SUMMARY_MISSING}: 1", summary)
        self.assertIn(f"{WEB_DIFF_SUMMARY_REVIEW}: 2", summary)
        self.assertFalse(dialog.show_unchanged.isChecked())
        unchanged = _parent_by_status(dialog, WEB_DIFF_STATUS_UNCHANGED)
        changed = _parent_by_status(dialog, WEB_DIFF_STATUS_CHANGED)
        assert unchanged is not None and changed is not None
        self.assertTrue(unchanged.isHidden())
        self.assertFalse(changed.isHidden())
        dialog.show_unchanged.setChecked(True)
        self.assertFalse(unchanged.isHidden())
        dialog.close()

    def test_11_all_status_and_field_labels_and_empty_web_value(self) -> None:
        field_changes = tuple(
            ControlAuthorityOfficeFieldChange(field, f"old-{field}", f"new-{field}")
            for field in WEB_DIFF_FIELD_USER_LABELS
        ) + (
            ControlAuthorityOfficeFieldChange("phone", "111 222", None),
        )
        statuses = (
            (WEB_DIFF_STATUS_UNCHANGED, WEB_DIFF_ACTION_NONE, False),
            (WEB_DIFF_STATUS_NEW, WEB_DIFF_ACTION_CREATE, False),
            (WEB_DIFF_STATUS_CHANGED, WEB_DIFF_ACTION_UPDATE, False),
            (WEB_DIFF_STATUS_PROTECTED, WEB_DIFF_ACTION_REVIEW, True),
            (WEB_DIFF_STATUS_MISSING_REMOTE, WEB_DIFF_ACTION_DEACTIVATE, False),
            (WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE, WEB_DIFF_ACTION_REVIEW, True),
            (WEB_DIFF_STATUS_INACTIVE_PRESENT, WEB_DIFF_ACTION_REACTIVATE, False),
            (WEB_DIFF_STATUS_POSSIBLE_DUPLICATE, WEB_DIFF_ACTION_REVIEW, True),
            (WEB_DIFF_STATUS_IDENTITY_CONFLICT, WEB_DIFF_ACTION_REVIEW, True),
            ("totally-unknown", "explode", True),
        )
        diffs = []
        for index, (status, action, review) in enumerate(statuses):
            local = _local(id=index + 1, name=f"Pracoviště {index}", external_key=f"du:{index}")
            remote = _remote(name=f"Pracoviště {index}", external_key=f"du:{index}")
            diffs.append(
                _diff(
                    status=status,
                    action=action,
                    review=review,
                    local=None if status == WEB_DIFF_STATUS_NEW else local,
                    remote=None if status in {
                        WEB_DIFF_STATUS_MISSING_REMOTE,
                        WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE,
                    } else remote,
                    field_changes=field_changes if status == WEB_DIFF_STATUS_CHANGED else (),
                )
            )
        dialog = ControlAuthorityWebPreviewDialog(self.tab, _result(tuple(diffs)))
        dialog.show_unchanged.setChecked(True)
        for status, action, review in statuses:
            parent = _parent_by_status(dialog, status)
            self.assertIsNotNone(parent, status)
            assert parent is not None
            if status == "totally-unknown":
                self.assertEqual(parent.text(0), WEB_CHECK_UI_UNKNOWN_STATUS_LABEL)
            else:
                self.assertEqual(parent.text(0), WEB_DIFF_STATUS_USER_LABELS[status])
            if action in WEB_DIFF_ACTION_USER_LABELS:
                self.assertEqual(parent.text(3), WEB_DIFF_ACTION_USER_LABELS[action])
            if review:
                self.assertEqual(parent.text(3), WEB_DIFF_ACTION_USER_LABELS[WEB_DIFF_ACTION_REVIEW] if action == WEB_DIFF_ACTION_REVIEW else parent.text(3))
        changed = _parent_by_status(dialog, WEB_DIFF_STATUS_CHANGED)
        assert changed is not None
        for field, label in WEB_DIFF_FIELD_USER_LABELS.items():
            child = _child_by_field(changed, field)
            self.assertIsNotNone(child, field)
            assert child is not None
            self.assertEqual(child.text(0), label)
            if field == "office_kind":
                self.assertEqual(
                    child.text(1),
                    format_web_diff_value(field, f"old-{field}"),
                )
            else:
                self.assertEqual(child.text(1), f"old-{field}")
                self.assertEqual(child.text(2), f"new-{field}")
        empty = _child_by_field(changed, "phone")
        assert empty is not None
        # poslední změna phone přepíše předchozí child se stejným polem; ověříme None samostatně
        dialog.close()

        none_diff = _diff(
            status=WEB_DIFF_STATUS_CHANGED,
            action=WEB_DIFF_ACTION_UPDATE,
            local=_local(),
            remote=_remote(phone=None),
            field_changes=(
                ControlAuthorityOfficeFieldChange("phone", "111 222", None),
            ),
        )
        dialog = ControlAuthorityWebPreviewDialog(self.tab, _result((none_diff,)))
        parent = dialog.tree.topLevelItem(0)
        child = parent.child(0)
        self.assertEqual(child.text(1), "111 222")
        self.assertEqual(child.text(2), EMPTY_VALUE)
        self.assertEqual(child.toolTip(2), WEB_CHECK_UI_EMPTY_WEB_VALUE_TOOLTIP)
        self.assertEqual(
            dialog.tree.textElideMode(), Qt.TextElideMode.ElideRight
        )
        dialog.close()

    def test_12_warnings_empty_state_and_close_only(self) -> None:
        warning = "Část stránky <b>nebyla</b> přečtena."
        mixed = _diff(
            status=WEB_DIFF_STATUS_CHANGED,
            action=WEB_DIFF_ACTION_UPDATE,
            local=_local(),
            remote=_remote(),
            field_changes=(ControlAuthorityOfficeFieldChange("name", "A", "B"),),
        )
        dialog = ControlAuthorityWebPreviewDialog(
            self.tab, _result((mixed,), warnings=(warning,))
        )
        self.assertFalse(dialog.warnings_box.isHidden())
        self.assertEqual(dialog.warnings_label.text(), warning)
        self.assertEqual(dialog.warnings_label.toolTip(), warning)
        self.assertEqual(dialog.warnings_label.textFormat(), Qt.TextFormat.PlainText)
        buttons = [
            widget.text()
            for widget in dialog.findChildren(QPushButton)
            if widget is not dialog.open_source_button
        ]
        self.assertIn("Zavřít", buttons)
        self.assertNotIn("Použít", " ".join(buttons))
        self.assertNotIn("Použít změny", " ".join(buttons))
        self.assertIsNotNone(
            dialog.close_box.button(QDialogButtonBox.StandardButton.Close)
        )
        self.assertIsNone(dialog.close_box.button(QDialogButtonBox.StandardButton.Save))
        dialog.close()

        unchanged = _diff(
            status=WEB_DIFF_STATUS_UNCHANGED,
            action=WEB_DIFF_ACTION_NONE,
            local=_local(),
            remote=_remote(),
        )
        empty = ControlAuthorityWebPreviewDialog(self.tab, _result((unchanged,)))
        self.assertEqual(empty.headline_label.text(), WEB_CHECK_UI_ALL_MATCH_TEXT)
        self.assertFalse(empty.show_unchanged.isChecked())
        self.assertFalse(empty.empty_state_label.isHidden())
        self.assertEqual(empty.empty_state_label.text(), WEB_CHECK_UI_EMPTY_FILTER_TEXT)
        self.assertTrue(empty.tree.isHidden())
        empty.show_unchanged.setChecked(True)
        self.assertTrue(empty.empty_state_label.isHidden())
        self.assertFalse(empty.tree.isHidden())
        self.assertTrue(empty.warnings_box.isHidden())
        empty.close()

    def test_13_preview_does_not_write_or_dirty_catalog(self) -> None:
        stamps = _catalog_stamps(self.db)
        suip = self.catalog.get_authority_by_code(SUIP_AUTHORITY_CODE)
        assert suip is not None
        editor = ControlAuthorityDialog(self.tab, authority=suip)
        editor.show()
        self.assertFalse(editor._editor.is_dirty())
        dialog = ControlAuthorityWebPreviewDialog(
            self.tab,
            _result(
                (
                    _diff(
                        status=WEB_DIFF_STATUS_CHANGED,
                        action=WEB_DIFF_ACTION_UPDATE,
                        local=_local(),
                        remote=_remote(),
                        field_changes=(
                            ControlAuthorityOfficeFieldChange("name", "A", "B"),
                        ),
                    ),
                )
            ),
        )
        dialog.show()
        self.assertFalse(editor._editor.is_dirty())
        self.assertEqual(_catalog_stamps(self.db), stamps)
        preview_source = inspect.getsource(ControlAuthorityWebPreviewDialog)
        tab_source = inspect.getsource(ControlAuthorityCatalogTab)
        self.assertNotIn("apply_authority_web_changes", preview_source)
        self.assertNotIn("apply_authority_web_changes", tab_source)
        self.assertNotIn("Použít", preview_source)
        dialog.close()
        editor.close()

    def test_14_network_timeout_structure_unknown_errors(self) -> None:
        self._select_code(DU_AUTHORITY_CODE)
        cases = (
            (WEB_ADAPTER_ERROR_NETWORK, WEB_CHECK_UI_ERROR_NETWORK),
            (WEB_ADAPTER_ERROR_TIMEOUT, WEB_CHECK_UI_ERROR_NETWORK),
            (WEB_DIFF_ERROR_INCOMPLETE, WEB_CHECK_UI_ERROR_STRUCTURE),
            (WEB_ADAPTER_ERROR_UNREADABLE_HTML, WEB_CHECK_UI_ERROR_STRUCTURE),
            (WEB_CHECK_ERROR_UNSUPPORTED, WEB_CHECK_UI_ERROR_UNSUPPORTED),
        )
        for code, message in cases:
            self.warn_mock.reset_mock()

            def fake(_authority_code: str, *, _code=code):
                raise ControlAuthorityWebCheckError("technický detail", code=_code)

            self._run_check(fake, expect_dialog=False)
            self.warn_mock.assert_called()
            args = self.warn_mock.call_args.args
            self.assertEqual(args[2], message)

        self.warn_mock.reset_mock()

        def boom(_code: str):
            raise RuntimeError("traceback-secret")

        self._run_check(boom, expect_dialog=False)
        self.assertEqual(self.warn_mock.call_args.args[2], WEB_CHECK_UI_ERROR_OTHER)

    def test_15_after_error_can_start_again(self) -> None:
        self._select_code(DU_AUTHORITY_CODE)
        calls: list[str] = []

        def fake(code: str):
            calls.append(code)
            if len(calls) == 1:
                raise ControlAuthorityWebCheckError("x", code=WEB_ADAPTER_ERROR_NETWORK)
            return _result(
                (
                    _diff(
                        status=WEB_DIFF_STATUS_CHANGED,
                        action=WEB_DIFF_ACTION_UPDATE,
                        local=_local(),
                        remote=_remote(),
                        field_changes=(
                            ControlAuthorityOfficeFieldChange("name", "A", "B"),
                        ),
                    ),
                )
            )

        self._run_check(fake, expect_dialog=False)
        self.assertTrue(self.tab.web_check_button.isEnabled())
        dialog = self._run_check(fake, expect_dialog=True)
        self.assertEqual(len(calls), 2)
        self.assertIsInstance(dialog, ControlAuthorityWebPreviewDialog)

    def test_16_callback_after_page_destroyed_does_not_open_dialog(self) -> None:
        self._select_code(DU_AUTHORITY_CODE)
        entered = threading.Event()
        release = threading.Event()
        done = threading.Event()

        def fake(_code: str):
            entered.set()
            release.wait(timeout=5)
            try:
                return _result()
            finally:
                done.set()

        with patch(_CHECK, side_effect=fake), patch(
            "moduly.statni_dozor.ui.control_authority_catalog_tab.ControlAuthorityWebPreviewDialog"
        ) as dialog_cls:
            tab = self.tab
            page = self.page
            tab.start_web_check()
            self.assertTrue(entered.wait(timeout=2))
            page.close()
            shiboken_delete(tab)
            self.assertFalse(isValid(tab))
            page.deleteLater()
            self.tab = None
            self.page = None
            self._app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            self._app.processEvents()
            release.set()
            self.assertTrue(done.wait(timeout=2))
            for _ in range(30):
                self._app.processEvents()
            dialog_cls.assert_not_called()
        self.page = NastaveniPage()
        self.tab = self.page.state_supervision_catalog_tab

    def test_17_no_http_on_settings_construct(self) -> None:
        with patch(_CHECK) as check, patch("requests.Session.request") as request:
            page = NastaveniPage()
            check.assert_not_called()
            request.assert_not_called()
            page.close()

    def test_18_no_db_write_on_success_or_error(self) -> None:
        stamps = _catalog_stamps(self.db)
        self._select_code(DU_AUTHORITY_CODE)
        self._run_check(lambda _code: _result(), expect_dialog=True)
        self.assertEqual(_catalog_stamps(self.db), stamps)

        def fail(_code: str):
            raise ControlAuthorityWebCheckError("x", code=WEB_ADAPTER_ERROR_NETWORK)

        self._run_check(fail, expect_dialog=False)
        self.assertEqual(_catalog_stamps(self.db), stamps)
        source = inspect.getsource(ControlAuthorityCatalogTab)
        self.assertNotIn("urllib.request", source)
        self.assertNotIn("urlopen", source)


if __name__ == "__main__":
    unittest.main()
