import unittest

from moduly.pravni_pozadavky.constants import (
    DOCUMENT_TYPE_NARIZENI_VLADY,
    DOCUMENT_TYPE_VYHLASKA,
    DOCUMENT_TYPE_ZAKON,
)
from moduly.pravni_pozadavky.legal_document_type_utils import (
    detect_document_type_from_bulk_prefix,
    detect_document_type_from_text,
    normalize_document_type,
    resolve_document_type,
)


class LegalDocumentTypeUtilsTestCase(unittest.TestCase):
    def test_detect_from_title_narizeni_vlady(self) -> None:
        title = "Nařízení vlády o povinnostech zaměstnavatele při pracovních úrazech"
        self.assertEqual(detect_document_type_from_text(title), DOCUMENT_TYPE_NARIZENI_VLADY)

    def test_detect_from_title_vyhlaska(self) -> None:
        title = "Vyhláška o provedení některých ustanovení zákona"
        self.assertEqual(detect_document_type_from_text(title), DOCUMENT_TYPE_VYHLASKA)

    def test_detect_from_title_zakon(self) -> None:
        title = "Zákon o bezpečnosti práce v souvislosti s provozem vyhrazených technických zařízení"
        self.assertEqual(detect_document_type_from_text(title), DOCUMENT_TYPE_ZAKON)

    def test_detect_from_title_zakonik(self) -> None:
        title = "Zákon zákoník práce"
        self.assertEqual(detect_document_type_from_text(title), DOCUMENT_TYPE_ZAKON)

    def test_detect_from_bulk_prefix_nv(self) -> None:
        self.assertEqual(
            detect_document_type_from_bulk_prefix("NV 390/2021 Sb."),
            DOCUMENT_TYPE_NARIZENI_VLADY,
        )

    def test_detect_from_bulk_prefix_without_prefix_returns_none(self) -> None:
        self.assertIsNone(detect_document_type_from_bulk_prefix("390/2021 Sb."))

    def test_resolve_prefers_title_over_explicit_zakon(self) -> None:
        title = "Nařízení vlády o bližších podmínkách poskytování osobních ochranných pracovních prostředků"
        self.assertEqual(
            resolve_document_type(explicit=DOCUMENT_TYPE_ZAKON, title=title),
            DOCUMENT_TYPE_NARIZENI_VLADY,
        )

    def test_normalize_document_type_accepts_label(self) -> None:
        self.assertEqual(
            normalize_document_type("Nařízení vlády"),
            DOCUMENT_TYPE_NARIZENI_VLADY,
        )


if __name__ == "__main__":
    unittest.main()
