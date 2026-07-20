"""UX-COORD-13 – přepracování evidence předání rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-13-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.koordinace_bozp.constants import (
        ENTITY_COORDINATION_RISK_SUBMISSION,
        RISK_SUBMISSION_STATUS_EARLIER,
        RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
        RISK_SUBMISSION_STATUS_LABELS,
        RISK_SUBMISSION_STATUS_STATED_AT_MEETING,
        RISK_SUBMISSION_STATUS_WILL_EMAIL,
        RISK_SUBMISSION_STATUS_WILL_PAPER,
        RISK_SUBMISSION_STATUSES,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
        CoordinationRiskSubmissionHistory,
    )
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
        CoordinationPbpRevision,
    )
    from moduly.koordinace_bozp.modely.coordination_workplace import (
        CoordinationWorkplace,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_attachment_service import (
        coordination_attachment_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
        coordination_protocol_builder,
    )
    from moduly.koordinace_bozp.sluzby.coordination_risk_submission_service import (
        CoordinationRiskSubmissionError,
        coordination_risk_submission_service,
    )
    from moduly.koordinace_bozp.ui.coordination_risk_submissions_tab import (
        CoordinationRiskSubmissionsTab,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.modely.task import Task
    from moduly.ukoly.sluzby.task_service import task_service


class UxCoord13RiskSubmissionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationRiskSubmissionHistory))
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationContact))
            session.execute(delete(CoordinationEmployerActivity))
            session.execute(delete(CoordinationMeasure))
            session.execute(delete(CoordinationWorkplace))
            session.execute(delete(CoordinationCoordinator))
            session.execute(delete(CoordinationParticipant))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.execute(delete(Task))
            session.commit()
        settings_service.save_employer(
            ico="12345678",
            name="Hlavní firma s.r.o.",
            address="Praha",
            nace="",
        )

    def _setup(self):
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-13",
            meeting_date=date.today(),
        )
        contractor = coordination_employer_service.add_participant(
            coordination.id,
            company_name="ZX - Zkušební firma, a.s.",
            abbreviation="ZX-ZF",
        )
        return coordination, contractor

    def test_all_new_statuses_exist(self) -> None:
        self.assertEqual(len(RISK_SUBMISSION_STATUSES), 5)
        self.assertNotIn("not_submitted", RISK_SUBMISSION_STATUSES)
        for status in RISK_SUBMISSION_STATUSES:
            self.assertTrue(RISK_SUBMISSION_STATUS_LABELS[status])

    def test_dynamic_fields_by_status(self) -> None:
        coordination, contractor = self._setup()
        tab = CoordinationRiskSubmissionsTab(None, coordination_id=coordination.id)
        index = tab.employer_combo.findData(contractor.id)
        tab.employer_combo.setCurrentIndex(index)

        tab.submission_method.setCurrentIndex(
            tab.submission_method.findData(RISK_SUBMISSION_STATUS_STATED_AT_MEETING)
        )
        self.assertTrue(tab.form.isRowVisible(tab.risks_text))
        self.assertFalse(tab.form.isRowVisible(tab.expected_email))

        tab.submission_method.setCurrentIndex(
            tab.submission_method.findData(RISK_SUBMISSION_STATUS_WILL_EMAIL)
        )
        self.assertTrue(tab.form.isRowVisible(tab.expected_email))
        self.assertTrue(tab.form.isRowVisible(tab.submission_date))
        self.assertFalse(tab.form.isRowVisible(tab.risks_text))

        tab.submission_method.setCurrentIndex(
            tab.submission_method.findData(RISK_SUBMISSION_STATUS_WILL_PAPER)
        )
        self.assertFalse(tab.form.isRowVisible(tab.expected_email))
        self.assertTrue(tab.form.isRowVisible(tab.submission_date))
        tab.close()

    def test_will_email_creates_task(self) -> None:
        coordination, contractor = self._setup()
        due = date.today() + timedelta(days=7)
        saved = coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_EMAIL,
            submission_date=due,
            expected_email="rizika@example.com",
            note="čekáme PDF",
        )
        self.assertIsNotNone(saved.task_id)
        task = task_service.get_task_by_id(saved.task_id)
        assert task is not None
        self.assertIn("ZX-ZF", task.title)
        self.assertEqual(task.due_date, due)
        self.assertEqual(task.source_module, ENTITY_COORDINATION_RISK_SUBMISSION)
        self.assertEqual(task.source_record_id, saved.id)
        self.assertIn("rizika@example.com", task.description)

    def test_will_paper_creates_task(self) -> None:
        _coordination, contractor = self._setup()
        due = date.today() + timedelta(days=3)
        saved = coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_PAPER,
            submission_date=due,
        )
        self.assertIsNotNone(saved.task_id)
        task = task_service.get_task_by_id(saved.task_id)
        assert task is not None
        self.assertEqual(task.due_date, due)
        self.assertIn("Předání rizik", task.title)

    def test_attachments_on_create_and_later(self) -> None:
        coordination, contractor = self._setup()
        coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_STATUS_STATED_AT_MEETING,
            risks_text="Pád z výšky",
            note="sděleno ústně",
        )
        first = _TMP / "rizika1.pdf"
        first.write_bytes(b"%PDF first")
        a1 = coordination_attachment_service.add_file(
            coordination_id=coordination.id,
            coordination_employer_id=contractor.id,
            source_path=first,
        )
        second = _TMP / "rizika2.pdf"
        second.write_bytes(b"%PDF second")
        a2 = coordination_attachment_service.add_file(
            coordination_id=coordination.id,
            coordination_employer_id=contractor.id,
            source_path=second,
        )
        items = coordination_attachment_service.list_for_employer(
            contractor.id,
            include_inactive=False,
        )
        self.assertEqual({item.id for item in items}, {a1.id, a2.id})

    def test_status_change_keeps_history_and_attachments(self) -> None:
        coordination, contractor = self._setup()
        due = date.today() + timedelta(days=5)
        first = coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_EMAIL,
            submission_date=due,
            expected_email="a@b.cz",
        )
        source = _TMP / "mail.pdf"
        source.write_bytes(b"%PDF mail")
        attachment = coordination_attachment_service.add_file(
            coordination_id=coordination.id,
            coordination_employer_id=contractor.id,
            source_path=source,
        )
        task_id = first.task_id
        updated = coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
            submission_date=date.today(),
            document_reference="MSG-001",
        )
        self.assertEqual(
            updated.submission_method,
            RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
        )
        history = coordination_risk_submission_service.list_history(updated.id)
        self.assertGreaterEqual(len(history), 2)
        self.assertEqual(history[-1].from_status, RISK_SUBMISSION_STATUS_WILL_EMAIL)
        self.assertEqual(history[-1].to_status, RISK_SUBMISSION_STATUS_EMAIL_BEFORE)
        still = coordination_attachment_service.get_by_id(attachment.id)
        assert still is not None
        self.assertTrue(still.active)
        # Úkol zůstává navázaný (pro budoucí uzavření).
        self.assertEqual(updated.task_id, task_id)

    def test_builder_uses_final_status_only(self) -> None:
        coordination, contractor = self._setup()
        coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_STATUS_EARLIER,
            submission_date=date(2026, 1, 15),
            document_reference="Protokol 1/2026",
            note="beze změn",
        )
        result = coordination_protocol_builder.build(coordination.id)
        rows = result.protocol_data["risk_handovers"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["handover_status"],
            RISK_SUBMISSION_STATUS_EARLIER,
        )
        self.assertEqual(
            rows[0]["handover_status_label"],
            RISK_SUBMISSION_STATUS_LABELS[RISK_SUBMISSION_STATUS_EARLIER],
        )
        submission = rows[0]["submission"]
        self.assertIn("task_id", submission)
        # Protokolová data obsahují stav; ODT/náhled tisknou jen label.

    def test_will_email_requires_fields(self) -> None:
        _coordination, contractor = self._setup()
        with self.assertRaises(CoordinationRiskSubmissionError):
            coordination_risk_submission_service.save_submission(
                contractor.id,
                submission_method=RISK_SUBMISSION_STATUS_WILL_EMAIL,
                expected_email="a@b.cz",
            )
        with self.assertRaises(CoordinationRiskSubmissionError):
            coordination_risk_submission_service.save_submission(
                contractor.id,
                submission_method=RISK_SUBMISSION_STATUS_WILL_EMAIL,
                submission_date=date.today(),
            )


if __name__ == "__main__":
    unittest.main()
