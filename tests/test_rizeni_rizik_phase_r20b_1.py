"""HOTFIX R20b.1 – normalizace právních odkazů AI vůči RPP."""

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

    from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
        legal_requirement_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_legal_requirement_resolver import (
        LegalRequirementMatchKind,
        expand_legal_abbreviations,
        hazard_catalog_legal_requirement_resolver,
        normalize_legal_citation_text,
        parse_legal_citation,
    )


class LegalCitationNormalizationR20b1TestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(LegalRequirement))
            session.commit()

        self.nv_378 = legal_requirement_service.create_requirement(
            title="Bezpečnost provozu",
            process_code="P-378",
            regulation_name="Nařízení vlády č. 378/2001 Sb.",
            regulation_number="378/2001 Sb.",
        )
        self.vyhl_50 = legal_requirement_service.create_requirement(
            title="Odborná způsobilost",
            process_code="P-050",
            regulation_name="Vyhláška č. 50/1978 Sb.",
            regulation_number="50/1978 Sb.",
        )
        self.zak_262 = legal_requirement_service.create_requirement(
            title="Zákoník práce",
            process_code="P-262",
            regulation_name="Zákon č. 262/2006 Sb.",
            regulation_number="262/2006 Sb.",
        )
        self.nv_other_year = legal_requirement_service.create_requirement(
            title="Jiný rok",
            process_code="P-379",
            regulation_name="Nařízení vlády č. 378/2002 Sb.",
            regulation_number="378/2002 Sb.",
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
        match = hazard_catalog_legal_requirement_resolver.resolve("NV č. 378/2001 Sb.")
        self.assertEqual(match.kind, LegalRequirementMatchKind.EXACT)
        self.assertEqual(match.requirement_id, self.nv_378.id)

    def test_nv_without_cislo_matches_same_regulation(self) -> None:
        match = hazard_catalog_legal_requirement_resolver.resolve("NV 378/2001")
        self.assertEqual(match.kind, LegalRequirementMatchKind.EXACT)
        self.assertEqual(match.requirement_id, self.nv_378.id)

    def test_vyhlaska_abbreviation(self) -> None:
        match = hazard_catalog_legal_requirement_resolver.resolve("vyhl. č. 50/1978 Sb.")
        self.assertEqual(match.kind, LegalRequirementMatchKind.EXACT)
        self.assertEqual(match.requirement_id, self.vyhl_50.id)

    def test_zakon_abbreviation(self) -> None:
        match = hazard_catalog_legal_requirement_resolver.resolve("zák. č. 262/2006 Sb.")
        self.assertEqual(match.kind, LegalRequirementMatchKind.EXACT)
        self.assertEqual(match.requirement_id, self.zak_262.id)

    def test_same_number_different_year_is_not_false_match(self) -> None:
        match = hazard_catalog_legal_requirement_resolver.resolve("NV č. 378/2001 Sb.")
        self.assertEqual(match.requirement_id, self.nv_378.id)
        other = hazard_catalog_legal_requirement_resolver.resolve("NV 378/2002")
        self.assertEqual(other.kind, LegalRequirementMatchKind.EXACT)
        self.assertEqual(other.requirement_id, self.nv_other_year.id)
        self.assertNotEqual(match.requirement_id, other.requirement_id)

    def test_ambiguous_when_multiple_processes_share_citation(self) -> None:
        second = legal_requirement_service.create_requirement(
            title="Další proces ke stejnému NV",
            process_code="P-380",
            regulation_name="Nařízení vlády č. 378/2001 Sb.",
            regulation_number="378/2001 Sb.",
        )
        match = hazard_catalog_legal_requirement_resolver.resolve("NV 378/2001")
        self.assertEqual(match.kind, LegalRequirementMatchKind.AMBIGUOUS)
        candidate_ids = {item[0] for item in match.candidates}
        self.assertEqual(candidate_ids, {self.nv_378.id, second.id})
