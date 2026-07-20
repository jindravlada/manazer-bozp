"""BUILDER-COORD-1a – typografické doladění koordinačního protokolu."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from moduly.koordinace_bozp.constants import (
    PROTOCOL_COORDINATOR_DETAILS_TITLE,
    PROTOCOL_PAGE_FOOTER,
)
from moduly.koordinace_bozp.sluzby.coordination_protocol_document import (
    BLOCK_KIND_BULLET,
    BLOCK_KIND_INDENTED,
    BLOCK_KIND_PBP_RULE,
    BLOCK_STYLE_EMPLOYER_ABBR,
    build_protocol_document,
    parse_ppe_items,
    render_blocks_to_plain_lines,
)
from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
    coordination_protocol_odt_renderer,
)


def _sample_data() -> dict:
    return {
        "basics": {
            "coordination_number": "K-2026-100",
            "subject": "Typografie 1a",
            "meeting_date": "2026-07-20",
            "place": "Praha",
        },
        "employers": [
            {
                "id": 1,
                "abbreviation": "ZX-ZF",
                "company_name": "ZX - Zkušební firma, a.s.",
                "display_name": "ZX-ZF – ZX - Zkušební firma, a.s.",
                "ico": "111",
                "address": "Depo 1",
                "is_main": True,
            },
            {
                "id": 2,
                "abbreviation": "TD",
                "company_name": "Testovací dodavatel s.r.o.",
                "display_name": "TD – Testovací dodavatel s.r.o.",
                "ico": "222",
                "address": "",
                "is_main": False,
            },
            {
                "id": 3,
                "abbreviation": "BEZ",
                "company_name": "Bez účastníka s.r.o.",
                "display_name": "BEZ – Bez účastníka s.r.o.",
                "ico": "333",
                "is_main": False,
            },
        ],
        "participants_by_employer": [
            {
                "employer": {
                    "id": 1,
                    "abbreviation": "ZX-ZF",
                    "company_name": "ZX - Zkušební firma, a.s.",
                    "display_name": "ZX-ZF – ZX - Zkušební firma, a.s.",
                    "is_main": True,
                },
                "participants": [
                    {
                        "full_name": "Pavlína Nová",
                        "role": "Mistr haly",
                        "phone": "",
                        "email": "",
                    },
                    {
                        "full_name": "Druhý Účastník",
                        "role": "Technik",
                        "phone": "",
                        "email": "",
                    },
                ],
            },
            {
                "employer": {
                    "id": 2,
                    "abbreviation": "TD",
                    "company_name": "Testovací dodavatel s.r.o.",
                    "display_name": "TD – Testovací dodavatel s.r.o.",
                    "is_main": False,
                },
                "participants": [
                    {
                        "full_name": "Alfréd Paša",
                        "role": "Technik",
                        "phone": "",
                        "email": "",
                    }
                ],
            },
        ],
        "coordinator": {
            "full_name": "Jan Koordinátor",
            "employer_name": "ZX - Zkušební firma, a.s.",
            "role": "koordinátor BOZP",
            "phone": "+420111",
            "email": "jan@example.com",
            "note": "Kontaktovat před vstupem.",
        },
        "workplaces": [{"label": "Hala 1"}],
        "activities_by_employer": [
            {
                "employer": {
                    "id": 1,
                    "abbreviation": "ZX-ZF",
                    "company_name": "ZX - Zkušební firma, a.s.",
                    "display_name": "ZX-ZF – ZX - Zkušební firma, a.s.",
                    "is_main": True,
                },
                "activities": [
                    {
                        "activity_name": "Údržba",
                        "workplace_label": "Hala 1",
                    }
                ],
            }
        ],
        "measures_by_category": [],
        "coordination_agreement": {
            "work_intent_information_text": "Informovat o vstupu.",
            "ppe_text": "a) přilba\nb) ochranný oděv\nc) výstražná vesta",
            "workplace_handover_text": "",
            "final_provisions_text": "",
        },
        "contacts_by_type": [
            {
                "contact_type": "technical_requirements",
                "contact_type_label": "Technické požadavky",
                "employer_groups": [
                    {
                        "employer_label": "ZX-ZF",
                        "employer_name": "ZX - Zkušební firma, a.s.",
                        "contacts": [
                            {
                                "custom_name": "Pavel Techničkák",
                                "role": "Odborný poradce",
                                "phone": "725 752 725",
                                "email": "pavel@example.com",
                            }
                        ],
                    }
                ],
            }
        ],
        "contacts": [],
        "emergency_procedures": {
            "emergency_reporting": "Hlásit",
            "accident_reporting": "",
            "fire_reporting": "",
            "evacuation_instructions": "",
        },
        "risk_handovers": [
            {
                "employer": {
                    "id": 2,
                    "abbreviation": "TD",
                    "company_name": "Testovací dodavatel s.r.o.",
                    "display_name": "TD – Testovací dodavatel s.r.o.",
                    "is_main": False,
                },
                "handover_status": "will_send_email",
                "handover_status_label": "Rizika budou zaslána e-mailem.",
            }
        ],
        "pbp_snapshot": {
            "content_lines": [
                "Dodržujte následující pravidla bezpečné práce.",
                "",
                "1. První pravidlo s delším textem.",
                "2. Druhé pravidlo s delším textem.",
            ]
        },
        "attachments_by_group": [],
    }


class BuilderCoord1aTypographyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="builder-coord-1a-"))
        self.data = _sample_data()
        self.document = build_protocol_document(self.data)
        self.lines = render_blocks_to_plain_lines(self.document["blocks"])
        self.joined = "\n".join(self.lines)

    def test_employer_split_on_two_lines(self) -> None:
        self.assertIn("ZX-ZF", self.lines)
        self.assertIn("ZX - Zkušební firma, a.s.", self.lines)
        self.assertNotIn("ZX-ZF – ZX - Zkušební firma, a.s.", self.joined)
        self.assertNotIn("ZX-ZF – ZX - Zkušební firma, a.s.:", self.joined)

        abbr_blocks = [
            block
            for block in self.document["blocks"]
            if block.get("style") == BLOCK_STYLE_EMPLOYER_ABBR
            and block.get("text") == "ZX-ZF"
        ]
        self.assertTrue(abbr_blocks)
        self.assertTrue(abbr_blocks[0].get("bold"))

    def test_contacts_hierarchy(self) -> None:
        self.assertIn("Technické požadavky", self.lines)
        self.assertIn("• Pavel Techničkák", self.lines)
        self.assertIn("  Odborný poradce", self.lines)
        self.assertIn("  Tel.: 725 752 725", self.lines)
        self.assertIn("  E-mail: pavel@example.com", self.lines)
        kinds = [block.get("kind") for block in self.document["blocks"]]
        self.assertIn(BLOCK_KIND_BULLET, kinds)
        self.assertIn(BLOCK_KIND_INDENTED, kinds)

    def test_coordinator_highlighted_before_legal_text(self) -> None:
        self.assertIn(PROTOCOL_COORDINATOR_DETAILS_TITLE, self.lines)
        idx_title = self.lines.index(PROTOCOL_COORDINATOR_DETAILS_TITLE)
        idx_name = self.lines.index("Jméno: Jan Koordinátor")
        idx_alias = next(
            i
            for i, line in enumerate(self.lines)
            if "koordinátor BOZP" in line and line.startswith("(")
        )
        self.assertLess(idx_title, idx_name)
        self.assertLess(idx_name, idx_alias)
        self.assertIn("Další informace:", self.lines)

    def test_risks_separated_by_employer(self) -> None:
        self.assertIn("TD", self.lines)
        self.assertIn("Rizika budou zaslána e-mailem.", self.lines)
        self.assertNotIn("předala rizika", self.joined)
        self.assertNotIn("TD předala rizika", self.joined)

    def test_ppe_uses_bullets(self) -> None:
        self.assertEqual(
            parse_ppe_items("a) přilba\nb) ochranný oděv\nc) výstražná vesta"),
            ["přilba", "ochranný oděv", "výstražná vesta"],
        )
        self.assertIn("• přilba", self.lines)
        self.assertIn("• ochranný oděv", self.lines)
        self.assertIn("• výstražná vesta", self.lines)
        self.assertNotIn("a) přilba", self.joined)

    def test_pbp_rules_emphasized(self) -> None:
        pbp_blocks = [
            block
            for block in self.document["blocks"]
            if block.get("kind") == BLOCK_KIND_PBP_RULE
        ]
        self.assertGreaterEqual(len(pbp_blocks), 2)
        self.assertEqual(pbp_blocks[0].get("level"), 1)
        runs = pbp_blocks[0].get("runs") or []
        self.assertTrue(runs)
        self.assertTrue(runs[0][1])
        self.assertIn("1. První pravidlo s delším textem.", self.lines)
        self.assertIn("2. Druhé pravidlo s delším textem.", self.lines)

    def test_signatures_from_first_participants(self) -> None:
        self.assertIn("Za ZX-ZF", self.lines)
        self.assertIn("Za TD", self.lines)
        self.assertIn("Za BEZ", self.lines)
        self.assertIn("Pavlína Nová", self.lines)
        self.assertIn("Mistr haly", self.lines)
        self.assertIn("Alfréd Paša", self.lines)
        self.assertIn("..............................................", self.joined)
        self.assertNotIn("jméno a příjmení, funkce", self.joined)
        # Podpis bere jen prvního účastníka zaměstnavatele.
        za_sdkd = self.lines.index("Za ZX-ZF")
        za_td = self.lines.index("Za TD")
        signature_chunk = self.lines[za_sdkd:za_td]
        self.assertIn("Pavlína Nová", signature_chunk)
        self.assertNotIn("Druhý Účastník", signature_chunk)

    def test_odt_footer_page_numbers(self) -> None:
        target = self.tmp / "footer.odt"
        payload = dict(self.data)
        payload["document"] = self.document
        coordination_protocol_odt_renderer.render(
            target,
            protocol_data=payload,
        )
        with zipfile.ZipFile(target) as zin:
            styles = zin.read("styles.xml").decode("utf-8")
            content = zin.read("content.xml").decode("utf-8")
        self.assertIn(PROTOCOL_PAGE_FOOTER, styles)
        self.assertIn("text:page-number", styles)
        self.assertIn("text:page-count", styles)
        self.assertIn('fo:text-align="end"', styles)
        self.assertIn("style:master-page", styles)
        self.assertIn("ProtocolBold", content)
        self.assertIn("• přilba", content)
        self.assertIn("Pavlína Nová", content)


if __name__ == "__main__":
    unittest.main()
