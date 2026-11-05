"""Fáze C3/4 – následné převzetí rizik se zaeviduje v katalogu stejným odkazem."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import delete, func, select

_TMP = Path(tempfile.mkdtemp(prefix="coord-catalog-receipt-c3-"))
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
    from core.models.attachment import Attachment
    from moduly.koordinace_bozp.constants import (
        PROTOCOL_CATALOG_DOCUMENTS_HEADING,
        PROTOCOL_SUBSEQUENT_RECEIPT_HEADING,
        RISK_RECEIPT_METHOD_EMAIL,
        RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
        RISK_SUBMISSION_STATUS_WILL_EMAIL,
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
    from moduly.koordinace_bozp.modely.coordination_risk_receipt import (
        CoordinationRiskReceipt,
        CoordinationRiskReceiptHistory,
    )
    from moduly.koordinace_bozp.modely.coordination_supplier_risk_link import (
        CoordinationSupplierRiskLink,
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
        coordination_risk_receipt_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_risk_submission_service import (
        coordination_risk_submission_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_supplier_risk_link_service import (
        CATALOG_RECEIPT_REGISTRATION_FAILED_MESSAGE,
        CATALOG_REGISTRATION_SKIPPED,
        coordination_supplier_risk_link_service,
    )
    from moduly.koordinace_bozp.ui.coordination_risk_receipt_dialog import (
        CoordinationRiskReceiptDialog,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.modely.supplier_risk import (
        SupplierRiskCompany,
        SupplierRiskDocument,
    )
    from moduly.rizeni_rizik.repository.supplier_risk_repository import (
        SupplierRiskRepository,
    )
    from moduly.rizeni_rizik.sluzby.supplier_risk_service import supplier_risk_service
    from moduly.ukoly.modely.task import Task
    from moduly.ukoly.sluzby.task_service import task_service


def _pdf(name: str, content: bytes) -> Path:
    path = _TMP / name
    path.write_bytes(content)
    return path


class CoordinationCatalogReceiptC3Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationSupplierRiskLink))
            session.execute(delete(SupplierRiskDocument))
            session.execute(delete(SupplierRiskCompany))
            session.execute(delete(CoordinationRiskReceiptHistory))
            session.execute(delete(CoordinationRiskReceipt))
            session.execute(delete(CoordinationRiskSubmissionHistory))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(Task))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.execute(delete(Attachment))
            session.commit()
        settings_service.save_employer(
            ico="11111111",
            name="Hlavní firma s.r.o.",
            address="Praha",
            nace="",
        )
        self._messages: list[str] = []

    def test_existing_supplier_receives_document_without_second_copy(self) -> None:
        employer = self._employer(ico="87 654 321", name="Alfa stavby")
        company = supplier_risk_service.create_company(
            name="Uložený název",
            ico="87654321",
        )
        agreement = coordination_risk_submission_service.save_submission(
            employer.id,
            submission_method=RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
            submission_date=date(2026, 3, 1),
            note="původní dohoda",
            risks_text="text dohody",
        )
        content = b"%PDF-1.4 prevzeti\n"
        dialog = self._dialog(employer)
        self._save(dialog, "prevzeti.pdf", content, received_on=date(2026, 11, 18))

        stored_company = supplier_risk_service.list_companies()[0]
        self.assertEqual(stored_company.id, company.id)
        self.assertEqual(stored_company.name, "Uložený název")
        self.assertEqual(stored_company.ico, "87654321")
        refreshed = coordination_employer_service.get_by_id(employer.id)
        self.assertEqual(refreshed.ico, "87 654 321")
        self.assertEqual(refreshed.company_name, "Alfa stavby")

        documents = supplier_risk_service.list_company_documents(company.id)
        self.assertEqual(len(documents), 1)
        document = documents[0]
        self.assertEqual(document.filename, "prevzeti.pdf")
        self.assertIsNone(document.prepared_on)
        self.assertEqual(document.received_on, date(2026, 11, 18))
        self.assertEqual(document.note, "")
        self.assertEqual(document.attachment_id, 0)
        self.assertEqual(self._global_attachment_count(), 0)
        self.assertEqual(self._link_count(), 1)
        receipt = coordination_risk_receipt_service.get_for_employer(employer.id)
        stored_path = coordination_attachment_service.resolve_path(
            coordination_attachment_service.get_by_id(receipt.attachment_id)
        )
        self.assertEqual(stored_path.read_bytes(), content)
        self.assertEqual(
            [path.name for path in stored_path.parent.iterdir() if path.is_file()].count(
                "prevzeti.pdf"
            ),
            1,
        )
        self.assertEqual(receipt.received_on, date(2026, 11, 18))
        self.assertEqual(receipt.receipt_method, RISK_RECEIPT_METHOD_EMAIL)
        self.assertEqual(receipt.note, "")
        current_agreement = coordination_risk_submission_service.get_for_employer(
            employer.id
        )
        self.assertEqual(current_agreement.id, agreement.id)
        self.assertEqual(current_agreement.note, "původní dohoda")
        self.assertEqual(current_agreement.risks_text, "text dohody")
        self.assertEqual(current_agreement.submission_date, date(2026, 3, 1))
        self.assertEqual(dialog.operational_status.text(), "Následně převzato")
        self.assertEqual(self._messages, ["Změny byly úspěšně uloženy."])

    def test_unknown_supplier_is_created_from_coordination_name(self) -> None:
        employer = self._employer(ico="12 345 678", name="Nový dodavatel")
        dialog = self._dialog(employer)
        self._save(dialog, "novy.pdf", b"%PDF-1.4 novy\n", received_on=date(2026, 11, 18))
        companies = supplier_risk_service.list_companies()
        self.assertEqual(
            [(item.name, item.ico) for item in companies],
            [("Nový dodavatel", "12345678")],
        )
        refreshed = coordination_employer_service.get_by_id(employer.id)
        self.assertEqual(refreshed.ico, "12 345 678")
        document = supplier_risk_service.list_company_documents(companies[0].id)[0]
        self.assertEqual(document.received_on, date(2026, 11, 18))
        self.assertIsNone(document.prepared_on)
        self.assertEqual(document.note, "")

    def test_catalog_opens_the_receipt_file(self) -> None:
        employer = self._employer(ico="87654321")
        content = b"%PDF-1.4 otevrit\n"
        dialog = self._dialog(employer)
        self._save(dialog, "otevrit.pdf", content, received_on=date(2026, 11, 18))
        document = supplier_risk_service.list_companies()
        row = supplier_risk_service.list_company_documents(document[0].id)[0]
        opened: dict[str, object] = {}

        def _open(path, parent=None, title=""):
            opened["path"] = Path(path)
            opened["title"] = title
            return True

        with patch(
            "moduly.rizeni_rizik.sluzby.supplier_risk_service.open_local_file",
            side_effect=_open,
        ):
            self.assertTrue(supplier_risk_service.open_document(row.id))
        receipt = coordination_risk_receipt_service.get_for_employer(employer.id)
        stored = coordination_attachment_service.resolve_path(
            coordination_attachment_service.get_by_id(receipt.attachment_id)
        )
        self.assertEqual(opened["path"], stored)
        self.assertEqual(opened["title"], "Dokument rizik")
        self.assertEqual(stored.read_bytes(), content)
        self.assertEqual(self._global_attachment_count(), 0)

    def test_repeated_save_does_not_duplicate(self) -> None:
        employer = self._employer(ico="87654321")
        dialog = self._dialog(employer)
        self._save(dialog, "jednou.pdf", b"%PDF-1.4 jednou\n", received_on=date(2026, 11, 18))
        first = supplier_risk_service.list_company_documents(
            supplier_risk_service.list_companies()[0].id
        )[0]
        self._save(dialog, None, b"", received_on=date(2026, 11, 18))
        documents = supplier_risk_service.list_company_documents(
            supplier_risk_service.list_companies()[0].id
        )
        self.assertEqual([item.id for item in documents], [first.id])
        self.assertEqual(self._document_count(), 1)
        self.assertEqual(self._link_count(), 1)
        self.assertEqual(
            coordination_risk_receipt_service.list_history(
                coordination_risk_receipt_service.get_for_employer(employer.id).id
            ),
            [],
        )

    def test_new_attachment_keeps_original_document_and_history(self) -> None:
        employer = self._employer(ico="87654321", name="Alfa stavby")
        submission = coordination_risk_submission_service.save_submission(
            employer.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_EMAIL,
            submission_date=date.today() + timedelta(days=7),
            expected_email="rizika@example.com",
            note="původní dohoda",
        )
        dialog = self._dialog(employer)
        self._save(
            dialog,
            "prvni.pdf",
            b"%PDF-1.4 prvni\n",
            received_on=date(2026, 11, 18),
            note="první záznam",
        )
        first_receipt = coordination_risk_receipt_service.get_for_employer(employer.id)
        first_attachment_id = first_receipt.attachment_id
        first_document = supplier_risk_service.list_company_documents(
            supplier_risk_service.list_companies()[0].id
        )[0]
        self.assertTrue(task_service.get_task_by_id(submission.task_id).completed)

        self._save(
            dialog,
            "druhy.pdf",
            b"%PDF-1.4 druhy\n",
            received_on=date(2026, 11, 20),
            note="oprava",
        )
        documents = supplier_risk_service.list_company_documents(
            supplier_risk_service.list_companies()[0].id
        )
        self.assertEqual(
            sorted(item.filename for item in documents),
            ["druhy.pdf", "prvni.pdf"],
        )
        kept = next(item for item in documents if item.id == first_document.id)
        self.assertEqual(kept.filename, "prvni.pdf")
        self.assertEqual(kept.received_on, date(2026, 11, 18))
        self.assertEqual(kept.coordination_attachment_id, first_attachment_id)
        first_file = coordination_attachment_service.get_by_id(first_attachment_id)
        self.assertEqual(
            coordination_attachment_service.resolve_path(first_file).read_bytes(),
            b"%PDF-1.4 prvni\n",
        )
        self.assertTrue(first_file.active)
        receipt = coordination_risk_receipt_service.get_for_employer(employer.id)
        self.assertEqual(receipt.received_on, date(2026, 11, 20))
        self.assertEqual(receipt.note, "oprava")
        self.assertNotEqual(receipt.attachment_id, first_attachment_id)
        history = coordination_risk_receipt_service.list_history(receipt.id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].attachment_id_before, first_attachment_id)
        self.assertEqual(history[0].attachment_id_after, receipt.attachment_id)
        self.assertEqual(history[0].note_before, "první záznam")
        self.assertEqual(history[0].note_after, "oprava")
        self.assertEqual(self._document_count(), 2)
        self.assertEqual(self._link_count(), 2)
        self.assertEqual(self._global_attachment_count(), 0)
        self.assertTrue(task_service.get_task_by_id(submission.task_id).completed)

    def test_catalog_failure_keeps_receipt_history_and_task(self) -> None:
        employer = self._employer(ico="87654321", name="Alfa stavby")
        submission = coordination_risk_submission_service.save_submission(
            employer.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_EMAIL,
            submission_date=date.today() + timedelta(days=7),
            expected_email="rizika@example.com",
        )
        dialog = self._dialog(employer)
        with patch(
            "moduly.koordinace_bozp.sluzby.coordination_supplier_risk_link_service._insert_catalog_document_and_link",
            side_effect=RuntimeError("databáze"),
        ):
            self._save(
                dialog,
                "selhani.pdf",
                b"%PDF-1.4 selhani\n",
                received_on=date(2026, 11, 18),
                note="uložené převzetí",
            )
        self.assertEqual(self._messages, [CATALOG_RECEIPT_REGISTRATION_FAILED_MESSAGE])
        self.assertIn("Následné převzetí rizik bylo uloženo.", self._messages[0])
        self.assertIn("Zápis dokumentu do katalogu", self._messages[0])
        receipt = coordination_risk_receipt_service.get_for_employer(employer.id)
        self.assertEqual(receipt.note, "uložené převzetí")
        self.assertEqual(receipt.received_on, date(2026, 11, 18))
        self.assertIsNotNone(receipt.attachment_id)
        self.assertTrue(
            coordination_attachment_service.resolve_path(
                coordination_attachment_service.get_by_id(receipt.attachment_id)
            ).is_file()
        )
        self.assertTrue(task_service.get_task_by_id(submission.task_id).completed)
        self.assertEqual(supplier_risk_service.list_companies(), [])
        self.assertEqual(self._document_count(), 0)
        self.assertEqual(self._link_count(), 0)

        self._save(
            dialog,
            None,
            b"",
            received_on=date(2026, 11, 18),
            note="uložené převzetí",
        )
        self.assertEqual(self._document_count(), 1)
        with patch(
            "moduly.koordinace_bozp.sluzby.coordination_supplier_risk_link_service._insert_catalog_document_and_link",
            side_effect=RuntimeError("databáze"),
        ):
            self._save(
                dialog,
                "oprava.pdf",
                b"%PDF-1.4 oprava\n",
                received_on=date(2026, 11, 21),
                note="oprava po výpadku",
            )
        self.assertEqual(self._messages, [CATALOG_RECEIPT_REGISTRATION_FAILED_MESSAGE])
        history = coordination_risk_receipt_service.list_history(receipt.id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].note_after, "oprava po výpadku")
        self.assertEqual(self._document_count(), 1)
        self.assertEqual(
            supplier_risk_service.list_company_documents(
                supplier_risk_service.list_companies()[0].id
            )[0].filename,
            "selhani.pdf",
        )
        corrected = coordination_risk_receipt_service.get_for_employer(employer.id)
        self.assertEqual(corrected.note, "oprava po výpadku")
        self.assertTrue(task_service.get_task_by_id(submission.task_id).completed)

    def test_appendix_b_keeps_agreement_catalog_and_receipt_apart(self) -> None:
        employer = self._employer(ico="87654321", name="Alfa stavby")
        coordination_risk_submission_service.save_submission(
            employer.id,
            submission_method=RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
            submission_date=date(2026, 3, 1),
            note="původní dohoda",
            risks_text="text dohody",
        )
        dialog = self._dialog(employer)
        self._save(
            dialog,
            "protokol.pdf",
            b"%PDF-1.4 protokol\n",
            received_on=date(2026, 11, 18),
            note="poznámka převzetí se netiskne",
        )
        built = coordination_protocol_builder.build(
            employer.coordination_id,
            today=date(2026, 11, 5),
        )
        text = "\n".join(
            render_blocks_to_plain_lines(built.protocol_data["document"]["blocks"])
        )
        agreement_at = text.index("text dohody")
        catalog_at = text.index(PROTOCOL_CATALOG_DOCUMENTS_HEADING)
        receipt_at = text.index(PROTOCOL_SUBSEQUENT_RECEIPT_HEADING)
        self.assertLess(agreement_at, catalog_at)
        self.assertLess(catalog_at, receipt_at)
        self.assertIn("původní dohoda", text)
        self.assertIn("protokol.pdf, převzato 18.11.2026", text)
        self.assertIn(
            "Následné převzetí rizik: 18.11.2026, E-mail, protokol.pdf",
            text,
        )
        self.assertNotIn("poznámka převzetí se netiskne", text)
        self.assertNotIn("zpracováno", text)

    def test_same_attachment_date_correction_updates_only_that_document(self) -> None:
        employer = self._employer(ico="87654321", name="Alfa stavby")
        company = supplier_risk_service.create_company(name="Alfa stavby", ico="87654321")
        other = supplier_risk_service.add_company_document(
            company.id,
            received_on=date(2026, 1, 15),
            prepared_on=date(2026, 1, 2),
            note="jiný dokument",
            source_path=str(_pdf("jiny.pdf", b"%PDF-1.4 jiny\n")),
        )
        submission = coordination_risk_submission_service.save_submission(
            employer.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_EMAIL,
            submission_date=date.today() + timedelta(days=7),
            expected_email="rizika@example.com",
            note="původní dohoda",
            risks_text="text dohody",
        )
        dialog = self._dialog(employer)
        self._save(
            dialog,
            "retezec.pdf",
            b"%PDF-1.4 retezec\n",
            received_on=date(2026, 11, 18),
        )
        before_links = self._link_count()
        before_documents = self._document_count()

        self._save(dialog, None, b"", received_on=date(2026, 11, 25))

        documents = {
            item.id: item
            for item in supplier_risk_service.list_company_documents(company.id)
        }
        receipt = coordination_risk_receipt_service.get_for_employer(employer.id)
        updated = next(
            item
            for item in documents.values()
            if item.coordination_attachment_id == receipt.attachment_id
        )
        self.assertEqual(updated.received_on, date(2026, 11, 25))
        self.assertIsNone(updated.prepared_on)
        self.assertEqual(updated.note, "")
        self.assertEqual(updated.filename, "retezec.pdf")
        untouched = documents[other.id]
        self.assertEqual(untouched.received_on, date(2026, 1, 15))
        self.assertEqual(untouched.prepared_on, date(2026, 1, 2))
        self.assertEqual(untouched.note, "jiný dokument")
        self.assertEqual(self._document_count(), before_documents)
        self.assertEqual(self._link_count(), before_links)
        self.assertEqual(receipt.received_on, date(2026, 11, 25))
        history = coordination_risk_receipt_service.list_history(receipt.id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].received_on_before, date(2026, 11, 18))
        self.assertEqual(history[0].received_on_after, date(2026, 11, 25))
        self.assertEqual(history[0].attachment_id_before, receipt.attachment_id)
        self.assertEqual(history[0].attachment_id_after, receipt.attachment_id)
        agreement = coordination_risk_submission_service.get_for_employer(employer.id)
        self.assertEqual(agreement.id, submission.id)
        self.assertEqual(agreement.note, "původní dohoda")
        self.assertEqual(agreement.risks_text, "text dohody")
        self.assertEqual(
            agreement.submission_method,
            RISK_SUBMISSION_STATUS_WILL_EMAIL,
        )
        self.assertTrue(task_service.get_task_by_id(submission.task_id).completed)
        self.assertEqual(self._messages, ["Změny byly úspěšně uloženy."])

    def test_catalog_date_update_failure_keeps_receipt_correction(self) -> None:
        employer = self._employer(ico="87654321", name="Alfa stavby")
        submission = coordination_risk_submission_service.save_submission(
            employer.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_EMAIL,
            submission_date=date.today() + timedelta(days=7),
            expected_email="rizika@example.com",
            note="původní dohoda",
            risks_text="text dohody",
        )
        dialog = self._dialog(employer)
        self._save(
            dialog,
            "stejny.pdf",
            b"%PDF-1.4 stejny\n",
            received_on=date(2026, 11, 18),
        )
        with patch.object(
            supplier_risk_service,
            "update_document_details",
            side_effect=RuntimeError("katalog"),
        ):
            self._save(dialog, None, b"", received_on=date(2026, 11, 25))
        self.assertEqual(self._messages, [CATALOG_RECEIPT_REGISTRATION_FAILED_MESSAGE])
        receipt = coordination_risk_receipt_service.get_for_employer(employer.id)
        self.assertEqual(receipt.received_on, date(2026, 11, 25))
        document = supplier_risk_service.list_company_documents(
            supplier_risk_service.list_companies()[0].id
        )[0]
        self.assertEqual(document.received_on, date(2026, 11, 18))
        self.assertEqual(document.coordination_attachment_id, receipt.attachment_id)
        self.assertEqual(self._document_count(), 1)
        self.assertEqual(self._link_count(), 1)
        history = coordination_risk_receipt_service.list_history(receipt.id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].received_on_after, date(2026, 11, 25))
        agreement = coordination_risk_submission_service.get_for_employer(employer.id)
        self.assertEqual(agreement.note, "původní dohoda")
        self.assertEqual(agreement.risks_text, "text dohody")
        self.assertTrue(task_service.get_task_by_id(submission.task_id).completed)

    def test_invalid_and_ambiguous_ico_leave_catalog_unchanged(self) -> None:
        missing = self._employer(ico="", name="Bez IČO")
        invalid = self._employer(ico="AB123456", name="Špatné IČO")
        ambiguous = self._employer(ico="555", name="Nejednoznačný")
        now = datetime.now()
        repository = SupplierRiskRepository()
        repository.add_company(
            SupplierRiskCompany(name="První zápis", ico="555", created_at=now, updated_at=now)
        )
        repository.add_company(
            SupplierRiskCompany(
                name="Druhý zápis",
                ico="00000555",
                created_at=now,
                updated_at=now,
            )
        )
        before = [(item.name, item.ico) for item in supplier_risk_service.list_companies()]
        for employer, filename in (
            (missing, "chybi.pdf"),
            (invalid, "neplatne.pdf"),
            (ambiguous, "nejednoznacne.pdf"),
        ):
            dialog = self._dialog(employer)
            self._save(dialog, filename, b"%PDF-1.4 x\n", received_on=date(2026, 11, 18))
            self.assertEqual(self._messages, ["Změny byly úspěšně uloženy."])
            receipt = coordination_risk_receipt_service.get_for_employer(employer.id)
            result = coordination_supplier_risk_link_service.register_handed_attachment(
                employer.id,
                receipt.attachment_id,
            )
            self.assertEqual(result.status, CATALOG_REGISTRATION_SKIPPED)
        self.assertEqual(
            [(item.name, item.ico) for item in supplier_risk_service.list_companies()],
            before,
        )
        self.assertEqual(self._document_count(), 0)
        self.assertEqual(self._link_count(), 0)

    def _employer(self, *, ico: str, name: str = "Alfa stavby") -> CoordinationEmployer:
        coordination = bozp_coordination_service.create_coordination(
            subject=f"Koordinace {name} {ico}",
            meeting_date=date(2026, 11, 5),
        )
        return coordination_employer_service.add_participant(
            coordination.id,
            company_name=name,
            ico=ico,
            abbreviation="ALF",
        )

    def _dialog(self, employer: CoordinationEmployer) -> CoordinationRiskReceiptDialog:
        dialog = CoordinationRiskReceiptDialog(None, coordination_id=employer.coordination_id)
        dialog.employer_combo.setCurrentIndex(
            dialog.employer_combo.findData(employer.id)
        )
        return dialog

    def _save(
        self,
        dialog: CoordinationRiskReceiptDialog,
        filename: str | None,
        content: bytes,
        *,
        received_on: date,
        note: str = "",
    ) -> None:
        dialog.received_on.set_date_value(received_on)
        dialog.receipt_method.setCurrentIndex(
            dialog.receipt_method.findData(RISK_RECEIPT_METHOD_EMAIL)
        )
        dialog.note.setPlainText(note)
        if filename:
            dialog._pending_path = str(_pdf(filename, content))
        self._messages = []
        with patch(
            "moduly.koordinace_bozp.ui.coordination_risk_receipt_dialog._exec_message_box",
            side_effect=self._capture,
        ):
            self.assertTrue(dialog.save_receipt())

    def _capture(self, box: QMessageBox) -> int:
        self._messages.append(box.text())
        return int(QMessageBox.StandardButton.Ok)

    def _global_attachment_count(self) -> int:
        with get_session() as session:
            return int(session.scalar(select(func.count()).select_from(Attachment)) or 0)

    def _document_count(self) -> int:
        with get_session() as session:
            return int(
                session.scalar(select(func.count()).select_from(SupplierRiskDocument)) or 0
            )

    def _link_count(self) -> int:
        with get_session() as session:
            return int(
                session.scalar(
                    select(func.count()).select_from(CoordinationSupplierRiskLink)
                )
                or 0
            )


if __name__ == "__main__":
    unittest.main()
