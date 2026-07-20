"""BUILDER-COORD-1b – finální doladění koordinačního protokolu."""

from __future__ import annotations

import unittest

from moduly.koordinace_bozp.constants import (
    PROTOCOL_FINAL_PROVISIONS_COPIES,
    PROTOCOL_MAIN_RISKS_VIA_PBP,
)
from moduly.koordinace_bozp.sluzby.coordination_protocol_document import (
    BLOCK_STYLE_EMPLOYER_ABBR,
    build_protocol_document,
    render_blocks_to_plain_lines,
)


def _base_data(**overrides) -> dict:
    data = {
        "basics": {
            "coordination_number": "K-2026-1b",
            "subject": "1b",
            "meeting_date": "2026-07-20",
            "place": "Praha",
        },
        "employers": [
            {
                "id": 1,
                "abbreviation": "ZX-ZF",
                "company_name": "ZX - Zkušební firma, a.s.",
                "display_name": "ZX-ZF – ZX - Zkušební firma, a.s.",
                "is_main": True,
            },
            {
                "id": 2,
                "abbreviation": "TD",
                "company_name": "Testovací dodavatel s.r.o.",
                "display_name": "TD – Testovací dodavatel s.r.o.",
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
                        "full_name": "",
                        "role": "Hradlař T1",
                        "phone": "",
                        "email": "",
                    },
                ],
            }
        ],
        "coordinator": None,
        "workplaces": [],
        "activities_by_employer": [
            {
                "employer": {
                    "id": 1,
                    "abbreviation": "ZX-ZF",
                    "company_name": "ZX - Zkušební firma, a.s.",
                    "display_name": "ZX-ZF – ZX - Zkušební firma, a.s.",
                    "is_main": True,
                },
                "activities": [{"activity_name": "Údržba", "workplace_label": ""}],
            }
        ],
        "measures_by_category": [],
        "coordination_agreement": {},
        "contacts_by_type": [
            {
                "contact_type_label": "Technické požadavky",
                "employer_groups": [
                    {
                        "employer_label": "ZX-ZF",
                        "contacts": [
                            {
                                "custom_name": "",
                                "role": "Hradlař T1",
                                "phone": "",
                                "email": "",
                            }
                        ],
                    }
                ],
            }
        ],
        "contacts": [],
        "emergency_procedures": {},
        "risk_handovers": [
            {
                "employer": {
                    "id": 2,
                    "abbreviation": "TD",
                    "company_name": "Testovací dodavatel s.r.o.",
                    "display_name": "TD – Testovací dodavatel s.r.o.",
                    "is_main": False,
                },
                "handover_status_label": "Rizika budou zaslána e-mailem.",
            }
        ],
        "pbp_snapshot": {
            "content_lines": ["Intro", "1. Pravidlo"]
        },
        "attachments_by_group": [],
    }
    data.update(overrides)
    return data


class BuilderCoord1bProtocolTestCase(unittest.TestCase):
    def _lines(self, data: dict) -> list[str]:
        document = build_protocol_document(data)
        return render_blocks_to_plain_lines(document["blocks"])

    def test_employer_group_heading_abbr_only(self) -> None:
        lines = self._lines(_base_data())
        joined = "\n".join(lines)
        self.assertIn("ZX-ZF", lines)
        self.assertIn("TD", lines)
        # Skupinové nadpisy bez celého názvu pod zkratkou.
        participants_idx = lines.index("Účastníci koordinační schůzky:")
        activities_idx = lines.index("Činnosti na pracovišti:")
        appendix_b_idx = lines.index(
            "Příloha B – Přehled předaných rizik zaměstnavatelů"
        )
        for start, end in (
            (participants_idx, activities_idx),
            (activities_idx, lines.index("Závěry z koordinační schůzky zástupců zúčastněných zaměstnavatelů:")),
            (appendix_b_idx, len(lines)),
        ):
            chunk = "\n".join(lines[start:end])
            self.assertNotIn("ZX - Zkušební firma, a.s.", chunk)
            self.assertNotIn("Testovací dodavatel s.r.o.", chunk)

        # Titulní seznam zaměstnavatelů stále obsahuje celý název.
        self.assertIn("ZX - Zkušební firma, a.s.", joined)

        document = build_protocol_document(_base_data())
        abbr_blocks = [
            block
            for block in document["blocks"]
            if block.get("style") == BLOCK_STYLE_EMPLOYER_ABBR
        ]
        self.assertTrue(all(block.get("bold") for block in abbr_blocks))

    def test_main_employer_pbp_sentence_when_appendix_a_present(self) -> None:
        expected = PROTOCOL_MAIN_RISKS_VIA_PBP.format(abbreviation="ZX-ZF")
        lines = self._lines(_base_data())
        self.assertIn(expected, lines)

        without_pbp = _base_data(pbp_snapshot=None)
        lines_without = self._lines(without_pbp)
        self.assertNotIn(expected, lines_without)
        self.assertNotIn("přílohu A této dohody", "\n".join(lines_without))

    def test_participant_and_contact_without_orphan_dash(self) -> None:
        lines = self._lines(_base_data())
        self.assertIn("• Pavlína Nová – Mistr haly", lines)
        self.assertIn("• Hradlař T1", lines)
        self.assertNotIn("• — Hradlař T1", lines)
        self.assertNotIn("• — – Hradlař T1", lines)

    def test_copy_count_matches_employer_count(self) -> None:
        for count in (2, 4, 6):
            employers = [
                {
                    "id": index,
                    "abbreviation": f"F{index}",
                    "company_name": f"Firma {index}",
                    "display_name": f"F{index} – Firma {index}",
                    "is_main": index == 1,
                }
                for index in range(1, count + 1)
            ]
            lines = self._lines(_base_data(employers=employers, risk_handovers=[]))
            expected = PROTOCOL_FINAL_PROVISIONS_COPIES.format(count=count)
            self.assertIn(expected, lines)
            self.assertNotIn("podle počtu zúčastněných stran", "\n".join(lines))
            self.assertNotIn("ve dvou", "\n".join(lines))


if __name__ == "__main__":
    unittest.main()
