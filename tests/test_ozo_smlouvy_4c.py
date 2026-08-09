"""OZO-SMLOUVY-4c: oprava ročního seznamu trvajících smluv."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

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

    from moduly.smlouvy_ozo.sluzby.ozo_contract_list_service import (
        ozo_contract_list_service,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_contract_service import (
        covers_calendar_year,
        ozo_contract_service,
    )
    from moduly.smlouvy_ozo.sluzby.ozo_person_service import ozo_person_service


class OzoSmlouvy4cTestCase(unittest.TestCase):
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
            "valid_from": date(2008, 1, 1),
            "valid_to": None,
            "indefinite": True,
            "active": True,
        }
        data.update(overrides)
        return ozo_contract_service.create(**data)

    def test_2008_indefinite_in_2026(self) -> None:
        contract = self._create(
            employer_name="Trvající od 2008",
            valid_from=date(2008, 3, 1),
            indefinite=True,
        )
        self.assertTrue(covers_calendar_year(contract, 2026))
        ids = {item.id for item in ozo_contract_service.list_for_calendar_year(2026)}
        self.assertIn(contract.id, ids)

    def test_ended_2025_not_in_2026(self) -> None:
        contract = self._create(
            employer_name="Konec 2025",
            valid_from=date(2008, 1, 1),
            indefinite=False,
            valid_to=date(2025, 12, 31),
        )
        self.assertFalse(covers_calendar_year(contract, 2026))
        ids = {item.id for item in ozo_contract_service.list_for_calendar_year(2026)}
        self.assertNotIn(contract.id, ids)

    def test_ends_mid_2026_in_2026(self) -> None:
        contract = self._create(
            employer_name="Konec březen 2026",
            valid_from=date(2008, 1, 1),
            indefinite=False,
            valid_to=date(2026, 3, 15),
        )
        self.assertTrue(covers_calendar_year(contract, 2026))
        self.assertIn(
            contract.id,
            {item.id for item in ozo_contract_service.list_for_calendar_year(2026)},
        )

    def test_starts_mid_2026_indefinite_in_2026(self) -> None:
        contract = self._create(
            employer_name="Od července 2026",
            valid_from=date(2026, 7, 1),
            indefinite=True,
        )
        self.assertTrue(covers_calendar_year(contract, 2026))
        self.assertFalse(covers_calendar_year(contract, 2025))

    def test_starts_2027_not_in_2026(self) -> None:
        contract = self._create(
            employer_name="Od 2027",
            valid_from=date(2027, 1, 1),
            indefinite=True,
        )
        self.assertFalse(covers_calendar_year(contract, 2026))
        self.assertNotIn(
            contract.id,
            {item.id for item in ozo_contract_service.list_for_calendar_year(2026)},
        )

    def test_deactivation_keeps_contract_in_year_list(self) -> None:
        contract = self._create(
            employer_name="Deaktivovaná trvající",
            valid_from=date(2008, 6, 1),
            indefinite=True,
        )
        ozo_contract_service.deactivate(contract.id)
        reloaded = ozo_contract_service.get_by_id(contract.id)
        self.assertIsNotNone(reloaded)
        self.assertFalse(reloaded.active)
        self.assertIn(
            contract.id,
            {item.id for item in ozo_contract_service.list_for_calendar_year(2026)},
        )

    def test_chronological_order_by_relation_date(self) -> None:
        self._create(
            employer_name="Pozdější",
            signed_on=date(2010, 5, 1),
            valid_from=date(2010, 5, 1),
            indefinite=True,
        )
        self._create(
            employer_name="Dřívější",
            signed_on=None,
            valid_from=date(2008, 1, 1),
            indefinite=True,
        )
        names = [
            item.employer_name
            for item in ozo_contract_service.list_for_calendar_year(2026)
        ]
        self.assertEqual(names, ["Dřívější", "Pozdější"])

    def test_list_html_includes_ongoing_2008_contract(self) -> None:
        ozo_person_service.save(
            first_name="Jan",
            last_name="Novák",
            certificate_number="CERT-2008",
        )
        self._create(
            employer_name="Firma 2008",
            valid_from=date(2008, 1, 15),
            indefinite=True,
        )
        html = ozo_contract_list_service.build_html(2026)
        self.assertIn("Firma 2008", html)
        self.assertIn("Jan Novák", html)
