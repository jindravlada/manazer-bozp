"""HOTFIX R20b.1 / R19b – normalizace právních odkazů AI vůči předpisům."""

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
        DOCUMENT_TYPE_NARIZENI_VLADY,
        DOCUMENT_TYPE_VYHLASKA,
        DOCUMENT_TYPE_ZAKON,
    )
    from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.rizeni_rizik.sluzby.hazard_catalog_legal_requirement_resolver import (
        LegalDocumentMatchKind,
        expand_legal_abbreviations,
        hazard_catalog_legal_document_resolver,
        normalize_legal_citation_text,
        parse_legal_citation,
    )


class LegalCitationNormalizationR20b1TestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(LegalDocument))
            session.commit()

        self.nv_378 = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            number="378",
            year=2001,
            title="Bezpečnost provozu",
        )
        self.vyhl_50 = legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            number="50",
            year=1978,
            title="Odborná způsobilost",
        )
        self.zak_262 = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            number="262",
            year=2006,
            title="Zákoník práce",
        )
        self.nv_other_year = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            number="378",
            year=2002,
            title="Jiný rok",
        )

    def test_expand_abbreviations(self) -> None:
        self.assertEqual(
            expand_legal_abbreviations("NV č. 378/2001 Sb."),
            "Nařízení vlády 378/2001 Sb.",
        )
        self.assertEqual(
            expand_legal_abbreviations("vyhl. č. 50/1978 Sb."),
            "Vyhláška 50/1978 Sb.",
        )
        self.assertEqual(
            expand_legal_abbreviations("zák. č. 262/2006 Sb."),
            "Zákon 262/2006 Sb.",
        )

    def test_normalize_ignores_current_wording_and_noise(self) -> None:
        left = normalize_legal_citation_text(
            "NV č. 378/2001 Sb. v aktuálním znění",
        )
        right = normalize_legal_citation_text("Nařízení vlády č. 378/2001 Sb.")
        self.assertEqual(left, right)

    def test_parse_citation_number_and_year(self) -> None:
        parsed = parse_legal_citation("NV 378/2001")
        assert parsed is not None
        self.assertEqual(parsed.number, "378")
        self.assertEqual(parsed.year, "2001")
        self.assertEqual(parsed.regulation_type, "narizeni_vlady")

    def test_nv_with_cislo_matches_full_name(self) -> None:
        match = hazard_catalog_legal_document_resolver.resolve("NV č. 378/2001 Sb.")
        self.assertEqual(match.kind, LegalDocumentMatchKind.EXACT)
        self.assertEqual(match.document_id, self.nv_378.id)

    def test_nv_without_cislo_matches_same_regulation(self) -> None:
        match = hazard_catalog_legal_document_resolver.resolve("NV 378/2001")
        self.assertEqual(match.kind, LegalDocumentMatchKind.EXACT)
        self.assertEqual(match.document_id, self.nv_378.id)

    def test_vyhlaska_abbreviation(self) -> None:
        match = hazard_catalog_legal_document_resolver.resolve("vyhl. č. 50/1978 Sb.")
        self.assertEqual(match.kind, LegalDocumentMatchKind.EXACT)
        self.assertEqual(match.document_id, self.vyhl_50.id)

    def test_zakon_abbreviation(self) -> None:
        match = hazard_catalog_legal_document_resolver.resolve("zák. č. 262/2006 Sb.")
        self.assertEqual(match.kind, LegalDocumentMatchKind.EXACT)
        self.assertEqual(match.document_id, self.zak_262.id)

    def test_same_number_different_year_is_not_false_match(self) -> None:
        match = hazard_catalog_legal_document_resolver.resolve("NV č. 378/2001 Sb.")
        self.assertEqual(match.document_id, self.nv_378.id)
        other = hazard_catalog_legal_document_resolver.resolve("NV 378/2002")
        self.assertEqual(other.kind, LegalDocumentMatchKind.EXACT)
        self.assertEqual(other.document_id, self.nv_other_year.id)
        self.assertNotEqual(match.document_id, other.document_id)

    def test_ambiguous_when_multiple_documents_share_citation(self) -> None:
        second = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            number="378",
            year=2001,
            title="Další předpis ke stejnému NV",
        )
        match = hazard_catalog_legal_document_resolver.resolve("NV 378/2001")
        self.assertEqual(match.kind, LegalDocumentMatchKind.AMBIGUOUS)
        candidate_ids = {item[0] for item in match.candidates}
        self.assertEqual(candidate_ids, {self.nv_378.id, second.id})
