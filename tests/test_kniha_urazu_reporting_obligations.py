import importlib
import tempfile
import unittest
from dataclasses import dataclass
from datetime import date
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

    from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
        OBLIGATION_EZOP,
        OBLIGATION_OIP_OBU_OHLASENI,
        OBLIGATION_OIP_OBU_ZASLANI,
        OBLIGATION_OO_OHLASENI,
        OBLIGATION_OO_PREDANI,
        OBLIGATION_POLICIE_OHLASENI,
        OBLIGATION_POLICIE_ZASLANI,
        OBLIGATION_RODINA_PREDANI,
        OBLIGATION_VYHOTOVENI_ZAZNAMU,
        OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
        OBLIGATION_AKTUALIZACE_OO,
        OBLIGATION_AKTUALIZACE_POLICIE,
        OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
        OBLIGATION_AKTUALIZACE_ZP,
        OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN,
        OBLIGATION_ZAMESTNANEC_PREDANI,
        OBLIGATION_ZP_OHLASENI,
        OBLIGATION_ZP_ZASLANI,
        SECTION_ODESLANI,
        SECTION_OHLASENI,
        SECTION_PREDANI,
        SECTION_ZAZNAM,
        applicable_obligations,
        is_criminal_suspicion,
        is_obligation_relevant,
        is_row_relevant,
        obligations_summary_state,
        obligation_rows_for_summary,
        oip_notice_uses_fixed_portal_suip,
        requires_police_obligation,
        row_is_done,
        row_status,
    )


@dataclass
class AccidentStub:
    druh_urazu: str = ""
    podezreni_trestny_cin: str = "NE"
    dpn_od: date | None = None
    dpn_do: date | None = None
    accident_date: date | None = None


class KnihaUrazuReportingObligationsTestCase(unittest.TestCase):
    def _keys(self, accident: AccidentStub, *, union_active: bool = True) -> set[str]:
        return {
            item.key
            for item in applicable_obligations(
                accident,
                union_organization_active=union_active,
            )
        }

    def test_no_pn_shows_only_union_notification(self) -> None:
        accident = AccidentStub(druh_urazu="")
        self.assertEqual(self._keys(accident), {OBLIGATION_OO_OHLASENI})

    def test_pn_two_days_shows_only_union(self) -> None:
        accident = AccidentStub(
            druh_urazu="pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny",
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 1, 2),
        )
        keys = self._keys(accident)
        self.assertEqual(keys, {OBLIGATION_OO_OHLASENI})
        self.assertFalse(is_obligation_relevant(accident, OBLIGATION_VYHOTOVENI_ZAZNAMU))
        self.assertFalse(is_obligation_relevant(accident, OBLIGATION_EZOP))

    def test_pn_ten_days_shows_record_matrix_without_oip_ohlaseni(self) -> None:
        accident = AccidentStub(
            druh_urazu="pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 1, 10),
        )
        keys = self._keys(accident)
        self.assertEqual(
            keys,
            {
                OBLIGATION_OO_OHLASENI,
                OBLIGATION_VYHOTOVENI_ZAZNAMU,
                OBLIGATION_OIP_OBU_ZASLANI,
                OBLIGATION_ZP_ZASLANI,
                OBLIGATION_EZOP,
                OBLIGATION_ZAMESTNANEC_PREDANI,
                OBLIGATION_OO_PREDANI,
                OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
                OBLIGATION_AKTUALIZACE_ZP,
                OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
                OBLIGATION_AKTUALIZACE_OO,
            },
        )
        self.assertNotIn(OBLIGATION_OIP_OBU_OHLASENI, keys)
        self.assertNotIn(OBLIGATION_POLICIE_OHLASENI, keys)
        self.assertNotIn(OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN, keys)
        self.assertNotIn(OBLIGATION_AKTUALIZACE_POLICIE, keys)

    def test_serious_accident_with_short_pn_shows_record_and_oip_ohlaseni(self) -> None:
        accident = AccidentStub(
            druh_urazu="závažný pracovní úraz (hospitalizace více než 5 po sobě jdoucích dnů)",
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 1, 2),
        )
        keys = self._keys(accident)
        self.assertEqual(
            keys,
            {
                OBLIGATION_OO_OHLASENI,
                OBLIGATION_OIP_OBU_OHLASENI,
                OBLIGATION_VYHOTOVENI_ZAZNAMU,
                OBLIGATION_OIP_OBU_ZASLANI,
                OBLIGATION_ZP_ZASLANI,
                OBLIGATION_EZOP,
                OBLIGATION_ZAMESTNANEC_PREDANI,
                OBLIGATION_OO_PREDANI,
                OBLIGATION_AKTUALIZACE_OIP_OBU_PORTAL,
                OBLIGATION_AKTUALIZACE_ZP,
                OBLIGATION_AKTUALIZACE_ZAMESTNANEC,
                OBLIGATION_AKTUALIZACE_OO,
            },
        )
        self.assertNotIn(OBLIGATION_AKTUALIZACE_POLICIE, keys)
        self.assertNotIn(OBLIGATION_AKTUALIZACE_ZAZNAMU_PO_DPN, keys)

    def test_fatal_accident_shows_full_matrix(self) -> None:
        accident = AccidentStub(druh_urazu="smrtelný")
        keys = self._keys(accident)
        self.assertEqual(
            keys,
            {
                OBLIGATION_OO_OHLASENI,
                OBLIGATION_OIP_OBU_OHLASENI,
                OBLIGATION_POLICIE_OHLASENI,
                OBLIGATION_ZP_OHLASENI,
                OBLIGATION_VYHOTOVENI_ZAZNAMU,
                OBLIGATION_OIP_OBU_ZASLANI,
                OBLIGATION_POLICIE_ZASLANI,
                OBLIGATION_ZP_ZASLANI,
                OBLIGATION_EZOP,
                OBLIGATION_OO_PREDANI,
                OBLIGATION_RODINA_PREDANI,
            },
        )
        self.assertNotIn(OBLIGATION_ZAMESTNANEC_PREDANI, keys)

    def test_fatal_accident_creates_police_without_criminal_suspicion(self) -> None:
        accident = AccidentStub(druh_urazu="smrtelný", podezreni_trestny_cin="")
        keys = self._keys(accident)
        self.assertIn(OBLIGATION_POLICIE_OHLASENI, keys)
        self.assertIn(OBLIGATION_POLICIE_ZASLANI, keys)
        self.assertIn(OBLIGATION_ZP_OHLASENI, keys)
        self.assertFalse(is_criminal_suspicion(accident))
        self.assertTrue(requires_police_obligation(accident))

    def test_serious_without_suspicion_has_no_police(self) -> None:
        accident = AccidentStub(
            druh_urazu="závažný pracovní úraz (hospitalizace více než 5 po sobě jdoucích dnů)",
            podezreni_trestny_cin="",
        )
        keys = self._keys(accident)
        self.assertIn(OBLIGATION_OIP_OBU_OHLASENI, keys)
        self.assertNotIn(OBLIGATION_POLICIE_OHLASENI, keys)
        self.assertNotIn(OBLIGATION_POLICIE_ZASLANI, keys)

    def test_serious_with_suspicion_creates_police(self) -> None:
        accident = AccidentStub(
            druh_urazu="závažný pracovní úraz (hospitalizace více než 5 po sobě jdoucích dnů)",
            podezreni_trestny_cin="ANO",
        )
        keys = self._keys(accident)
        self.assertIn(OBLIGATION_POLICIE_OHLASENI, keys)
        self.assertIn(OBLIGATION_POLICIE_ZASLANI, keys)

    def test_oip_notice_portal_cutoff_uses_accident_date(self) -> None:
        self.assertTrue(
            oip_notice_uses_fixed_portal_suip(
                AccidentStub(druh_urazu="smrtelný", accident_date=date(2026, 1, 1))
            )
        )
        self.assertFalse(
            oip_notice_uses_fixed_portal_suip(
                AccidentStub(druh_urazu="smrtelný", accident_date=date(2025, 12, 31))
            )
        )

    def test_criminal_suspicion_adds_police_ohlaseni_only_for_short_pn(self) -> None:
        accident = AccidentStub(
            druh_urazu="pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny",
            podezreni_trestny_cin="ANO",
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 1, 2),
        )
        self.assertEqual(
            self._keys(accident),
            {OBLIGATION_OO_OHLASENI, OBLIGATION_POLICIE_OHLASENI},
        )

    def test_criminal_suspicion_with_pn_over_3_adds_police_to_record_section(self) -> None:
        accident = AccidentStub(
            druh_urazu="pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            podezreni_trestny_cin="ANO",
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 1, 10),
        )
        keys = self._keys(accident)
        self.assertIn(OBLIGATION_POLICIE_OHLASENI, keys)
        self.assertIn(OBLIGATION_POLICIE_ZASLANI, keys)

    def test_oip_obu_zaslani_has_deadline_support_via_row(self) -> None:
        accident = AccidentStub(
            druh_urazu="pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 1, 10),
        )
        row = {
            "key": OBLIGATION_OIP_OBU_ZASLANI,
            "nazev": "OIP / OBÚ – zaslání záznamu o pracovním úrazu",
            "lhuta": "2026-02-01",
        }
        self.assertTrue(is_row_relevant(accident, row))
        self.assertFalse(row_is_done(row))

        done_row = {**row, "datum": "2026-01-20"}
        self.assertTrue(row_is_done(done_row))

    def test_row_status_matches_detail_priority(self) -> None:
        today = date(2026, 1, 15)
        self.assertEqual(row_status({"lhuta": "2026-01-01"}, today), "overdue")
        self.assertEqual(row_status({"lhuta": "2026-02-01"}, today), "waiting")
        self.assertEqual(row_status({"datum": "2026-01-10"}, today), "done")

    def test_zou_summary_without_saved_rows_is_waiting(self) -> None:
        accident = AccidentStub(druh_urazu="")
        self.assertEqual(
            obligations_summary_state(accident, [], date(2026, 1, 15)),
            "waiting",
        )

    def test_zou_summary_missing_obligations_count_as_waiting(self) -> None:
        accident = AccidentStub(
            druh_urazu="pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 1, 10),
        )
        rows = [
            {
                "key": OBLIGATION_OO_OHLASENI,
                "datum": "2026-01-05",
            },
        ]
        self.assertEqual(
            obligations_summary_state(accident, rows, date(2026, 1, 15)),
            "waiting",
        )

    def test_zou_summary_one_overdue_makes_red(self) -> None:
        accident = AccidentStub(
            druh_urazu="pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 1, 10),
        )
        rows = [
            {
                "key": OBLIGATION_OO_OHLASENI,
                "datum": "2026-01-05",
            },
            {
                "key": OBLIGATION_VYHOTOVENI_ZAZNAMU,
                "lhuta": "2026-01-01",
            },
        ]
        self.assertEqual(
            obligations_summary_state(accident, rows, date(2026, 1, 15)),
            "overdue",
        )

    def test_toolbar_button_label(self) -> None:
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)

        from moduly.kniha_urazu.ui.kniha_urazu_page import KnihaUrazuPage

        page = KnihaUrazuPage()
        self.assertEqual(page.investigation_btn.text(), "Ohlašovací povinnosti")
        self.assertNotIn("Administrace úrazu", page.investigation_btn.text())

    def test_legacy_row_names_are_recognized(self) -> None:
        accident = AccidentStub(
            druh_urazu="pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 1, 10),
        )
        self.assertTrue(
            is_row_relevant(accident, {"nazev": "Záznam o pracovním úrazu – Portál SÚIP"})
        )
        self.assertTrue(
            is_row_relevant(
                accident,
                {"nazev": "Postižený zaměstnanec – předání podepsaného záznamu o pracovním úrazu"},
            )
        )

    def test_kooperativa_is_never_relevant(self) -> None:
        accident = AccidentStub(druh_urazu="smrtelný")
        self.assertFalse(is_row_relevant(accident, {"nazev": "Kooperativa"}))

    def test_sections_are_assigned_correctly(self) -> None:
        accident = AccidentStub(druh_urazu="smrtelný")
        by_section: dict[str, list[str]] = {}
        for item in applicable_obligations(accident):
            by_section.setdefault(item.section, []).append(item.key)

        self.assertIn(OBLIGATION_OO_OHLASENI, by_section[SECTION_OHLASENI])
        self.assertIn(OBLIGATION_VYHOTOVENI_ZAZNAMU, by_section[SECTION_ZAZNAM])
        self.assertIn(OBLIGATION_OIP_OBU_ZASLANI, by_section[SECTION_ODESLANI])
        self.assertIn(OBLIGATION_RODINA_PREDANI, by_section[SECTION_PREDANI])

    def test_zou_summary_without_record_only_tracks_ohlaseni(self) -> None:
        accident = AccidentStub(druh_urazu="")
        rows = [
            {
                "key": OBLIGATION_OO_OHLASENI,
                "nazev": "Odborová organizace – ohlášení pracovního úrazu",
                "lhuta": "2026-02-01",
            }
        ]
        today = date(2026, 1, 15)
        self.assertEqual(obligations_summary_state(accident, rows, today), "waiting")

        done_rows = [{**rows[0], "datum": "2026-01-10"}]
        self.assertEqual(obligations_summary_state(accident, done_rows, today), "done")

    def test_zou_summary_marks_overdue_when_deadline_passed(self) -> None:
        accident = AccidentStub(druh_urazu="")
        rows = [
            {
                "key": OBLIGATION_OO_OHLASENI,
                "nazev": "Odborová organizace – ohlášení pracovního úrazu",
                "lhuta": "2026-01-01",
            }
        ]
        self.assertEqual(
            obligations_summary_state(accident, rows, date(2026, 1, 15)),
            "overdue",
        )

    def test_zou_summary_aggregates_all_sections(self) -> None:
        accident = AccidentStub(
            druh_urazu="pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 1, 10),
        )
        rows = [
            {
                "key": OBLIGATION_OO_OHLASENI,
                "nazev": "Odborová organizace – ohlášení pracovního úrazu",
                "datum": "2026-01-05",
            },
            {
                "key": OBLIGATION_VYHOTOVENI_ZAZNAMU,
                "nazev": "Vyhotovení Záznamu o pracovním úrazu",
                "lhuta": "2026-02-01",
            },
        ]
        self.assertEqual(
            obligations_summary_state(accident, rows, date(2026, 1, 15)),
            "waiting",
        )

    def test_obligation_rows_for_summary_matches_detail_overdue_state(self) -> None:
        accident = AccidentStub(
            druh_urazu="závažný pracovní úraz (hospitalizace více než 5 po sobě jdoucích dnů)",
            accident_date=date(2026, 3, 23),
        )
        saved_data = {
            "admin_ohlaseni": [
                {
                    "nazev": "Odborová organizace – ohlášení pracovního úrazu",
                    "datum": "2026-06-27",
                    "lhuta": "2026-06-29",
                },
                {
                    "nazev": "OIP / OBÚ – ohlášení závažného nebo smrtelného pracovního úrazu",
                    "datum": "2026-06-27",
                    "lhuta": "2026-06-29",
                },
                {
                    "nazev": "Policie ČR – ohlášení smrtelného pracovního úrazu / podezření na trestný čin",
                    "datum": "2026-06-27",
                    "lhuta": "2026-06-29",
                },
                {
                    "nazev": "EZOP – ohlášení pracovního úrazu",
                    "datum": "2026-06-27",
                    "lhuta": "2026-06-29",
                },
            ],
            "admin_zaslani": [
                {
                    "nazev": "Záznam o pracovním úrazu – Portál SÚIP",
                    "lhuta": "2026-07-17",
                },
                {
                    "nazev": "Kooperativa",
                    "lhuta": "",
                },
            ],
        }
        rows = obligation_rows_for_summary(accident, saved_data)
        today = date(2026, 7, 1)

        self.assertEqual(obligations_summary_state(accident, rows, today), "overdue")
        self.assertIn(OBLIGATION_OIP_OBU_ZASLANI, {row["key"] for row in rows})
        self.assertEqual(
            row_status(
                next(row for row in rows if row["key"] == OBLIGATION_VYHOTOVENI_ZAZNAMU),
                today,
            ),
            "overdue",
        )

    def test_obligation_rows_for_summary_keeps_done_rows(self) -> None:
        accident = AccidentStub(
            druh_urazu="závažný pracovní úraz (hospitalizace více než 5 po sobě jdoucích dnů)",
            accident_date=date(2026, 3, 23),
        )
        saved_data = {
            "admin_ohlaseni": [
                {
                    "key": OBLIGATION_OO_OHLASENI,
                    "nazev": "Odborová organizace – ohlášení pracovního úrazu",
                    "datum": "2026-06-27",
                    "lhuta": "2026-06-29",
                },
            ],
        }
        rows = obligation_rows_for_summary(accident, saved_data)
        done_row = next(row for row in rows if row["key"] == OBLIGATION_OO_OHLASENI)

        self.assertEqual(row_status(done_row, date(2026, 7, 1)), "done")


class SetreniDialogExecTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication, QDialog

        cls._app = QApplication.instance() or QApplication([])
        cls._dialog = QDialog

    def test_opens_via_exec_maximized_helper(self) -> None:
        from PySide6.QtWidgets import QDialog

        from core.widgets.dialog_utils import exec_maximized
        from moduly.kniha_urazu.modely.accident import Accident
        from moduly.kniha_urazu.ui.setreni.setreni_dialog import SetreniDialog

        accident = Accident(number="2026-001")
        accident.id = 1

        with patch(
            "core.widgets.dialog_utils.prepare_work_dialog_maximized"
        ) as mock_prepare:
            with patch.object(QDialog, "exec", return_value=QDialog.Accepted) as mock_exec:
                dialog = SetreniDialog(accident=accident)
                result = exec_maximized(dialog)

        self.assertEqual(result, QDialog.Accepted)
        mock_prepare.assert_called_once_with(dialog)
        mock_exec.assert_called_once()

    def test_save_administrativa_marks_accident_closed(self) -> None:
        from moduly.kniha_urazu.modely.accident import Accident
        from moduly.kniha_urazu.ui.setreni.setreni_dialog import SetreniDialog

        accident = Accident(number="2026-001", closed=False)
        accident.id = 7
        dialog = SetreniDialog(accident=accident)
        dialog.admin_pripad_uzavren = dialog._radio_choice(["ANO", "NE"])
        dialog._set_radio_choice(dialog.admin_pripad_uzavren, "ANO")

        with patch(
            "moduly.kniha_urazu.sluzby.accident_reporting_obligations.employer_union_organization_active",
            return_value=False,
        ):
            with patch(
                "moduly.kniha_urazu.ui.setreni.setreni_dialog.investigation_service.save_zajisteni_dukazu"
            ) as mock_save:
                with patch(
                    "moduly.kniha_urazu.ui.setreni.setreni_dialog.accident_service.update_accident",
                    return_value=accident,
                ) as mock_update:
                    dialog._save_administrativa()

        mock_save.assert_called_once()
        mock_update.assert_called_once_with(7, closed=True)


class AccidentDialogExecTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication, QDialog

        cls._app = QApplication.instance() or QApplication([])
        cls._dialog = QDialog

    def test_opens_via_exec_maximized_helper(self) -> None:
        from PySide6.QtWidgets import QDialog

        from core.widgets.dialog_utils import exec_maximized
        from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog

        with patch(
            "core.widgets.dialog_utils.prepare_work_dialog_maximized"
        ) as mock_prepare:
            with patch.object(QDialog, "exec", return_value=QDialog.Accepted) as mock_exec:
                dialog = AccidentDialog()
                result = exec_maximized(dialog)

        self.assertEqual(result, QDialog.Accepted)
        mock_prepare.assert_called_once_with(dialog)
        mock_exec.assert_called_once()


if __name__ == "__main__":
    unittest.main()
