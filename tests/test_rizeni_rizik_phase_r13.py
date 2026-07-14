"""Fáze R13 – fotodokumentace identifikace rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from core.services.photo_optimization import HAZARD_IDENTIFICATION_PHOTO_MAX_BYTES
    from core.services.storage_service import storage_service
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
        HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        TAB_PHOTOS,
        is_identification_photos_read_only,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_identification_photo import (
        HazardIdentificationPhoto,
    )
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.sluzby.hazard_identification_peer_review_provider import (
        hazard_identification_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_photo_service import (
        HazardIdentificationPhotoError,
        hazard_identification_photo_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_dialog import (
        HazardIdentificationDialog,
    )
    from moduly.rizeni_rizik.ui.hazard_identification_photos_widget import (
        HazardIdentificationPhotosWidget,
    )


def _write_image(path: Path, *, format_name: str, size: tuple[int, int] = (80, 60)) -> Path:
    image = Image.new("RGB", size, color=(40, 120, 200))
    image.save(path, format=format_name)
    return path


def _write_large_jpeg(path: Path) -> Path:
    # Velký obraz s vysokou detailností, aby JPEG překročil 1 MB před optimalizací.
    image = Image.new("RGB", (4000, 3000))
    pixels = image.load()
    for y in range(0, 3000, 3):
        for x in range(0, 4000, 3):
            pixels[x, y] = ((x * 37) % 256, (y * 53) % 256, ((x + y) * 17) % 256)
    image.save(path, format="JPEG", quality=95)
    return path


class HazardIdentificationPhotosR13TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(HazardIdentificationPhoto))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        operation = settings_service.save_workplace(
            name="Provoz R13",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="Pracoviště R13",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        person = person_service.create_person(first_name="Foto", last_name="Test")
        self.identification = hazard_identification_service.create_identification(
            operation_id=operation.id,
            workplace_id=workplace.id,
            responsible_person_id=person.id,
        )
        self.workspace = Path(tempfile.mkdtemp())
        self.provider = hazard_identification_peer_review_provider

    def test_photos_table_exists(self) -> None:
        columns = _table_columns("hazard_identification_photos")
        for name in (
            "hazard_identification_id",
            "filename",
            "stored_filename",
            "relative_path",
            "caption",
            "note",
            "taken_at",
            "file_size",
            "width",
            "height",
            "active",
            "sort_order",
        ):
            self.assertIn(name, columns)

    def test_insert_jpg_png_webp(self) -> None:
        jpg = _write_image(self.workspace / "a.jpg", format_name="JPEG")
        png = _write_image(self.workspace / "b.png", format_name="PNG")
        webp = _write_image(self.workspace / "c.webp", format_name="WEBP")

        for source in (jpg, png, webp):
            photo = hazard_identification_photo_service.create_photo(
                hazard_identification_id=self.identification.id,
                source_path=source,
                caption=f"Popis {source.suffix}",
            )
            absolute = hazard_identification_photo_service.absolute_path(photo)
            self.assertTrue(absolute.is_file())
            self.assertTrue(photo.relative_path.startswith("rizeni_rizik/"))
            self.assertIn("/fotografie/", photo.relative_path)
            self.assertNotIn(str(storage_service.base), photo.relative_path)
            self.assertLessEqual(photo.file_size, HAZARD_IDENTIFICATION_PHOTO_MAX_BYTES)
            self.assertTrue(photo.stored_filename.endswith(".jpg"))

    def test_reject_unsupported_format(self) -> None:
        gif = self.workspace / "x.gif"
        Image.new("RGB", (20, 20), color=(1, 2, 3)).save(gif, format="GIF")
        with self.assertRaises(HazardIdentificationPhotoError) as ctx:
            hazard_identification_photo_service.create_photo(
                hazard_identification_id=self.identification.id,
                source_path=gif,
            )
        self.assertIn("JPG", str(ctx.exception))

    def test_auto_shrink_under_1mb(self) -> None:
        large = _write_large_jpeg(self.workspace / "large.jpg")
        self.assertGreater(large.stat().st_size, HAZARD_IDENTIFICATION_PHOTO_MAX_BYTES)
        photo = hazard_identification_photo_service.create_photo(
            hazard_identification_id=self.identification.id,
            source_path=large,
            caption="Velká",
        )
        self.assertLessEqual(photo.file_size, HAZARD_IDENTIFICATION_PHOTO_MAX_BYTES)
        absolute = hazard_identification_photo_service.absolute_path(photo)
        self.assertLessEqual(absolute.stat().st_size, HAZARD_IDENTIFICATION_PHOTO_MAX_BYTES)

    def test_relative_path_and_open(self) -> None:
        source = _write_image(self.workspace / "open.jpg", format_name="JPEG")
        photo = hazard_identification_photo_service.create_photo(
            hazard_identification_id=self.identification.id,
            source_path=source,
        )
        self.assertFalse(Path(photo.relative_path).is_absolute())
        absolute = hazard_identification_photo_service.absolute_path(photo)
        self.assertTrue(absolute.is_file())
        self.assertTrue(hazard_identification_photo_service.file_exists(photo))

        widget = HazardIdentificationPhotosWidget()
        widget.set_identification(self.identification.id, read_only=False)
        widget.table.selectRow(0)
        with patch(
            "moduly.rizeni_rizik.ui.hazard_identification_photos_widget.ImageViewerDialog"
        ) as viewer_cls:
            viewer = viewer_cls.return_value
            viewer.exec.return_value = 0
            widget.open_selected_photo()
            viewer_cls.assert_called_once()
            called_path = viewer_cls.call_args.args[0]
            self.assertEqual(Path(called_path), absolute)

    def test_missing_file_shows_warning(self) -> None:
        source = _write_image(self.workspace / "missing.jpg", format_name="JPEG")
        photo = hazard_identification_photo_service.create_photo(
            hazard_identification_id=self.identification.id,
            source_path=source,
        )
        absolute = hazard_identification_photo_service.absolute_path(photo)
        absolute.unlink()
        self.assertFalse(hazard_identification_photo_service.file_exists(photo))

        widget = HazardIdentificationPhotosWidget()
        widget.set_identification(self.identification.id, read_only=False)
        widget.table.selectRow(0)
        with patch(
            "moduly.rizeni_rizik.ui.hazard_identification_photos_widget.QMessageBox.warning"
        ) as warning:
            widget.open_selected_photo()
            warning.assert_called_once()

    def test_read_only_mode(self) -> None:
        self.assertTrue(is_identification_photos_read_only(HAZARD_IDENTIFICATION_STATUS_COMPLETED))
        self.assertTrue(is_identification_photos_read_only(HAZARD_IDENTIFICATION_STATUS_ARCHIVED))

        source = _write_image(self.workspace / "ro.jpg", format_name="JPEG")
        hazard_identification_photo_service.create_photo(
            hazard_identification_id=self.identification.id,
            source_path=source,
        )
        widget = HazardIdentificationPhotosWidget()
        widget.set_identification(self.identification.id, read_only=True)
        self.assertFalse(widget.add_btn.isEnabled())
        self.assertFalse(widget.edit_btn.isEnabled())
        self.assertFalse(widget.activate_btn.isEnabled())
        self.assertFalse(widget.deactivate_btn.isEnabled())
        self.assertTrue(widget.open_btn.isEnabled())

        with patch(
            "moduly.rizeni_rizik.ui.hazard_identification_photos_widget.QMessageBox.information"
        ) as info:
            self.assertFalse(widget.add_photo())
            info.assert_called()

    def test_photos_not_in_ai_export(self) -> None:
        source = _write_image(self.workspace / "ai.jpg", format_name="JPEG")
        photo = hazard_identification_photo_service.create_photo(
            hazard_identification_id=self.identification.id,
            source_path=source,
            caption="Tajná fotka z obhlídky",
        )
        hazard_inventory_item_service.create_item(
            hazard_identification_id=self.identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Jeřáb",
        )
        content = self.provider.build_export_content(
            self.identification.id,
            options=AiPeerReviewExportOptions(),
        )
        blob = "\n".join(
            [
                content.data_text,
                content.overview_text,
                str(content.zadani_json),
                photo.relative_path,
                photo.stored_filename,
                "Tajná fotka z obhlídky",
            ]
        )
        self.assertNotIn("Tajná fotka z obhlídky", content.data_text)
        self.assertNotIn(photo.stored_filename, content.data_text)
        self.assertNotIn("fotografie", content.data_text.casefold())
        self.assertNotIn(photo.relative_path, str(content.zadani_json))

    def test_dialog_tab_order_includes_photos(self) -> None:
        dialog = HazardIdentificationDialog(identification=self.identification)
        self.assertEqual(dialog.tabs.tabText(1), TAB_PHOTOS)
        self.assertTrue(dialog.tabs.isTabEnabled(1))
        self.assertTrue(dialog.tabs.isTabEnabled(4))  # AI
        self.assertIs(dialog.tabs.widget(1), dialog.photos_widget)


if __name__ == "__main__":
    unittest.main()
