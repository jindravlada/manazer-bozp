"""Fáze C3/2 – odkazy na dokumenty katalogu v koordinaci a příloze B."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QApplication, QHeaderView, QMessageBox
from sqlalchemy import delete, func, select

_TMP = Path(tempfile.mkdtemp(prefix="coord-catalog-links-c3-"))
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
        ATTACHMENT_TYPE_CONTRACTOR_RISKS,
        PROTOCOL_CATALOG_DOCUMENTS_HEADING,
        PROTOCOL_SUBSEQUENT_RECEIPT_HEADING,
        PROTOCOL_WARNING_RISKS_WITHOUT_ATTACHMENT,
        RISK_RECEIPT_METHOD_EMAIL,
        RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
        RISK_SUBMISSION_STATUS_LABELS,
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
        CATALOG_ASSIGNMENT_REFUSED_MESSAGE,
        SUPPLIER_APPROVAL_REQUIRED_MESSAGE,
        CoordinationSupplierRiskLinkError,
        coordination_supplier_risk_link_service,
    )
    from moduly.koordinace_bozp.ui.coordination_catalog_documents_dialog import (
        CoordinationCatalogDocumentsDialog,
    )
    from moduly.koordinace_bozp.ui.coordination_risk_submissions_tab import (
        CoordinationRiskSubmissionsTab,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.modely.supplier_risk import (
        SupplierRiskCompany,
        SupplierRiskDocument,
    )
    from moduly.rizeni_rizik.repository.supplier_risk_repository import (
        SupplierRiskRepository,
    )
    from moduly.rizeni_rizik.sluzby.supplier_risk_service import (
        SUPPLIER_CATALOG_MATCH_AMBIGUOUS,
        SUPPLIER_CATALOG_MATCH_INVALID,
        SUPPLIER_CATALOG_MATCH_NONE,
        SUPPLIER_CATALOG_MATCH_ONE,
        supplier_risk_service,
    )


def _pdf(name: str, content: bytes) -> Path:
    path = _TMP / name
    path.write_bytes(content)
    return path


class CoordinationCatalogLinksC3Test(unittest.TestCase):
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
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.commit()
        settings_service.save_employer(
            ico="11111111",
            name="Hlavní firma s.r.o.",
            address="Praha",
            nace="",
        )

    def test_confirm_one_and_several_documents(self) -> None:
        employer = self._employer(ico="87 654 321")
        first, second = self._two_documents()
        submission = coordination_risk_submission_service.save_submission(
            employer.id,
            submission_method=RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
            note="původní dohoda",
            risks_text="text dohody",
        )
        before_path = first.stored_path
        before_attachments = self._attachment_count()

        dialog = CoordinationCatalogDocumentsDialog(employer.id)
        self._select_rows(dialog, [0])
        self.assertFalse(dialog.use_button.isEnabled())
        dialog.confirm_selected()
        self.assertEqual(
            coordination_supplier_risk_link_service.list_for_employer(employer.id),
            [],
        )

        dialog.approval_checkbox.setChecked(True)
        self.assertTrue(dialog.use_button.isEnabled())
        dialog.confirm_selected()
        linked = coordination_supplier_risk_link_service.list_for_employer(employer.id)
        self.assertEqual([item.document_id for item in linked], [first.id])

        dialog = CoordinationCatalogDocumentsDialog(employer.id)
        self._select_rows(dialog, [0, 1])
        dialog.approval_checkbox.setChecked(True)
        dialog.confirm_selected()
        linked = coordination_supplier_risk_link_service.list_for_employer(employer.id)
        self.assertEqual(
            [item.document_id for item in linked],
            [first.id, second.id],
        )
        self.assertEqual(self._attachment_count(), before_attachments)
        refreshed = supplier_risk_service.list_company_documents(
            supplier_risk_service.find_catalog_company_by_ico("87654321").company_id
        )
        stored = next(item for item in refreshed if item.id == first.id)
        self.assertEqual(stored.stored_path, before_path)
        self.assertEqual(stored.attachment_id, first.attachment_id)
        agreement = coordination_risk_submission_service.get_for_employer(employer.id)
        self.assertEqual(agreement.id, submission.id)
        self.assertEqual(agreement.note, "původní dohoda")
        self.assertEqual(agreement.risks_text, "text dohody")
        self.assertEqual(
            agreement.submission_method,
            RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
        )

    def test_refusal_and_missing_approval_write_nothing(self) -> None:
        employer = self._employer(ico="87654321")
        document, _second = self._two_documents()
        dialog = CoordinationCatalogDocumentsDialog(employer.id)
        self._select_rows(dialog, [0])
        dialog.reject()
        self.assertEqual(
            coordination_supplier_risk_link_service.list_for_employer(employer.id),
            [],
        )
        with self.assertRaises(CoordinationSupplierRiskLinkError) as raised:
            coordination_supplier_risk_link_service.confirm_documents(
                employer.id,
                [document.id],
                supplier_approved=False,
            )
        self.assertEqual(str(raised.exception), SUPPLIER_APPROVAL_REQUIRED_MESSAGE)
        self.assertEqual(
            coordination_supplier_risk_link_service.list_for_employer(employer.id),
            [],
        )
        self.assertEqual(len(supplier_risk_service.list_companies()), 1)

    def test_duplicate_confirmation_keeps_single_link(self) -> None:
        employer = self._employer(ico="87654321")
        document, _second = self._two_documents()
        coordination_supplier_risk_link_service.confirm_documents(
            employer.id,
            [document.id, document.id],
            supplier_approved=True,
        )
        coordination_supplier_risk_link_service.confirm_documents(
            employer.id,
            [document.id],
            supplier_approved=True,
        )
        linked = coordination_supplier_risk_link_service.list_for_employer(employer.id)
        self.assertEqual([item.document_id for item in linked], [document.id])

    def test_open_document_writes_nothing(self) -> None:
        employer = self._employer(ico="87654321")
        document, _second = self._two_documents()
        dialog = CoordinationCatalogDocumentsDialog(employer.id)
        self._select_rows(dialog, [0])
        self.assertTrue(dialog.open_button.isEnabled())
        with patch(
            "moduly.koordinace_bozp.ui.coordination_catalog_documents_dialog"
            ".supplier_risk_service.open_document",
            return_value=True,
        ) as opened:
            dialog.open_selected()
        opened.assert_called_once_with(document.id, parent=dialog)
        self.assertEqual(
            coordination_supplier_risk_link_service.list_for_employer(employer.id),
            [],
        )
        self.assertEqual(len(supplier_risk_service.list_company_documents(
            document.company_id
        )), 2)

    def test_remove_link_keeps_catalog_and_other_coordination(self) -> None:
        first_employer = self._employer(ico="87654321", name="První dodavatel")
        second_coordination = bozp_coordination_service.create_coordination(
            subject="Druhá koordinace",
            meeting_date=date(2026, 11, 6),
        )
        second_employer = coordination_employer_service.add_participant(
            second_coordination.id,
            company_name="Druhý zápis",
            ico="87654321",
            abbreviation="DRU",
        )
        document, _second = self._two_documents()
        for employer in (first_employer, second_employer):
            coordination_supplier_risk_link_service.confirm_documents(
                employer.id,
                [document.id],
                supplier_approved=True,
            )
        dialog = CoordinationCatalogDocumentsDialog(first_employer.id)
        self._select_rows(dialog, [0])
        with patch(
            "moduly.koordinace_bozp.ui.coordination_catalog_documents_dialog"
            "._exec_message_box",
            return_value=int(QMessageBox.StandardButton.No),
        ):
            dialog.remove_selected()
        self.assertEqual(
            len(
                coordination_supplier_risk_link_service.list_for_employer(
                    first_employer.id
                )
            ),
            1,
        )
        with patch(
            "moduly.koordinace_bozp.ui.coordination_catalog_documents_dialog"
            "._exec_message_box",
            return_value=int(QMessageBox.StandardButton.Yes),
        ):
            dialog.remove_selected()
        self.assertEqual(
            coordination_supplier_risk_link_service.list_for_employer(
                first_employer.id
            ),
            [],
        )
        remaining = coordination_supplier_risk_link_service.list_for_employer(
            second_employer.id
        )
        self.assertEqual([item.document_id for item in remaining], [document.id])
        self.assertIsNotNone(supplier_risk_service.list_company_documents(
            document.company_id
        ))
        self.assertEqual(
            len(supplier_risk_service.list_company_documents(document.company_id)),
            2,
        )

    def test_ambiguous_and_invalid_ico_assign_nothing(self) -> None:
        SupplierRiskRepository().add_company(
            SupplierRiskCompany(name="Stará", ico="555")
        )
        SupplierRiskRepository().add_company(
            SupplierRiskCompany(name="Nová", ico="00000555")
        )
        ambiguous = self._employer(ico="555", name="Nejednoznačný")
        invalid = coordination_employer_service.add_participant(
            ambiguous.coordination_id,
            company_name="Neplatné IČO",
            ico="12AB",
            abbreviation="NEP",
        )
        missing = coordination_employer_service.add_participant(
            ambiguous.coordination_id,
            company_name="Bez shody",
            ico="12345678",
            abbreviation="BEZ",
        )
        self.assertEqual(
            coordination_supplier_risk_link_service.offer_for_employer(
                ambiguous.id
            ).status,
            SUPPLIER_CATALOG_MATCH_AMBIGUOUS,
        )
        self.assertEqual(
            coordination_supplier_risk_link_service.offer_for_employer(
                invalid.id
            ).status,
            SUPPLIER_CATALOG_MATCH_INVALID,
        )
        self.assertEqual(
            coordination_supplier_risk_link_service.offer_for_employer(
                missing.id
            ).status,
            SUPPLIER_CATALOG_MATCH_NONE,
        )
        tab = CoordinationRiskSubmissionsTab(None, ambiguous.coordination_id)
        for employer in (ambiguous, invalid, missing):
            tab.employer_combo.setCurrentIndex(tab.employer_combo.findData(employer.id))
            self.assertFalse(tab.catalog_documents_btn.isEnabled())
            self.assertTrue(tab.add_attachment_btn.isEnabled())
            with self.assertRaises(CoordinationSupplierRiskLinkError) as raised:
                coordination_supplier_risk_link_service.confirm_documents(
                    employer.id,
                    [1],
                    supplier_approved=True,
                )
            self.assertEqual(str(raised.exception), CATALOG_ASSIGNMENT_REFUSED_MESSAGE)
        self.assertEqual(self._link_count(), 0)
        self.assertEqual(len(supplier_risk_service.list_companies()), 2)

    def test_catalog_table_gives_remaining_width_to_document_name(self) -> None:
        employer = self._employer(ico="87654321")
        self._two_documents()
        dialog = CoordinationCatalogDocumentsDialog(employer.id)
        dialog.show()
        QApplication.processEvents()
        header = dialog.table.horizontalHeader()
        self.assertFalse(header.stretchLastSection())
        self.assertEqual(
            header.sectionResizeMode(0),
            QHeaderView.ResizeMode.Stretch,
        )
        for column in (1, 2, 3):
            self.assertEqual(
                header.sectionResizeMode(column),
                QHeaderView.ResizeMode.Fixed,
            )
        metrics = header.fontMetrics()
        self.assertGreaterEqual(
            dialog.table.columnWidth(1),
            metrics.horizontalAdvance("Datum zpracování"),
        )
        self.assertGreaterEqual(
            dialog.table.columnWidth(1),
            metrics.horizontalAdvance("00.00.0000"),
        )
        self.assertGreaterEqual(
            dialog.table.columnWidth(2),
            metrics.horizontalAdvance("Datum převzetí"),
        )
        self.assertGreaterEqual(
            dialog.table.columnWidth(3),
            metrics.horizontalAdvance("Použito"),
        )
        self.assertGreaterEqual(
            dialog.table.columnWidth(3),
            metrics.horizontalAdvance("Ano"),
        )
        self.assertLess(dialog.table.columnWidth(3), dialog.table.columnWidth(1))
        prepared = dialog.table.columnWidth(1)
        received = dialog.table.columnWidth(2)
        used = dialog.table.columnWidth(3)
        document = dialog.table.columnWidth(0)
        dialog.resize(dialog.width() + 280, dialog.height())
        QApplication.processEvents()
        self.assertGreater(dialog.table.columnWidth(0), document)
        self.assertEqual(dialog.table.columnWidth(1), prepared)
        self.assertEqual(dialog.table.columnWidth(2), received)
        self.assertEqual(dialog.table.columnWidth(3), used)
        self.assertGreater(dialog.table.columnWidth(0), dialog.table.columnWidth(3))
        dialog.close()

    def test_catalog_button_follows_match_and_edit_rules(self) -> None:
        employer = self._employer(ico="87654321")
        self._two_documents()
        tab = CoordinationRiskSubmissionsTab(None, employer.coordination_id)
        self.assertTrue(tab.catalog_documents_btn.isEnabled())
        self.assertTrue(tab.add_attachment_btn.isEnabled())
        tab.set_content_editable(False)
        self.assertFalse(tab.catalog_documents_btn.isEnabled())
        self.assertFalse(tab.add_attachment_btn.isEnabled())
        offer = coordination_supplier_risk_link_service.offer_for_employer(employer.id)
        self.assertEqual(offer.status, SUPPLIER_CATALOG_MATCH_ONE)
        self.assertEqual(self._link_count(), 0)

    def test_appendix_b_keeps_agreement_and_shows_documents_and_receipt(self) -> None:
        employer = self._employer(ico="87654321", name="Alfa stavby")
        first, second = self._two_documents()
        coordination_risk_submission_service.save_submission(
            employer.id,
            submission_method=RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
            note="původní dohoda",
            risks_text="text dohody",
        )
        coordination_supplier_risk_link_service.confirm_documents(
            employer.id,
            [first.id, second.id],
            supplier_approved=True,
        )
        coordination_risk_receipt_service.save_receipt(
            employer.id,
            received_on=date(2026, 11, 18),
            receipt_method=RISK_RECEIPT_METHOD_EMAIL,
            note="poznámka převzetí se netiskne",
        )
        built = coordination_protocol_builder.build(
            employer.coordination_id,
            today=date(2026, 11, 5),
        )
        lines = render_blocks_to_plain_lines(built.protocol_data["document"]["blocks"])
        text = "\n".join(lines)
        agreement_at = text.index("text dohody")
        catalog_at = text.index(PROTOCOL_CATALOG_DOCUMENTS_HEADING)
        receipt_at = text.index(PROTOCOL_SUBSEQUENT_RECEIPT_HEADING)
        self.assertLess(agreement_at, catalog_at)
        self.assertLess(catalog_at, receipt_at)
        self.assertIn("původní dohoda", text)
        self.assertIn(
            RISK_SUBMISSION_STATUS_LABELS[RISK_SUBMISSION_STATUS_EMAIL_BEFORE],
            text,
        )
        self.assertIn(
            f"• {first.filename}, zpracováno 02.02.2026, převzato 01.03.2026",
            text,
        )
        self.assertIn(f"• {second.filename}", text)
        self.assertNotIn(f"{second.filename}, zpracováno", text)
        self.assertNotIn(f"{second.filename}, převzato", text)
        self.assertIn("Následné převzetí rizik: 18.11.2026, E-mail", text)
        self.assertNotIn("poznámka převzetí se netiskne", text)
        self.assertNotIn("Následně převzato", text)
        agreement = coordination_risk_submission_service.get_for_employer(employer.id)
        self.assertEqual(agreement.risks_text, "text dohody")
        self.assertEqual(agreement.note, "původní dohoda")

    def test_catalog_link_satisfies_documentation_check(self) -> None:
        employer = self._employer(ico="87654321")
        document, _second = self._two_documents()
        coordination_risk_submission_service.save_submission(
            employer.id,
            submission_method=RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
            risks_text="text dohody",
        )
        missing = coordination_protocol_builder.build(
            employer.coordination_id,
            today=date(2026, 11, 5),
        )
        self.assertIn(
            PROTOCOL_WARNING_RISKS_WITHOUT_ATTACHMENT,
            [item.code for item in missing.warnings],
        )
        coordination_supplier_risk_link_service.confirm_documents(
            employer.id,
            [document.id],
            supplier_approved=True,
        )
        covered = coordination_protocol_builder.build(
            employer.coordination_id,
            today=date(2026, 11, 5),
        )
        self.assertNotIn(
            PROTOCOL_WARNING_RISKS_WITHOUT_ATTACHMENT,
            [item.code for item in covered.warnings],
        )
        self.assertEqual(
            coordination_attachment_service.list_for_employer(employer.id),
            [],
        )

    def test_direct_attachment_does_not_enter_catalog(self) -> None:
        employer = self._employer(ico="87654321")
        created = coordination_attachment_service.add_file(
            coordination_id=employer.coordination_id,
            coordination_employer_id=employer.id,
            source_path=str(_pdf("prime.pdf", b"%PDF-1.4 prime\n")),
            attachment_type=ATTACHMENT_TYPE_CONTRACTOR_RISKS,
        )
        self.assertIsNotNone(created.id)
        self.assertEqual(len(supplier_risk_service.list_companies()), 0)
        self.assertEqual(self._link_count(), 0)
        tab = CoordinationRiskSubmissionsTab(None, employer.coordination_id)
        self.assertFalse(tab.catalog_documents_btn.isEnabled())
        self.assertTrue(tab.add_attachment_btn.isEnabled())

    def _employer(self, *, ico: str, name: str = "Alfa stavby") -> CoordinationEmployer:
        coordination = bozp_coordination_service.create_coordination(
            subject=f"Koordinace {name}",
            meeting_date=date(2026, 11, 5),
        )
        return coordination_employer_service.add_participant(
            coordination.id,
            company_name=name,
            ico=ico,
            abbreviation="ALF",
        )

    def _two_documents(self):
        company = supplier_risk_service.create_company(
            name="Alfa stavby",
            ico="87654321",
        )
        first = supplier_risk_service.add_company_document(
            company.id,
            received_on=date(2026, 3, 1),
            prepared_on=date(2026, 2, 2),
            note="s daty",
            source_path=str(_pdf("prvni.pdf", b"%PDF-1.4 prvni\n")),
        )
        second = supplier_risk_service.add_company_document(
            company.id,
            received_on=None,
            prepared_on=None,
            note="bez dat",
            source_path=str(_pdf("druhy.pdf", b"%PDF-1.4 druhy\n")),
        )
        return first, second

    def _select_rows(self, dialog: CoordinationCatalogDocumentsDialog, rows: list[int]) -> None:
        dialog.table.clearSelection()
        selection = dialog.table.selectionModel()
        for row in rows:
            selection.select(
                dialog.table.model().index(row, 0),
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            )

    def _attachment_count(self) -> int:
        with get_session() as session:
            return int(session.scalar(select(func.count()).select_from(Attachment)) or 0)

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
