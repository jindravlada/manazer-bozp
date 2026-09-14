import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
        DOCUMENT_TYPE_ZAKON,
        NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX,
        SECTION_PARAGRAPH,
        VERSION_STATUS_HISTORICAL,
        VERSION_STATUS_IN_USE,
        VERSION_STATUS_PENDING_ADOPTION,
        WORDING_STATUS_ADOPTED,
        WORDING_STATUS_PENDING,
        legal_change_wording_status_label,
        legal_document_version_status_label,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client import (
        legal_document_esbirka_opendata_client,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_tree import (
        legal_document_esbirka_opendata_tree_builder,
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
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.sluzby.legal_version_adoption_service import (
        legal_version_adoption_service,
    )
    from moduly.pravni_pozadavky.ui.legal_change_detail_dialog import LegalChangeDetailDialog
    from moduly.pravni_pozadavky.ui.legal_document_version_table import LegalDocumentVersionTable
    from tests.legal_opendata_check_fakes import fake_in_force_tree, parsed_sections_from_version


class LegalVersionAdoptionTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

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

    def _create_document_and_versions(self):
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262",
            year=2006,
        )
        old_version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
            checksum="esbirka:111111:old-checksum",
            effective_from=date(2007, 1, 1),
        )
        new_version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Nově zjištěné znění – e-Sbírka 1",
            checksum="esbirka:222222:new-checksum",
            pending_adoption=True,
        )
        old_kept = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=old_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="1",
            title="§ 1",
            text="Původní text § 1",
            sort_order=1,
        )
        old_removed = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=old_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="2",
            title="§ 2",
            text="Původní text § 2",
            sort_order=2,
        )
        new_kept = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=new_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="1",
            title="§ 1",
            text="Nový text § 1",
            sort_order=1,
        )
        change = legal_change_service.create(
            legal_document_id=document.id,
            legal_document_version_id=old_version.id,
            new_legal_document_version_id=new_version.id,
            change_type=CHANGE_NOVELIZATION,
            title="Předpis byl novelizován.",
            note=f"{NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX}esbirka:222222:new-checksum",
        )
        legal_change_section_service.sync_version_content_changes(change)
        return (
            document,
            old_version,
            new_version,
            old_kept,
            old_removed,
            new_kept,
            change,
        )

    def test_pending_version_shows_adopt_button(self) -> None:
        _document, _old, _new, _kept, _removed, _new_kept, change = self._create_document_and_versions()
        dialog = LegalChangeDetailDialog(change=change)
        self.assertFalse(dialog.adopt_btn.isHidden())
        self.assertTrue(dialog.adopt_btn.isEnabled())
        self.assertEqual(dialog.evaluation_status_label.text(), "Ne")
        self.assertEqual(dialog.wording_status_label.text(), WORDING_STATUS_PENDING)
        dialog.close()

    def test_evaluation_does_not_adopt_version(self) -> None:
        _document, old_version, new_version, _kept, _removed, _new_kept, change = (
            self._create_document_and_versions()
        )
        dialog = LegalChangeDetailDialog(change=change)
        dialog.evaluation_note_edit.setPlainText("Dopad omezený na školení.")
        dialog._save_evaluation()

        updated = legal_change_service.get_by_id(change.id)
        assert updated is not None
        self.assertTrue(updated.evaluated)
        self.assertEqual(updated.evaluation_note, "Dopad omezený na školení.")
        self.assertTrue(updated.note.startswith(NOVELIZATION_REMOTE_CHECKSUM_NOTE_PREFIX))
        detected = legal_document_version_service.get_by_id(new_version.id)
        assert detected is not None
        self.assertTrue(detected.pending_adoption)
        current = legal_document_version_service.get_current_version(old_version.legal_document_id)
        assert current is not None
        self.assertEqual(current.id, old_version.id)
        self.assertEqual(dialog.wording_status_label.text(), WORDING_STATUS_PENDING)
        dialog.close()

    def test_adoption_does_not_mark_evaluated(self) -> None:
        document, old_version, new_version, _kept, _removed, _new_kept, change = (
            self._create_document_and_versions()
        )
        result = legal_version_adoption_service.adopt_detected_version(change.id)

        updated = legal_change_service.get_by_id(change.id)
        assert updated is not None
        self.assertFalse(updated.evaluated)
        self.assertEqual(
            legal_change_wording_status_label(
                updated,
                detected_version=result.adopted_version,
            ),
            WORDING_STATUS_ADOPTED,
        )
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        self.assertEqual(current.id, new_version.id)
        self.assertFalse(current.pending_adoption)
        preserved_old = legal_document_version_service.get_by_id(old_version.id)
        assert preserved_old is not None
        self.assertTrue(preserved_old.active)
        self.assertEqual(preserved_old.checksum, "esbirka:111111:old-checksum")
        old_sections = legal_section_service.list_by_version(old_version.id)
        self.assertEqual(len(old_sections), 2)
        self.assertEqual(
            legal_document_version_status_label(current, current_version_id=current.id),
            VERSION_STATUS_IN_USE,
        )
        self.assertEqual(
            legal_document_version_status_label(preserved_old, current_version_id=current.id),
            VERSION_STATUS_HISTORICAL,
        )

    def test_adoption_prefers_new_version_even_without_effective_from(self) -> None:
        document, old_version, new_version, _kept, _removed, _new_kept, change = (
            self._create_document_and_versions()
        )
        self.assertIsNotNone(old_version.effective_from)
        self.assertIsNone(new_version.effective_from)
        legal_version_adoption_service.adopt_detected_version(change.id)
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        self.assertEqual(current.id, new_version.id)

    def test_original_and_new_texts_remain_after_adoption(self) -> None:
        _document, _old, _new, _kept, _removed, _new_kept, change = self._create_document_and_versions()
        legal_version_adoption_service.adopt_detected_version(change.id)
        rows = legal_change_section_service.list_sections_for_change(change.id)
        modified = [item for item in rows if item.change_type == CHANGE_SECTION_MODIFIED]
        self.assertTrue(modified)
        self.assertEqual(modified[0].old_text, "Původní text § 1")
        self.assertEqual(modified[0].new_text, "Nový text § 1")
        dialog = LegalChangeDetailDialog(change=legal_change_service.get_by_id(change.id))
        self.assertTrue(dialog.adopt_btn.isHidden())
        self.assertEqual(dialog.wording_status_label.text(), WORDING_STATUS_ADOPTED)
        self.assertEqual(dialog.old_text_edit.toPlainText(), "Původní text § 1")
        self.assertEqual(dialog.new_text_edit.toPlainText(), "Nový text § 1")
        dialog.close()

    def test_safe_links_are_remapped_removed_links_stay(self) -> None:
        document, old_version, new_version, old_kept, old_removed, new_kept, change = (
            self._create_document_and_versions()
        )
        kept_requirement = legal_requirement_service.create_requirement(
            title="Zachovaná vazba",
            regulation_name="Zachovaná vazba",
            legal_document_id=document.id,
            legal_section_id=old_kept.id,
            source_section_id=old_kept.id,
        )
        removed_requirement = legal_requirement_service.create_requirement(
            title="Zrušená vazba",
            regulation_name="Zrušená vazba",
            legal_document_id=document.id,
            legal_section_id=old_removed.id,
            source_section_id=old_removed.id,
        )

        unresolved_before = legal_version_adoption_service.list_unresolved_section_links(change)
        self.assertEqual({item.section_id for item in unresolved_before}, {old_removed.id})

        result = legal_version_adoption_service.adopt_detected_version(change.id)
        self.assertGreaterEqual(result.remapped_count, 1)
        self.assertEqual({item.section_id for item in result.unresolved_links}, {old_removed.id})

        updated_kept = legal_requirement_service.get_by_id(kept_requirement.id)
        assert updated_kept is not None
        self.assertEqual(updated_kept.legal_section_id, new_kept.id)
        self.assertEqual(updated_kept.source_section_id, new_kept.id)
        sources = legal_requirement_service.source_repository.list_by_requirement(kept_requirement.id)
        self.assertEqual([item.legal_section_id for item in sources], [new_kept.id])

        updated_removed = legal_requirement_service.get_by_id(removed_requirement.id)
        assert updated_removed is not None
        self.assertEqual(updated_removed.legal_section_id, old_removed.id)
        self.assertEqual(updated_removed.source_section_id, old_removed.id)
        removed_sources = legal_requirement_service.source_repository.list_by_requirement(
            removed_requirement.id,
        )
        self.assertEqual([item.legal_section_id for item in removed_sources], [old_removed.id])

        preserved_old = legal_document_version_service.get_by_id(old_version.id)
        assert preserved_old is not None
        self.assertTrue(preserved_old.active)
        self.assertFalse(legal_document_version_service.get_by_id(new_version.id).pending_adoption)

        dialog = LegalChangeDetailDialog(change=legal_change_service.get_by_id(change.id))
        self.assertFalse(dialog.unresolved_group.isHidden())
        self.assertIn("§2", dialog.unresolved_label.text())
        dialog.close()

    def test_unresolved_list_includes_only_removed_sections_of_this_change(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
        from moduly.pravni_pozadavky.sluzby.legal_section_structure_compare_service import (
            SectionStructureCompareResult,
            SectionStructureEntry,
        )

        document, old_version, _new_version, _old_kept, old_removed, _new_kept, change = (
            self._create_document_and_versions()
        )
        extra_removed = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=old_version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="3",
            title="§ 3",
            text="Původní text § 3",
            sort_order=3,
        )
        legal_requirement_service.create_requirement(
            title="Zrušená vazba",
            regulation_name="Zrušená vazba",
            legal_document_id=document.id,
            legal_section_id=old_removed.id,
            source_section_id=old_removed.id,
        )
        legal_requirement_service.create_requirement(
            title="Jiná zrušená vazba",
            regulation_name="Jiná zrušená vazba",
            legal_document_id=document.id,
            legal_section_id=extra_removed.id,
            source_section_id=extra_removed.id,
        )
        with get_session() as session:
            session.execute(
                delete(LegalChangeSection).where(LegalChangeSection.legal_change_id == change.id),
            )
            session.commit()
        legal_change_section_service.add_sections_to_change(
            change.id,
            SectionStructureCompareResult(
                removed=[SectionStructureEntry("§:2", "§2", "fp2")],
            ),
        )

        unresolved = legal_version_adoption_service.list_unresolved_section_links(change)
        self.assertEqual({item.section_id for item in unresolved}, {old_removed.id})
        self.assertNotIn(extra_removed.id, {item.section_id for item in unresolved})

    def test_repeated_check_after_adoption_does_not_duplicate(self) -> None:
        document, _old, new_version, _kept, _removed, _new_kept, change = (
            self._create_document_and_versions()
        )
        legal_version_adoption_service.adopt_detected_version(change.id)
        remote_eli = "eli/cz/sb/2006/262/2024-01-01"
        run = legal_check_run_service._begin_automatic_check(date(2024, 3, 1), date(2024, 3, 31))
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        sections = parsed_sections_from_version(current.id)
        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            return_value=fake_in_force_tree(remote_eli, sections),
        ):
            result = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )
        self.assertEqual(result.status, NOVELIZATION_UNCHANGED)
        self.assertIsNone(result.change)
        self.assertEqual(len(legal_change_service.list_by_document(document.id)), 1)
        versions = legal_document_version_service.list_by_document(document.id, include_inactive=True)
        self.assertEqual(len(versions), 2)
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        self.assertEqual(current.id, new_version.id)
        self.assertEqual(
            current.checksum,
            legal_document_esbirka_opendata_client.build_version_checksum(remote_eli),
        )

    def test_later_novelization_uses_adopted_version_as_original(self) -> None:
        document, old_version, new_version, _kept, _removed, _new_kept, change = (
            self._create_document_and_versions()
        )
        legal_version_adoption_service.adopt_detected_version(change.id)
        first_eli = "eli/cz/sb/2006/262/2024-01-01"
        later_eli = "eli/cz/sb/2006/262/2025-01-01"
        baseline_run = legal_check_run_service._begin_automatic_check(
            date(2024, 3, 1),
            date(2024, 3, 31),
        )
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        matching = parsed_sections_from_version(current.id)
        changed = parsed_sections_from_version(current.id)
        changed[0].text = "Další novela § 1"
        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            return_value=fake_in_force_tree(first_eli, matching),
        ):
            baseline = legal_check_novelization_service.check_document(
                document,
                check_run_id=baseline_run.id,
            )
        self.assertEqual(baseline.status, NOVELIZATION_UNCHANGED)
        legal_check_run_service._mark_completed(
            baseline_run.id,
            documents_checked_count=1,
            changes_found_count=0,
        )
        run = legal_check_run_service._begin_automatic_check(date(2025, 1, 1), date(2025, 1, 31))
        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            return_value=fake_in_force_tree(later_eli, changed),
        ):
            later_outcome = legal_check_novelization_service.check_document(
                document,
                check_run_id=run.id,
            )
        self.assertEqual(later_outcome.status, NOVELIZATION_CHANGED)
        later_change = later_outcome.change
        assert later_change is not None
        self.assertNotEqual(later_change.id, change.id)
        self.assertEqual(later_change.legal_document_version_id, new_version.id)
        self.assertIsNotNone(later_change.new_legal_document_version_id)
        current = legal_document_version_service.get_current_version(document.id)
        assert current is not None
        self.assertEqual(current.id, new_version.id)
        self.assertEqual(len(legal_change_service.list_by_document(document.id)), 2)
        self.assertEqual(
            len(legal_document_version_service.list_by_document(document.id, include_inactive=True)),
            3,
        )
        preserved_first = legal_document_version_service.get_by_id(old_version.id)
        assert preserved_first is not None
        self.assertTrue(preserved_first.active)

    def test_versions_table_shows_historical_after_adoption(self) -> None:
        document, old_version, new_version, _kept, _removed, _new_kept, change = (
            self._create_document_and_versions()
        )
        legal_version_adoption_service.adopt_detected_version(change.id)
        current = legal_document_version_service.get_current_version(document.id)
        table = LegalDocumentVersionTable()
        versions = legal_document_version_service.list_by_document(document.id, include_inactive=True)
        table.load_versions(versions, current_version_id=current.id if current else None)
        labels = {
            table.item(row, 1).text(): table.item(row, 2).text()
            for row in range(table.rowCount())
        }
        self.assertEqual(labels[new_version.version_name], VERSION_STATUS_IN_USE)
        self.assertEqual(labels[old_version.version_name], VERSION_STATUS_HISTORICAL)


if __name__ == "__main__":
    unittest.main()
