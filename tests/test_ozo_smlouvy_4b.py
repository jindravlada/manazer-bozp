"""OZO-SMLOUVY-4b: tituly OZO."""

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

    from moduly.smlouvy_ozo.constants import format_ozo_display_name
    from moduly.smlouvy_ozo.sluzby.ozo_contract_list_service import (
        ozo_contract_list_service,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_person_service import ozo_person_service
    from moduly.smlouvy_ozo.ui.ozo_person_dialog import OzoPersonDialog


class OzoSmlouvy4bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.smlouvy_ozo.modely.ozo_person import OzoPerson

        with get_session() as session:
            session.execute(delete(OzoPerson))
            session.commit()

    def test_format_without_titles(self) -> None:
        self.assertEqual(
            format_ozo_display_name("", "Jan", "Novák", ""),
            "Jan Novák",
        )

    def test_format_title_before_only(self) -> None:
        self.assertEqual(
            format_ozo_display_name("Ing.", "Jan", "Novák", ""),
            "Ing. Jan Novák",
        )

    def test_format_title_after_only(self) -> None:
        self.assertEqual(
            format_ozo_display_name("", "Jan", "Novák", "DiS."),
            "Jan Novák, DiS.",
        )

    def test_format_both_titles(self) -> None:
        self.assertEqual(
            format_ozo_display_name("Ing.", "Jan", "Novák", "Ph.D."),
            "Ing. Jan Novák, Ph.D.",
        )

    def test_format_no_double_comma(self) -> None:
        self.assertEqual(
            format_ozo_display_name("Ing.", "Jan", "Novák", ", Ph.D."),
            "Ing. Jan Novák, Ph.D.",
        )
        self.assertEqual(
            format_ozo_display_name("", "Jan", "Novák", ", DiS."),
            "Jan Novák, DiS.",
        )

    def test_format_no_double_spaces(self) -> None:
        self.assertEqual(
            format_ozo_display_name("  Ing.  ", " Jan ", " Novák ", "  Ph.D. "),
            "Ing. Jan Novák, Ph.D.",
        )

    def test_save_and_full_name(self) -> None:
        person = ozo_person_service.save(
            title_before="Ing.",
            first_name="Jan",
            last_name="Novák",
            title_after="Ph.D.",
            certificate_number="12345",
        )
        self.assertEqual(person.title_before, "Ing.")
        self.assertEqual(person.title_after, "Ph.D.")
        self.assertEqual(
            ozo_person_service.full_name(person),
            "Ing. Jan Novák, Ph.D.",
        )

    def test_validation_does_not_require_titles(self) -> None:
        ozo_person_service.save(
            first_name="Eva",
            last_name="Svobodová",
            certificate_number="C-1",
        )
        self.assertEqual(ozo_person_service.missing_for_list_output(), [])
        self.assertEqual(
            ozo_person_service.full_name(),
            "Eva Svobodová",
        )

    def test_list_html_includes_titles(self) -> None:
        ozo_person_service.save(
            title_before="Ing.",
            first_name="Jan",
            last_name="Novák",
            title_after="Ph.D.",
            certificate_number="12345",
        )
        html = ozo_contract_list_service.build_html(2030)
        self.assertIn("Ing. Jan Novák, Ph.D.", html)
        self.assertIn("12345", html)

    def test_dialog_field_order_and_titles(self) -> None:
        dialog = OzoPersonDialog()
        dialog.title_before.setText("Mgr.")
        dialog.first_name.setText("Anna")
        dialog.last_name.setText("Veselá")
        dialog.title_after.setText("MBA")
        data = dialog.get_data()
        self.assertEqual(
            list(data.keys())[:4],
            ["title_before", "first_name", "last_name", "title_after"],
        )
        self.assertTrue(dialog._save())
        self.assertEqual(
            ozo_person_service.full_name(dialog.person),
            "Mgr. Anna Veselá, MBA",
        )
        dialog.close()


if __name__ == "__main__":
    unittest.main()
