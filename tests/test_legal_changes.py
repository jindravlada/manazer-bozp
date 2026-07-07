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

    from core.shared.constants import (
        ENTITY_LEGAL_CHANGE,
        ENTITY_LEGAL_REQUIREMENT,
        ENTITY_RISK,
        ENTITY_TASK,
        LINK_RELATED,
    )
    from core.shared.sluzby.entity_link_service import entity_link_service
    from moduly.pravni_pozadavky.constants import (
        CHANGE_NEW,
        CHANGE_UPDATED,
        DOCUMENT_TYPE_ZAKON,
        SECTION_PARAGRAPH,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_export_context_service import (
        legal_change_export_context_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_impact_service import (
        legal_change_impact_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_change_service import legal_change_service
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalChangeServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from core.shared.modely.entity_link import EntityLink
        from moduly.pravni_pozadavky.modely.legal_change import LegalChange
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(EntityLink))
            session.execute(delete(LegalChange))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

    def _create_document(self, *, title: str = "Zákoník práce"):
        return legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title=title,
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )

    def _create_version(self, document):
        return legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 2024",
        )

    def _create_section(self, document, version, **kwargs):
        defaults = {
            "legal_document_id": document.id,
            "legal_document_version_id": version.id,
            "section_type": SECTION_PARAGRAPH,
            "paragraph": "90",
            "title": "Školení zaměstnanců",
            "text": "Zaměstnavatel zajistí školení.",
        }
        defaults.update(kwargs)
        return legal_section_service.create(**defaults)

    def _create_change(self, document, **kwargs):
        defaults = {
            "legal_document_id": document.id,
            "change_type": CHANGE_NEW,
            "title": "Nová povinnost školení",
            "description": "Popis změny",
            "published_at": date(2024, 6, 1),
            "effective_from": date(2024, 7, 1),
        }
        defaults.update(kwargs)
        return legal_change_service.create(**defaults)

    def test_create_change(self) -> None:
        document = self._create_document()
        change = self._create_change(document)

        self.assertIsNotNone(change.id)
        self.assertEqual(change.legal_document_id, document.id)
        self.assertEqual(change.title, "Nová povinnost školení")
        self.assertFalse(change.evaluated)
        self.assertTrue(change.active)

    def test_update_change(self) -> None:
        document = self._create_document()
        change = self._create_change(document)
        updated = legal_change_service.update(
            change.id,
            legal_document_id=document.id,
            change_type=CHANGE_UPDATED,
            title="Upravený název",
            description="Upravený popis",
            active=True,
        )

        assert updated is not None
        self.assertEqual(updated.change_type, CHANGE_UPDATED)
        self.assertEqual(updated.title, "Upravený název")
        self.assertEqual(updated.description, "Upravený popis")

    def test_deactivate_and_restore_change(self) -> None:
        document = self._create_document()
        change = self._create_change(document)

        deactivated = legal_change_service.deactivate(change.id)
        assert deactivated is not None
        self.assertFalse(deactivated.active)

        active_only = legal_change_service.list_all()
        self.assertEqual(active_only, [])

        restored = legal_change_service.restore(change.id)
        assert restored is not None
        self.assertTrue(restored.active)

    def test_list_changes_by_document(self) -> None:
        first_document = self._create_document(title="První")
        second_document = self._create_document(title="Druhý")
        first_change = self._create_change(first_document, title="Změna 1")
        self._create_change(second_document, title="Změna 2")

        changes = legal_change_service.list_by_document(first_document.id)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].id, first_change.id)

    def test_list_changes_by_version(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        change = self._create_change(
            document,
            legal_document_version_id=version.id,
            title="Změna verze",
        )

        changes = legal_change_service.list_by_version(version.id)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].id, change.id)

    def test_list_changes_by_section(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_section(document, version)
        change = self._create_change(
            document,
            legal_document_version_id=version.id,
            legal_section_id=section.id,
            title="Změna ustanovení",
        )

        changes = legal_change_service.list_by_section(section.id)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].id, change.id)

    def test_mark_evaluated(self) -> None:
        document = self._create_document()
        change = self._create_change(document)

        evaluated = legal_change_service.mark_evaluated(
            change.id,
            evaluated_by="Jan Novák",
            note="Vyhodnoceno na poradě",
        )
        assert evaluated is not None
        self.assertTrue(evaluated.evaluated)
        self.assertIsNotNone(evaluated.evaluated_at)
        self.assertEqual(evaluated.evaluated_by, "Jan Novák")
        self.assertEqual(evaluated.note, "Vyhodnoceno na poradě")

    def test_mark_unevaluated(self) -> None:
        document = self._create_document()
        change = self._create_change(document)
        legal_change_service.mark_evaluated(change.id, evaluated_by="Jan Novák")

        unevaluated = legal_change_service.mark_unevaluated(change.id)
        assert unevaluated is not None
        self.assertFalse(unevaluated.evaluated)
        self.assertIsNone(unevaluated.evaluated_at)
        self.assertEqual(unevaluated.evaluated_by, "")

    def test_create_change_requires_title(self) -> None:
        document = self._create_document()
        with self.assertRaises(ValueError):
            legal_change_service.create(
                legal_document_id=document.id,
                change_type=CHANGE_NEW,
                title="   ",
            )

    def test_create_change_requires_change_type(self) -> None:
        document = self._create_document()
        with self.assertRaises(ValueError):
            legal_change_service.create(
                legal_document_id=document.id,
                change_type="   ",
                title="Bez typu",
            )

    def test_create_change_requires_legal_document_id(self) -> None:
        with self.assertRaises(ValueError):
            legal_change_service.create(
                legal_document_id=0,
                change_type=CHANGE_NEW,
                title="Bez předpisu",
            )

    def test_export_context_includes_document_version_section_and_links(self) -> None:
        document = self._create_document(title="Zákon o BOZP")
        version = self._create_version(document)
        section = self._create_section(
            document,
            version,
            paragraph="103",
            title="Školení",
            text="Text ustanovení",
        )
        change = self._create_change(
            document,
            legal_document_version_id=version.id,
            legal_section_id=section.id,
            title="Exportovaná změna",
            description="Popis exportu",
        )
        entity_link_service.create(
            source_type=ENTITY_LEGAL_CHANGE,
            source_id=change.id,
            target_type=ENTITY_LEGAL_REQUIREMENT,
            target_id=42,
            link_type=LINK_RELATED,
            note="Související požadavek",
        )
        entity_link_service.create(
            source_type=ENTITY_LEGAL_CHANGE,
            source_id=change.id,
            target_type=ENTITY_RISK,
            target_id=7,
            link_type=LINK_RELATED,
            note="Související riziko",
        )

        context = legal_change_export_context_service.build_for_change(change.id)
        assert context is not None
        row = context.rows[0]
        self.assertEqual(row.title, "Exportovaná změna")
        self.assertEqual(row.legal_document_id, document.id)
        self.assertEqual(row.legal_document_title, "Zákon o BOZP")
        self.assertEqual(row.legal_document_version_id, version.id)
        self.assertEqual(row.legal_document_version_name, "Verze 2024")
        self.assertEqual(row.legal_section_id, section.id)
        self.assertEqual(row.legal_section_paragraph, "103")
        self.assertEqual(row.legal_section_title, "Školení")
        self.assertEqual(row.legal_section_text, "Text ustanovení")
        self.assertEqual(len(row.links), 2)
        self.assertEqual(row.links[0].target_type, ENTITY_LEGAL_REQUIREMENT)
        self.assertEqual(row.links[1].target_type, ENTITY_RISK)
        self.assertEqual(row.total_impact_count, 2)
        self.assertEqual(row.impact_counts_by_type[ENTITY_LEGAL_REQUIREMENT], 1)
        self.assertEqual(row.impact_counts_by_type[ENTITY_RISK], 1)
        self.assertEqual(len(row.impact_links), 2)
        self.assertTrue(all(link.active for link in row.impact_links))

    def test_change_without_links_has_zero_impacts(self) -> None:
        document = self._create_document()
        change = self._create_change(document)

        summary = legal_change_impact_service.build_summary(change.id)
        assert summary is not None
        self.assertEqual(summary.total_count, 0)
        self.assertEqual(summary.counts_by_type, {})
        self.assertEqual(summary.links, [])

    def test_change_with_multiple_links_returns_correct_total_count(self) -> None:
        document = self._create_document()
        change = self._create_change(document)
        entity_link_service.create(
            source_type=ENTITY_LEGAL_CHANGE,
            source_id=change.id,
            target_type=ENTITY_LEGAL_REQUIREMENT,
            target_id=1,
        )
        entity_link_service.create(
            source_type=ENTITY_LEGAL_CHANGE,
            source_id=change.id,
            target_type=ENTITY_TASK,
            target_id=2,
        )
        entity_link_service.create(
            source_type=ENTITY_LEGAL_CHANGE,
            source_id=change.id,
            target_type=ENTITY_RISK,
            target_id=3,
        )

        summary = legal_change_impact_service.build_summary(change.id)
        assert summary is not None
        self.assertEqual(summary.total_count, 3)
        self.assertEqual(len(summary.links), 3)

    def test_impact_counts_by_target_type(self) -> None:
        document = self._create_document()
        change = self._create_change(document)
        entity_link_service.create(
            source_type=ENTITY_LEGAL_CHANGE,
            source_id=change.id,
            target_type=ENTITY_LEGAL_REQUIREMENT,
            target_id=10,
        )
        entity_link_service.create(
            source_type=ENTITY_LEGAL_CHANGE,
            source_id=change.id,
            target_type=ENTITY_LEGAL_REQUIREMENT,
            target_id=11,
        )
        entity_link_service.create(
            source_type=ENTITY_LEGAL_CHANGE,
            source_id=change.id,
            target_type=ENTITY_RISK,
            target_id=20,
        )

        summary = legal_change_impact_service.build_summary(change.id)
        assert summary is not None
        self.assertEqual(summary.counts_by_type[ENTITY_LEGAL_REQUIREMENT], 2)
        self.assertEqual(summary.counts_by_type[ENTITY_RISK], 1)

    def test_inactive_links_are_excluded_from_impacts(self) -> None:
        document = self._create_document()
        change = self._create_change(document)
        active_link = entity_link_service.create(
            source_type=ENTITY_LEGAL_CHANGE,
            source_id=change.id,
            target_type=ENTITY_TASK,
            target_id=5,
        )
        inactive_link = entity_link_service.create(
            source_type=ENTITY_LEGAL_CHANGE,
            source_id=change.id,
            target_type=ENTITY_RISK,
            target_id=6,
        )
        entity_link_service.deactivate(inactive_link.id)

        summary = legal_change_impact_service.build_summary(change.id)
        assert summary is not None
        self.assertEqual(summary.total_count, 1)
        self.assertEqual(summary.links[0].target_type, ENTITY_TASK)
        self.assertEqual(summary.links[0].target_id, active_link.target_id)
        self.assertNotIn(ENTITY_RISK, summary.counts_by_type)

    def test_export_includes_impacts(self) -> None:
        document = self._create_document()
        change = self._create_change(document)
        entity_link_service.create(
            source_type=ENTITY_LEGAL_CHANGE,
            source_id=change.id,
            target_type=ENTITY_LEGAL_REQUIREMENT,
            target_id=99,
            note="Dopad na požadavek",
        )

        context = legal_change_export_context_service.build_for_change(change.id)
        assert context is not None
        row = context.rows[0]
        self.assertEqual(row.total_impact_count, 1)
        self.assertEqual(row.impact_counts_by_type[ENTITY_LEGAL_REQUIREMENT], 1)
        self.assertEqual(len(row.impact_links), 1)
        self.assertEqual(row.impact_links[0].target_id, 99)
        self.assertEqual(row.impact_links[0].note, "Dopad na požadavek")
        self.assertTrue(row.impact_links[0].active)


if __name__ == "__main__":
    unittest.main()
