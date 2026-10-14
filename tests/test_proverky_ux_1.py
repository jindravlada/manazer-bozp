"""PROVERKY-UX-1: potvrzení úspěšného uložení prověrky až po dokončení zápisu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="proverky-ux-1-"))

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
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.modely.finding import Finding
    from core.shared.sluzby.finding_service import finding_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.constants import (
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
    )
    from moduly.proverky.modely.bozp_inspection import BozpInspection
    from moduly.proverky.sluzby.bozp_inspection_commission_service import (
        bozp_inspection_commission_service,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog


def _read_silne(inspection_id: int) -> str:
    with get_session() as session:
        row = session.get(BozpInspection, inspection_id)
        assert row is not None
        value = row.silne_stranky or ""
        session.expunge(row)
        return value


def _read_finding_description(finding_id: int) -> str:
    with get_session() as session:
        row = session.get(Finding, finding_id)
        assert row is not None
        value = row.description or ""
        session.expunge(row)
        return value


class ProverkyUx1SaveConfirmationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in list(bozp_inspection_service.get_all()):
            bozp_inspection_service.delete_inspection(inspection.id)
        suffix = uuid.uuid4().hex[:6]
        self.leader_id = settings_service.save_worker(
            first_name="Jan", last_name=f"L-{suffix}"
        ).id
        self.workplace_rep_id = settings_service.save_worker(
            first_name="Eva", last_name=f"W-{suffix}"
        ).id
        self.union_id = person_service.create_person(
            first_name="Lucie", last_name=f"U-{suffix}"
        ).id

    def _create_inspection(self, *, silne: str = "") -> BozpInspection:
        inspection = bozp_inspection_service.create_inspection(
            inspection_date=date(2026, 4, 15),
            title="UX-1",
            silne_stranky=silne,
        )
        bozp_inspection_commission_service.save_members(
            inspection.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": self.leader_id,
                    "display_name": "L",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": self.workplace_rep_id,
                    "display_name": "W",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "person_id": self.union_id,
                    "display_name": "U",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
        reloaded = bozp_inspection_service.get_by_id(inspection.id)
        assert reloaded is not None
        return reloaded

    def _open_dialog(self, inspection: BozpInspection) -> BozpInspectionDialog:
        dialog = BozpInspectionDialog(inspection=inspection)
        dialog.commission_widget.leader_selector.set_person_id(self.leader_id)
        dialog.commission_widget.workplace_selector.set_person_id(self.workplace_rep_id)
        dialog.commission_widget.union_selector.set_person_id(self.union_id)
        dialog._capture_baseline()
        return dialog

    def _finding_payload(self, description: str) -> dict:
        return {
            "finding_type": FINDING_TYPE_ZJISTENI,
            "reference_label": "",
            "description": description,
            "recommended_action": "",
            "responsible_person_id": None,
            "responsible_person_name": "",
            "due_date": None,
            "status": FINDING_STATUS_OTEVRENE,
            "resolution_note": "",
        }

    def test_successful_save_confirms_only_after_full_persist(self) -> None:
        inspection = self._create_inspection(silne="Před")
        finding = finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Před",
            status=FINDING_STATUS_OTEVRENE,
        )
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.silne_stranky_edit.setPlainText("Uloženo")
        dialog._deferred.stage_finding_update(
            finding.id,
            self._finding_payload("Uložené zjištění"),
        )
        order: list[str] = []

        real_update = bozp_inspection_service.update_inspection
        real_flush = dialog._deferred.flush

        def _update(*args, **kwargs):
            order.append("update")
            return real_update(*args, **kwargs)

        def _flush(*args, **kwargs):
            order.append("flush")
            return real_flush(*args, **kwargs)

        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            order.append("info")
            shown.append(box)
            self.assertEqual(_read_silne(inspection.id), "Uloženo")
            self.assertEqual(_read_finding_description(finding.id), "Uložené zjištění")
            self.assertFalse(dialog._is_dirty())
            return int(QMessageBox.StandardButton.Ok)

        with (
            patch.object(bozp_inspection_service, "update_inspection", _update),
            patch.object(dialog._deferred, "flush", _flush),
            patch(
                "moduly.proverky.ui.bozp_inspection_dialog._exec_message_box",
                side_effect=_exec,
            ),
        ):
            dialog._save_btn.click()

        self.assertEqual(len(shown), 1)
        self.assertEqual(shown[0].windowTitle(), "Prověrky BOZP")
        self.assertEqual(shown[0].text(), "Změny byly úspěšně uloženy.")
        ok_button = shown[0].button(QMessageBox.StandardButton.Ok)
        assert ok_button is not None
        self.assertEqual(ok_button.text(), "OK")
        self.assertEqual(order, ["update", "flush", "info"])
        self.assertFalse(dialog._closing)
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertFalse(dialog._is_dirty())

    def test_validation_failure_does_not_confirm(self) -> None:
        inspection = self._create_inspection(silne="Původní")
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.silne_stranky_edit.setPlainText("Bez komise")

        with (
            patch.object(
                dialog.commission_widget,
                "validate",
                return_value=(False, "Chybí vedoucí prověrky."),
            ),
            patch.object(bozp_inspection_service, "update_inspection") as update,
            patch(
                "moduly.proverky.ui.bozp_inspection_dialog._exec_message_box"
            ) as info,
            patch(
                "moduly.proverky.ui.bozp_inspection_dialog.QMessageBox.warning"
            ) as warning,
        ):
            dialog._save_btn.click()

        info.assert_not_called()
        update.assert_not_called()
        warning.assert_called_once()
        self.assertEqual(warning.call_args.args[2], "Chybí vedoucí prověrky.")
        self.assertFalse(dialog._closing)
        self.assertTrue(dialog._is_dirty())
        self.assertEqual(_read_silne(inspection.id), "Původní")

    def test_deferred_flush_failure_does_not_confirm(self) -> None:
        inspection = self._create_inspection(silne="Původní")
        finding = finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Původní zjištění",
            status=FINDING_STATUS_OTEVRENE,
        )
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.silne_stranky_edit.setPlainText("Po flushi")
        dialog._deferred.stage_finding_update(
            finding.id,
            self._finding_payload("Nemá se zapsat"),
        )

        with (
            patch.object(
                dialog._deferred,
                "flush",
                side_effect=RuntimeError("flush selhal"),
            ),
            patch(
                "moduly.proverky.ui.bozp_inspection_dialog._exec_message_box"
            ) as info,
            patch(
                "moduly.proverky.ui.bozp_inspection_dialog.QMessageBox.warning"
            ) as warning,
        ):
            dialog._save_btn.click()

        info.assert_not_called()
        warning.assert_called_once()
        self.assertIn("Odložené změny se nepodařilo uložit", warning.call_args.args[2])
        self.assertIn("flush selhal", warning.call_args.args[2])
        self.assertFalse(dialog._closing)
        self.assertTrue(dialog._is_dirty())
        self.assertEqual(_read_finding_description(finding.id), "Původní zjištění")

    def test_missing_inspection_does_not_confirm(self) -> None:
        inspection = self._create_inspection(silne="Původní")
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.silne_stranky_edit.setPlainText("Nenalezeno")

        with (
            patch.object(
                bozp_inspection_service,
                "update_inspection",
                return_value=None,
            ),
            patch(
                "moduly.proverky.ui.bozp_inspection_dialog._exec_message_box"
            ) as info,
        ):
            dialog._save_btn.click()

        info.assert_not_called()
        self.assertFalse(dialog._closing)
        self.assertTrue(dialog._is_dirty())
        self.assertEqual(_read_silne(inspection.id), "Původní")

    def test_ok_does_not_save_again_and_second_click_keeps_one_inspection(self) -> None:
        inspection = self._create_inspection(silne="Před")
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.silne_stranky_edit.setPlainText("Jednou")
        during_dialog: list[int] = []

        real_update = bozp_inspection_service.update_inspection

        def _update(*args, **kwargs):
            return real_update(*args, **kwargs)

        def _info(*args, **kwargs):
            during_dialog.append(update_spy.call_count)
            return QMessageBox.StandardButton.Ok

        with (
            patch.object(
                bozp_inspection_service,
                "update_inspection",
                side_effect=_update,
            ) as update_spy,
            patch(
                "moduly.proverky.ui.bozp_inspection_dialog._exec_message_box",
                side_effect=_info,
            ),
        ):
            dialog._save_btn.click()
            self.assertEqual(during_dialog, [1])
            self.assertEqual(update_spy.call_count, 1)
            self.assertFalse(dialog._is_dirty())
            self.assertFalse(dialog._closing)

            dialog.conclusion_widget.silne_stranky_edit.setPlainText("Podruhé")
            dialog._save_btn.click()

        self.assertEqual(update_spy.call_count, 2)
        self.assertEqual(len(bozp_inspection_service.get_all()), 1)
        self.assertEqual(bozp_inspection_service.get_all()[0].id, inspection.id)
        self.assertEqual(_read_silne(inspection.id), "Podruhé")
        self.assertFalse(dialog._is_dirty())
        self.assertFalse(dialog._closing)

    def test_save_and_close_persists_without_success_dialog(self) -> None:
        inspection = self._create_inspection(silne="Před zavřením")
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.silne_stranky_edit.setPlainText("Zavřeno")

        with (
            patch(
                "moduly.proverky.ui.bozp_inspection_dialog._exec_message_box"
            ) as info,
            patch.object(dialog, "_done_accept") as accept,
        ):
            dialog._save_and_close()

        info.assert_not_called()
        accept.assert_called_once()
        self.assertEqual(_read_silne(inspection.id), "Zavřeno")

    def test_save_without_changes_does_not_confirm(self) -> None:
        inspection = self._create_inspection(silne="Beze změny")
        dialog = self._open_dialog(inspection)
        with patch("moduly.proverky.ui.bozp_inspection_dialog._exec_message_box") as confirm:
            dialog._save_btn.click()
            self.assertFalse(dialog._is_dirty())
            dialog._save_keep_open()
        confirm.assert_not_called()
        self.assertEqual(_read_silne(inspection.id), "Beze změny")
        self.assertTrue(dialog._save_btn.isEnabled())

    def test_reopen_keeps_saved_changes(self) -> None:
        inspection = self._create_inspection(silne="Původní")
        dialog = self._open_dialog(inspection)
        dialog.conclusion_widget.silne_stranky_edit.setPlainText("Po uložení")
        with patch(
            "moduly.proverky.ui.bozp_inspection_dialog._exec_message_box",
            return_value=int(QMessageBox.StandardButton.Ok),
        ):
            dialog._save_btn.click()
        dialog._closing = True
        dialog.close()

        reopened = self._open_dialog(bozp_inspection_service.get_by_id(inspection.id))
        self.assertEqual(
            reopened.conclusion_widget.silne_stranky_edit.toPlainText(),
            "Po uložení",
        )
        reopened._closing = True
        reopened.close()

    def test_deferred_change_confirms_and_other_actions_do_not(self) -> None:
        inspection = self._create_inspection(silne="Beze změny textu")
        finding = finding_service.create(
            ENTITY_PROVERKY,
            inspection.id,
            finding_type=FINDING_TYPE_ZJISTENI,
            description="Původní zjištění",
            status=FINDING_STATUS_OTEVRENE,
        )
        dialog = self._open_dialog(inspection)
        self.assertFalse(dialog._is_dirty())
        dialog._deferred.stage_finding_update(
            finding.id,
            self._finding_payload("Odložená změna"),
        )
        self.assertTrue(dialog._is_dirty())
        with patch(
            "moduly.proverky.ui.bozp_inspection_dialog._exec_message_box",
            return_value=int(QMessageBox.StandardButton.Ok),
        ) as confirm:
            dialog._save_btn.click()
        confirm.assert_called_once()
        self.assertEqual(_read_finding_description(finding.id), "Odložená změna")
        self.assertEqual(_read_silne(inspection.id), "Beze změny textu")
        self.assertFalse(dialog._is_dirty())

        with patch("moduly.proverky.ui.bozp_inspection_dialog._exec_message_box") as confirm:
            dialog.tabs.setCurrentIndex(1)
            dialog._save_btn.click()
        confirm.assert_not_called()

        dialog.conclusion_widget.silne_stranky_edit.setPlainText("Při zavření")
        with (
            patch(
                "moduly.proverky.ui.bozp_inspection_dialog.confirm_unsaved_editor_close",
                return_value="save",
            ),
            patch("moduly.proverky.ui.bozp_inspection_dialog._exec_message_box") as confirm,
        ):
            dialog._request_close()
        confirm.assert_not_called()
        self.assertEqual(_read_silne(inspection.id), "Při zavření")


if __name__ == "__main__":
    unittest.main()
