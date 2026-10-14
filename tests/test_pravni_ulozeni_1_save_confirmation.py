"""PRAVNI-ULOZENI-1 – potvrzení uložení v pracovním režimu právních požadavků."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

_TMP = Path(tempfile.mkdtemp(prefix="pravni-ulozeni-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.pravni_pozadavky.constants import (
        DOCUMENT_TYPE_ZAKON,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.ui.legal_document_workbench_tab import (
        LegalDocumentWorkbenchTab,
    )

CONFIRMATION_TITLE = "Právní požadavky"
CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."


class PravniUlozeni1SaveConfirmationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _create_document(self):
        return legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262/2006 Sb.",
            year=2006,
            short_title="ZP",
        )

    def _create_version(self, document):
        return legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Verze 2024",
        )

    def _create_sections(self, document, version, count: int):
        paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="101",
            title="Předmět",
            sort_order=1,
        )
        sections = []
        for index in range(1, count + 1):
            sections.append(
                legal_section_service.create(
                    legal_document_id=document.id,
                    legal_document_version_id=version.id,
                    section_type=SECTION_SUBSECTION,
                    parent_section_id=paragraph.id,
                    section_number=str(index),
                    text=f"Text odstavce {index}",
                    sort_order=index,
                )
            )
        return sections

    def _requirement(self, document, section, *, summary: str, note: str = ""):
        return legal_requirement_service.create_requirement(
            title="Povinnost BOZP",
            regulation_name="Zákoník práce",
            legal_document_id=document.id,
            legal_section_id=section.id,
            source_section_id=section.id,
            requirement_summary=summary,
            note=note,
        )

    def _open(self, document, version) -> LegalDocumentWorkbenchTab:
        tab = LegalDocumentWorkbenchTab(document_id=document.id, version_id=version.id)
        tab.show()
        self.app.processEvents()
        return tab

    def _load(self, tab: LegalDocumentWorkbenchTab, section_id: int):
        assert tab.tree is not None
        tab.tree.select_section_id(section_id)
        tab.load_section(section_id)
        self.app.processEvents()
        assert tab.editor is not None
        return tab.editor

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(
            "moduly.pravni_pozadavky.ui.legal_document_workbench_tab._exec_message_box",
            side_effect=_exec,
        ):
            action()
        return shown

    def _assert_confirmation(self, shown: list[QMessageBox]) -> None:
        self.assertEqual(len(shown), 1)
        box = shown[0]
        self.assertEqual(box.windowTitle(), CONFIRMATION_TITLE)
        self.assertEqual(box.text(), CONFIRMATION_TEXT)
        self.assertEqual(box.icon(), QMessageBox.Icon.Information)
        self.assertEqual(box.standardButtons(), QMessageBox.StandardButton.Ok)
        ok_button = box.button(QMessageBox.StandardButton.Ok)
        assert ok_button is not None
        self.assertEqual(ok_button.text(), "OK")

    def test_successful_save_shows_confirmation_and_keeps_data(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_sections(document, version, 1)[0]
        self._requirement(document, section, summary="Původní plnění", note="původní")
        tab = self._open(document, version)
        editor = self._load(tab, section.id)
        self.assertFalse(editor.has_changes())
        editor.note.setPlainText("uložená poznámka")
        editor.requirement_summary.setPlainText("uložené plnění")
        shown = self._run(editor.save_btn.click)
        self._assert_confirmation(shown)
        self.assertFalse(editor.has_changes())
        self.assertFalse(tab.isHidden())
        self.assertEqual(editor.note.toPlainText(), "uložená poznámka")

        reopened = self._open(document, version)
        editor = self._load(reopened, section.id)
        self.assertEqual(editor.note.toPlainText(), "uložená poznámka")
        self.assertEqual(editor.requirement_summary.toPlainText(), "uložené plnění")
        stored = legal_requirement_service.get_by_source_section_id(section.id)
        assert stored is not None
        self.assertEqual(stored.legal_section_id, section.id)
        self.assertEqual(stored.note, "uložená poznámka")

    def test_save_without_changes_does_not_confirm(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_sections(document, version, 1)[0]
        self._requirement(document, section, summary="Beze změny", note="stejná")
        tab = self._open(document, version)
        editor = self._load(tab, section.id)
        editor.note.setPlainText("jedna změna")
        first = self._run(editor.save_btn.click)
        self._assert_confirmation(first)
        second = self._run(editor.save_btn.click)
        self.assertEqual(second, [])
        self.assertEqual(editor.note.toPlainText(), "jedna změna")

    def test_failed_save_keeps_draft_and_skips_confirmation(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_sections(document, version, 1)[0]
        created = self._requirement(document, section, summary="Platné plnění", note="původní")
        tab = self._open(document, version)
        editor = self._load(tab, section.id)
        editor.note.setPlainText("rozepsaná poznámka")
        editor.requirement_summary.setPlainText("rozepsané plnění")

        def _fail(*_args, **_kwargs):
            raise ValueError("Požadavek nebyl nalezen.")

        with (
            patch(
                "moduly.pravni_pozadavky.ui.legal_document_workbench_tab.legal_requirement_service.update_requirement",
                side_effect=_fail,
            ),
            patch(
                "moduly.pravni_pozadavky.ui.legal_document_workbench_tab.QMessageBox.warning",
            ) as warn,
        ):
            shown = self._run(editor.save_btn.click)
        self.assertEqual(shown, [])
        warn.assert_called_once()
        self.assertIn("Požadavek nebyl nalezen.", warn.call_args.args[2])
        self.assertEqual(editor.note.toPlainText(), "rozepsaná poznámka")
        self.assertEqual(editor.requirement_summary.toPlainText(), "rozepsané plnění")
        self.assertTrue(editor.has_changes())
        stored = legal_requirement_service.get_by_id(created.id)
        assert stored is not None
        self.assertEqual(stored.note, "původní")
        self.assertEqual(stored.requirement_summary, "Platné plnění")

    def test_confirmation_appears_only_after_write(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        section = self._create_sections(document, version, 1)[0]
        self._requirement(document, section, summary="Plnění", note="původní")
        tab = self._open(document, version)
        editor = self._load(tab, section.id)
        editor.note.setPlainText("až po zápisu")
        order: list[str] = []
        original = legal_requirement_service.update_requirement

        def _update(*args, **kwargs):
            order.append("write")
            self.assertEqual(order, ["write"])
            return original(*args, **kwargs)

        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            self.assertEqual(order, ["write"])
            order.append("dialog")
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with (
            patch(
                "moduly.pravni_pozadavky.ui.legal_document_workbench_tab.legal_requirement_service.update_requirement",
                side_effect=_update,
            ),
            patch(
                "moduly.pravni_pozadavky.ui.legal_document_workbench_tab._exec_message_box",
                side_effect=_exec,
            ),
        ):
            editor.save_btn.click()
        self.assertEqual(order, ["write", "dialog"])
        self._assert_confirmation(shown)
        stored = legal_requirement_service.get_by_source_section_id(section.id)
        assert stored is not None
        self.assertEqual(stored.note, "až po zápisu")

    def test_other_actions_do_not_confirm(self) -> None:
        document = self._create_document()
        version = self._create_version(document)
        first, second = self._create_sections(document, version, 2)
        self._requirement(document, first, summary="První", note="A")
        self._requirement(document, second, summary="Druhé", note="B")
        tab = self._open(document, version)
        editor = self._load(tab, first.id)
        editor.note.setPlainText("uloženo dalším ustanovením")
        shown = self._run(editor.next_btn.click)
        self.assertEqual(shown, [])
        stored = legal_requirement_service.get_by_source_section_id(first.id)
        assert stored is not None
        self.assertEqual(stored.note, "uloženo dalším ustanovením")
        self.assertEqual(editor.note.toPlainText(), "B")

        editor = self._load(tab, first.id)
        editor.note.setPlainText("jen ve formuláři")
        shown = self._run(lambda: tab.save_current())
        self.assertEqual(shown, [])
        stored = legal_requirement_service.get_by_source_section_id(first.id)
        assert stored is not None
        self.assertEqual(stored.note, "jen ve formuláři")

        editor.note.setPlainText("zahodit přepnutím")
        shown = self._run(lambda: tab.tree.select_section_id(second.id))
        self.assertEqual(shown, [])
        stored = legal_requirement_service.get_by_source_section_id(first.id)
        assert stored is not None
        self.assertEqual(stored.note, "jen ve formuláři")
        self.assertEqual(editor.note.toPlainText(), "B")
