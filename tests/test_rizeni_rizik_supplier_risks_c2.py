"""Fáze C2/2 – seznam dodavatelů a detail firmy."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="supplier-risk-c2-"))
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
    from core.services.attachment_service import attachment_service
    from moduly.rizeni_rizik.constants import (
        SUPPLIER_RISK_COL_COMPANY,
        SUPPLIER_RISK_ENTITY_TYPE,
    )
    from moduly.rizeni_rizik.modely.supplier_risk import (
        SupplierRiskCompany,
        SupplierRiskDocument,
    )
    from moduly.rizeni_rizik.repository.supplier_risk_repository import (
        SupplierRiskRepository,
    )
    from moduly.rizeni_rizik.sluzby.supplier_risk_service import (
        DUPLICATE_SUPPLIER_ICO_MESSAGE,
        SupplierRiskError,
        supplier_risk_service,
    )
    from moduly.rizeni_rizik.ui.supplier_risk_company_dialog import (
        SupplierRiskCompanyDialog,
    )
    from moduly.rizeni_rizik.ui.supplier_risk_document_dialog import (
        SupplierRiskDocumentDialog,
    )
    from moduly.rizeni_rizik.ui.supplier_risk_documents_tab import (
        SupplierRiskDocumentsTab,
    )


def _pdf(name: str, content: bytes) -> Path:
    path = _TMP / name
    path.write_bytes(content)
    return path


def _file_bytes(attachment_id: int) -> bytes:
    attachment = attachment_service.repository.get_by_id(attachment_id)
    return attachment_service.resolve_path(attachment).read_bytes()


def _visible_names(tab: SupplierRiskDocumentsTab) -> list[str]:
    names = []
    for row in range(tab.table.rowCount()):
        if tab.table.isRowHidden(row):
            continue
        item = tab.table.item(row, SUPPLIER_RISK_COL_COMPANY)
        names.append("" if item is None else item.text())
    return names


class SupplierRiskC2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        with get_session() as session:
            session.execute(delete(SupplierRiskDocument))
            session.execute(delete(SupplierRiskCompany))
            session.execute(
                delete(Attachment).where(
                    Attachment.entity_type == SUPPLIER_RISK_ENTITY_TYPE
                )
            )
            session.commit()

    def test_one_supplier_with_several_documents_is_one_row(self):
        company = supplier_risk_service.create_company(name="Alfa stavby", ico="12345678")
        supplier_risk_service.add_company_document(
            company.id,
            received_on=date(2026, 1, 1),
            note="první",
            source_path=str(_pdf("alfa-1.pdf", b"alfa-1")),
        )
        supplier_risk_service.add_company_document(
            company.id,
            received_on=None,
            note="druhý",
            source_path=str(_pdf("alfa-2.pdf", b"alfa-2")),
        )
        supplier_risk_service.create_company(name="Beta montáže", ico="87654321")
        tab = SupplierRiskDocumentsTab()
        self.assertEqual(tab.new_btn.text(), "Nový dodavatel")
        self.assertEqual(tab.open_btn.text(), "Otevřít")
        self.assertTrue(tab.new_btn.isEnabled())
        self.assertFalse(tab.open_btn.isEnabled())
        self.assertEqual(tab.table.columnCount(), 2)
        self.assertEqual(
            [tab.table.horizontalHeaderItem(column).text() for column in range(2)],
            ["IČO", "Název firmy"],
        )
        self.assertEqual(tab.table.rowCount(), 2)
        self.assertEqual(len(supplier_risk_service.list_documents()), 2)
        self.assertEqual(sorted(_visible_names(tab)), ["Alfa stavby", "Beta montáže"])
        alfa_row = _visible_names(tab).index("Alfa stavby")
        tab.table.selectRow(alfa_row)
        self.assertTrue(tab.open_btn.isEnabled())
        tab.deleteLater()

    def test_search_by_name_and_ico(self):
        alfa = supplier_risk_service.create_company(name="Alfa stavby", ico="12345678")
        supplier_risk_service.add_company_document(
            alfa.id,
            received_on=None,
            note="tajná poznámka",
            source_path=str(_pdf("hledani.pdf", b"hledani")),
        )
        supplier_risk_service.create_company(name="Beta montáže", ico="87654321")
        tab = SupplierRiskDocumentsTab()
        tab.text_filter.search_edit.setText("stavby")
        self.assertEqual(_visible_names(tab), ["Alfa stavby"])
        tab.text_filter.search_edit.setText("87654321")
        self.assertEqual(_visible_names(tab), ["Beta montáže"])
        tab.text_filter.search_edit.setText("tajná")
        self.assertEqual(_visible_names(tab), [])
        tab.text_filter.search_edit.setText("")
        self.assertEqual(sorted(_visible_names(tab)), ["Alfa stavby", "Beta montáže"])
        tab.deleteLater()

    def test_create_company_without_document(self):
        with self.assertRaises(SupplierRiskError):
            supplier_risk_service.create_company(name="   ", ico="12345678")
        with self.assertRaises(SupplierRiskError):
            supplier_risk_service.create_company(name="Bez IČO", ico="   ")
        self.assertEqual(supplier_risk_service.list_companies(), [])

        dialog = SupplierRiskCompanyDialog()
        self.assertFalse(dialog.add_document_btn.isEnabled())
        self.assertFalse(dialog.edit_document_btn.isEnabled())
        self.assertFalse(dialog.open_document_btn.isEnabled())
        dialog.name.setText("  Nová firma  ")
        dialog.ico.setText(" 123 ")
        with patch.object(QMessageBox, "warning") as warning:
            dialog._save_identity()
        warning.assert_not_called()
        self.assertIsNotNone(dialog.company)
        self.assertEqual(dialog.company.name, "Nová firma")
        self.assertEqual(dialog.company.ico, "00000123")
        self.assertEqual(supplier_risk_service.list_documents(), [])
        self.assertEqual(len(supplier_risk_service.list_companies()), 1)
        self.assertTrue(dialog.add_document_btn.isEnabled())
        self.assertEqual(dialog.documents.rowCount(), 0)
        dialog.deleteLater()

    def test_add_several_documents(self):
        company = supplier_risk_service.create_company(name="Alfa", ico="12345678")
        missing = SupplierRiskDocumentDialog(company_id=company.id)
        with patch.object(QMessageBox, "warning") as warning:
            missing._save()
        self.assertNotEqual(missing.result(), QDialog.DialogCode.Accepted)
        self.assertIn("povinný", warning.call_args.args[2])
        self.assertEqual(supplier_risk_service.list_company_documents(company.id), [])

        first_dialog = SupplierRiskDocumentDialog(company_id=company.id)
        first_dialog.source_path = str(_pdf("prvni.pdf", b"prvni-soubor"))
        first_dialog.note.setPlainText("první")
        with patch.object(QMessageBox, "warning") as warning:
            first_dialog._save()
        warning.assert_not_called()
        self.assertEqual(first_dialog.result(), QDialog.DialogCode.Accepted)

        second_dialog = SupplierRiskDocumentDialog(company_id=company.id)
        second_dialog.source_path = str(_pdf("druhy.pdf", b"druhy-soubor"))
        second_dialog.received_on.set_date_value(date(2026, 4, 4))
        with patch.object(QMessageBox, "warning") as warning:
            second_dialog._save()
        warning.assert_not_called()

        documents = supplier_risk_service.list_company_documents(company.id)
        self.assertEqual(len(documents), 2)
        self.assertEqual(len(supplier_risk_service.list_companies()), 1)
        first = next(row for row in documents if row.note == "první")
        second = next(row for row in documents if row.note != "první")
        self.assertIsNone(first.received_on)
        self.assertEqual(second.received_on, date(2026, 4, 4))
        self.assertNotEqual(first.attachment_id, second.attachment_id)
        self.assertNotEqual(first.filename, second.filename)
        self.assertEqual(_file_bytes(first.attachment_id), b"prvni-soubor")
        self.assertEqual(_file_bytes(second.attachment_id), b"druhy-soubor")
        detail = SupplierRiskCompanyDialog(company=company)
        self.assertEqual(
            [detail.documents.horizontalHeaderItem(column).text() for column in range(4)],
            ["Dokument rizik", "Datum zpracování", "Datum převzetí", "Poznámka"],
        )
        self.assertEqual(detail.documents.rowCount(), 2)
        missing.deleteLater()
        first_dialog.deleteLater()
        second_dialog.deleteLater()
        detail.deleteLater()

    def test_edit_date_and_note_keeps_attachment(self):
        company = supplier_risk_service.create_company(name="Alfa", ico="12345678")
        first = supplier_risk_service.add_company_document(
            company.id,
            received_on=None,
            note="původní",
            source_path=str(_pdf("puvodni.pdf", b"puvodni-soubor")),
        )
        second = supplier_risk_service.add_company_document(
            company.id,
            received_on=date(2026, 2, 2),
            note="druhý",
            source_path=str(_pdf("druhy.pdf", b"druhy-soubor")),
        )
        updated = supplier_risk_service.update_document_details(
            first.id,
            received_on=date(2026, 5, 6),
            note="nová poznámka",
        )
        self.assertEqual(updated.attachment_id, first.attachment_id)
        self.assertEqual(updated.company_id, company.id)
        self.assertEqual(updated.received_on, date(2026, 5, 6))
        self.assertEqual(updated.note, "nová poznámka")
        self.assertEqual(_file_bytes(first.attachment_id), b"puvodni-soubor")

        edit = SupplierRiskDocumentDialog(document=second, company_id=company.id)
        self.assertFalse(edit.file_button.isEnabled())
        edit.source_path = str(_pdf("vymena.pdf", b"nesmi-se-ulozit"))
        edit.received_on.set_date_value(date(2026, 8, 9))
        edit.note.setPlainText("upraveno v dialogu")
        with patch.object(QMessageBox, "warning") as warning:
            edit._save()
        warning.assert_not_called()
        stored = {
            row.id: row
            for row in supplier_risk_service.list_company_documents(company.id)
        }
        self.assertEqual(set(stored), {first.id, second.id})
        self.assertEqual(stored[second.id].attachment_id, second.attachment_id)
        self.assertEqual(stored[second.id].received_on, date(2026, 8, 9))
        self.assertEqual(stored[second.id].note, "upraveno v dialogu")
        self.assertEqual(stored[second.id].filename, second.filename)
        self.assertEqual(_file_bytes(second.attachment_id), b"druhy-soubor")
        self.assertEqual(_file_bytes(first.attachment_id), b"puvodni-soubor")
        self.assertEqual(supplier_risk_service.get_company(company.id).ico, "12345678")
        edit.deleteLater()

    def test_open_existing_document(self):
        company = supplier_risk_service.create_company(name="Alfa", ico="27074358")
        created = supplier_risk_service.add_company_document(
            company.id,
            received_on=None,
            note="",
            source_path=str(_pdf("otevrit.pdf", b"obsah-dokumentu")),
        )
        with patch(
            "moduly.rizeni_rizik.sluzby.supplier_risk_service.open_local_file",
            return_value=True,
        ) as opened:
            self.assertTrue(supplier_risk_service.open_document(created.id))
        self.assertEqual(Path(opened.call_args.args[0]).read_bytes(), b"obsah-dokumentu")

        detail = SupplierRiskCompanyDialog(
            company=supplier_risk_service.get_company(company.id)
        )
        self.assertEqual(detail.documents.rowCount(), 1)
        detail.documents.selectRow(0)
        self.assertTrue(detail.open_document_btn.isEnabled())
        with patch(
            "moduly.rizeni_rizik.sluzby.supplier_risk_service.open_local_file",
            return_value=True,
        ) as opened:
            detail._open_document()
        self.assertEqual(Path(opened.call_args.args[0]).read_bytes(), b"obsah-dokumentu")
        detail.deleteLater()

    def test_company_without_ico_and_its_documents_remain(self):
        company = SupplierRiskRepository().add_company(
            SupplierRiskCompany(name="OGES", ico=None)
        )
        first = supplier_risk_service.add_company_document(
            company.id,
            received_on=date(2026, 1, 3),
            note="první dokument",
            source_path=str(_pdf("oges-1.pdf", b"oges-prvni")),
        )
        second = supplier_risk_service.add_company_document(
            company.id,
            received_on=None,
            note="druhý dokument",
            source_path=str(_pdf("oges-2.pdf", b"oges-druhy")),
        )
        tab = SupplierRiskDocumentsTab()
        self.assertEqual(_visible_names(tab), ["OGES"])
        self.assertEqual(tab.table.item(0, 0).text(), "—")
        self.assertEqual(tab.table.item(0, 1).text(), "OGES")
        detail = SupplierRiskCompanyDialog(
            company=supplier_risk_service.get_company(company.id)
        )
        self.assertEqual(detail.name.text(), "OGES")
        self.assertEqual(detail.ico.text(), "")
        filenames = {
            detail.documents.item(row, 0).text()
            for row in range(detail.documents.rowCount())
        }
        self.assertEqual(filenames, {"oges-1.pdf", "oges-2.pdf"})
        for row in range(detail.documents.rowCount()):
            detail.documents.selectRow(row)
            with patch(
                "moduly.rizeni_rizik.sluzby.supplier_risk_service.open_local_file",
                return_value=True,
            ) as opened:
                detail._open_document()
            self.assertTrue(Path(opened.call_args.args[0]).is_file())

        detail.name.setText("OGES nové")
        detail.ico.clear()
        with patch.object(QMessageBox, "warning") as warning:
            detail._save_identity()
        self.assertIn("IČO", warning.call_args.args[2])
        stored = supplier_risk_service.get_company(company.id)
        self.assertEqual(stored.name, "OGES")
        self.assertIsNone(stored.ico)
        documents = supplier_risk_service.list_company_documents(company.id)
        self.assertEqual({row.id for row in documents}, {first.id, second.id})
        self.assertEqual(_file_bytes(first.attachment_id), b"oges-prvni")
        self.assertEqual(_file_bytes(second.attachment_id), b"oges-druhy")

        filled = supplier_risk_service.update_company_identity(
            company.id,
            name="OGES",
            ico="5",
        )
        self.assertEqual(filled.ico, "00000005")
        kept = supplier_risk_service.list_company_documents(company.id)
        self.assertEqual({row.id for row in kept}, {first.id, second.id})
        self.assertEqual(
            {row.attachment_id for row in kept},
            {first.attachment_id, second.attachment_id},
        )
        self.assertEqual(_file_bytes(first.attachment_id), b"oges-prvni")
        self.assertEqual(_file_bytes(second.attachment_id), b"oges-druhy")
        tab.deleteLater()
        detail.deleteLater()

    def test_duplicate_ico_is_rejected(self):
        alfa = supplier_risk_service.create_company(name="Alfa", ico="11111111")
        alfa_document = supplier_risk_service.add_company_document(
            alfa.id,
            received_on=None,
            note="u alfy",
            source_path=str(_pdf("alfa.pdf", b"alfa-soubor")),
        )
        with self.assertRaises(SupplierRiskError) as duplicate:
            supplier_risk_service.create_company(name="Jiná Alfa", ico="11 111 111")
        self.assertEqual(str(duplicate.exception), DUPLICATE_SUPPLIER_ICO_MESSAGE)
        self.assertEqual(len(supplier_risk_service.list_companies()), 1)

        beta = supplier_risk_service.create_company(name="Beta", ico="22222222")
        beta_document = supplier_risk_service.add_company_document(
            beta.id,
            received_on=None,
            note="u bety",
            source_path=str(_pdf("beta.pdf", b"beta-soubor")),
        )
        with self.assertRaises(SupplierRiskError) as moved:
            supplier_risk_service.update_company_identity(
                beta.id,
                name="Beta sloučená",
                ico="11111111",
            )
        self.assertEqual(str(moved.exception), DUPLICATE_SUPPLIER_ICO_MESSAGE)
        self.assertEqual(supplier_risk_service.get_company(beta.id).name, "Beta")
        self.assertEqual(supplier_risk_service.get_company(beta.id).ico, "22222222")
        self.assertEqual(
            [row.id for row in supplier_risk_service.list_company_documents(alfa.id)],
            [alfa_document.id],
        )
        self.assertEqual(
            [row.id for row in supplier_risk_service.list_company_documents(beta.id)],
            [beta_document.id],
        )
        self.assertEqual(_file_bytes(alfa_document.attachment_id), b"alfa-soubor")
        self.assertEqual(_file_bytes(beta_document.attachment_id), b"beta-soubor")

        dialog = SupplierRiskCompanyDialog()
        dialog.name.setText("Gama")
        dialog.ico.setText("11111111")
        with patch.object(QMessageBox, "warning") as warning:
            dialog._save_identity()
        self.assertIsNone(dialog.company)
        self.assertEqual(warning.call_args.args[2], DUPLICATE_SUPPLIER_ICO_MESSAGE)
        self.assertEqual(len(supplier_risk_service.list_companies()), 2)
        dialog.deleteLater()

    def test_ares_fills_only_name_on_company_dialog(self):
        dialog = SupplierRiskCompanyDialog()
        dialog.name.setText("Ruční název")
        dialog.ico.setText("123")
        with patch(
            "moduly.rizeni_rizik.sluzby.supplier_risk_service.ares_service.find_by_ico",
            return_value={"ico": "123", "name": "ARES Firma", "address": "Ulice 1"},
        ) as find_by_ico:
            dialog._load_from_ares()
        find_by_ico.assert_called_once_with("00000123")
        self.assertEqual(dialog.name.text(), "ARES Firma")
        self.assertEqual(dialog.ico.text(), "123")
        self.assertIsNone(dialog.company)
        self.assertEqual(supplier_risk_service.list_companies(), [])

        dialog.name.setText("Původní název")
        with patch(
            "moduly.rizeni_rizik.sluzby.supplier_risk_service.ares_service.find_by_ico",
            return_value=None,
        ), patch.object(QMessageBox, "warning"):
            dialog._load_from_ares()
        self.assertEqual(dialog.name.text(), "Původní název")
        self.assertEqual(dialog.ico.text(), "123")
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
