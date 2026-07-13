"""Fáze 98d – přehled použití ustanovení v řídicích procesech."""

from __future__ import annotations

import importlib
import tempfile
import unittest
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

    from moduly.pravni_pozadavky.constants import (
        DOCUMENT_TYPE_VYHLASKA,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
        legal_section_provision_label,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_process_usage_service import (
        legal_document_process_usage_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalDocumentProcessUsagePhase98dTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Vyhláška č. 79/2013 Sb.",
            number="79",
            year=2013,
            short_title="V79",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
        )
        self.document = document
        self.paragraph_12 = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="12",
            title="§ 12",
            sort_order=1,
        )
        self.paragraph_13 = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="13",
            title="§ 13",
            sort_order=2,
        )
        self.paragraph_5a = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="5a",
            title="§ 5a",
            sort_order=3,
        )
        self.subsection_5a_1 = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=self.paragraph_5a.id,
            section_number="1",
            text="Odstavec 1",
            sort_order=4,
        )
        self.sections_by_id = legal_section_service.build_sections_map(
            legal_section_service.list_by_version(version.id),
        )

    def _row_for(self, section_id: int):
        rows = legal_document_process_usage_service.list_process_usage_for_document(
            self.document.id,
        )
        for row in rows:
            if row.section_id == section_id:
                return row
        self.fail(f"Section {section_id} not found in usage rows")

    def test_section_assigned_to_single_process(self) -> None:
        process = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-003",
            source_section_ids=[self.paragraph_12.id],
        )

        row = self._row_for(self.paragraph_12.id)

        self.assertEqual(
            row.provision_label,
            legal_section_provision_label(self.paragraph_12, sections_by_id=self.sections_by_id),
        )
        self.assertTrue(row.is_assigned)
        self.assertEqual(len(row.processes), 1)
        self.assertEqual(row.processes[0].requirement_id, process.id)
        self.assertEqual(row.processes[0].process_code, "P-003")
        self.assertEqual(row.processes[0].process_name, "Řízení rizik")
        self.assertEqual(row.processes[0].display_label, "P-003 – Řízení rizik")

    def test_section_assigned_to_multiple_processes(self) -> None:
        process_one = legal_requirement_service.create_requirement(
            title="Koordinace zaměstnavatelů a řízení dodavatelů",
            process_code="P-004",
            source_section_ids=[self.subsection_5a_1.id],
        )
        process_two = legal_requirement_service.create_requirement(
            title="Řízení zdravotní způsobilosti",
            process_code="P-009",
            source_section_ids=[self.subsection_5a_1.id],
        )

        row = self._row_for(self.subsection_5a_1.id)

        self.assertTrue(row.is_assigned)
        self.assertEqual(
            {item.requirement_id for item in row.processes},
            {process_one.id, process_two.id},
        )
        self.assertEqual(
            [item.process_code for item in row.processes],
            ["P-004", "P-009"],
        )

    def test_unassigned_section_is_marked(self) -> None:
        row = self._row_for(self.paragraph_13.id)

        self.assertFalse(row.is_assigned)
        self.assertEqual(row.processes, ())

    def test_ignores_inactive_process(self) -> None:
        inactive = legal_requirement_service.create_requirement(
            title="Neaktivní proces",
            process_code="P-099",
            source_section_ids=[self.paragraph_13.id],
            active=False,
        )
        active = legal_requirement_service.create_requirement(
            title="Aktivní proces",
            process_code="P-010",
            source_section_ids=[self.paragraph_13.id],
        )

        row = self._row_for(self.paragraph_13.id)

        self.assertTrue(row.is_assigned)
        self.assertEqual(len(row.processes), 1)
        self.assertEqual(row.processes[0].requirement_id, active.id)
        self.assertNotIn(inactive.id, {item.requirement_id for item in row.processes})

    def test_deduplicates_process_linked_via_junction_and_legacy_field(self) -> None:
        process = legal_requirement_service.create_requirement(
            title="Jednotný proces",
            process_code="P-011",
            source_section_id=self.paragraph_12.id,
            source_section_ids=[self.paragraph_12.id],
        )

        row = self._row_for(self.paragraph_12.id)

        self.assertEqual(len(row.processes), 1)
        self.assertEqual(row.processes[0].requirement_id, process.id)

    def test_returns_empty_without_current_version(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Bez verze",
            number="1",
            year=2024,
            short_title="BV",
        )

        rows = legal_document_process_usage_service.list_process_usage_for_document(document.id)

        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
