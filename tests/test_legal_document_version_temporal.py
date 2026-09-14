import importlib
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.database_initializer import (
        LEGAL_DOCUMENT_VERSION_SOURCE_ELI_UNIQUE_INDEX,
        _ensure_legal_document_version_columns,
        _table_columns,
        _table_indexes,
    )
    from moduly.pravni_pozadavky.constants import (
        DOCUMENT_TYPE_ZAKON,
        SECTION_PARAGRAPH,
        VERSION_STATUS_FUTURE,
        VERSION_STATUS_HISTORICAL,
        VERSION_STATUS_IN_USE,
        VERSION_STATUS_PENDING_ADOPTION,
        legal_document_version_status_label,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client import (
        legal_document_esbirka_opendata_client,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        DUPLICATE_SOURCE_ELI_MESSAGE,
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_version_temporal import (
        TEMPORAL_STATE_FUTURE,
        TEMPORAL_STATE_IN_FORCE,
        TEMPORAL_STATE_LEGACY,
        classify_temporal_wording,
        is_identified_temporal_version,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
        legal_requirement_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


AS_OF_BEFORE_2027 = date(2026, 9, 14)
AS_OF_2027 = date(2027, 1, 1)
ELI_2026 = "eli/cz/sb/2006/262/2026-01-01"
ELI_2027 = "eli/cz/sb/2006/262/2027-01-01"
ELI_361 = "eli/cz/sb/2007/361/2026-09-01"


class LegalDocumentVersionTemporalTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_source import (
            LegalRequirementSource,
        )
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

    def _create_document(self, *, number: str = "262", year: int = 2006):
        return legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number=number,
            year=year,
        )

    def test_a_legacy_version_stays_in_use(self) -> None:
        document = self._create_document()
        first = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
            checksum=f"esbirka-eli:{ELI_2027}",
        )
        second = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Novější legacy",
            effective_from=date(2007, 1, 1),
        )

        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        self.assertEqual(current.id, second.id)
        self.assertIsNone(first.source_eli)
        self.assertIsNone(second.source_eli)
        self.assertFalse(is_identified_temporal_version(first))
        self.assertEqual(
            legal_document_version_status_label(second, current_version_id=current.id),
            VERSION_STATUS_IN_USE,
        )
        self.assertEqual(
            legal_document_version_status_label(first, current_version_id=current.id),
            VERSION_STATUS_HISTORICAL,
        )

    def test_b_future_wording_is_not_current_before_effective_from(self) -> None:
        document = self._create_document()
        wording_2026 = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Znění 2026",
            source_eli=ELI_2026,
            effective_from=date(2026, 1, 1),
        )
        wording_2027 = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Znění 2027",
            source_eli=ELI_2027,
            effective_from=date(2027, 1, 1),
        )

        current = legal_document_version_service.get_effective_version(
            document.id,
            AS_OF_BEFORE_2027,
        )
        assert current is not None
        self.assertEqual(current.id, wording_2026.id)
        self.assertEqual(
            legal_document_version_status_label(
                wording_2026,
                current_version_id=current.id,
                as_of=AS_OF_BEFORE_2027,
            ),
            VERSION_STATUS_IN_USE,
        )
        self.assertEqual(
            legal_document_version_status_label(
                wording_2027,
                current_version_id=current.id,
                as_of=AS_OF_BEFORE_2027,
            ),
            VERSION_STATUS_FUTURE,
        )

    def test_c_wording_becomes_current_on_effective_from(self) -> None:
        document = self._create_document()
        wording_2026 = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Znění 2026",
            source_eli=ELI_2026,
            effective_from=date(2026, 1, 1),
        )
        wording_2027 = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Znění 2027",
            source_eli=ELI_2027,
            effective_from=date(2027, 1, 1),
        )

        current = legal_document_version_service.get_effective_version(
            document.id,
            AS_OF_2027,
        )
        assert current is not None
        self.assertEqual(current.id, wording_2027.id)
        self.assertEqual(
            legal_document_version_status_label(
                wording_2027,
                current_version_id=current.id,
                as_of=AS_OF_2027,
            ),
            VERSION_STATUS_IN_USE,
        )
        self.assertEqual(
            legal_document_version_status_label(
                wording_2026,
                current_version_id=current.id,
                as_of=AS_OF_2027,
            ),
            VERSION_STATUS_HISTORICAL,
        )

    def test_d_higher_id_future_version_is_not_used_early(self) -> None:
        document = self._create_document()
        wording_2026 = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Znění 2026",
            source_eli=ELI_2026,
            effective_from=date(2026, 1, 1),
        )
        wording_2027 = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Znění 2027",
            source_eli=ELI_2027,
            effective_from=date(2027, 1, 1),
        )

        self.assertGreater(wording_2027.id, wording_2026.id)
        current = legal_document_version_service.get_effective_version(
            document.id,
            AS_OF_BEFORE_2027,
        )
        assert current is not None
        self.assertEqual(current.id, wording_2026.id)
        self.assertNotEqual(current.id, wording_2027.id)

    def test_e_source_eli_is_unique_per_document(self) -> None:
        document = self._create_document()
        legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="První",
            source_eli=ELI_2026,
            effective_from=date(2026, 1, 1),
        )
        with self.assertRaises(ValueError) as raised:
            legal_document_version_service.create(
                legal_document_id=document.id,
                version_name="Duplicitní",
                source_eli=f"https://opendata.eselpoint.gov.cz/esel-esb/{ELI_2026}",
                effective_from=date(2026, 1, 1),
            )
        self.assertEqual(str(raised.exception), DUPLICATE_SOURCE_ELI_MESSAGE)

    def test_f_same_source_eli_on_other_document_is_allowed(self) -> None:
        first = self._create_document(number="262", year=2006)
        second = self._create_document(number="361", year=2007)
        first_version = legal_document_version_service.create(
            legal_document_id=first.id,
            version_name="ZP 2026",
            source_eli=ELI_2026,
            effective_from=date(2026, 1, 1),
        )
        second_version = legal_document_version_service.create(
            legal_document_id=second.id,
            version_name="Jiný předpis se stejným ELI řetězcem",
            source_eli=ELI_2026,
            effective_from=date(2026, 1, 1),
        )
        self.assertEqual(first_version.source_eli, ELI_2026)
        self.assertEqual(second_version.source_eli, ELI_2026)

    def test_g_migration_keeps_legacy_ids_and_links(self) -> None:
        document = self._create_document()
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
            checksum=f"esbirka-eli:{ELI_2027}",
        )
        section = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="103",
            title="§ 103",
            text="Původní text",
            sort_order=1,
        )
        requirement = legal_requirement_service.create_requirement(
            title="Školení",
            process_code="P-001",
            legal_document_id=document.id,
            legal_section_id=section.id,
            source_section_id=section.id,
        )

        version_id = version.id
        section_id = section.id
        requirement_id = requirement.id
        source_ids = [
            source.id
            for source in legal_requirement_service.source_repository.list_by_requirement(
                requirement.id
            )
        ]
        source_section_ids = [
            source.legal_section_id
            for source in legal_requirement_service.source_repository.list_by_requirement(
                requirement.id
            )
        ]

        _ensure_legal_document_version_columns()

        stored_version = legal_document_version_service.get_by_id(version_id)
        stored_section = legal_section_service.get_by_id(section_id)
        stored_requirement = legal_requirement_service.get_by_id(requirement_id)
        assert stored_version is not None
        assert stored_section is not None
        assert stored_requirement is not None
        self.assertEqual(stored_version.id, version_id)
        self.assertIsNone(stored_version.source_eli)
        self.assertIsNone(stored_version.effective_from)
        self.assertEqual(stored_version.checksum, f"esbirka-eli:{ELI_2027}")
        self.assertEqual(stored_section.id, section_id)
        self.assertEqual(stored_requirement.legal_section_id, section_id)
        self.assertEqual(stored_requirement.source_section_id, section_id)
        self.assertEqual(
            [
                source.id
                for source in legal_requirement_service.source_repository.list_by_requirement(
                    requirement_id
                )
            ],
            source_ids,
        )
        self.assertEqual(
            [
                source.legal_section_id
                for source in legal_requirement_service.source_repository.list_by_requirement(
                    requirement_id
                )
            ],
            source_section_ids,
        )
        self.assertIn("source_eli", _table_columns("legal_document_versions"))
        self.assertIn("future_wording", _table_columns("legal_document_versions"))
        self.assertIn(
            LEGAL_DOCUMENT_VERSION_SOURCE_ELI_UNIQUE_INDEX,
            _table_indexes("legal_document_versions"),
        )

    def test_g_additive_migration_on_pre_source_eli_schema(self) -> None:
        db_path = Path(tempfile.mkdtemp()) / "pre-source-eli.db"
        connection = sqlite3.connect(db_path)
        try:
            connection.executescript(
                """
                CREATE TABLE legal_documents (
                    id INTEGER PRIMARY KEY,
                    document_type VARCHAR(50) NOT NULL,
                    number VARCHAR(100) DEFAULT '',
                    year INTEGER,
                    title VARCHAR(300) NOT NULL
                );
                CREATE TABLE legal_document_versions (
                    id INTEGER PRIMARY KEY,
                    legal_document_id INTEGER NOT NULL,
                    version_name VARCHAR(150) NOT NULL,
                    effective_from DATE,
                    checksum VARCHAR(128) DEFAULT '',
                    pending_adoption BOOLEAN DEFAULT 0,
                    active BOOLEAN DEFAULT 1
                );
                CREATE TABLE legal_sections (
                    id INTEGER PRIMARY KEY,
                    legal_document_id INTEGER NOT NULL,
                    legal_document_version_id INTEGER NOT NULL,
                    section_type VARCHAR(30) NOT NULL,
                    paragraph VARCHAR(50) DEFAULT ''
                );
                CREATE TABLE legal_requirements (
                    id INTEGER PRIMARY KEY,
                    legal_document_id INTEGER,
                    legal_section_id INTEGER,
                    source_section_id INTEGER
                );
                """
            )
            connection.execute(
                "INSERT INTO legal_documents (id, document_type, number, year, title) "
                "VALUES (1, 'zakon', '262', 2006, 'Zákoník práce')"
            )
            connection.execute(
                "INSERT INTO legal_document_versions "
                "(id, legal_document_id, version_name, checksum) "
                "VALUES (7, 1, 'Aktuální znění', ?)",
                (f"esbirka-eli:{ELI_2027}",),
            )
            connection.execute(
                "INSERT INTO legal_sections "
                "(id, legal_document_id, legal_document_version_id, section_type, paragraph) "
                "VALUES (42, 1, 7, 'paragraph', '103')"
            )
            connection.execute(
                "INSERT INTO legal_requirements "
                "(id, legal_document_id, legal_section_id, source_section_id) "
                "VALUES (9, 1, 42, 42)"
            )
            connection.commit()

            connection.execute(
                "ALTER TABLE legal_document_versions ADD COLUMN source_eli VARCHAR(255)"
            )
            connection.execute(
                f"CREATE UNIQUE INDEX {LEGAL_DOCUMENT_VERSION_SOURCE_ELI_UNIQUE_INDEX} "
                "ON legal_document_versions (legal_document_id, source_eli)"
            )
            connection.execute(
                "INSERT INTO legal_document_versions "
                "(id, legal_document_id, version_name, checksum) "
                "VALUES (8, 1, 'Druhá legacy', 'esbirka:old')"
            )
            connection.commit()

            version_row = connection.execute(
                "SELECT id, source_eli, checksum FROM legal_document_versions WHERE id = 7"
            ).fetchone()
            other_legacy = connection.execute(
                "SELECT id, source_eli FROM legal_document_versions WHERE id = 8"
            ).fetchone()
            section_row = connection.execute(
                "SELECT id FROM legal_sections WHERE id = 42"
            ).fetchone()
            requirement_row = connection.execute(
                "SELECT legal_section_id, source_section_id FROM legal_requirements WHERE id = 9"
            ).fetchone()
        finally:
            connection.close()

        self.assertEqual(version_row[0], 7)
        self.assertIsNone(version_row[1])
        self.assertEqual(version_row[2], f"esbirka-eli:{ELI_2027}")
        self.assertEqual(other_legacy[0], 8)
        self.assertIsNone(other_legacy[1])
        self.assertEqual(section_row[0], 42)
        self.assertEqual(requirement_row, (42, 42))

    def test_h_get_effective_version_for_dates(self) -> None:
        document = self._create_document()
        wording_2026 = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Znění 2026",
            source_eli=ELI_2026,
            effective_from=date(2026, 1, 1),
        )
        wording_2027 = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Znění 2027",
            source_eli=ELI_2027,
            effective_from=date(2027, 1, 1),
        )

        self.assertEqual(
            legal_document_version_service.get_effective_version(
                document.id,
                date(2025, 12, 31),
            ),
            None,
        )
        before = legal_document_version_service.get_effective_version(
            document.id,
            date(2026, 1, 1),
        )
        during = legal_document_version_service.get_effective_version(
            document.id,
            AS_OF_BEFORE_2027,
        )
        on_day = legal_document_version_service.get_effective_version(
            document.id,
            AS_OF_2027,
        )
        after = legal_document_version_service.get_effective_version(
            document.id,
            date(2027, 6, 1),
        )
        assert before is not None
        assert during is not None
        assert on_day is not None
        assert after is not None
        self.assertEqual(before.id, wording_2026.id)
        self.assertEqual(during.id, wording_2026.id)
        self.assertEqual(on_day.id, wording_2027.id)
        self.assertEqual(after.id, wording_2027.id)

    def test_pending_adoption_is_not_future_label(self) -> None:
        document = self._create_document()
        current = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Znění 2026",
            source_eli=ELI_2026,
            effective_from=date(2026, 1, 1),
        )
        pending = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Nově zjištěné znění 2027",
            source_eli=ELI_2027,
            effective_from=date(2027, 1, 1),
            pending_adoption=True,
        )

        selected = legal_document_version_service.get_effective_version(
            document.id,
            AS_OF_2027,
        )
        assert selected is not None
        self.assertEqual(selected.id, current.id)
        self.assertEqual(
            legal_document_version_status_label(
                pending,
                current_version_id=selected.id,
                as_of=AS_OF_2027,
            ),
            VERSION_STATUS_PENDING_ADOPTION,
        )

    def test_legacy_plus_future_keeps_legacy_until_effective_from(self) -> None:
        document = self._create_document()
        legacy = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
            checksum=f"esbirka-eli:{ELI_2027}",
        )
        future = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Znění 2027",
            source_eli=ELI_2027,
            effective_from=date(2027, 1, 1),
        )

        before = legal_document_version_service.get_effective_version(
            document.id,
            AS_OF_BEFORE_2027,
        )
        after = legal_document_version_service.get_effective_version(
            document.id,
            AS_OF_2027,
        )
        assert before is not None
        assert after is not None
        self.assertEqual(before.id, legacy.id)
        self.assertEqual(after.id, future.id)

    def test_catalog_future_wording_is_not_current_after_effective_from(self) -> None:
        document = self._create_document()
        legacy = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
        )
        future = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Znění 2027",
            source_eli=ELI_2027,
            effective_from=date(2027, 1, 1),
            future_wording=True,
        )

        before = legal_document_version_service.get_effective_version(
            document.id,
            AS_OF_BEFORE_2027,
        )
        after = legal_document_version_service.get_effective_version(
            document.id,
            AS_OF_2027,
        )
        current = legal_document_version_service.get_current_version(document.id)
        assert before is not None
        assert after is not None
        assert current is not None
        self.assertEqual(before.id, legacy.id)
        self.assertEqual(after.id, legacy.id)
        self.assertEqual(current.id, legacy.id)
        self.assertFalse(future.pending_adoption)
        self.assertEqual(
            legal_document_version_status_label(
                future,
                current_version_id=current.id,
                as_of=AS_OF_2027,
            ),
            VERSION_STATUS_FUTURE,
        )

    def test_opendata_helpers_normalize_eli_and_effective_from(self) -> None:
        self.assertEqual(
            legal_document_esbirka_opendata_client.normalize_source_eli(
                f"https://opendata.eselpoint.gov.cz/esel-esb/{ELI_2027}"
            ),
            ELI_2027,
        )
        self.assertEqual(
            legal_document_esbirka_opendata_client.effective_from_from_source_eli(ELI_2027),
            date(2027, 1, 1),
        )
        self.assertEqual(
            legal_document_esbirka_opendata_client.effective_from_from_source_eli(ELI_361),
            date(2026, 9, 1),
        )
        self.assertEqual(
            classify_temporal_wording(
                effective_from=date(2027, 1, 1),
                on_date=AS_OF_BEFORE_2027,
            ),
            TEMPORAL_STATE_FUTURE,
        )
        self.assertEqual(
            classify_temporal_wording(
                effective_from=date(2026, 1, 1),
                on_date=AS_OF_BEFORE_2027,
            ),
            TEMPORAL_STATE_IN_FORCE,
        )
        self.assertEqual(
            classify_temporal_wording(effective_from=None, on_date=AS_OF_BEFORE_2027),
            TEMPORAL_STATE_LEGACY,
        )

    def test_update_without_source_eli_keeps_existing_identity(self) -> None:
        document = self._create_document()
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Znění 2026",
            source_eli=ELI_2026,
            effective_from=date(2026, 1, 1),
        )
        updated = legal_document_version_service.update(
            version.id,
            legal_document_id=document.id,
            version_name="Upravený název",
            effective_from=date(2026, 1, 1),
            active=True,
        )
        assert updated is not None
        self.assertEqual(updated.source_eli, ELI_2026)
        self.assertEqual(updated.version_name, "Upravený název")


if __name__ == "__main__":
    unittest.main()
