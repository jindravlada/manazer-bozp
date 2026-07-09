import importlib
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

    from core.services.app_runtime_service import mark_application_started

    mark_application_started()

    from moduly.pravni_pozadavky.constants import (
        CHANGE_NOVELIZATION,
        DOCUMENT_TYPE_ZAKON,
        NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX,
        SECTION_PARAGRAPH,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_client import (
        ESbirkaVersionInfo,
        legal_document_esbirka_client,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_check_novelization_service import (
        legal_check_novelization_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import legal_check_run_service
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalCheckNovelizationServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_change import LegalChange
        from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalChange))
            session.execute(delete(LegalCheckRun))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

        self.fixture_390 = Path(__file__).resolve().parent / "data" / "sample_esbirka_390_2021.html"
        self.fixture_html = self.fixture_390.read_text(encoding="utf-8")
        self.remote_version = legal_document_esbirka_client.extract_version_info(
            self.fixture_html,
            year=2021,
            number="390",
        )

    def _create_document_with_version(self, *, checksum: str = ""):
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Nařízení vlády č. 390/2021 Sb.",
            number="390/2021 Sb.",
            year=2021,
            short_title="NV 390/2021 Sb.",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
            checksum=checksum,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            section_number="1",
            title="§ 1",
            text="Původní znění",
            sort_order=1,
        )
        return document, version

    def test_extract_version_info_from_fixture(self) -> None:
        self.assertEqual(self.remote_version.slice_id, "347995")
        self.assertEqual(self.remote_version.doc_id, "17597164")
        self.assertEqual(self.remote_version.publication_date, date(2021, 10, 11))

    def test_same_version_does_not_create_change(self) -> None:
        document, version = self._create_document_with_version(
            checksum=legal_document_esbirka_client.build_version_checksum(
                slice_id=self.remote_version.slice_id,
                text_checksum=self.remote_version.text_checksum,
            ),
        )
        run = legal_check_run_service._begin_automatic_check(date(2024, 1, 1), date(2024, 1, 31))

        with patch.object(
            legal_document_esbirka_client,
            "fetch_version_info",
            return_value=self.remote_version,
        ):
            change = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )

        self.assertIsNone(change)
        self.assertEqual(legal_change_service.list_by_check_run(run.id), [])

    def test_newer_version_creates_change(self) -> None:
        document, version = self._create_document_with_version(
            checksum=legal_document_esbirka_client.build_version_checksum(
                slice_id="111111",
                text_checksum="old-checksum",
            ),
        )
        run = legal_check_run_service._begin_automatic_check(date(2024, 1, 1), date(2024, 1, 31))

        with patch.object(
            legal_document_esbirka_client,
            "fetch_version_info",
            return_value=self.remote_version,
        ):
            change = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )

        assert change is not None
        self.assertEqual(change.change_type, CHANGE_NOVELIZATION)
        self.assertEqual(change.legal_check_run_id, run.id)
        self.assertEqual(change.legal_document_id, document.id)
        self.assertEqual(change.legal_document_version_id, version.id)
        self.assertEqual(change.title, "Předpis byl novelizován.")
        self.assertFalse(change.evaluated)
        self.assertEqual(change.published_at, date(2021, 10, 11))
        self.assertIn("Aktuální znění", change.description)
        self.assertIn(self.remote_version.version_label, change.description)

    def test_run_automatic_check_counts_created_changes(self) -> None:
        document, _version = self._create_document_with_version(
            checksum=legal_document_esbirka_client.build_version_checksum(
                slice_id="111111",
                text_checksum="old-checksum",
            ),
        )

        with patch.object(
            legal_document_esbirka_client,
            "fetch_version_info",
            return_value=self.remote_version,
        ):
            result = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 1, 1),
                period_to=date(2024, 1, 31),
            )

        self.assertEqual(result.changes_count, 1)
        self.assertEqual(result.run.changes_found_count, 1)
        changes = legal_change_service.list_by_check_run(result.run.id)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].legal_document_id, document.id)

    def test_second_check_document_does_not_recreate_change(self) -> None:
        document, version = self._create_document_with_version(
            checksum=legal_document_esbirka_client.build_version_checksum(
                slice_id="111111",
                text_checksum="old-checksum",
            ),
        )
        run1 = legal_check_run_service._begin_automatic_check(date(2024, 1, 1), date(2024, 1, 31))
        run2 = legal_check_run_service._begin_automatic_check(date(2024, 2, 1), date(2024, 2, 28))

        with patch.object(
            legal_document_esbirka_client,
            "fetch_version_info",
            return_value=self.remote_version,
        ):
            change1 = legal_check_novelization_service.check_document(
                document,
                check_run_id=run1.id,
            )
            change2 = legal_check_novelization_service.check_document(
                document,
                check_run_id=run2.id,
            )

        assert change1 is not None
        self.assertIsNone(change2)
        self.assertEqual(len(legal_change_service.list_by_document(document.id)), 1)
        updated_version = legal_document_version_service.get_by_id(version.id)
        assert updated_version is not None
        self.assertEqual(
            updated_version.checksum,
            legal_document_esbirka_client.build_version_checksum(
                slice_id=self.remote_version.slice_id,
                text_checksum=self.remote_version.text_checksum,
            ),
        )

    def test_second_automatic_check_finds_no_changes(self) -> None:
        document, version = self._create_document_with_version(
            checksum=legal_document_esbirka_client.build_version_checksum(
                slice_id="111111",
                text_checksum="old-checksum",
            ),
        )

        with patch.object(
            legal_document_esbirka_client,
            "fetch_version_info",
            return_value=self.remote_version,
        ):
            result1 = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 1, 1),
                period_to=date(2024, 1, 31),
            )
            result2 = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
            )

        self.assertEqual(result1.changes_count, 1)
        self.assertEqual(result1.run.changes_found_count, 1)
        self.assertEqual(result2.changes_count, 0)
        self.assertEqual(result2.run.changes_found_count, 0)
        self.assertEqual(len(legal_change_service.list_by_document(document.id)), 1)
        updated_version = legal_document_version_service.get_by_id(version.id)
        assert updated_version is not None
        self.assertEqual(
            updated_version.checksum,
            legal_document_esbirka_client.build_version_checksum(
                slice_id=self.remote_version.slice_id,
                text_checksum=self.remote_version.text_checksum,
            ),
        )

    def test_skips_duplicate_when_unevaluated_novelization_exists(self) -> None:
        document, version = self._create_document_with_version(
            checksum=legal_document_esbirka_client.build_version_checksum(
                slice_id="111111",
                text_checksum="old-checksum",
            ),
        )
        remote_checksum = legal_document_esbirka_client.build_version_checksum(
            slice_id=self.remote_version.slice_id,
            text_checksum=self.remote_version.text_checksum,
        )
        run = legal_check_run_service._begin_automatic_check(date(2024, 1, 1), date(2024, 1, 31))
        legal_change_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            legal_check_run_id=run.id,
            change_type=CHANGE_NOVELIZATION,
            title="Předpis byl novelizován.",
            description="Existující nevyhodnocená změna",
            note=f"{NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX}{remote_checksum}",
        )

        duplicate_run = legal_check_run_service._begin_automatic_check(
            date(2024, 2, 1),
            date(2024, 2, 28),
        )
        with patch.object(
            legal_document_esbirka_client,
            "fetch_version_info",
            return_value=self.remote_version,
        ):
            change = legal_check_novelization_service.check_document(
                document,
                check_run_id=duplicate_run.id,
            )

        self.assertIsNone(change)
        self.assertEqual(len(legal_change_service.list_by_document(document.id)), 1)
        updated_version = legal_document_version_service.get_by_id(version.id)
        assert updated_version is not None
        self.assertEqual(updated_version.checksum, remote_checksum)


if __name__ == "__main__":
    unittest.main()
