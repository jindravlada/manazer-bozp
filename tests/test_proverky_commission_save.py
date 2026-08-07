import html
import importlib
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.proverky.constants import (
        COMMISSION_MISSING_LEADER_MESSAGE,
        COMMISSION_MISSING_UNION_MESSAGE,
        COMMISSION_MISSING_WORKPLACE_MESSAGE,
        COMMISSION_RECORD_INVITED,
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_MEMBER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
    )
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.protokol_proverky_service import protokol_proverky_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _odt_plain_text(content: str) -> str:
    """ODT content.xml → čitelný text (tagy, text:s, line-break)."""
    text = re.sub(r"<text:line-break\s*/>", "\n", content)
    text = re.sub(
        r'<text:s\s+text:c="(\d+)"/>',
        lambda match: " " * int(match.group(1)),
        text,
    )
    text = re.sub(r"<text:s\s*/>", " ", text)
    text = re.sub(r"<text:tab\s*/>", "\t", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


class ProverkyCommissionSaveTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

    def _create_workers_and_union(self):
        leader_id = settings_service.save_worker(first_name="Jan", last_name="Novák").id
        workplace_id = settings_service.save_worker(first_name="Eva", last_name="Králová").id
        member_id = settings_service.save_worker(first_name="Petr", last_name="Svoboda").id
        union_id = person_service.create_person(first_name="Lucie", last_name="Horáková").id
        invited_id = person_service.create_person(first_name="Tomáš", last_name="Malý").id
        return leader_id, workplace_id, member_id, union_id, invited_id

    def _open_dialog(self, inspection):
        from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog

        return BozpInspectionDialog(inspection=inspection)

    def test_leader_only_cannot_validate(self) -> None:
        leader_id, _, _, _, _ = self._create_workers_and_union()
        inspection = bozp_inspection_service.create_inspection()
        dialog = self._open_dialog(inspection)
        dialog.commission_widget.leader_selector.set_person_id(leader_id)

        valid, message = dialog.commission_widget.validate()

        self.assertFalse(valid)
        self.assertEqual(message, COMMISSION_MISSING_WORKPLACE_MESSAGE)

    @patch("moduly.proverky.ui.bozp_inspection_dialog.QMessageBox.warning")
    def test_leader_only_blocks_dialog_accept(self, mock_warning) -> None:
        leader_id, _, _, _, _ = self._create_workers_and_union()
        inspection = bozp_inspection_service.create_inspection()
        dialog = self._open_dialog(inspection)
        dialog.commission_widget.leader_selector.set_person_id(leader_id)

        dialog.accept()

        mock_warning.assert_called_once()
        self.assertEqual(dialog.tabs.currentWidget(), dialog.commission_widget)

    def test_leader_and_workplace_still_missing_union(self) -> None:
        leader_id, workplace_id, _, _, _ = self._create_workers_and_union()
        inspection = bozp_inspection_service.create_inspection()
        dialog = self._open_dialog(inspection)
        dialog.commission_widget.leader_selector.set_person_id(leader_id)
        dialog.commission_widget.workplace_selector.set_person_id(workplace_id)

        valid, message = dialog.commission_widget.validate()

        self.assertFalse(valid)
        self.assertEqual(message, COMMISSION_MISSING_UNION_MESSAGE)

    def test_full_mandatory_commission_validates(self) -> None:
        leader_id, workplace_id, _, union_id, _ = self._create_workers_and_union()
        inspection = bozp_inspection_service.create_inspection()
        dialog = self._open_dialog(inspection)
        dialog.commission_widget.leader_selector.set_person_id(leader_id)
        dialog.commission_widget.workplace_selector.set_person_id(workplace_id)
        dialog.commission_widget.union_selector.set_person_id(union_id)

        valid, message = dialog.commission_widget.validate()

        self.assertTrue(valid)
        self.assertEqual(message, "")

    @patch("moduly.proverky.ui.bozp_inspection_dialog.QMessageBox.warning")
    def test_full_commission_allows_dialog_accept(self, mock_warning) -> None:
        leader_id, workplace_id, _, union_id, _ = self._create_workers_and_union()
        inspection = bozp_inspection_service.create_inspection()
        dialog = self._open_dialog(inspection)
        dialog.commission_widget.leader_selector.set_person_id(leader_id)
        dialog.commission_widget.workplace_selector.set_person_id(workplace_id)
        dialog.commission_widget.union_selector.set_person_id(union_id)

        dialog.accept()

        mock_warning.assert_not_called()

    def test_protocol_shows_signature_roles_only(self) -> None:
        leader_id, workplace_id, member_id, union_id, invited_id = self._create_workers_and_union()
        inspection = bozp_inspection_service.create_inspection()
        bozp_inspection_commission_service.save_members(
            inspection.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": leader_id,
                    "display_name": "Jan Novák",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": workplace_id,
                    "display_name": "Eva Králová",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "person_id": union_id,
                    "display_name": "Lucie Horáková",
                    "display_order": 20,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_MEMBER,
                    "thp_worker_id": member_id,
                    "display_name": "Petr Svoboda",
                    "role_text": "Technik BOZP",
                    "display_order": 30,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_INVITED,
                    "person_id": invited_id,
                    "display_name": "Tomáš Malý",
                    "role_text": "Revizní technik",
                    "display_order": 40,
                    "active": True,
                },
            ],
        )
        loaded = bozp_inspection_service.get_by_id(inspection.id)
        assert loaded is not None

        path = protokol_proverky_service.generate_for_inspection(loaded)
        content = _odt_content(path)
        plain = _odt_plain_text(content)

        leader_pos = plain.index("Jan Novák")
        workplace_pos = plain.index("Eva Králová")

        self.assertIn("Vedoucí prověrky", plain)
        self.assertIn("Zástupce provozu", plain)
        self.assertLess(leader_pos, workplace_pos)

        # V základních informacích jsou i ostatní role.
        self.assertIn("Lucie Horáková", plain)
        self.assertIn("Petr Svoboda", plain)
        self.assertIn("Tomáš Malý", plain)

        # Podpisy: vedoucí, zástupce provozu a (pokud existuje) zástupce odborů.
        signatures = _odt_plain_text(content.split("Podpisy", 1)[1])
        self.assertIn("Vedoucí prověrky", signatures)
        self.assertIn("Zástupce provozu", signatures)
        self.assertIn("Zástupce odborové organizace", signatures)
        self.assertIn("Jan Novák", signatures)
        self.assertIn("Eva Králová", signatures)
        self.assertIn("Lucie Horáková", signatures)
        self.assertNotIn("Petr Svoboda", signatures)
        self.assertNotIn("Tomáš Malý", signatures)
        self.assertNotIn("Členové komise", signatures)
        self.assertNotIn("Přizvané osoby", signatures)


if __name__ == "__main__":
    unittest.main()
