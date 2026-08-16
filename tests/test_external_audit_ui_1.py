"""EXTERNAL-AUDIT-UI-1: šířky tabulek a řádek času návštěvy."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHeaderView

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="external-audit-ui-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.externi_audity.constants import (
        EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
        EXTERNAL_AUDIT_FINDING_STATUS_RECORDED,
        EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
        EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
        EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
        EXTERNAL_AUDIT_STATUS_PLANNED,
        EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
    )
    from moduly.externi_audity.sluzby.external_audit_draft import (
        ExternalAuditDraft,
        FindingDraft,
        VisitDraft,
        new_client_key,
    )
    from moduly.externi_audity.sluzby.external_audit_service import (
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
        COL_ICO,
        COL_ORG,
        COL_STATUS,
        COL_WP,
        ExternalAuditsOverviewDialog,
    )
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class ExternalAuditUi1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        suffix = uuid.uuid4().hex[:6]
        self.workplace = settings_service.save_workplace(
            name=f"UI1-WP-{suffix}",
            address="Ulice 1",
            active=True,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )

    def test_01_overview_stretch_and_compact_modes(self) -> None:
        long_name = "Velmi dlouhý název certifikační organizace " + ("X" * 40)
        draft = ExternalAuditDraft(
            audit_id=None,
            audit_type=EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
            status=EXTERNAL_AUDIT_STATUS_PLANNED,
            organization_ico="12345678",
            organization_name=long_name,
            organization_address="Praha",
            visits=[
                VisitDraft(
                    client_key=new_client_key(),
                    visit_date=date(2026, 9, 10),
                    workplace_id=int(self.workplace.id),
                    workplace_name_snapshot=self.workplace.name,
                    workplace_address_snapshot="",
                )
            ],
        )
        external_audit_service.save_bundle(draft)

        dialog = ExternalAuditsOverviewDialog()
        dialog.resize(1280, 620)
        dialog.refresh()
        header = dialog.table.horizontalHeader()
        self.assertEqual(
            header.sectionResizeMode(COL_ORG),
            QHeaderView.ResizeMode.Stretch,
        )
        self.assertEqual(
            header.sectionResizeMode(COL_WP),
            QHeaderView.ResizeMode.Stretch,
        )
        for col in (COL_FROM, COL_ICO, COL_STATUS):
            self.assertEqual(
                header.sectionResizeMode(col),
                QHeaderView.ResizeMode.ResizeToContents,
                col,
            )
        # Tabulka má využít šířku viewportu (ne zůstat úzký blok vlevo).
        used = sum(dialog.table.columnWidth(i) for i in range(dialog.table.columnCount()))
        self.assertGreaterEqual(used, dialog.table.viewport().width() - 24)
        # Tooltip plného textu organizace
        org_item = dialog.table.item(0, COL_ORG)
        self.assertIsNotNone(org_item)
        self.assertIn("Velmi dlouhý", org_item.toolTip() or org_item.text())

        # Resize okna nesmí rozbít režimy
        dialog.resize(900, 500)
        QApplication.processEvents()
        self.assertEqual(
            header.sectionResizeMode(COL_ORG),
            QHeaderView.ResizeMode.Stretch,
        )
        dialog.close()

    def test_02_program_table_resize_modes(self) -> None:
        draft = ExternalAuditDraft(
            audit_id=None,
            audit_type=EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
            status=EXTERNAL_AUDIT_STATUS_PLANNED,
            organization_ico="87654321",
            organization_name="Program Org",
            organization_address="",
            visits=[
                VisitDraft(
                    client_key=new_client_key(),
                    visit_date=date(2026, 10, 1),
                    workplace_id=int(self.workplace.id),
                    workplace_name_snapshot=self.workplace.name,
                    workplace_address_snapshot="",
                    time_from="08:00",
                    time_to="12:00",
                    note="Poznámka s delším textem pro tooltip",
                )
            ],
        )
        saved = external_audit_service.save_bundle(draft)
        editor = ExternalAuditEditorDialog(audit_id=int(saved.id))
        editor.resize(1100, 720)
        header = editor.visits_table.horizontalHeader()
        for col in (0, 1, 2):
            self.assertEqual(
                header.sectionResizeMode(col),
                QHeaderView.ResizeMode.ResizeToContents,
                col,
            )
        for col in (3, 4, 5, 6, 7):
            self.assertEqual(
                header.sectionResizeMode(col),
                QHeaderView.ResizeMode.Stretch,
                col,
            )
        note_item = editor.visits_table.item(0, 7)
        self.assertIsNotNone(note_item)
        self.assertIn("Poznámka", note_item.toolTip() or note_item.text())
        used = sum(
            editor.visits_table.columnWidth(i)
            for i in range(editor.visits_table.columnCount())
        )
        self.assertGreaterEqual(used, editor.visits_table.viewport().width() - 24)
        editor.close()

    def test_03_findings_text_columns_stretch(self) -> None:
        draft = ExternalAuditDraft(
            audit_id=None,
            audit_type=EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
            status=EXTERNAL_AUDIT_STATUS_PLANNED,
            organization_ico="11223344",
            organization_name="Findings Org",
            organization_address="",
            findings=[
                FindingDraft(
                    client_key=new_client_key(),
                    finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                    description="Dlouhý text neshody " + ("abc " * 30),
                    status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
                ),
                FindingDraft(
                    client_key=new_client_key(),
                    finding_type=EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
                    description="Dlouhý text PKZ " + ("xyz " * 30),
                    status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
                ),
                FindingDraft(
                    client_key=new_client_key(),
                    finding_type=EXTERNAL_AUDIT_FINDING_TYPE_STRENGTH,
                    description="Silná stránka " + ("ok " * 40),
                    status=EXTERNAL_AUDIT_FINDING_STATUS_RECORDED,
                ),
            ],
        )
        saved = external_audit_service.save_bundle(draft)
        editor = ExternalAuditEditorDialog(audit_id=int(saved.id))
        editor.findings.refresh()

        nc_header = editor.findings.nc_panel.table.horizontalHeader()
        self.assertEqual(
            nc_header.sectionResizeMode(0),
            QHeaderView.ResizeMode.Stretch,
        )
        for col in (1, 2, 3, 4):
            self.assertEqual(
                nc_header.sectionResizeMode(col),
                QHeaderView.ResizeMode.ResizeToContents,
                col,
            )

        pkz_header = editor.findings.pkz_panel.table.horizontalHeader()
        self.assertEqual(
            pkz_header.sectionResizeMode(0),
            QHeaderView.ResizeMode.Stretch,
        )

        strength_header = editor.findings.strength_panel.table.horizontalHeader()
        self.assertEqual(
            strength_header.sectionResizeMode(0),
            QHeaderView.ResizeMode.Stretch,
        )
        self.assertEqual(editor.findings.strength_panel.table.columnCount(), 1)

        nc_item = editor.findings.nc_panel.table.item(0, 0)
        self.assertIsNotNone(nc_item)
        self.assertIn("Dlouhý text neshody", nc_item.toolTip() or nc_item.text())
        editor.close()

    def test_04_visit_time_row_height_and_normalization(self) -> None:
        dialog = ExternalAuditVisitDialog(participants=[])
        dialog.visit_date.set_date_value(date(2026, 9, 10))
        dialog.workplace.setCurrentIndex(
            max(dialog.workplace.findData(int(self.workplace.id)), 0)
        )
        hint_from = dialog.time_from.sizeHint().height()
        hint_to = dialog.time_to.sizeHint().height()
        self.assertGreaterEqual(dialog.time_from.height() or hint_from, hint_from)
        self.assertGreaterEqual(hint_from, 34)
        self.assertGreaterEqual(hint_to, 34)
        # Wrapper kolem času má rezervu pod rámečkem
        time_wrap = dialog.time_from.parentWidget()
        self.assertIsNotNone(time_wrap)
        self.assertGreaterEqual(time_wrap.minimumHeight(), hint_from + 8)

        dialog.time_from.line_edit.setText("800")
        dialog.time_to.line_edit.setText("1430")
        with patch.object(dialog, "accept"):
            dialog._accept()
        self.assertEqual(dialog.result_visit.time_from, "08:00")
        self.assertEqual(dialog.result_visit.time_to, "14:30")
        dialog.close()


if __name__ == "__main__":
    unittest.main()
