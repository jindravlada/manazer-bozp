import importlib
import tempfile
import unittest
import uuid
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

    from moduly.audity.constants import COMMISSION_DUPLICATE_PERSON_MESSAGE
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


class AudityCommissionUiDuplicateTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

        suffix = uuid.uuid4().hex[:6]
        self.leader_id = settings_service.save_worker(
            first_name="Jan", last_name=f"Novák-{suffix}"
        ).id
        self.workplace_id = settings_service.save_worker(
            first_name="Eva", last_name=f"Králová-{suffix}"
        ).id
        self.member_id = settings_service.save_worker(
            first_name="Petr", last_name=f"Svoboda-{suffix}"
        ).id
        self.union_id = person_service.create_person(
            first_name="Lucie", last_name=f"Horáková-{suffix}"
        ).id
        self.invited_id = person_service.create_person(
            first_name="Tomáš", last_name=f"Malý-{suffix}"
        ).id

    def _widget(self):
        from moduly.audity.ui.audit_commission_widget import AuditCommissionWidget

        widget = AuditCommissionWidget()
        widget.set_audit_context(None)
        return widget

    @patch("moduly.audity.ui.audit_commission_widget.QMessageBox.information")
    def test_leader_blocks_duplicate_workplace_selection(self, mock_message) -> None:
        widget = self._widget()
        widget.leader_selector.set_person_id(self.leader_id)
        widget.workplace_selector.set_person_id(self.leader_id)

        mock_message.assert_called_once()
        self.assertEqual(mock_message.call_args.args[2], COMMISSION_DUPLICATE_PERSON_MESSAGE)
        self.assertIsNone(widget.workplace_selector.current_person_id())
        self.assertEqual(widget._committed_leader_id, self.leader_id)
        self.assertIsNone(widget._committed_workplace_id)

    @patch("moduly.audity.ui.audit_commission_widget.QMessageBox.information")
    def test_leader_blocks_adding_same_auditor(self, mock_message) -> None:
        widget = self._widget()
        widget.leader_selector.set_person_id(self.leader_id)

        with patch(
            "moduly.audity.ui.audit_commission_widget.AuditCommissionEntryDialog"
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

    @patch("moduly.audity.ui.audit_commission_widget.QMessageBox.information")
    def test_union_blocks_duplicate_invited(self, mock_message) -> None:
        widget = self._widget()
        widget.union_selector.set_person_id(self.union_id)

        with patch(
            "moduly.audity.ui.audit_commission_widget.AuditCommissionEntryDialog"
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

    def test_union_selector_excludes_thp_linked_persons(self) -> None:
        from moduly.nastaveni.sluzby.person_thp_link import ensure_person_for_thp_worker

        thp_person = ensure_person_for_thp_worker(
            settings_service.get_worker_by_id(self.leader_id)
        )
        widget = self._widget()
        union_ids = {
            widget.union_selector.itemData(index)
            for index in range(widget.union_selector.count())
            if isinstance(widget.union_selector.itemData(index), int)
        }
        self.assertIn(self.union_id, union_ids)
        self.assertIn(self.invited_id, union_ids)
        self.assertNotIn(thp_person.id, union_ids)


if __name__ == "__main__":
    unittest.main()
