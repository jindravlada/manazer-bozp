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

    from core.http_safe import SafeHttpsError
    from moduly.pravni_pozadavky.constants import (
        CHANGE_NOVELIZATION,
        CHANGE_SECTION_MODIFIED,
        DOCUMENT_TYPE_ZAKON,
        SECTION_PARAGRAPH,
        SECTION_PART,
        SECTION_SUBSECTION,
        VERSION_STATUS_IN_USE,
        VERSION_STATUS_PENDING_ADOPTION,
        legal_document_version_status_label,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_client import (
        legal_document_esbirka_client,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client import (
        legal_document_esbirka_opendata_client,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_tree import (
        legal_document_esbirka_opendata_tree_builder,
    )
    from moduly.pravni_pozadavky.parser.legal_document_parser_models import ParsedLegalSection
    from moduly.pravni_pozadavky.sluzby.legal_change_impacted_process_service import (
        legal_change_impacted_process_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_section_service import (
        legal_change_section_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_check_novelization_service import (
        NOVELIZATION_CHANGED,
        NOVELIZATION_FAILED,
        NOVELIZATION_UNCHANGED,
        legal_check_novelization_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import legal_check_run_service
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.sluzby.legal_version_adoption_service import (
        legal_version_adoption_service,
    )
    from tests.legal_opendata_check_fakes import fake_in_force_tree, parsed_sections_from_version


_IN_FORCE = "eli/cz/sb/2006/262/2026-01-01"
_FUTURE = "eli/cz/sb/2006/262/2027-01-01"


class LegalCheckOpenDataWorkflowTestCase(unittest.TestCase):
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

    def _legacy_document(self):
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262",
            year=2006,
            short_title="ZP",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
            checksum=legal_document_esbirka_client.build_version_checksum(
                slice_id="111111",
                text_checksum="old-checksum",
            ),
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

    def _begin_run(self):
        return legal_check_run_service._begin_automatic_check(date(2026, 9, 1), date(2026, 9, 14))

    def _patch_tree(self, version_id: int, eli: str, *, text: str | None = None):
        sections = parsed_sections_from_version(version_id)
        if text is not None and sections:
            sections[0].text = text
        return patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            return_value=fake_in_force_tree(eli, sections),
        )

    def test_legacy_345_unchanged_initializes_identifiers(self) -> None:
        document, version, _section = self._legacy_document()
        run = self._begin_run()
        with self._patch_tree(version.id, _IN_FORCE), patch.object(
            legal_document_esbirka_opendata_client,
            "fetch_latest_wording",
        ) as latest_mock:
            result = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )
        latest_mock.assert_not_called()
        self.assertEqual(result.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(result.change)
        self.assertEqual(legal_change_service.list_by_document(document.id), [])
        updated = legal_document_version_service.get_by_id(version.id)
        assert updated is not None
        self.assertEqual(updated.source_eli, _IN_FORCE)
        self.assertEqual(updated.effective_from, date(2026, 1, 1))
        self.assertEqual(
            updated.checksum,
            legal_document_esbirka_opendata_client.build_version_checksum(_IN_FORCE),
        )
        self.assertEqual(
            legal_document_version_service.get_current_version(document.id).id,
            version.id,
        )

    def test_legacy_345_real_change_creates_pending_and_diff(self) -> None:
        document, version, section = self._legacy_document()
        requirement = legal_requirement_service.create_requirement(
            title="Vazba na § 1",
            regulation_name="Vazba na § 1",
            legal_document_id=document.id,
            legal_section_id=section.id,
            source_section_id=section.id,
        )
        original_checksum = version.checksum
        run = self._begin_run()
        with self._patch_tree(version.id, _IN_FORCE, text="Nové znění Open Data"):
            result = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )
        self.assertEqual(result.status, NOVELIZATION_CHANGED)
        assert result.change is not None
        self.assertEqual(result.change.change_type, CHANGE_NOVELIZATION)
        pending_id = result.change.new_legal_document_version_id
        self.assertIsNotNone(pending_id)
        pending = legal_document_version_service.get_by_id(pending_id)
        assert pending is not None
        self.assertTrue(pending.pending_adoption)
        self.assertEqual(pending.source_eli, _IN_FORCE)
        self.assertEqual(pending.effective_from, date(2026, 1, 1))
        pending_sections = legal_section_service.list_by_version(pending.id)
        self.assertEqual(len(pending_sections), 1)
        self.assertEqual(pending_sections[0].text, "Nové znění Open Data")
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        self.assertEqual(current.id, version.id)
        self.assertEqual(current.checksum, original_checksum)
        self.assertEqual(
            legal_document_version_status_label(current, current_version_id=current.id),
            VERSION_STATUS_IN_USE,
        )
        self.assertEqual(
            legal_document_version_status_label(pending, current_version_id=current.id),
            VERSION_STATUS_PENDING_ADOPTION,
        )
        saved = legal_change_section_service.list_sections_for_change(result.change.id)
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].change_type, CHANGE_SECTION_MODIFIED)
        self.assertEqual(saved[0].old_text, "Původní znění")
        self.assertEqual(saved[0].new_text, "Nové znění Open Data")
        impacts = legal_change_impacted_process_service.list_processes_for_change(result.change.id)
        self.assertTrue(impacts)

        adopted = legal_version_adoption_service.adopt_detected_version(result.change.id)
        self.assertEqual(adopted.adopted_version.id, pending.id)
        self.assertFalse(adopted.adopted_version.pending_adoption)
        current_after = legal_document_version_service.get_current_version(document.id)
        assert current_after is not None
        self.assertEqual(current_after.id, pending.id)
        updated_requirement = legal_requirement_service.get_by_id(requirement.id)
        assert updated_requirement is not None
        self.assertEqual(updated_requirement.legal_section_id, pending_sections[0].id)
        self.assertEqual(updated_requirement.source_section_id, pending_sections[0].id)

    def test_repeated_check_does_not_duplicate_pending_or_change(self) -> None:
        document, version, _section = self._legacy_document()
        run1 = self._begin_run()
        with self._patch_tree(version.id, _IN_FORCE, text="Nové znění Open Data"):
            first = legal_check_novelization_service.check_document(
                document,
                check_run_id=run1.id,
            )
        self.assertEqual(first.status, NOVELIZATION_CHANGED)
        legal_check_run_service._mark_completed(run1.id, documents_checked_count=1, changes_found_count=1)
        run2 = legal_check_run_service._begin_automatic_check(date(2026, 9, 15), date(2026, 9, 16))
        with self._patch_tree(version.id, _IN_FORCE, text="Nové znění Open Data"):
            second = legal_check_novelization_service.check_document(
                document,
                check_run_id=run2.id,
            )
        self.assertEqual(second.status, NOVELIZATION_UNCHANGED)
        self.assertEqual(len(legal_change_service.list_by_document(document.id)), 1)
        self.assertEqual(
            len(legal_document_version_service.list_by_document(document.id, include_inactive=True)),
            2,
        )

    def test_failed_fetch_does_not_mutate_data(self) -> None:
        document, version, _section = self._legacy_document()
        original_checksum = version.checksum
        run = self._begin_run()
        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            side_effect=SafeHttpsError("Neplatná adresa služby.", kind="invalid_url"),
        ):
            result = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )
        self.assertEqual(result.status, NOVELIZATION_FAILED)
        self.assertIsNone(result.change)
        updated = legal_document_version_service.get_by_id(version.id)
        assert updated is not None
        self.assertEqual(updated.checksum, original_checksum)
        self.assertIsNone(updated.source_eli)
        self.assertEqual(legal_change_service.list_by_document(document.id), [])
        self.assertEqual(
            len(legal_document_version_service.list_by_document(document.id, include_inactive=True)),
            1,
        )

    def test_footnote_only_difference_is_not_a_change(self) -> None:
        document, version, _section = self._legacy_document()
        run = self._begin_run()
        with self._patch_tree(version.id, _IN_FORCE, text="Původní znění73)"):
            result = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )
        self.assertEqual(result.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(result.change)
        updated = legal_document_version_service.get_by_id(version.id)
        assert updated is not None
        self.assertEqual(updated.source_eli, _IN_FORCE)

    def test_future_wording_does_not_fake_in_force_change(self) -> None:
        document, version, _section = self._legacy_document()
        run = self._begin_run()
        with self._patch_tree(version.id, _IN_FORCE), patch.object(
            legal_document_esbirka_opendata_client,
            "fetch_latest_wording",
            return_value=type(
                "W",
                (),
                {
                    "last_wording_eli": _FUTURE,
                    "source_url": "https://opendata.eselpoint.gov.cz/esel-esb/eli/cz/sb/2006/262",
                    "effective_from": date(2027, 1, 1),
                    "version_label": f"e-Sbírka {_FUTURE}",
                },
            )(),
        ) as latest_mock:
            result = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )
        latest_mock.assert_not_called()
        self.assertEqual(result.status, NOVELIZATION_UNCHANGED)
        self.assertEqual(legal_change_service.list_by_document(document.id), [])
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        self.assertEqual(current.id, version.id)
        self.assertEqual(current.source_eli, _IN_FORCE)
        self.assertNotEqual(current.source_eli, _FUTURE)
        self.assertEqual(current.effective_from, date(2026, 1, 1))
        self.assertLessEqual(current.effective_from, date.today())

    def test_legacy_html_equivalent_opendata_tree_is_unchanged(self) -> None:
        document, version, _section = self._legacy_document()
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PART,
            section_number="I",
            text="ÚVODNÍ USTANOVENÍ",
            sort_order=2,
        )
        opendata = [
            ParsedLegalSection(
                section_type=SECTION_PART,
                section_number="PRVNÍ",
                text="ÚVODNÍ USTANOVENÍ",
                sort_order=1,
            ),
            ParsedLegalSection(
                section_type=SECTION_PARAGRAPH,
                paragraph="1",
                title="§ 1",
                sort_order=2,
                parent_sort_order=1,
            ),
            ParsedLegalSection(
                section_type=SECTION_SUBSECTION,
                section_number="1",
                text="Původní znění",
                sort_order=3,
                parent_sort_order=2,
            ),
        ]
        run = self._begin_run()
        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            return_value=fake_in_force_tree(_IN_FORCE, opendata),
        ):
            result = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )
        self.assertEqual(result.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(result.change)
        self.assertEqual(legal_change_service.list_by_document(document.id), [])
        self.assertEqual(
            legal_document_version_service.get_current_version(document.id).id,
            version.id,
        )

    def test_whitespace_only_difference_is_unchanged(self) -> None:
        document, version, _section = self._legacy_document()
        run = self._begin_run()
        with self._patch_tree(version.id, _IN_FORCE, text="Původní   znění\n"):
            result = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )
        self.assertEqual(result.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(result.change)

    def test_real_361_style_removed_paragraph_stays_changed(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Nařízení vlády o ochraně zdraví při práci",
            number="361",
            year=2007,
            short_title="NV 361/2007",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
            checksum=legal_document_esbirka_client.build_version_checksum(
                slice_id="3612007",
                text_checksum="old-361",
            ),
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="12",
            text="Hodnocení rizik se provádí podle přílohy.",
            sort_order=1,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="12a",
            title="Mladiství žáci smějí pouze v rámci přípravy",
            text="nakládat s nebezpečnými chemickými látkami.",
            sort_order=2,
        )
        opendata = [
            ParsedLegalSection(
                section_type=SECTION_PARAGRAPH,
                paragraph="12",
                text="Hodnocení rizik se provádí podle přílohy.",
                sort_order=1,
            ),
        ]
        run = self._begin_run()
        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            return_value=fake_in_force_tree(
                "eli/cz/sb/2007/361/2026-09-01",
                opendata,
                effective_from=date(2026, 9, 1),
            ),
        ):
            result = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )
        self.assertEqual(result.status, NOVELIZATION_CHANGED)
        assert result.change is not None
        self.assertIsNotNone(result.change.new_legal_document_version_id)
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        self.assertEqual(current.id, version.id)
        self.assertFalse(current.pending_adoption)


if __name__ == "__main__":
    unittest.main()
