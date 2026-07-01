import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.proverky.constants import COMMISSION_DUPLICATE_PERSON_MESSAGE
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


class ProverkyCommissionUiDuplicateTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

        self.leader_id = settings_service.save_worker(first_name="Jan", last_name="Novák").id
        self.workplace_id = settings_service.save_worker(first_name="Eva", last_name="Králová").id
        self.member_id = settings_service.save_worker(first_name="Petr", last_name="Svoboda").id
        self.union_id = person_service.create_person(first_name="Lucie", last_name="Horáková").id
        self.invited_id = person_service.create_person(first_name="Tomáš", last_name="Malý").id

    def _widget(self):
        from moduly.proverky.ui.bozp_inspection_commission_widget import (
            BozpInspectionCommissionWidget,
        )

        widget = BozpInspectionCommissionWidget()
        widget.set_inspection_context(None)
        return widget

    @patch("moduly.proverky.ui.bozp_inspection_commission_widget.QMessageBox.information")
    def test_leader_blocks_duplicate_workplace_selection(self, mock_message) -> None:
        widget = self._widget()
        widget.leader_selector.set_person_id(self.leader_id)
        widget.workplace_selector.set_person_id(self.leader_id)

        mock_message.assert_called_once()
        self.assertEqual(mock_message.call_args.args[2], COMMISSION_DUPLICATE_PERSON_MESSAGE)
        self.assertIsNone(widget.workplace_selector.current_person_id())
        self.assertEqual(widget._committed_leader_id, self.leader_id)
        self.assertIsNone(widget._committed_workplace_id)

    @patch("moduly.proverky.ui.bozp_inspection_commission_widget.QMessageBox.information")
    def test_leader_blocks_adding_same_member(self, mock_message) -> None:
        widget = self._widget()
        widget.leader_selector.set_person_id(self.leader_id)

        with patch(
            "moduly.proverky.ui.bozp_inspection_commission_widget.BozpInspectionCommissionEntryDialog"
        ) as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = True
            mock_dialog.get_data.return_value = {
                "thp_worker_id": self.leader_id,
                "display_name": "Jan Novák",
                "role_text": None,
                "note_text": None,
            }
            mock_dialog_cls.return_value = mock_dialog

            widget.add_member()

        mock_message.assert_called_once()
        self.assertEqual(len(widget._members), 0)

    @patch("moduly.proverky.ui.bozp_inspection_commission_widget.QMessageBox.information")
    def test_workplace_blocks_adding_same_member(self, mock_message) -> None:
        widget = self._widget()
        widget.workplace_selector.set_person_id(self.workplace_id)

        with patch(
            "moduly.proverky.ui.bozp_inspection_commission_widget.BozpInspectionCommissionEntryDialog"
        ) as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = True
            mock_dialog.get_data.return_value = {
                "thp_worker_id": self.workplace_id,
                "display_name": "Eva Králová",
                "role_text": None,
                "note_text": None,
            }
            mock_dialog_cls.return_value = mock_dialog

            widget.add_member()

        mock_message.assert_called_once()
        self.assertEqual(len(widget._members), 0)

    @patch("moduly.proverky.ui.bozp_inspection_commission_widget.QMessageBox.information")
    def test_union_blocks_duplicate_invited(self, mock_message) -> None:
        widget = self._widget()
        widget.union_selector.set_person_id(self.union_id)

        with patch(
            "moduly.proverky.ui.bozp_inspection_commission_widget.BozpInspectionCommissionEntryDialog"
        ) as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = True
            mock_dialog.get_data.return_value = {
                "person_id": self.union_id,
                "display_name": "Lucie Horáková",
                "role_text": None,
                "note_text": None,
            }
            mock_dialog_cls.return_value = mock_dialog

            widget.add_invited()

        mock_message.assert_called_once()
        self.assertEqual(len(widget._invited), 0)

    @patch("moduly.proverky.ui.bozp_inspection_commission_widget.QMessageBox.information")
    def test_duplicate_invited_not_added_twice(self, mock_message) -> None:
        widget = self._widget()
        widget.union_selector.set_person_id(self.union_id)
        widget._invited.append(
            {
                "person_id": self.invited_id,
                "display_name": "Tomáš Malý",
                "role_text": None,
                "note_text": None,
            }
        )

        with patch(
            "moduly.proverky.ui.bozp_inspection_commission_widget.BozpInspectionCommissionEntryDialog"
        ) as mock_dialog_cls:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = True
            mock_dialog.get_data.return_value = {
                "person_id": self.invited_id,
                "display_name": "Tomáš Malý",
                "role_text": None,
                "note_text": None,
            }
            mock_dialog_cls.return_value = mock_dialog

            widget.add_invited()

        mock_message.assert_called_once()
        self.assertEqual(len(widget._invited), 1)

    def test_full_commission_still_validates_and_saves(self) -> None:
        widget = self._widget()
        widget.leader_selector.set_person_id(self.leader_id)
        widget.workplace_selector.set_person_id(self.workplace_id)
        widget.union_selector.set_person_id(self.union_id)
        widget._members.append(
            {
                "thp_worker_id": self.member_id,
                "display_name": "Petr Svoboda",
                "role_text": "Technik",
                "note_text": None,
            }
        )
        widget._invited.append(
            {
                "person_id": self.invited_id,
                "display_name": "Tomáš Malý",
                "role_text": "Revizní technik",
                "note_text": None,
            }
        )

        valid, message = widget.validate()
        self.assertTrue(valid, message)

        inspection = bozp_inspection_service.create_inspection()
        bozp_inspection_commission_service.save_members(
            inspection.id,
            widget.get_members_for_save(),
        )

        loaded = bozp_inspection_commission_service.get_for_inspection(inspection.id)
        self.assertEqual(len(loaded), 5)


if __name__ == "__main__":
    unittest.main()
