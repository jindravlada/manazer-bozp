"""ACCIDENT-INJURY-DATES-LAYOUT-1 – DPN u data úrazu a potvrzení změny data."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QMessageBox,
)
from sqlalchemy import delete

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="accident-injury-dates-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        ACCIDENT_DATE_DELAY_WARNING,
        DPN_KIND_MISMATCH_MESSAGE,
        dpn_calendar_days,
        is_accident_date_delayed,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.ui.accident_dialog import (
        ACCIDENT_DATE_CHANGE_CANCEL_LABEL,
        ACCIDENT_DATE_CHANGE_CONFIRM_LABEL,
        ACCIDENT_DATE_CHANGE_MESSAGE,
        ACCIDENT_DATE_CHANGE_TITLE,
        AccidentDialog,
    )
    from moduly.ukoly.modely.task import Task


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
KIND_UP_TO_3 = "pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny"


class AccidentInjuryDatesLayout1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(AccidentInvestigation))
            session.execute(delete(Accident))
            session.commit()

    def _create(self, *, accident_date: date | None = None, **overrides):
        data = {
            "jmeno_prijmeni": "Jan Novák",
            "pohlavi": "Muž",
            "datum_narozeni": date(1990, 1, 1),
            "druh_urazu": KIND_OVER_3,
            "accident_date": accident_date or (date.today() - timedelta(days=20)),
            "accident_time": "10:00",
            "popis_urazoveho_deje": "Pád z žebříku",
            "dpn_od": date.today() - timedelta(days=20),
            "dpn_do": date.today() - timedelta(days=10),
            "opatreni": "Kontrola žebříků",
            "zranena_cast_tela": "Levé zápěstí",
        }
        data.update(overrides)
        return accident_service.create_accident(**data)

    def _open(self, accident=None) -> AccidentDialog:
        return AccidentDialog(accident=accident)

    def _bypass_required_validation(self, dialog: AccidentDialog) -> None:
        for tab in (
            dialog.tab_podatel_widget,
            dialog.tab_zamestnanec_widget,
            dialog.tab_uraz_widget,
            dialog.tab_pracoviste_widget,
            dialog.tab_dalsi_widget,
            dialog.tab_svedci_widget,
        ):
            if hasattr(tab, "validate"):
                tab.validate = MagicMock(return_value=[])

    def _answer_date_change(self, *, confirm: bool):
        boxes: list[QMessageBox] = []

        def fake_exec(box):
            boxes.append(box)
            label = (
                ACCIDENT_DATE_CHANGE_CONFIRM_LABEL
                if confirm
                else ACCIDENT_DATE_CHANGE_CANCEL_LABEL
            )
            for button in box.buttons():
                if button.text() == label:
                    box._test_clicked = button
                    break
            return 0

        def fake_clicked(box):
            return getattr(box, "_test_clicked", None)

        exec_patch = patch.object(QMessageBox, "exec", fake_exec)
        clicked_patch = patch.object(QMessageBox, "clickedButton", fake_clicked)
        exec_patch.start()
        clicked_patch.start()
        self.addCleanup(exec_patch.stop)
        self.addCleanup(clicked_patch.stop)
        return boxes

    def test_dpn_fields_are_not_on_employee_tab(self) -> None:
        dialog = self._open()
        employee = dialog.tab_zamestnanec_widget
        self.assertFalse(hasattr(employee, "dpn_od"))
        self.assertFalse(hasattr(employee, "dpn_do"))
        self.assertFalse(hasattr(employee, "dpn_duration_label"))
        dialog.close()

    def test_dpn_fields_share_one_row_on_injury_tab(self) -> None:
        dialog = self._open()
        tab = dialog.tab_uraz_widget
        self.assertIs(tab.dpn_od.parentWidget().parentWidget(), tab.dpn_range_row)
        self.assertIs(tab.dpn_do.parentWidget().parentWidget(), tab.dpn_range_row)
        self.assertIsInstance(tab.dpn_range_row.layout(), QHBoxLayout)
        self.assertEqual(tab.dpn_range_row.layout().stretch(0), 1)
        self.assertEqual(tab.dpn_range_row.layout().stretch(1), 1)
        dialog.close()

    def test_injury_date_and_time_share_one_row(self) -> None:
        dialog = self._open()
        tab = dialog.tab_uraz_widget
        self.assertIs(
            tab.accident_date.parentWidget().parentWidget(),
            tab.accident_datetime_row,
        )
        self.assertIs(
            tab.accident_time.parentWidget().parentWidget(),
            tab.accident_datetime_row,
        )
        self.assertIsInstance(tab.accident_datetime_row.layout(), QHBoxLayout)
        self.assertEqual(tab.accident_datetime_row.layout().stretch(0), 1)
        self.assertEqual(tab.accident_datetime_row.layout().stretch(1), 1)
        dialog.close()

    def test_dpn_duration_still_calculates(self) -> None:
        dialog = self._open()
        tab = dialog.tab_uraz_widget
        start = date(2026, 3, 1)
        end = date(2026, 3, 3)
        tab.dpn_od.set_date_value(start)
        tab.dpn_do.set_date_value(end)
        self.assertEqual(dpn_calendar_days(start, end), 3)
        self.assertIn("3 dní", tab.dpn_duration_label.text())
        tab.dpn_do.clear_date()
        self.assertIn("—", tab.dpn_duration_label.text())
        dialog.close()

    def test_dpn_kind_warning_still_works(self) -> None:
        dialog = self._open()
        tab = dialog.tab_uraz_widget
        tab.druh_urazu.set_value(KIND_UP_TO_3)
        tab.dpn_od.set_date_value(date(2026, 3, 1))
        tab.dpn_do.set_date_value(date(2026, 3, 25))
        dialog._refresh_dpn_kind_warning()
        self.assertFalse(tab.dpn_kind_warning_label.isHidden())
        self.assertEqual(tab.dpn_kind_warning_label.text(), DPN_KIND_MISMATCH_MESSAGE)
        tab.dpn_do.set_date_value(date(2026, 3, 2))
        dialog._refresh_dpn_kind_warning()
        self.assertTrue(tab.dpn_kind_warning_label.isHidden())
        dialog.close()

    def test_new_accident_older_than_14_days_shows_delay_warning(self) -> None:
        dialog = self._open()
        old = date.today() - timedelta(days=15)
        self.assertTrue(is_accident_date_delayed(old))
        dialog.tab_uraz_widget.accident_date.set_date_iso(old.isoformat())
        self.assertFalse(dialog.tab_uraz_widget.accident_date_delay_warning.isHidden())
        self.assertEqual(
            dialog.tab_uraz_widget.accident_date_delay_warning.text(),
            ACCIDENT_DATE_DELAY_WARNING,
        )
        dialog.close()

    def test_opening_saved_old_accident_hides_delay_warning(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        self.assertEqual(dialog.tab_uraz_widget.get_accident_date(), accident.accident_date)
        self.assertTrue(dialog.tab_uraz_widget.accident_date_delay_warning.isHidden())
        dialog.close()

    def test_changing_saved_injury_date_recalculates_delay_warning(self) -> None:
        accident = self._create(accident_date=date.today() - timedelta(days=3))
        dialog = self._open(accident)
        self.assertTrue(dialog.tab_uraz_widget.accident_date_delay_warning.isHidden())
        delayed = date.today() - timedelta(days=20)
        dialog.tab_uraz_widget.accident_date.set_date_iso(delayed.isoformat())
        self.assertFalse(dialog.tab_uraz_widget.accident_date_delay_warning.isHidden())
        recent = date.today() - timedelta(days=2)
        dialog.tab_uraz_widget.accident_date.set_date_iso(recent.isoformat())
        self.assertTrue(dialog.tab_uraz_widget.accident_date_delay_warning.isHidden())
        dialog.close()

    def test_reverting_saved_injury_date_hides_delay_warning(self) -> None:
        original = date.today() - timedelta(days=20)
        accident = self._create(accident_date=original)
        dialog = self._open(accident)
        dialog.tab_uraz_widget.accident_date.set_date_iso(
            (date.today() - timedelta(days=16)).isoformat()
        )
        self.assertFalse(dialog.tab_uraz_widget.accident_date_delay_warning.isHidden())
        dialog.tab_uraz_widget.accident_date.set_date_iso(original.isoformat())
        self.assertTrue(dialog.tab_uraz_widget.accident_date_delay_warning.isHidden())
        dialog.close()

    def test_changing_other_field_does_not_confirm_injury_date(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        self._bypass_required_validation(dialog)
        dialog.tab_zamestnanec_widget.jmeno_prijmeni.setText("Petr Nový")
        boxes = self._answer_date_change(confirm=True)
        dialog.accept()
        self.assertEqual(boxes, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        dialog.close()

    def test_changing_injury_date_asks_before_write(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        self._bypass_required_validation(dialog)
        new_date = accident.accident_date - timedelta(days=5)
        dialog.tab_uraz_widget.accident_date.set_date_iso(new_date.isoformat())
        boxes = self._answer_date_change(confirm=False)
        dialog.accept()
        self.assertEqual(len(boxes), 1)
        box = boxes[0]
        self.assertEqual(box.windowTitle(), ACCIDENT_DATE_CHANGE_TITLE)
        self.assertEqual(box.text(), ACCIDENT_DATE_CHANGE_MESSAGE)
        labels = {button.text() for button in box.buttons()}
        self.assertEqual(
            labels,
            {ACCIDENT_DATE_CHANGE_CONFIRM_LABEL, ACCIDENT_DATE_CHANGE_CANCEL_LABEL},
        )
        self.assertEqual(box.defaultButton().text(), ACCIDENT_DATE_CHANGE_CANCEL_LABEL)
        self.assertEqual(box.escapeButton().text(), ACCIDENT_DATE_CHANGE_CANCEL_LABEL)
        dialog.close()

    def test_cancel_date_change_keeps_dirty_value_and_does_not_save(self) -> None:
        accident = self._create()
        original = accident.accident_date
        dialog = self._open(accident)
        self._bypass_required_validation(dialog)
        new_date = accident.accident_date - timedelta(days=5)
        dialog.tab_uraz_widget.accident_date.set_date_iso(new_date.isoformat())
        self._answer_date_change(confirm=False)
        dialog.accept()
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.tab_uraz_widget.get_accident_date(), new_date)
        self.assertTrue(dialog.tab_uraz_widget.injury_date_changed_from_baseline())
        reloaded = accident_service.get_by_id(accident.id)
        self.assertEqual(reloaded.accident_date, original)
        dialog.close()

    def test_confirm_date_change_saves_new_date(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        self._bypass_required_validation(dialog)
        new_date = accident.accident_date - timedelta(days=5)
        dialog.tab_uraz_widget.accident_date.set_date_iso(new_date.isoformat())
        self._answer_date_change(confirm=True)
        dialog.accept()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.get_data()["accident_date"], new_date)
        self.assertFalse(dialog.tab_uraz_widget.injury_date_changed_from_baseline())
        dialog.close()

    def test_repeat_save_without_date_change_does_not_ask_again(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        self._bypass_required_validation(dialog)
        new_date = accident.accident_date - timedelta(days=5)
        dialog.tab_uraz_widget.accident_date.set_date_iso(new_date.isoformat())
        boxes = self._answer_date_change(confirm=True)
        dialog.accept()
        self.assertEqual(len(boxes), 1)
        dialog.accept()
        self.assertEqual(len(boxes), 1)
        dialog.close()

    def test_new_accident_does_not_confirm_injury_date(self) -> None:
        dialog = self._open()
        self._bypass_required_validation(dialog)
        dialog.tab_uraz_widget.accident_date.set_date_iso(
            (date.today() - timedelta(days=20)).isoformat()
        )
        dialog.tab_podatel_widget.datum_zapisu.set_date_value(date.today())
        boxes = self._answer_date_change(confirm=True)
        dialog.accept()
        self.assertEqual(boxes, [])
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        dialog.close()

    def test_save_and_close_paths_use_the_same_date_rule(self) -> None:
        accident = self._create()
        dialog = self._open(accident)
        self._bypass_required_validation(dialog)
        new_date = accident.accident_date - timedelta(days=5)
        dialog.tab_uraz_widget.accident_date.set_date_iso(new_date.isoformat())
        boxes = self._answer_date_change(confirm=False)

        buttons = dialog.findChild(QDialogButtonBox)
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        save_btn.click()
        self.assertEqual(len(boxes), 1)
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)

        dialog.accept()
        self.assertEqual(len(boxes), 2)

        close_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        close_btn.click()
        self.assertEqual(len(boxes), 2)
        self.assertTrue(dialog.tab_uraz_widget.injury_date_changed_from_baseline())

    def test_opening_editor_does_not_write_accident(self) -> None:
        accident = self._create()
        original_date = accident.accident_date
        original_name = accident.jmeno_prijmeni
        with patch.object(accident_service, "update_accident") as mock_update:
            dialog = self._open(accident)
            dialog.close()
        mock_update.assert_not_called()
        reloaded = accident_service.get_by_id(accident.id)
        self.assertEqual(reloaded.accident_date, original_date)
        self.assertEqual(reloaded.jmeno_prijmeni, original_name)


if __name__ == "__main__":
    unittest.main()
