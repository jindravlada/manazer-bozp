"""OZO-OSVEDCENI-UX-3: maximalizace a šířky seznamu osvědčení."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialogButtonBox, QHeaderView

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

    from moduly.smlouvy_ozo.constants import DIALOG_TITLE_OTHER_CERTIFICATES
    from moduly.smlouvy_ozo.ui.qualification_certificates_dialog import (
        QualificationCertificatesDialog,
    )
    from moduly.smlouvy_ozo.ui.smlouvy_ozo_page import SmlouvyOzoPage


class OzoOsvedceniUx3TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_other_certificates_opens_maximized(self) -> None:
        page = SmlouvyOzoPage()
        with patch(
            "moduly.smlouvy_ozo.ui.smlouvy_ozo_page.exec_maximized",
            return_value=0,
        ) as mocked:
            page.open_other_certificates()
        mocked.assert_called_once()
        dialog = mocked.call_args.args[0]
        self.assertEqual(dialog.windowTitle(), DIALOG_TITLE_OTHER_CERTIFICATES)
        page.close()

    def test_list_name_column_stretches_not_last(self) -> None:
        dialog = QualificationCertificatesDialog()
        header = dialog.table.horizontalHeader()
        self.assertFalse(header.stretchLastSection())
        self.assertEqual(
            header.sectionResizeMode(0),
            QHeaderView.ResizeMode.Stretch,
        )
        for column in (1, 2, 3, 4):
            self.assertEqual(
                header.sectionResizeMode(column),
                QHeaderView.ResizeMode.ResizeToContents,
            )
        close_btn = dialog.findChildren(QDialogButtonBox)[0].button(
            QDialogButtonBox.StandardButton.Close
        )
        self.assertIsNotNone(close_btn)
        self.assertEqual(close_btn.text(), "Zavřít")
        dialog.close()


if __name__ == "__main__":
    unittest.main()
