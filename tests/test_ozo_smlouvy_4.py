"""OZO-SMLOUVY-4: zákonné údaje OZO a chronologický seznam smluv."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMessageBox

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

    from moduly.smlouvy_ozo.constants import (
        ACTION_CHRONOLOGICAL_LIST,
        ACTION_OZO_PERSON,
        COL_EMPLOYER,
        YEAR_FILTER_ALL,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_contract_list_service import (
        ozo_contract_list_service,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_contract_service import (
        ozo_contract_service,
        relation_date,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_person_service import ozo_person_service
    from moduly.smlouvy_ozo.ui.smlouvy_ozo_page import SmlouvyOzoPage


class OzoSmlouvy4TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.smlouvy_ozo.modely.ozo_contract import OzoContract
        from moduly.smlouvy_ozo.modely.ozo_person import OzoPerson

        self._ico_seq = 0
        with get_session() as session:
            session.execute(delete(OzoContract))
            session.execute(delete(OzoPerson))
            session.commit()

    def _next_ico(self) -> str:
        self._ico_seq += 1
        return f"{self._ico_seq:08d}"

    def _create(self, **overrides):
        data = {
            "employer_name": "Objednatel A",
            "ico": self._next_ico(),
            "valid_from": date(2030, 3, 1),
            "valid_to": date(2030, 12, 31),
            "indefinite": False,
            "active": True,
        }
        data.update(overrides)
        return ozo_contract_service.create(**data)

    def test_save_ozo_person(self) -> None:
        person = ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            residence_address="Praha 1",
            exam_date=date(2024, 5, 10),
            certificate_number="OZO-123",
            certificate_valid_to=date(2029, 5, 10),
        )
        reloaded = ozo_person_service.get()
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.id, person.id)
        self.assertEqual(reloaded.first_name, "Jan")
        self.assertEqual(reloaded.last_name, "Novák")
        self.assertEqual(reloaded.certificate_number, "OZO-123")
        self.assertEqual(ozo_person_service.full_name(), "Jan Novák")

    def test_relation_date_prefers_signed_on(self) -> None:
        contract = self._create(
            signed_on=date(2030, 2, 15),
            valid_from=date(2030, 3, 1),
        )
        self.assertEqual(relation_date(contract), date(2030, 2, 15))
        without_signed = self._create(
            employer_name="Bez podpisu",
            signed_on=None,
            valid_from=date(2030, 4, 1),
        )
        self.assertEqual(relation_date(without_signed), date(2030, 4, 1))

    def test_year_list_chronological_includes_inactive(self) -> None:
        early = self._create(
            employer_name="Brzy",
            signed_on=date(2030, 1, 10),
            valid_from=date(2030, 1, 10),
        )
        late = self._create(
            employer_name="Pozdě",
            signed_on=date(2030, 8, 20),
            valid_from=date(2030, 8, 20),
        )
        mid = self._create(
            employer_name="Uprostřed",
            signed_on=None,
            valid_from=date(2030, 5, 1),
        )
        ozo_contract_service.deactivate(early.id)

        rows = ozo_contract_service.list_for_calendar_year(2030)
        names = [item.employer_name for item in rows]
        self.assertEqual(names, ["Brzy", "Uprostřed", "Pozdě"])
        reloaded_early = ozo_contract_service.get_by_id(early.id)
        self.assertIsNotNone(reloaded_early)
        self.assertFalse(reloaded_early.active)
        self.assertIn(early.id, {item.id for item in rows})
        self.assertNotIn(
            late.id,
            {item.id for item in ozo_contract_service.list_for_calendar_year(2029)},
        )
        self.assertIn(mid.id, {item.id for item in rows})

    def test_page_year_filter_shows_history(self) -> None:
        active = self._create(employer_name="Aktivní 2030", signed_on=date(2030, 6, 1))
        inactive = self._create(
            employer_name="Historická 2030",
            signed_on=date(2030, 2, 1),
        )
        ozo_contract_service.deactivate(inactive.id)
        other_year = self._create(
            employer_name="Jiný rok",
            signed_on=date(2031, 1, 5),
            valid_from=date(2031, 1, 5),
            valid_to=date(2031, 12, 31),
        )

        page = SmlouvyOzoPage()
        index = page.year_filter.findData(2030)
        self.assertGreaterEqual(index, 0)
        page.year_filter.setCurrentIndex(index)
        names = [
            page.table.item(row, COL_EMPLOYER).text()
            for row in range(page.table.rowCount())
        ]
        self.assertEqual(names, ["Historická 2030", "Aktivní 2030"])
        self.assertNotIn("Jiný rok", names)
        self.assertEqual(page.ozo_person_btn.text(), ACTION_OZO_PERSON)
        self.assertEqual(page.list_btn.text(), ACTION_CHRONOLOGICAL_LIST)
        page.close()
        self.assertTrue(ozo_contract_service.get_by_id(active.id).active)
        self.assertFalse(ozo_contract_service.get_by_id(inactive.id).active)
        self.assertTrue(ozo_contract_service.get_by_id(other_year.id).active)

    def test_list_output_requires_ozo_fields(self) -> None:
        self.assertEqual(
            ozo_contract_list_service.missing_ozo_fields(),
            ["Jméno", "Příjmení", "Číslo osvědčení"],
        )
        ozo_person_service.save(
            first_name="Eva",
            last_name="Svobodová",
            certificate_number="CERT-9",
        )
        self.assertEqual(ozo_contract_list_service.missing_ozo_fields(), [])

    def test_list_html_contains_ozo_and_contracts(self) -> None:
        ozo_person_service.save(
            first_name="Petr",
            last_name="Dvořák",
            certificate_number="OZO-77",
        )
        self._create(
            employer_name="Firma Chrono",
            ico="22222222",
            contract_number="S-9",
            signed_on=date(2030, 3, 12),
            valid_from=date(2030, 3, 12),
        )
        html = ozo_contract_list_service.build_html(2030)
        self.assertIn("2030", html)
        self.assertIn("Petr Dvořák", html)
        self.assertIn("OZO-77", html)
        self.assertIn("Firma Chrono", html)
        self.assertIn("12.03.2030", html)
        self.assertIn("S-9", html)
        self.assertIn("§ 10 odst. 4 písm. a)", html)

    def test_open_list_warns_when_year_all(self) -> None:
        page = SmlouvyOzoPage()
        all_index = page.year_filter.findData(None)
        page.year_filter.setCurrentIndex(all_index)
        self.assertEqual(page.year_filter.currentText(), YEAR_FILTER_ALL)
        with patch.object(QMessageBox, "warning") as warning:
            page.open_chronological_list()
        warning.assert_called_once()
        page.close()

    def test_open_list_warns_when_ozo_missing(self) -> None:
        page = SmlouvyOzoPage()
        index = page.year_filter.findData(date.today().year)
        if index < 0:
            page.year_filter.setCurrentIndex(0)
        else:
            page.year_filter.setCurrentIndex(index)
        with patch.object(QMessageBox, "warning") as warning:
            page.open_chronological_list()
        warning.assert_called_once()
        args = warning.call_args[0]
        self.assertIn("Jméno", args[2])
        page.close()


if __name__ == "__main__":
    unittest.main()
