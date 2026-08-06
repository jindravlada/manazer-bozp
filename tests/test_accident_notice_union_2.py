"""ACCIDENT-NOTICE-UNION-2: zpřehlednění výstupu ohlášení."""

from __future__ import annotations

import importlib
import os
import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.sluzby.union_notice_service import union_notice_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


class AccidentNoticeUnion2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _create_accident(self, **overrides):
        settings_service.save_employer(
            name="BOZP Firma s.r.o.",
            ico="12345678",
            address="Praha 1, Václavské náměstí 1",
            nace="",
            abbreviation="BOZP",
        )
        payload = {
            "jmeno_prijmeni": "Jan Novák",
            "pohlavi": "Muž",
            "datum_narozeni": date(1990, 5, 1),
            "statni_obcanstvi": "Česko",
            "adresa_pobytu": "Praha 5, Ulice 10",
            "vztah_k_zamestnavateli": "V pracovním poměru",
            "den_vzniku_pravniho_vztahu": date(2018, 1, 15),
            "druh_vykonavane_prace": "3115 – Technici",
            "druh_urazu": "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            "accident_date": date(2026, 3, 10),
            "accident_time": "09:30",
            "druh_zraneni": "010 – Zlomeniny",
            "zranena_cast_tela": "53 – Ruka",
            "hromadny_uraz": "Ne",
            "celkovy_pocet_zranenych": 1,
            "cinnost_pri_urazu": "Manipulace",
            "adresa_pracoviste": "Praha 9, Skladová 5",
            "misto_urazu": "Sklad B",
            "charakteristika_pracoviste": "Skladovací prostory",
            "popis_urazoveho_deje": "Při manipulaci spadl materiál na ruku.",
            "pricina_urazu": "Nesprávný postup",
            "zdroj_urazu": "Materiál",
            "zamestnavatel_nazev": "BOZP Firma s.r.o.",
            "zamestnavatel_ico": "12345678",
            "zamestnavatel_adresa": "Praha 1, Václavské náměstí 1",
            "podatel_jmeno": "Petr Podatel",
            "podatel_telefon": "777123456",
            "podatel_email": "podatel@firma.cz",
            "podatel_pracovni_zarazeni": "Specialista BOZP",
        }
        payload.update(overrides)
        return accident_service.create_accident(**payload)

    def test_section_iv_title(self) -> None:
        data = union_notice_service.build_from_accident(self._create_accident())
        html = union_notice_service.build_html(data, draft=False)
        self.assertIn("IV. Charakteristika pracoviště", html)
        self.assertNotIn("IV. Charakteristika místa", html)
        self.assertIn("<b>Charakteristika pracoviště</b>", html)

    def test_section_viii_without_place_bold_labels(self) -> None:
        data = union_notice_service.build_from_accident(self._create_accident())
        self.assertEqual(data.description, "Při manipulaci spadl materiál na ruku.")
        self.assertEqual(data.cause, "Nesprávný postup")
        self.assertEqual(data.source, "Materiál")
        self.assertNotIn("Místo:", data.description)

        html = union_notice_service.build_html(data, draft=False)
        self.assertIn("<b>Popis</b>", html)
        self.assertIn("<b>Příčina</b>", html)
        self.assertIn("<b>Zdroj</b>", html)
        self.assertNotIn(">Místo<", html)
        self.assertNotIn("<b>Místo</b>", html)
        # Pořadí Popis → Příčina → Zdroj
        popis = html.index("<b>Popis</b>")
        pricina = html.index("<b>Příčina</b>")
        zdroj = html.index("<b>Zdroj</b>")
        self.assertLess(popis, pricina)
        self.assertLess(pricina, zdroj)

    def test_death_date_row_only_for_fatal(self) -> None:
        nonfatal = union_notice_service.build_from_accident(self._create_accident())
        html_nf = union_notice_service.build_html(nonfatal, draft=False)
        self.assertNotIn("Datum úmrtí", html_nf)
        self.assertNotIn("není relevantní", html_nf)

        fatal = union_notice_service.build_from_accident(
            self._create_accident(druh_urazu="smrtelný")
        )
        fatal.death_date = "11.03.2026"
        html_f = union_notice_service.build_html(fatal, draft=False)
        self.assertIn("<b>Datum úmrtí</b>", html_f)
        self.assertIn("11.03.2026", html_f)
        self.assertEqual(len(re.findall(r"Datum úmrtí", html_f)), 1)


if __name__ == "__main__":
    unittest.main()
