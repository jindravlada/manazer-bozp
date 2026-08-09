"""OZO-SMLOUVY-5: validace překryvu smluv a lifecycle."""

from __future__ import annotations

import importlib
import os
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

    from moduly.smlouvy_ozo.constants import OVERLAP_MESSAGE, STATUS_EXPIRED
    from moduly.smlouvy_ozo.sluzby.ozo_contract_list_service import (
        ozo_contract_list_service,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_contract_service import (
        OzoContractValidationError,
        ozo_contract_service,
        validity_intervals_overlap,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_person_service import ozo_person_service
    from moduly.smlouvy_ozo.ui.ozo_contract_dialog import OzoContractDialog
    from moduly.smlouvy_ozo.ui.smlouvy_ozo_page import SmlouvyOzoPage


class OzoSmlouvy5TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.smlouvy_ozo.modely.ozo_contract import OzoContract
        from moduly.smlouvy_ozo.modely.ozo_person import OzoPerson

        with get_session() as session:
            session.execute(delete(OzoContract))
            session.execute(delete(OzoPerson))
            session.commit()

    def _create(self, **overrides):
        data = {
            "employer_name": "Objednatel",
            "ico": "12345678",
            "valid_from": date(2008, 1, 1),
            "valid_to": None,
            "indefinite": True,
            "active": True,
        }
        data.update(overrides)
        return ozo_contract_service.create(**data)

    def test_duplicate_indefinite_blocked(self) -> None:
        self._create()
        with self.assertRaises(OzoContractValidationError) as ctx:
            self._create(employer_name="Duplicita")
        self.assertEqual(str(ctx.exception), OVERLAP_MESSAGE)

    def test_definite_overlap_blocked(self) -> None:
        self._create(
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 12, 31),
            indefinite=False,
        )
        with self.assertRaises(OzoContractValidationError):
            self._create(
                employer_name="Překryv",
                valid_from=date(2026, 7, 1),
                valid_to=date(2027, 6, 30),
                indefinite=False,
            )

    def test_definite_plus_indefinite_overlap_blocked(self) -> None:
        self._create(
            valid_from=date(2020, 1, 1),
            valid_to=date(2030, 12, 31),
            indefinite=False,
        )
        with self.assertRaises(OzoContractValidationError):
            self._create(
                employer_name="Neurčitá přes určitou",
                valid_from=date(2025, 1, 1),
                indefinite=True,
            )

    def test_adjacent_intervals_allowed(self) -> None:
        first = self._create(
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 12, 31),
            indefinite=False,
        )
        second = self._create(
            employer_name="Navazující",
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 12, 31),
            indefinite=False,
        )
        self.assertNotEqual(first.id, second.id)
        self.assertFalse(
            validity_intervals_overlap(
                date(2025, 1, 1),
                date(2025, 12, 31),
                date(2026, 1, 1),
                date(2026, 12, 31),
            )
        )

    def test_different_ico_same_dates_allowed(self) -> None:
        self._create(ico="11111111")
        other = self._create(
            employer_name="Jiný objednatel",
            ico="22222222",
        )
        self.assertIsNotNone(other.id)

    def test_edit_self_does_not_overlap(self) -> None:
        contract = self._create(
            employer_name="Editovaná",
            valid_from=date(2024, 1, 1),
            valid_to=date(2024, 12, 31),
            indefinite=False,
        )
        updated = ozo_contract_service.update(
            contract.id,
            employer_name="Editovaná",
            ico="12345678",
            valid_from=date(2024, 1, 1),
            valid_to=date(2024, 12, 31),
            indefinite=False,
        )
        self.assertEqual(updated.id, contract.id)
        self.assertEqual(updated.employer_name, "Editovaná")

    def test_expired_status_without_deactivate(self) -> None:
        contract = self._create(
            valid_from=date(2020, 1, 1),
            valid_to=date(2020, 12, 31),
            indefinite=False,
        )
        self.assertTrue(contract.active)
        self.assertEqual(
            ozo_contract_service.status_for(contract, today=date(2021, 1, 1)),
            STATUS_EXPIRED,
        )

    def test_no_activate_deactivate_in_ui(self) -> None:
        page = SmlouvyOzoPage()
        self.assertFalse(hasattr(page, "activate_btn"))
        self.assertFalse(hasattr(page, "deactivate_btn"))
        dialog = OzoContractDialog()
        self.assertFalse(hasattr(dialog, "active_checkbox"))
        self.assertNotIn("active", dialog.get_data())
        dialog.close()
        page.close()

    def test_historical_list_keeps_partial_year_contract(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            certificate_number="CERT-5",
        )
        ongoing = self._create(
            employer_name="Od 2008",
            ico="55555555",
            valid_from=date(2008, 1, 1),
            indefinite=True,
        )
        partial = self._create(
            employer_name="Část 2026",
            ico="66666666",
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 9, 30),
            indefinite=False,
        )
        ended = self._create(
            employer_name="Konec 2025",
            ico="77777777",
            valid_from=date(2008, 1, 1),
            valid_to=date(2025, 12, 31),
            indefinite=False,
        )
        rows = ozo_contract_service.list_for_calendar_year(2026)
        ids = {item.id for item in rows}
        self.assertIn(ongoing.id, ids)
        self.assertIn(partial.id, ids)
        self.assertNotIn(ended.id, ids)
        html = ozo_contract_list_service.build_html(2026)
        self.assertIn("Od 2008", html)
        self.assertIn("Část 2026", html)
        self.assertNotIn("Konec 2025", html)


if __name__ == "__main__":
    unittest.main()
