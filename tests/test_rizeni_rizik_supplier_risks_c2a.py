"""Fáze C2/2a – sloupce seznamu, datum zpracování a dvojklik na dokument."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog
from sqlalchemy import delete, text

_TMP = Path(tempfile.mkdtemp(prefix="supplier-risk-c2a-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _db_engine,
        _table_columns,
        initialize_database,
    )

    initialize_database()

    from core.database.session import get_session
    from core.models.attachment import Attachment
    from core.services.attachment_service import attachment_service
    from moduly.rizeni_rizik.constants import SUPPLIER_RISK_ENTITY_TYPE
    from moduly.rizeni_rizik.modely.supplier_risk import (
        SupplierRiskCompany,
        SupplierRiskDocument,
    )
    from moduly.rizeni_rizik.repository.supplier_risk_repository import (
        SupplierRiskRepository,
    )
    from moduly.rizeni_rizik.sluzby.supplier_risk_service import supplier_risk_service
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


def _row_with_text(table, column: int, value: str) -> int:
    for row in range(table.rowCount()):
        item = table.item(row, column)
        if item is not None and item.text() == value:
            return row
    raise AssertionError(value)


class SupplierRiskC2ATest(unittest.TestCase):
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

    def test_company_list_columns_and_search(self):
        supplier_risk_service.create_company(name="Alfa stavby", ico="12345678")
        supplier_risk_service.create_company(name="Beta montáže", ico="87654321")
        tab = SupplierRiskDocumentsTab()
        self.assertEqual(tab.table.columnCount(), 2)
        self.assertEqual(
            [tab.table.horizontalHeaderItem(column).text() for column in range(2)],
            ["IČO", "Název firmy"],
        )
        alfa = _row_with_text(tab.table, 1, "Alfa stavby")
        self.assertEqual(tab.table.item(alfa, 0).text(), "12345678")
        tab.text_filter.search_edit.setText("mont")
        self.assertFalse(tab.table.isRowHidden(_row_with_text(tab.table, 1, "Beta montáže")))
        self.assertTrue(tab.table.isRowHidden(alfa))
        tab.text_filter.search_edit.setText("12345678")
        self.assertFalse(tab.table.isRowHidden(alfa))
        self.assertTrue(
            tab.table.isRowHidden(_row_with_text(tab.table, 1, "Beta montáže"))
        )
        tab.deleteLater()

    def test_save_document_with_and_without_prepared_date(self):
        company = supplier_risk_service.create_company(name="Alfa", ico="12345678")
        with_date = SupplierRiskDocumentDialog(company_id=company.id)
        with_date.source_path = str(_pdf("s-datem.pdf", b"s-datem"))
        with_date.prepared_on.set_date_value(date(2026, 6, 1))
        with_date.received_on.set_date_value(date(2026, 6, 2))
        with_date._save()
        self.assertEqual(with_date.result(), QDialog.DialogCode.Accepted)

        without_date = SupplierRiskDocumentDialog(company_id=company.id)
        without_date.source_path = str(_pdf("bez-data.pdf", b"bez-data"))
        without_date.received_on.set_date_value(date(2026, 7, 3))
        without_date._save()

        documents = {
            row.filename: row
            for row in supplier_risk_service.list_company_documents(company.id)
        }
        dated = next(row for row in documents.values() if row.prepared_on == date(2026, 6, 1))
        empty = next(row for row in documents.values() if row.prepared_on is None)
        self.assertEqual(dated.received_on, date(2026, 6, 2))
        self.assertNotEqual(dated.prepared_on, dated.received_on)
        self.assertEqual(empty.received_on, date(2026, 7, 3))
        self.assertEqual(_file_bytes(dated.attachment_id), b"s-datem")
        self.assertEqual(_file_bytes(empty.attachment_id), b"bez-data")

        detail = SupplierRiskCompanyDialog(company=company)
        self.assertEqual(
            [detail.documents.horizontalHeaderItem(column).text() for column in range(4)],
            ["Dokument rizik", "Datum zpracování", "Datum převzetí", "Poznámka"],
        )
        dated_row = _row_with_text(detail.documents, 0, dated.filename)
        empty_row = _row_with_text(detail.documents, 0, empty.filename)
        self.assertEqual(detail.documents.item(dated_row, 1).text(), "01.06.2026")
        self.assertEqual(detail.documents.item(dated_row, 2).text(), "02.06.2026")
        self.assertEqual(detail.documents.item(empty_row, 1).text(), "—")
        self.assertEqual(detail.documents.item(empty_row, 2).text(), "03.07.2026")
        with_date.deleteLater()
        without_date.deleteLater()
        detail.deleteLater()

    def test_edit_prepared_date_keeps_attachment_and_received_date(self):
        company = supplier_risk_service.create_company(name="Alfa", ico="12345678")
        created = supplier_risk_service.add_company_document(
            company.id,
            received_on=date(2026, 1, 10),
            note="původní",
            source_path=str(_pdf("zpracovani.pdf", b"puvodni-soubor")),
            prepared_on=date(2026, 1, 2),
        )
        changed_note = supplier_risk_service.update_document_details(
            created.id,
            received_on=date(2026, 1, 10),
            note="jen poznámka",
        )
        self.assertEqual(changed_note.prepared_on, date(2026, 1, 2))
        self.assertEqual(changed_note.received_on, date(2026, 1, 10))
        self.assertEqual(changed_note.attachment_id, created.attachment_id)

        edit = SupplierRiskDocumentDialog(document=changed_note, company_id=company.id)
        self.assertEqual(edit.prepared_on.get_date(), date(2026, 1, 2))
        self.assertFalse(edit.file_button.isEnabled())
        edit.source_path = str(_pdf("vymena.pdf", b"nesmi-se-ulozit"))
        edit.prepared_on.set_date_value(date(2026, 3, 4))
        edit._save()
        stored = supplier_risk_service.list_company_documents(company.id)[0]
        self.assertEqual(stored.prepared_on, date(2026, 3, 4))
        self.assertEqual(stored.received_on, date(2026, 1, 10))
        self.assertEqual(stored.note, "jen poznámka")
        self.assertEqual(stored.attachment_id, created.attachment_id)
        self.assertEqual(stored.filename, created.filename)
        self.assertEqual(_file_bytes(created.attachment_id), b"puvodni-soubor")
        edit.deleteLater()

    def test_migration_keeps_existing_documents_without_prepared_date(self):
        company = SupplierRiskRepository().add_company(
            SupplierRiskCompany(name="Stará", ico="11223344")
        )
        with _db_engine().begin() as connection:
            connection.execute(text("DROP TABLE supplier_risk_documents"))
            connection.execute(
                text(
                    "CREATE TABLE supplier_risk_documents ("
                    "id INTEGER PRIMARY KEY, "
                    "company_id INTEGER NOT NULL, "
                    "received_on DATE, "
                    "note TEXT NOT NULL DEFAULT '', "
                    "attachment_id INTEGER, "
                    "created_at DATETIME, "
                    "updated_at DATETIME)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO supplier_risk_documents "
                    "(company_id, received_on, note, attachment_id) "
                    "VALUES (:company_id, :received_on, :note, :attachment_id)"
                ),
                {
                    "company_id": company.id,
                    "received_on": "2024-05-06",
                    "note": "historie",
                    "attachment_id": 99,
                },
            )
        initialize_database()
        initialize_database()
        self.assertIn("prepared_on", _table_columns("supplier_risk_documents"))
        with _db_engine().connect() as connection:
            column = next(
                row
                for row in connection.execute(
                    text("PRAGMA table_info(supplier_risk_documents)")
                )
                if row[1] == "prepared_on"
            )
            stored = connection.execute(
                text(
                    "SELECT prepared_on, received_on, note, attachment_id "
                    "FROM supplier_risk_documents"
                )
            ).one()
        self.assertEqual(column[3], 0)
        self.assertIsNone(stored.prepared_on)
        self.assertEqual(stored.received_on, "2024-05-06")
        self.assertEqual(stored.note, "historie")
        self.assertEqual(stored.attachment_id, 99)
        loaded = supplier_risk_service.list_documents()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].company_name, "Stará")
        self.assertIsNone(loaded[0].prepared_on)
        self.assertEqual(loaded[0].received_on, date(2024, 5, 6))
        self.assertEqual(loaded[0].note, "historie")
        self.assertEqual(loaded[0].attachment_id, 99)

    def test_double_click_opens_file_and_edit_button_opens_editor(self):
        company = supplier_risk_service.create_company(name="Alfa", ico="27074358")
        supplier_risk_service.add_company_document(
            company.id,
            received_on=None,
            note="",
            source_path=str(_pdf("dvojklik.pdf", b"obsah-dvojkliku")),
        )
        detail = SupplierRiskCompanyDialog(
            company=supplier_risk_service.get_company(company.id)
        )
        detail.documents.selectRow(0)
        self.assertTrue(detail.open_document_btn.isEnabled())
        self.assertTrue(detail.edit_document_btn.isEnabled())
        index = detail.documents.model().index(0, 0)
        with patch(
            "moduly.rizeni_rizik.sluzby.supplier_risk_service.open_local_file",
            return_value=True,
        ) as opened, patch.object(SupplierRiskDocumentDialog, "exec") as editor:
            detail.documents.doubleClicked.emit(index)
        self.assertEqual(Path(opened.call_args.args[0]).read_bytes(), b"obsah-dvojkliku")
        editor.assert_not_called()

        with patch.object(
            SupplierRiskDocumentDialog,
            "exec",
            return_value=QDialog.DialogCode.Rejected,
        ) as editor, patch(
            "moduly.rizeni_rizik.sluzby.supplier_risk_service.open_local_file",
            return_value=True,
        ) as opened:
            detail.edit_document_btn.click()
        editor.assert_called_once()
        opened.assert_not_called()

        with patch(
            "moduly.rizeni_rizik.sluzby.supplier_risk_service.open_local_file",
            return_value=True,
        ) as opened, patch.object(SupplierRiskDocumentDialog, "exec") as editor:
            detail.open_document_btn.click()
        self.assertEqual(Path(opened.call_args.args[0]).read_bytes(), b"obsah-dvojkliku")
        editor.assert_not_called()
        detail.deleteLater()


if __name__ == "__main__":
    unittest.main()
