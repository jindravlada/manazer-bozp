"""OZO-HIST-UX-3: maximalizované okno OZO."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.smlouvy_ozo.constants import DIALOG_TITLE_OZO_PERSON
    from moduly.smlouvy_ozo.ui.smlouvy_ozo_page import SmlouvyOzoPage


class OzoHistUx3TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_ozo_person_opens_maximized(self) -> None:
        page = SmlouvyOzoPage()
        with patch(
            "moduly.smlouvy_ozo.ui.smlouvy_ozo_page.exec_maximized",
            return_value=0,
        ) as mocked:
            page.edit_ozo_person()
        mocked.assert_called_once()
        dialog = mocked.call_args.args[0]
        self.assertEqual(dialog.windowTitle(), DIALOG_TITLE_OZO_PERSON)
        page.close()


if __name__ == "__main__":
    unittest.main()
