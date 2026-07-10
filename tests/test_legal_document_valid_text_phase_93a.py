import importlib
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
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
        SECTION_DIVISION,
        SECTION_HEAD,
        SECTION_PARAGRAPH,
        SECTION_PART,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_valid_text_service import (
        legal_document_valid_text_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.ui.legal_document_valid_text_tab import (
        LegalDocumentValidTextTab,
    )
    from moduly.pravni_pozadavky.ui.legal_document_version_dialog import (
        LegalDocumentVersionDialog,
    )


class LegalDocumentValidTextServicePhase93aTestCase(unittest.TestCase):
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

        self.document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Vyhláška č. 101/2020 Sb.",
            number="101",
            year=2020,
        )
        self.version = legal_document_version_service.create(
            legal_document_id=self.document.id,
            version_name="Aktuální znění",
        )
        self._create_sample_structure()

    def _create_sample_structure(self) -> None:
        part = legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_PART,
            section_number="PRVNÍ",
            sort_order=1,
        )
        head = legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_HEAD,
            section_number="I",
            parent_section_id=part.id,
            sort_order=2,
        )
        division = legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_DIVISION,
            section_number="1",
            parent_section_id=head.id,
            sort_order=3,
        )
        paragraph_101 = legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="101",
            parent_section_id=division.id,
            sort_order=4,
        )
        legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph_101.id,
            section_number="1",
            text="První odstavec paragrafu 101.",
            sort_order=5,
        )
        paragraph_102 = legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="102",
            parent_section_id=division.id,
            sort_order=6,
        )
        legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph_102.id,
            section_number="1",
            text="Text paragrafu 102 s klíčovým slovem bezpečnost.",
            sort_order=7,
        )

    def test_compose_version_contains_structure_and_paragraphs(self) -> None:
        document = legal_document_valid_text_service.compose_version(self.version.id)

        self.assertIn("ČÁST PRVNÍ", document.plain_text)
        self.assertIn("HLAVA I", document.plain_text)
        self.assertIn("Oddíl 1", document.plain_text)
        self.assertIn("§ 101", document.plain_text)
        self.assertIn("§ 102", document.plain_text)
        self.assertIn("První odstavec paragrafu 101.", document.plain_text)
        self.assertIn('name="p101"', document.html)
        self.assertIn("<b>§ 101</b>", document.html)

    def test_large_document_compose_is_fast(self) -> None:
        for index in range(200):
            legal_section_service.create(
                legal_document_id=self.document.id,
                legal_document_version_id=self.version.id,
                section_type=SECTION_PARAGRAPH,
                paragraph=str(200 + index),
                text=f"Text paragrafu {200 + index}.",
                sort_order=100 + index,
            )

        started = time.perf_counter()
        document = legal_document_valid_text_service.compose_version(self.version.id)
        elapsed = time.perf_counter() - started

        self.assertGreater(len(document.plain_text), 4000)
        self.assertLess(elapsed, 2.0)


class LegalDocumentValidTextTabPhase93aTestCase(unittest.TestCase):
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

        self.document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Vyhláška č. 55/2021 Sb.",
            number="55",
            year=2021,
        )
        self.version = legal_document_version_service.create(
            legal_document_id=self.document.id,
            version_name="Aktuální znění",
        )
        paragraph = legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="7",
            sort_order=1,
        )
        legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph.id,
            section_number="1",
            text="Bezpečnost práce je prioritou. Bezpečnost musí být zajištěna.",
            sort_order=2,
        )

    def test_tab_shows_full_text_and_allows_selection(self) -> None:
        tab = LegalDocumentValidTextTab(version_id=self.version.id)
        tab.refresh()

        plain = tab.text_browser.toPlainText()
        self.assertIn("§ 7", plain)
        self.assertIn("Bezpečnost práce je prioritou.", plain)
        self.assertTrue(
            bool(
                tab.text_browser.textInteractionFlags()
                & Qt.TextInteractionFlag.TextSelectableByMouse
            )
        )

    def test_find_text_and_enter_continue_to_next_match(self) -> None:
        tab = LegalDocumentValidTextTab(version_id=self.version.id)
        tab.refresh()
        tab.search_input.setText("bezpečnost")

        tab._find_next()
        first_position = tab.text_browser.textCursor().position()
        self.assertGreater(first_position, 0)

        tab._find_next()
        second_position = tab.text_browser.textCursor().position()
        self.assertGreater(second_position, first_position)

    def test_paragraph_number_jump_accepts_multiple_formats(self) -> None:
        tab = LegalDocumentValidTextTab(version_id=self.version.id)
        tab.refresh()

        for query in ("7", "§7", "§ 7"):
            tab.search_input.setText(query)
            tab._find_next()
            self.assertIn("§ 7", tab.text_browser.textCursor().block().text())

    def test_version_dialog_contains_valid_text_tab_after_provisions(self) -> None:
        dialog = LegalDocumentVersionDialog(version=self.version)
        labels = [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]

        self.assertEqual(labels, ["Verze", "Ustanovení", "📖 Platné znění", "Pracovní režim"])
        self.assertIsInstance(dialog.valid_text_tab, LegalDocumentValidTextTab)


if __name__ == "__main__":
    unittest.main()
