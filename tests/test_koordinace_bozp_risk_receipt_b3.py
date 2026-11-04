"""Fáze B3 – dialog a tlačítko následného převzetí rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="coord-risk-receipt-b3-"))
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
        BOZP_COORDINATION_STATUS_CLOSED,
        BOZP_COORDINATION_STATUS_DRAFT,
        ATTACHMENT_TYPE_CONTRACTOR_RISKS,
        ATTACHMENT_TYPE_RISK_RECEIPT,
        ATT_COL_ID,
        COL_ID,
        PROTOCOL_WARNING_RISKS_WITHOUT_ATTACHMENT,
        RISK_RECEIPT_METHOD_EMAIL,
        RISK_RECEIPT_METHOD_IN_PERSON,
        RISK_RECEIPT_METHOD_PAPER,
        RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
        RISK_SUBMISSION_STATUS_STATED_AT_MEETING,
        RISK_SUBMISSION_STATUS_WILL_EMAIL,
        RISK_SUBMISSION_STATUS_WILL_PAPER,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
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
    from moduly.koordinace_bozp.sluzby.coordination_attachment_service import (
        coordination_attachment_service,
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
    from moduly.koordinace_bozp.ui.coordination_risk_receipt_dialog import (
        CoordinationRiskReceiptDialog,
    )
    from moduly.koordinace_bozp.ui.coordination_risk_submissions_tab import (
        CoordinationRiskSubmissionsTab,
    )
    from moduly.koordinace_bozp.ui.koordinace_bozp_page import KoordinaceBozpPage
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.modely.task import Task


_PROTOCOL_DAY = date(2026, 11, 4)
_BOX = (
    "moduly.koordinace_bozp.ui.coordination_risk_receipt_dialog._exec_message_box"
)


class CoordinationRiskReceiptB3Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

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
            session.execute(delete(Task))
            session.commit()
        settings_service.save_employer(
            ico="12345678",
            name="Hlavní firma s.r.o.",
            address="Praha",
            nace="",
        )
        self._messages: list[str] = []

    def test_button_is_active_only_for_closed_coordination_with_handover(self) -> None:
        draft = bozp_coordination_service.create_coordination(
            subject="Rozpracovaná",
            meeting_date=date.today(),
        )
        empty_closed = self._closed_coordination("Uzavřená bez předání")
        coordination_employer_service.add_participant(
            empty_closed.id,
            company_name="Bez dohody a.s.",
            abbreviation="BEZ",
        )
        planned = self._closed_coordination("Uzavřená s plánem")
        planned_supplier = coordination_employer_service.add_participant(
            planned.id,
            company_name="Plánovaný dodavatel a.s.",
            abbreviation="PLA",
        )
        self._plan_email(planned_supplier)
        received = self._closed_coordination("Uzavřená s převzetím")
        received_supplier = coordination_employer_service.add_participant(
            received.id,
            company_name="Už předal a.s.",
            abbreviation="UZP",
        )
        coordination_risk_submission_service.save_submission(
            received_supplier.id,
            submission_method=RISK_SUBMISSION_STATUS_STATED_AT_MEETING,
            risks_text="sděleno na schůzce",
        )
        coordination_risk_receipt_service.save_receipt(
            received_supplier.id,
            received_on=date(2026, 11, 3),
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
        )

        page = KoordinaceBozpPage()
        self.assertEqual(page.risk_receipt_btn.text(), "Předání rizik")
        self.assertTrue(page.new_btn.isEnabled())
        self.assertFalse(page.risk_receipt_btn.isEnabled())

        self._select(page, draft.id)
        self.assertFalse(page.risk_receipt_btn.isEnabled())
        self.assertTrue(page.open_btn.isEnabled())
        self.assertTrue(page.print_btn.isEnabled())

        self._select(page, empty_closed.id)
        self.assertFalse(page.risk_receipt_btn.isEnabled())

        self._select(page, planned.id)
        self.assertTrue(page.risk_receipt_btn.isEnabled())

        self._select(page, received.id)
        self.assertTrue(page.risk_receipt_btn.isEnabled())

    def test_dialog_lists_only_coordination_suppliers_and_their_status(self) -> None:
        coordination, first, second = self._pair()
        self._close(coordination)
        self._plan_email(first, due=date(2026, 11, 20), note="dohoda prvního")
        coordination_risk_submission_service.save_submission(
            second.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_PAPER,
            submission_date=date(2026, 11, 21),
            note="dohoda druhého",
        )
        dialog = CoordinationRiskReceiptDialog(None, coordination_id=coordination.id)

        labels = [
            dialog.employer_combo.itemText(index)
            for index in range(dialog.employer_combo.count())
        ]
        ids = [
            dialog.employer_combo.itemData(index)
            for index in range(dialog.employer_combo.count())
        ]
        self.assertEqual(ids, [first.id, second.id])
        self.assertTrue(any("Rizika budou zaslána e-mailem" in label for label in labels))
        self.assertTrue(any("Rizika budou předána listinně" in label for label in labels))
        self.assertNotIn("Hlavní firma", " ".join(labels))

        dialog.employer_combo.setCurrentIndex(dialog.employer_combo.findData(first.id))
        self.assertIn("e-mailem", dialog.agreement_method.text())
        self.assertEqual(dialog.agreement_date.text(), "20.11.2026")
        self.assertEqual(dialog.operational_status.text(), "Rizika budou zaslána e-mailem")

        dialog.employer_combo.setCurrentIndex(dialog.employer_combo.findData(second.id))
        self.assertIn("listinně", dialog.agreement_method.text())
        self.assertEqual(dialog.agreement_date.text(), "21.11.2026")

    def test_confirmation_is_required_and_values_stay(self) -> None:
        coordination, contractor, _other = self._pair()
        self._close(coordination)
        self._plan_email(contractor)
        dialog = CoordinationRiskReceiptDialog(None, coordination_id=coordination.id)
        dialog.employer_combo.setCurrentIndex(
            dialog.employer_combo.findData(contractor.id)
        )
        dialog.received_on.set_date_value(date(2026, 11, 18))
        dialog.note.setPlainText("rozepsaná poznámka")
        dialog.confirmed.setChecked(False)

        with self._capture_messages():
            self.assertFalse(dialog.save_receipt())

        self.assertTrue(any("Potvrďte" in message for message in self._messages))
        self.assertEqual(dialog.note.toPlainText(), "rozepsaná poznámka")
        self.assertEqual(dialog.received_on.get_date(), date(2026, 11, 18))
        self.assertIsNone(
            coordination_risk_receipt_service.get_for_employer(contractor.id)
        )
        self.assertEqual(
            bozp_coordination_service.get_by_id(coordination.id).status,
            BOZP_COORDINATION_STATUS_CLOSED,
        )

    def test_paper_requires_storage_and_attachment_is_optional(self) -> None:
        coordination, contractor, _other = self._pair()
        self._close(coordination)
        self._plan_email(contractor)
        dialog = self._dialog_for(coordination.id, contractor.id)
        dialog.confirmed.setChecked(True)
        dialog.received_on.set_date_value(date(2026, 11, 18))
        dialog.receipt_method.setCurrentIndex(
            dialog.receipt_method.findData(RISK_RECEIPT_METHOD_PAPER)
        )
        dialog.storage_location.clear()
        dialog.note.setPlainText("listiny bez místa")

        with self._capture_messages():
            self.assertFalse(dialog.save_receipt())

        self.assertTrue(any("místo uložení" in message for message in self._messages))
        self.assertEqual(dialog.note.toPlainText(), "listiny bez místa")
        self.assertIsNone(
            coordination_risk_receipt_service.get_for_employer(contractor.id)
        )

        dialog.receipt_method.setCurrentIndex(
            dialog.receipt_method.findData(RISK_RECEIPT_METHOD_EMAIL)
        )
        with self._capture_messages():
            self.assertTrue(dialog.save_receipt())
        stored = coordination_risk_receipt_service.get_for_employer(contractor.id)
        self.assertIsNone(stored.attachment_id)
        self.assertEqual(
            bozp_coordination_service.get_by_id(coordination.id).status,
            BOZP_COORDINATION_STATUS_CLOSED,
        )

    def test_correction_shows_history_and_keeps_recorded_at(self) -> None:
        coordination, contractor, _other = self._pair()
        self._close(coordination)
        self._plan_email(contractor)
        dialog = self._dialog_for(coordination.id, contractor.id)
        dialog.confirmed.setChecked(True)
        dialog.received_on.set_date_value(date(2026, 11, 18))
        dialog.receipt_method.setCurrentIndex(
            dialog.receipt_method.findData(RISK_RECEIPT_METHOD_EMAIL)
        )
        dialog.note.setPlainText("první evidence")
        with self._capture_messages():
            self.assertTrue(dialog.save_receipt())
        recorded_at = coordination_risk_receipt_service.get_for_employer(
            contractor.id
        ).recorded_at

        dialog.note.setPlainText("oprava data")
        dialog.receipt_method.setCurrentIndex(
            dialog.receipt_method.findData(RISK_RECEIPT_METHOD_IN_PERSON)
        )
        with self._capture_messages():
            self.assertTrue(dialog.save_receipt())

        stored = coordination_risk_receipt_service.get_for_employer(contractor.id)
        self.assertEqual(stored.recorded_at, recorded_at)
        self.assertEqual(stored.note, "oprava data")
        self.assertEqual(dialog.history_table.rowCount(), 1)
        note_cell = dialog.history_table.item(0, 7).text()
        self.assertIn("první evidence", note_cell)
        self.assertIn("oprava data", note_cell)
        self.assertEqual(dialog.recorded_label.text(), recorded_at.strftime("%d.%m.%Y %H:%M"))
        agreement = coordination_risk_submission_service.get_for_employer(contractor.id)
        self.assertEqual(agreement.submission_method, RISK_SUBMISSION_STATUS_WILL_EMAIL)
        self.assertEqual(agreement.note, "plánované předání")
        self.assertEqual(
            bozp_coordination_service.get_by_id(coordination.id).status,
            BOZP_COORDINATION_STATUS_CLOSED,
        )

    def test_dialog_save_keeps_protocol_and_closed_coordination(self) -> None:
        coordination, contractor, other = self._pair()
        self._close(coordination)
        coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_EMAIL,
            submission_date=date(2026, 11, 20),
            expected_email="rizika@example.com",
            note="dohoda v protokolu",
            risks_text="text rizik v protokolu",
        )
        coordination_risk_submission_service.save_submission(
            other.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_PAPER,
            submission_date=date(2026, 11, 21),
            note="dohoda druhého",
        )
        before = coordination_protocol_builder.build(
            coordination.id,
            today=_PROTOCOL_DAY,
        )
        source = _TMP / "rizika.pdf"
        source.write_bytes(b"%PDF-1.4\n")
        dialog = self._dialog_for(coordination.id, contractor.id)
        dialog.confirmed.setChecked(True)
        dialog.received_on.set_date_value(date(2026, 11, 18))
        dialog.note.setPlainText("poznámka mimo protokol")
        dialog._pending_path = str(source)

        with self._capture_messages():
            self.assertTrue(dialog.save_receipt())

        after = coordination_protocol_builder.build(
            coordination.id,
            today=_PROTOCOL_DAY,
        )
        self.assertEqual(
            before.protocol_data["document"]["blocks"],
            after.protocol_data["document"]["blocks"],
        )
        lines = "\n".join(
            render_blocks_to_plain_lines(after.protocol_data["document"]["blocks"])
        )
        self.assertIn("dohoda v protokolu", lines)
        self.assertIn("text rizik v protokolu", lines)
        self.assertNotIn("poznámka mimo protokol", lines)
        self.assertNotIn("Následně převzato", lines)
        self.assertNotIn("rizika.pdf", lines)
        stored = coordination_risk_receipt_service.get_for_employer(contractor.id)
        self.assertIsNotNone(stored.attachment_id)
        attached = coordination_attachment_service.get_by_id(stored.attachment_id)
        self.assertEqual(attached.attachment_type, ATTACHMENT_TYPE_RISK_RECEIPT)
        self.assertEqual(
            before.protocol_data["attachments_by_group"],
            after.protocol_data["attachments_by_group"],
        )
        self.assertEqual(
            before.summary.active_attachments,
            after.summary.active_attachments,
        )
        self.assertEqual(
            bozp_coordination_service.get_by_id(coordination.id).status,
            BOZP_COORDINATION_STATUS_CLOSED,
        )
        self.assertEqual(
            coordination_risk_submission_service.handover_status(other.id),
            RISK_SUBMISSION_STATUS_WILL_PAPER,
        )

    def test_closed_tab_shows_receipt_without_hiding_agreement(self) -> None:
        coordination, contractor, _other = self._pair()
        self._close(coordination)
        self._plan_email(contractor, due=date(2026, 11, 20), note="původní dohoda")
        coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=date(2026, 11, 18),
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
            note="skutečné převzetí",
        )
        tab = CoordinationRiskSubmissionsTab(None, coordination_id=coordination.id)
        tab.set_content_editable(False)
        tab.employer_combo.setCurrentIndex(tab.employer_combo.findData(contractor.id))

        self.assertIn("Následně převzato", tab.status_label.text())
        self.assertIn("18.11.2026", tab.subsequent_receipt_label.text())
        self.assertIn("E-mail", tab.subsequent_receipt_label.text())
        self.assertFalse(tab.subsequent_receipt_label.isHidden())
        self.assertEqual(
            tab.submission_method.currentData(),
            RISK_SUBMISSION_STATUS_WILL_EMAIL,
        )
        self.assertEqual(tab.note.toPlainText(), "původní dohoda")
        self.assertEqual(tab.submission_date.get_date(), date(2026, 11, 20))
        self.assertFalse(tab.submission_method.isEnabled())
        self.assertTrue(tab.note.isReadOnly())
        self.assertFalse(tab.save_btn.isEnabled())

    def test_receipt_file_stays_out_of_original_list_and_protocol(self) -> None:
        coordination, contractor, _other = self._pair()
        self._close(coordination)
        coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
            submission_date=date(2026, 11, 1),
            note="předáno e-mailem",
            risks_text="původní text rizik",
        )
        original = self._attach(
            coordination,
            contractor,
            "puvodni.pdf",
            ATTACHMENT_TYPE_CONTRACTOR_RISKS,
            b"%PDF-1.4 puvodni\n",
        )
        before = coordination_protocol_builder.build(
            coordination.id,
            today=_PROTOCOL_DAY,
        )
        receipt_file = self._attach(
            coordination,
            contractor,
            "nasledne.pdf",
            ATTACHMENT_TYPE_RISK_RECEIPT,
            b"%PDF-1.4 nasledne\n",
        )
        coordination_risk_receipt_service.save_receipt(
            contractor.id,
            received_on=date(2026, 11, 18),
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
            attachment_id=receipt_file.id,
        )
        after = coordination_protocol_builder.build(
            coordination.id,
            today=_PROTOCOL_DAY,
        )
        self.assertEqual(
            before.protocol_data["document"]["blocks"],
            after.protocol_data["document"]["blocks"],
        )
        self.assertEqual(
            before.protocol_data["attachments_by_group"],
            after.protocol_data["attachments_by_group"],
        )
        self.assertEqual(
            before.summary.active_attachments,
            after.summary.active_attachments,
        )
        lines = "\n".join(
            render_blocks_to_plain_lines(after.protocol_data["document"]["blocks"])
        )
        self.assertNotIn("nasledne.pdf", lines)
        self.assertIn("puvodni.pdf", self._group_filenames(after))
        self.assertNotIn("nasledne.pdf", self._group_filenames(after))
        warning_codes = [item.code for item in after.warnings]
        self.assertNotIn(PROTOCOL_WARNING_RISKS_WITHOUT_ATTACHMENT, warning_codes)

        with_original = coordination_protocol_builder.build(
            coordination.id,
            today=_PROTOCOL_DAY,
        )
        coordination_attachment_service.deactivate(original.id)
        only_receipt = coordination_protocol_builder.build(
            coordination.id,
            today=_PROTOCOL_DAY,
        )
        self.assertNotIn(
            PROTOCOL_WARNING_RISKS_WITHOUT_ATTACHMENT,
            [item.code for item in with_original.warnings],
        )
        self.assertIn(
            PROTOCOL_WARNING_RISKS_WITHOUT_ATTACHMENT,
            [item.code for item in only_receipt.warnings],
        )
        self.assertEqual(only_receipt.summary.active_attachments, 0)
        self.assertEqual(only_receipt.protocol_data["attachments_by_group"], [])

        kept = coordination_attachment_service.get_by_id(original.id)
        self.assertEqual(kept.file_path, original.file_path)
        self.assertEqual(kept.attachment_type, ATTACHMENT_TYPE_CONTRACTOR_RISKS)
        stored_receipt = coordination_attachment_service.get_by_id(receipt_file.id)
        self.assertTrue(stored_receipt.active)
        self.assertEqual(
            coordination_attachment_service.resolve_path(stored_receipt).read_bytes(),
            b"%PDF-1.4 nasledne\n",
        )

        tab = CoordinationRiskSubmissionsTab(None, coordination_id=coordination.id)
        tab.set_content_editable(True)
        tab.employer_combo.setCurrentIndex(tab.employer_combo.findData(contractor.id))
        shown = self._table_ids(tab.attachments_table)
        self.assertEqual(shown, [original.id])
        self.assertNotIn(receipt_file.id, shown)

    def test_receipt_rejects_original_and_foreign_attachment(self) -> None:
        coordination, contractor, other = self._pair()
        original = self._attach(
            coordination,
            contractor,
            "puvodni.pdf",
            ATTACHMENT_TYPE_CONTRACTOR_RISKS,
        )
        foreign = self._attach(
            coordination,
            other,
            "cizi.pdf",
            ATTACHMENT_TYPE_RISK_RECEIPT,
        )
        mismatched = self._attach(
            coordination,
            contractor,
            "jina-koordinace.pdf",
            ATTACHMENT_TYPE_RISK_RECEIPT,
        )
        elsewhere = bozp_coordination_service.create_coordination(
            subject="Jiná koordinace",
            meeting_date=date.today(),
        )
        mismatched.coordination_id = elsewhere.id
        coordination_attachment_service.repository.update(mismatched)

        cases = (
            (original.id, "Následné převzetí rizik"),
            (foreign.id, "dodavateli"),
            (mismatched.id, "koordinaci"),
        )
        for attachment_id, fragment in cases:
            with self.assertRaises(CoordinationRiskReceiptError) as caught:
                coordination_risk_receipt_service.save_receipt(
                    contractor.id,
                    received_on=date(2026, 11, 18),
                    receipt_method=RISK_RECEIPT_METHOD_EMAIL,
                    attachment_id=attachment_id,
                )
            self.assertIn(fragment, str(caught.exception))
        self.assertIsNone(
            coordination_risk_receipt_service.get_for_employer(contractor.id)
        )
        kept = coordination_attachment_service.get_by_id(original.id)
        self.assertEqual(kept.attachment_type, ATTACHMENT_TYPE_CONTRACTOR_RISKS)
        self.assertTrue(kept.active)
        self.assertEqual(kept.coordination_employer_id, contractor.id)

    def test_replaced_receipt_file_stays_openable_from_history(self) -> None:
        coordination, contractor, _other = self._pair()
        self._close(coordination)
        self._plan_email(contractor)
        dialog = self._dialog_for(coordination.id, contractor.id)
        dialog.confirmed.setChecked(True)
        dialog.received_on.set_date_value(date(2026, 11, 18))
        first = self._pdf("prvni.pdf", b"%PDF-1.4 prvni\n")
        second = self._pdf("druhy.pdf", b"%PDF-1.4 druhy\n")
        third = self._pdf("treti.pdf", b"%PDF-1.4 treti\n")
        dialog._pending_path = str(first)
        with self._capture_messages():
            self.assertTrue(dialog.save_receipt())
        first_id = dialog._current_attachment_id
        dialog._pending_path = str(second)
        dialog.note.setPlainText("první výměna")
        with self._capture_messages():
            self.assertTrue(dialog.save_receipt())
        second_id = dialog._current_attachment_id
        dialog._pending_path = str(third)
        dialog.note.setPlainText("druhá výměna")
        with self._capture_messages():
            self.assertTrue(dialog.save_receipt())
        third_id = dialog._current_attachment_id

        self.assertEqual(dialog.history_table.rowCount(), 2)
        self.assertEqual(dialog.history_table.item(0, 8).text(), "prvni.pdf")
        self.assertEqual(dialog.history_table.item(0, 9).text(), "druhy.pdf")
        self.assertEqual(dialog.history_table.item(1, 8).text(), "druhy.pdf")
        self.assertEqual(dialog.history_table.item(1, 9).text(), "treti.pdf")
        self.assertTrue(dialog.open_attachment_btn.isEnabled())

        opened: list[Path] = []

        def remember(path, parent=None, title=""):
            opened.append(Path(path))
            return True

        opener = (
            "moduly.koordinace_bozp.sluzby.coordination_attachment_service"
            ".open_local_file"
        )
        with patch(opener, side_effect=remember):
            self.assertTrue(dialog.open_current_attachment())
            dialog.history_table.selectRow(0)
            self.assertTrue(dialog.open_selected_history_attachment())
            dialog.history_table.selectRow(1)
            self.assertTrue(dialog.open_selected_history_attachment())

        self.assertEqual(
            opened,
            [
                coordination_attachment_service.resolve_path(
                    coordination_attachment_service.get_by_id(third_id)
                ),
                coordination_attachment_service.resolve_path(
                    coordination_attachment_service.get_by_id(first_id)
                ),
                coordination_attachment_service.resolve_path(
                    coordination_attachment_service.get_by_id(second_id)
                ),
            ],
        )
        for attachment_id, payload in (
            (first_id, b"%PDF-1.4 prvni\n"),
            (second_id, b"%PDF-1.4 druhy\n"),
            (third_id, b"%PDF-1.4 treti\n"),
        ):
            stored = coordination_attachment_service.get_by_id(attachment_id)
            self.assertEqual(stored.attachment_type, ATTACHMENT_TYPE_RISK_RECEIPT)
            self.assertTrue(stored.active)
            self.assertEqual(
                coordination_attachment_service.resolve_path(stored).read_bytes(),
                payload,
            )

    def _capture_messages(self):
        def capture(box: QMessageBox) -> int:
            self._messages.append(box.text())
            return int(QMessageBox.StandardButton.Ok)

        self._messages.clear()
        return patch(_BOX, side_effect=capture)

    def _dialog_for(self, coordination_id: int, employer_id: int):
        dialog = CoordinationRiskReceiptDialog(None, coordination_id=coordination_id)
        dialog.employer_combo.setCurrentIndex(
            dialog.employer_combo.findData(employer_id)
        )
        return dialog

    def _pair(self):
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

    def _closed_coordination(self, subject: str):
        coordination = bozp_coordination_service.create_coordination(
            subject=subject,
            meeting_date=date.today(),
        )
        self._close(coordination)
        return coordination

    def _close(self, coordination) -> None:
        coordination.status = BOZP_COORDINATION_STATUS_CLOSED
        bozp_coordination_service.repository.update(coordination)

    def _pdf(self, name: str, payload: bytes = b"%PDF-1.4\n") -> Path:
        path = _TMP / name
        path.write_bytes(payload)
        return path

    def _attach(self, coordination, employer, name, attachment_type, payload=b"%PDF-1.4\n"):
        return coordination_attachment_service.add_file(
            coordination_id=coordination.id,
            coordination_employer_id=employer.id,
            source_path=self._pdf(name, payload),
            attachment_type=attachment_type,
        )

    def _table_ids(self, table) -> list[int]:
        ids = []
        for row in range(table.rowCount()):
            item = table.item(row, ATT_COL_ID)
            if item is not None:
                ids.append(int(item.text()))
        return ids

    def _group_filenames(self, result) -> list[str]:
        names = []
        for group in result.protocol_data["attachments_by_group"]:
            for attachment in group["attachments"]:
                names.append(attachment["original_filename"])
        return names

    def _plan_email(self, contractor, *, due=None, note="plánované předání"):
        return coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_EMAIL,
            submission_date=due or (date.today() + timedelta(days=7)),
            expected_email="rizika@example.com",
            note=note,
        )

    def _select(self, page: KoordinaceBozpPage, coordination_id: int) -> None:
        for row in range(page.table.rowCount()):
            item = page.table.item(row, COL_ID)
            if item is not None and int(item.text()) == coordination_id:
                page.table.selectRow(row)
                return
        self.fail(f"Koordinace {coordination_id} není v přehledu.")

    def test_draft_constant_is_not_eligible(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="Pořád rozpracováno",
            meeting_date=date.today(),
            status=BOZP_COORDINATION_STATUS_DRAFT,
        )
        supplier = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Dodavatel a.s.",
            abbreviation="DOD",
        )
        self._plan_email(supplier)
        self.assertFalse(
            coordination_risk_submission_service.accepts_subsequent_risk_receipt(
                coordination.id
            )
        )
