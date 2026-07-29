"""UX-PBP-VALIDATION-1b: zpřesnění detekce správně formulovaných pravidel."""

from __future__ import annotations

import unittest

from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
    is_unsuitable_employee_rule,
)


class UxPbpValidation1bTestCase(unittest.TestCase):
    def test_negative_imperatives_are_suitable(self) -> None:
        for text in (
            "Neprovádějte zásahy ani úpravy elektrické instalace bez příslušného oprávnění.",
            "Nevstupujte do kolejiště bez souhlasu výpravčího.",
            "Nepoužívejte poškozené elektrické nářadí.",
            "Neodstraňujte ochranné kryty za chodu stroje.",
            "Nepodléhejte tlaku na urychlení práce.",
            "Nenastupujte do vozidla za jízdy.",
        ):
            with self.subTest(text=text):
                self.assertFalse(is_unsuitable_employee_rule(text))

    def test_positive_imperatives_are_suitable(self) -> None:
        for text in (
            "Používejte ochrannou přilbu.",
            "Dodržujte bezpečnostní pokyny.",
            "Oznamte vedoucímu zaměstnance každou závadu.",
            "Přerušte práci při nebezpečí.",
            "Ukončete činnost při poruše zařízení.",
        ):
            with self.subTest(text=text):
                self.assertFalse(is_unsuitable_employee_rule(text))

    def test_noun_formulations_remain_unsuitable(self) -> None:
        for text in (
            "Používání ochranných pracovních prostředků.",
            "Dodržování pokynů vedoucího zaměstnance.",
            "Kontrola stavu zařízení.",
            "Evidence závad.",
            "Provádění údržby bez povolení.",
            "Zajištění pracoviště proti pádu.",
        ):
            with self.subTest(text=text):
                self.assertTrue(is_unsuitable_employee_rule(text))


if __name__ == "__main__":
    unittest.main()
