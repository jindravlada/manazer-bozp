"""AUDIT-ROLLBACK-1 – smoke test: AuditDialog bez dialogového UX freeze."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="audit-rollback-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication

    from core.shared.verification_type import (
        VERIFICATION_TYPE_DOCUMENTATION,
        VERIFICATION_TYPE_TERRAIN,
    )
    from moduly.audity.constants import TAB_LABELS
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui.audit_dialog import AuditDialog


class AuditRollback1StabilityTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        audit_knowledge_service.ensure_catalogs()

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)
        self._audit = audit_service.create_audit(title="ROLLBACK-1 audit")

    def tearDown(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def test_audit_dialog_has_no_editor_dialog_controller(self) -> None:
        dialog = AuditDialog(audit=self._audit)
        self.assertFalse(hasattr(dialog, "_editor"))
        self.assertFalse(
            hasattr(dialog, "install_auto_dirty_tracking")
            or getattr(type(dialog), "install_auto_dirty_tracking", None)
        )
        # Stay-open footer (bez QDialogButtonBox / bez plošného EDC).
        self.assertEqual(dialog._save_btn.text(), "Uložit")
        self.assertEqual(dialog._save_close_btn.text(), "Uložit a zavřít")
        self.assertEqual(dialog._close_btn.text(), "Zavřít")
        dialog.close()

    def test_open_switch_tabs_documentation_terrain(self) -> None:
        dialog = AuditDialog(audit=self._audit)
        dialog.show()
        self._app.processEvents()

        self.assertEqual(dialog.tabs.count(), len(TAB_LABELS))
        for index in range(dialog.tabs.count()):
            dialog.tabs.setCurrentIndex(index)
            self._app.processEvents()

        self.assertEqual(
            dialog.processes_widget._verification_type,
            VERIFICATION_TYPE_DOCUMENTATION,
        )
        self.assertEqual(
            dialog.terrain_widget._verification_type,
            VERIFICATION_TYPE_TERRAIN,
        )

        dialog.tabs.setCurrentWidget(dialog.processes_widget)
        self._app.processEvents()
        dialog.tabs.setCurrentWidget(dialog.terrain_widget)
        self._app.processEvents()
        dialog.tabs.setCurrentWidget(dialog.spis_widget)
        self._app.processEvents()

        # Editace spisu bez dirty-tracking smyčky z EDC.
        if dialog.spis_widget.year_combo.count() > 1:
            dialog.spis_widget.year_combo.setCurrentIndex(0)
            self._app.processEvents()
        dialog.spis_widget.type_combo.setCurrentIndex(0)
        self._app.processEvents()
        dialog.spis_widget.workplace_selector.set_workplace(None, "")
        self._app.processEvents()

        dialog.close()
        self._app.processEvents()


if __name__ == "__main__":
    unittest.main()
