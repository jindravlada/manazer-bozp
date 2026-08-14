"""EXTERNAL-AUDIT-EA-1-UX1: český čas (800→8:00) a datum dd.MM.yyyy."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date, time
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="external-audit-ea-1-ux1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.nullable_time_edit import NullableTimeEdit, parse_czech_time
    from core.widgets.typed_table_sort import TYPED_SORT_ROLE
    from moduly.externi_audity.constants import format_display_date
    from moduly.externi_audity.sluzby.external_audit_draft import (
        ExternalAuditDraft,
        VisitDraft,
        new_client_key,
    )
    from moduly.externi_audity.sluzby.external_audit_service import (
        ExternalAuditError,
        _normalize_time,
        _validate_time_range,
        external_audit_service,
    )
    from moduly.externi_audity.ui.external_audit_editor_dialog import (
        ExternalAuditEditorDialog,
    )
    from moduly.externi_audity.ui.external_audit_visit_dialog import (
        ExternalAuditVisitDialog,
    )
    from moduly.externi_audity.ui.external_audits_overview_dialog import (
        COL_FROM,
        COL_REMIND,
        COL_TO,
        ExternalAuditsOverviewDialog,
    )
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class ExternalAuditEa1Ux1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls._home = patch.object(Path, "home", return_value=_TMP)
        cls._home.start()
        importlib.reload(storage_module)
        storage_module.storage_service.ensure_structure()
        importlib.reload(session_module)
        session_module.reconfigure_database_engine(force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._home.stop()

    def setUp(self) -> None:
        suffix = uuid.uuid4().hex[:6]
        self.workplace = settings_service.save_workplace(
            name=f"UX1-WP-{suffix}",
            address="Ulice 1",
            active=True,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )

    def test_01_parse_and_normalize_time_inputs(self) -> None:
        cases = {
            "800": time(8, 0),
            "0800": time(8, 0),
            "8:00": time(8, 0),
            "1430": time(14, 30),
            "14:30": time(14, 30),
            "": None,
            "   ": None,
        }
        for raw, expected in cases.items():
            self.assertEqual(parse_czech_time(raw), expected, raw)

        self.assertIsNone(parse_czech_time("99:99"))
        self.assertIsNone(parse_czech_time("abcd"))

        edit = NullableTimeEdit()
        for raw, expected in (
            ("800", "08:00"),
            ("0800", "08:00"),
            ("8:00", "08:00"),
            ("1430", "14:30"),
        ):
            edit.line_edit.setText(raw)
            edit._normalize_input()
            self.assertEqual(edit.get_time(), parse_czech_time(raw))
            self.assertEqual(edit.line_edit.text(), expected)

        edit.line_edit.clear()
        edit._normalize_input()
        self.assertIsNone(edit.get_time())
        self.assertEqual(edit.line_edit.text(), "")

        self.assertEqual(_normalize_time("800"), "08:00")
        self.assertEqual(_normalize_time("1430"), "14:30")
        with self.assertRaises(ExternalAuditError):
            _normalize_time("xx")

    def test_02_time_range_validation(self) -> None:
        self.assertEqual(_validate_time_range("800", "1430"), ("08:00", "14:30"))
        with self.assertRaises(ExternalAuditError):
            _validate_time_range("15:00", "10:00")
        self.assertEqual(_validate_time_range("", None), (None, None))

    def test_03_visit_dialog_finishes_pending_time_edit(self) -> None:
        dialog = ExternalAuditVisitDialog(participants=[])
        dialog.visit_date.set_date_value(date(2026, 9, 10))
        dialog.workplace.setCurrentIndex(
            max(dialog.workplace.findData(int(self.workplace.id)), 0)
        )
        dialog.time_from.line_edit.setText("800")
        dialog.time_to.line_edit.setText("1430")
        # Bez ztráty fokusu — _accept musí dokončit editaci.
        with patch.object(dialog, "accept"):
            dialog._accept()
        self.assertIsNotNone(dialog.result_visit)
        self.assertEqual(dialog.result_visit.time_from, "08:00")
        self.assertEqual(dialog.result_visit.time_to, "14:30")

        dialog2 = ExternalAuditVisitDialog(participants=[])
        dialog2.visit_date.set_date_value(date(2026, 9, 10))
        dialog2.workplace.setCurrentIndex(
            max(dialog2.workplace.findData(int(self.workplace.id)), 0)
        )
        dialog2.time_from.line_edit.setText("9999")
        with (
            patch.object(dialog2, "accept") as accept,
            patch(
                "moduly.externi_audity.ui.external_audit_visit_dialog.QMessageBox.warning"
            ),
        ):
            dialog2._accept()
            accept.assert_not_called()
        self.assertIsNone(dialog2.result_visit)

    def test_04_czech_date_display_overview_and_editor(self) -> None:
        draft = ExternalAuditDraft(
            audit_id=None,
            audit_type="surveillance",
            status="planned",
            organization_ico="12345678",
            organization_name="UX1 Org",
            organization_address="",
            remind_from=date(2026, 8, 1),
            visits=[
                VisitDraft(
                    client_key=new_client_key(),
                    visit_date=date(2026, 9, 10),
                    workplace_id=int(self.workplace.id),
                    workplace_name_snapshot=self.workplace.name,
                    workplace_address_snapshot="",
                    display_order=10,
                ),
                VisitDraft(
                    client_key=new_client_key(),
                    visit_date=date(2026, 9, 12),
                    workplace_id=int(self.workplace.id),
                    workplace_name_snapshot=self.workplace.name,
                    workplace_address_snapshot="",
                    display_order=20,
                ),
            ],
        )
        saved = external_audit_service.save_bundle(draft)

        overview = ExternalAuditsOverviewDialog()
        overview.year_filter.setValue(2026)
        overview.refresh()
        row_index = None
        for row in range(overview.table.rowCount()):
            item = overview.table.item(row, 3)
            if item and int(item.data(Qt.ItemDataRole.UserRole)) == int(saved.id):
                row_index = row
                break
        self.assertIsNotNone(row_index)
        self.assertEqual(
            overview.table.item(row_index, COL_FROM).text(), "10.09.2026"
        )
        self.assertEqual(overview.table.item(row_index, COL_TO).text(), "12.09.2026")
        self.assertEqual(
            overview.table.item(row_index, COL_REMIND).text(), "01.08.2026"
        )
        sort_from = overview.table.item(row_index, COL_FROM).data(TYPED_SORT_ROLE)
        self.assertEqual(sort_from.payload, date(2026, 9, 10))

        undated = external_audit_service.save_bundle(
            ExternalAuditDraft(
                audit_id=None,
                audit_type="surveillance",
                status="planned",
                organization_ico="87654321",
                organization_name="Bez termínu",
                organization_address="",
            )
        )
        overview.year_filter.setValue(1899)
        overview.refresh()
        empty_row = None
        for row in range(overview.table.rowCount()):
            item = overview.table.item(row, 3)
            if item and int(item.data(Qt.ItemDataRole.UserRole)) == int(undated.id):
                empty_row = row
                break
        self.assertIsNotNone(empty_row)
        self.assertEqual(overview.table.item(empty_row, COL_FROM).text(), "—")
        self.assertEqual(overview.table.item(empty_row, COL_REMIND).text(), "")

        editor = ExternalAuditEditorDialog(audit_id=int(saved.id))
        self.assertEqual(editor.date_from.text(), "10.09.2026")
        self.assertEqual(editor.date_to.text(), "12.09.2026")
        visit_dates = {
            editor.visits_table.item(row, 0).text()
            for row in range(editor.visits_table.rowCount())
        }
        self.assertEqual(visit_dates, {"10.09.2026", "12.09.2026"})
        self.assertEqual(format_display_date(None), "—")
        self.assertEqual(format_display_date(date(2026, 1, 5)), "05.01.2026")

    def test_05_dirty_discard_keeps_original(self) -> None:
        draft = ExternalAuditDraft(
            audit_id=None,
            audit_type="surveillance",
            status="planned",
            organization_ico="55555555",
            organization_name="Dirty Org",
            organization_address="",
            remind_from=date(2026, 7, 1),
        )
        saved = external_audit_service.save_bundle(draft)
        editor = ExternalAuditEditorDialog(audit_id=int(saved.id))
        self.assertFalse(editor._is_dirty())
        editor.remind_from.set_date_value(date(2026, 7, 15))
        self.assertTrue(editor._is_dirty())
        editor._draft.attachments.clear()
        editor._closing = True
        editor.reject()
        reloaded = external_audit_service.get_by_id(int(saved.id))
        self.assertEqual(reloaded.remind_from, date(2026, 7, 1))

    def test_06_sorting_uses_real_dates_not_lexicographic_text(self) -> None:
        # 10.09 vs 02.10 — lexikograficky by 02.10 bylo dříve, datumově později.
        for day, ico in ((date(2026, 9, 10), "10101010"), (date(2026, 10, 2), "20202020")):
            external_audit_service.save_bundle(
                ExternalAuditDraft(
                    audit_id=None,
                    audit_type="surveillance",
                    status="planned",
                    organization_ico=ico,
                    organization_name=f"Sort {ico}",
                    organization_address="",
                    visits=[
                        VisitDraft(
                            client_key=new_client_key(),
                            visit_date=day,
                            workplace_id=int(self.workplace.id),
                            workplace_name_snapshot=self.workplace.name,
                            workplace_address_snapshot="",
                            display_order=10,
                        )
                    ],
                )
            )
        overview = ExternalAuditsOverviewDialog()
        overview.year_filter.setValue(2026)
        overview.refresh()
        overview.table.sortItems(COL_FROM, Qt.SortOrder.AscendingOrder)
        texts = [
            overview.table.item(row, COL_FROM).text()
            for row in range(overview.table.rowCount())
            if overview.table.item(row, COL_FROM).text() not in {"", "—"}
        ]
        # Mezi našimi dvěma musí být 10.09 dříve než 02.10 při vzestupném řazení.
        self.assertLess(texts.index("10.09.2026"), texts.index("02.10.2026"))


if __name__ == "__main__":
    unittest.main()
