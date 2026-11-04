"""Fáze B1 – uložení, načtení a historie následného převzetí rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="coord-risk-receipt-b1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.koordinace_bozp.constants import (
        ATTACHMENT_TYPE_RISK_RECEIPT,
        RISK_RECEIPT_METHOD_EMAIL,
        RISK_RECEIPT_METHOD_IN_PERSON,
        RISK_RECEIPT_METHOD_PAPER,
        RISK_SUBMISSION_STATUS_WILL_EMAIL,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
        CoordinationRiskSubmissionHistory,
    )
    from moduly.koordinace_bozp.modely.coordination_risk_receipt import (
        CoordinationRiskReceipt,
        CoordinationRiskReceiptHistory,
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
    from moduly.koordinace_bozp.sluzby.coordination_risk_receipt_service import (
        CoordinationRiskReceiptError,
        coordination_risk_receipt_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_risk_submission_service import (
        coordination_risk_submission_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class CoordinationRiskReceiptB1Test(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationRiskReceiptHistory))
            session.execute(delete(CoordinationRiskReceipt))
            session.execute(delete(CoordinationRiskSubmissionHistory))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationMeasure))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.commit()
        settings_service.save_employer(
            ico="12345678",
            name="Hlavní firma s.r.o.",
            address="Praha",
            nace="",
        )

    def test_tables_exist(self) -> None:
        receipt_columns = _table_columns("coordination_risk_receipts")
        for name in (
            "coordination_employer_id",
            "received_on",
            "receipt_method",
            "storage_location",
            "note",
            "attachment_id",
            "recorded_at",
            "created_at",
            "updated_at",
        ):
            self.assertIn(name, receipt_columns)

        history_columns = _table_columns("coordination_risk_receipt_history")
        for name in (
            "receipt_id",
            "received_on_before",
            "received_on_after",
            "receipt_method_before",
            "receipt_method_after",
            "storage_location_before",
            "storage_location_after",
            "note_before",
            "note_after",
            "attachment_id_before",
            "attachment_id_after",
            "changed_at",
        ):
            self.assertIn(name, history_columns)

    def test_save_and_load_leaves_original_agreement(self) -> None:
        _coordination, contractor, other = self._contractors()
        due = date.today() + timedelta(days=7)
        agreement = coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_EMAIL,
            submission_date=due,
            expected_email="rizika@example.com",
            note="dohodnuto na schůzce",
        )
        received_on = date.today()

        stored = coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=received_on,
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
            note="doručeno po uzavření",
        )

        loaded = coordination_risk_receipt_service.get_for_employer(contractor.id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.id, stored.id)
        self.assertEqual(loaded.received_on, received_on)
        self.assertEqual(loaded.receipt_method, RISK_RECEIPT_METHOD_EMAIL)
        self.assertEqual(loaded.note, "doručeno po uzavření")
        self.assertEqual(loaded.storage_location, "")
        self.assertIsNone(loaded.attachment_id)
        self.assertIsNotNone(loaded.recorded_at)
        self.assertEqual(
            coordination_risk_receipt_service.list_history(loaded.id),
            [],
        )
        self.assertIsNone(
            coordination_risk_receipt_service.get_for_employer(other.id)
        )

        current_agreement = coordination_risk_submission_service.get_for_employer(
            contractor.id
        )
        self.assertEqual(current_agreement.id, agreement.id)
        self.assertEqual(
            current_agreement.submission_method,
            RISK_SUBMISSION_STATUS_WILL_EMAIL,
        )
        self.assertEqual(current_agreement.submission_date, due)
        self.assertEqual(current_agreement.expected_email, "rizika@example.com")
        self.assertEqual(current_agreement.note, "dohodnuto na schůzce")
        self.assertEqual(current_agreement.risks_text, "")
        self.assertEqual(current_agreement.document_reference, "")

    def test_paper_requires_storage_location_and_attachment_stays_optional(self) -> None:
        _coordination, contractor, _other = self._contractors()
        with self.assertRaises(CoordinationRiskReceiptError):
            coordination_risk_receipt_service.save_receipt(
                contractor.id,
                received_on=date.today(),
                receipt_method=RISK_RECEIPT_METHOD_PAPER,
                note="obal bez místa",
            )
        self.assertIsNone(
            coordination_risk_receipt_service.get_for_employer(contractor.id)
        )

        stored = coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=date.today(),
            receipt_method=RISK_RECEIPT_METHOD_PAPER,
            storage_location="Spisovna, skříň 3",
        )
        self.assertEqual(stored.storage_location, "Spisovna, skříň 3")
        self.assertIsNone(stored.attachment_id)
        self.assertEqual(
            coordination_risk_receipt_service.list_history(stored.id),
            [],
        )

    def test_correction_keeps_history_and_current_values(self) -> None:
        coordination, contractor, _other = self._contractors()
        first_day = date(2026, 11, 2)
        second_day = date(2026, 11, 4)
        created = coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=first_day,
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
            note="první evidence",
        )
        recorded_at = created.recorded_at
        source = _TMP / "prevzeti.pdf"
        source.write_bytes(b"%PDF-1.4\n")
        attachment = coordination_attachment_service.add_file(
            coordination_id=coordination.id,
            coordination_employer_id=contractor.id,
            source_path=source,
            attachment_type=ATTACHMENT_TYPE_RISK_RECEIPT,
        )

        updated = coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=second_day,
            receipt_method=RISK_RECEIPT_METHOD_PAPER,
            storage_location="Archiv stavby",
            note="upřesněno po kontrole",
            attachment_id=attachment.id,
        )
        self.assertEqual(updated.id, created.id)
        self.assertEqual(updated.recorded_at, recorded_at)
        self.assertEqual(updated.received_on, second_day)
        self.assertEqual(updated.receipt_method, RISK_RECEIPT_METHOD_PAPER)
        self.assertEqual(updated.storage_location, "Archiv stavby")
        self.assertEqual(updated.note, "upřesněno po kontrole")
        self.assertEqual(updated.attachment_id, attachment.id)

        history = coordination_risk_receipt_service.list_history(created.id)
        self.assertEqual(len(history), 1)
        entry = history[0]
        self.assertEqual(entry.received_on_before, first_day)
        self.assertEqual(entry.received_on_after, second_day)
        self.assertEqual(entry.receipt_method_before, RISK_RECEIPT_METHOD_EMAIL)
        self.assertEqual(entry.receipt_method_after, RISK_RECEIPT_METHOD_PAPER)
        self.assertEqual(entry.storage_location_before, "")
        self.assertEqual(entry.storage_location_after, "Archiv stavby")
        self.assertEqual(entry.note_before, "první evidence")
        self.assertEqual(entry.note_after, "upřesněno po kontrole")
        self.assertIsNone(entry.attachment_id_before)
        self.assertEqual(entry.attachment_id_after, attachment.id)
        self.assertIsNotNone(entry.changed_at)

        again = coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=date(2026, 11, 5),
            receipt_method=RISK_RECEIPT_METHOD_IN_PERSON,
            note="předáno na stavbě",
        )
        self.assertEqual(again.id, created.id)
        self.assertEqual(again.recorded_at, recorded_at)
        history = coordination_risk_receipt_service.list_history(created.id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[1].receipt_method_before, RISK_RECEIPT_METHOD_PAPER)
        self.assertEqual(
            history[1].receipt_method_after,
            RISK_RECEIPT_METHOD_IN_PERSON,
        )
        self.assertEqual(history[1].storage_location_before, "Archiv stavby")
        self.assertEqual(history[1].storage_location_after, "")
        self.assertEqual(history[1].attachment_id_before, attachment.id)
        self.assertIsNone(history[1].attachment_id_after)
        loaded = coordination_risk_receipt_service.get_for_employer(contractor.id)
        self.assertEqual(loaded.receipt_method, RISK_RECEIPT_METHOD_IN_PERSON)
        self.assertEqual(loaded.note, "předáno na stavbě")

    def test_unchanged_save_does_not_append_history(self) -> None:
        _coordination, contractor, _other = self._contractors()
        created = coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=date.today(),
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
            note="beze změny",
        )
        repeated = coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=date.today(),
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
            note="  beze změny  ",
        )
        self.assertEqual(repeated.id, created.id)
        self.assertEqual(repeated.recorded_at, created.recorded_at)
        self.assertEqual(
            coordination_risk_receipt_service.list_history(created.id),
            [],
        )

    def test_failed_correction_keeps_current_receipt(self) -> None:
        _coordination, contractor, _other = self._contractors()
        coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=date.today(),
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
            note="platný záznam",
        )
        with self.assertRaises(CoordinationRiskReceiptError):
            coordination_risk_receipt_service.save_receipt(
                contractor.id,
                received_on=date.today(),
                receipt_method=RISK_RECEIPT_METHOD_PAPER,
            )
        loaded = coordination_risk_receipt_service.get_for_employer(contractor.id)
        self.assertEqual(loaded.receipt_method, RISK_RECEIPT_METHOD_EMAIL)
        self.assertEqual(loaded.note, "platný záznam")
        self.assertEqual(
            coordination_risk_receipt_service.list_history(loaded.id),
            [],
        )

    def test_main_employer_is_rejected(self) -> None:
        coordination, _contractor, _other = self._contractors()
        main = coordination_employer_service.repository.get_main(coordination.id)
        with self.assertRaises(CoordinationRiskReceiptError):
            coordination_risk_receipt_service.save_receipt(
                main.id,
                received_on=date.today(),
                receipt_method=RISK_RECEIPT_METHOD_EMAIL,
            )

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
