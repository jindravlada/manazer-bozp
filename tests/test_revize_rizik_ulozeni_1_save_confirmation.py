"""REVIZE-RIZIK-ULOZENI-1 – potvrzení uložení revize posouzení rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

_TMP = Path(tempfile.mkdtemp(prefix="revize-rizik-ulozeni-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
        hazard_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
        RiskMeasureReviewError,
        risk_measure_review_service,
    )
    from moduly.rizeni_rizik.ui.risk_measure_review_dialog import RiskMeasureReviewDialog
    from moduly.rizeni_rizik.ui.risk_measure_review_execution_dialog import (
        RiskMeasureReviewExecutionDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group

CONFIRMATION_TITLE = "Řízení rizik"
CONFIRMATION_TEXT = "Změny byly úspěšně uloženy."
REVIEWER_REQUIRED_MESSAGE = "Vyberte kontrolující osobu."


class RevizeRizikUlozeni1SaveConfirmationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.operation = settings_service.save_workplace(
            name="Provoz revize uložení",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna revize uložení",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.reviewer = settings_service.save_worker(
            first_name="Eva",
            last_name="Revizní",
        )
        self.group = ensure_exposed_group("Skupina revize uložení")

    def _run(self, action):
        shown: list[QMessageBox] = []

        def _exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(QMessageBox.StandardButton.Ok)

        with patch(
            "moduly.rizeni_rizik.ui.risk_measure_review_save_confirmation._exec_message_box",
            side_effect=_exec,
        ):
            action()
        return shown

    def _assert_confirmation(self, shown: list[QMessageBox]) -> None:
        self.assertEqual(len(shown), 1)
        box = shown[0]
        self.assertEqual(box.windowTitle(), CONFIRMATION_TITLE)
        self.assertEqual(box.text(), CONFIRMATION_TEXT)
        self.assertEqual(box.icon(), QMessageBox.Icon.Information)
        self.assertEqual(box.standardButtons(), QMessageBox.StandardButton.Ok)
        ok_button = box.button(QMessageBox.StandardButton.Ok)
        assert ok_button is not None
        self.assertEqual(ok_button.text(), "OK")

    def _close(self, dialog) -> None:
        dialog._editor._closing = True
        dialog.close()

    def _fill_header(self, dialog: RiskMeasureReviewDialog, note: str) -> None:
        dialog.reviewer.set_person_id(self.reviewer.id)
        index = dialog.operation.findData(self.operation.id)
        self.assertGreaterEqual(index, 0)
        dialog.operation.setCurrentIndex(index)
        dialog.note.setPlainText(note)

    def _create_measure(self, title: str):
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            name=f"Zdroj {title}",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name=f"Událost {title}",
        )
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            exposed_group_ids=[self.group.id],
            severity=RISK_SEVERITY_MODERATE,
        )
        return hazard_required_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            title=title,
        )

    def test_successful_save_shows_confirmation_and_keeps_data(self) -> None:
        dialog = RiskMeasureReviewDialog()
        dialog.show()
        self._fill_header(dialog, "uložená poznámka")
        order: list[str] = []
        original = risk_measure_review_service.create_review

        def _create(**kwargs):
            order.append("write")
            return original(**kwargs)

        def _action() -> None:
            with patch.object(
                risk_measure_review_service,
                "create_review",
                side_effect=_create,
            ):
                dialog._editor.save_button.click()

        shown = self._run(_action)
        self.assertEqual(order, ["write"])
        self._assert_confirmation(shown)
        self.assertFalse(dialog._editor.is_dirty())
        self.assertFalse(dialog.isHidden())
        review_id = dialog.review.id
        self._close(dialog)

        reopened = RiskMeasureReviewDialog(
            review=risk_measure_review_service.get_by_id(review_id)
        )
        reopened.show()
        self.assertEqual(reopened.note.toPlainText(), "uložená poznámka")
        self.assertEqual(reopened.reviewer.current_person_id(), self.reviewer.id)
        self.assertEqual(reopened.operation.currentData(), self.operation.id)
        self._close(reopened)

    def test_save_without_changes_does_not_confirm(self) -> None:
        dialog = RiskMeasureReviewDialog()
        dialog.show()
        self._fill_header(dialog, "Jedna změna")
        first = self._run(dialog._editor.save_button.click)
        self._assert_confirmation(first)
        self.assertFalse(dialog._editor.save_button.isEnabled())
        second = self._run(dialog._editor.save_button.click)
        self.assertEqual(second, [])
        direct = self._run(dialog._editor._handle_save_clicked)
        self.assertEqual(direct, [])
        self.assertEqual(dialog.note.toPlainText(), "Jedna změna")
        self._close(dialog)

    def test_failed_save_keeps_draft_and_skips_confirmation(self) -> None:
        dialog = RiskMeasureReviewDialog()
        dialog.show()
        dialog.note.setPlainText("rozepsaná poznámka")
        with patch(
            "moduly.rizeni_rizik.ui.risk_measure_review_dialog.QMessageBox.warning",
        ) as warn:
            shown = self._run(dialog._editor.save_button.click)
        self.assertEqual(shown, [])
        warn.assert_called_once()
        self.assertIn(REVIEWER_REQUIRED_MESSAGE, warn.call_args.args[2])
        self.assertEqual(dialog.note.toPlainText(), "rozepsaná poznámka")
        self.assertTrue(dialog._editor.is_dirty())
        self.assertIsNone(dialog.review)
        self._close(dialog)

    def test_other_actions_do_not_confirm(self) -> None:
        dialog = RiskMeasureReviewDialog()
        dialog.show()
        self._fill_header(dialog, "bez tlačítka")
        shown = self._run(lambda: self.assertTrue(dialog._save()))
        self.assertEqual(shown, [])
        stored = risk_measure_review_service.get_by_id(dialog.review.id)
        assert stored is not None
        self.assertEqual(stored.note, "bez tlačítka")
        self._close(dialog)

        dialog = RiskMeasureReviewDialog()
        dialog.show()
        self._fill_header(dialog, "při zavření")
        with patch(
            "core.widgets.editor_dialog_controller.confirm_unsaved_editor_close",
            return_value="save",
        ):
            shown = self._run(lambda: self.assertTrue(dialog._editor.request_close()))
        self.assertEqual(shown, [])
        stored = risk_measure_review_service.get_by_id(dialog.review.id)
        assert stored is not None
        self.assertEqual(stored.note, "při zavření")
        self._close(dialog)

        dialog = RiskMeasureReviewDialog()
        dialog.show()
        index = dialog.operation.findData(self.operation.id)
        shown = self._run(lambda: dialog.operation.setCurrentIndex(index))
        self.assertEqual(shown, [])
        self.assertIsNone(dialog.review)
        self._close(dialog)

    def test_execution_confirms_only_changed_save_button(self) -> None:
        measure = self._create_measure("Kryt stroje")
        review = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        dialog = RiskMeasureReviewExecutionDialog(review=review)
        dialog.show()
        self.assertEqual(dialog.checklist.point_count(), 1)
        point = dialog.checklist.points[0]
        self.assertEqual(point.item_id, risk_measure_review_service.list_checklist_rows(review.id)[0].item_id)

        shown = self._run(dialog._editor.save_button.click)
        self.assertEqual(shown, [])

        point.compliant_radio.setChecked(True)
        point.note_edit.setText("bez závad")
        shown = self._run(dialog._editor.save_button.click)
        self._assert_confirmation(shown)
        self.assertFalse(dialog.isHidden())
        rows = risk_measure_review_service.list_checklist_rows(review.id)
        self.assertTrue(rows[0].compliant)
        self.assertEqual(rows[0].note, "bez závad")
        self.assertEqual(rows[0].follow_up_measure_id, measure.id)
        second = self._run(dialog._editor._handle_save_clicked)
        self.assertEqual(second, [])
        self._close(dialog)

        reopened = RiskMeasureReviewExecutionDialog(
            review=risk_measure_review_service.get_by_id(review.id)
        )
        reopened.show()
        reopened_point = reopened.checklist.points[0]
        self.assertTrue(reopened_point.compliant_radio.isChecked())
        self.assertEqual(reopened_point.note_edit.text(), "bez závad")
        self._close(reopened)

        failed = RiskMeasureReviewExecutionDialog(
            review=risk_measure_review_service.get_by_id(review.id)
        )
        failed.show()
        failed.checklist.points[0].note_edit.setText("rozepsaný výsledek")
        with (
            patch.object(
                risk_measure_review_service,
                "update_review",
                side_effect=RiskMeasureReviewError("Nelze uložit revizi."),
            ),
            patch(
                "moduly.rizeni_rizik.ui.risk_measure_review_execution_dialog.QMessageBox.warning",
            ) as warn,
        ):
            shown = self._run(failed._editor.save_button.click)
        self.assertEqual(shown, [])
        warn.assert_called_once()
        self.assertEqual(failed.checklist.points[0].note_edit.text(), "rozepsaný výsledek")
        stored_rows = risk_measure_review_service.list_checklist_rows(review.id)
        self.assertEqual(stored_rows[0].note, "bez závad")
        self._close(failed)

        other = RiskMeasureReviewExecutionDialog(
            review=risk_measure_review_service.get_by_id(review.id)
        )
        other.show()
        other.checklist.points[0].note_edit.setText("úkol bez potvrzení")
        shown = self._run(lambda: self.assertTrue(other._persist_checklist_for_resolution()))
        self.assertEqual(shown, [])
        self.assertEqual(
            risk_measure_review_service.list_checklist_rows(review.id)[0].note,
            "úkol bez potvrzení",
        )
        shown = self._run(lambda: other.tabs.setCurrentIndex(1))
        self.assertEqual(shown, [])
        shown = self._run(lambda: self.assertTrue(other._save()))
        self.assertEqual(shown, [])
        self._close(other)
