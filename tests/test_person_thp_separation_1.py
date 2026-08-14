"""PERSON-THP-SEPARATION-1: zrcadla THP mimo Osoby + polymorfní Schůzky/EA."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="person-thp-sep-1-"))
_HOME = _TMP / "home"
_HOME.mkdir(parents=True)


with patch.object(Path, "home", return_value=_HOME):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database
    from core.database.upgrade_guard import (
        PreMigrationBackupError,
        clear_transition_complete,
        is_transition_complete,
        mark_migration_complete,
    )
    from moduly.externi_audity.constants import (
        EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
        EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
        EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON,
        EXTERNAL_AUDIT_SOURCE_LEGACY_INVALID,
        EXTERNAL_AUDIT_SOURCE_PERSON,
        EXTERNAL_AUDIT_SOURCE_THP_WORKER,
        EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
    )
    from moduly.externi_audity.sluzby.external_audit_draft import (
        ExternalAuditDraft,
        ParticipantDraft,
        VisitDraft,
        new_client_key,
    )
    from moduly.externi_audity.sluzby.external_audit_ea_0_schema_migration import (
        prepare_external_audit_ea_0_schema,
    )
    from moduly.externi_audity.sluzby.external_audit_service import (
        ExternalAuditError,
        external_audit_service,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.person_thp_separation_migration import (
        TRANSITION_ID,
        apply_person_thp_separation_data,
        build_unambiguous_mirror_map,
        needs_person_thp_separation,
        prepare_person_thp_separation,
        preflight_report,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.schuzky.sluzby.meeting_participant_ref import MEETING_SOURCE_THP_WORKER
    from moduly.schuzky.sluzby.meeting_service import meeting_service
    from moduly.schuzky.sluzby.meeting_template_service import meeting_template_service
    from moduly.schuzky.ui.meeting_people_widgets import MeetingPersonTypeahead
    from PySide6.QtWidgets import QApplication


class PersonThpSeparation1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        initialize_database()
        cls.ws = storage_module.storage_service.base
        cls.db_path = storage_module.storage_service.database_path
        prepare_external_audit_ea_0_schema(
            workspace_root=cls.ws,
            database_path=cls.db_path,
        )

    def setUp(self) -> None:
        clear_transition_complete(self.ws, transition_id=TRANSITION_ID)

    def _db_path(self) -> Path:
        return Path(storage_module.storage_service.database_path)

    def _workspace(self) -> Path:
        return Path(storage_module.storage_service.base)

    def _person_count(self) -> int:
        return len(person_service.get_all(include_inactive=True))

    def _make_thp_and_mirror(self, *, first: str, last: str, email: str = ""):
        worker = settings_service.save_worker(
            first_name=first,
            last_name=last,
            email=email,
            position="Technik",
        )
        person = person_service.create_person(
            first_name=first,
            last_name=last,
            email=email,
            job_title="Technik",
            is_employee=True,
        )
        return worker, person

    def test_01_unambiguous_map_and_is_employee_alone(self) -> None:
        worker, person = self._make_thp_and_mirror(first="Ada", last="Mapová")
        lone = person_service.create_person(
            first_name="Bez",
            last_name="Thpéčka",
            is_employee=True,
        )
        import sqlite3

        con = sqlite3.connect(str(self._db_path()))
        try:
            mapping = build_unambiguous_mirror_map(con)
            self.assertEqual(mapping.get(person.id), worker.id)
            self.assertNotIn(lone.id, mapping)
            report = preflight_report(con)
            self.assertIn(person.id, report["convertible"])
        finally:
            con.close()

    def test_02_ambiguous_not_deleted(self) -> None:
        settings_service.save_worker(first_name="Dvoj", last_name="Stejný", email="a@x.cz")
        settings_service.save_worker(first_name="Dvoj", last_name="Stejný", email="b@x.cz")
        person = person_service.create_person(
            first_name="Dvoj",
            last_name="Stejný",
            email="",
            is_employee=True,
        )
        before = self._person_count()
        result = prepare_person_thp_separation(
            workspace_root=self._workspace(),
            database_path=self._db_path(),
        )
        self.assertTrue(result.migrated or result.skipped_reason)
        # Osoba s nejednoznačnou shodou zůstane
        self.assertIsNotNone(person_service.get_by_id(person.id))
        self.assertGreaterEqual(self._person_count(), 1)

    def test_03_backup_failure_no_change(self) -> None:
        worker, person = self._make_thp_and_mirror(first="Zaloha", last="Selže")
        clear_transition_complete(self._workspace(), transition_id=TRANSITION_ID)
        before = self._person_count()
        with patch(
            "moduly.nastaveni.sluzby.person_thp_separation_migration.create_verified_pre_migration_backup",
            side_effect=PreMigrationBackupError("fail"),
        ):
            with self.assertRaises(PreMigrationBackupError):
                prepare_person_thp_separation(
                    workspace_root=self._workspace(),
                    database_path=self._db_path(),
                )
        self.assertEqual(self._person_count(), before)
        self.assertIsNotNone(person_service.get_by_id(person.id))
        self.assertFalse(
            is_transition_complete(self._workspace(), TRANSITION_ID)
        )

    def test_04_meetings_and_templates_convert(self) -> None:
        worker, person = self._make_thp_and_mirror(first="Org", last="Schůzka")
        external = person_service.create_person(
            first_name="Ext",
            last_name="Host",
            is_employee=False,
        )
        meeting = meeting_service.create_meeting(
            title="Test",
            organizer_person_id=person.id,
            participant_ids=[person.id, external.id],
        )
        template = meeting_template_service.create_template(
            name="Šablona",
            organizer_person_id=person.id,
            participant_ids=[person.id],
        )
        clear_transition_complete(self._workspace(), transition_id=TRANSITION_ID)
        result = prepare_person_thp_separation(
            workspace_root=self._workspace(),
            database_path=self._db_path(),
        )
        self.assertTrue(result.migrated)
        self.assertIsNotNone(result.pre_migration_backup_path)
        self.assertTrue(result.pre_migration_backup_path.is_file())

        meeting = meeting_service.get_by_id(meeting.id)
        org = meeting_service.organizer_ref(meeting)
        self.assertEqual(org["source_type"], MEETING_SOURCE_THP_WORKER)
        self.assertEqual(org["source_id"], worker.id)
        self.assertIsNone(meeting.organizer_person_id)
        refs = meeting_service.parse_participant_refs(meeting)
        self.assertIn(
            {"source_type": MEETING_SOURCE_THP_WORKER, "source_id": worker.id},
            refs,
        )
        self.assertIn(
            {"source_type": "person", "source_id": external.id},
            refs,
        )
        self.assertIsNotNone(person_service.get_by_id(external.id))
        self.assertIsNone(person_service.get_by_id(person.id))

        template = meeting_template_service.get_by_id(template.id)
        t_org = meeting_template_service.organizer_ref(template)
        self.assertEqual(t_org["source_type"], MEETING_SOURCE_THP_WORKER)
        self.assertEqual(t_org["source_id"], worker.id)

    def test_05_typeahead_read_only(self) -> None:
        worker = settings_service.save_worker(
            first_name="Read",
            last_name="Only",
            position="BOZP",
        )
        before = self._person_count()
        widget = MeetingPersonTypeahead()
        widget.reload()
        widget.reload()
        self.assertEqual(self._person_count(), before)
        # THP je ve výběru jako thp_worker
        found = False
        for i in range(widget.count()):
            data = widget.itemData(i)
            if isinstance(data, dict) and data.get("source_id") == worker.id:
                found = True
                break
        self.assertTrue(found)
        widget.close()

    def test_06_ea_invited_and_invalid_auditor(self) -> None:
        from datetime import date

        from moduly.nastaveni.constants.workplace_hierarchy_constants import (
            WORKPLACE_ITEM_TYPE_OPERATION,
        )

        wp = settings_service.save_workplace(
            name="Provoz SEP",
            address="Ulice 1",
            active=True,
            audit_enabled=True,
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )

        thp_inv, person_inv = self._make_thp_and_mirror(first="Poz", last="Vaný")
        # Auditor mirror: nejdřív Osoba + participant, teprve potom THP (runtime už odmítá mirror)
        person_aud = person_service.create_person(
            first_name="Aud",
            last_name="Itor",
            job_title="Technik",
            is_employee=True,
        )
        real_ext = person_service.create_person(
            first_name="Skut",
            last_name="Ečný",
            is_employee=False,
        )
        thp_rep = settings_service.save_worker(
            first_name="Zást",
            last_name="Upce",
        )

        audit = external_audit_service.create_audit(
            audit_type=EXTERNAL_AUDIT_TYPE_SURVEILLANCE,
            organization_ico="12345678",
            organization_name="Firma",
        )
        p_inv = external_audit_service.add_participant(
            audit.id,
            role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON,
            source_type=EXTERNAL_AUDIT_SOURCE_PERSON,
            source_id=person_inv.id,
        )
        p_aud = external_audit_service.add_participant(
            audit.id,
            role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
            source_type=EXTERNAL_AUDIT_SOURCE_PERSON,
            source_id=person_aud.id,
        )
        thp_aud = settings_service.save_worker(
            first_name="Aud",
            last_name="Itor",
            position="Technik",
        )
        external_audit_service.add_participant(
            audit.id,
            role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE,
            source_type=EXTERNAL_AUDIT_SOURCE_THP_WORKER,
            source_id=thp_rep.id,
        )
        visit = external_audit_service.add_visit(
            audit.id,
            visit_date=date(2026, 8, 1),
            workplace_id=wp.id,
        )
        external_audit_service.set_visit_participants(
            visit.id, [p_inv.id, p_aud.id]
        )

        clear_transition_complete(self._workspace(), transition_id=TRANSITION_ID)
        result = prepare_person_thp_separation(
            workspace_root=self._workspace(),
            database_path=self._db_path(),
        )
        self.assertTrue(result.migrated)

        draft = external_audit_service.load_draft(audit.id)
        invited = [
            p
            for p in draft.participants
            if p.role == EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON
        ]
        self.assertEqual(len(invited), 1)
        self.assertEqual(invited[0].source_type, EXTERNAL_AUDIT_SOURCE_THP_WORKER)
        self.assertEqual(invited[0].source_id, thp_inv.id)

        auditors = [
            p
            for p in draft.participants
            if p.role == EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR
        ]
        self.assertEqual(len(auditors), 1)
        self.assertEqual(auditors[0].source_type, EXTERNAL_AUDIT_SOURCE_LEGACY_INVALID)
        self.assertEqual(auditors[0].source_id, 0)
        self.assertTrue(auditors[0].display_name_snapshot)

        reps = [
            p
            for p in draft.participants
            if p.role == EXTERNAL_AUDIT_PARTICIPANT_ROLE_COMPANY_REPRESENTATIVE
        ]
        self.assertEqual(reps[0].source_type, EXTERNAL_AUDIT_SOURCE_THP_WORKER)
        self.assertEqual(len(draft.visits[0].participant_keys), 2)

        with self.assertRaises(ExternalAuditError):
            external_audit_service.save_bundle(draft)

        draft.participants = [
            p
            for p in draft.participants
            if p.source_type != EXTERNAL_AUDIT_SOURCE_LEGACY_INVALID
        ]
        draft.participants.append(
            ParticipantDraft(
                client_key=new_client_key(),
                role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_EXTERNAL_AUDITOR,
                source_type=EXTERNAL_AUDIT_SOURCE_PERSON,
                source_id=real_ext.id,
                display_name_snapshot=real_ext.display_name,
                display_order=10,
            )
        )
        for v in draft.visits:
            v.participant_keys = [
                k
                for k in v.participant_keys
                if any(p.client_key == k for p in draft.participants)
            ]
        external_audit_service.save_bundle(draft)

        # Nový invited může být THP
        draft = external_audit_service.load_draft(audit.id)
        draft.participants.append(
            ParticipantDraft(
                client_key=new_client_key(),
                role=EXTERNAL_AUDIT_PARTICIPANT_ROLE_INVITED_PERSON,
                source_type=EXTERNAL_AUDIT_SOURCE_THP_WORKER,
                source_id=thp_rep.id,
                display_name_snapshot=thp_rep.display_name,
                display_order=40,
            )
        )
        external_audit_service.save_bundle(draft)

    def test_07_idempotent_second_run(self) -> None:
        self._make_thp_and_mirror(first="Idem", last="Potent")
        clear_transition_complete(self._workspace(), transition_id=TRANSITION_ID)
        first = prepare_person_thp_separation(
            workspace_root=self._workspace(),
            database_path=self._db_path(),
        )
        self.assertTrue(first.migrated)
        second = prepare_person_thp_separation(
            workspace_root=self._workspace(),
            database_path=self._db_path(),
        )
        self.assertFalse(second.migrated)
        self.assertEqual(second.skipped_reason, "already_complete")

    def test_08_rollback_mid_convert(self) -> None:
        worker, person = self._make_thp_and_mirror(first="Roll", last="Back")
        meeting_service.create_meeting(
            title="RB",
            organizer_person_id=person.id,
        )
        import sqlite3

        con = sqlite3.connect(str(self._db_path()))
        before = self._person_count()
        try:
            con.execute("BEGIN IMMEDIATE")
            with patch(
                "moduly.nastaveni.sluzby.person_thp_separation_migration._convert_external_audit_participants",
                side_effect=RuntimeError("boom"),
            ):
                with self.assertRaises(RuntimeError):
                    apply_person_thp_separation_data(con)
            con.rollback()
        finally:
            con.close()
        self.assertEqual(self._person_count(), before)
        self.assertIsNotNone(person_service.get_by_id(person.id))


if __name__ == "__main__":
    unittest.main()
