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
        OBLIGATION_ZAMESTNANEC_PREDANI,
        OBLIGATION_ZP_OHLASENI,
        OBLIGATION_ZP_ZASLANI,
        SECTION_ODESLANI,
        SECTION_OHLASENI,
        SECTION_PREDANI,
        SECTION_ZAZNAM,
        applicable_obligations,
        is_obligation_relevant,
        is_row_relevant,
        obligations_summary_state,
        row_is_done,
    )


@dataclass
class AccidentStub:
    druh_urazu: str = ""
    podezreni_trestny_cin: str = "NE"
    dpn_od: date | None = None
    dpn_do: date | None = None


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
            },
        )
        self.assertNotIn(OBLIGATION_OIP_OBU_OHLASENI, keys)
        self.assertNotIn(OBLIGATION_POLICIE_OHLASENI, keys)

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
            },
        )

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


if __name__ == "__main__":
    unittest.main()
