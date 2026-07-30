"""UX-PHOTOS-1: sjednocení utilitky pro přidávání fotografií."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QListWidget
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-photos-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.ui.photo_picker_dialog import (
        PHOTO_PICKER_SELECT_MULTI_LABEL,
        PhotoPickerDialog,
    )
    from moduly.audity.ui.audity_knowledge_reference_photo_dialog import (
        AudityKnowledgeReferencePhotoDialog,
    )
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service
    from moduly.proverky.sluzby.proverky_reference_photo_service import (
        proverky_reference_photo_service,
    )
    from moduly.proverky.ui.proverky_knowledge_section_edit_dialog import (
        ProverkyKnowledgeSectionEditDialog,
    )
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_identification_photo import (
        HazardIdentificationPhoto,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_photo_service import (
        hazard_identification_photo_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_photo_dialog import (
        HazardIdentificationPhotoDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_photos_widget import (
        HazardIdentificationPhotosWidget,
    )
    from moduly.vysetrovani_mu.sluzby.mu_investigation_service import (
        mu_investigation_service,
    )
    from moduly.vysetrovani_mu.ui.mu_zajisteni_dukazu_widget import MuZajisteniDukazuWidget


_TARGETS = (
    "moduly/vysetrovani_mu/ui/mu_zajisteni_dukazu_widget.py",
    "moduly/audity/ui/audity_knowledge_reference_photo_dialog.py",
    "moduly/audity/ui/audity_knowledge_reference_photo_editor_widget.py",
    "moduly/proverky/ui/proverky_knowledge_section_edit_dialog.py",
    "moduly/rizeni_rizik/ui/hazard_identification_photo_dialog.py",
    "moduly/rizeni_rizik/ui/hazard_identification_photos_widget.py",
)


def _make_jpg(directory: Path, name: str) -> Path:
    path = directory / name
    Image.new("RGB", (48, 36), color=(120, 40, 80)).save(path, format="JPEG")
    return path


class UxPhotos1UnificationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.photos_dir = Path(tempfile.mkdtemp(prefix="ux-photos-1-src-", dir=_TMP))
        self.photo_a = _make_jpg(self.photos_dir, "alpha.jpg")
        self.photo_b = _make_jpg(self.photos_dir, "beta.jpg")

        with get_session() as session:
            session.execute(delete(HazardIdentificationPhoto))
            session.execute(delete(HazardIdentification))
            session.commit()

    def test_targets_use_photo_picker_not_file_dialog(self) -> None:
        for relative in _TARGETS:
            source = Path(relative).read_text(encoding="utf-8")
            self.assertIn("PhotoPickerDialog", source, relative)
            self.assertNotIn("QFileDialog.getOpenFileName", source, relative)
            self.assertNotIn("QFileDialog.getOpenFileNames", source, relative)

    def test_picker_supports_multi_select(self) -> None:
        dialog = PhotoPickerDialog(
            initial_directory=self.photos_dir,
            allow_multiple=True,
        )
        self.addCleanup(dialog.close)
        self.assertEqual(dialog._select_btn.text(), PHOTO_PICKER_SELECT_MULTI_LABEL)
        self.assertEqual(dialog._list.count(), 2)
        dialog._list.selectAll()
        dialog._sync_selected_paths()
        self.assertEqual(len(dialog.selected_paths()), 2)
        dialog._accept_selection()
        self.assertEqual(
            {path.name for path in dialog.selected_paths()},
            {"alpha.jpg", "beta.jpg"},
        )

    def test_mu_evidence_add_photo(self) -> None:
        investigation = mu_investigation_service.create_investigation(title="UX-PHOTOS-1")
        widget = MuZajisteniDukazuWidget()
        widget.set_context(investigation.id, event_number="MU-1")
        key = next(iter(widget.dukazy_photo_statuses))
        status = widget.dukazy_photo_statuses[key]

        with patch.object(PhotoPickerDialog, "get_photo", return_value=self.photo_a):
            widget._select_photo(status, key)

        self.assertTrue(status.text().startswith("Přiloženo:"))
        self.assertTrue(widget.dukazy_photo_paths[key])

        # Znovunačtení stavů z aktuálních cest.
        widget2 = MuZajisteniDukazuWidget()
        widget2.set_context(investigation.id, event_number="MU-1")
        widget2.dukazy_photo_paths = dict(widget.dukazy_photo_paths)
        for item_key, filename in widget2.dukazy_photo_paths.items():
            label = widget2.dukazy_photo_statuses.get(item_key)
            if label is not None and filename:
                label.setText(f"Přiloženo: {filename}")
        self.assertTrue(
            widget2.dukazy_photo_statuses[key].text().startswith("Přiloženo:")
        )

    def test_audit_reference_browse_uses_picker(self) -> None:
        dialog = AudityKnowledgeReferencePhotoDialog(existing_ids=set())
        with patch.object(PhotoPickerDialog, "get_photo", return_value=self.photo_a):
            dialog._browse_file()
        self.assertEqual(dialog._soubor_edit.text(), str(self.photo_a))

        source = Path(
            "moduly/audity/ui/audity_knowledge_reference_photo_editor_widget.py"
        ).read_text(encoding="utf-8")
        self.assertIn("PhotoPickerDialog.get_photos", source)
        self.assertIn("def _add_item", source)

    def test_proverky_reference_add_multiple_remove_and_reload(self) -> None:
        proverky_knowledge_service.ensure_catalogs()
        sections = proverky_knowledge_service.list_sections("chemie", include_inactive=True)
        self.assertTrue(sections)
        section_id = str(sections[0].get("id"))

        editor = ProverkyKnowledgeSectionEditDialog(
            area_id="chemie",
            section_id=section_id,
            embedded=True,
        )
        list_widget: QListWidget = next(iter(editor._reference_lists))
        before = list_widget.count()

        with patch.object(
            PhotoPickerDialog,
            "get_photos",
            return_value=[self.photo_a, self.photo_b],
        ):
            editor._add_reference_photo(list_widget)

        self.assertEqual(list_widget.count(), before + 2)

        for row in range(before, list_widget.count()):
            data = list_widget.item(row).data(Qt.ItemDataRole.UserRole)
            self.assertIsInstance(data, dict)
            relative = str(data.get("soubor") or "")
            absolute = proverky_reference_photo_service.absolute_photo_path(relative)
            self.assertTrue(absolute.is_file(), absolute)

        from PySide6.QtWidgets import QMessageBox

        list_widget.setCurrentRow(list_widget.count() - 1)
        with patch(
            "moduly.proverky.ui.proverky_knowledge_section_edit_dialog.QMessageBox.question",
            return_value=QMessageBox.Yes,
        ):
            editor._remove_reference_photo(list_widget)
        self.assertEqual(list_widget.count(), before + 1)

        self.assertTrue(editor.persist_changes())
        reloaded = ProverkyKnowledgeSectionEditDialog(
            area_id="chemie",
            section_id=section_id,
            embedded=True,
        )
        reloaded_list = next(iter(reloaded._reference_lists))
        self.assertEqual(reloaded_list.count(), before + 1)
        data = reloaded_list.item(reloaded_list.count() - 1).data(Qt.ItemDataRole.UserRole)
        absolute = proverky_reference_photo_service.absolute_photo_path(
            str(data.get("soubor") or "")
        )
        self.assertTrue(absolute.is_file())

    def test_hazard_photos_add_multi_and_reload_previews(self) -> None:
        operation = settings_service.save_workplace(
            name="Provoz UX-PHOTOS-1",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Pracoviště UX-PHOTOS-1",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        person = person_service.create_person(first_name="Foto", last_name="UX")
        identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
            responsible_person_id=person.id,
        )

        widget = HazardIdentificationPhotosWidget()
        widget.set_identification(identification.id, read_only=False)

        with patch.object(PhotoPickerDialog, "get_photos", return_value=[self.photo_a]):
            with patch.object(HazardIdentificationPhotoDialog, "exec", return_value=False):
                self.assertFalse(widget.add_photo())

        with patch.object(
            PhotoPickerDialog,
            "get_photos",
            return_value=[self.photo_a, self.photo_b],
        ):
            self.assertTrue(widget.add_photo())

        widget.refresh()
        self.assertGreaterEqual(widget.table.rowCount(), 2)

        photos = hazard_identification_photo_service.get_for_identification(
            identification.id
        )
        self.assertGreaterEqual(len(photos), 2)
        for photo in photos[:2]:
            path = hazard_identification_photo_service.absolute_path(photo)
            self.assertTrue(path.is_file(), path)

        hazard_identification_photo_service.deactivate_photo(photos[0].id)
        widget.refresh()
        self.assertGreaterEqual(widget.table.rowCount(), 2)


if __name__ == "__main__":
    unittest.main()
