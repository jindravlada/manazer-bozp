"""Fáze R19b – právní vazby zdrojů rizik na právní předpisy."""

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

    from core.database.database_initializer import (
        _migrate_hazard_library_template_legal_links_to_documents,
        initialize_database,
    )

    initialize_database()

    from sqlalchemy import text

    from core.database.session import get_session
    from moduly.pravni_pozadavky.constants import (
        DOCUMENT_TYPE_NARIZENI_VLADY,
        DOCUMENT_TYPE_VYHLASKA,
        DOCUMENT_TYPE_ZAKON,
    )
    from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
    from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
        legal_requirement_service,
    )
    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_ALL
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_legal_link import (
        HazardLibraryTemplateLegalLink,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_legal_requirement_resolver import (
        LegalDocumentMatchKind,
        hazard_catalog_legal_document_resolver,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_legal_requirement_usage_service import (
        hazard_catalog_legal_requirement_usage_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
        HazardCatalogPackageIncorporateError,
        hazard_catalog_package_incorporate_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_legal_link_service import (
        hazard_library_template_legal_link_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from core.ai_oponentni.proposal_package_types import AiProposalPackageLegalLink


class LegalDocumentLinksR19bTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        with get_session() as session:
            session.execute(delete(HazardLibraryTemplateLegalLink))
            session.execute(delete(HazardLibraryTemplate))
            session.execute(delete(LegalRequirement))
            session.execute(delete(LegalDocument))
            session.commit()

        self.nv = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            number="378",
            year=2001,
            title="Nařízení vlády o bezpečnosti práce",
        )
        self.vyhl = legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            number="50",
            year=1978,
            title="Vyhláška o odborné způsobilosti",
        )
        self.zak = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            number="262",
            year=2006,
            title="Zákoník práce",
        )
        self.nv_other_year = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            number="378",
            year=2002,
            title="Jiné NV 378/2002",
        )
        self.template = hazard_library_template_service.create_template(
            name="Zdroj R19b",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )

    def test_nv_citation_matches_legal_document(self) -> None:
        match = hazard_catalog_legal_document_resolver.resolve("NV č. 378/2001 Sb.")
        self.assertEqual(match.kind, LegalDocumentMatchKind.EXACT)
        self.assertEqual(match.document_id, self.nv.id)

    def test_full_name_and_abbreviations(self) -> None:
        self.assertEqual(
            hazard_catalog_legal_document_resolver.resolve(
                "Nařízení vlády č. 378/2001 Sb.",
            ).document_id,
            self.nv.id,
        )
        self.assertEqual(
            hazard_catalog_legal_document_resolver.resolve("vyhl. č. 50/1978 Sb.").document_id,
            self.vyhl.id,
        )
        self.assertEqual(
            hazard_catalog_legal_document_resolver.resolve("zák. č. 262/2006 Sb.").document_id,
            self.zak.id,
        )

    def test_same_number_different_year_is_not_false_match(self) -> None:
        first = hazard_catalog_legal_document_resolver.resolve("NV č. 378/2001 Sb.")
        second = hazard_catalog_legal_document_resolver.resolve("NV 378/2002")
        self.assertEqual(first.document_id, self.nv.id)
        self.assertEqual(second.document_id, self.nv_other_year.id)

    def test_package_resolve_assigns_document_without_dialog(self) -> None:
        document_id = hazard_catalog_package_incorporate_service._resolve_legal_document_id(
            AiProposalPackageLegalLink(reference="NV č. 378/2001 Sb."),
        )
        self.assertEqual(document_id, self.nv.id)

    def test_source_link_to_document_and_usage(self) -> None:
        link = hazard_library_template_legal_link_service.create_link(
            template_id=self.template.id,
            legal_document_id=self.nv.id,
        )
        self.assertEqual(link.legal_document_id, self.nv.id)
        sources = hazard_catalog_legal_requirement_usage_service.list_sources_for_document(
            self.nv.id,
        )
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].template_id, self.template.id)

    def test_process_usage_via_child_documents_dedupes(self) -> None:
        process = legal_requirement_service.create_requirement(
            title="Proces",
            process_code="P-800",
        )
        child_a = legal_requirement_service.create_requirement(
            title="Požadavek A",
            process_code=legal_requirement_service.allocate_child_process_code(process.id),
            parent_requirement_id=process.id,
            legal_document_id=self.nv.id,
        )
        child_b = legal_requirement_service.create_requirement(
            title="Požadavek B",
            process_code=legal_requirement_service.allocate_child_process_code(process.id),
            parent_requirement_id=process.id,
            legal_document_id=self.nv.id,
        )
        self.assertIsNotNone(child_a.id)
        self.assertIsNotNone(child_b.id)

        other = hazard_library_template_service.create_template(
            name="Zdroj jiný",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        hazard_library_template_legal_link_service.create_link(
            template_id=self.template.id,
            legal_document_id=self.nv.id,
        )
        hazard_library_template_legal_link_service.create_link(
            template_id=other.id,
            legal_document_id=self.nv.id,
        )
        sources = hazard_catalog_legal_requirement_usage_service.list_sources_for_process(
            process.id,
        )
        self.assertEqual(len(sources), 2)
        self.assertEqual(
            {item.template_id for item in sources},
            {self.template.id, other.id},
        )

    def test_migration_requirement_link_to_document(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            title="Požadavek k NV",
            process_code="P-801",
            legal_document_id=self.nv.id,
        )
        with get_session() as session:
            session.execute(
                text(
                    """
                    INSERT INTO hazard_library_template_legal_links (
                        template_id,
                        legal_document_id,
                        legal_requirement_id,
                        note,
                        active,
                        sort_order,
                        created_at,
                        updated_at
                    ) VALUES (
                        :template_id,
                        NULL,
                        :requirement_id,
                        '',
                        1,
                        1,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "template_id": self.template.id,
                    "requirement_id": requirement.id,
                },
            )
            session.commit()

        _migrate_hazard_library_template_legal_links_to_documents()

        links = hazard_library_template_legal_link_service.get_for_template(self.template.id)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].legal_requirement_id, requirement.id)
        self.assertEqual(links[0].legal_document_id, self.nv.id)

    def test_ambiguous_documents_raise_for_package(self) -> None:
        legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            number="378",
            year=2001,
            title="Duplicitní NV 378/2001",
        )
        with self.assertRaises(HazardCatalogPackageIncorporateError):
            hazard_catalog_package_incorporate_service._resolve_legal_document_id(
                AiProposalPackageLegalLink(reference="NV 378/2001"),
            )


if __name__ == "__main__":
    unittest.main()
