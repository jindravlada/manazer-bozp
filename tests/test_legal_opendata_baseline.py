"""PRE-4.0-BLOCKER-5R: jednorázový Open Data baseline RPP."""

from __future__ import annotations

import importlib
import inspect
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

    from core.database.upgrade_guard import prepare_database_for_startup
    from core.http_safe import SafeHttpsError
    from moduly.pravni_pozadavky.constants import (
        CHANGE_NOVELIZATION,
        DOCUMENT_TYPE_NARIZENI_VLADY,
        DOCUMENT_TYPE_ZAKON,
        NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX,
        SECTION_PARAGRAPH,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client import (
        ESbirkaOpenDataTemporalWording,
        legal_document_esbirka_opendata_client,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_tree import (
        legal_document_esbirka_opendata_tree_builder,
    )
    from moduly.pravni_pozadavky.parser.legal_document_parser_models import ParsedLegalSection
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_check_novelization_service import (
        NOVELIZATION_UNCHANGED,
        legal_check_novelization_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import LegalCheckRunService
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_opendata_baseline_service import (
        BASELINE_ACTION_FAILED,
        BASELINE_ACTION_REPLACE,
        BASELINE_ACTION_SKIPPED,
        BASELINE_ACTION_STAMP,
        UNMAPPED_SOURCE_NOTE_PREFIX,
        legal_opendata_baseline_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from tests.legal_opendata_check_fakes import (
        fake_in_force_tree,
        parsed_sections_from_version,
        patch_no_future_wordings,
    )


_IN_FORCE = "eli/cz/sb/2006/262/2026-01-01"
_FUTURE = "eli/cz/sb/2006/262/2027-01-01"
_NV_ELI = "eli/cz/sb/2007/361/2026-09-01"
_ACT_378 = "eli/cz/sb/2012/378/2026-01-01"


class LegalOpenDataBaselineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_change import LegalChange
        from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
        from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
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

    def _legacy_document(
        self,
        *,
        number: str = "262",
        year: int = 2006,
        title: str = "Zákoník práce",
        document_type: str = DOCUMENT_TYPE_ZAKON,
        short_title: str = "ZP",
        included_in_processes: bool = True,
    ):
        document = legal_document_service.create(
            document_type=document_type,
            title=title,
            number=number,
            year=year,
            short_title=short_title,
            included_in_processes=included_in_processes,
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
            checksum="esbirka:111111:old-checksum",
        )
        section = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="1",
            title="§ 1",
            text="Původní znění",
            sort_order=1,
        )
        return document, version, section

    def _patch_tree(self, version_id: int, eli: str, *, text: str | None = None):
        sections = parsed_sections_from_version(version_id)
        if text is not None and sections:
            sections[0].text = text
        return patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            return_value=fake_in_force_tree(eli, sections),
        )

    def test_matching_tree_is_stamped_without_legal_change(self) -> None:
        document, version, _section = self._legacy_document()
        with self._patch_tree(version.id, _IN_FORCE):
            result = legal_opendata_baseline_service.apply_document(document)
        self.assertEqual(result.action, BASELINE_ACTION_STAMP)
        updated = legal_document_version_service.get_by_id(version.id)
        assert updated is not None
        self.assertEqual(updated.source_eli, _IN_FORCE)
        self.assertEqual(updated.effective_from, date(2026, 1, 1))
        self.assertEqual(
            legal_document_version_service.get_current_version(document.id).id,
            version.id,
        )
        self.assertEqual(legal_change_service.list_by_document(document.id), [])

    def test_mismatch_replaces_tree_without_legal_change(self) -> None:
        document, version, section = self._legacy_document()
        requirement = legal_requirement_service.create_requirement(
            title="Vazba na § 1",
            process_code="P-001",
            legal_document_id=document.id,
            legal_section_id=section.id,
            source_section_id=section.id,
        )
        with self._patch_tree(version.id, _IN_FORCE, text="Aktuální Open Data znění"):
            result = legal_opendata_baseline_service.apply_document(document)
        self.assertEqual(result.action, BASELINE_ACTION_REPLACE)
        self.assertEqual(legal_change_service.list_by_document(document.id), [])
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        self.assertNotEqual(current.id, version.id)
        self.assertFalse(current.pending_adoption)
        self.assertEqual(current.source_eli, _IN_FORCE)
        new_sections = legal_section_service.list_by_version(current.id)
        self.assertEqual(new_sections[0].text, "Aktuální Open Data znění")
        updated = legal_requirement_service.get_by_id(requirement.id)
        assert updated is not None
        self.assertEqual(updated.legal_section_id, new_sections[0].id)
        self.assertEqual(updated.process_code, "P-001")
        self.assertEqual(updated.legal_document_id, document.id)
        refreshed = legal_document_service.get_by_id(document.id)
        assert refreshed is not None
        self.assertTrue(refreshed.included_in_processes)

    def test_p012_unmapped_12a_is_kept_without_guessing(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            title="NV 361/2007",
            number="361",
            year=2007,
            short_title="NV 361/2007",
            included_in_processes=True,
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
            checksum="esbirka:111111:old-checksum",
        )
        sec12 = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="12",
            title="§ 12",
            text="Hodnocení rizik původní",
            sort_order=1,
        )
        sec12a = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="12a",
            title="§ 12a",
            text="Zrušené ustanovení",
            sort_order=2,
        )
        parent = legal_requirement_service.create_requirement(
            title="Rodič",
            process_code="P-011",
            legal_document_id=document.id,
            legal_section_id=sec12.id,
            source_section_id=sec12.id,
        )
        requirement = legal_requirement_service.create_requirement(
            title="P-012",
            process_code="P-012",
            legal_document_id=document.id,
            legal_section_id=sec12.id,
            source_section_ids=[sec12.id, sec12a.id],
            parent_requirement_id=parent.id,
        )
        opendata = [
            ParsedLegalSection(
                section_type=SECTION_PARAGRAPH,
                paragraph="12",
                title="§ 12",
                text="Hodnocení rizik",
                sort_order=1,
            ),
        ]
        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            return_value=fake_in_force_tree(
                _NV_ELI,
                opendata,
                effective_from=date(2026, 9, 1),
            ),
        ):
            result = legal_opendata_baseline_service.apply_document(document)
        self.assertEqual(result.action, BASELINE_ACTION_REPLACE)
        self.assertEqual(result.unresolved_count, 1)
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        new_sections = legal_section_service.list_by_version(current.id)
        self.assertEqual(len(new_sections), 1)
        updated = legal_requirement_service.get_by_id(requirement.id)
        assert updated is not None
        self.assertEqual(updated.process_code, "P-012")
        self.assertEqual(updated.parent_requirement_id, parent.id)
        self.assertEqual(updated.legal_document_id, document.id)
        sources = legal_requirement_service.source_repository.list_by_requirement(requirement.id)
        source_ids = {item.legal_section_id for item in sources}
        self.assertIn(new_sections[0].id, source_ids)
        self.assertIn(sec12a.id, source_ids)
        self.assertEqual(updated.legal_section_id, new_sections[0].id)
        self.assertIn(UNMAPPED_SOURCE_NOTE_PREFIX, updated.note or "")
        self.assertIn("12a", updated.note or "")
        self.assertEqual(legal_change_service.list_by_document(document.id), [])

    def test_378_2012_gets_paragraphs_1_2_3(self) -> None:
        document, version, _section = self._legacy_document(
            number="378",
            year=2012,
            title="NV 378/2012",
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            short_title="NV 378/2012",
        )
        opendata = [
            ParsedLegalSection(
                section_type=SECTION_PARAGRAPH,
                paragraph=str(index),
                title=f"§ {index}",
                text=f"Text § {index}",
                sort_order=index,
            )
            for index in (1, 2, 3)
        ]
        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            return_value=fake_in_force_tree(_ACT_378, opendata),
        ):
            result = legal_opendata_baseline_service.apply_document(document)
        self.assertEqual(result.action, BASELINE_ACTION_REPLACE)
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        paragraphs = sorted(
            (item.paragraph or "").strip()
            for item in legal_section_service.list_by_version(current.id)
            if item.section_type == SECTION_PARAGRAPH
        )
        self.assertEqual(paragraphs, ["1", "2", "3"])

    def test_future_wording_is_stored_but_not_current(self) -> None:
        document, version, _section = self._legacy_document()
        future_sections = parsed_sections_from_version(version.id)
        future_sections[0].text = "Budoucí znění 2027"
        future_tree = fake_in_force_tree(_FUTURE, future_sections)
        wording = ESbirkaOpenDataTemporalWording(
            source_eli=_FUTURE,
            source_url="https://opendata.eselpoint.gov.cz/esel-esb/eli/cz/sb/2006/262",
            effective_from=date(2027, 1, 1),
            version_label=f"e-Sbírka {_FUTURE}",
        )
        with self._patch_tree(version.id, _IN_FORCE), patch.object(
            legal_document_esbirka_opendata_client,
            "fetch_temporal_wordings",
            return_value=(wording,),
        ), patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_tree_for_source_eli",
            return_value=future_tree,
        ):
            result = legal_opendata_baseline_service.apply_document(document)
        self.assertEqual(result.action, BASELINE_ACTION_STAMP)
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        self.assertEqual(current.id, version.id)
        self.assertEqual(current.source_eli, _IN_FORCE)
        stored_future = legal_document_version_service.find_by_source_eli(document.id, _FUTURE)
        assert stored_future is not None
        self.assertTrue(stored_future.future_wording)
        self.assertFalse(stored_future.pending_adoption)
        self.assertEqual(stored_future.effective_from, date(2027, 1, 1))

    def test_pending_novelization_is_reused_and_deactivated(self) -> None:
        document, version, _section = self._legacy_document()
        checksum = legal_document_esbirka_opendata_client.build_version_checksum(_IN_FORCE)
        pending = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Nově zjištěné znění",
            checksum=checksum,
            source_eli=_IN_FORCE,
            effective_from=date(2026, 1, 1),
            pending_adoption=True,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=pending.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="1",
            title="§ 1",
            text="Open Data znění",
            sort_order=1,
        )
        change = legal_change_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            new_legal_document_version_id=pending.id,
            change_type=CHANGE_NOVELIZATION,
            title="Předpis byl novelizován.",
            note=f"{NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX}{checksum}",
            published_at=date(2026, 1, 1),
        )
        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            return_value=fake_in_force_tree(
                _IN_FORCE,
                [
                    ParsedLegalSection(
                        section_type=SECTION_PARAGRAPH,
                        paragraph="1",
                        title="§ 1",
                        text="Open Data znění",
                        sort_order=1,
                    ),
                ],
            ),
        ):
            result = legal_opendata_baseline_service.apply_document(document)
        self.assertEqual(result.action, BASELINE_ACTION_REPLACE)
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        self.assertEqual(current.id, pending.id)
        self.assertFalse(current.pending_adoption)
        self.assertEqual(
            legal_change_service.list_by_document(document.id, include_inactive=False),
            [],
        )
        deactivated = legal_change_service.get_by_id(change.id)
        assert deactivated is not None
        self.assertFalse(deactivated.active)
        versions = legal_document_version_service.list_by_document(
            document.id,
            include_inactive=True,
        )
        self.assertEqual(len(versions), 2)

    def test_second_run_is_idempotent(self) -> None:
        document, version, _section = self._legacy_document()
        with self._patch_tree(version.id, _IN_FORCE):
            first = legal_opendata_baseline_service.apply_if_needed()
        self.assertTrue(first.applied)
        self.assertEqual(first.results[0].action, BASELINE_ACTION_STAMP)
        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
        ) as fetch_mock:
            second = legal_opendata_baseline_service.apply_if_needed()
        fetch_mock.assert_not_called()
        self.assertFalse(second.applied)
        self.assertEqual(
            legal_document_version_service.get_current_version(document.id).id,
            version.id,
        )

    def test_identified_current_is_not_rebased(self) -> None:
        document, version, _section = self._legacy_document()
        legal_document_version_service.apply_official_wording_identifiers(
            version.id,
            source_eli=_IN_FORCE,
            checksum=legal_document_esbirka_opendata_client.build_version_checksum(_IN_FORCE),
            effective_from=date(2026, 1, 1),
        )
        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
        ) as fetch_mock:
            result = legal_opendata_baseline_service.apply_document(document)
        fetch_mock.assert_not_called()
        self.assertEqual(result.action, BASELINE_ACTION_SKIPPED)

    def test_fetch_error_does_not_mutate_data(self) -> None:
        document, version, _section = self._legacy_document()
        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            side_effect=SafeHttpsError("Vypršel časový limit spojení.", kind="timeout"),
        ):
            result = legal_opendata_baseline_service.apply_document(document)
        self.assertEqual(result.action, BASELINE_ACTION_FAILED)
        updated = legal_document_version_service.get_by_id(version.id)
        assert updated is not None
        self.assertIsNone(updated.source_eli)
        self.assertEqual(legal_change_service.list_by_document(document.id), [])
        self.assertEqual(
            legal_document_version_service.get_current_version(document.id).id,
            version.id,
        )

    def test_check_after_baseline_creates_no_change(self) -> None:
        document, version, _section = self._legacy_document()
        from moduly.pravni_pozadavky.sluzby.legal_check_run_service import (
            legal_check_run_service,
        )

        run = legal_check_run_service._begin_automatic_check(date(2026, 9, 1), date(2026, 9, 14))
        with self._patch_tree(version.id, _IN_FORCE):
            legal_opendata_baseline_service.apply_document(document)
            outcome = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )
        self.assertEqual(outcome.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(outcome.change)
        self.assertEqual(legal_change_service.list_by_document(document.id), [])

    def test_startup_and_check_hooks_exist(self) -> None:
        self.assertIn(
            "legal_opendata_baseline_service",
            inspect.getsource(prepare_database_for_startup),
        )
        self.assertIn(
            "legal_opendata_baseline_service",
            inspect.getsource(LegalCheckRunService._execute_automatic_check),
        )


if __name__ == "__main__":
    unittest.main()
