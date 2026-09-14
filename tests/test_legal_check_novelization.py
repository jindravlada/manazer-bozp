import importlib
import tempfile
import unittest
from contextlib import contextmanager
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
        CHANGE_SECTION_MODIFIED,
        CHECK_RUN_COMPLETED,
        DOCUMENT_TYPE_NARIZENI_VLADY,
        DOCUMENT_TYPE_ZAKON,
        NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX,
        SECTION_LETTER,
        SECTION_PARAGRAPH,
        VERSION_STATUS_IN_USE,
        detected_version_name,
        legal_document_catalog_link_label,
        legal_document_version_status_label,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_client import (
        legal_document_esbirka_client,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client import (
        ESbirkaOpenDataWording,
        legal_document_esbirka_opendata_client,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_tree import (
        legal_document_esbirka_opendata_tree_builder,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_number import (
        normalize_legal_act_number_and_year,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_section_service import (
        legal_change_section_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_check_novelization_service import (
        NOVELIZATION_CHANGED,
        NOVELIZATION_UNCHANGED,
        legal_check_novelization_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import legal_check_run_service
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from tests.legal_opendata_check_fakes import (
        fake_in_force_tree,
        parsed_sections_from_version,
        patch_no_future_wordings,
    )


class LegalCheckNovelizationServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_change import LegalChange
        from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
        from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalChangeSection))
            session.execute(delete(LegalChange))
            session.execute(delete(LegalCheckRun))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

        no_futures = patch_no_future_wordings()
        no_futures.start()
        self.addCleanup(no_futures.stop)

        self.fixture_390 = Path(__file__).resolve().parent / "data" / "sample_esbirka_390_2021.html"
        self.fixture_html = self.fixture_390.read_text(encoding="utf-8")
        self.remote_eli = "eli/cz/sb/2021/390/2021-10-11"
        self.remote_version = ESbirkaOpenDataWording(
            last_wording_eli=self.remote_eli,
            source_url="https://opendata.eselpoint.gov.cz/esel-esb/eli/cz/sb/2021/390",
            effective_from=date(2021, 10, 11),
            version_label=f"e-Sbírka {self.remote_eli}",
        )
        self.html_version = legal_document_esbirka_client.extract_version_info(
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

    @contextmanager
    def _patched_esbirka(self, version_info=None, *, change_text: str | None = None):
        info = version_info or self.remote_version
        source_eli = info.last_wording_eli

        def _fetch(*, year, number, on_date):
            want_number, want_year = normalize_legal_act_number_and_year(number, year)
            document = None
            for item in legal_document_service.list_all(include_inactive=False):
                try:
                    got_number, got_year = normalize_legal_act_number_and_year(
                        item.number or "",
                        item.year if item.year is not None else want_year,
                    )
                except ValueError:
                    continue
                if got_number == want_number and got_year == want_year:
                    document = item
                    break
            if document is None:
                raise ValueError("Předpis nenalezen.")
            version = legal_document_version_service.get_current_version(document.id)
            sections = parsed_sections_from_version(version.id) if version is not None else []
            if change_text is not None and sections:
                sections[0].text = change_text
            return fake_in_force_tree(
                source_eli,
                sections,
                effective_from=info.effective_from,
                source_url=info.source_url,
            )

        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            side_effect=_fetch,
        ):
            yield

    def _old_checksum(self) -> str:
        return legal_document_esbirka_opendata_client.build_version_checksum(
            "eli/cz/sb/2021/390/2020-01-01",
        )

    def _legacy_checksum(self) -> str:
        return legal_document_esbirka_client.build_version_checksum(
            slice_id="111111",
            text_checksum="old-checksum",
        )

    def _remote_checksum(self, version_info=None) -> str:
        info = version_info or self.remote_version
        return legal_document_esbirka_opendata_client.build_version_checksum(
            info.last_wording_eli,
        )

    def test_extract_version_info_from_fixture(self) -> None:
        self.assertEqual(self.html_version.slice_id, "347995")
        self.assertEqual(self.html_version.doc_id, "17597164")
        self.assertEqual(self.html_version.publication_date, date(2021, 10, 11))

    def test_same_version_does_not_create_change(self) -> None:
        document, version = self._create_document_with_version(
            checksum=self._remote_checksum(),
        )
        run = legal_check_run_service._begin_automatic_check(date(2024, 1, 1), date(2024, 1, 31))

        with self._patched_esbirka():
            outcome = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )

        self.assertEqual(outcome.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(outcome.change)
        self.assertEqual(legal_change_service.list_by_check_run(run.id), [])

    def test_newer_version_creates_change(self) -> None:
        document, version = self._create_document_with_version(
            checksum=self._old_checksum(),
        )
        original_checksum = version.checksum
        run = legal_check_run_service._begin_automatic_check(date(2024, 1, 1), date(2024, 1, 31))

        with self._patched_esbirka(change_text="Nové znění Open Data"):
            outcome = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )

        change = outcome.change
        self.assertEqual(outcome.status, NOVELIZATION_CHANGED)
        assert change is not None
        self.assertEqual(change.change_type, CHANGE_NOVELIZATION)
        self.assertEqual(change.legal_check_run_id, run.id)
        self.assertEqual(change.legal_document_id, document.id)
        self.assertEqual(change.legal_document_version_id, version.id)
        self.assertIsNotNone(change.new_legal_document_version_id)
        self.assertEqual(change.title, "Předpis byl novelizován.")
        self.assertFalse(change.evaluated)
        self.assertEqual(change.published_at, date(2021, 10, 11))
        self.assertIn("Aktuální znění", change.description)
        self.assertIn(detected_version_name(self.remote_version.version_label), change.description)
        updated_original = legal_document_version_service.get_by_id(version.id)
        assert updated_original is not None
        self.assertEqual(updated_original.checksum, original_checksum)
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        self.assertEqual(current.id, version.id)
        pending = legal_document_version_service.get_by_id(change.new_legal_document_version_id)
        assert pending is not None
        self.assertTrue(pending.pending_adoption)
        self.assertEqual(pending.source_eli, self.remote_eli)
        self.assertTrue(legal_section_service.list_by_version(pending.id))

    def test_novelization_saves_changed_sections_to_legal_change(self) -> None:
        document, version = self._create_document_with_version(
            checksum=self._old_checksum(),
        )
        run = legal_check_run_service._begin_automatic_check(date(2024, 1, 1), date(2024, 1, 31))

        with self._patched_esbirka(change_text="Nové znění Open Data"):
            outcome = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )

        self.assertEqual(outcome.status, NOVELIZATION_CHANGED)
        assert outcome.change is not None
        self.assertEqual(outcome.change.title, "Předpis byl novelizován.")
        saved = legal_change_section_service.list_sections_for_change(outcome.change.id)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].change_type, CHANGE_SECTION_MODIFIED)
        self.assertEqual(saved[0].old_text, "Původní znění")
        self.assertEqual(saved[0].new_text, "Nové znění Open Data")

    def test_novelization_without_content_diff_does_not_create_change(self) -> None:
        document, version = self._create_document_with_version(
            checksum=self._old_checksum(),
        )
        run = legal_check_run_service._begin_automatic_check(date(2024, 1, 1), date(2024, 1, 31))

        with self._patched_esbirka():
            outcome = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )

        self.assertEqual(outcome.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(outcome.change)
        self.assertEqual(legal_change_service.list_by_check_run(run.id), [])
        updated = legal_document_version_service.get_by_id(version.id)
        assert updated is not None
        self.assertEqual(updated.checksum, self._remote_checksum())
        self.assertEqual(updated.source_eli, self.remote_eli)

    def test_run_automatic_check_counts_created_changes(self) -> None:
        document, _version = self._create_document_with_version(
            checksum=self._old_checksum(),
        )
        legal_check_run_service.create(
            title="První kontrola",
            period_from=date(2024, 1, 1),
            period_to=date(2024, 1, 31),
            status=CHECK_RUN_COMPLETED,
            documents_checked_count=1,
            changes_found_count=0,
        )

        with self._patched_esbirka(change_text="Nové znění Open Data"):
            result = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
            )

        self.assertFalse(result.is_first_check)
        self.assertEqual(result.changes_count, 1)
        self.assertEqual(result.run.changes_found_count, 1)
        changes = legal_change_service.list_by_check_run(result.run.id)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].legal_document_id, document.id)

    def test_second_check_document_does_not_recreate_change(self) -> None:
        document, version = self._create_document_with_version(
            checksum=self._old_checksum(),
        )
        original_checksum = version.checksum
        run1 = legal_check_run_service._begin_automatic_check(date(2024, 1, 1), date(2024, 1, 31))
        run2 = legal_check_run_service._begin_automatic_check(date(2024, 2, 1), date(2024, 2, 28))

        with self._patched_esbirka(change_text="Nové znění Open Data"):
            first = legal_check_novelization_service.check_document(
                document,
                check_run_id=run1.id,
            )
        self.assertEqual(first.status, NOVELIZATION_CHANGED)
        assert first.change is not None
        legal_check_run_service._mark_completed(
            run1.id,
            documents_checked_count=1,
            changes_found_count=1,
        )
        with self._patched_esbirka(change_text="Nové znění Open Data"):
            second = legal_check_novelization_service.check_document(
                document,
                check_run_id=run2.id,
            )

        self.assertEqual(second.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(second.change)
        self.assertEqual(len(legal_change_service.list_by_document(document.id)), 1)
        versions = legal_document_version_service.list_by_document(document.id, include_inactive=True)
        self.assertEqual(len(versions), 2)
        updated_version = legal_document_version_service.get_by_id(version.id)
        assert updated_version is not None
        self.assertEqual(updated_version.checksum, original_checksum)

    def test_second_automatic_check_finds_no_changes(self) -> None:
        document, version = self._create_document_with_version(
            checksum=self._old_checksum(),
        )

        with self._patched_esbirka():
            result1 = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 1, 1),
                period_to=date(2024, 1, 31),
            )
            result2 = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
            )

        self.assertEqual(result1.changes_count, 0)
        self.assertTrue(result1.is_first_check)
        self.assertEqual(result1.run.changes_found_count, 0)
        self.assertFalse(result2.is_first_check)
        self.assertEqual(result2.changes_count, 0)
        self.assertEqual(result2.run.changes_found_count, 0)
        self.assertEqual(len(legal_change_service.list_by_document(document.id)), 0)
        updated_version = legal_document_version_service.get_by_id(version.id)
        assert updated_version is not None
        self.assertEqual(updated_version.checksum, self._remote_checksum())

    def test_skips_duplicate_when_unevaluated_novelization_exists(self) -> None:
        document, version = self._create_document_with_version(
            checksum=self._old_checksum(),
        )
        original_checksum = version.checksum
        remote_checksum = self._remote_checksum()
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
        legal_check_run_service._mark_completed(
            run.id,
            documents_checked_count=1,
            changes_found_count=1,
        )

        duplicate_run = legal_check_run_service._begin_automatic_check(
            date(2024, 2, 1),
            date(2024, 2, 28),
        )
        with self._patched_esbirka(change_text="Nové znění Open Data"):
            outcome = legal_check_novelization_service.check_document(
                document,
                check_run_id=duplicate_run.id,
            )

        self.assertEqual(outcome.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(outcome.change)
        changes = legal_change_service.list_by_document(document.id)
        self.assertEqual(len(changes), 1)
        self.assertIsNotNone(changes[0].new_legal_document_version_id)
        updated_version = legal_document_version_service.get_by_id(version.id)
        assert updated_version is not None
        self.assertEqual(updated_version.checksum, original_checksum)
        self.assertEqual(
            len(legal_document_version_service.list_by_document(document.id, include_inactive=True)),
            2,
        )

    def test_first_check_initializes_reference_without_changes(self) -> None:
        document, version = self._create_document_with_version(
            checksum=self._old_checksum(),
        )

        with self._patched_esbirka():
            result = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 1, 1),
                period_to=date(2024, 1, 31),
            )

        self.assertTrue(result.is_first_check)
        self.assertEqual(result.changes_count, 0)
        self.assertEqual(result.run.status, CHECK_RUN_COMPLETED)
        self.assertEqual(result.run.changes_found_count, 0)
        self.assertEqual(legal_change_service.list_by_document(document.id), [])
        updated_version = legal_document_version_service.get_by_id(version.id)
        assert updated_version is not None
        self.assertEqual(updated_version.checksum, self._remote_checksum())

    def test_second_automatic_check_detects_novelization_after_reference_init(self) -> None:
        document, version = self._create_document_with_version(
            checksum=self._old_checksum(),
        )
        original_after_init = self._remote_checksum()
        newer_eli = "eli/cz/sb/2021/390/2024-01-01"
        newer_remote = ESbirkaOpenDataWording(
            last_wording_eli=newer_eli,
            source_url=self.remote_version.source_url,
            effective_from=date(2024, 1, 1),
            version_label=f"e-Sbírka {newer_eli}",
        )

        with self._patched_esbirka():
            first_result = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 1, 1),
                period_to=date(2024, 1, 31),
            )
        with self._patched_esbirka(newer_remote, change_text="Nové znění Open Data"):
            second_result = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
            )

        self.assertTrue(first_result.is_first_check)
        self.assertEqual(first_result.changes_count, 0)
        self.assertFalse(second_result.is_first_check)
        self.assertEqual(second_result.changes_count, 1)
        changes = legal_change_service.list_by_document(document.id)
        self.assertEqual(len(changes), 1)
        updated_version = legal_document_version_service.get_by_id(version.id)
        assert updated_version is not None
        self.assertEqual(updated_version.checksum, original_after_init)
        self.assertIsNotNone(changes[0].new_legal_document_version_id)

    def test_document_without_reference_state_stamps_eli_baseline(self) -> None:
        document, version = self._create_document_with_version(checksum="")
        run = legal_check_run_service._begin_automatic_check(date(2024, 1, 1), date(2024, 1, 31))

        with self._patched_esbirka():
            outcome = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )

        self.assertEqual(outcome.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(outcome.change)
        self.assertEqual(legal_change_service.list_by_check_run(run.id), [])
        updated_version = legal_document_version_service.get_by_id(version.id)
        assert updated_version is not None
        self.assertEqual(updated_version.checksum, self._remote_checksum())

    def test_legacy_checksum_is_rebaselined_without_false_novelization(self) -> None:
        document, version = self._create_document_with_version(checksum=self._legacy_checksum())
        run = legal_check_run_service._begin_automatic_check(date(2024, 1, 1), date(2024, 1, 31))

        with self._patched_esbirka():
            outcome = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )

        self.assertEqual(outcome.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(outcome.change)
        updated_version = legal_document_version_service.get_by_id(version.id)
        assert updated_version is not None
        self.assertEqual(updated_version.checksum, self._remote_checksum())

    def test_new_document_without_reference_gets_baseline_on_next_check(self) -> None:
        existing_document, _existing_version = self._create_document_with_version(checksum="")
        remote_checksum = self._remote_checksum()

        with self._patched_esbirka():
            first_result = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 1, 1),
                period_to=date(2024, 1, 31),
            )

        new_document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákon č. 262/2006 Sb.",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )
        new_version = legal_document_version_service.create(
            legal_document_id=new_document.id,
            version_name="Aktuální znění",
            checksum="",
        )
        legal_section_service.create(
            legal_document_id=new_document.id,
            legal_document_version_id=new_version.id,
            section_type=SECTION_PARAGRAPH,
            section_number="1",
            title="§ 1",
            text="Nově přidaný předpis",
            sort_order=1,
        )
        zp_eli = "eli/cz/sb/2006/262/2007-01-01"
        zp_remote = ESbirkaOpenDataWording(
            last_wording_eli=zp_eli,
            source_url="https://opendata.eselpoint.gov.cz/esel-esb/eli/cz/sb/2006/262",
            effective_from=date(2007, 1, 1),
            version_label=f"e-Sbírka {zp_eli}",
        )

        def _tree_for(*, year, number, on_date):
            want_number, want_year = normalize_legal_act_number_and_year(number, year)
            document = None
            for item in legal_document_service.list_all(include_inactive=False):
                got_number, got_year = normalize_legal_act_number_and_year(
                    item.number or "",
                    item.year if item.year is not None else want_year,
                )
                if got_number == want_number and got_year == want_year:
                    document = item
                    break
            if document is None:
                raise ValueError("Předpis nenalezen.")
            version = legal_document_version_service.get_current_version(document.id)
            sections = parsed_sections_from_version(version.id) if version is not None else []
            remote = self.remote_version if want_number == "390" else zp_remote
            return fake_in_force_tree(
                remote.last_wording_eli,
                sections,
                effective_from=remote.effective_from,
                source_url=remote.source_url,
            )

        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            side_effect=_tree_for,
        ):
            second_result = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
            )

        self.assertTrue(first_result.is_first_check)
        self.assertEqual(first_result.changes_count, 0)
        self.assertFalse(second_result.is_first_check)
        self.assertEqual(second_result.changes_count, 0)
        self.assertEqual(legal_change_service.list_by_document(existing_document.id), [])
        self.assertEqual(legal_change_service.list_by_document(new_document.id), [])
        updated_new_version = legal_document_version_service.get_by_id(new_version.id)
        assert updated_new_version is not None
        self.assertEqual(
            updated_new_version.checksum,
            legal_document_esbirka_opendata_client.build_version_checksum(zp_eli),
        )
        updated_existing_version = legal_document_version_service.get_current_version(
            existing_document.id,
        )
        assert updated_existing_version is not None
        self.assertEqual(updated_existing_version.checksum, remote_checksum)

    def test_new_document_detects_novelization_after_reference_baseline(self) -> None:
        new_document, new_version = self._create_document_with_version(checksum="")
        baseline_eli = "eli/cz/sb/2021/390/2021-10-11"
        later_eli = "eli/cz/sb/2021/390/2024-01-01"
        baseline_remote = ESbirkaOpenDataWording(
            last_wording_eli=baseline_eli,
            source_url=self.remote_version.source_url,
            effective_from=date(2021, 10, 11),
            version_label=f"e-Sbírka {baseline_eli}",
        )
        newer_remote = ESbirkaOpenDataWording(
            last_wording_eli=later_eli,
            source_url=self.remote_version.source_url,
            effective_from=date(2024, 1, 1),
            version_label=f"e-Sbírka {later_eli}",
        )
        legal_check_run_service.create(
            title="První kontrola",
            period_from=date(2024, 1, 1),
            period_to=date(2024, 1, 31),
            status=CHECK_RUN_COMPLETED,
            documents_checked_count=0,
            changes_found_count=0,
        )

        with self._patched_esbirka(baseline_remote):
            second_result = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 2, 1),
                period_to=date(2024, 2, 28),
            )

        self.assertFalse(second_result.is_first_check)
        self.assertEqual(second_result.changes_count, 0)
        self.assertEqual(legal_change_service.list_by_document(new_document.id), [])
        updated_new_version = legal_document_version_service.get_by_id(new_version.id)
        assert updated_new_version is not None
        self.assertEqual(
            updated_new_version.checksum,
            legal_document_esbirka_opendata_client.build_version_checksum(baseline_eli),
        )

        with self._patched_esbirka(newer_remote, change_text="Nové znění Open Data"):
            third_result = legal_check_run_service.run_automatic_check(
                period_from=date(2024, 3, 1),
                period_to=date(2024, 3, 31),
            )

        self.assertEqual(third_result.changes_count, 1)
        changes = legal_change_service.list_by_document(new_document.id)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].change_type, CHANGE_NOVELIZATION)
        self.assertIsNotNone(changes[0].new_legal_document_version_id)
        current = legal_document_version_service.get_by_id(new_version.id)
        assert current is not None
        self.assertEqual(
            current.checksum,
            legal_document_esbirka_opendata_client.build_version_checksum(baseline_eli),
        )

    def test_novelization_keeps_stored_sections_unchanged(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            title="Nařízení vlády, kterým se stanoví podmínky ochrany zdraví při práci",
            number="361",
            year=2007,
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
            checksum=self._old_checksum(),
        )
        section_12a = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="12a",
            title="Mladiství žáci",
            text="Původní text § 12a",
            sort_order=1,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_LETTER,
            parent_section_id=section_12a.id,
            item_letter="a",
            text="písmeno a původní",
            sort_order=2,
        )
        run = legal_check_run_service._begin_automatic_check(date(2024, 1, 1), date(2024, 1, 31))

        with self._patched_esbirka(change_text="Nové znění Open Data"):
            outcome = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )

        self.assertEqual(outcome.status, NOVELIZATION_CHANGED)
        assert outcome.change is not None
        self.assertIsNotNone(outcome.change.new_legal_document_version_id)
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        self.assertEqual(current.id, version.id)
        self.assertEqual(current.checksum, self._old_checksum())
        old_sections = legal_section_service.list_by_version(version.id)
        self.assertTrue(
            any(item.paragraph == "12a" and item.text == "Původní text § 12a" for item in old_sections),
        )
        self.assertEqual(
            legal_document_version_status_label(current, current_version_id=current.id),
            VERSION_STATUS_IN_USE,
        )
        self.assertEqual(
            len(legal_document_version_service.list_by_document(document.id, include_inactive=True)),
            2,
        )
        saved = legal_change_section_service.list_sections_for_change(outcome.change.id)
        self.assertTrue(saved)

    def test_repeated_check_is_idempotent(self) -> None:
        document, version = self._create_document_with_version(checksum=self._old_checksum())
        run1 = legal_check_run_service._begin_automatic_check(date(2024, 1, 1), date(2024, 1, 31))
        run2 = legal_check_run_service._begin_automatic_check(date(2024, 2, 1), date(2024, 2, 28))

        with self._patched_esbirka(change_text="Nové znění Open Data"):
            first = legal_check_novelization_service.check_document(
                document,
                check_run_id=run1.id,
            )
        self.assertEqual(first.status, NOVELIZATION_CHANGED)
        assert first.change is not None
        legal_check_run_service._mark_completed(
            run1.id,
            documents_checked_count=1,
            changes_found_count=1,
        )
        with self._patched_esbirka(change_text="Nové znění Open Data"):
            second = legal_check_novelization_service.check_document(
                document,
                check_run_id=run2.id,
            )

        self.assertEqual(second.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(second.change)
        self.assertEqual(len(legal_change_service.list_by_document(document.id)), 1)
        versions = legal_document_version_service.list_by_document(document.id, include_inactive=True)
        self.assertEqual(len(versions), 2)
        self.assertTrue(legal_change_section_service.list_sections_for_change(first.change.id))

    def test_repeated_check_after_evaluation_is_idempotent(self) -> None:
        document, version = self._create_document_with_version(checksum=self._old_checksum())
        run1 = legal_check_run_service._begin_automatic_check(date(2024, 1, 1), date(2024, 1, 31))
        run2 = legal_check_run_service._begin_automatic_check(date(2024, 2, 1), date(2024, 2, 28))

        with self._patched_esbirka(change_text="Nové znění Open Data"):
            first = legal_check_novelization_service.check_document(
                document,
                check_run_id=run1.id,
            )
        self.assertEqual(first.status, NOVELIZATION_CHANGED)
        assert first.change is not None
        legal_change_service.mark_evaluated(first.change.id)
        legal_check_run_service._mark_completed(
            run1.id,
            documents_checked_count=1,
            changes_found_count=1,
        )
        with self._patched_esbirka(change_text="Nové znění Open Data"):
            second = legal_check_novelization_service.check_document(
                document,
                check_run_id=run2.id,
            )

        self.assertEqual(second.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(second.change)
        self.assertEqual(len(legal_change_service.list_by_document(document.id)), 1)
        versions = legal_document_version_service.list_by_document(document.id, include_inactive=True)
        self.assertEqual(len(versions), 2)

    def test_matching_eli_does_not_recreate_existing_change(self) -> None:
        document, version = self._create_document_with_version(
            checksum=self._remote_checksum(),
        )
        run = legal_check_run_service._begin_automatic_check(date(2024, 1, 1), date(2024, 1, 31))
        change = legal_change_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            legal_check_run_id=run.id,
            change_type=CHANGE_NOVELIZATION,
            title="Předpis byl novelizován.",
            description="Původní verze: Aktuální znění\nNová verze: e-Sbírka",
            note=f"{NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX}{self._remote_checksum()}",
        )
        legal_check_run_service._mark_completed(
            run.id,
            documents_checked_count=1,
            changes_found_count=1,
        )
        old_text = legal_section_service.list_by_version(version.id)[0].text
        repair_run = legal_check_run_service._begin_automatic_check(date(2024, 2, 1), date(2024, 2, 28))

        with self._patched_esbirka():
            outcome = legal_check_novelization_service.check_document(
                document,
                check_run_id=repair_run.id,
            )

        self.assertEqual(outcome.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(outcome.change)
        updated_change = legal_change_service.get_by_id(change.id)
        assert updated_change is not None
        self.assertIsNone(updated_change.new_legal_document_version_id)
        updated_original = legal_document_version_service.get_by_id(version.id)
        assert updated_original is not None
        self.assertEqual(updated_original.checksum, self._remote_checksum())
        self.assertEqual(legal_section_service.list_by_version(version.id)[0].text, old_text)
        self.assertEqual(len(legal_change_service.list_by_document(document.id)), 1)

    def test_text_novelization_without_structure_change_is_shown_as_modified(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            title="Nařízení vlády, kterým se stanoví okruh a rozsah jiných důležitých osobních překážek v práci",
            number="590",
            year=2006,
        )
        old_version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
            checksum=self._old_checksum(),
        )
        new_version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Nově zjištěné znění – e-Sbírka 355597",
            checksum=self._remote_checksum(),
            pending_adoption=True,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=old_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="1",
            title="Okruh a rozsah",
            text="Původní text § 1",
            sort_order=1,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=old_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="2",
            title="Účinnost",
            text="Toto nařízení nabývá účinnosti dnem 1. ledna 2007.",
            sort_order=2,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=new_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="1",
            title="Okruh a rozsah",
            text="Nové znění § 1 po novele",
            sort_order=1,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=new_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="2",
            title="Účinnost",
            text="Toto nařízení nabývá účinnosti dnem 1. ledna 2007.",
            sort_order=2,
        )
        change = legal_change_service.create(
            legal_document_id=document.id,
            legal_document_version_id=old_version.id,
            new_legal_document_version_id=new_version.id,
            change_type=CHANGE_NOVELIZATION,
            title="Předpis byl novelizován.",
        )
        version_count = len(
            legal_document_version_service.list_by_document(document.id, include_inactive=True),
        )

        saved, _result = legal_change_section_service.sync_version_content_changes(change)
        again, _again_result = legal_change_section_service.sync_version_content_changes(change)

        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].change_type, CHANGE_SECTION_MODIFIED)
        self.assertEqual(saved[0].section_key, "§:1")
        self.assertEqual(saved[0].old_text, "Původní text § 1")
        self.assertEqual(saved[0].new_text, "Nové znění § 1 po novele")
        self.assertEqual([item.id for item in again], [item.id for item in saved])
        self.assertEqual(
            len(legal_document_version_service.list_by_document(document.id, include_inactive=True)),
            version_count,
        )
        self.assertEqual(len(legal_change_service.list_by_document(document.id)), 1)

    def test_catalog_label_identifies_government_regulation(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            title="Nařízení vlády, kterým se stanoví podmínky ochrany zdraví při práci",
            number="361",
            year=2007,
        )
        self.assertEqual(
            legal_document_catalog_link_label(document),
            "Nařízení vlády 361/2007 Sb. – Nařízení vlády, kterým se stanoví podmínky ochrany zdraví při práci",
        )


if __name__ == "__main__":
    unittest.main()
