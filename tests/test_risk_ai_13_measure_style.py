"""RISK-AI-13: rozlišení stylu Zásad bezpečné práce a kontrolních otázek."""

from __future__ import annotations

import unittest

from core.ai_oponentni.sluzby.prompt_builder import (
    MEASURE_FORMULATION_STYLE_HEADING,
    build_ai_peer_review_prompt,
    build_catalog_source_ai_peer_review_prompt,
    measure_formulation_style_section,
)


class RiskAi13MeasureStylePromptTestCase(unittest.TestCase):
    def test_style_section_distinguishes_principles_and_followups(self) -> None:
        text = "\n".join(measure_formulation_style_section())
        self.assertTrue(text.startswith(MEASURE_FORMULATION_STYLE_HEADING))
        self.assertIn("A) Zásady bezpečné práce", text)
        self.assertIn("B) Kontrolní otázky pro revizi rizik", text)
        self.assertIn("C) Kontrola významu před návrhem úpravy", text)
        self.assertIn("Zásady bezpečné práce jsou určeny zaměstnanci", text)
        self.assertIn("umožňovat odpověď Ano / Ne / Netýká se", text)
        self.assertIn("Kontrolní otázka není úkol", text)
        self.assertIn("Při jízdě na stanovišti drážního vozidla se držte určeného madla.", text)
        self.assertIn(
            "Jsou kontroly, revize a údržba prováděny ve stanovených termínech?",
            text,
        )
        self.assertIn("Je text pokynem zaměstnanci?", text)
        self.assertIn("takový návrh nesmíte navrhnout", text)

    def test_style_section_does_not_force_employee_voice_on_followups(self) -> None:
        text = "\n".join(measure_formulation_style_section())
        self.assertNotIn(
            "Každé opatření formulujte jako jednoznačný pokyn zaměstnanci",
            text,
        )
        self.assertNotIn(
            "Nepoužívejte administrativní formulace bez určení adresáta",
            text,
        )
        self.assertIn("neobsahovat odpovědnou osobu ani termín", text)

    def test_identification_and_catalog_prompts_include_distinction(self) -> None:
        identification = build_ai_peer_review_prompt()
        catalog = build_catalog_source_ai_peer_review_prompt()
        for prompt in (identification, catalog):
            self.assertIn(MEASURE_FORMULATION_STYLE_HEADING, prompt)
            self.assertIn("umožňovat odpověď Ano / Ne / Netýká se", prompt)
            self.assertIn("Zásady bezpečné práce jsou určeny zaměstnanci", prompt)
            self.assertIn("Je text pokynem zaměstnanci?", prompt)
        self.assertIn("schema 2.0", catalog.casefold())
        self.assertIn("measure_recommendations", catalog)


if __name__ == "__main__":
    unittest.main()
