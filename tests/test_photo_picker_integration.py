"""UX-PHOTO-1b – zapojení PhotoPickerDialog do auditů a kontrol/prověrek."""

from __future__ import annotations

import importlib
import inspect
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-photo-1b-"))
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
    from core.shared.constants import (
        ENTITY_AUDITY,
        ENTITY_PROVERKY,
    )
    from core.shared.modely.control_result import ControlResult
    from core.shared.sluzby.control_result_service import (
        ControlPointContext,
        control_result_service,
    )
    from core.ui.photo_picker_dialog import PhotoPickerDialog
    from core.widgets.control_result_photo_widget import ControlResultPhotoWidget
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _context() -> ControlPointContext:
    return ControlPointContext(
        area_id="oblast",
        area_label="Oblast",
        section_id="sekce",
        section_label="Sekce",
        control_point_id="bod_1",
        control_point_label="Kontrolní bod",
    )


class PhotoPickerIntegrationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _app()

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(ControlResult))
            session.commit()
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def test_widget_source_uses_photo_picker_not_file_dialog(self) -> None:
        source = inspect.getsource(ControlResultPhotoWidget)
        self.assertIn("PhotoPickerDialog", source)
        self.assertNotIn("QFileDialog", source)

        module_source = Path(
            "core/widgets/control_result_photo_widget.py"
        ).read_text(encoding="utf-8")
        self.assertIn("PhotoPickerDialog.get_photo", module_source)
        self.assertNotIn("QFileDialog.getOpenFileName", module_source)

    def test_audits_and_proverky_use_control_result_photo_widget(self) -> None:
        audit_source = Path(
            "moduly/audity/ui/audit_knowledge_criterion_widget.py"
        ).read_text(encoding="utf-8")
        proverky_source = Path(
            "moduly/proverky/ui/bozp_knowledge_section_widget.py"
        ).read_text(encoding="utf-8")
        self.assertIn("ControlResultPhotoWidget", audit_source)
        self.assertIn("ControlResultPhotoWidget", proverky_source)

    def test_add_photo_uses_picker_and_keeps_attach_storage(self) -> None:
        workplace = settings_service.save_workplace(name="Provoz foto")
        audit = audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
        )
        source = _TMP / "source_photo.jpg"
        Image.new("RGB", (80, 60), color=(30, 90, 140)).save(source, format="JPEG")

        widget = ControlResultPhotoWidget()
        widget.configure(
            entity_type=ENTITY_AUDITY,
            entity_id=audit.id,
            context=_context(),
            must_be_saved_message="uložit",
        )

        with patch.object(PhotoPickerDialog, "get_photo", return_value=source) as mock_pick:
            widget._add_photo()
            mock_pick.assert_called_once()

        row = control_result_service.get_for_control_point(
            ENTITY_AUDITY, audit.id, _context()
        )
        self.assertIsNotNone(row)
        assert row is not None
        self.assertTrue(row.photo_path)
        stored = control_result_service.resolve_photo_path(row)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertTrue(stored.is_file())

    def test_add_photo_cancel_does_not_change_storage(self) -> None:
        workplace = settings_service.save_workplace(name="Provoz cancel")
        audit = audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
        )
        widget = ControlResultPhotoWidget()
        widget.configure(
            entity_type=ENTITY_AUDITY,
            entity_id=audit.id,
            context=_context(),
            must_be_saved_message="uložit",
        )
        with patch.object(PhotoPickerDialog, "get_photo", return_value=None):
            widget._add_photo()
        row = control_result_service.get_for_control_point(
            ENTITY_AUDITY, audit.id, _context()
        )
        self.assertTrue(row is None or not row.photo_path)

    def test_proverky_entity_also_stores_via_same_widget(self) -> None:
        inspection = bozp_inspection_service.create_inspection()
        source = _TMP / "proverka_photo.jpg"
        Image.new("RGB", (50, 40), color=(20, 120, 60)).save(source, format="JPEG")

        widget = ControlResultPhotoWidget()
        widget.configure(
            entity_type=ENTITY_PROVERKY,
            entity_id=inspection.id,
            context=_context(),
            must_be_saved_message="uložit",
        )
        with patch.object(PhotoPickerDialog, "get_photo", return_value=source):
            widget._add_photo()

        row = control_result_service.get_for_control_point(
            ENTITY_PROVERKY, inspection.id, _context()
        )
        self.assertIsNotNone(row)
        assert row is not None
        self.assertTrue(str(row.photo_path).startswith("control_results/"))


if __name__ == "__main__":
    unittest.main()
