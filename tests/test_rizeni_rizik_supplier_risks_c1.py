"""Fáze C1 – evidence rizik dodavatelů."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError

_TMP = Path(tempfile.mkdtemp(prefix="supplier-risk-c1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _table_columns,
        _table_indexes,
        initialize_database,
    )

    initialize_database()

    from core.database.session import engine, get_session
    from core.models.attachment import Attachment
    from core.services.attachment_service import attachment_service
    from moduly.rizeni_rizik.constants import (
        SUPPLIER_RISK_ENTITY_TYPE,
        SUPPLIER_RISK_TAB_TITLE,
    )
    from moduly.rizeni_rizik.modely.supplier_risk import (
        SupplierRiskCompany,
        SupplierRiskDocument,
    )
    from moduly.rizeni_rizik.sluzby.supplier_risk_service import (
        SupplierRiskError,
        normalize_supplier_ico,
        supplier_risk_search_matches,
        supplier_risk_service,
    )
    from moduly.rizeni_rizik.ui.rizeni_rizik_page import RizeniRizikPage
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


class SupplierRiskC1Test(unittest.TestCase):
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

    def test_fresh_database_has_supplier_tables(self):
        company_columns = _table_columns("supplier_risk_companies")
        document_columns = _table_columns("supplier_risk_documents")
        self.assertIn("name", company_columns)
        self.assertIn("ico", company_columns)
        with engine.connect() as connection:
            ico_column = next(
                row
                for row in connection.execute(
                    text("PRAGMA table_info(supplier_risk_companies)")
                )
                if row[1] == "ico"
            )
        self.assertEqual(ico_column[3], 0)
        self.assertIn("company_id", document_columns)
        self.assertIn("received_on", document_columns)
        self.assertIn("note", document_columns)
        self.assertIn("attachment_id", document_columns)
        self.assertIn(
            "uq_supplier_risk_companies_ico",
            _table_indexes("supplier_risk_companies"),
        )
        self.assertIn(
            "idx_supplier_risk_documents_company",
            _table_indexes("supplier_risk_documents"),
        )

    def test_existing_database_gains_tables_and_keeps_rows(self):
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS supplier_risk_documents"))
            connection.execute(text("DROP TABLE IF EXISTS supplier_risk_companies"))
            connection.execute(
                text(
                    "CREATE TABLE supplier_risk_companies ("
                    "id INTEGER PRIMARY KEY, "
                    "name VARCHAR(250) NOT NULL, "
                    "ico VARCHAR(20), "
                    "created_at DATETIME, "
                    "updated_at DATETIME)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO supplier_risk_companies (name, ico) "
                    "VALUES ('Původní firma', '555')"
                )
            )
        initialize_database()
        self.assertIn("attachment_id", _table_columns("supplier_risk_documents"))
        self.assertIn(
            "uq_supplier_risk_companies_ico",
            _table_indexes("supplier_risk_companies"),
        )
        companies = supplier_risk_service.list_companies()
        self.assertEqual([company.name for company in companies], ["Původní firma"])
        self.assertEqual(companies[0].ico, "555")
        with self.assertRaises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO supplier_risk_companies (name, ico) "
                        "VALUES ('Jiná firma', '555')"
                    )
                )
        initialize_database()
        self.assertEqual(
            [company.name for company in supplier_risk_service.list_companies()],
            ["Původní firma"],
        )

    def test_create_company_and_several_documents_without_replacing_files(self):
        first = _pdf("prvni.pdf", b"prvni-verze")
        second = _pdf("druha.pdf", b"druha-verze")
        created = supplier_risk_service.create_document(
            company_id=None,
            name=" Alfa s.r.o. ",
            ico=" 123 45 678 ",
            received_on=date(2026, 3, 1),
            note="první",
            source_path=str(first),
        )
        self.assertFalse(created.reused_existing_company)
        self.assertEqual(created.row.company_name, "Alfa s.r.o.")
        self.assertEqual(created.row.ico, "12345678")
        again = supplier_risk_service.create_document(
            company_id=created.row.company_id,
            name="Alfa s.r.o.",
            ico="12345678",
            received_on=None,
            note="",
            source_path=str(second),
        )
        self.assertFalse(again.reused_existing_company)
        self.assertEqual(again.row.company_id, created.row.company_id)
        self.assertIsNone(again.row.received_on)
        self.assertEqual(len(supplier_risk_service.list_companies()), 1)
        rows = supplier_risk_service.list_documents()
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(created.row.attachment_id, again.row.attachment_id)
        first_path = attachment_service.resolve_path(
            attachment_service.repository.get_by_id(created.row.attachment_id)
        )
        second_path = attachment_service.resolve_path(
            attachment_service.repository.get_by_id(again.row.attachment_id)
        )
        self.assertEqual(first_path.read_bytes(), b"prvni-verze")
        self.assertEqual(second_path.read_bytes(), b"druha-verze")
        stored = attachment_service.get_for_entity(
            SUPPLIER_RISK_ENTITY_TYPE,
            created.row.id,
        )
        self.assertEqual(len(stored), 1)

    def test_duplicate_ico_reuses_company_and_empty_ico_stays_separate(self):
        source = _pdf("ico.pdf", b"dokument")
        first = supplier_risk_service.create_document(
            company_id=None,
            name="Alfa",
            ico="11223344",
            received_on=None,
            note="",
            source_path=str(source),
        )
        reused = supplier_risk_service.create_document(
            company_id=None,
            name="Jiný název",
            ico="11 223 344",
            received_on=None,
            note="další",
            source_path=str(_pdf("ico-2.pdf", b"dalsi")),
        )
        self.assertTrue(reused.reused_existing_company)
        self.assertEqual(reused.row.company_id, first.row.company_id)
        self.assertEqual(reused.row.company_name, "Alfa")
        with self.assertRaises(SupplierRiskError) as missing_ico:
            supplier_risk_service.create_document(
                company_id=None,
                name="Alfa",
                ico="  ",
                received_on=None,
                note="",
                source_path=str(_pdf("bez-ica.pdf", b"bez")),
            )
        self.assertIn("IČO", str(missing_ico.exception))
        self.assertEqual(len(supplier_risk_service.list_companies()), 1)
        with self.assertRaises(SupplierRiskError):
            supplier_risk_service.create_document(
                company_id=None,
                name="   ",
                ico="999",
                received_on=None,
                note="",
                source_path=str(source),
            )
        with self.assertRaises(SupplierRiskError):
            supplier_risk_service.create_document(
                company_id=None,
                name="Bez souboru",
                ico=None,
                received_on=None,
                note="",
                source_path=str(_TMP / "chybi.pdf"),
            )

    def test_update_keeps_original_file_and_relinks_duplicate_ico(self):
        original = _pdf("puvodni.pdf", b"puvodni")
        created = supplier_risk_service.create_document(
            company_id=None,
            name="Alfa",
            ico="100",
            received_on=None,
            note="původní poznámka",
            source_path=str(original),
        )
        other = supplier_risk_service.create_document(
            company_id=None,
            name="Beta",
            ico="200",
            received_on=date(2026, 1, 2),
            note="",
            source_path=str(_pdf("beta.pdf", b"beta")),
        )
        updated = supplier_risk_service.update_document(
            created.row.id,
            company_id=created.row.company_id,
            name="Alfa upravená",
            ico="100",
            received_on=date(2026, 4, 5),
            note="nová poznámka",
        )
        self.assertEqual(updated.row.attachment_id, created.row.attachment_id)
        self.assertEqual(updated.row.company_name, "Alfa upravená")
        self.assertEqual(updated.row.received_on, date(2026, 4, 5))
        path = attachment_service.resolve_path(
            attachment_service.repository.get_by_id(created.row.attachment_id)
        )
        self.assertEqual(path.read_bytes(), b"puvodni")
        self.assertEqual(
            len(
                attachment_service.get_for_entity(
                    SUPPLIER_RISK_ENTITY_TYPE,
                    created.row.id,
                )
            ),
            1,
        )
        moved = supplier_risk_service.update_document(
            created.row.id,
            company_id=created.row.company_id,
            name="Alfa upravená",
            ico="200",
            received_on=None,
            note="přesun",
        )
        self.assertTrue(moved.reused_existing_company)
        self.assertEqual(moved.row.company_id, other.row.company_id)
        self.assertEqual(moved.row.company_name, "Beta")
        self.assertEqual(moved.row.attachment_id, created.row.attachment_id)
        names = {company.id: company.name for company in supplier_risk_service.list_companies()}
        self.assertEqual(names[created.row.company_id], "Alfa upravená")
        self.assertEqual(names[other.row.company_id], "Beta")

    def test_search_matches_only_company_name_and_ico(self):
        self.assertTrue(
            supplier_risk_search_matches(
                company_name="Alfa stavby",
                ico="12345678",
                query="alfa",
            )
        )
        self.assertTrue(
            supplier_risk_search_matches(
                company_name="Alfa stavby",
                ico="12345678",
                query="345",
            )
        )
        self.assertFalse(
            supplier_risk_search_matches(
                company_name="Alfa stavby",
                ico="12345678",
                query="poznamka",
            )
        )

    def test_open_document_uses_stored_attachment(self):
        created = supplier_risk_service.create_document(
            company_id=None,
            name="Alfa",
            ico="27074358",
            received_on=None,
            note="",
            source_path=str(_pdf("otevrit.pdf", b"obsah")),
        )
        with patch(
            "moduly.rizeni_rizik.sluzby.supplier_risk_service.open_local_file",
            return_value=True,
        ) as opened:
            self.assertTrue(supplier_risk_service.open_document(created.row.id))
        path = opened.call_args.args[0]
        self.assertTrue(Path(path).is_file())
        self.assertEqual(Path(path).read_bytes(), b"obsah")
        self.assertEqual(opened.call_args.kwargs["title"], "Dokument rizik")

    def test_tab_search_open_and_buttons(self):
        supplier_risk_service.create_document(
            company_id=None,
            name="Alfa",
            ico="111",
            received_on=None,
            note="tajná poznámka",
            source_path=str(_pdf("tab-a.pdf", b"a")),
        )
        supplier_risk_service.create_document(
            company_id=None,
            name="Beta",
            ico="222",
            received_on=date(2026, 5, 6),
            note="",
            source_path=str(_pdf("tab-b.pdf", b"b")),
        )
        tab = SupplierRiskDocumentsTab()
        self.assertTrue(tab.new_btn.isEnabled())
        self.assertFalse(tab.edit_btn.isEnabled())
        self.assertFalse(tab.open_btn.isEnabled())
        self.assertEqual(tab.table.columnCount(), 5)
        self.assertEqual(
            [tab.table.horizontalHeaderItem(column).text() for column in range(5)],
            ["Název firmy", "IČO", "Dokument rizik", "Datum převzetí", "Poznámka"],
        )
        tab.text_filter.search_edit.setText("222")
        self.assertEqual(tab.table.rowCount(), 2)
        hidden = [
            tab.table.isRowHidden(row) for row in range(tab.table.rowCount())
        ]
        self.assertEqual(hidden.count(False), 1)
        visible_row = hidden.index(False)
        self.assertEqual(tab.table.item(visible_row, 0).text(), "Beta")
        tab.text_filter.search_edit.setText("tajná")
        self.assertTrue(all(tab.table.isRowHidden(row) for row in range(2)))
        tab.text_filter.search_edit.setText("alfa")
        visible_row = next(
            row for row in range(2) if not tab.table.isRowHidden(row)
        )
        tab.table.selectRow(visible_row)
        self.assertTrue(tab.edit_btn.isEnabled())
        self.assertTrue(tab.open_btn.isEnabled())
        with patch(
            "moduly.rizeni_rizik.sluzby.supplier_risk_service.open_local_file",
            return_value=True,
        ) as opened:
            tab.open_document()
        self.assertEqual(Path(opened.call_args.args[0]).read_bytes(), b"a")
        tab.deleteLater()

    def test_dialog_creates_document_without_date_and_reuses_ico(self):
        dialog = SupplierRiskDocumentDialog()
        dialog.name.setText("Gama")
        dialog.ico.setText("333")
        dialog.source_path = str(_pdf("gama.pdf", b"gama"))
        dialog.file_name.setText("gama.pdf")
        with patch.object(QMessageBox, "warning"), patch.object(QMessageBox, "information"):
            dialog._save()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        rows = supplier_risk_service.list_documents()
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].received_on)
        self.assertEqual(rows[0].company_name, "Gama")
        self.assertEqual(rows[0].ico, "00000333")

        second = SupplierRiskDocumentDialog()
        second.company.setCurrentIndex(0)
        second.name.setText("Jiná Gama")
        second.ico.setText("333")
        second.source_path = str(_pdf("gama-2.pdf", b"gama2"))
        with patch.object(QMessageBox, "warning"), patch.object(
            QMessageBox, "information"
        ) as info:
            second._save()
        self.assertTrue(second.reused_existing_company)
        info.assert_called_once()
        self.assertEqual(len(supplier_risk_service.list_companies()), 1)
        self.assertEqual(len(supplier_risk_service.list_documents()), 2)
        edit = SupplierRiskDocumentDialog(document=rows[0])
        self.assertFalse(edit.file_button.isEnabled())
        edit.note.setPlainText("upraveno")
        with patch.object(QMessageBox, "warning"), patch.object(QMessageBox, "information"):
            edit._save()
        stored = supplier_risk_service.list_documents()
        original = next(row for row in stored if row.id == rows[0].id)
        self.assertEqual(original.note, "upraveno")
        self.assertEqual(original.attachment_id, rows[0].attachment_id)
        dialog.deleteLater()
        second.deleteLater()
        edit.deleteLater()

    def test_page_appends_tab_and_keeps_existing_tabs(self):
        page = RizeniRizikPage()
        self.assertEqual(page.library_tab_index, 1)
        self.assertEqual(page.tabs.count(), 4)
        self.assertEqual(page.tabs.tabText(0), "Identifikace")
        self.assertEqual(page.tabs.tabText(3), SUPPLIER_RISK_TAB_TITLE)
        self.assertIs(page.tabs.widget(3), page.supplier_risks_tab)
        page.refresh()
        page.deleteLater()

    def test_ico_is_eight_digits_and_rejects_other_characters(self):
        self.assertEqual(normalize_supplier_ico(" 123 "), "00000123")
        self.assertEqual(normalize_supplier_ico("123 4567"), "01234567")
        self.assertEqual(normalize_supplier_ico("12345678"), "12345678")
        self.assertIsNone(normalize_supplier_ico("   "))
        with self.assertRaises(SupplierRiskError):
            normalize_supplier_ico("12AB5678")
        with self.assertRaises(SupplierRiskError):
            normalize_supplier_ico("123456789")
        created = supplier_risk_service.create_document(
            company_id=None,
            name="Krátké IČO",
            ico="123",
            received_on=None,
            note="",
            source_path=str(_pdf("kratke.pdf", b"kratke")),
        )
        self.assertEqual(created.row.ico, "00000123")
        reused = supplier_risk_service.create_document(
            company_id=None,
            name="Jiný zápis",
            ico="00000123",
            received_on=None,
            note="",
            source_path=str(_pdf("kratke-2.pdf", b"dalsi")),
        )
        self.assertTrue(reused.reused_existing_company)
        self.assertEqual(reused.row.company_id, created.row.company_id)
        self.assertEqual(len(supplier_risk_service.list_companies()), 1)

    def test_legacy_company_without_ico_stays_and_document_opens(self):
        from moduly.rizeni_rizik.repository.supplier_risk_repository import (
            SupplierRiskRepository,
        )

        company = SupplierRiskRepository().add_company(
            SupplierRiskCompany(name="Starý dodavatel", ico=None)
        )
        created = supplier_risk_service.create_document(
            company_id=company.id,
            name="Starý dodavatel",
            ico="",
            received_on=None,
            note="původní",
            source_path=str(_pdf("stary.pdf", b"stary-soubor")),
        )
        stored = supplier_risk_service.list_companies()
        self.assertEqual(stored[0].id, company.id)
        self.assertIsNone(stored[0].ico)
        self.assertEqual(created.row.company_id, company.id)
        with patch(
            "moduly.rizeni_rizik.sluzby.supplier_risk_service.open_local_file",
            return_value=True,
        ) as opened:
            self.assertTrue(supplier_risk_service.open_document(created.row.id))
        self.assertEqual(Path(opened.call_args.args[0]).read_bytes(), b"stary-soubor")
        with self.assertRaises(SupplierRiskError):
            supplier_risk_service.update_document(
                created.row.id,
                company_id=company.id,
                name="Přejmenováno",
                ico="",
                received_on=None,
                note="beze změny firmy",
            )
        again = supplier_risk_service.list_companies()
        self.assertEqual(again[0].name, "Starý dodavatel")
        self.assertIsNone(again[0].ico)
        self.assertEqual(
            supplier_risk_service.list_documents()[0].note,
            "původní",
        )
        filled = supplier_risk_service.update_document(
            created.row.id,
            company_id=company.id,
            name="Starý dodavatel",
            ico="5",
            received_on=date(2026, 2, 2),
            note="doplněno",
        )
        self.assertEqual(filled.row.ico, "00000005")
        self.assertEqual(filled.row.attachment_id, created.row.attachment_id)
        self.assertEqual(
            attachment_service.resolve_path(
                attachment_service.repository.get_by_id(created.row.attachment_id)
            ).read_bytes(),
            b"stary-soubor",
        )

    def test_ares_fills_only_name_and_keeps_fields_on_failure(self):
        dialog = SupplierRiskDocumentDialog()
        dialog.name.setText("Ruční název")
        dialog.ico.setText("123")
        with patch(
            "moduly.rizeni_rizik.sluzby.supplier_risk_service.ares_service.find_by_ico",
            return_value={
                "ico": "123",
                "name": "ARES Firma",
                "address": "Ulice 1",
            },
        ) as find_by_ico:
            dialog._load_from_ares()
        find_by_ico.assert_called_once_with("00000123")
        self.assertEqual(dialog.name.text(), "ARES Firma")
        self.assertEqual(dialog.ico.text(), "123")
        dialog.name.setText("Upraveno ručně")
        self.assertEqual(dialog.name.text(), "Upraveno ručně")

        dialog.name.setText("Původní název")
        dialog.ico.setText("123")
        with patch(
            "moduly.rizeni_rizik.sluzby.supplier_risk_service.ares_service.find_by_ico",
            return_value=None,
        ), patch.object(QMessageBox, "warning"):
            dialog._load_from_ares()
        self.assertEqual(dialog.name.text(), "Původní název")
        self.assertEqual(dialog.ico.text(), "123")

        dialog.ico.setText("12AB")
        with patch(
            "moduly.rizeni_rizik.sluzby.supplier_risk_service.ares_service.find_by_ico",
        ) as skipped, patch.object(QMessageBox, "warning"):
            dialog._load_from_ares()
        skipped.assert_not_called()
        self.assertEqual(dialog.name.text(), "Původní název")
        self.assertEqual(dialog.ico.text(), "12AB")
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
