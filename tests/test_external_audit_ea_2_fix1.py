"""EXTERNAL-AUDIT-EA-2-FIX1: auditor persist + TaskDialog bez duplicitních kwargs."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="external-audit-ea-2-fix1-"))

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
        EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
        EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
        EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
        EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
        EXTERNAL_AUDIT_SOURCE_LEGACY_INVALID,
        EXTERNAL_AUDIT_SOURCE_PERSON,
        EXTERNAL_AUDIT_SOURCE_THP_WORKER,
        EXTERNAL_AUDIT_STATUS_PLANNED,
        EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
    )
    from moduly.externi_audity.sluzby.external_audit_draft import (
        ExternalAuditDraft,
        FindingDraft,
        ParticipantDraft,
        new_client_key,
    )
    from moduly.externi_audity.sluzby.external_audit_service import (
        ExternalAuditError,
        external_audit_service,
    )
    from moduly.externi_audity.ui.external_audit_editor_dialog import (
        ExternalAuditEditorDialog,
    )
    from moduly.externi_audity.ui.external_audit_findings_widget import (
        _task_description,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.ui.task_dialog import TaskDialog


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class ExternalAuditEa2Fix1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()
        suffix = uuid.uuid4().hex[:6]
        cls.person = person_service.create_person(
            first_name="Ext",
            last_name=f"Auditor-{suffix}",
            active=True,
        )
        cls.person2 = person_service.create_person(
            first_name="Dalsi",
            last_name=f"Auditor-{suffix}",
            active=True,
        )
        cls.thp = settings_service.save_worker(
            first_name="THP",
            last_name=f"Worker-{suffix}",
        )

    def _draft(self, **kwargs) -> ExternalAuditDraft:
        data = {
            "audit_id": None,
            "audit_type": EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
            "status": EXTERNAL_AUDIT_STATUS_PLANNED,
            "organization_ico": f"77{uuid.uuid4().hex[:6]}",
            "organization_name": "FIX1 Org",
            "organization_address": "",
        }
        data.update(kwargs)
        return ExternalAuditDraft(**data)

    def test_01_valid_person_auditor_survives_save_reload_reopen(self) -> None:
        editor = ExternalAuditEditorDialog()
        editor.ico.setText("99887766")
        editor.organization_name.setText("Auditor Persist Org")
        editor.auditor_selector.set_person_id(int(self.person.id))
        editor._add_participant(
            EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
            "person",
            editor.auditor_selector,
            editor.auditor_list,
        )
        auditors = editor._draft.participants_for_role(
            EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR
        )
        self.assertEqual(len(auditors), 1)
        self.assertEqual(auditors[0].source_type, EXTERNAL_AUDIT_SOURCE_PERSON)
        self.assertEqual(int(auditors[0].source_id), int(self.person.id))

        self.assertTrue(editor._persist())
        audit_id = int(editor._draft.audit_id)
        after_save = editor._draft.participants_for_role(
            EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR
        )
        self.assertEqual(len(after_save), 1)
        self.assertIsNotNone(after_save[0].db_id)

        loaded = external_audit_service.load_draft(audit_id)
        self.assertEqual(len(loaded.participants_for_role(
            EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR
        )), 1)

        editor2 = ExternalAuditEditorDialog(audit_id=audit_id)
        self.assertEqual(editor2.auditor_list.count(), 1)
        self.assertIn(self.person.display_name, editor2.auditor_list.item(0).text())

        # Opakované Uložit bez změny → žádná duplicita
        self.assertTrue(editor2._persist())
        detail = external_audit_service.get_detail(audit_id)
        auditors_db = [
            p
            for p in detail.participants
            if p.role == EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR
        ]
        self.assertEqual(len(auditors_db), 1)

    def test_02_discard_does_not_write_new_auditor(self) -> None:
        saved = external_audit_service.save_bundle(
            self._draft(organization_name="Discard Org")
        )
        editor = ExternalAuditEditorDialog(audit_id=int(saved.id))
        editor.auditor_selector.set_person_id(int(self.person.id))
        editor._add_participant(
            EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
            "person",
            editor.auditor_selector,
            editor.auditor_list,
        )
        self.assertTrue(editor._is_dirty())
        with patch(
            "moduly.externi_audity.ui.external_audit_editor_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            editor._request_close()
        detail = external_audit_service.get_detail(int(saved.id))
        self.assertEqual(
            [
                p
                for p in detail.participants
                if p.role == EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR
            ],
            [],
        )

    def test_03_thp_cannot_be_external_auditor(self) -> None:
        draft = self._draft()
        draft.participants = [
            ParticipantDraft(
                client_key=new_client_key(),
                role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
                source_type=EXTERNAL_AUDIT_SOURCE_THP_WORKER,
                source_id=int(self.thp.id),
                display_name_snapshot=self.thp.display_name,
            )
        ]
        with self.assertRaises(ExternalAuditError):
            external_audit_service.save_bundle(draft)

    def test_04_legacy_invalid_blocks_save_but_keeps_new_auditor_in_draft(self) -> None:
        draft = self._draft()
        draft.participants = [
            ParticipantDraft(
                client_key=new_client_key(),
                role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
                source_type=EXTERNAL_AUDIT_SOURCE_LEGACY_INVALID,
                source_id=0,
                display_name_snapshot="Starý THP auditor",
                db_id=None,
            ),
            ParticipantDraft(
                client_key=new_client_key(),
                role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
                source_type=EXTERNAL_AUDIT_SOURCE_PERSON,
                source_id=int(self.person.id),
                display_name_snapshot=self.person.display_name,
            ),
        ]
        with self.assertRaises(ExternalAuditError):
            external_audit_service.save_bundle(draft)
        # Draft si nové i legacy řádky ponechá — žádné tiché zahození.
        self.assertEqual(len(draft.participants), 2)

        # Po odebrání legacy se nový auditor uloží.
        draft.participants = [
            p
            for p in draft.participants
            if p.source_type != EXTERNAL_AUDIT_SOURCE_LEGACY_INVALID
        ]
        saved = external_audit_service.save_bundle(draft)
        detail = external_audit_service.get_detail(int(saved.id))
        auditors = [
            p
            for p in detail.participants
            if p.role == EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR
        ]
        self.assertEqual(len(auditors), 1)
        self.assertEqual(auditors[0].source_type, EXTERNAL_AUDIT_SOURCE_PERSON)
        self.assertEqual(int(auditors[0].source_id), int(self.person.id))

    def test_05_legacy_invalid_loaded_stays_visible_until_user_fixes(self) -> None:
        # Přímý zápis legacy přes dočasné obcházení validace není žádoucí;
        # simulujeme load_draft stavem po SEPARATION.
        saved = external_audit_service.save_bundle(
            self._draft(
                organization_name="Legacy Visible",
                participants=[
                    ParticipantDraft(
                        client_key=new_client_key(),
                        role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
                        source_type=EXTERNAL_AUDIT_SOURCE_THP_WORKER,
                        source_id=int(self.thp.id),
                        display_name_snapshot=self.thp.display_name,
                    )
                ],
            )
        )
        from core.database.session import get_session
        from moduly.externi_audity.modely import ExternalAuditParticipant
        from datetime import datetime

        with get_session() as session:
            session.add(
                ExternalAuditParticipant(
                    external_audit_id=int(saved.id),
                    role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
                    source_type=EXTERNAL_AUDIT_SOURCE_LEGACY_INVALID,
                    source_id=0,
                    display_name_snapshot="Historický auditor",
                    display_order=5,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
            )
            session.commit()

        editor = ExternalAuditEditorDialog(audit_id=int(saved.id))
        self.assertEqual(editor.auditor_list.count(), 1)
        self.assertIn("Neplatný externí auditor", editor.auditor_list.item(0).text())
        # Přidání platného auditora do draftu + Uložit musí selhat, dokud legacy zůstane.
        editor.auditor_selector.set_person_id(int(self.person2.id))
        editor._add_participant(
            EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
            "person",
            editor.auditor_selector,
            editor.auditor_list,
        )
        self.assertEqual(editor.auditor_list.count(), 2)
        with patch.object(QMessageBox, "warning") as warn:
            self.assertFalse(editor._persist())
            warn.assert_called()
        # Po selhání zůstávají oba v draftu (žádné tiché zahození nového).
        self.assertEqual(
            len(
                editor._draft.participants_for_role(
                    EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR
                )
            ),
            2,
        )

    def test_06_task_create_factory_no_duplicate_kwargs(self) -> None:
        draft = self._draft()
        draft.findings = [
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description="Neshoda pro úkol",
                status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
            )
        ]
        saved = external_audit_service.save_bundle(draft)
        finding_id = int(draft.findings[0].db_id)
        editor = ExternalAuditEditorDialog(audit_id=int(saved.id))
        panel = editor.findings.nc_panel
        panel.refresh()
        panel.table.selectRow(0)

        captured: dict = {}

        class _FakeTaskDialog:
            def __init__(self, parent=None, task=None, *, create_kwargs=None, create_factory=None, **kwargs):
                self.task = None
                self._create_kwargs = dict(create_kwargs or {})
                self._create_factory = create_factory
                self._title = ""
                self.title_edit = type(
                    "T",
                    (),
                    {
                        "setPlainText": lambda _s, text: setattr(self, "_title", text),
                    },
                )()
                self.workplace_selector = type(
                    "W", (), {"set_workplace_id": lambda *a, **k: None}
                )()
                captured["create_kwargs"] = dict(self._create_kwargs)
                captured["has_factory"] = create_factory is not None

            def _capture_baseline(self):
                return None

            def exec(self):
                # Simulace TaskDialog.get_data() + create_factory (bez create_kwargs)
                data = {
                    "title": self._title or "Neshoda pro úkol",
                    "description": "",
                    "priority": "Normální",
                    "due_date": date.today(),
                    "remind_from": None,
                    "responsible_person_id": None,
                    "workplace_id": None,
                    "completed": False,
                    "completed_date": None,
                    "requires_verification": False,
                    "check_due_date": None,
                    "checked_date": None,
                    "checked_by_id": None,
                    "canceled": False,
                    "note": "",
                }
                assert self._create_kwargs == {}
                assert set(data) & set(self._create_kwargs) == set()
                captured["title"] = data["title"]
                self.task = self._create_factory(data)
                return QDialog.DialogCode.Rejected  # Uložit → Zavřít bez Accepted

        with patch(
            "moduly.externi_audity.ui.external_audit_findings_widget.TaskDialog",
            _FakeTaskDialog,
        ):
            panel.create_task()

        self.assertTrue(captured["has_factory"])
        self.assertEqual(captured["create_kwargs"], {})
        self.assertEqual(captured.get("title"), "Neshoda pro úkol")
        self.assertNotIn("Externí audit", captured.get("title") or "")
        links = external_audit_service.list_finding_task_ids(finding_id)
        self.assertEqual(len(links), 1)
        task = task_service.get_task_by_id(links[0])
        self.assertIsNotNone(task)
        self.assertEqual(task.title, "Neshoda pro úkol")
        self.assertIn("Typ auditu:", task.description)
        self.assertIn("Neshoda pro úkol", task.description)
        self.assertIn("Vzniklo z externího auditu", task.description)

    def test_07_task_save_then_close_links_once_for_nc_and_pkz(self) -> None:
        for finding_type, panel_attr in (
            (EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY, "nc_panel"),
            (EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT, "pkz_panel"),
        ):
            draft = self._draft(organization_name=f"Task {finding_type}")
            draft.findings = [
                FindingDraft(
                    client_key=new_client_key(),
                    finding_type=finding_type,
                    description=f"Text {finding_type}",
                    status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
                )
            ]
            saved = external_audit_service.save_bundle(draft)
            finding_id = int(draft.findings[0].db_id)
            editor = ExternalAuditEditorDialog(audit_id=int(saved.id))
            panel = getattr(editor.findings, panel_attr)
            panel.refresh()
            panel.table.selectRow(0)

            class _FakeTaskDialog:
                def __init__(self, *args, create_factory=None, create_kwargs=None, **kwargs):
                    self.task = None
                    self._create_factory = create_factory
                    self._create_kwargs = dict(create_kwargs or {})
                    self.title_edit = type("T", (), {"setPlainText": lambda *a, **k: None})()
                    self.workplace_selector = type(
                        "W", (), {"set_workplace_id": lambda *a, **k: None}
                    )()

                def _capture_baseline(self):
                    return None

                def exec(self):
                    data = {
                        "title": "t",
                        "description": "",
                        "priority": "Normální",
                        "due_date": date.today(),
                        "remind_from": None,
                        "responsible_person_id": None,
                        "workplace_id": None,
                        "completed": False,
                        "completed_date": None,
                        "requires_verification": False,
                        "check_due_date": None,
                        "checked_date": None,
                        "checked_by_id": None,
                        "canceled": False,
                        "note": "",
                    }
                    # Uložit (stay-open) + opětovné Uložit nesmí spadnout na kwargs
                    self.task = self._create_factory(data)
                    # druhé „Uložit“ už jen update — factory se znovu nevolá
                    return QDialog.DialogCode.Rejected

            with patch(
                "moduly.externi_audity.ui.external_audit_findings_widget.TaskDialog",
                _FakeTaskDialog,
            ):
                panel.create_task()
            links = external_audit_service.list_finding_task_ids(finding_id)
            self.assertEqual(len(links), 1, finding_type)
            with self.assertRaises(ExternalAuditError):
                external_audit_service.link_task(finding_id, links[0])

    def test_08_failed_main_save_blocks_task_dialog(self) -> None:
        draft = self._draft()
        draft.findings = [
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
                description="Blokovaný úkol",
                status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
            )
        ]
        saved = external_audit_service.save_bundle(draft)
        editor = ExternalAuditEditorDialog(audit_id=int(saved.id))
        # Znečistit + vložit legacy_invalid → hlavní Uložit selže
        editor._draft.participants.append(
            ParticipantDraft(
                client_key=new_client_key(),
                role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
                source_type=EXTERNAL_AUDIT_SOURCE_LEGACY_INVALID,
                source_id=0,
                display_name_snapshot="Legacy",
            )
        )
        editor._draft.findings[0].description = "Změněný text"
        panel = editor.findings.nc_panel
        panel.refresh()
        panel.table.selectRow(0)

        opened = {"value": False}

        class _BoomDialog:
            def __init__(self, *args, **kwargs):
                opened["value"] = True

            def exec(self):
                return QDialog.DialogCode.Rejected

        with (
            patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
            patch.object(QMessageBox, "warning"),
            patch(
                "moduly.externi_audity.ui.external_audit_findings_widget.TaskDialog",
                _BoomDialog,
            ),
        ):
            panel.create_task()
        self.assertFalse(opened["value"])

    def test_09_task_service_error_shows_message_no_link(self) -> None:
        draft = self._draft()
        draft.findings = [
            FindingDraft(
                client_key=new_client_key(),
                finding_type=EXTERNAL_AUDIT_FINDING_TYPE_IMPROVEMENT,
                description="Chyba služby",
                status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
            )
        ]
        saved = external_audit_service.save_bundle(draft)
        finding_id = int(draft.findings[0].db_id)
        editor = ExternalAuditEditorDialog(audit_id=int(saved.id))
        panel = editor.findings.pkz_panel
        panel.refresh()
        panel.table.selectRow(0)

        class _FakeTaskDialog:
            def __init__(self, *args, create_factory=None, **kwargs):
                self.task = None
                self._create_factory = create_factory
                self.title_edit = type("T", (), {"setPlainText": lambda *a, **k: None})()
                self.workplace_selector = type(
                    "W", (), {"set_workplace_id": lambda *a, **k: None}
                )()

            def _capture_baseline(self):
                return None

            def exec(self):
                data = {
                    "title": "x",
                    "description": "",
                    "priority": "Normální",
                    "due_date": date.today(),
                    "remind_from": None,
                    "responsible_person_id": None,
                    "workplace_id": None,
                    "completed": False,
                    "completed_date": None,
                    "requires_verification": False,
                    "check_due_date": None,
                    "checked_date": None,
                    "checked_by_id": None,
                    "canceled": False,
                    "note": "",
                }
                self.task = self._create_factory(data)
                return QDialog.DialogCode.Accepted

        with (
            patch(
                "moduly.externi_audity.ui.external_audit_findings_widget.task_service.create_task",
                side_effect=RuntimeError("DB down"),
            ),
            patch(
                "moduly.externi_audity.ui.external_audit_findings_widget.QMessageBox.warning"
            ) as warn,
            patch(
                "moduly.externi_audity.ui.external_audit_findings_widget.TaskDialog",
                _FakeTaskDialog,
            ),
        ):
            panel.create_task()
            warn.assert_called()
        self.assertEqual(external_audit_service.list_finding_task_ids(finding_id), [])

    def test_10_task_dialog_baseline_after_save_not_dirty(self) -> None:
        dialog = TaskDialog()
        dialog.title_edit.setPlainText("Baseline test")
        dialog._capture_baseline()
        self.assertFalse(dialog._is_dirty())
        # Po simulaci úspěšného persist se baseline obnoví
        dialog._baseline = dialog.get_data()
        self.assertFalse(dialog._is_dirty())

    def test_11_prefilled_description_helper(self) -> None:
        draft = self._draft(organization_name="Popis Org")
        finding = FindingDraft(
            client_key=new_client_key(),
            finding_type=EXTERNAL_AUDIT_FINDING_TYPE_NONCONFORMITY,
            description="Detail zjištění",
            status=EXTERNAL_AUDIT_FINDING_STATUS_OPEN,
        )
        text = _task_description(draft, finding)
        self.assertIn("Popis Org", text)
        self.assertIn("Detail zjištění", text)


if __name__ == "__main__":
    unittest.main()
