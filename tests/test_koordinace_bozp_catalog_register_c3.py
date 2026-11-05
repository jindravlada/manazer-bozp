"""Fáze C3/3 – automatické zaevidování přílohy koordinace v katalogu rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import delete, func, select, text

_TMP = Path(tempfile.mkdtemp(prefix="coord-catalog-register-c3-"))
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
        ATTACHMENT_TYPE_RISK_RECEIPT,
        PROTOCOL_CATALOG_DOCUMENTS_HEADING,
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
    from moduly.koordinace_bozp.sluzby.coordination_risk_submission_service import (
        coordination_risk_submission_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_supplier_risk_link_service import (
        CATALOG_REGISTRATION_ALREADY,
        CATALOG_REGISTRATION_FAILED_MESSAGE,
        CATALOG_REGISTRATION_REGISTERED,
        CATALOG_REGISTRATION_SKIPPED,
        CoordinationSupplierRiskLinkError,
        coordination_supplier_risk_link_service,
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
    from moduly.rizeni_rizik.sluzby.supplier_risk_service import supplier_risk_service


def _pdf(name: str, content: bytes) -> Path:
    path = _TMP / name
    path.write_bytes(content)
    return path


class CoordinationCatalogRegisterC3Test(unittest.TestCase):
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
            session.execute(delete(Attachment))
            session.commit()
        settings_service.save_employer(
            ico="11111111",
            name="Hlavní firma s.r.o.",
            address="Praha",
            nace="",
        )

    def test_existing_supplier_gets_document_without_second_copy(self) -> None:
        employer = self._employer(ico="87 654 321", name="Alfa stavby")
        company = supplier_risk_service.create_company(
            name="Uložený název",
            ico="87654321",
        )
        coordination_risk_submission_service.save_submission(
            employer.id,
            submission_method=RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
            submission_date=date(2026, 3, 18),
            note="původní dohoda",
            risks_text="text dohody",
        )
        content = b"%PDF-1.4 predani\n"
        before_global = self._global_attachment_count()
        created = self._hand_over(employer, "predani.pdf", content)

        result = coordination_supplier_risk_link_service.register_handed_attachment(
            employer.id,
            created.id,
        )
        self.assertEqual(result.status, CATALOG_REGISTRATION_REGISTERED)
        self.assertEqual(result.company_id, company.id)
        stored_company = supplier_risk_service.list_companies()[0]
        self.assertEqual(stored_company.name, "Uložený název")
        self.assertEqual(stored_company.ico, "87654321")
        refreshed = coordination_employer_service.get_by_id(employer.id)
        self.assertEqual(refreshed.ico, "87 654 321")
        self.assertEqual(refreshed.company_name, "Alfa stavby")

        documents = supplier_risk_service.list_company_documents(company.id)
        self.assertEqual(len(documents), 1)
        document = documents[0]
        self.assertEqual(document.filename, "predani.pdf")
        self.assertIsNone(document.prepared_on)
        self.assertEqual(document.received_on, date(2026, 3, 18))
        self.assertEqual(document.note, "")
        self.assertEqual(document.attachment_id, 0)
        self.assertEqual(document.coordination_attachment_id, created.id)
        self.assertEqual(self._global_attachment_count(), before_global)
        self.assertEqual(self._link_count(), 1)
        stored_path = coordination_attachment_service.resolve_path(created)
        self.assertEqual(stored_path.read_bytes(), content)
        self.assertEqual(
            [path.name for path in self._files_beside(created)].count("predani.pdf"),
            1,
        )

        agreement = coordination_risk_submission_service.get_for_employer(employer.id)
        self.assertEqual(agreement.submission_method, RISK_SUBMISSION_STATUS_EMAIL_BEFORE)
        self.assertEqual(agreement.submission_date, date(2026, 3, 18))
        self.assertEqual(agreement.risks_text, "text dohody")
        self.assertEqual(agreement.note, "původní dohoda")

        built = coordination_protocol_builder.build(
            employer.coordination_id,
            today=date(2026, 11, 5),
        )
        text_lines = "\n".join(
            render_blocks_to_plain_lines(built.protocol_data["document"]["blocks"])
        )
        self.assertLess(
            text_lines.index("text dohody"),
            text_lines.index(PROTOCOL_CATALOG_DOCUMENTS_HEADING),
        )
        self.assertIn("původní dohoda", text_lines)
        self.assertIn("predani.pdf, převzato 18.03.2026", text_lines)
        self.assertNotIn("zpracováno", text_lines)

    def test_unknown_supplier_is_created_from_coordination_name(self) -> None:
        employer = self._employer(ico="12 345 678", name="Nový dodavatel")
        created = self._hand_over(employer, "novy.pdf", b"%PDF-1.4 novy\n")
        result = coordination_supplier_risk_link_service.register_handed_attachment(
            employer.id,
            created.id,
        )
        self.assertEqual(result.status, CATALOG_REGISTRATION_REGISTERED)
        companies = supplier_risk_service.list_companies()
        self.assertEqual([(item.name, item.ico) for item in companies], [("Nový dodavatel", "12345678")])
        refreshed = coordination_employer_service.get_by_id(employer.id)
        self.assertEqual(refreshed.ico, "12 345 678")
        self.assertEqual(refreshed.company_name, "Nový dodavatel")
        document = supplier_risk_service.list_company_documents(companies[0].id)[0]
        self.assertIsNone(document.prepared_on)
        self.assertIsNone(document.received_on)
        self.assertEqual(document.note, "")

    def test_catalog_opens_the_coordination_file(self) -> None:
        employer = self._employer(ico="87654321")
        content = b"%PDF-1.4 otevrit\n"
        created = self._hand_over(employer, "otevrit.pdf", content)
        result = coordination_supplier_risk_link_service.register_handed_attachment(
            employer.id,
            created.id,
        )
        opened: dict[str, object] = {}

        def _open(path, parent=None, title=""):
            opened["path"] = Path(path)
            opened["title"] = title
            return True

        with patch(
            "moduly.rizeni_rizik.sluzby.supplier_risk_service.open_local_file",
            side_effect=_open,
        ):
            self.assertTrue(supplier_risk_service.open_document(result.document_id))
        stored_path = coordination_attachment_service.resolve_path(created)
        self.assertEqual(opened["path"], stored_path)
        self.assertEqual(opened["title"], "Dokument rizik")
        self.assertEqual(stored_path.read_bytes(), content)
        self.assertEqual(self._global_attachment_count(), 0)

    def test_repeated_registration_does_not_duplicate(self) -> None:
        employer = self._employer(ico="87654321")
        created = self._hand_over(employer, "jednou.pdf", b"%PDF-1.4 jednou\n")
        first = coordination_supplier_risk_link_service.register_handed_attachment(
            employer.id,
            created.id,
        )
        second = coordination_supplier_risk_link_service.register_handed_attachment(
            employer.id,
            created.id,
        )
        self.assertEqual(first.status, CATALOG_REGISTRATION_REGISTERED)
        self.assertEqual(second.status, CATALOG_REGISTRATION_ALREADY)
        self.assertEqual(second.document_id, first.document_id)
        self.assertEqual(self._document_count(), 1)
        self.assertEqual(self._link_count(), 1)
        self.assertEqual(
            [path.name for path in self._files_beside(created)].count("jednou.pdf"),
            1,
        )

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
            created = self._hand_over(employer, filename, b"%PDF-1.4 x\n")
            result = coordination_supplier_risk_link_service.register_handed_attachment(
                employer.id,
                created.id,
            )
            self.assertEqual(result.status, CATALOG_REGISTRATION_SKIPPED)
            self.assertIsNotNone(
                coordination_attachment_service.get_by_id(created.id)
            )
        self.assertEqual(
            [(item.name, item.ico) for item in supplier_risk_service.list_companies()],
            before,
        )
        self.assertEqual(self._document_count(), 0)
        self.assertEqual(self._link_count(), 0)
        pending = self._employer(ico="87654321", name="Jen termín")
        coordination_risk_submission_service.save_submission(
            pending.id,
            submission_method=RISK_SUBMISSION_STATUS_WILL_EMAIL,
            submission_date=date(2026, 12, 1),
            expected_email="dodavatel@example.com",
            risks_text="ještě nepředáno",
        )
        created = self._hand_over(pending, "termin.pdf", b"%PDF-1.4 termin\n")
        coordination_supplier_risk_link_service.register_handed_attachment(
            pending.id,
            created.id,
        )
        created_company = next(
            item
            for item in supplier_risk_service.list_companies()
            if item.ico == "87654321"
        )
        document = supplier_risk_service.list_company_documents(created_company.id)[0]
        self.assertIsNone(document.received_on)

    def test_catalog_write_failure_keeps_attachment_and_warns(self) -> None:
        employer = self._employer(ico="87654321", name="Alfa stavby")
        created = self._hand_over(employer, "selhani.pdf", b"%PDF-1.4 selhani\n")
        with patch(
            "moduly.koordinace_bozp.sluzby.coordination_supplier_risk_link_service._insert_catalog_document_and_link",
            side_effect=RuntimeError("databáze"),
        ):
            with self.assertRaises(CoordinationSupplierRiskLinkError) as raised:
                coordination_supplier_risk_link_service.register_handed_attachment(
                    employer.id,
                    created.id,
                )
        self.assertEqual(str(raised.exception), CATALOG_REGISTRATION_FAILED_MESSAGE)
        self.assertIn("Příloha koordinace byla uložena.", str(raised.exception))
        self.assertIn("Zápis do katalogu", str(raised.exception))
        self.assertIsNotNone(coordination_attachment_service.get_by_id(created.id))
        self.assertEqual(supplier_risk_service.list_companies(), [])
        self.assertEqual(self._document_count(), 0)
        self.assertEqual(self._link_count(), 0)
        self.assertTrue(coordination_attachment_service.resolve_path(created).is_file())

        existing = supplier_risk_service.create_company(name="Zůstane", ico="87654321")
        with patch(
            "moduly.koordinace_bozp.sluzby.coordination_supplier_risk_link_service._insert_catalog_document_and_link",
            side_effect=RuntimeError("databáze"),
        ):
            with self.assertRaises(CoordinationSupplierRiskLinkError):
                coordination_supplier_risk_link_service.register_handed_attachment(
                    employer.id,
                    created.id,
                )
        self.assertEqual(
            [(item.id, item.name) for item in supplier_risk_service.list_companies()],
            [(existing.id, "Zůstane")],
        )

        warnings: list[str] = []
        tab = CoordinationRiskSubmissionsTab(None, employer.coordination_id)
        with (
            patch(
                "moduly.koordinace_bozp.ui.coordination_risk_submissions_tab.QFileDialog.getOpenFileName",
                return_value=(str(_pdf("z-karty.pdf", b"%PDF-1.4 karta\n")), ""),
            ),
            patch.object(
                coordination_supplier_risk_link_service,
                "register_handed_attachment",
                side_effect=RuntimeError("databáze"),
            ),
            patch.object(QMessageBox, "warning", side_effect=lambda *_args: warnings.append(_args[2])),
        ):
            tab.add_attachment()
        self.assertEqual(warnings, [CATALOG_REGISTRATION_FAILED_MESSAGE])
        attachments = coordination_attachment_service.list_for_employer(employer.id)
        self.assertEqual(
            sorted(item.original_filename for item in attachments),
            ["selhani.pdf", "z-karty.pdf"],
        )
        self.assertEqual(self._document_count(), 0)

    def test_receipt_attachment_is_not_registered(self) -> None:
        employer = self._employer(ico="87654321")
        created = coordination_attachment_service.add_file(
            coordination_id=employer.coordination_id,
            coordination_employer_id=employer.id,
            source_path=str(_pdf("prevzeti.pdf", b"%PDF-1.4 prevzeti\n")),
            attachment_type=ATTACHMENT_TYPE_RISK_RECEIPT,
        )
        result = coordination_supplier_risk_link_service.register_handed_attachment(
            employer.id,
            created.id,
        )
        self.assertEqual(result.status, CATALOG_REGISTRATION_SKIPPED)
        self.assertEqual(supplier_risk_service.list_companies(), [])
        self.assertEqual(self._link_count(), 0)

    def test_confirmed_catalog_link_still_works_beside_registered_file(self) -> None:
        employer = self._employer(ico="87654321", name="Alfa stavby")
        company = supplier_risk_service.create_company(name="Alfa stavby", ico="87654321")
        catalog = supplier_risk_service.add_company_document(
            company.id,
            received_on=date(2026, 2, 2),
            prepared_on=date(2026, 1, 1),
            note="z katalogu",
            source_path=str(_pdf("katalog.pdf", b"%PDF-1.4 katalog\n")),
        )
        coordination_supplier_risk_link_service.confirm_documents(
            employer.id,
            [catalog.id],
            supplier_approved=True,
        )
        created = self._hand_over(employer, "z-koordinace.pdf", b"%PDF-1.4 koord\n")
        coordination_supplier_risk_link_service.register_handed_attachment(
            employer.id,
            created.id,
        )
        linked = coordination_supplier_risk_link_service.list_for_employer(employer.id)
        self.assertEqual(
            [item.filename for item in linked],
            ["katalog.pdf", "z-koordinace.pdf"],
        )
        self.assertEqual(self._global_attachment_count(), 1)
        self.assertEqual(self._document_count(), 2)

    def test_migration_adds_optional_link_and_keeps_existing_documents(self) -> None:
        from core.database.database_initializer import _db_engine, initialize_database

        company = SupplierRiskRepository().add_company(
            SupplierRiskCompany(
                name="Historická firma",
                ico="11223344",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
        )
        with _db_engine().begin() as connection:
            connection.execute(text("DROP TABLE supplier_risk_documents"))
            connection.execute(
                text(
                    "CREATE TABLE supplier_risk_documents ("
                    "id INTEGER PRIMARY KEY, "
                    "company_id INTEGER NOT NULL, "
                    "received_on DATE, "
                    "prepared_on DATE, "
                    "note TEXT NOT NULL DEFAULT '', "
                    "attachment_id INTEGER, "
                    "created_at DATETIME, "
                    "updated_at DATETIME)"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO supplier_risk_documents "
                    "(company_id, received_on, prepared_on, note, attachment_id) "
                    "VALUES (:company_id, :received_on, :prepared_on, :note, :attachment_id)"
                ),
                {
                    "company_id": company.id,
                    "received_on": "2024-05-06",
                    "prepared_on": "2024-04-01",
                    "note": "historie",
                    "attachment_id": 99,
                },
            )
        initialize_database()
        initialize_database()
        with _db_engine().connect() as connection:
            columns = {
                row[1]: row
                for row in connection.execute(
                    text("PRAGMA table_info(supplier_risk_documents)")
                )
            }
            self.assertIn("coordination_attachment_id", columns)
            self.assertEqual(columns["coordination_attachment_id"][3], 0)
            stored = connection.execute(
                text(
                    "SELECT company_id, received_on, prepared_on, note, "
                    "attachment_id, coordination_attachment_id "
                    "FROM supplier_risk_documents"
                )
            ).one()
            index_names = {
                row[0]
                for row in connection.execute(
                    text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'index' AND tbl_name = 'supplier_risk_documents'"
                    )
                )
            }
        self.assertEqual(stored[0], company.id)
        self.assertEqual(str(stored[1]), "2024-05-06")
        self.assertEqual(str(stored[2]), "2024-04-01")
        self.assertEqual(stored[3], "historie")
        self.assertEqual(stored[4], 99)
        self.assertIsNone(stored[5])
        self.assertIn(
            "uq_supplier_risk_documents_coordination_attachment",
            index_names,
        )

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

    def _hand_over(
        self,
        employer: CoordinationEmployer,
        filename: str,
        content: bytes,
    ) -> CoordinationAttachment:
        return coordination_attachment_service.add_file(
            coordination_id=employer.coordination_id,
            coordination_employer_id=employer.id,
            source_path=str(_pdf(filename, content)),
            attachment_type=ATTACHMENT_TYPE_CONTRACTOR_RISKS,
        )

    def _files_beside(self, attachment: CoordinationAttachment) -> list[Path]:
        folder = coordination_attachment_service.resolve_path(attachment).parent
        return sorted(path for path in folder.iterdir() if path.is_file())

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
