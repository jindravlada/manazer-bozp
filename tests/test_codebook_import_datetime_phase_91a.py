import importlib
import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete, select

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.nastaveni.modely.workplace import Workplace
    from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
    from moduly.sprava_dat.sluzby.codebook_catalog_service import MODULE_GLOBAL, codebook_catalog_service
    from moduly.sprava_dat.sluzby.codebook_export_service import codebook_export_service
    from moduly.sprava_dat.sluzby.codebook_import_service import codebook_import_service
    from moduly.sprava_dat.sluzby.codebook_record_normalizer import (
        CodebookRecordNormalizationError,
        ensure_database_session_rollback,
        normalize_database_record,
    )


class CodebookRecordNormalizerTestCase(unittest.TestCase):
    def test_iso_datetime_string_converts_to_datetime(self) -> None:
        normalized = normalize_database_record(
            Workplace,
            {"created_at": "2026-07-02T16:49:08"},
            codebook_name="Pracoviště",
        )
        self.assertIsInstance(normalized["created_at"], datetime)
        self.assertEqual(normalized["created_at"], datetime(2026, 7, 2, 16, 49, 8))

    def test_iso_date_string_converts_to_date(self) -> None:
        normalized = normalize_database_record(
            LegalDocumentVersion,
            {"valid_from": "2026-07-02"},
            codebook_name="Verze předpisu",
        )
        self.assertIsInstance(normalized["valid_from"], date)
        self.assertEqual(normalized["valid_from"], date(2026, 7, 2))

    def test_datetime_string_converts_to_date_for_date_column(self) -> None:
        normalized = normalize_database_record(
            LegalDocumentVersion,
            {"valid_from": "2026-07-02T16:49:08"},
            codebook_name="Verze předpisu",
        )
        self.assertEqual(normalized["valid_from"], date(2026, 7, 2))

    def test_none_stays_none_for_nullable_datetime(self) -> None:
        normalized = normalize_database_record(
            LegalDocumentVersion,
            {"valid_from": None},
            codebook_name="Verze předpisu",
        )
        self.assertIsNone(normalized["valid_from"])

    def test_empty_string_becomes_none_for_nullable_date(self) -> None:
        normalized = normalize_database_record(
            LegalDocumentVersion,
            {"valid_from": ""},
            codebook_name="Verze předpisu",
        )
        self.assertIsNone(normalized["valid_from"])

    def test_invalid_datetime_returns_clear_error(self) -> None:
        with self.assertRaises(CodebookRecordNormalizationError) as ctx:
            normalize_database_record(
                Workplace,
                {"created_at": "neplatné-datum"},
                codebook_name="Pracoviště",
            )
        self.assertIn("Pracoviště", str(ctx.exception))
        self.assertIn("created_at", str(ctx.exception))
        self.assertIn("neplatné-datum", str(ctx.exception))


class CodebookImportDatetimePhase91aTestCase(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(Workplace))
            session.commit()

    def _workplace_payload(self, *, created_at: str, workplace_id: int = 1, name: str = "Sklad") -> dict:
        return {
            "codebook_id": "db:workplaces",
            "name": "Pracoviště",
            "exported_at": "2026-07-10T12:00:00",
            "records": [
                {
                    "id": workplace_id,
                    "name": name,
                    "address": "Ulice 1",
                    "note": "",
                    "active": True,
                    "audit_enabled": True,
                    "audit_interval_months": 12,
                    "preferred_months_json": "[]",
                    "created_at": created_at,
                }
            ],
        }

    def test_import_workplaces_with_created_at_succeeds(self) -> None:
        entry = codebook_catalog_service.get_by_id("db:workplaces")
        self.assertIsNotNone(entry)
        assert entry is not None

        source = storage_module.storage_service.exports_dir / "workplaces-created-at.json"
        source.write_text(
            json.dumps(self._workplace_payload(created_at="2026-07-02T16:49:08"), ensure_ascii=False),
            encoding="utf-8",
        )

        summary = codebook_import_service.import_codebook(entry, source)

        self.assertIn(entry.name, summary.updated)
        self.assertEqual(summary.errors, [])

        with get_session() as session:
            workplace = session.scalars(select(Workplace).where(Workplace.id == 1)).first()
        self.assertIsNotNone(workplace)
        assert workplace is not None
        self.assertIsInstance(workplace.created_at, datetime)
        self.assertEqual(workplace.created_at, datetime(2026, 7, 2, 16, 49, 8))

    def test_import_global_group_succeeds_without_statement_error(self) -> None:
        workplaces_entry = codebook_catalog_service.get_by_id("db:workplaces")
        self.assertIsNotNone(workplaces_entry)
        assert workplaces_entry is not None

        single = storage_module.storage_service.exports_dir / "seed-workplaces.json"
        single.write_text(
            json.dumps(
                self._workplace_payload(
                    created_at="2026-07-02T16:49:08",
                    workplace_id=20,
                    name="Sklad skupiny",
                ),
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        seed_summary = codebook_import_service.import_codebook(workplaces_entry, single)
        self.assertIn(workplaces_entry.name, seed_summary.updated)

        group_zip = storage_module.storage_service.exports_dir / "global-group-import.zip"
        codebook_export_service.export_group_codebooks(MODULE_GLOBAL, group_zip)

        from sqlalchemy import delete

        with get_session() as session:
            session.execute(delete(Workplace))
            session.commit()

        summary = codebook_import_service.import_group_codebooks(MODULE_GLOBAL, group_zip)
        self.assertGreaterEqual(len(summary.updated), 1)
        self.assertEqual(len(summary.errors), 0)

    def test_invalid_record_reports_error_and_keeps_other_records(self) -> None:
        entry = codebook_catalog_service.get_by_id("db:workplaces")
        self.assertIsNotNone(entry)
        assert entry is not None

        source = storage_module.storage_service.exports_dir / "workplaces-mixed.json"
        payload = {
            "codebook_id": "db:workplaces",
            "name": "Pracoviště",
            "records": [
                {
                    "id": 10,
                    "name": "Platné",
                    "address": "",
                    "note": "",
                    "active": True,
                    "audit_enabled": True,
                    "audit_interval_months": 12,
                    "preferred_months_json": "[]",
                    "created_at": "2026-07-02T16:49:08",
                },
                {
                    "id": 11,
                    "name": "Neplatné",
                    "address": "",
                    "note": "",
                    "active": True,
                    "audit_enabled": True,
                    "audit_interval_months": 12,
                    "preferred_months_json": "[]",
                    "created_at": "špatně",
                },
                {
                    "id": 12,
                    "name": "Další platné",
                    "address": "",
                    "note": "",
                    "active": True,
                    "audit_enabled": True,
                    "audit_interval_months": 12,
                    "preferred_months_json": "[]",
                    "created_at": "2026-07-03T10:00:00",
                },
            ],
        }
        source.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

        summary = codebook_import_service.import_codebook(entry, source)

        self.assertIn(entry.name, summary.updated)
        self.assertEqual(len(summary.errors), 1)
        self.assertIn("created_at", summary.errors[0])
        self.assertIn("špatně", summary.errors[0])

        with get_session() as session:
            names = {
                workplace.name
                for workplace in session.scalars(
                    select(Workplace).where(Workplace.name.in_(["Platné", "Další platné"]))
                ).all()
            }
        self.assertEqual(names, {"Platné", "Další platné"})

    def test_session_is_rollbacked_after_failed_record(self) -> None:
        entry = codebook_catalog_service.get_by_id("db:workplaces")
        self.assertIsNotNone(entry)
        assert entry is not None

        source = storage_module.storage_service.exports_dir / "workplaces-invalid.json"
        source.write_text(
            json.dumps(self._workplace_payload(created_at="neplatné"), ensure_ascii=False),
            encoding="utf-8",
        )

        summary = codebook_import_service.import_codebook(entry, source)
        self.assertEqual(summary.updated, [])
        self.assertEqual(len(summary.errors), 1)

        ensure_database_session_rollback()
        with get_session() as session:
            workplace = session.scalars(select(Workplace).where(Workplace.id == 1)).first()
        self.assertIsNone(workplace)


if __name__ == "__main__":
    unittest.main()
