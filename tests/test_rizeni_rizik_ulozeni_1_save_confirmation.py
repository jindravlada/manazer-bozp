"""RIZIKA-ULOZENI-1 – potvrzení úspěšného uložení v katalogu rizik a kategoriích."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

_TMP = Path(tempfile.mkdtemp(prefix="rizika-ulozeni-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_source_category_service import (
        hazard_source_category_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_dialog import (
        HazardLibraryTemplateDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_event_dialog import (
        HazardLibraryTemplateEventDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_source_categories_management_dialog import (
        CategoryDraft,
        HazardSourceCategoriesManagementDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_source_category_dialog import (
        HazardSourceCategoryDialog,
    )

CONFIRMATION_TITLE = "Řízení rizik"
CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."


class _SaveConfirmationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(
            "moduly.rizeni_rizik.ui.save_confirmation._exec_message_box",
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

    def _close(self, dialog) -> None:
        dialog._closing = True
        dialog.close()


class CatalogSaveConfirmationTests(_SaveConfirmationTestCase):
    def _open(self, template=None) -> HazardLibraryTemplateDialog:
        dialog = HazardLibraryTemplateDialog(template=template)
        dialog.show()
        self.app.processEvents()
        return dialog

    def _create_template(self, suffix: str):
        return hazard_library_template_service.create_template(
            name=f"RIZIKA-ULOZENI-1 {suffix} {uuid.uuid4().hex[:8]}",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )

    def test_successful_save_shows_confirmation_and_keeps_data(self) -> None:
        template = self._create_template("ulozeni")
        dialog = self._open(template)
        dialog.note.setPlainText("uložená poznámka")
        dialog.description.setPlainText("uložený popis")
        shown = self._run(dialog.save_button.click)
        self._assert_confirmation(shown)
        self.assertFalse(dialog.is_dirty())
        self.assertFalse(dialog.isHidden())
        template_id = dialog.template.id
        self._close(dialog)

        reopened = self._open(hazard_library_template_service.get_by_id(template_id))
        self.assertEqual(reopened.note.toPlainText(), "uložená poznámka")
        self.assertEqual(reopened.description.toPlainText(), "uložený popis")
        self._close(reopened)

    def test_save_without_changes_does_not_confirm(self) -> None:
        template = self._create_template("beze-zmeny")
        dialog = self._open(template)
        dialog.note.setPlainText("jedna změna")
        first = self._run(dialog.save_button.click)
        self._assert_confirmation(first)
        self.assertFalse(dialog.save_button.isEnabled())
        second = self._run(dialog.save_button.click)
        self.assertEqual(second, [])
        direct = self._run(dialog._save_keep_open)
        self.assertEqual(direct, [])
        self.assertEqual(dialog.note.toPlainText(), "jedna změna")
        self._close(dialog)

    def test_failed_save_keeps_draft_and_skips_confirmation(self) -> None:
        template = self._create_template("chyba")
        dialog = self._open(template)
        dialog.note.setPlainText("rozepsaná poznámka")
        dialog.name.setText("")
        with patch(
            "moduly.rizeni_rizik.ui.hazard_library_template_dialog.QMessageBox.warning",
        ) as warn:
            shown = self._run(dialog.save_button.click)
        self.assertEqual(shown, [])
        warn.assert_called_once()
        self.assertIn("Název zdroje rizika je povinný.", warn.call_args.args[2])
        self.assertEqual(dialog.note.toPlainText(), "rozepsaná poznámka")
        self.assertEqual(dialog.name.text(), "")
        self.assertTrue(dialog.is_dirty())
        self.assertFalse(dialog.isHidden())
        stored = hazard_library_template_service.get_by_id(template.id)
        assert stored is not None
        self.assertEqual(stored.name, template.name)
        self.assertEqual(stored.note or "", "")
        self._close(dialog)

    def test_save_and_close_does_not_confirm(self) -> None:
        template = self._create_template("zavrit")
        dialog = self._open(template)
        dialog.note.setPlainText("uloženo zavřením")
        shown = self._run(dialog.save_close_button.click)
        self.assertEqual(shown, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        stored = hazard_library_template_service.get_by_id(template.id)
        assert stored is not None
        self.assertEqual(stored.note, "uloženo zavřením")

    def test_close_prompt_save_does_not_confirm(self) -> None:
        template = self._create_template("prompt")
        dialog = self._open(template)
        dialog.note.setPlainText("uloženo z promptu")
        with patch.object(dialog, "_prompt_unsaved_close", return_value="save"):
            shown = self._run(dialog.reject)
        self.assertEqual(shown, [])
        stored = hazard_library_template_service.get_by_id(template.id)
        assert stored is not None
        self.assertEqual(stored.note, "uloženo z promptu")

    def test_tab_switch_does_not_save_or_confirm(self) -> None:
        template = self._create_template("zalozka")
        dialog = self._open(template)
        dialog.note.setPlainText("jen v editoru")
        shown = self._run(lambda: dialog.tabs.setCurrentIndex(dialog.content_tab_index))
        self.assertEqual(shown, [])
        self.assertTrue(dialog.is_dirty())
        stored = hazard_library_template_service.get_by_id(template.id)
        assert stored is not None
        self.assertEqual(stored.note or "", "")
        self._close(dialog)

    def test_nested_event_save_stays_in_working_copy(self) -> None:
        template = self._create_template("udalost")
        dialog = self._open(template)
        event_dialog = HazardLibraryTemplateEventDialog(
            dialog,
            template_id=template.id,
        )
        event_dialog.name.setText("Jen koncept")
        shown = self._run(event_dialog.accept)
        self.assertEqual(shown, [])
        self.assertTrue(dialog.is_dirty())
        self.assertEqual(
            [event.name for event in dialog._content_store.get_events()],
            ["Jen koncept"],
        )
        self.assertEqual(
            hazard_library_template_event_service.get_for_template(template.id),
            [],
        )
        notified = self._run(dialog._on_content_changed)
        self.assertEqual(notified, [])
        self.assertTrue(dialog.save_button.isEnabled())

        shown = self._run(dialog.save_button.click)
        self._assert_confirmation(shown)
        stored_events = hazard_library_template_event_service.get_for_template(template.id)
        self.assertEqual([event.name for event in stored_events], ["Jen koncept"])
        self._close(dialog)

    def test_opening_duplicate_does_not_confirm(self) -> None:
        existing = self._create_template("duplicita")
        dialog = self._open()
        dialog.name.setText(existing.name)
        with patch.object(dialog, "_prompt_duplicate_name", return_value="open"):
            shown = self._run(dialog.save_button.click)
        self.assertEqual(shown, [])
        self.assertEqual(dialog.template.id, existing.id)
        self.assertFalse(dialog.isHidden())
        self.assertEqual(dialog.name.text(), existing.name)
        self._close(dialog)

    def test_new_template_save_confirms_and_stays_open(self) -> None:
        dialog = self._open()
        name = f"Nový zdroj {uuid.uuid4().hex[:8]}"
        dialog.name.setText(name)
        shown = self._run(dialog.save_button.click)
        self._assert_confirmation(shown)
        self.assertIsNotNone(dialog.template)
        self.assertFalse(dialog.isHidden())
        self.assertFalse(dialog.is_dirty())
        stored = hazard_library_template_service.get_by_id(dialog.template.id)
        assert stored is not None
        self.assertEqual(stored.name, name)
        self._close(dialog)


class CategorySaveConfirmationTests(_SaveConfirmationTestCase):
    def _open(self) -> HazardSourceCategoriesManagementDialog:
        dialog = HazardSourceCategoriesManagementDialog()
        dialog.show()
        self.app.processEvents()
        return dialog

    def _category_named(self, name: str):
        for category in hazard_source_category_service.get_all(include_inactive=True):
            if category.name == name:
                return category
        return None

    def test_successful_save_shows_confirmation_and_keeps_data(self) -> None:
        dialog = self._open()
        name = f"Kategorie uložení {uuid.uuid4().hex[:8]}"
        dialog._working_items.append(
            CategoryDraft(
                key=dialog._next_temp_key,
                code=None,
                name=name,
                description="uložený popis",
                sort_order=8800,
                active=True,
                is_new=True,
            ),
        )
        dialog._next_temp_key -= 1
        dialog._mark_dirty()
        shown = self._run(dialog.save_button.click)
        self._assert_confirmation(shown)
        self.assertFalse(dialog.is_dirty())
        self.assertFalse(dialog.isHidden())
        self._close(dialog)

        reopened = self._open()
        match = next(item for item in reopened._working_items if item.name == name)
        self.assertEqual(match.description, "uložený popis")
        self.assertFalse(match.is_new)
        stored = self._category_named(name)
        assert stored is not None
        self.assertEqual(stored.description, "uložený popis")
        self._close(reopened)

    def test_save_without_changes_does_not_confirm(self) -> None:
        dialog = self._open()
        name = f"Kategorie jednou {uuid.uuid4().hex[:8]}"
        dialog._working_items.append(
            CategoryDraft(
                key=dialog._next_temp_key,
                code=None,
                name=name,
                description="první popis",
                sort_order=8801,
                active=True,
                is_new=True,
            ),
        )
        dialog._mark_dirty()
        first = self._run(dialog.save_button.click)
        self._assert_confirmation(first)
        self.assertFalse(dialog.save_button.isEnabled())
        second = self._run(dialog.save_button.click)
        self.assertEqual(second, [])
        direct = self._run(dialog._save_keep_open)
        self.assertEqual(direct, [])
        self._close(dialog)

    def test_failed_save_keeps_draft_and_skips_confirmation(self) -> None:
        dialog = self._open()
        dialog._working_items.append(
            CategoryDraft(
                key=dialog._next_temp_key,
                code=None,
                name="",
                description="rozepsaný popis",
                sort_order=8802,
                active=True,
                is_new=True,
            ),
        )
        dialog._mark_dirty()
        with patch(
            "moduly.rizeni_rizik.ui.hazard_source_categories_management_dialog.QMessageBox.warning",
        ) as warn:
            shown = self._run(dialog.save_button.click)
        self.assertEqual(shown, [])
        warn.assert_called_once()
        self.assertIn("Název kategorie je povinný.", warn.call_args.args[2])
        draft = dialog._working_items[-1]
        self.assertEqual(draft.name, "")
        self.assertEqual(draft.description, "rozepsaný popis")
        self.assertTrue(draft.is_new)
        self.assertTrue(dialog.is_dirty())
        self.assertFalse(dialog.isHidden())
        self.assertIsNone(self._category_named(""))
        self._close(dialog)

    def test_close_prompt_save_does_not_confirm(self) -> None:
        dialog = self._open()
        name = f"Kategorie prompt {uuid.uuid4().hex[:8]}"
        dialog._working_items.append(
            CategoryDraft(
                key=dialog._next_temp_key,
                code=None,
                name=name,
                description="z promptu",
                sort_order=8803,
                active=True,
                is_new=True,
            ),
        )
        dialog._mark_dirty()
        with patch.object(dialog, "_prompt_unsaved_close", return_value="save"):
            shown = self._run(dialog.reject)
        self.assertEqual(shown, [])
        stored = self._category_named(name)
        assert stored is not None
        self.assertEqual(stored.description, "z promptu")

    def test_filter_switch_does_not_save_or_confirm(self) -> None:
        dialog = self._open()
        item = dialog._working_items[0]
        original = item.description
        item.description = f"{original} koncept"
        dialog._mark_dirty()
        shown = self._run(lambda: dialog.filter.setCurrentIndex(1))
        self.assertEqual(shown, [])
        self.assertTrue(dialog.is_dirty())
        stored = hazard_source_category_service.get_all(include_inactive=True)
        match = next(category for category in stored if category.id == item.key)
        self.assertEqual(match.description or "", original or "")
        self._close(dialog)

    def test_category_editor_save_does_not_write_or_confirm(self) -> None:
        dialog = self._open()
        child = HazardSourceCategoryDialog(dialog)
        name = f"Jen koncept {uuid.uuid4().hex[:8]}"
        child.name.setText(name)
        child.description.setPlainText("bez zápisu")
        shown = self._run(child.accept)
        self.assertEqual(shown, [])
        self.assertEqual(child.result(), QDialog.DialogCode.Accepted)
        self.assertFalse(dialog.is_dirty())
        self.assertIsNone(self._category_named(name))
        self._close(dialog)
        self._close(child)
