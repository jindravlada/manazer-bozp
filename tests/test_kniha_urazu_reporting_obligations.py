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
        OBLIGATION_POLICIE_OHLASENI,
        OBLIGATION_POLICIE_ZASLANI,
        OBLIGATION_VYHOTOVENI_ZAZNAMU,
        OBLIGATION_ZP_OHLASENI,
        OBLIGATION_ZP_ZASLANI,
        SECTION_ODESLANI,
        OBLIGATION_LABELS,
        SECTION_OHLASENI,
        SECTION_ZAZNAM,
        applicable_obligations,
        is_obligation_relevant,
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
        keys = self._keys(accident)
        self.assertEqual(keys, {OBLIGATION_OO_OHLASENI})

    def test_no_pn_without_union_shows_nothing(self) -> None:
        accident = AccidentStub(druh_urazu="")
        keys = self._keys(accident, union_active=False)
        self.assertEqual(keys, set())

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

    def test_pn_ten_days_shows_record_sections(self) -> None:
        accident = AccidentStub(
            druh_urazu="pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 1, 10),
        )
        keys = self._keys(accident)
        self.assertIn(OBLIGATION_OO_OHLASENI, keys)
        self.assertIn(OBLIGATION_EZOP, keys)
        self.assertIn(OBLIGATION_VYHOTOVENI_ZAZNAMU, keys)
        self.assertIn(OBLIGATION_ZP_ZASLANI, keys)
        self.assertNotIn(OBLIGATION_OIP_OBU_OHLASENI, keys)
        self.assertNotIn(OBLIGATION_POLICIE_OHLASENI, keys)

    def test_serious_accident_adds_oip_obu_only_in_ohlaseni(self) -> None:
        accident = AccidentStub(
            druh_urazu="závažný pracovní úraz (hospitalizace více než 5 po sobě jdoucích dnů)",
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 1, 2),
        )
        keys = self._keys(accident)
        self.assertEqual(
            keys,
            {OBLIGATION_OO_OHLASENI, OBLIGATION_OIP_OBU_OHLASENI},
        )

    def test_fatal_accident_shows_full_obligations(self) -> None:
        accident = AccidentStub(druh_urazu="smrtelný")
        keys = self._keys(accident)
        self.assertIn(OBLIGATION_OO_OHLASENI, keys)
        self.assertIn(OBLIGATION_OIP_OBU_OHLASENI, keys)
        self.assertIn(OBLIGATION_POLICIE_OHLASENI, keys)
        self.assertIn(OBLIGATION_ZP_OHLASENI, keys)
        self.assertIn(OBLIGATION_EZOP, keys)
        self.assertIn(OBLIGATION_VYHOTOVENI_ZAZNAMU, keys)
        self.assertIn(OBLIGATION_OIP_OBU_ZASLANI, keys)
        self.assertIn(OBLIGATION_ZP_ZASLANI, keys)
        self.assertIn(OBLIGATION_POLICIE_ZASLANI, keys)

    def test_criminal_suspicion_adds_police_only(self) -> None:
        accident = AccidentStub(
            druh_urazu="pracovní úraz s pracovní neschopností nepřesahující 3 kalendářní dny",
            podezreni_trestny_cin="ANO",
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 1, 2),
        )
        keys = self._keys(accident)
        self.assertEqual(keys, {OBLIGATION_OO_OHLASENI, OBLIGATION_POLICIE_OHLASENI})

    def test_criminal_suspicion_with_pn_over_3_adds_police_to_sending(self) -> None:
        accident = AccidentStub(
            druh_urazu="pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            podezreni_trestny_cin="ANO",
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 1, 10),
        )
        keys = self._keys(accident)
        self.assertIn(OBLIGATION_POLICIE_OHLASENI, keys)
        self.assertIn(OBLIGATION_POLICIE_ZASLANI, keys)

    def test_legacy_row_names_are_recognized(self) -> None:
        accident = AccidentStub(
            druh_urazu="pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            dpn_od=date(2026, 1, 1),
            dpn_do=date(2026, 1, 10),
        )
        legacy_row = {"nazev": "Záznam o pracovním úrazu – Portál SÚIP"}
        from moduly.kniha_urazu.sluzby.accident_reporting_obligations import is_row_relevant

        self.assertTrue(is_row_relevant(accident, legacy_row))

    def test_kooperativa_is_never_relevant(self) -> None:
        accident = AccidentStub(druh_urazu="smrtelný")
        from moduly.kniha_urazu.sluzby.accident_reporting_obligations import is_row_relevant

        self.assertFalse(is_row_relevant(accident, {"nazev": "Kooperativa"}))

    def test_sections_are_assigned_correctly(self) -> None:
        accident = AccidentStub(druh_urazu="smrtelný")
        by_section = {}
        for item in applicable_obligations(accident):
            by_section.setdefault(item.section, []).append(item.key)

        self.assertIn(OBLIGATION_OO_OHLASENI, by_section[SECTION_OHLASENI])
        self.assertIn(OBLIGATION_VYHOTOVENI_ZAZNAMU, by_section[SECTION_ZAZNAM])
        self.assertIn(OBLIGATION_ZP_ZASLANI, by_section[SECTION_ODESLANI])

    def test_all_definitions_have_labels(self) -> None:
        self.assertEqual(len(OBLIGATION_LABELS), 9)


if __name__ == "__main__":
    unittest.main()
