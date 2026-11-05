"""Fáze C3/1 – vyhledání dodavatele v katalogu podle IČO z koordinace."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="supplier-catalog-match-c3-"))

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
        COORDINATION_EMPLOYER_TYPE_PARTICIPANT,
        DEFAULT_BOZP_COORDINATION_STATUS,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
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


class SupplierCatalogMatchC3Test(unittest.TestCase):
    def setUp(self):
        with get_session() as session:
            session.execute(delete(SupplierRiskDocument))
            session.execute(delete(SupplierRiskCompany))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.commit()

    def test_different_writings_find_the_same_company(self):
        company = SupplierRiskRepository().add_company(
            SupplierRiskCompany(name="Alfa stavby", ico="12345678")
        )
        for raw in ("12345678", "123 45678", "12 345 678", " 12345678 "):
            found = supplier_risk_service.find_catalog_company_by_ico(raw)
            self.assertEqual(found.status, SUPPLIER_CATALOG_MATCH_ONE)
            self.assertEqual(found.normalized_ico, "12345678")
            self.assertEqual(found.company_id, company.id)
            self.assertEqual(found.match_count, 1)
        self.assertEqual(
            supplier_risk_service.get_company(company.id).ico,
            "12345678",
        )

    def test_legacy_unpadded_ico_matches_normalized_query(self):
        company = SupplierRiskRepository().add_company(
            SupplierRiskCompany(name="Krátké IČO", ico="123")
        )
        for raw in ("123", "00000123", " 12 3 "):
            found = supplier_risk_service.find_catalog_company_by_ico(raw)
            self.assertEqual(found.status, SUPPLIER_CATALOG_MATCH_ONE)
            self.assertEqual(found.normalized_ico, "00000123")
            self.assertEqual(found.company_id, company.id)
        self.assertEqual(supplier_risk_service.get_company(company.id).ico, "123")

    def test_no_match_ignores_company_without_ico(self):
        SupplierRiskRepository().add_company(
            SupplierRiskCompany(name="OGES", ico=None)
        )
        SupplierRiskRepository().add_company(
            SupplierRiskCompany(name="Jiná", ico="87654321")
        )
        found = supplier_risk_service.find_catalog_company_by_ico("12345678")
        self.assertEqual(found.status, SUPPLIER_CATALOG_MATCH_NONE)
        self.assertEqual(found.normalized_ico, "12345678")
        self.assertIsNone(found.company_id)
        self.assertEqual(found.match_count, 0)
        self.assertEqual(len(supplier_risk_service.list_companies()), 2)

    def test_ambiguous_match_does_not_assign_company(self):
        first = SupplierRiskRepository().add_company(
            SupplierRiskCompany(name="Stará", ico="555")
        )
        second = SupplierRiskRepository().add_company(
            SupplierRiskCompany(name="Nová", ico="00000555")
        )
        for raw in ("555", "00000555", "5 55"):
            found = supplier_risk_service.find_catalog_company_by_ico(raw)
            self.assertEqual(found.status, SUPPLIER_CATALOG_MATCH_AMBIGUOUS)
            self.assertEqual(found.normalized_ico, "00000555")
            self.assertIsNone(found.company_id)
            self.assertEqual(found.match_count, 2)
            self.assertNotIn(found.company_id, {first.id, second.id})
        stored = {
            company.id: company.ico
            for company in supplier_risk_service.list_companies()
        }
        self.assertEqual(stored, {first.id: "555", second.id: "00000555"})

    def test_missing_and_invalid_ico(self):
        SupplierRiskRepository().add_company(
            SupplierRiskCompany(name="Alfa", ico="12345678")
        )
        for raw in (None, "", "   ", "12AB", "12AB5678", "123456789"):
            found = supplier_risk_service.find_catalog_company_by_ico(raw)
            self.assertEqual(found.status, SUPPLIER_CATALOG_MATCH_INVALID)
            self.assertIsNone(found.normalized_ico)
            self.assertIsNone(found.company_id)
            self.assertEqual(found.match_count, 0)
        self.assertEqual(len(supplier_risk_service.list_companies()), 1)

    def test_lookup_does_not_change_catalog_or_coordination(self):
        company = SupplierRiskRepository().add_company(
            SupplierRiskCompany(name="Alfa stavby", ico="12345678")
        )
        document = supplier_risk_service.add_company_document(
            company.id,
            received_on=date(2026, 3, 1),
            note="původní",
            source_path=str(_pdf("katalog.pdf", b"katalog-soubor")),
            prepared_on=date(2026, 2, 2),
        )
        with get_session() as session:
            coordination = BozpCoordination(
                coordination_number="C3-1",
                meeting_date=date(2026, 11, 5),
                subject="Zkouška protokolu",
                status=DEFAULT_BOZP_COORDINATION_STATUS,
            )
            session.add(coordination)
            session.commit()
            session.refresh(coordination)
            employer = CoordinationEmployer(
                coordination_id=coordination.id,
                employer_type=COORDINATION_EMPLOYER_TYPE_PARTICIPANT,
                company_name="Alfa stavby",
                ico="123 45 678",
            )
            session.add(employer)
            session.commit()
            session.refresh(employer)
            coordination_id = coordination.id
            employer_id = employer.id

        found = supplier_risk_service.find_catalog_company_by_ico("123 45 678")
        self.assertEqual(found.status, SUPPLIER_CATALOG_MATCH_ONE)
        self.assertEqual(found.company_id, company.id)

        with get_session() as session:
            stored_employer = session.get(CoordinationEmployer, employer_id)
            stored_coordination = session.get(BozpCoordination, coordination_id)
            self.assertEqual(stored_employer.ico, "123 45 678")
            self.assertEqual(stored_employer.company_name, "Alfa stavby")
            self.assertEqual(stored_coordination.subject, "Zkouška protokolu")
            self.assertEqual(
                stored_coordination.status,
                DEFAULT_BOZP_COORDINATION_STATUS,
            )

        stored_company = supplier_risk_service.get_company(company.id)
        self.assertEqual(stored_company.name, "Alfa stavby")
        self.assertEqual(stored_company.ico, "12345678")
        documents = supplier_risk_service.list_company_documents(company.id)
        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0].id, document.id)
        self.assertEqual(documents[0].attachment_id, document.attachment_id)
        self.assertEqual(documents[0].prepared_on, date(2026, 2, 2))
        self.assertEqual(documents[0].received_on, date(2026, 3, 1))
        self.assertEqual(len(supplier_risk_service.list_companies()), 1)


if __name__ == "__main__":
    unittest.main()
