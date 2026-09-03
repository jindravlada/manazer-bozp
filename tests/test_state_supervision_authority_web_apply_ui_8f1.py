"""STATE-SUPERVISION-AUTHORITY-WEB-APPLY-UI-8F1: výběr a potvrzení změn."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HOME = Path(tempfile.mkdtemp(prefix="state-supervision-web-apply-ui-8f1-"))
_HOME_PATCHER = patch.object(Path, "home", return_value=_HOME)
_HOME_PATCHER.start()

import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()

import core.database.session as session_module

importlib.reload(session_module)
from core.database.database_initializer import initialize_database

initialize_database()

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from moduly.nastaveni.ui.nastaveni_page import NastaveniPage
from moduly.statni_dozor.constants import (
    DU_AUTHORITY_CODE,
    DU_OFFICES_SOURCE_URL,
    EMPTY_VALUE,
    OFFICE_KIND_HEADQUARTERS,
    WEB_APPLY_ACTION_CREATE,
    WEB_APPLY_ACTION_DEACTIVATE,
    WEB_APPLY_ACTION_REACTIVATE,
    WEB_APPLY_ACTION_UPDATE,
    WEB_APPLY_ERROR_FIELDS,
    WEB_APPLY_ERROR_STALE,
    WEB_APPLY_UI_ACTION_CREATE,
    WEB_APPLY_UI_ACTION_DEACTIVATE,
    WEB_APPLY_UI_ACTION_REACTIVATE,
    WEB_APPLY_UI_BUTTON_LABEL,
    WEB_APPLY_UI_CONFIRM_APPLY,
    WEB_APPLY_UI_CONFIRM_BODY,
    WEB_APPLY_UI_CONFIRM_CANCEL,
    WEB_APPLY_UI_CONFIRM_TITLE,
    WEB_APPLY_UI_CONFLICT_HINT,
    WEB_APPLY_UI_DUPLICATE_HINT,
    WEB_APPLY_UI_ERASE_TOOLTIP,
    WEB_APPLY_UI_MISSING_HINT,
    WEB_APPLY_UI_NONE_SELECTED,
    WEB_APPLY_UI_PROTECTED_BATCH_WARNING,
    WEB_APPLY_UI_PROTECTED_NOTICE,
    WEB_APPLY_UI_REFRESH_FAILED,
    WEB_APPLY_UI_STALE,
    WEB_APPLY_UI_UNKNOWN_HINT,
    WEB_DIFF_ACTION_CREATE,
    WEB_DIFF_ACTION_DEACTIVATE,
    WEB_DIFF_ACTION_NONE,
    WEB_DIFF_ACTION_REACTIVATE,
    WEB_DIFF_ACTION_REVIEW,
    WEB_DIFF_ACTION_UPDATE,
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
)
from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
    control_authority_catalog_service,
)
from moduly.statni_dozor.sluzby.control_authority_web.apply import (
    ControlAuthorityWebApplyError,
    ControlAuthorityWebApplyResult,
)
from moduly.statni_dozor.sluzby.control_authority_web.check import (
    ControlAuthorityWebAdapterInfo,
    ControlAuthorityWebCheckResult,
)
from moduly.statni_dozor.sluzby.control_authority_web.coverage import du_web_coverage
from moduly.statni_dozor.sluzby.control_authority_web.diff_models import (
    ControlAuthorityOfficeCatalogSnapshot,
    ControlAuthorityOfficeDiff,
    ControlAuthorityOfficeFieldChange,
)
from moduly.statni_dozor.sluzby.control_authority_web.labels import (
    WebApplySelectionSummary,
    web_apply_confirm_lines,
    web_apply_selection_count_text,
    web_apply_success_message,
)
from moduly.statni_dozor.sluzby.control_authority_web.models import (
    ControlAuthorityOfficeWebRecord,
)
from moduly.statni_dozor.ui.control_authority_catalog_tab import (
    ControlAuthorityCatalogTab,
)
from moduly.statni_dozor.ui.control_authority_web_preview_dialog import (
    ControlAuthorityWebApplyConfirmDialog,
    ControlAuthorityWebPreviewDialog,
)
from tests.test_state_supervision_authority_web_apply_core_8e1 import (
    _ApplyCoreMixin,
)

_HOME_PATCHER.stop()

_APPLY = "moduly.statni_dozor.ui.control_authority_web_preview_dialog.apply_authority_web_changes"
_CHECK = "moduly.statni_dozor.ui.control_authority_catalog_tab.check_authority_web"
_FIXED_AT = datetime(2026, 9, 3, 10, 12, 0)
_SOURCE_URL = DU_OFFICES_SOURCE_URL
_ADAPTER = ControlAuthorityWebAdapterInfo(
    authority_code=DU_AUTHORITY_CODE,
    display_name="Drážní úřad",
    source_name="Kontakty Drážního úřadu",
    source_url=_SOURCE_URL,
    coverage=du_web_coverage(),
)


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
) -> ControlAuthorityWebCheckResult:
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


def _apply_result(**overrides) -> ControlAuthorityWebApplyResult:
    values = {
        "authority_code": DU_AUTHORITY_CODE,
        "applied_at": _FIXED_AT,
        "created_ids": (),
        "updated_ids": (),
        "deactivated_ids": (),
        "reactivated_ids": (),
        "applied_count": 0,
    }
    values.update(overrides)
    return ControlAuthorityWebApplyResult(**values)


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


def _is_checkable(item) -> bool:
    return bool(item.flags() & Qt.ItemFlag.ItemIsUserCheckable)


def _changed_diff(*fields: str, **local_overrides):
    remote_overrides = {}
    changes = []
    for field in fields:
        if field == "name":
            changes.append(ControlAuthorityOfficeFieldChange("name", "A", "B"))
            remote_overrides["name"] = "B"
        elif field == "address":
            changes.append(ControlAuthorityOfficeFieldChange("address", "Old", "New"))
            remote_overrides["address"] = "New"
        elif field == "phone":
            changes.append(ControlAuthorityOfficeFieldChange("phone", "111", "222"))
            remote_overrides["phone"] = "222"
        elif field == "email":
            changes.append(ControlAuthorityOfficeFieldChange("email", "a@x.cz", "b@x.cz"))
            remote_overrides["email"] = "b@x.cz"
        else:
            changes.append(ControlAuthorityOfficeFieldChange(field, "old", "new"))
    local = _local(**local_overrides)
    return _diff(
        status=WEB_DIFF_STATUS_CHANGED,
        action=WEB_DIFF_ACTION_UPDATE,
        local=local,
        remote=_remote(external_key=local.external_key, **remote_overrides),
        field_changes=tuple(changes),
    )


class StateSupervisionAuthorityWebApplyUiLabels8f1TestCase(unittest.TestCase):
    def test_01_selection_count_and_success_text(self) -> None:
        self.assertEqual(web_apply_selection_count_text(0), WEB_APPLY_UI_NONE_SELECTED)
        self.assertEqual(web_apply_selection_count_text(3), "Vybráno změn: 3")
        result = _apply_result(
            updated_ids=(1, 2, 3),
            created_ids=(4,),
        )
        self.assertEqual(
            web_apply_success_message(result),
            "Změny byly použity. Aktualizováno: 3, založeno: 1, "
            "deaktivováno: 0, aktivováno: 0.",
        )

    def test_02_confirm_lines_include_deactivations_and_erasures(self) -> None:
        summary = WebApplySelectionSummary(
            update_fields=5,
            creates=1,
            deactivates=1,
            reactivates=0,
            protected_records=1,
            erasures=1,
        )
        text = "\n".join(web_apply_confirm_lines(summary))
        self.assertIn("Aktualizovaná pole: 5", text)
        self.assertIn("Nová pracoviště: 1", text)
        self.assertIn("Deaktivovaná pracoviště: 1", text)
        self.assertIn("Znovu aktivovaná pracoviště: 0", text)
        self.assertIn("Ručně upravené záznamy: 1", text)
        self.assertIn("Vymazané hodnoty: 1", text)


class StateSupervisionAuthorityWebApplyUi8f1TestCase(unittest.TestCase):
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
        self.page = NastaveniPage()
        self.tab: ControlAuthorityCatalogTab = self.page.state_supervision_catalog_tab
        self._warn = patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok)
        self.warn_mock = self._warn.start()
        self._info = patch.object(QMessageBox, "information", return_value=QMessageBox.Ok)
        self.info_mock = self._info.start()

    def tearDown(self) -> None:
        self._info.stop()
        self._warn.stop()
        self.page.close()

    def _select_code(self, code: str) -> None:
        authority = self.catalog.get_authority_by_code(code)
        assert authority is not None
        self.tab._restore_selection("authority", int(authority.id))
        self.tab.update_buttons()

    def _dialog(self, *diffs) -> ControlAuthorityWebPreviewDialog:
        return ControlAuthorityWebPreviewDialog(self.tab, _result(tuple(diffs)))

    def test_01_nothing_checked_and_apply_disabled(self) -> None:
        dialog = self._dialog(
            _changed_diff("name", "address", "phone"),
            _diff(
                status=WEB_DIFF_STATUS_NEW,
                action=WEB_DIFF_ACTION_CREATE,
                remote=_remote(external_key="du:brno", name="Brno"),
            ),
            _diff(
                status=WEB_DIFF_STATUS_MISSING_REMOTE,
                action=WEB_DIFF_ACTION_DEACTIVATE,
                local=_local(id=12, external_key="du:olomouc", name="Olomouc"),
            ),
            _diff(
                status=WEB_DIFF_STATUS_INACTIVE_PRESENT,
                action=WEB_DIFF_ACTION_REACTIVATE,
                local=_local(id=13, external_key="du:plzen", name="Plzeň", active=False),
                remote=_remote(external_key="du:plzen", name="Plzeň"),
            ),
            _diff(
                status=WEB_DIFF_STATUS_PROTECTED,
                action=WEB_DIFF_ACTION_REVIEW,
                review=True,
                local=_local(id=14, external_key="du:ostrava", name="Ostrava"),
                remote=_remote(external_key="du:ostrava"),
                field_changes=(ControlAuthorityOfficeFieldChange("name", "A", "B"),),
            ),
        )
        for index in range(dialog.tree.topLevelItemCount()):
            parent = dialog.tree.topLevelItem(index)
            if _is_checkable(parent):
                self.assertEqual(parent.checkState(0), Qt.CheckState.Unchecked)
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                if _is_checkable(child):
                    self.assertEqual(child.checkState(0), Qt.CheckState.Unchecked)
        self.assertFalse(dialog.apply_button.isEnabled())
        self.assertEqual(dialog.apply_button.text(), WEB_APPLY_UI_BUTTON_LABEL)
        self.assertEqual(dialog.selection_count_label.text(), WEB_APPLY_UI_NONE_SELECTED)
        self.assertTrue(dialog.close_button.isDefault())
        self.assertFalse(dialog.apply_button.isDefault())
        self.assertFalse(dialog.apply_button.autoDefault())
        self.assertEqual(dialog.current_selections(), ())
        dialog.close()

    def test_02_one_changed_field_enables_apply(self) -> None:
        dialog = self._dialog(_changed_diff("name", "address"))
        parent = dialog.tree.topLevelItem(0)
        name = _child_by_field(parent, "name")
        assert name is not None
        name.setCheckState(0, Qt.CheckState.Checked)
        self.assertTrue(dialog.apply_button.isEnabled())
        self.assertEqual(dialog.selection_count_label.text(), "Vybráno změn: 1")
        name.setCheckState(0, Qt.CheckState.Unchecked)
        self.assertFalse(dialog.apply_button.isEnabled())
        self.assertEqual(dialog.selection_count_label.text(), WEB_APPLY_UI_NONE_SELECTED)
        dialog.close()

    def test_03_selected_fields_are_exact_and_unchecked_are_omitted(self) -> None:
        dialog = self._dialog(_changed_diff("name", "address", "phone", "email"))
        parent = dialog.tree.topLevelItem(0)
        _child_by_field(parent, "address").setCheckState(0, Qt.CheckState.Checked)
        _child_by_field(parent, "phone").setCheckState(0, Qt.CheckState.Checked)
        _child_by_field(parent, "email").setCheckState(0, Qt.CheckState.Checked)
        selections = dialog.current_selections()
        self.assertEqual(len(selections), 1)
        self.assertEqual(selections[0].action, WEB_APPLY_ACTION_UPDATE)
        self.assertEqual(selections[0].external_key, "du:praha")
        self.assertEqual(selections[0].local_id, 11)
        self.assertEqual(
            selections[0].selected_fields, frozenset({"address", "phone", "email"})
        )
        self.assertNotIn("name", selections[0].selected_fields)
        self.assertFalse(selections[0].confirm_protected)
        dialog.close()

    def test_04_tristate_parent_selects_and_clears_field_changes(self) -> None:
        dialog = self._dialog(_changed_diff("name", "address", "phone"))
        parent = dialog.tree.topLevelItem(0)
        self.assertTrue(_is_checkable(parent))
        self.assertTrue(parent.flags() & Qt.ItemFlag.ItemIsUserTristate)
        self.assertFalse(parent.flags() & Qt.ItemFlag.ItemIsAutoTristate)
        child = _child_by_field(parent, "address")
        child.setCheckState(0, Qt.CheckState.Checked)
        self.assertEqual(parent.checkState(0), Qt.CheckState.PartiallyChecked)
        parent.setCheckState(0, Qt.CheckState.Checked)
        self.assertEqual(
            dialog.current_selections()[0].selected_fields,
            frozenset({"name", "address", "phone"}),
        )
        parent.setCheckState(0, Qt.CheckState.Unchecked)
        self.assertEqual(dialog.current_selections(), ())
        for index in range(parent.childCount()):
            self.assertEqual(parent.child(index).checkState(0), Qt.CheckState.Unchecked)
        dialog.close()

    def test_05_explicit_none_is_erasure(self) -> None:
        dialog = self._dialog(
            _diff(
                status=WEB_DIFF_STATUS_CHANGED,
                action=WEB_DIFF_ACTION_UPDATE,
                local=_local(),
                remote=_remote(phone=None),
                field_changes=(
                    ControlAuthorityOfficeFieldChange("phone", "111 222", None),
                ),
            )
        )
        child = dialog.tree.topLevelItem(0).child(0)
        self.assertTrue(_is_checkable(child))
        self.assertEqual(child.text(2), EMPTY_VALUE)
        self.assertEqual(child.toolTip(2), WEB_APPLY_UI_ERASE_TOOLTIP)
        child.setCheckState(0, Qt.CheckState.Checked)
        summary = dialog.selection_summary()
        self.assertEqual(summary.erasures, 1)
        self.assertEqual(summary.update_fields, 1)
        dialog.close()

    def test_06_inapplicable_rows_have_no_checkbox_and_do_not_block(self) -> None:
        dialog = self._dialog(
            _diff(
                status=WEB_DIFF_STATUS_UNCHANGED,
                action=WEB_DIFF_ACTION_NONE,
                local=_local(id=1, external_key="du:u"),
                remote=_remote(external_key="du:u"),
            ),
            _diff(
                status=WEB_DIFF_STATUS_POSSIBLE_DUPLICATE,
                action=WEB_DIFF_ACTION_REVIEW,
                review=True,
                local=_local(id=2, external_key="du:d"),
                remote=_remote(external_key="du:d"),
            ),
            _diff(
                status=WEB_DIFF_STATUS_IDENTITY_CONFLICT,
                action=WEB_DIFF_ACTION_REVIEW,
                review=True,
                local=_local(id=3, external_key="du:c"),
                remote=_remote(external_key="du:c"),
            ),
            _diff(
                status="mystery",
                action=WEB_DIFF_ACTION_REVIEW,
                review=True,
                local=_local(id=4, external_key="du:x"),
                remote=_remote(external_key="du:x"),
            ),
            _changed_diff("name"),
        )
        unchanged = _parent_by_status(dialog, WEB_DIFF_STATUS_UNCHANGED)
        duplicate = _parent_by_status(dialog, WEB_DIFF_STATUS_POSSIBLE_DUPLICATE)
        conflict = _parent_by_status(dialog, WEB_DIFF_STATUS_IDENTITY_CONFLICT)
        unknown = _parent_by_status(dialog, "mystery")
        changed = _parent_by_status(dialog, WEB_DIFF_STATUS_CHANGED)
        assert unchanged is not None
        assert duplicate is not None
        assert conflict is not None
        assert unknown is not None
        assert changed is not None
        self.assertFalse(_is_checkable(unchanged))
        self.assertFalse(_is_checkable(duplicate))
        self.assertFalse(_is_checkable(conflict))
        self.assertFalse(_is_checkable(unknown))
        self.assertEqual(duplicate.text(3), WEB_APPLY_UI_DUPLICATE_HINT)
        self.assertEqual(conflict.text(3), WEB_APPLY_UI_CONFLICT_HINT)
        self.assertEqual(unknown.text(3), WEB_APPLY_UI_UNKNOWN_HINT)
        _child_by_field(changed, "name").setCheckState(0, Qt.CheckState.Checked)
        self.assertTrue(dialog.apply_button.isEnabled())
        selections = dialog.current_selections()
        self.assertEqual(len(selections), 1)
        self.assertEqual(selections[0].action, WEB_APPLY_ACTION_UPDATE)
        dialog.close()

    def test_07_new_missing_inactive_create_parent_selections(self) -> None:
        dialog = self._dialog(
            _diff(
                status=WEB_DIFF_STATUS_NEW,
                action=WEB_DIFF_ACTION_CREATE,
                remote=_remote(external_key="du:brno", name="Brno"),
                field_changes=(
                    ControlAuthorityOfficeFieldChange("name", None, "Brno"),
                ),
            ),
            _diff(
                status=WEB_DIFF_STATUS_MISSING_REMOTE,
                action=WEB_DIFF_ACTION_DEACTIVATE,
                local=_local(id=22, external_key="du:olomouc", name="Olomouc"),
            ),
            _diff(
                status=WEB_DIFF_STATUS_INACTIVE_PRESENT,
                action=WEB_DIFF_ACTION_REACTIVATE,
                local=_local(id=23, external_key="du:plzen", name="Plzeň", active=False),
                remote=_remote(external_key="du:plzen", name="Plzeň"),
            ),
        )
        created = _parent_by_status(dialog, WEB_DIFF_STATUS_NEW)
        missing = _parent_by_status(dialog, WEB_DIFF_STATUS_MISSING_REMOTE)
        inactive = _parent_by_status(dialog, WEB_DIFF_STATUS_INACTIVE_PRESENT)
        assert created is not None
        assert missing is not None
        assert inactive is not None
        self.assertTrue(_is_checkable(created))
        self.assertTrue(_is_checkable(missing))
        self.assertTrue(_is_checkable(inactive))
        self.assertFalse(_is_checkable(created.child(0)))
        self.assertEqual(created.text(3), WEB_APPLY_UI_ACTION_CREATE)
        self.assertEqual(missing.text(3), WEB_APPLY_UI_ACTION_DEACTIVATE)
        self.assertEqual(missing.toolTip(3), WEB_APPLY_UI_MISSING_HINT)
        self.assertEqual(inactive.text(3), WEB_APPLY_UI_ACTION_REACTIVATE)
        created.setCheckState(0, Qt.CheckState.Checked)
        missing.setCheckState(0, Qt.CheckState.Checked)
        inactive.setCheckState(0, Qt.CheckState.Checked)
        by_action = {item.action: item for item in dialog.current_selections()}
        self.assertEqual(by_action[WEB_APPLY_ACTION_CREATE].external_key, "du:brno")
        self.assertIsNone(by_action[WEB_APPLY_ACTION_CREATE].local_id)
        self.assertEqual(by_action[WEB_APPLY_ACTION_CREATE].selected_fields, frozenset())
        self.assertEqual(by_action[WEB_APPLY_ACTION_DEACTIVATE].local_id, 22)
        self.assertEqual(by_action[WEB_APPLY_ACTION_REACTIVATE].local_id, 23)
        self.assertEqual(dialog.selection_summary().total, 3)
        dialog.close()

    def test_08_protected_default_unchecked_cancel_confirm_does_not_apply(self) -> None:
        dialog = self._dialog(
            _diff(
                status=WEB_DIFF_STATUS_PROTECTED,
                action=WEB_DIFF_ACTION_REVIEW,
                review=True,
                local=_local(),
                remote=_remote(name="Web"),
                field_changes=(ControlAuthorityOfficeFieldChange("name", "A", "Web"),),
            )
        )
        parent = dialog.tree.topLevelItem(0)
        child = parent.child(0)
        self.assertEqual(parent.text(3), WEB_APPLY_UI_PROTECTED_NOTICE)
        self.assertEqual(child.checkState(0), Qt.CheckState.Unchecked)
        dialog.show()
        child.setCheckState(0, Qt.CheckState.Checked)
        with patch.object(dialog, "_confirm_apply", return_value=False) as confirm, patch(
            _APPLY
        ) as apply:
            dialog.apply_button.click()
        confirm.assert_called_once()
        apply.assert_not_called()
        self.assertTrue(dialog.isVisible())
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(child.checkState(0), Qt.CheckState.Checked)
        self.assertIsNone(dialog.apply_result)
        dialog.close()

    def test_09_protected_and_protected_missing_send_confirm_flag(self) -> None:
        dialog = self._dialog(
            _diff(
                status=WEB_DIFF_STATUS_PROTECTED,
                action=WEB_DIFF_ACTION_REVIEW,
                review=True,
                local=_local(id=11, external_key="du:praha"),
                remote=_remote(name="Web"),
                field_changes=(ControlAuthorityOfficeFieldChange("name", "A", "Web"),),
            ),
            _diff(
                status=WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE,
                action=WEB_DIFF_ACTION_REVIEW,
                review=True,
                local=_local(id=12, external_key="du:olomouc", name="Olomouc"),
            ),
        )
        _child_by_field(dialog.tree.topLevelItem(0), "name").setCheckState(
            0, Qt.CheckState.Checked
        )
        missing = _parent_by_status(dialog, WEB_DIFF_STATUS_PROTECTED_MISSING_REMOTE)
        assert missing is not None
        self.assertTrue(_is_checkable(missing))
        self.assertEqual(missing.checkState(0), Qt.CheckState.Unchecked)
        missing.setCheckState(0, Qt.CheckState.Checked)
        fake = _apply_result(updated_ids=(11,), deactivated_ids=(12,))
        with patch.object(dialog, "_confirm_apply", return_value=True), patch(
            _APPLY, return_value=fake
        ) as apply:
            dialog.apply_button.click()
        apply.assert_called_once()
        check_result, selections = apply.call_args.args
        self.assertIs(check_result, dialog._result)
        by_action = {item.action: item for item in selections}
        self.assertTrue(by_action[WEB_APPLY_ACTION_UPDATE].confirm_protected)
        self.assertTrue(by_action[WEB_APPLY_ACTION_DEACTIVATE].confirm_protected)
        self.assertEqual(dialog.apply_result, fake)
        self.assertTrue(dialog._consumed)
        dialog.close()

    def test_10_confirm_dialog_counts_default_cancel_and_escape(self) -> None:
        summary = WebApplySelectionSummary(
            update_fields=5,
            creates=1,
            deactivates=1,
            reactivates=0,
            protected_records=1,
            erasures=1,
        )
        dialog = ControlAuthorityWebApplyConfirmDialog(self.tab, summary)
        self.assertEqual(dialog.windowTitle(), WEB_APPLY_UI_CONFIRM_TITLE)
        intro = dialog.layout().itemAt(0).widget()
        self.assertEqual(intro.text(), WEB_APPLY_UI_CONFIRM_BODY)
        self.assertIn("Deaktivovaná pracoviště: 1", dialog.summary_label.text())
        self.assertIn("Vymazané hodnoty: 1", dialog.summary_label.text())
        self.assertFalse(dialog.protected_label.isHidden())
        self.assertEqual(dialog.protected_label.text(), WEB_APPLY_UI_PROTECTED_BATCH_WARNING)
        self.assertEqual(dialog.apply_button.text(), WEB_APPLY_UI_CONFIRM_APPLY)
        self.assertEqual(dialog.cancel_button.text(), WEB_APPLY_UI_CONFIRM_CANCEL)
        self.assertTrue(dialog.cancel_button.isDefault())
        self.assertFalse(dialog.apply_button.isDefault())
        self.assertFalse(dialog.apply_button.autoDefault())
        QTimer.singleShot(0, lambda: QTest.keyClick(dialog, Qt.Key.Key_Escape))
        self.assertEqual(dialog.exec(), QDialog.DialogCode.Rejected)

        plain = ControlAuthorityWebApplyConfirmDialog(
            self.tab, WebApplySelectionSummary(deactivates=2, erasures=1)
        )
        self.assertTrue(plain.protected_label.isHidden())
        QTimer.singleShot(0, lambda: QTest.keyClick(plain, Qt.Key.Key_Return))
        self.assertEqual(plain.exec(), QDialog.DialogCode.Rejected)

    def test_11_fake_apply_receives_original_dto_once_and_closes(self) -> None:
        check = _result((_changed_diff("name", "address"),))
        dialog = ControlAuthorityWebPreviewDialog(self.tab, check)
        _child_by_field(dialog.tree.topLevelItem(0), "name").setCheckState(
            0, Qt.CheckState.Checked
        )
        fake = _apply_result(updated_ids=(11,))
        with patch.object(dialog, "_confirm_apply", return_value=True), patch(
            _APPLY, return_value=fake
        ) as apply:
            dialog.apply_button.click()
            dialog.apply_button.click()
        apply.assert_called_once()
        sent_check, selections = apply.call_args.args
        self.assertIs(sent_check, check)
        self.assertEqual(selections[0].selected_fields, frozenset({"name"}))
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.apply_result, fake)
        self.assertTrue(dialog._consumed)
        self.assertFalse(dialog.apply_button.isEnabled())
        dialog.close()

    def test_12_success_refreshes_tree_once_and_restores_authority(self) -> None:
        self._select_code(DU_AUTHORITY_CODE)
        authority = self.catalog.get_authority_by_code(DU_AUTHORITY_CODE)
        assert authority is not None
        dialog = self._dialog(_changed_diff("name"))
        dialog.apply_result = _apply_result(updated_ids=(11,))
        calls: list[tuple | None] = []
        original = self.tab.refresh

        def wrapped(select=None):
            calls.append(select)
            return original(select=select)

        with patch("requests.Session.request") as request, patch(
            _CHECK
        ) as check:
            with patch.object(self.tab, "refresh", side_effect=wrapped):
                self.tab._handle_web_apply_outcome(dialog)
        self.assertEqual(calls, [("authority", int(authority.id))])
        kind, record_id = self.tab._selected()
        self.assertEqual(kind, "authority")
        self.assertEqual(record_id, int(authority.id))
        request.assert_not_called()
        check.assert_not_called()
        self.info_mock.assert_called()
        self.assertEqual(
            self.info_mock.call_args[0][2],
            web_apply_success_message(dialog.apply_result),
        )
        dialog.close()

    def test_13_stale_preview_disables_apply_and_does_not_write(self) -> None:
        stamps = _catalog_stamps(self.db)
        dialog = self._dialog(_changed_diff("name"))
        dialog.show()
        _child_by_field(dialog.tree.topLevelItem(0), "name").setCheckState(
            0, Qt.CheckState.Checked
        )
        with patch.object(dialog, "_confirm_apply", return_value=True), patch(
            _APPLY,
            side_effect=ControlAuthorityWebApplyError("stale", code=WEB_APPLY_ERROR_STALE),
        ) as apply, patch(_CHECK) as check:
            dialog.apply_button.click()
        apply.assert_called_once()
        self.assertTrue(dialog.stale_label.isVisible())
        self.assertEqual(dialog.stale_label.text(), WEB_APPLY_UI_STALE)
        self.assertTrue(dialog.apply_button.isHidden())
        self.assertFalse(dialog.apply_button.isEnabled())
        self.assertIsNone(dialog.apply_result)
        self.assertFalse(dialog._consumed)
        self.assertEqual(_catalog_stamps(self.db), stamps)
        check.assert_not_called()
        dialog.close()

    def test_14_apply_error_keeps_dialog_and_selection(self) -> None:
        dialog = self._dialog(_changed_diff("name", "address"))
        dialog.show()
        _child_by_field(dialog.tree.topLevelItem(0), "name").setCheckState(
            0, Qt.CheckState.Checked
        )
        with patch.object(dialog, "_confirm_apply", return_value=True), patch(
            _APPLY,
            side_effect=ControlAuthorityWebApplyError(
                "Pole nelze použít.", code=WEB_APPLY_ERROR_FIELDS
            ),
        ) as apply, patch(_CHECK) as check:
            dialog.apply_button.click()
        apply.assert_called_once()
        check.assert_not_called()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
        self.assertTrue(dialog.apply_button.isEnabled())
        self.assertEqual(
            dialog.current_selections()[0].selected_fields, frozenset({"name"})
        )
        self.assertIsNone(dialog.apply_result)
        dialog.close()

    def test_15_refresh_failure_after_commit_is_not_save_error(self) -> None:
        self._select_code(DU_AUTHORITY_CODE)
        dialog = self._dialog(_changed_diff("name"))
        dialog.apply_result = _apply_result(updated_ids=(11,))
        with patch.object(self.tab, "refresh", side_effect=RuntimeError("boom")):
            self.tab._handle_web_apply_outcome(dialog)
        self.warn_mock.assert_called()
        message = self.warn_mock.call_args[0][2]
        self.assertEqual(message, WEB_APPLY_UI_REFRESH_FAILED)
        self.assertNotIn("Uložení se nezdařilo", message)
        self.info_mock.assert_not_called()
        dialog.close()

    def test_16_close_without_apply_and_empty_selection_do_not_call_service(self) -> None:
        stamps = _catalog_stamps(self.db)
        dialog = self._dialog(_changed_diff("name"))
        with patch(_APPLY) as apply:
            dialog._on_apply_clicked()
            QTimer.singleShot(0, dialog.reject)
            dialog.exec()
        apply.assert_not_called()
        self.assertEqual(_catalog_stamps(self.db), stamps)
        dialog.close()

    def test_17_enter_does_not_apply_escape_closes_without_write(self) -> None:
        stamps = _catalog_stamps(self.db)
        dialog = self._dialog(_changed_diff("name"))
        _child_by_field(dialog.tree.topLevelItem(0), "name").setCheckState(
            0, Qt.CheckState.Checked
        )
        with patch(_APPLY) as apply:
            QTimer.singleShot(0, lambda: QTest.keyClick(dialog, Qt.Key.Key_Return))
            self.assertEqual(dialog.exec(), QDialog.DialogCode.Rejected)
            apply.assert_not_called()
        dialog = self._dialog(_changed_diff("name"))
        _child_by_field(dialog.tree.topLevelItem(0), "name").setCheckState(
            0, Qt.CheckState.Checked
        )
        with patch(_APPLY) as apply:
            QTimer.singleShot(0, lambda: QTest.keyClick(dialog, Qt.Key.Key_Escape))
            self.assertEqual(dialog.exec(), QDialog.DialogCode.Rejected)
            apply.assert_not_called()
        self.assertEqual(_catalog_stamps(self.db), stamps)


class StateSupervisionAuthorityWebApplyUiIntegration8f1TestCase(
    _ApplyCoreMixin, unittest.TestCase
):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        super().setUpClass()

    def setUp(self) -> None:
        super().setUp()
        self._warn = patch.object(QMessageBox, "warning", return_value=QMessageBox.Ok)
        self._warn.start()

    def tearDown(self) -> None:
        self._warn.stop()

    def _parent_for_key(self, dialog, key: str):
        for index, diff in enumerate(dialog._result.diffs):
            if diff.external_key == key:
                return dialog.tree.topLevelItem(index)
        return None

    def test_01_selective_update_one_field_uses_real_core(self) -> None:
        offices = self._offices()
        original_address = offices["du:praha"].address
        remotes = self._matching_remotes(
            **{
                "du:praha": {
                    "name": "Drážní úřad Praha – web",
                    "address": "Jiná adresa 1, Praha",
                }
            }
        )
        check = self._check(remotes)
        dialog = ControlAuthorityWebPreviewDialog(None, check)
        parent = self._parent_for_key(dialog, "du:praha")
        assert parent is not None
        _child_by_field(parent, "name").setCheckState(0, Qt.CheckState.Checked)
        with patch.object(dialog, "_confirm_apply", return_value=True):
            dialog.apply_button.click()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertIsNotNone(dialog.apply_result)
        updated = self._office("du:praha")
        self.assertEqual(updated.name, "Drážní úřad Praha – web")
        self.assertEqual(updated.address, original_address)
        self.assertEqual(dialog.apply_result.updated_ids, (updated.id,))
        dialog.close()

    def test_02_stale_second_row_rolls_back_and_keeps_selection(self) -> None:
        remotes = self._matching_remotes(
            **{
                "du:praha": {"name": "Webový název Praha"},
                "du:plzen": {"name": "Webový název Plzeň"},
            }
        )
        check = self._check(remotes)
        self._sql(
            "UPDATE control_authority_offices SET name=? WHERE external_key=?",
            ("Mezitím změněný název", "du:praha"),
        )
        dialog = ControlAuthorityWebPreviewDialog(None, check)
        dialog.show()
        praha = self._parent_for_key(dialog, "du:praha")
        plzen = self._parent_for_key(dialog, "du:plzen")
        assert praha is not None
        assert plzen is not None
        _child_by_field(praha, "name").setCheckState(0, Qt.CheckState.Checked)
        _child_by_field(plzen, "name").setCheckState(0, Qt.CheckState.Checked)
        with patch.object(dialog, "_confirm_apply", return_value=True), patch(
            _CHECK
        ) as web_check:
            dialog.apply_button.click()
        web_check.assert_not_called()
        self.assertTrue(dialog.stale_label.isVisible())
        self.assertTrue(dialog.apply_button.isHidden())
        self.assertIsNone(dialog.apply_result)
        self.assertEqual(self._office("du:praha").name, "Mezitím změněný název")
        self.assertNotEqual(self._office("du:plzen").name, "Webový název Plzeň")
        self.assertEqual(
            dialog.current_selections()[0].selected_fields, frozenset({"name"})
        )
        self.assertEqual(len(dialog.current_selections()), 2)
        dialog.close()


if __name__ == "__main__":
    unittest.main()
