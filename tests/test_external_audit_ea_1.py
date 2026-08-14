"""EXTERNAL-AUDIT-EA-1: přehled, editor, ARES, pracovní kopie, přílohy."""

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
from PySide6.QtWidgets import QApplication, QMessageBox, QSpinBox
from sqlalchemy.orm import Session

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="external-audit-ea-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.audity.ui.audity_page import AudityPage
    from moduly.externi_audity.constants import (
        ENTITY_EXTERNAL_AUDIT,
        EXTERNAL_AUDITS_BUTTON_LABEL,
        EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
        EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
        EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON,
        EXTERNAL_AUDIT_SOURCE_PERSON,
        EXTERNAL_AUDIT_SOURCE_THP_WORKER,
        EXTERNAL_AUDIT_STATUS_PLANNED,
        EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
        EXTERNAL_AUDIT_YEAR_FILTER_ALL,
        EXTERNAL_AUDIT_YEAR_SPIN_ALL_VALUE,
    )
    from moduly.externi_audity.modely import ExternalAuditVisit
    from moduly.externi_audity.sluzby.external_audit_draft import (
        ExternalAuditDraft,
        ParticipantDraft,
        VisitDraft,
        new_client_key,
    )
    from moduly.externi_audity.sluzby.external_audit_service import (
        ExternalAuditError,
        external_audit_service,
    )
    from moduly.externi_audity.ui.external_audit_editor_dialog import (
        ExternalAuditEditorDialog,
        TAB_ATTACHMENTS,
        TAB_PARTICIPANTS,
        TAB_PROGRAM,
        TAB_SPIS,
    )
    from moduly.externi_audity.ui.external_audits_overview_dialog import (
        ExternalAuditsOverviewDialog,
    )
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _table_ids(dialog: ExternalAuditsOverviewDialog) -> set[int]:
    ids: set[int] = set()
    for row in range(dialog.table.rowCount()):
        item = dialog.table.item(row, 3)
        if item is not None:
            ids.add(int(item.data(Qt.ItemDataRole.UserRole)))
    return ids


class ExternalAuditEa1TestCase(unittest.TestCase):
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
            name=f"EA1-WP-{suffix}",
            address=f"Adresa {suffix}",
            active=True,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.non_auditable = settings_service.save_workplace(
            name=f"EA1-OFF-{suffix}",
            active=True,
            audit_enabled=False,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.person = person_service.create_person(
            first_name="Eva",
            last_name=f"Auditor-{suffix}",
        )
        self.invited = person_service.create_person(
            first_name="Petr",
            last_name=f"Host-{suffix}",
        )
        self.thp = settings_service.save_worker(
            first_name="Jana",
            last_name=f"THP-{suffix}",
        )

    def _draft(self, **overrides) -> ExternalAuditDraft:
        auditor_key = new_client_key()
        draft = ExternalAuditDraft(
            audit_id=None,
            audit_type=EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
            status=EXTERNAL_AUDIT_STATUS_PLANNED,
            organization_ico="00000000",
            organization_name="CertOrg a.s.",
            organization_address="Praha",
            organization_extra={"source": "test"},
            participants=[
                ParticipantDraft(
                    client_key=auditor_key,
                    role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
                    source_type=EXTERNAL_AUDIT_SOURCE_PERSON,
                    source_id=int(self.person.id),
                    display_name_snapshot=self.person.display_name,
                    display_order=10,
                ),
                ParticipantDraft(
                    client_key=new_client_key(),
                    role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
                    source_type=EXTERNAL_AUDIT_SOURCE_THP_WORKER,
                    source_id=int(self.thp.id),
                    display_name_snapshot=self.thp.display_name,
                    display_order=10,
                ),
                ParticipantDraft(
                    client_key=new_client_key(),
                    role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON,
                    source_type=EXTERNAL_AUDIT_SOURCE_PERSON,
                    source_id=int(self.invited.id),
                    display_name_snapshot=self.invited.display_name,
                    display_order=10,
                ),
            ],
            visits=[
                VisitDraft(
                    client_key=new_client_key(),
                    visit_date=date(2026, 9, 10),
                    workplace_id=int(self.workplace.id),
                    workplace_name_snapshot=self.workplace.name,
                    workplace_address_snapshot=self.workplace.address or "",
                    time_from="09:00",
                    time_to="12:00",
                    display_order=10,
                    participant_keys=[auditor_key],
                ),
                VisitDraft(
                    client_key=new_client_key(),
                    visit_date=date(2026, 9, 12),
                    workplace_id=int(self.workplace.id),
                    workplace_name_snapshot=self.workplace.name,
                    workplace_address_snapshot=self.workplace.address or "",
                    display_order=20,
                    participant_keys=[],
                ),
            ],
        )
        for key, value in overrides.items():
            setattr(draft, key, value)
        return draft

    def test_01_audity_page_button(self) -> None:
        page = AudityPage()
        self.assertEqual(page.external_audits_btn.text(), EXTERNAL_AUDITS_BUTTON_LABEL)
        self.assertTrue(callable(page.open_external_audits))

    def test_02_overview_year_spin_and_filters(self) -> None:
        saved = external_audit_service.save_bundle(self._draft())
        undated = external_audit_service.save_bundle(
            ExternalAuditDraft(
                audit_id=None,
                audit_type=EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
                status=EXTERNAL_AUDIT_STATUS_PLANNED,
                organization_ico="12345678",
                organization_name="Bez programu",
                organization_address="",
            )
        )
        dialog = ExternalAuditsOverviewDialog()
        self.assertIsInstance(dialog.year_filter, QSpinBox)
        self.assertEqual(
            dialog.year_filter.specialValueText(), EXTERNAL_AUDIT_YEAR_FILTER_ALL
        )
        self.assertIn(
            str(EXTERNAL_AUDIT_YEAR_SPIN_ALL_VALUE), dialog.year_all_hint.text()
        )

        dialog.year_filter.setValue(EXTERNAL_AUDIT_YEAR_SPIN_ALL_VALUE)
        dialog.refresh()
        all_ids = _table_ids(dialog)
        self.assertIn(int(saved.id), all_ids)
        self.assertIn(int(undated.id), all_ids)

        dialog.year_filter.setValue(2026)
        dialog.refresh()
        year_ids = _table_ids(dialog)
        self.assertIn(int(saved.id), year_ids)
        self.assertNotIn(int(undated.id), year_ids)

        dialog.table.clearSelection()
        dialog._refresh_actions()
        self.assertFalse(dialog.edit_btn.isEnabled())
        dialog.table.selectRow(0)
        dialog._refresh_actions()
        self.assertTrue(dialog.edit_btn.isEnabled())

    def test_03_editor_tabs_and_ares_only_on_click(self) -> None:
        editor = ExternalAuditEditorDialog()
        self.assertEqual(editor.tabs.tabText(TAB_SPIS), "Spis")
        self.assertEqual(editor.tabs.tabText(TAB_PROGRAM), "Program")
        self.assertEqual(editor.tabs.tabText(TAB_PARTICIPANTS), "Účastníci")
        self.assertEqual(editor.tabs.tabText(TAB_ATTACHMENTS), "Přílohy")
        from moduly.externi_audity.constants import EXTERNAL_AUDIT_ATTACHMENTS_NEED_SAVE

        self.assertFalse(editor.attachments.btn_add.isEnabled())
        self.assertEqual(
            editor.attachments.hint.text(),
            EXTERNAL_AUDIT_ATTACHMENTS_NEED_SAVE,
        )

        editor.ico.setText("00000000")
        editor.organization_name.setText("Původní")
        editor.organization_address.setText("Stará adresa")
        with (
            patch(
                "moduly.externi_audity.ui.external_audit_editor_dialog.ares_service.find_by_ico"
            ) as mocked,
            patch(
                "moduly.externi_audity.ui.external_audit_editor_dialog.QMessageBox.critical"
            ),
            patch(
                "moduly.externi_audity.ui.external_audit_editor_dialog.QMessageBox.warning"
            ),
        ):
            mocked.side_effect = RuntimeError("síť")
            editor._load_from_ares()
            mocked.assert_called_once()
        self.assertEqual(editor.organization_name.text(), "Původní")
        self.assertEqual(editor.organization_address.text(), "Stará adresa")

        with (
            patch(
                "moduly.externi_audity.ui.external_audit_editor_dialog.ares_service.find_by_ico",
                return_value={
                    "ico": "00000000",
                    "name": "ARES Firma",
                    "address": "Nová 1",
                },
            ) as mocked,
            patch(
                "moduly.externi_audity.ui.external_audit_editor_dialog.QMessageBox.critical"
            ),
            patch(
                "moduly.externi_audity.ui.external_audit_editor_dialog.QMessageBox.warning"
            ),
        ):
            editor._load_from_ares()
            mocked.assert_called_once()
        self.assertEqual(editor.organization_name.text(), "ARES Firma")
        self.assertEqual(editor.organization_address.text(), "Nová 1")

    def test_04_save_bundle_visits_participants_snapshot(self) -> None:
        draft = self._draft()
        saved = external_audit_service.save_bundle(draft)
        detail = external_audit_service.get_detail(saved.id)
        self.assertEqual(detail.date_from, date(2026, 9, 10))
        self.assertEqual(detail.date_to, date(2026, 9, 12))
        self.assertEqual(len(detail.visits), 2)
        self.assertEqual(len(detail.participants), 3)
        self.assertEqual(detail.audit.organization_name, "CertOrg a.s.")
        self.assertIn("00000000", detail.audit.organization_snapshot_json or "")

        names = {item.display_name_snapshot for item in detail.participants}
        self.assertIn(self.person.display_name, names)
        self.assertIn(self.thp.display_name, names)

        reloaded = external_audit_service.load_draft(saved.id)
        external_audit_service.save_bundle(reloaded)
        detail2 = external_audit_service.get_detail(saved.id)
        self.assertEqual(len(detail2.visits), 2)
        self.assertEqual(len(detail2.participants), 3)

        with self.assertRaises(ExternalAuditError):
            bad = self._draft()
            bad.visits[0].workplace_id = int(self.non_auditable.id)
            bad.visits[0].workplace_name_snapshot = ""
            external_audit_service.save_bundle(bad)

        with self.assertRaises(ExternalAuditError):
            bad = self._draft()
            bad.visits[0].time_from = "15:00"
            bad.visits[0].time_to = "10:00"
            external_audit_service.save_bundle(bad)

    def test_05_deferred_discard_and_attachments(self) -> None:
        marker = f"discard-{uuid.uuid4().hex[:8]}"
        editor = ExternalAuditEditorDialog()
        editor.ico.setText("11111111")
        editor.organization_name.setText(marker)
        self.assertTrue(editor._is_dirty())
        editor._draft.attachments.pending_add_paths.append("/tmp/fake.pdf")
        editor._closing = True
        editor.reject()
        self.assertFalse(
            any(
                row.organization_name == marker
                for row in external_audit_service.list_overview_rows()
            )
        )

        editor2 = ExternalAuditEditorDialog()
        editor2.ico.setText("22222222")
        editor2.organization_name.setText("Uloženo")
        self.assertTrue(editor2._persist())
        self.assertIsNotNone(editor2._draft.audit_id)
        self.assertFalse(editor2.attachments.hint.isVisible())
        self.assertTrue(editor2.attachments.btn_add.isEnabled())

        tmp = Path(tempfile.mkdtemp()) / "doklad.pdf"
        tmp.write_bytes(b"%PDF-1.4 test")
        editor2.attachments.staging.pending_add_paths.append(str(tmp))
        self.assertEqual(
            len(external_audit_service.list_attachments(editor2._draft.audit_id)), 0
        )
        self.assertTrue(editor2._persist())
        attachments = external_audit_service.list_attachments(editor2._draft.audit_id)
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].entity_type, ENTITY_EXTERNAL_AUDIT)

        editor3 = ExternalAuditEditorDialog(audit_id=editor2._draft.audit_id)
        before = len(external_audit_service.list_attachments(editor3._draft.audit_id))
        orphan = Path(tempfile.mkdtemp()) / "orphan.pdf"
        orphan.write_bytes(b"%PDF orphan")
        editor3.attachments.staging.pending_add_paths.append(str(orphan))
        editor3._draft.attachments.clear()
        self.assertEqual(
            len(external_audit_service.list_attachments(editor3._draft.audit_id)),
            before,
        )

    def test_06_save_keep_open_and_save_close(self) -> None:
        editor = ExternalAuditEditorDialog()
        editor.ico.setText("33333333")
        editor.organization_name.setText("Keep open")
        editor._save_keep_open()
        self.assertIsNotNone(editor._draft.audit_id)

        editor2 = ExternalAuditEditorDialog()
        editor2.ico.setText("44444444")
        editor2.organization_name.setText("Close me")
        with patch.object(editor2, "accept") as accept:
            editor2._save_and_close()
            accept.assert_called_once()

    def test_07_atomic_rollback(self) -> None:
        marker = f"rollback-{uuid.uuid4().hex[:8]}"
        draft = self._draft(organization_name=marker)
        real_add = Session.add
        visits_seen = {"n": 0}

        def counting_add(self, instance):
            real_add(self, instance)
            if isinstance(instance, ExternalAuditVisit):
                visits_seen["n"] += 1
                if visits_seen["n"] == 1:
                    raise RuntimeError("boom")

        with patch.object(Session, "add", counting_add):
            with self.assertRaises(RuntimeError):
                external_audit_service.save_bundle(draft)

        self.assertFalse(
            any(
                row.organization_name == marker
                for row in external_audit_service.list_overview_rows()
            )
        )

    def test_08_overview_batch_no_n_plus_one_shape(self) -> None:
        external_audit_service.save_bundle(self._draft())
        external_audit_service.save_bundle(
            self._draft(organization_ico="99999999", organization_name="Druhý")
        )
        rows = external_audit_service.list_overview_rows()
        self.assertGreaterEqual(len(rows), 2)
        for row in rows:
            self.assertTrue(hasattr(row, "workplaces_label"))
            self.assertTrue(hasattr(row, "date_from"))

    def test_09_remove_used_participant_from_draft(self) -> None:
        editor = ExternalAuditEditorDialog()
        draft = self._draft()
        editor._draft = draft
        editor._load_draft_into_widgets()
        auditor = draft.participants_for_role(
            EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR
        )[0]
        editor.auditor_list.setCurrentRow(0)
        with patch(
            "moduly.externi_audity.ui.external_audit_editor_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            editor._remove_participant(
                EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
                editor.auditor_list,
            )
        self.assertIsNone(editor._draft.participant_by_key(auditor.client_key))
        self.assertTrue(
            all(
                auditor.client_key not in visit.participant_keys
                for visit in editor._draft.visits
            )
        )


if __name__ == "__main__":
    unittest.main()
