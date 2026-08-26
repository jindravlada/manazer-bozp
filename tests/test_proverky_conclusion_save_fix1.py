"""PROVERKY-CONCLUSION-SAVE-FIX1: uložení doporučení vedoucího (záložka Závěr)."""

from __future__ import annotations

import importlib
import os
import shutil
import tempfile
import unittest
import uuid
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="proverky-conclusion-save-fix1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.shared.section_summary import NOTES_MODE_SECTION_SUMMARY_V1
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.constants import (
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
    )
    from moduly.proverky.modely.bozp_inspection import BozpInspection
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.protokol_proverky_service import protokol_proverky_service
    from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog

REPO_ROOT = Path(__file__).resolve().parents[1]
CONCLUSION_TEXT = "Doporučení: příliš žluťoučký kůň úpěl ďábelské ódy."
MULTILINE_TEXT = "První odstavec.\n\nDruhý odstavec s čárkou."


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _read_inspection(inspection_id: int) -> BozpInspection:
    loaded = bozp_inspection_service.get_by_id(inspection_id)
    assert loaded is not None
    return loaded


def _updated_at(inspection_id: int):
    with get_session() as session:
        row = session.get(BozpInspection, inspection_id)
        assert row is not None
        return row.updated_at


def _sync_templates() -> None:
    import moduly.proverky.sluzby.protokol_proverky_service as protokol_module

    importlib.reload(protokol_module)
    for name, detailed in (
        ("ProtokolProverkyBOZP.odt", False),
        ("PodrobnaZpravaProverky.odt", True),
    ):
        bundled = REPO_ROOT / "moduly" / "proverky" / "templates" / "exporty" / name
        target = protokol_module.protokol_proverky_service.template_path(
            detailed=detailed
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bundled, target)


class ProverkyConclusionSaveFix1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])
        _sync_templates()

    def setUp(self) -> None:
        for inspection in list(bozp_inspection_service.get_all()):
            bozp_inspection_service.delete_inspection(inspection.id)
        suffix = uuid.uuid4().hex[:6]
        self.leader_id = settings_service.save_worker(
            first_name="Jan", last_name=f"L-{suffix}"
        ).id
        self.workplace_rep_id = settings_service.save_worker(
            first_name="Eva", last_name=f"W-{suffix}"
        ).id
        self.union_id = person_service.create_person(
            first_name="Lucie", last_name=f"U-{suffix}"
        ).id
        self.workplace = settings_service.save_workplace(name=f"Provoz-{suffix}")

    def _create_inspection(self, *, notes_mode=NOTES_MODE_SECTION_SUMMARY_V1, **fields):
        payload = {
            "workplace_id": self.workplace.id,
            "workplace_name": self.workplace.name,
            "year": 2026,
            "started_at": date(2026, 8, 1),
            "title": "Prověrka závěr",
            "notes_mode": notes_mode,
        }
        payload.update(fields)
        inspection = bozp_inspection_service.create_inspection(**payload)
        bozp_inspection_commission_service.save_members(
            inspection.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": self.leader_id,
                    "display_name": "Jan L",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": self.workplace_rep_id,
                    "display_name": "Eva W",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "person_id": self.union_id,
                    "display_name": "Lucie U",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
        return _read_inspection(inspection.id)

    def _open_dialog(self, inspection) -> BozpInspectionDialog:
        dialog = BozpInspectionDialog(inspection=inspection)
        dialog.commission_widget.leader_selector.set_person_id(self.leader_id)
        dialog.commission_widget.workplace_selector.set_person_id(self.workplace_rep_id)
        dialog.commission_widget.union_selector.set_person_id(self.union_id)
        dialog._capture_baseline()
        return dialog

    def _assert_saved(self, inspection_id: int, text: str) -> None:
        loaded = _read_inspection(inspection_id)
        self.assertEqual(loaded.doporuceni_vedouciho, text)

    def test_new_mode_save_keep_open_writes_db_and_widget(self) -> None:
        inspection = self._create_inspection()
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.doporuceni_edit.setPlainText(CONCLUSION_TEXT)
        self.assertTrue(dialog._persist())
        self.assertEqual(
            dialog.conclusion_widget.doporuceni_edit.toPlainText(), CONCLUSION_TEXT
        )
        self._assert_saved(inspection.id, CONCLUSION_TEXT)
        self.assertFalse(dialog._is_dirty())

    def test_new_mode_save_and_close_reopen(self) -> None:
        inspection = self._create_inspection()
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.doporuceni_edit.setPlainText(CONCLUSION_TEXT)
        dialog._save_and_close()
        self._assert_saved(inspection.id, CONCLUSION_TEXT)
        reopened = self._open_dialog(_read_inspection(inspection.id))
        self.assertEqual(
            reopened.conclusion_widget.doporuceni_edit.toPlainText(), CONCLUSION_TEXT
        )

    def test_new_mode_close_prompt_save(self) -> None:
        inspection = self._create_inspection()
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.doporuceni_edit.setPlainText(CONCLUSION_TEXT)
        with patch(
            "moduly.proverky.ui.bozp_inspection_dialog.confirm_unsaved_editor_close",
            return_value="save",
        ):
            self.assertFalse(dialog._confirm_close())
        self._assert_saved(inspection.id, CONCLUSION_TEXT)

    def test_new_mode_close_prompt_discard(self) -> None:
        inspection = self._create_inspection(doporuceni_vedouciho="Původní")
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.doporuceni_edit.setPlainText("Zahozeno")
        with patch(
            "moduly.proverky.ui.bozp_inspection_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(dialog._confirm_close())
        self._assert_saved(inspection.id, "Původní")

    def test_legacy_save_keep_open_and_reopen(self) -> None:
        inspection = self._create_inspection(notes_mode=None)
        self.assertIsNone(inspection.notes_mode)
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.doporuceni_edit.setPlainText(CONCLUSION_TEXT)
        self.assertTrue(dialog._persist())
        self._assert_saved(inspection.id, CONCLUSION_TEXT)
        reopened = self._open_dialog(_read_inspection(inspection.id))
        self.assertEqual(
            reopened.conclusion_widget.doporuceni_edit.toPlainText(), CONCLUSION_TEXT
        )

    def test_legacy_close_save_and_discard(self) -> None:
        inspection = self._create_inspection(notes_mode=None, doporuceni_vedouciho="A")
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.doporuceni_edit.setPlainText("B")
        with patch(
            "moduly.proverky.ui.bozp_inspection_dialog.confirm_unsaved_editor_close",
            return_value="save",
        ):
            dialog._confirm_close()
        self._assert_saved(inspection.id, "B")

        dialog2 = self._open_dialog(_read_inspection(inspection.id))
        dialog2.conclusion_widget.doporuceni_edit.setPlainText("C")
        with patch(
            "moduly.proverky.ui.bozp_inspection_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(dialog2._confirm_close())
        self._assert_saved(inspection.id, "B")

    def test_existing_inspection_edit(self) -> None:
        inspection = self._create_inspection(doporuceni_vedouciho="Původní závěr")
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.doporuceni_edit.setPlainText("Upravený závěr")
        self.assertTrue(dialog._persist())
        self._assert_saved(inspection.id, "Upravený závěr")

    def test_multiline_and_czech_characters(self) -> None:
        inspection = self._create_inspection()
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.doporuceni_edit.setPlainText(MULTILINE_TEXT)
        self.assertTrue(dialog._persist())
        self._assert_saved(inspection.id, MULTILINE_TEXT)
        self.assertEqual(
            dialog.conclusion_widget.doporuceni_edit.toPlainText(), MULTILINE_TEXT
        )

    def test_empty_conclusion_is_allowed(self) -> None:
        inspection = self._create_inspection(doporuceni_vedouciho="Bylo vyplněno")
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.doporuceni_edit.setPlainText("   \n  ")
        self.assertTrue(dialog._persist())
        self._assert_saved(inspection.id, "")

    def test_refresh_after_save_does_not_overwrite(self) -> None:
        inspection = self._create_inspection()
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.doporuceni_edit.setPlainText(CONCLUSION_TEXT)
        self.assertTrue(dialog._persist())
        dialog.conclusion_widget.refresh()
        dialog._on_related_data_changed()
        self.assertEqual(
            dialog.conclusion_widget.doporuceni_edit.toPlainText(), CONCLUSION_TEXT
        )
        self._assert_saved(inspection.id, CONCLUSION_TEXT)

    def test_tab_switch_and_related_refresh_keep_unsaved_text(self) -> None:
        inspection = self._create_inspection()
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.doporuceni_edit.setPlainText(CONCLUSION_TEXT)
        dialog.tabs.setCurrentWidget(dialog.spis_widget)
        dialog.tabs.setCurrentWidget(dialog.areas_widget)
        dialog.tabs.setCurrentWidget(dialog.conclusion_widget)
        dialog._on_related_data_changed()
        self.assertEqual(
            dialog.conclusion_widget.doporuceni_edit.toPlainText(), CONCLUSION_TEXT
        )
        self._assert_saved(inspection.id, "")

    def test_protocol_and_detailed_report_use_saved_text(self) -> None:
        inspection = self._create_inspection()
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.doporuceni_edit.setPlainText(CONCLUSION_TEXT)
        self.assertTrue(dialog._persist())
        protocol = _odt_content(
            protokol_proverky_service.generate_for_inspection(
                _read_inspection(inspection.id)
            )
        )
        detailed = _odt_content(
            protokol_proverky_service.generate_detailed_report_for_inspection(
                _read_inspection(inspection.id)
            )
        )
        self.assertIn(CONCLUSION_TEXT, protocol)
        self.assertIn(CONCLUSION_TEXT, detailed)

    def test_unsaved_change_does_not_enter_export_or_db(self) -> None:
        inspection = self._create_inspection(doporuceni_vedouciho="Uložené")
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.doporuceni_edit.setPlainText("Jen v editoru")
        content = _odt_content(
            protokol_proverky_service.generate_for_inspection(dialog.inspection)
        )
        self.assertIn("Uložené", content)
        self.assertNotIn("Jen v editoru", content)
        self._assert_saved(inspection.id, "Uložené")

    def test_repeated_export_does_not_write_db(self) -> None:
        inspection = self._create_inspection(doporuceni_vedouciho=CONCLUSION_TEXT)
        before = _updated_at(inspection.id)
        protokol_proverky_service.generate_for_inspection(inspection)
        protokol_proverky_service.generate_detailed_report_for_inspection(inspection)
        self.assertEqual(_updated_at(inspection.id), before)
        self._assert_saved(inspection.id, CONCLUSION_TEXT)

    def test_open_dialog_does_not_write(self) -> None:
        inspection = self._create_inspection(doporuceni_vedouciho=CONCLUSION_TEXT)
        before = _updated_at(inspection.id)
        dialog = self._open_dialog(inspection)
        self.assertEqual(
            dialog.conclusion_widget.doporuceni_edit.toPlainText(), CONCLUSION_TEXT
        )
        self.assertEqual(_updated_at(inspection.id), before)
        self._assert_saved(inspection.id, CONCLUSION_TEXT)


if __name__ == "__main__":
    unittest.main()
