import importlib
import tempfile
import unittest
import uuid
from datetime import date
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

    from moduly.audity.constants import (
        AUDIT_STATUS_PLANOVANO,
        AUDIT_STATUS_PROBIHA,
        AUDIT_TYPE_RADNY,
        COMMISSION_MISSING_LEADER_MESSAGE,
        COMMISSION_MISSING_UNION_MESSAGE,
        COMMISSION_MISSING_WORKPLACE_MESSAGE,
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
        TAB_LABELS,
    )
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


class AudityDialogTestCase(unittest.TestCase):
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
        self.workplace_rep_id = settings_service.save_worker(
            first_name="Eva", last_name=f"Králová-{suffix}"
        ).id
        self.auditor_id = settings_service.save_worker(
            first_name="Petr", last_name=f"Svoboda-{suffix}"
        ).id
        self.union_id = person_service.create_person(
            first_name="Lucie", last_name=f"Horáková-{suffix}"
        ).id
        self.invited_id = person_service.create_person(
            first_name="Tomáš", last_name=f"Malý-{suffix}"
        ).id

    def _open_dialog(self, audit=None):
        from moduly.audity.ui.audit_dialog import AuditDialog

        return AuditDialog(audit=audit)

    def _fill_spis(self, dialog) -> None:
        dialog.spis_widget._set_year(2026)
        dialog.spis_widget.planned_month_combo.setCurrentIndex(3)
        dialog.spis_widget.audit_date_edit.set_date_value(date(2026, 4, 15))
        dialog.spis_widget.type_combo.setCurrentText(AUDIT_TYPE_RADNY)

    def _fill_mandatory_commission(self, dialog) -> None:
        dialog.commission_widget.leader_selector.set_person_id(self.leader_id)
        dialog.commission_widget.workplace_selector.set_person_id(self.workplace_rep_id)
        dialog.commission_widget.union_selector.set_person_id(self.union_id)

    def test_new_audit_dialog_opens(self) -> None:
        dialog = self._open_dialog()

        self.assertIsNone(dialog.audit)
        self.assertEqual(dialog.tabs.count(), 8)
        for index, label in enumerate(TAB_LABELS):
            self.assertEqual(dialog.tabs.tabText(index), label)

    def test_dialog_opens_maximized(self) -> None:
        from PySide6.QtWidgets import QDialog

        from core.widgets.dialog_utils import exec_maximized

        dialog = self._open_dialog()

        with patch.object(QDialog, "exec", return_value=0):
            with patch.object(dialog, "showMaximized") as mock_maximized:
                exec_maximized(dialog)

        mock_maximized.assert_called_once()

    def test_spis_fields_and_derived_status(self) -> None:
        dialog = self._open_dialog()
        self._fill_spis(dialog)

        self.assertEqual(dialog.spis_widget.status_label.text(), AUDIT_STATUS_PLANOVANO)

        dialog.spis_widget.started_at_edit.set_date_value(date(2026, 4, 10))
        self.assertEqual(dialog.spis_widget.status_label.text(), AUDIT_STATUS_PROBIHA)

        data = dialog.spis_widget.get_data()
        self.assertEqual(data["year"], 2026)
        self.assertEqual(data["planned_month"], 3)
        self.assertEqual(data["audit_date"], date(2026, 4, 15))
        self.assertEqual(data["audit_type"], AUDIT_TYPE_RADNY)

    @patch("moduly.audity.ui.audit_dialog.QMessageBox.warning")
    def test_save_without_commission_switches_to_komise(self, mock_warning) -> None:
        audit = audit_service.create_audit(title="Test")
        dialog = self._open_dialog(audit)
        self._fill_spis(dialog)

        dialog.accept()

        mock_warning.assert_called_once()
        self.assertEqual(mock_warning.call_args.args[2], COMMISSION_MISSING_LEADER_MESSAGE)
        self.assertEqual(dialog.tabs.currentWidget(), dialog.commission_widget)

    def test_commission_validation_steps(self) -> None:
        audit = audit_service.create_audit()
        dialog = self._open_dialog(audit)

        valid, message = dialog.commission_widget.validate()
        self.assertFalse(valid)
        self.assertEqual(message, COMMISSION_MISSING_LEADER_MESSAGE)

        dialog.commission_widget.leader_selector.set_person_id(self.leader_id)
        valid, message = dialog.commission_widget.validate()
        self.assertFalse(valid)
        self.assertEqual(message, COMMISSION_MISSING_WORKPLACE_MESSAGE)

        dialog.commission_widget.workplace_selector.set_person_id(self.workplace_rep_id)
        valid, message = dialog.commission_widget.validate()
        self.assertFalse(valid)
        self.assertEqual(message, COMMISSION_MISSING_UNION_MESSAGE)

        dialog.commission_widget.union_selector.set_person_id(self.union_id)
        valid, message = dialog.commission_widget.validate()
        self.assertTrue(valid)

    @patch("moduly.audity.ui.audit_dialog.QMessageBox.warning")
    def test_full_save_and_reload(self, mock_warning) -> None:
        audit = audit_service.create_audit(title="Původní")
        dialog = self._open_dialog(audit)
        self._fill_spis(dialog)
        dialog.spis_widget.started_at_edit.set_date_value(date(2026, 4, 10))
        self._fill_mandatory_commission(dialog)

        dialog.accept()
        mock_warning.assert_not_called()

        data = dialog.get_data()
        payload = dialog.prepare_save_payload(data)
        updated = audit_service.update_audit(audit.id, **payload)
        assert updated is not None
        dialog.save_commission_members(audit.id, data)

        self.assertEqual(updated.status, AUDIT_STATUS_PROBIHA)

        reloaded = audit_service.get_by_id(audit.id)
        assert reloaded is not None
        reopen = self._open_dialog(reloaded)

        self.assertEqual(reopen.spis_widget.number_label.text(), reloaded.number)
        self.assertEqual(reopen.spis_widget.year_combo.currentData(), 2026)
        self.assertEqual(reopen.spis_widget.started_at_edit.get_date(), date(2026, 4, 10))
        self.assertEqual(reopen.spis_widget.status_label.text(), AUDIT_STATUS_PROBIHA)

        members = audit_commission_service.get_for_audit(audit.id)
        record_types = {member.record_type for member in members}
        self.assertEqual(
            record_types,
            {COMMISSION_RECORD_LEADER, COMMISSION_RECORD_WORKPLACE, COMMISSION_RECORD_UNION},
        )
        self.assertEqual(reopen.commission_widget.leader_selector.current_person_id(), self.leader_id)
        self.assertEqual(
            reopen.commission_widget.workplace_selector.current_person_id(),
            self.workplace_rep_id,
        )
        self.assertEqual(reopen.commission_widget.union_selector.current_person_id(), self.union_id)


if __name__ == "__main__":
    unittest.main()
