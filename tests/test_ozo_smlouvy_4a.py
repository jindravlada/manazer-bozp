"""OZO-SMLOUVY-4a: přílohy k údajům OZO."""

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

    from core.services.attachment_service import attachment_service
    from moduly.smlouvy_ozo.constants import ENTITY_OZO_PERSON
    from moduly.smlouvy_ozo.sluzby.ozo_contract_list_service import (
        ozo_contract_list_service,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_person_service import ozo_person_service
    from moduly.smlouvy_ozo.ui.ozo_person_dialog import OzoPersonDialog


class OzoSmlouvy4aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from core.models.attachment import Attachment
        from moduly.smlouvy_ozo.modely.ozo_person import OzoPerson

        with get_session() as session:
            session.execute(
                delete(Attachment).where(Attachment.entity_type == ENTITY_OZO_PERSON)
            )
            session.execute(delete(OzoPerson))
            session.commit()

    def test_attachments_after_save_optional(self) -> None:
        dialog = OzoPersonDialog()
        self.assertIsNone(dialog.attachments.entity_id)
        self.assertFalse(dialog.attachments.btn_add.isEnabled())

        dialog.first_name.setText("Jan")
        dialog.last_name.setText("Novák")
        dialog.certificate_number.setText("OZO-1")
        self.assertTrue(dialog._save())

        self.assertIsNotNone(dialog.person)
        self.assertEqual(dialog.attachments.entity_type, ENTITY_OZO_PERSON)
        self.assertEqual(dialog.attachments.entity_id, dialog.person.id)
        self.assertTrue(dialog.attachments.btn_add.isEnabled())

        tmp = Path(tempfile.mkdtemp()) / "osvedceni.pdf"
        tmp.write_bytes(b"%PDF-ozo")
        attachment_service.add_file(ENTITY_OZO_PERSON, dialog.person.id, str(tmp))
        items = attachment_service.get_for_entity(ENTITY_OZO_PERSON, dialog.person.id)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].filename, "osvedceni.pdf")
        dialog.close()

    def test_save_without_attachment(self) -> None:
        dialog = OzoPersonDialog()
        dialog.first_name.setText("Eva")
        dialog.last_name.setText("Testová")
        self.assertTrue(dialog._save())
        items = attachment_service.get_for_entity(
            ENTITY_OZO_PERSON, dialog.person.id
        )
        self.assertEqual(items, [])
        dialog.close()

    def test_list_html_does_not_include_attachments(self) -> None:
        person = ozo_person_service.save(
            first_name="Petr",
            last_name="Dvořák",
            certificate_number="OZO-77",
        )
        tmp = Path(tempfile.mkdtemp()) / "tajny-sken.pdf"
        tmp.write_bytes(b"%PDF-secret")
        attachment_service.add_file(ENTITY_OZO_PERSON, person.id, str(tmp))

        html = ozo_contract_list_service.build_html(2030)
        self.assertIn("Petr Dvořák", html)
        self.assertIn("OZO-77", html)
        self.assertNotIn("tajny-sken", html)
        self.assertNotIn("Příloh", html)
        self.assertNotIn("osvědčení.pdf", html.lower())


if __name__ == "__main__":
    unittest.main()
