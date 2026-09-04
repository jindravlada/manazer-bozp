"""PU-DPN-6 – uzavření případu pracovního úrazu podle ZoÚ a DPN."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLabel
from sqlalchemy import inspect as sa_inspect

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="pu-dpn-6-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
    from moduly.kniha_urazu.sluzby.accident_case_closure import (
        CASE_CLOSED_LABEL,
        CASE_CLOSED_NO,
        CASE_CLOSED_YES,
        CLOSURE_DATE_LABEL,
        DPN_NOT_ENDED_CLOSURE_MESSAGE,
        ZOU_NOT_DONE_CLOSURE_INTRO,
        evaluate_accident_case_closure,
        is_saved_case_closed,
    )
    from moduly.kniha_urazu.sluzby.accident_dpn_care import DPN_CARE_RETURN_KEY
    from moduly.kniha_urazu.sluzby.accident_dpn_responsibility import (
        DPN_EMPLOYER_RESPONSIBILITY_KEY,
    )
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        OBLIGATION_OO_OHLASENI,
        OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI,
        POST_DPN_OBLIGATION_KEYS,
        ZAKONNA_POJISTOVNA_KEYS,
        applicable_obligations,
        obligations_summary_state,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.setreni.setreni_dialog import SetreniDialog
    from moduly.ukoly.modely.task import Task


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
TODAY = date(2026, 4, 20)


class PuDpn6TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(AccidentInvestigation))
            session.execute(delete(Accident))
            session.commit()

    def _create(self, **overrides):
        data = {
            "jmeno_prijmeni": "Jan Novák",
            "pohlavi": "Muž",
            "datum_narozeni": date(1990, 1, 1),
            "druh_urazu": KIND_OVER_3,
            "accident_date": date(2026, 4, 1),
            "accident_time": "10:00",
            "popis_urazoveho_deje": "Pád",
            "dpn_od": date(2026, 4, 1),
            "dpn_do": None,
            "vrchni_dozor": "OIP",
        }
        data.update(overrides)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            return accident_service.create_accident(**data)

    def _saved_data(self, accident_id: int) -> dict:
        investigation = investigation_service.get_or_create(accident_id)
        raw = getattr(investigation, "zajisteni_dukazu_json", "") or ""
        if not str(raw).strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def _write_saved(self, accident_id: int, payload: dict) -> dict:
        current = self._saved_data(accident_id)
        current.update(payload)
        investigation_service.save_zajisteni_dukazu(
            accident_id,
            json.dumps(current, ensure_ascii=False),
        )
        return self._saved_data(accident_id)

    def _snapshot(self, accident: Accident) -> dict:
        mapper = sa_inspect(Accident)
        return {
            attr.key: getattr(accident, attr.key)
            for attr in mapper.column_attrs
            if attr.key != "updated_at"
        }

    def _done_rows(self, accident, saved_data=None, *, include_post_dpn=True):
        rows = []
        for item in applicable_obligations(
            accident,
            saved_data=saved_data,
            union_organization_active=True,
        ):
            if item.key in ZAKONNA_POJISTOVNA_KEYS:
                continue
            if not include_post_dpn and item.key in POST_DPN_OBLIGATION_KEYS:
                continue
            rows.append({"key": item.key, "datum": "2026-04-16"})
        return rows

    def _check(self, accident, saved_data=None):
        return evaluate_accident_case_closure(
            accident,
            saved_data=saved_data,
            today=TODAY,
            union_organization_active=True,
        )

    def _summary(self, accident, rows, saved_data=None):
        return obligations_summary_state(
            accident,
            rows,
            TODAY,
            saved_data=saved_data,
            union_organization_active=True,
        )

    def test_unfinished_zou_blocks_closure(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        saved = {"admin_zaslani": self._done_rows(accident, include_post_dpn=False)}
        self.assertEqual(self._summary(accident, saved["admin_zaslani"], saved), "waiting")
        check = self._check(accident, saved)
        self.assertFalse(check.allowed)
        self.assertFalse(check.dpn_not_ended)
        self.assertTrue(check.unfinished_labels)
        self.assertIn(ZOU_NOT_DONE_CLOSURE_INTRO, check.message)

    def test_green_zou_allows_closure(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        saved = {"admin_zaslani": self._done_rows(accident)}
        self.assertEqual(self._summary(accident, saved["admin_zaslani"], saved), "done")
        check = self._check(accident, saved)
        self.assertTrue(check.allowed)
        self.assertEqual(check.unfinished_labels, ())
        self.assertFalse(check.dpn_not_ended)

    def test_ongoing_dpn_blocks_closure(self) -> None:
        accident = self._create()
        saved = {"admin_zaslani": self._done_rows(accident, include_post_dpn=False)}
        self.assertEqual(self._summary(accident, saved["admin_zaslani"], saved), "done")
        check = self._check(accident, saved)
        self.assertFalse(check.allowed)
        self.assertTrue(check.dpn_not_ended)
        self.assertIn(DPN_NOT_ENDED_CLOSURE_MESSAGE, check.message)

    def test_after_dpn_end_new_duties_block_until_done(self) -> None:
        accident = self._create()
        before = self._check(accident, {"admin_zaslani": self._done_rows(accident)})
        self.assertTrue(before.dpn_not_ended)
        self.assertFalse(before.allowed)

        ended = accident_service.update_accident(accident.id, dpn_do=date(2026, 4, 15))
        original_done = {
            "admin_zaslani": self._done_rows(ended, include_post_dpn=False),
        }
        waiting = self._check(ended, original_done)
        self.assertFalse(waiting.dpn_not_ended)
        self.assertFalse(waiting.allowed)
        self.assertTrue(any("aktualiz" in label.lower() for label in waiting.unfinished_labels))
        self.assertEqual(
            self._summary(ended, original_done["admin_zaslani"], original_done),
            "waiting",
        )

        complete = {"admin_zaslani": self._done_rows(ended)}
        self.assertEqual(self._summary(ended, complete["admin_zaslani"], complete), "done")
        self.assertTrue(self._check(ended, complete).allowed)

    def test_statutory_insurer_and_care_do_not_block(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        saved = {
            "admin_zaslani": self._done_rows(accident)
            + [{"key": OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI}],
            DPN_CARE_RETURN_KEY: {"exam_required": "NE"},
            DPN_EMPLOYER_RESPONSIBILITY_KEY: {"proposed_percent": 40},
        }
        check = self._check(accident, saved)
        self.assertTrue(check.allowed)
        self.assertEqual(self._summary(accident, saved["admin_zaslani"], saved), "done")
        self.assertNotIn(OBLIGATION_ZAKONNA_POJISTOVNA_HLASENI, check.unfinished_labels)

    def test_historically_closed_case_stays_closed(self) -> None:
        accident = self._create(closed=True)
        saved = self._write_saved(
            accident.id,
            {
                "admin_pripad_uzavren": CASE_CLOSED_YES,
                "admin_ukonceni": "2026-04-10",
                "admin_zaslani": [{"key": OBLIGATION_OO_OHLASENI}],
            },
        )
        self.assertTrue(is_saved_case_closed(saved, accident))
        check = self._check(accident, saved)
        self.assertFalse(check.allowed)

        before = self._snapshot(accident_service.get_by_id(accident.id))
        dialog = SetreniDialog(accident=accident_service.get_by_id(accident.id))
        labels = [widget.text() for widget in dialog.findChildren(QLabel)]
        self.assertTrue(any(text.startswith(CLOSURE_DATE_LABEL) for text in labels))
        self.assertTrue(any(text.startswith(CASE_CLOSED_LABEL) for text in labels))
        self.assertFalse(any("Datum ukončení šetření" in text for text in labels))
        self.assertEqual(
            dialog._radio_choice_value(dialog.admin_pripad_uzavren),
            CASE_CLOSED_YES,
        )
        with patch(
            "moduly.kniha_urazu.ui.setreni.setreni_dialog.QMessageBox.warning"
        ) as mock_warn:
            dialog._save_administrativa()
        mock_warn.assert_not_called()
        dialog.close()

        reloaded = accident_service.get_by_id(accident.id)
        after = self._snapshot(reloaded)
        self.assertTrue(reloaded.closed)
        self.assertEqual(after["closed"], before["closed"])
        self.assertEqual(
            self._saved_data(reloaded.id).get("admin_pripad_uzavren"),
            CASE_CLOSED_YES,
        )

    def test_dialog_blocks_new_close_when_dpn_running(self) -> None:
        accident = self._create()
        self._write_saved(
            accident.id,
            {"admin_zaslani": self._done_rows(accident, include_post_dpn=False)},
        )
        dialog = SetreniDialog(accident=accident_service.get_by_id(accident.id))
        with patch(
            "moduly.kniha_urazu.ui.setreni.setreni_dialog.QMessageBox.warning"
        ) as mock_warn:
            dialog._set_radio_choice(dialog.admin_pripad_uzavren, CASE_CLOSED_YES)
            dialog._save_administrativa()
        mock_warn.assert_called()
        self.assertEqual(
            dialog._radio_choice_value(dialog.admin_pripad_uzavren),
            CASE_CLOSED_NO,
        )
        dialog.close()
        self.assertFalse(accident_service.get_by_id(accident.id).closed)
        self.assertNotEqual(
            self._saved_data(accident.id).get("admin_pripad_uzavren"),
            CASE_CLOSED_YES,
        )

    def _mark_dialog_zou_done(self, dialog: SetreniDialog) -> None:
        for row in list(dialog.admin_ohlaseni_rows) + list(dialog._admin_all_zaslani_rows()):
            if row.get("key") in ZAKONNA_POJISTOVNA_KEYS:
                continue
            if row.get("datum") is None:
                continue
            dialog._set_date_widget(row["datum"], date(2026, 4, 16))

    def test_dialog_closes_when_zou_is_green(self) -> None:
        accident = self._create(dpn_do=date(2026, 4, 15))
        dialog = SetreniDialog(accident=accident_service.get_by_id(accident.id))
        self._mark_dialog_zou_done(dialog)
        with patch(
            "moduly.kniha_urazu.ui.setreni.setreni_dialog.QMessageBox.warning"
        ) as mock_warn:
            dialog._set_radio_choice(dialog.admin_pripad_uzavren, CASE_CLOSED_YES)
            dialog._save_administrativa()
        mock_warn.assert_not_called()
        dialog.close()
        reloaded = accident_service.get_by_id(accident.id)
        self.assertTrue(reloaded.closed)
        self.assertEqual(
            self._saved_data(reloaded.id).get("admin_pripad_uzavren"),
            CASE_CLOSED_YES,
        )


if __name__ == "__main__":
    unittest.main()
