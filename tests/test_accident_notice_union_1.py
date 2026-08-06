"""ACCIDENT-NOTICE-UNION-1: ohlášení pracovního úrazu odborové organizaci."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QToolButton

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
    from moduly.kniha_urazu.sluzby.union_notice_service import (
        ACTION_PDF,
        ACTION_PREVIEW,
        DOCUMENT_SUBTITLE,
        DOCUMENT_TITLE,
        MISSING_MARKER,
        RELATION_EMPLOYMENT,
        union_notice_service,
    )
    from moduly.kniha_urazu.ui.accident_dialog import AccidentDialog
    from moduly.kniha_urazu.ui.union_notice_dialog import UnionNoticeDialog
    from moduly.nastaveni.sluzby.settings_service import settings_service


class AccidentNoticeUnion1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _create_full_accident(self, **overrides):
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
            "adresa_dorucovani": "",
            "vztah_k_zamestnavateli": "V pracovním poměru",
            "den_vzniku_pravniho_vztahu": date(2018, 1, 15),
            "druh_vykonavane_prace": "3115 – Technici v chemickém průmyslu",
            "cz_isco_kod": "3115",
            "cz_isco_nazev": "Technici v chemickém průmyslu",
            "druh_urazu": "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny",
            "accident_date": date(2026, 3, 10),
            "accident_time": "09:30",
            "druh_zraneni": "010 – Zlomeniny",
            "zranena_cast_tela": "53 – Ruka",
            "hromadny_uraz": "Ne",
            "celkovy_pocet_zranenych": 1,
            "cinnost_pri_urazu": "Manipulace s materiálem",
            "misto_urazu": "Sklad B",
            "adresa_pracoviste": "Praha 9, Skladová 5",
            "charakteristika_pracoviste": "Skladovací prostory",
            "popis_urazoveho_deje": "Při manipulaci spadl materiál na ruku.",
            "pricina_urazu": "Nesprávný postup",
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

    def test_union_notice_dialog_opens_for_saved_accident(self) -> None:
        accident = self._create_full_accident()
        notice = UnionNoticeDialog(None, accident=accident)
        self.assertIn(DOCUMENT_TITLE, notice.windowTitle())
        self.assertIn(DOCUMENT_SUBTITLE, notice.windowTitle())

    def test_editor_has_no_notice_button(self) -> None:
        accident = self._create_full_accident()
        dialog = AccidentDialog(accident=accident)
        self.assertFalse(hasattr(dialog, "notice_btn"))
        texts = [btn.text() for btn in dialog.findChildren(QToolButton)]
        self.assertNotIn("Ohlášení", texts)

    def test_prefill_employer_employee_injury(self) -> None:
        accident = self._create_full_accident()
        data = union_notice_service.build_from_accident(accident)
        self.assertEqual(data.employer_name, "BOZP Firma s.r.o.")
        self.assertEqual(data.employer_ico, "12345678")
        self.assertIn("Václavské", data.employer_address)
        self.assertEqual(data.employee_name, "Jan Novák")
        self.assertEqual(data.employee_gender, "Muž")
        self.assertEqual(data.employee_relation, RELATION_EMPLOYMENT)
        self.assertEqual(data.employee_relation_start, "15.01.2018")
        self.assertIn("Skladová", data.accident_place_address)
        self.assertEqual(data.workplace_characteristic, "Skladovací prostory")
        self.assertEqual(data.activity, "Manipulace s materiálem")
        self.assertIn("3115", data.cz_isco)
        self.assertEqual(data.injury_type, "010 – Zlomeniny")
        self.assertEqual(data.body_part, "53 – Ruka")
        self.assertEqual(data.accident_date, "10.03.2026")
        self.assertEqual(data.accident_time, "09:30")
        self.assertEqual(data.mass_accident, "Ne")
        self.assertEqual(data.notifier_name, "Petr Podatel")
        self.assertEqual(data.notifier_email, "podatel@firma.cz")

    def test_fatal_and_mass_accident(self) -> None:
        fatal = self._create_full_accident(
            druh_urazu="smrtelný",
            hromadny_uraz="Ano",
            celkovy_pocet_zranenych=3,
        )
        data = union_notice_service.build_from_accident(fatal)
        self.assertTrue(data.is_fatal)
        self.assertEqual(data.mass_accident, "Ano")
        self.assertEqual(data.injured_count, "3")
        missing = union_notice_service.required_missing(data)
        keys = {item.key for item in missing}
        self.assertIn("death_date", keys)

        nonfatal = self._create_full_accident()
        data2 = union_notice_service.build_from_accident(nonfatal)
        self.assertFalse(data2.is_fatal)
        na_keys = {
            item.key
            for item in union_notice_service.validate(data2)
            if item.kind == "not_relevant"
        }
        self.assertIn("death_date", na_keys)

    def test_missing_checklist_and_draft_preview(self) -> None:
        accident = self._create_full_accident(jmeno_prijmeni="", popis_urazoveho_deje="")
        data = union_notice_service.build_from_accident(accident)
        required = union_notice_service.required_missing(data)
        self.assertTrue(any(item.key == "employee_name" for item in required))

        html = union_notice_service.build_html(data, draft=True)
        self.assertIn(MISSING_MARKER, html)
        self.assertIn(DOCUMENT_TITLE, html)
        self.assertIn("I. Údaje o zaměstnavateli", html)
        self.assertIn("IX. Osoba oznamující", html)

        filled = union_notice_service.build_from_accident(self._create_full_accident())
        # Doplnit vše, co může chybět (telefon bez @).
        filled.notifier_phone = "777000111"
        filled.notifier_email = "a@b.cz"
        final_html = union_notice_service.build_html(filled, draft=False)
        self.assertNotIn(MISSING_MARKER, final_html)

    def test_one_off_edit_does_not_change_accident(self) -> None:
        accident = self._create_full_accident()
        original_name = accident.jmeno_prijmeni
        original_place = accident.adresa_pracoviste
        dialog = UnionNoticeDialog(accident=accident)
        dialog.employee_name.setText("Dočasná Změna")
        dialog.accident_place_address.setPlainText("Jiná adresa 99")
        edited = dialog.get_data()
        self.assertEqual(edited.employee_name, "Dočasná Změna")

        reloaded = accident_service.get_by_id(accident.id)
        assert reloaded is not None
        self.assertEqual(reloaded.jmeno_prijmeni, original_name)
        self.assertEqual(reloaded.adresa_pracoviste, original_place)

    def test_history_and_pdf(self) -> None:
        accident = self._create_full_accident()
        data = union_notice_service.build_from_accident(accident)
        entry = union_notice_service.record_history(
            accident.id,
            action=ACTION_PREVIEW,
            notifier_name=data.notifier_name,
        )
        self.assertEqual(entry["action"], ACTION_PREVIEW)
        self.assertEqual(entry["notifier"], "Petr Podatel")

        history = union_notice_service.get_history(accident.id)
        self.assertEqual(len(history), 1)

        html = union_notice_service.build_html(data, draft=False)
        pdf_path = Path(tempfile.mkdtemp()) / "ohlaseni.pdf"
        written = union_notice_service.write_pdf(html, pdf_path)
        self.assertTrue(written.exists())
        self.assertGreater(written.stat().st_size, 100)

        union_notice_service.record_history(
            accident.id,
            action=ACTION_PDF,
            notifier_name=data.notifier_name,
        )
        history2 = union_notice_service.get_history(accident.id)
        self.assertEqual(len(history2), 2)
        self.assertEqual(history2[-1]["action"], ACTION_PDF)

    def test_new_accident_editor_has_no_notice(self) -> None:
        dialog = AccidentDialog()
        self.assertFalse(hasattr(dialog, "notice_btn"))


if __name__ == "__main__":
    unittest.main()
