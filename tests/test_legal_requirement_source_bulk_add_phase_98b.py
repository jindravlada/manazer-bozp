"""Fáze 98b – hromadné přidávání právních ustanovení k řídicímu procesu."""

from __future__ import annotations

import importlib
import os
import tempfile
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
        DOCUMENT_TYPE_ZAKON,
        SECTION_LETTER,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
        legal_document_list_label,
        legal_document_matches_search,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.ui.legal_requirement_source_add_dialog import (
        LegalRequirementSourceAddDialog,
    )
    from moduly.pravni_pozadavky.ui.legal_requirement_sources_widget import (
        LegalRequirementSourcesWidget,
    )


class LegalRequirementSourceBulkAddPhase98bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

        self.document_309 = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákon, kterým se upravují další požadavky pro bezpečnost a ochranu zdraví",
            number="309",
            year=2006,
            short_title="",
        )
        self.document_oopp = legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Vyhláška o osobních ochranných pracovních prostředcích",
            number="378",
            year=2001,
            short_title="OOPP",
        )
        self.document_zp = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262",
            year=2006,
            short_title="ZP",
        )

        version_309 = legal_document_version_service.create(
            legal_document_id=self.document_309.id,
            version_name="Aktuální znění",
        )
        version_oopp = legal_document_version_service.create(
            legal_document_id=self.document_oopp.id,
            version_name="Aktuální znění",
        )

        self.paragraph_4 = legal_section_service.create(
            legal_document_id=self.document_oopp.id,
            legal_document_version_id=version_oopp.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="4",
            sort_order=1,
        )
        self.subsection_4_1 = legal_section_service.create(
            legal_document_id=self.document_oopp.id,
            legal_document_version_id=version_oopp.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=self.paragraph_4.id,
            section_number="1",
            text="Text odstavce 1.",
            sort_order=2,
        )
        self.letter_4_1_c = legal_section_service.create(
            legal_document_id=self.document_oopp.id,
            legal_document_version_id=version_oopp.id,
            section_type=SECTION_LETTER,
            parent_section_id=self.subsection_4_1.id,
            item_letter="c",
            text="Text písmene c).",
            sort_order=3,
        )

        self.paragraph_309 = legal_section_service.create(
            legal_document_id=self.document_309.id,
            legal_document_version_id=version_309.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="1",
            text="Text § 1 zákona 309.",
            sort_order=1,
        )

    def test_document_search_by_number(self) -> None:
        matches = legal_document_service.list_matching("309")
        ids = {document.id for document in matches}
        self.assertIn(self.document_309.id, ids)
        self.assertNotIn(self.document_zp.id, ids)

    def test_document_search_by_partial_title_and_short_title(self) -> None:
        self.assertTrue(
            legal_document_matches_search(self.document_zp, "zákoník"),
        )
        self.assertTrue(
            legal_document_matches_search(self.document_oopp, "OOPP"),
        )
        matches = legal_document_service.list_matching("378")
        self.assertIn(self.document_oopp.id, {document.id for document in matches})

    def test_document_list_label_format(self) -> None:
        self.assertEqual(
            legal_document_list_label(self.document_309),
            "309/2006 Sb. – Zákon, kterým se upravují další požadavky pro bezpečnost a ochranu zdraví",
        )

    def _select_document_in_dialog(
        self,
        dialog: LegalRequirementSourceAddDialog,
        document_id: int,
    ) -> None:
        for row in range(dialog.document_list.count()):
            item = dialog.document_list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == document_id:
                dialog.document_list.setCurrentItem(item)
                return
        self.fail(f"Předpis #{document_id} nebyl nalezen v seznamu dialogu.")

    def _find_checkable_item(
        self,
        dialog: LegalRequirementSourceAddDialog,
        section_id: int,
    ):
        def walk(item):
            if item.data(0, Qt.ItemDataRole.UserRole) == section_id:
                return item
            for index in range(item.childCount()):
                found = walk(item.child(index))
                if found is not None:
                    return found
            return None

        for index in range(dialog.sections_tree.topLevelItemCount()):
            top = dialog.sections_tree.topLevelItem(index)
            if top is None:
                continue
            found = walk(top)
            if found is not None:
                return found
        return None

    def test_dialog_allows_selecting_multiple_sections(self) -> None:
        dialog = LegalRequirementSourceAddDialog()
        self._select_document_in_dialog(dialog, self.document_oopp.id)

        for section_id in (
            self.paragraph_4.id,
            self.subsection_4_1.id,
            self.letter_4_1_c.id,
        ):
            item = self._find_checkable_item(dialog, section_id)
            self.assertIsNotNone(item)
            self.assertTrue(item.flags() & Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked)

        dialog._accept()
        self.assertEqual(
            dialog.selected_section_ids(),
            [
                self.paragraph_4.id,
                self.subsection_4_1.id,
                self.letter_4_1_c.id,
            ],
        )

    def test_already_assigned_sections_are_checked_and_disabled(self) -> None:
        dialog = LegalRequirementSourceAddDialog(
            excluded_section_ids={self.subsection_4_1.id},
        )
        self._select_document_in_dialog(dialog, self.document_oopp.id)

        item = self._find_checkable_item(dialog, self.subsection_4_1.id)
        self.assertIsNotNone(item)
        self.assertEqual(item.checkState(0), Qt.CheckState.Checked)
        self.assertFalse(item.flags() & Qt.ItemFlag.ItemIsUserCheckable)

        paragraph_item = self._find_checkable_item(dialog, self.paragraph_4.id)
        paragraph_item.setCheckState(0, Qt.CheckState.Checked)
        dialog._accept()
        self.assertEqual(dialog.selected_section_ids(), [self.paragraph_4.id])

    def test_append_source_sections_batch_keeps_existing_and_skips_duplicates(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            title="Testovací proces",
            source_section_ids=[self.subsection_4_1.id],
        )

        updated = legal_requirement_service.append_source_sections(
            requirement.id,
            [
                self.subsection_4_1.id,
                self.paragraph_4.id,
                self.letter_4_1_c.id,
            ],
        )

        section_ids = legal_requirement_service.list_source_section_ids_for_requirement(
            updated.id,
        )
        self.assertEqual(
            section_ids,
            [
                self.subsection_4_1.id,
                self.paragraph_4.id,
                self.letter_4_1_c.id,
            ],
        )

    def test_sources_widget_adds_multiple_sections_from_dialog(self) -> None:
        widget = LegalRequirementSourcesWidget()
        widget.load_section_ids([self.subsection_4_1.id])

        dialog = LegalRequirementSourceAddDialog(
            excluded_section_ids=set(widget.get_section_ids()),
        )
        self._select_document_in_dialog(dialog, self.document_oopp.id)
        paragraph_item = self._find_checkable_item(dialog, self.paragraph_4.id)
        letter_item = self._find_checkable_item(dialog, self.letter_4_1_c.id)
        paragraph_item.setCheckState(0, Qt.CheckState.Checked)
        letter_item.setCheckState(0, Qt.CheckState.Checked)
        dialog._accept()

        for section_id in dialog.selected_section_ids():
            widget._append_section(section_id)

        self.assertEqual(
            widget.get_section_ids(),
            [
                self.subsection_4_1.id,
                self.paragraph_4.id,
                self.letter_4_1_c.id,
            ],
        )


if __name__ == "__main__":
    unittest.main()
