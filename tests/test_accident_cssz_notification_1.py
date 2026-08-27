"""ACCIDENT-CSSZ-NOTIFICATION-1 – podklady k nemocenskému (ČSSZ/ÚSSZ)."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QGroupBox, QLabel, QRadioButton

_TMP = Path(tempfile.mkdtemp(prefix="accident-cssz-notification-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.constants import ENTITY_ACCIDENT
    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        CSSZ_STATUS_DONE,
        CSSZ_STATUS_OPTIONAL,
        CSSZ_STATUS_REQUIRED,
        METHOD_PORTAL_SUIP,
        OBLIGATION_CSSZ_USSZ_NEMOCENSKE,
        OBLIGATION_LABELS,
        OBLIGATION_OO_OHLASENI,
        OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU,
        OBLIGATION_VYHOTOVENI_ZAZNAMU,
        RECORD_DUTY_GENERATION_COMBINED,
        RECORD_DUTY_GENERATION_KEY,
        RECORD_DUTY_GENERATION_LEGACY,
        SECTION_NEMOCENSKE,
        SECTION_OHLASENI,
        SECTION_ZAZNAM,
        applicable_obligations,
        cssz_dpn_calendar_days,
        cssz_nemocenske_is_required,
        cssz_row_ui_state,
        dpn_calendar_days,
        is_obligation_relevant,
        is_obligation_required,
        is_obligation_visible,
        is_row_visible,
        obligation_default_deadline,
        obligation_key_from_row,
        obligation_rows_for_summary,
        obligations_summary_state,
        record_duty_keys_hidden_for_generation,
        _section_for_key,
    )
    from moduly.kniha_urazu.sluzby.accident_reporting_task_service import (
        OHLASENI_TASK_TITLE_PREFIX,
        ZAZNAM_TASK_TITLE_PREFIX,
        accident_reporting_task_service,
    )
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.investigation_service import investigation_service
    from moduly.kniha_urazu.ui.setreni.setreni_dialog import SetreniDialog
    from moduly.ukoly.sluzby.task_service import task_service


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
KIND_UP_TO_3 = "pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny"
CSSZ_LABEL = "ČSSZ / ÚSSZ – podklady k nemocenskému"
TODAY = date(2026, 8, 27)


class AccidentStub:
    def __init__(
        self,
        *,
        druh_urazu: str = "",
        dpn_od: date | None = None,
        dpn_do: date | None = None,
        accident_date: date | None = None,
        podezreni_trestny_cin: str = "NE",
    ):
        self.druh_urazu = druh_urazu
        self.dpn_od = dpn_od
        self.dpn_do = dpn_do
        self.accident_date = accident_date
        self.podezreni_trestny_cin = podezreni_trestny_cin


class CsszDpnCalculationTestCase(unittest.TestCase):
    def test_first_day_counts_as_one_calendar_day(self) -> None:
        start = date(2026, 3, 1)
        self.assertEqual(cssz_dpn_calendar_days(start, start, today=start), 1)
        self.assertEqual(cssz_dpn_calendar_days(start, None, today=start), 1)

    def test_day_14_is_not_required(self) -> None:
        start = date(2026, 3, 1)
        day_14 = date(2026, 3, 14)
        self.assertEqual(cssz_dpn_calendar_days(start, day_14, today=day_14), 14)
        accident = AccidentStub(dpn_od=start, dpn_do=day_14)
        self.assertFalse(cssz_nemocenske_is_required(accident, today=day_14))
        self.assertFalse(
            is_obligation_required(
                accident,
                OBLIGATION_CSSZ_USSZ_NEMOCENSKE,
                today=day_14,
            )
        )

    def test_day_15_is_required(self) -> None:
        start = date(2026, 3, 1)
        day_15 = date(2026, 3, 15)
        self.assertEqual(cssz_dpn_calendar_days(start, day_15, today=day_15), 15)
        accident = AccidentStub(dpn_od=start, dpn_do=day_15)
        self.assertTrue(cssz_nemocenske_is_required(accident, today=day_15))

    def test_closed_14_days_not_required(self) -> None:
        accident = AccidentStub(dpn_od=date(2026, 4, 1), dpn_do=date(2026, 4, 14))
        self.assertFalse(cssz_nemocenske_is_required(accident, today=date(2026, 4, 20)))

    def test_closed_15_days_required(self) -> None:
        accident = AccidentStub(dpn_od=date(2026, 4, 1), dpn_do=date(2026, 4, 15))
        self.assertTrue(cssz_nemocenske_is_required(accident, today=date(2026, 4, 20)))

    def test_ongoing_uses_passed_today(self) -> None:
        start = date(2026, 5, 1)
        self.assertEqual(
            cssz_dpn_calendar_days(start, None, today=date(2026, 5, 14)),
            14,
        )
        self.assertEqual(
            cssz_dpn_calendar_days(start, None, today=date(2026, 5, 15)),
            15,
        )
        accident = AccidentStub(dpn_od=start)
        self.assertFalse(cssz_nemocenske_is_required(accident, today=date(2026, 5, 14)))
        self.assertTrue(cssz_nemocenske_is_required(accident, today=date(2026, 5, 15)))

    def test_without_dpn_od_duration_unknown(self) -> None:
        self.assertIsNone(cssz_dpn_calendar_days(None, date(2026, 5, 20), today=TODAY))
        accident = AccidentStub(dpn_do=date(2026, 5, 20), druh_urazu=KIND_OVER_3)
        self.assertFalse(cssz_nemocenske_is_required(accident, today=TODAY))

    def test_invalid_or_future_interval_does_not_create_duty(self) -> None:
        start = date(2026, 6, 10)
        self.assertIsNone(
            cssz_dpn_calendar_days(start, date(2026, 6, 1), today=date(2026, 6, 20))
        )
        self.assertIsNone(
            cssz_dpn_calendar_days(date(2026, 7, 1), None, today=date(2026, 6, 1))
        )
        # Budoucí dpn_do se nesmí započítat jako dlouhá uzavřená DPN.
        self.assertEqual(
            cssz_dpn_calendar_days(start, date(2026, 8, 1), today=start),
            1,
        )
        accident = AccidentStub(dpn_od=start, dpn_do=date(2026, 8, 1))
        self.assertFalse(cssz_nemocenske_is_required(accident, today=start))

    def test_existing_dpn_calendar_days_unchanged(self) -> None:
        start = date(2026, 3, 1)
        self.assertEqual(dpn_calendar_days(start, date(2026, 3, 3)), 3)
        self.assertIsNone(dpn_calendar_days(start, None))


class CsszVisibilityAndStateTestCase(unittest.TestCase):
    def test_official_label_and_section(self) -> None:
        self.assertEqual(OBLIGATION_LABELS[OBLIGATION_CSSZ_USSZ_NEMOCENSKE], CSSZ_LABEL)
        self.assertEqual(_section_for_key(OBLIGATION_CSSZ_USSZ_NEMOCENSKE), SECTION_NEMOCENSKE)
        self.assertNotEqual(_section_for_key(OBLIGATION_CSSZ_USSZ_NEMOCENSKE), SECTION_OHLASENI)

    def test_not_visible_without_dpn_od_or_saved_data(self) -> None:
        accident = AccidentStub(druh_urazu=KIND_OVER_3)
        self.assertFalse(
            is_obligation_visible(accident, OBLIGATION_CSSZ_USSZ_NEMOCENSKE)
        )
        self.assertFalse(
            is_row_visible(accident, {"key": OBLIGATION_CSSZ_USSZ_NEMOCENSKE})
        )

    def test_kind_with_pn_without_dpn_od_is_not_enough(self) -> None:
        accident = AccidentStub(druh_urazu=KIND_OVER_3)
        self.assertFalse(
            is_obligation_visible(accident, OBLIGATION_CSSZ_USSZ_NEMOCENSKE)
        )

    def test_visible_immediately_when_dpn_od_set(self) -> None:
        accident = AccidentStub(dpn_od=TODAY, druh_urazu=KIND_UP_TO_3)
        self.assertTrue(is_obligation_visible(accident, OBLIGATION_CSSZ_USSZ_NEMOCENSKE))
        self.assertFalse(
            is_obligation_required(
                accident,
                OBLIGATION_CSSZ_USSZ_NEMOCENSKE,
                today=TODAY,
            )
        )
        self.assertEqual(
            cssz_row_ui_state(accident, {}, today=TODAY),
            "optional",
        )

    def test_required_on_day_15_without_sending(self) -> None:
        start = TODAY - timedelta(days=14)
        accident = AccidentStub(dpn_od=start)
        self.assertTrue(cssz_nemocenske_is_required(accident, today=TODAY))
        self.assertEqual(
            cssz_row_ui_state(accident, {}, today=TODAY),
            "required",
        )

    def test_sending_before_day_15_is_done(self) -> None:
        accident = AccidentStub(dpn_od=TODAY, dpn_do=TODAY + timedelta(days=3))
        row = {"key": OBLIGATION_CSSZ_USSZ_NEMOCENSKE, "datum": TODAY.isoformat()}
        self.assertEqual(cssz_row_ui_state(accident, row, today=TODAY), "done")
        later = AccidentStub(dpn_od=TODAY, dpn_do=TODAY + timedelta(days=20))
        self.assertEqual(
            cssz_row_ui_state(later, row, today=TODAY + timedelta(days=20)),
            "done",
        )

    def test_short_closed_dpn_stays_visible_but_not_required(self) -> None:
        accident = AccidentStub(dpn_od=date(2026, 4, 1), dpn_do=date(2026, 4, 10))
        self.assertTrue(is_obligation_visible(accident, OBLIGATION_CSSZ_USSZ_NEMOCENSKE))
        self.assertFalse(cssz_nemocenske_is_required(accident, today=date(2026, 4, 20)))
        self.assertEqual(
            cssz_row_ui_state(accident, {}, today=date(2026, 4, 20)),
            "optional",
        )

    def test_saved_sending_survives_missing_dpn(self) -> None:
        accident = AccidentStub(druh_urazu=KIND_UP_TO_3)
        saved = {
            "admin_zaslani": [
                {
                    "key": OBLIGATION_CSSZ_USSZ_NEMOCENSKE,
                    "datum": "2026-04-02",
                    "cas": "09:10",
                    "zpusob": "E-mail",
                    "upresneni": "odesláno předem",
                }
            ]
        }
        self.assertTrue(
            is_obligation_visible(
                accident,
                OBLIGATION_CSSZ_USSZ_NEMOCENSKE,
                saved_data=saved,
            )
        )
        self.assertFalse(
            cssz_nemocenske_is_required(accident, today=TODAY)
        )
        self.assertEqual(
            cssz_row_ui_state(
                accident,
                saved["admin_zaslani"][0],
                today=TODAY,
            ),
            "done",
        )

    def test_cssz_never_relevant_for_nv322_matrix(self) -> None:
        accident = AccidentStub(
            druh_urazu=KIND_OVER_3,
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 2, 1),
        )
        self.assertFalse(
            is_obligation_relevant(accident, OBLIGATION_CSSZ_USSZ_NEMOCENSKE)
        )
        keys = {item.key for item in applicable_obligations(accident)}
        self.assertNotIn(OBLIGATION_CSSZ_USSZ_NEMOCENSKE, keys)

    def test_no_nv322_deadlines(self) -> None:
        notification = date(2026, 7, 1)
        self.assertIsNone(
            obligation_default_deadline(
                notification,
                obligation_key=OBLIGATION_CSSZ_USSZ_NEMOCENSKE,
                section=SECTION_NEMOCENSKE,
                label=CSSZ_LABEL,
            )
        )
        self.assertIsNotNone(
            obligation_default_deadline(
                notification,
                obligation_key=OBLIGATION_OO_OHLASENI,
                section=SECTION_OHLASENI,
            )
        )
        self.assertIsNotNone(
            obligation_default_deadline(
                notification,
                obligation_key=OBLIGATION_VYHOTOVENI_ZAZNAMU,
                section=SECTION_ZAZNAM,
            )
        )

    def test_not_hidden_by_record_generation(self) -> None:
        self.assertNotIn(
            OBLIGATION_CSSZ_USSZ_NEMOCENSKE,
            record_duty_keys_hidden_for_generation(RECORD_DUTY_GENERATION_LEGACY),
        )
        self.assertNotIn(
            OBLIGATION_CSSZ_USSZ_NEMOCENSKE,
            record_duty_keys_hidden_for_generation(RECORD_DUTY_GENERATION_COMBINED),
        )

    def test_zou_summary_ignores_required_unsent_cssz(self) -> None:
        start = TODAY - timedelta(days=14)
        accident = AccidentStub(dpn_od=start, druh_urazu=KIND_UP_TO_3)
        self.assertTrue(cssz_nemocenske_is_required(accident, today=TODAY))
        self.assertIsNone(
            obligations_summary_state(
                accident,
                [],
                TODAY,
                union_organization_active=False,
            )
        )
        rows = obligation_rows_for_summary(
            accident,
            {},
            union_organization_active=False,
        )
        self.assertNotIn(
            OBLIGATION_CSSZ_USSZ_NEMOCENSKE,
            {obligation_key_from_row(row) for row in rows},
        )


class CsszDialogPersistenceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
        from moduly.ukoly.modely.task import Task

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(AccidentInvestigation))
            session.execute(delete(Accident))
            session.commit()

    def _create(
        self,
        *,
        dpn_od: date | None,
        dpn_do: date | None = None,
        druh_urazu: str = KIND_UP_TO_3,
        name: str = "ČSSZ úraz",
    ) -> Accident:
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=False,
        ):
            return accident_service.create_accident(
                jmeno_prijmeni=name,
                accident_date=dpn_od or TODAY,
                druh_urazu=druh_urazu,
                dpn_od=dpn_od,
                dpn_do=dpn_do,
            )

    def _saved_data(self, accident_id: int) -> dict:
        investigation = investigation_service.get_or_create(accident_id)
        raw = getattr(investigation, "zajisteni_dukazu_json", "") or ""
        if not raw.strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}

    def _cssz_row(self, dialog: SetreniDialog) -> dict:
        self.assertEqual(len(dialog.admin_nemocenske_rows), 1)
        return dialog.admin_nemocenske_rows[0]

    def _visible_cssz(self, dialog: SetreniDialog) -> bool:
        return any(dialog._admin_row_relevant(row) for row in dialog.admin_nemocenske_rows)

    def _cssz_saved(self, accident_id: int) -> dict:
        for row in self._saved_data(accident_id).get("admin_zaslani") or []:
            if obligation_key_from_row(row) == OBLIGATION_CSSZ_USSZ_NEMOCENSKE:
                return row
        return {}

    def _status_texts(self, dialog: SetreniDialog) -> list[str]:
        texts: list[str] = []
        for box in dialog.findChildren(QGroupBox):
            if box.title() == CSSZ_LABEL or box.title() == "NEMOCENSKÉ POJIŠTĚNÍ":
                texts.extend(label.text() for label in box.findChildren(QLabel))
        return texts

    def _fill_cssz(self, dialog: SetreniDialog, sent: date) -> None:
        row = self._cssz_row(dialog)
        dialog._set_date_widget(row["datum"], sent)
        row["cas"].setText("09:15")
        dialog._set_radio_choice(row["zpusob"], "E-mail")
        row["upresneni"].setText("podklady odeslány předem")

    def test_hidden_without_dpn(self) -> None:
        accident = self._create(dpn_od=None, druh_urazu="")
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=False,
        ):
            dialog = SetreniDialog(accident=accident)
        self.assertFalse(self._visible_cssz(dialog))
        self.assertNotIn("NEMOCENSKÉ POJIŠTĚNÍ", [box.title() for box in dialog.findChildren(QGroupBox)])

    def test_visible_with_dpn_od_and_optional_status(self) -> None:
        today = date.today()
        accident = self._create(dpn_od=today)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=False,
        ):
            dialog = SetreniDialog(accident=accident)
        self.assertTrue(self._visible_cssz(dialog))
        self.assertIn(CSSZ_STATUS_OPTIONAL, self._status_texts(dialog))
        self.assertNotIn("Po termínu", self._status_texts(dialog))
        self.assertNotIn("Nevyřízeno", self._status_texts(dialog))

    def test_required_status_on_day_15(self) -> None:
        start = TODAY - timedelta(days=14)
        accident = self._create(dpn_od=start)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=False,
        ):
            dialog = SetreniDialog(accident=accident)
            row = self._cssz_row(dialog)
            state = cssz_row_ui_state(
                accident,
                dialog._admin_row_state_dict(row),
                today=TODAY,
            )
        self.assertEqual(state, "required")
        self.assertTrue(dialog._admin_row_relevant(row))

    def test_opening_dialog_does_not_write_cssz(self) -> None:
        accident = self._create(dpn_od=TODAY)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=False,
        ):
            SetreniDialog(accident=accident)
        self.assertEqual(self._cssz_saved(accident.id), {})

    def test_reject_discards_unsaved_cssz(self) -> None:
        accident = self._create(dpn_od=TODAY)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=False,
        ):
            dialog = SetreniDialog(accident=accident)
            self._fill_cssz(dialog, TODAY)
            dialog.reject()
        self.assertEqual(self._cssz_saved(accident.id), {})

    def test_save_roundtrip_keeps_fields(self) -> None:
        accident = self._create(dpn_od=TODAY)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=False,
        ):
            dialog = SetreniDialog(accident=accident)
            self._fill_cssz(dialog, TODAY)
            dialog.accept()

        saved = self._cssz_saved(accident.id)
        self.assertEqual(saved.get("key"), OBLIGATION_CSSZ_USSZ_NEMOCENSKE)
        self.assertEqual(saved.get("nazev"), CSSZ_LABEL)
        self.assertEqual(saved.get("section"), SECTION_NEMOCENSKE)
        self.assertEqual(saved.get("datum"), TODAY.isoformat())
        self.assertEqual(saved.get("cas"), "09:15")
        self.assertEqual(saved.get("zpusob"), "E-mail")
        self.assertEqual(saved.get("upresneni"), "podklady odeslány předem")
        self.assertNotEqual(saved.get("zpusob"), METHOD_PORTAL_SUIP)

        accident = accident_service.get_by_id(accident.id)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=False,
        ):
            dialog = SetreniDialog(accident=accident)
            row = self._cssz_row(dialog)
            self.assertTrue(dialog._admin_row_relevant(row))
            self.assertEqual(dialog._admin_date_value(row["datum"]), TODAY)
            self.assertEqual(row["cas"].text(), "09:15")
            self.assertEqual(dialog._radio_choice_value(row["zpusob"]), "E-mail")
            self.assertEqual(row["upresneni"].text(), "podklady odeslány předem")
            dialog.accept()

        again = self._cssz_saved(accident.id)
        self.assertEqual(again.get("datum"), TODAY.isoformat())
        self.assertEqual(again.get("cas"), "09:15")
        self.assertEqual(again.get("zpusob"), "E-mail")
        self.assertEqual(again.get("upresneni"), "podklady odeslány předem")

    def test_not_portal_suip_methods(self) -> None:
        accident = self._create(dpn_od=TODAY)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=False,
        ):
            dialog = SetreniDialog(accident=accident)
            row = self._cssz_row(dialog)
        methods = [button.text() for button in row["zpusob"].findChildren(QRadioButton)]
        self.assertNotIn(METHOD_PORTAL_SUIP, methods)
        self.assertIn("Datová schránka", methods)
        self.assertIsNone(row.get("lhuta"))

    def test_change_dpn_do_does_not_overwrite_cssz(self) -> None:
        accident = self._create(dpn_od=date(2026, 4, 1), dpn_do=None)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=False,
        ):
            dialog = SetreniDialog(accident=accident)
            self._fill_cssz(dialog, date(2026, 4, 3))
            dialog.accept()

        updated = accident_service.update_accident(
            accident.id,
            dpn_do=date(2026, 4, 8),
        )
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=False,
        ):
            dialog = SetreniDialog(accident=updated)
            row = self._cssz_row(dialog)
            self.assertEqual(dialog._admin_date_value(row["datum"]), date(2026, 4, 3))
            self.assertEqual(row["upresneni"].text(), "podklady odeslány předem")
            self.assertTrue(dialog._admin_row_relevant(row))
            self.assertEqual(
                cssz_row_ui_state(
                    updated,
                    dialog._admin_row_state_dict(row),
                    today=date(2026, 4, 20),
                ),
                "done",
            )

    def test_removing_dpn_od_keeps_saved_sending(self) -> None:
        accident = self._create(dpn_od=date(2026, 4, 1))
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=False,
        ):
            dialog = SetreniDialog(accident=accident)
            self._fill_cssz(dialog, date(2026, 4, 2))
            dialog.accept()

        updated = accident_service.update_accident(accident.id, dpn_od=None, dpn_do=None)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=False,
        ):
            dialog = SetreniDialog(accident=updated)
            row = self._cssz_row(dialog)
            self.assertTrue(dialog._admin_row_relevant(row))
            self.assertEqual(dialog._admin_date_value(row["datum"]), date(2026, 4, 2))
            dialog.accept()

        saved = self._cssz_saved(accident.id)
        self.assertEqual(saved.get("datum"), "2026-04-02")
        self.assertEqual(saved.get("upresneni"), "podklady odeslány předem")

    def test_generation_switch_keeps_cssz_row(self) -> None:
        accident = self._create(
            dpn_od=date(2026, 4, 1),
            dpn_do=date(2026, 4, 20),
            druh_urazu=KIND_OVER_3,
        )
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            dialog = SetreniDialog(accident=accident)
            self._fill_cssz(dialog, date(2026, 4, 5))
            dialog.accept()

        data = self._saved_data(accident.id)
        data[RECORD_DUTY_GENERATION_KEY] = RECORD_DUTY_GENERATION_LEGACY
        data.setdefault("admin_zaslani", []).append(
            {
                "key": OBLIGATION_VYHOTOVENI_ZAZNAMU,
                "nazev": OBLIGATION_LABELS[OBLIGATION_VYHOTOVENI_ZAZNAMU],
                "datum": "2026-04-10",
            }
        )
        investigation_service.save_zajisteni_dukazu(
            accident.id,
            json.dumps(data, ensure_ascii=False),
        )
        accident = accident_service.get_by_id(accident.id)
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            dialog = SetreniDialog(accident=accident)
            row = self._cssz_row(dialog)
            self.assertEqual(dialog._admin_date_value(row["datum"]), date(2026, 4, 5))
            dialog.accept()

        saved = self._cssz_saved(accident.id)
        self.assertEqual(saved.get("datum"), "2026-04-05")
        keys = {
            obligation_key_from_row(row)
            for row in self._saved_data(accident.id).get("admin_zaslani") or []
        }
        self.assertIn(OBLIGATION_CSSZ_USSZ_NEMOCENSKE, keys)
        self.assertIn(OBLIGATION_VYHOTOVENI_ZAZNAMU, keys)
        self.assertNotIn(OBLIGATION_VYHOTOVENI_ZASLANI_ZAZNAMU, keys)

    def test_cssz_not_in_record_section_or_tasks(self) -> None:
        start = TODAY - timedelta(days=14)
        accident = self._create(
            dpn_od=start,
            druh_urazu=KIND_OVER_3,
            dpn_do=TODAY,
        )
        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=True,
        ):
            dialog = SetreniDialog(accident=accident)
            record_titles = [
                row["nazev"]
                for row in list(dialog.admin_zaznam_rows) + list(dialog.admin_odeslani_rows)
                if dialog._admin_row_relevant(row)
            ]
            ohlaseni_titles = [
                row["nazev"]
                for row in dialog.admin_ohlaseni_rows
                if dialog._admin_row_relevant(row)
            ]
            predani_titles = [
                row["nazev"]
                for row in dialog.admin_predani_rows
                if dialog._admin_row_relevant(row)
            ]
        self.assertNotIn(CSSZ_LABEL, record_titles)
        self.assertNotIn(CSSZ_LABEL, ohlaseni_titles)
        self.assertNotIn(CSSZ_LABEL, predani_titles)

        accident_reporting_task_service.sync_for_accident(accident)
        titles = [
            task.title
            for task in task_service.get_all_tasks()
            if task.source_module == ENTITY_ACCIDENT
            and task.source_record_id == accident.id
            and not task.completed
            and not task.canceled
        ]
        for title in titles:
            self.assertNotIn("ČSSZ", title)
            self.assertNotIn("nemocensk", title.lower())
        self.assertTrue(any(title.startswith(OHLASENI_TASK_TITLE_PREFIX) for title in titles))
        self.assertTrue(any(title.startswith(ZAZNAM_TASK_TITLE_PREFIX) for title in titles))
        self.assertTrue(
            all(
                "ČSSZ" not in (task.description or "")
                for task in task_service.get_all_tasks()
                if task.source_record_id == accident.id
            )
        )


if __name__ == "__main__":
    unittest.main()
