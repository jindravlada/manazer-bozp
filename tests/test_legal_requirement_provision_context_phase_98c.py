"""Fáze 98c – kontext nadřazených ustanovení v panelu Znění právního podkladu."""

from __future__ import annotations

import importlib
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

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
        SECTION_LETTER,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
        legal_section_provision_label,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_display_text_service import (
        legal_section_display_text_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service


class LegalRequirementProvisionContextPhase98cTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Vyhláška č. 180/2015 Sb.",
            number="180",
            year=2015,
            short_title="V180",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
        )
        self._paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="4",
            title="Zaměstnankyním-matkám jsou zakázány práce uvedené",
            sort_order=1,
        )
        self._subsection = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=self._paragraph.id,
            section_number="1",
            text="Text prvního odstavce.",
            sort_order=2,
        )
        self._letter = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_LETTER,
            parent_section_id=self._subsection.id,
            item_letter="c",
            text="Text písmene c).",
            sort_order=3,
        )
        self._subsection_with_full_text = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=self._paragraph.id,
            section_number="2",
            text="Text odstavce 2 pro zobrazení.",
            sort_order=4,
        )
        self._sections_by_id = legal_section_service.build_sections_map(
            [
                self._paragraph,
                self._subsection,
                self._letter,
                self._subsection_with_full_text,
            ],
        )

        document_79 = legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Vyhláška č. 79/2013 Sb.",
            number="79",
            year=2013,
            short_title="V79",
        )
        version_79 = legal_document_version_service.create(
            legal_document_id=document_79.id,
            version_name="Aktuální znění",
        )
        paragraph_5a = legal_section_service.create(
            legal_document_id=document_79.id,
            legal_document_version_id=version_79.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="5a",
            title=(
                "Náhradní postupy, organizace a provádění pracovnělékařských služeb "
                "při vyhlášení nouzového stavu, stavu ohrožení státu, válečného stavu "
                "nebo při nařízení mimořádného opatření při epidemii a nebezpečí jejího vzniku"
            ),
            sort_order=1,
        )
        subsection_5a_1 = legal_section_service.create(
            legal_document_id=document_79.id,
            legal_document_version_id=version_79.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph_5a.id,
            section_number="1",
            text=(
                "Při zajištění poskytování pracovnělékařských služeb v případě vyhlášení "
                "nouzového stavu, stavu ohrožení státu, válečného stavu nebo nařízení "
                "mimořádného opatření při epidemii a nebezpečí jejího vzniku, jsou-li tyto "
                "stavy a opatření vyhlášeny pro celé území České republiky, (dále jen "
                "„stavy nebo opatření“) se, pokud dále není stanoveno jinak, postupuje tak, že"
            ),
            sort_order=2,
        )
        legal_section_service.create(
            legal_document_id=document_79.id,
            legal_document_version_id=version_79.id,
            section_type=SECTION_LETTER,
            parent_section_id=subsection_5a_1.id,
            item_letter="a",
            text="se neprovádějí vstupní prohlídky podle § 10,",
            sort_order=3,
        )
        self._letter_5a_b = legal_section_service.create(
            legal_document_id=document_79.id,
            legal_document_version_id=version_79.id,
            section_type=SECTION_LETTER,
            parent_section_id=subsection_5a_1.id,
            item_letter="b",
            text=(
                "se neprovádějí periodické prohlídky podle § 11 u prací zařazených "
                "do kategorie první a druhé podle zákona o ochraně veřejného zdraví, "
                "a není-li součástí této práce činnost, pro jejíž výkon jsou podmínky "
                "zdravotní způsobilosti stanoveny v příloze č. 1 k této vyhlášce "
                "nebo v jiných právních předpisech; periodické prohlídky, které "
                "nebyly provedeny z důvodu vyhlášeného stavu nebo opatření, se provedou "
                "do uplynutí 180 dnů ode dne následujícího po dni ukončení stavu "
                "nebo opatření,"
            ),
            sort_order=4,
        )
        self._sections_by_id_79 = legal_section_service.build_sections_map(
            legal_section_service.list_by_version(version_79.id),
        )

    def _compose_panel_body(self, section_id: int) -> str:
        return legal_section_display_text_service.compose(
            section_id,
            include_root_provision_label=False,
            include_ancestor_context=True,
        )

    def test_compose_paragraph_includes_children_without_root_label(self) -> None:
        composed = self._compose_panel_body(self._paragraph.id)

        self.assertFalse(composed.startswith("§ 4"))
        self.assertIn("Zaměstnankyním-matkám jsou zakázány práce uvedené", composed)
        self.assertIn("(1) Text prvního odstavce.", composed)
        self.assertIn("c) Text písmene c).", composed)

    def test_compose_subsection_with_own_text_includes_paragraph_intro(self) -> None:
        composed = self._compose_panel_body(self._subsection_with_full_text.id)

        self.assertIn("Zaměstnankyním-matkám jsou zakázány práce uvedené", composed)
        self.assertIn("Text odstavce 2 pro zobrazení.", composed)
        self.assertNotIn("(2)", composed)
        self.assertNotIn("Text prvního odstavce.", composed)

    def test_compose_letter_includes_subsection_intro(self) -> None:
        composed = self._compose_panel_body(self._letter.id)

        self.assertIn("Zaměstnankyním-matkám jsou zakázány práce uvedené", composed)
        self.assertIn("Text prvního odstavce.", composed)
        self.assertIn("Text písmene c).", composed)
        self.assertIsNone(re.search(r"(?m)^\s*c\)\s", composed))

    def test_compose_without_ancestor_context_keeps_previous_behavior(self) -> None:
        composed = legal_section_display_text_service.compose(
            self._letter.id,
            include_root_provision_label=False,
        )

        self.assertEqual(composed, "Text písmene c).")

    def test_compose_does_not_repeat_provision_label_in_body(self) -> None:
        for section_id in (self._paragraph.id, self._subsection.id, self._letter.id):
            composed = self._compose_panel_body(section_id)
            self.assertNotRegex(composed, r"(?m)^§\s*4\b")
            self.assertNotIn("§ 4 odst", composed)
            self.assertNotIn("písm.", composed)

    def test_regression_79_2013_section_5a_subsection_1_letter_b(self) -> None:
        self.assertEqual(
            legal_section_provision_label(
                self._letter_5a_b,
                sections_by_id=self._sections_by_id_79,
            ),
            "§ 5a odst. 1 písm. b)",
        )

        composed = self._compose_panel_body(self._letter_5a_b.id)

        self.assertIn(
            "Náhradní postupy, organizace a provádění pracovnělékařských služeb",
            composed,
        )
        self.assertIn("postupuje tak, že", composed)
        self.assertTrue(composed.endswith("nebo opatření,"))
        self.assertIn("se neprovádějí periodické prohlídky", composed)
        self.assertNotRegex(composed, r"(?m)^§\s*5a\b")
        self.assertIsNone(re.search(r"(?m)^\s*b\)\s", composed))


if __name__ == "__main__":
    unittest.main()
