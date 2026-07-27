"""UX-RISK-3a – dotažení správce kategorií zdrojů (tabulka, deferred save, počty)."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.rizeni_rizik.constants import (
        DEFAULT_HAZARD_SOURCE_CATEGORIES,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_source_category_service import (
        hazard_source_category_service,
    )
    from moduly.rizeni_rizik.ui.hazard_source_categories_management_dialog import (
        COL_NAME,
        CategoryDraft,
        HazardSourceCategoriesManagementDialog,
    )
    from core.widgets.editor_dialog_controller import (
        EDITOR_UNSAVED_ABORT_LABEL,
        EDITOR_UNSAVED_DISCARD_LABEL,
        EDITOR_UNSAVED_SAVE_LABEL,
    )


class UxRisk3aCategoryManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _open_dialog(self) -> HazardSourceCategoriesManagementDialog:
        dialog = HazardSourceCategoriesManagementDialog()
        dialog.show()
        return dialog

    def _close_dialog(self, dialog: HazardSourceCategoriesManagementDialog) -> None:
        dialog._mark_clean()
        dialog._closing = True
        dialog.close()

    def test_table_hides_row_numbers_and_order_column(self) -> None:
        dialog = self._open_dialog()
        try:
            self.assertFalse(dialog.table.verticalHeader().isVisible())
            self.assertEqual(dialog.table.columnCount(), 3)
            self.assertEqual(
                [
                    dialog.table.horizontalHeaderItem(index).text()
                    for index in range(dialog.table.columnCount())
                ],
                ["Název", "Popis", "Aktivní"],
            )
            self.assertEqual(dialog.table.textElideMode(), Qt.TextElideMode.ElideRight)
            first_name = dialog.table.item(0, COL_NAME)
            self.assertIsNotNone(first_name)
            self.assertTrue(first_name.toolTip())
        finally:
            self._close_dialog(dialog)

    def test_footer_has_close_then_save(self) -> None:
        dialog = self._open_dialog()
        try:
            self.assertEqual(dialog.close_button.text(), "Zavřít")
            self.assertEqual(dialog.save_button.text(), "Uložit")
            self.assertFalse(dialog.save_button.isEnabled())
            footer = dialog.layout().itemAt(dialog.layout().count() - 1).layout()
            widgets = [
                footer.itemAt(index).widget()
                for index in range(footer.count())
                if footer.itemAt(index).widget() is not None
            ]
            self.assertEqual(widgets, [dialog.close_button, dialog.save_button])
        finally:
            self._close_dialog(dialog)

    def test_counts_reflect_filter_and_search(self) -> None:
        dialog = self._open_dialog()
        try:
            total = len(DEFAULT_HAZARD_SOURCE_CATEGORIES)
            self.assertEqual(
                dialog.text_filter.count_label.text(),
                f"Zobrazeno: {total} / {total}",
            )

            dialog._working_items.append(
                CategoryDraft(
                    key=-99,
                    code=None,
                    name="ZZZ neaktivní UX-RISK-3a",
                    description="",
                    sort_order=999,
                    active=False,
                    is_new=True,
                ),
            )
            dialog._mark_dirty()
            dialog.filter.setCurrentIndex(0)  # Aktivní
            dialog.refresh()
            self.assertEqual(
                dialog.text_filter.count_label.text(),
                f"Zobrazeno: {total} / {total + 1}",
            )

            dialog.filter.setCurrentIndex(1)  # Všechny
            dialog.refresh()
            self.assertEqual(
                dialog.text_filter.count_label.text(),
                f"Zobrazeno: {total + 1} / {total + 1}",
            )

            dialog.text_filter.search_edit.setText("ZZZ neaktivní")
            self.assertEqual(
                dialog.text_filter.count_label.text(),
                f"Zobrazeno: 1 / {total + 1}",
            )
        finally:
            self._close_dialog(dialog)

    def test_deferred_save_keeps_db_clean_until_save(self) -> None:
        dialog = self._open_dialog()
        try:
            before = {
                item.code: item.name
                for item in hazard_source_category_service.get_all(include_inactive=True)
            }
            equipment = next(
                item
                for item in dialog._working_items
                if item.code == HAZARD_INVENTORY_CATEGORY_EQUIPMENT
            )
            equipment.name = "Dočasný název UX-RISK-3a"
            dialog._mark_dirty()
            dialog.refresh()
            self.assertTrue(dialog.is_dirty())
            self.assertTrue(dialog.save_button.isEnabled())

            db_equipment = hazard_source_category_service.get_by_code(
                HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            )
            assert db_equipment is not None
            self.assertEqual(db_equipment.name, before[HAZARD_INVENTORY_CATEGORY_EQUIPMENT])

            self.assertTrue(dialog._save_all())
            self.assertFalse(dialog.is_dirty())
            self.assertFalse(dialog.save_button.isEnabled())
            self.assertTrue(dialog.isVisible())

            saved = hazard_source_category_service.get_by_code(
                HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            )
            assert saved is not None
            self.assertEqual(saved.name, "Dočasný název UX-RISK-3a")

            hazard_source_category_service.update_category(
                saved.id,
                name=before[HAZARD_INVENTORY_CATEGORY_EQUIPMENT],
                description=saved.description or "",
                active=True,
                sort_order=saved.sort_order,
            )
        finally:
            self._close_dialog(dialog)

    def test_discard_close_does_not_persist(self) -> None:
        dialog = self._open_dialog()
        try:
            original = hazard_source_category_service.get_by_code(
                HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            )
            assert original is not None
            equipment = next(
                item
                for item in dialog._working_items
                if item.code == HAZARD_INVENTORY_CATEGORY_EQUIPMENT
            )
            equipment.name = "Zahodit tento název UX-RISK-3a"
            dialog._mark_dirty()

            prompts: list[str] = []

            def fake_prompt() -> str:
                prompts.append("discard")
                return "discard"

            dialog._prompt_unsaved_close = fake_prompt  # type: ignore[method-assign]
            dialog.reject()
            self.assertEqual(prompts, ["discard"])

            reloaded = hazard_source_category_service.get_by_code(
                HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            )
            assert reloaded is not None
            self.assertEqual(reloaded.name, original.name)
        finally:
            self._close_dialog(dialog)

    def test_save_validates_deactivate_with_active_source(self) -> None:
        empty = hazard_source_category_service.create_category(
            name="Kategorie k deaktivaci UX-RISK-3a",
            sort_order=500,
        )
        template = hazard_library_template_service.create_template(
            name="Zdroj blokující deaktivaci UX-RISK-3a",
            category=empty.code,
        )
        dialog = self._open_dialog()
        try:
            item = next(row for row in dialog._working_items if row.key == empty.id)
            item.active = False
            dialog._mark_dirty()
            with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Ok):
                self.assertFalse(dialog._save_all())
            reloaded = hazard_source_category_service.get_by_id(empty.id)
            assert reloaded is not None
            self.assertTrue(reloaded.active)
        finally:
            self._close_dialog(dialog)
            hazard_library_template_service.deactivate(template.id)
            hazard_source_category_service.deactivate(empty.id)

    def test_unsaved_prompt_labels(self) -> None:
        dialog = self._open_dialog()
        try:
            captured: dict[str, list[str]] = {"texts": []}

            def fake_exec(self):  # noqa: ANN001
                captured["texts"] = [button.text() for button in self.buttons()]
                cancel = next(
                    button
                    for button in self.buttons()
                    if button.text() == EDITOR_UNSAVED_ABORT_LABEL
                )
                self.clickedButton = lambda: cancel  # type: ignore[method-assign]
                return int(QMessageBox.StandardButton.Cancel)

            with patch.object(QMessageBox, "exec", fake_exec):
                result = dialog._prompt_unsaved_close()

            self.assertEqual(result, "cancel")
            self.assertEqual(
                set(captured["texts"]),
                {
                    EDITOR_UNSAVED_SAVE_LABEL,
                    EDITOR_UNSAVED_DISCARD_LABEL,
                    EDITOR_UNSAVED_ABORT_LABEL,
                },
            )
        finally:
            self._close_dialog(dialog)


if __name__ == "__main__":
    unittest.main()
