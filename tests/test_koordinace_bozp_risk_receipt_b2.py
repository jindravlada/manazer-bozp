"""Fáze B2 – provozní stav převzetí, protokol a dokončení navázaného úkolu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="coord-risk-receipt-b2-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.session import get_session
    from moduly.koordinace_bozp.constants import (
        BOZP_COORDINATION_STATUS_CLOSED,
        ENTITY_COORDINATION_RISK_SUBMISSION,
        PROTOCOL_WARNING_RISKS_NOT_SUBMITTED,
        RISK_HANDOVER_STATUS_SUBSEQUENTLY_RECEIVED,
        RISK_RECEIPT_METHOD_EMAIL,
        RISK_RECEIPT_METHOD_IN_PERSON,
        RISK_RECEIPT_METHOD_PAPER,
        RISK_SUBMISSION_STATUS_WILL_EMAIL,
        RISK_SUBMISSION_STATUS_WILL_PAPER,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
        CoordinationRiskSubmissionHistory,
    )
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
    from moduly.koordinace_bozp.modely.coordination_risk_receipt import (
        CoordinationRiskReceipt,
        CoordinationRiskReceiptHistory,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
        coordination_protocol_builder,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_document import (
        render_blocks_to_plain_lines,
    )
    from moduly.koordinace_bozp.sluzby.coordination_risk_receipt_service import (
        CoordinationRiskReceiptError,
        coordination_risk_receipt_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_risk_submission_service import (
        coordination_risk_submission_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.modely.task import Task
    from moduly.ukoly.sluzby.task_service import task_service


_PROTOCOL_DAY = date(2026, 11, 4)


class CoordinationRiskReceiptB2Test(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationRiskReceiptHistory))
            session.execute(delete(CoordinationRiskReceipt))
            session.execute(delete(CoordinationRiskSubmissionHistory))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationMeasure))
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

    def test_one_supplier_receipt_updates_operational_status_only(self) -> None:
        coordination, contractor, _other = self._contractors()
        self._close(coordination)
        due = date(2026, 11, 20)
        coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_EMAIL,
            submission_date=due,
            expected_email="rizika@example.com",
            note="dohodnuto na schůzce",
            risks_text="text z protokolu",
        )
        received_on = date(2026, 11, 18)

        coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=received_on,
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
            note="doručeno později",
        )

        operational = coordination_risk_submission_service.operational_handover(
            contractor.id
        )
        self.assertEqual(
            operational.status,
            RISK_HANDOVER_STATUS_SUBSEQUENTLY_RECEIVED,
        )
        self.assertEqual(operational.label, "Následně převzato")
        self.assertEqual(operational.received_on, received_on)
        self.assertEqual(operational.receipt_method, RISK_RECEIPT_METHOD_EMAIL)
        self.assertEqual(operational.receipt_method_label, "E-mail")
        self.assertEqual(
            coordination_risk_submission_service.handover_status(contractor.id),
            RISK_SUBMISSION_STATUS_WILL_EMAIL,
        )
        agreement = coordination_risk_submission_service.get_for_employer(contractor.id)
        self.assertEqual(agreement.submission_date, due)
        self.assertEqual(agreement.expected_email, "rizika@example.com")
        self.assertEqual(agreement.note, "dohodnuto na schůzce")
        self.assertEqual(agreement.risks_text, "text z protokolu")
        self.assertNotIn(
            contractor.id,
            self._pending_risk_employers(coordination.id),
        )
        self.assertEqual(
            bozp_coordination_service.get_by_id(coordination.id).status,
            BOZP_COORDINATION_STATUS_CLOSED,
        )

    def test_other_supplier_and_protocol_stay_unchanged(self) -> None:
        coordination, first, second = self._contractors()
        self._close(coordination)
        coordination_risk_submission_service.save_submission(
            first.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_EMAIL,
            submission_date=date(2026, 11, 20),
            expected_email="prvni@example.com",
            note="dohoda prvního",
            risks_text="rizika prvního dodavatele",
        )
        coordination_risk_submission_service.save_submission(
            second.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_PAPER,
            submission_date=date(2026, 11, 21),
            note="dohoda druhého",
        )
        before = coordination_protocol_builder.build(
            coordination.id,
            today=_PROTOCOL_DAY,
        )
        before_lines = render_blocks_to_plain_lines(
            before.protocol_data["document"]["blocks"]
        )
        self.assertEqual(
            self._pending_risk_employers(coordination.id),
            {first.id, second.id},
        )

        coordination_risk_receipt_service.save_receipt(
            first.id,
            received_on=date(2026, 11, 18),
            receipt_method=RISK_RECEIPT_METHOD_IN_PERSON,
            note="poznámka mimo protokol",
        )

        after = coordination_protocol_builder.build(
            coordination.id,
            today=_PROTOCOL_DAY,
        )
        after_lines = render_blocks_to_plain_lines(
            after.protocol_data["document"]["blocks"]
        )
        self.assertEqual(
            before.protocol_data["document"]["blocks"],
            after.protocol_data["document"]["blocks"],
        )
        self.assertEqual(before_lines, after_lines)
        self.assertEqual(
            before.protocol_data["attachments_by_group"],
            after.protocol_data["attachments_by_group"],
        )
        self.assertNotIn("Následně převzato", "\n".join(after_lines))
        self.assertNotIn("poznámka mimo protokol", "\n".join(after_lines))
        self.assertIn("dohoda prvního", "\n".join(after_lines))
        self.assertIn("dohoda druhého", "\n".join(after_lines))
        self.assertIn("rizika prvního dodavatele", "\n".join(after_lines))
        self.assertEqual(self._pending_risk_employers(coordination.id), {second.id})

        first_state = coordination_risk_submission_service.operational_handover(first.id)
        second_state = coordination_risk_submission_service.operational_handover(
            second.id
        )
        self.assertEqual(
            first_state.status,
            RISK_HANDOVER_STATUS_SUBSEQUENTLY_RECEIVED,
        )
        self.assertEqual(first_state.received_on, date(2026, 11, 18))
        self.assertEqual(first_state.receipt_method_label, "Osobně")
        self.assertEqual(second_state.status, RISK_SUBMISSION_STATUS_WILL_PAPER)
        self.assertIsNone(second_state.received_on)
        self.assertEqual(second_state.receipt_method, "")
        self.assertEqual(
            coordination_risk_submission_service.handover_status(first.id),
            RISK_SUBMISSION_STATUS_WILL_EMAIL,
        )
        self.assertEqual(
            coordination_risk_submission_service.handover_status(second.id),
            RISK_SUBMISSION_STATUS_WILL_PAPER,
        )
        self.assertEqual(
            bozp_coordination_service.get_by_id(coordination.id).status,
            BOZP_COORDINATION_STATUS_CLOSED,
        )

    def test_open_linked_task_is_completed_and_title_lookalike_is_not(self) -> None:
        coordination, contractor, _other = self._contractors()
        self._close(coordination)
        submission = self._plan_email(contractor)
        linked = task_service.get_task_by_id(submission.task_id)
        lookalike = task_service.create_task(
            title=linked.title,
            description="Stejný název, jiný původ.",
            source_module="manual",
        )

        with self.assertRaises(CoordinationRiskReceiptError):
            coordination_risk_receipt_service.save_receipt(
                contractor.id,
                received_on=date(2026, 11, 18),
                receipt_method=RISK_RECEIPT_METHOD_PAPER,
            )
        self.assertFalse(task_service.get_task_by_id(linked.id).completed)

        coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=date(2026, 11, 18),
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
        )

        self.assertTrue(task_service.get_task_by_id(linked.id).completed)
        self.assertFalse(task_service.get_task_by_id(lookalike.id).completed)
        self.assertEqual(
            len(
                task_service.list_by_source(
                    ENTITY_COORDINATION_RISK_SUBMISSION,
                    submission.id,
                )
            ),
            1,
        )
        self.assertEqual(
            bozp_coordination_service.get_by_id(coordination.id).status,
            BOZP_COORDINATION_STATUS_CLOSED,
        )

    def test_completed_task_is_left_unchanged(self) -> None:
        _coordination, contractor, _other = self._contractors()
        submission = self._plan_email(contractor)
        task_service.mark_completed(submission.task_id)
        task = task_service.get_task_by_id(submission.task_id)
        task.note = "historický záznam"
        task.completed_date = date(2024, 5, 6)
        task.description = "Původní popis úkolu."
        task.updated_at = datetime(2024, 5, 6, 9, 0, 0)
        task_service.repository.update(task)

        coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=date(2026, 11, 18),
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
        )

        stored = task_service.get_task_by_id(submission.task_id)
        self.assertTrue(stored.completed)
        self.assertEqual(stored.completed_date, date(2024, 5, 6))
        self.assertEqual(stored.note, "historický záznam")
        self.assertEqual(stored.description, "Původní popis úkolu.")
        self.assertEqual(stored.updated_at, datetime(2024, 5, 6, 9, 0, 0))
        self.assertEqual(
            len(
                task_service.list_by_source(
                    ENTITY_COORDINATION_RISK_SUBMISSION,
                    submission.id,
                )
            ),
            1,
        )

    def test_missing_task_is_not_created(self) -> None:
        _coordination, contractor, _other = self._contractors()
        submission = self._plan_email(contractor)
        removed_id = submission.task_id
        with get_session() as session:
            session.execute(delete(Task).where(Task.id == removed_id))
            session.commit()
        self.assertIsNone(task_service.get_task_by_id(removed_id))
        submission.task_id = None
        coordination_risk_submission_service.repository.update(submission)
        decoy = task_service.create_task(
            title="Předání rizik dodavatele PRV",
            source_module="manual",
        )

        coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=date(2026, 11, 18),
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
        )

        self.assertEqual(
            [task.id for task in task_service.repository.get_all()],
            [decoy.id],
        )
        self.assertEqual(
            task_service.list_by_source(
                ENTITY_COORDINATION_RISK_SUBMISSION,
                submission.id,
            ),
            [],
        )
        self.assertFalse(task_service.get_task_by_id(decoy.id).completed)
        self.assertIsNotNone(
            coordination_risk_receipt_service.get_for_employer(contractor.id)
        )

    def test_historical_duplicates_complete_only_linked_task(self) -> None:
        _coordination, contractor, _other = self._contractors()
        submission = self._plan_email(contractor)
        linked_before = self._snapshot(submission.task_id)
        duplicate = task_service.create_task(
            title="Starší duplicitní úkol",
            description="Nemazat.",
            note="duplicita",
            source_module=ENTITY_COORDINATION_RISK_SUBMISSION,
            source_record_id=submission.id,
        )
        duplicate_before = self._snapshot(duplicate.id)
        lookalike = task_service.create_task(
            title=task_service.get_task_by_id(submission.task_id).title,
            source_module="manual",
        )

        coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=date(2026, 11, 18),
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
        )

        linked = task_service.get_task_by_id(submission.task_id)
        self.assertTrue(linked.completed)
        self.assertEqual(linked.title, linked_before[0])
        self.assertEqual(linked.description, linked_before[1])
        stored_duplicate = task_service.get_task_by_id(duplicate.id)
        self.assertEqual(self._snapshot(stored_duplicate.id), duplicate_before)
        self.assertFalse(stored_duplicate.completed)
        self.assertFalse(task_service.get_task_by_id(lookalike.id).completed)
        self.assertEqual(
            len(
                task_service.list_by_source(
                    ENTITY_COORDINATION_RISK_SUBMISSION,
                    submission.id,
                )
            ),
            2,
        )

    def test_ambiguous_duplicates_without_task_link_stay_open(self) -> None:
        _coordination, contractor, _other = self._contractors()
        submission = self._plan_email(contractor)
        first_id = submission.task_id
        second = task_service.create_task(
            title="Druhý otevřený úkol",
            source_module=ENTITY_COORDINATION_RISK_SUBMISSION,
            source_record_id=submission.id,
        )
        submission.task_id = None
        coordination_risk_submission_service.repository.update(submission)
        completed_duplicate = task_service.create_task(
            title="Už splněná duplicita",
            completed=True,
            completed_date=date(2023, 1, 2),
            note="hotovo dříve",
            source_module=ENTITY_COORDINATION_RISK_SUBMISSION,
            source_record_id=submission.id,
        )
        completed_before = self._snapshot(completed_duplicate.id)

        coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=date(2026, 11, 18),
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
        )

        self.assertFalse(task_service.get_task_by_id(first_id).completed)
        self.assertFalse(task_service.get_task_by_id(second.id).completed)
        self.assertEqual(self._snapshot(completed_duplicate.id), completed_before)
        self.assertEqual(
            coordination_risk_submission_service.get_for_employer(
                contractor.id
            ).task_id,
            None,
        )

    def test_repeat_and_correction_do_not_complete_tasks_again(self) -> None:
        _coordination, contractor, _other = self._contractors()
        submission = self._plan_email(contractor)
        duplicate = task_service.create_task(
            title="Duplicita zůstává otevřená",
            source_module=ENTITY_COORDINATION_RISK_SUBMISSION,
            source_record_id=submission.id,
        )
        coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=date(2026, 11, 18),
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
            note="první evidence",
        )
        linked = task_service.get_task_by_id(submission.task_id)
        linked.updated_at = datetime(2024, 5, 6, 9, 0, 0)
        linked.completed_date = date(2024, 5, 6)
        task_service.repository.update(linked)
        duplicate_before = self._snapshot(duplicate.id)
        agreement_before = self._agreement_snapshot(contractor.id)

        coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=date(2026, 11, 18),
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
            note="  první evidence  ",
        )
        coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=date(2026, 11, 19),
            receipt_method=RISK_RECEIPT_METHOD_IN_PERSON,
            note="oprava data",
        )

        stored = task_service.get_task_by_id(submission.task_id)
        self.assertTrue(stored.completed)
        self.assertEqual(stored.completed_date, date(2024, 5, 6))
        self.assertEqual(stored.updated_at, datetime(2024, 5, 6, 9, 0, 0))
        self.assertEqual(self._snapshot(duplicate.id), duplicate_before)
        self.assertEqual(self._agreement_snapshot(contractor.id), agreement_before)
        history = coordination_risk_receipt_service.list_history(
            coordination_risk_receipt_service.get_for_employer(contractor.id).id
        )
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].note_before, "první evidence")
        self.assertEqual(history[0].note_after, "oprava data")
        self.assertFalse(task_service.get_task_by_id(duplicate.id).completed)

    def _contractors(self):
        coordination = bozp_coordination_service.create_coordination(
            subject="Následné převzetí",
            meeting_date=date.today(),
        )
        first = coordination_employer_service.add_participant(
            coordination.id,
            company_name="První dodavatel a.s.",
            abbreviation="PRV",
        )
        second = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Druhý dodavatel a.s.",
            abbreviation="DRU",
        )
        return coordination, first, second

    def _close(self, coordination) -> None:
        coordination.status = BOZP_COORDINATION_STATUS_CLOSED
        bozp_coordination_service.repository.update(coordination)

    def _plan_email(self, contractor):
        return coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_EMAIL,
            submission_date=date.today() + timedelta(days=7),
            expected_email="rizika@example.com",
            note="plánované předání",
        )

    def _pending_risk_employers(self, coordination_id: int) -> set[int]:
        result = coordination_protocol_builder.build(
            coordination_id,
            today=_PROTOCOL_DAY,
        )
        return {
            item.related_entity_id
            for item in result.warnings
            if item.code == PROTOCOL_WARNING_RISKS_NOT_SUBMITTED
        }

    def _snapshot(self, task_id: int):
        task = task_service.get_task_by_id(task_id)
        return (
            task.title,
            task.description,
            task.note,
            task.completed,
            task.completed_date,
            task.canceled,
            task.source_module,
            task.source_record_id,
            task.updated_at,
        )

    def _agreement_snapshot(self, employer_id: int):
        agreement = coordination_risk_submission_service.get_for_employer(employer_id)
        return (
            agreement.submission_method,
            agreement.submission_date,
            agreement.expected_email,
            agreement.document_reference,
            agreement.risks_text,
            agreement.note,
            agreement.task_id,
        )
