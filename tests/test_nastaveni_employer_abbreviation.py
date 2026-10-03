"""Zkratka zaměstnavatele v nastavení – nepovinná, jedinečná, s auto fallbackem."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="employer-abbr-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
        default_abbreviation,
        employer_abbreviation,
    )
    from moduly.nastaveni.modely.employer import Employer
    from moduly.nastaveni.sluzby.settings_service import (
        SettingsEmployerError,
        settings_service,
    )


class EmployerAbbreviationSettingsTestCase(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.execute(delete(Employer))
            session.commit()

    def test_column_exists_without_rewriting_data(self) -> None:
        self.assertIn("abbreviation", _table_columns("employers"))
        settings_service.save_employer(
            ico="11111111",
            name="Firma bez zkratky",
            address="Praha",
            nace="",
        )
        employer = settings_service.get_employer()
        assert employer is not None
        self.assertEqual(employer.abbreviation, "")

    def test_manual_abbreviation_has_priority(self) -> None:
        settings_service.save_employer(
            ico="12345678",
            name="Hlavní firma s.r.o.",
            address="Praha 1",
            nace="",
            abbreviation="HLFIRMA",
        )
        employer = settings_service.get_employer()
        assert employer is not None
        self.assertEqual(employer.abbreviation, "HLFIRMA")

        coordination = bozp_coordination_service.create_coordination(
            subject="Ruční zkratka z nastavení",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.list_for_coordination(coordination.id)[0]
        self.assertEqual(main.abbreviation, "HLFIRMA")
        self.assertEqual(employer_abbreviation(main), "HLFIRMA")
        self.assertNotEqual(
            employer_abbreviation(main),
            default_abbreviation("Hlavní firma s.r.o."),
        )

    def test_settings_manual_abbreviation_beats_automatic(self) -> None:
        settings_service.save_employer(
            ico="00000000",
            name="ZX - Zkušební firma, a.s.",
            address="Praha",
            nace="",
            abbreviation="ZX-ZF",
        )
        coordination = bozp_coordination_service.create_coordination(
            subject="Zkratka ZX-ZF",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.list_for_coordination(coordination.id)[0]
        self.assertEqual(main.abbreviation, "ZX-ZF")
        self.assertEqual(employer_abbreviation(main), "ZX-ZF")
        # Automatika z názvu by dala „Z-ZF“ — to se nesmí použít.
        self.assertEqual(
            default_abbreviation("ZX - Zkušební firma, a.s."),
            "Z-ZF",
        )
        self.assertNotEqual(main.abbreviation, "Z-ZF")

    def test_settings_change_applies_to_new_only(self) -> None:
        settings_service.save_employer(
            ico="00000000",
            name="ZX - Zkušební firma, a.s.",
            address="Praha",
            nace="",
            abbreviation="ZX-ZF",
        )
        first = bozp_coordination_service.create_coordination(
            subject="První",
            meeting_date=date.today(),
        )
        first_main = coordination_employer_service.list_for_coordination(first.id)[0]
        self.assertEqual(first_main.abbreviation, "ZX-ZF")

        settings_service.save_employer(
            ico="00000000",
            name="ZX - Zkušební firma, a.s.",
            address="Praha",
            nace="",
            abbreviation="ZF",
        )
        second = bozp_coordination_service.create_coordination(
            subject="Druhá",
            meeting_date=date.today(),
        )
        second_main = coordination_employer_service.list_for_coordination(second.id)[0]
        self.assertEqual(second_main.abbreviation, "ZF")

        # Existující záznam zůstává beze změny.
        reloaded = coordination_employer_service.get_by_id(first_main.id)
        assert reloaded is not None
        self.assertEqual(reloaded.abbreviation, "ZX-ZF")

    def test_empty_abbreviation_uses_automatic(self) -> None:
        settings_service.save_employer(
            ico="12345678",
            name="Hlavní firma s.r.o.",
            address="Praha 1",
            nace="",
            abbreviation="",
        )
        employer = settings_service.get_employer()
        assert employer is not None
        self.assertEqual(employer.abbreviation, "")

        coordination = bozp_coordination_service.create_coordination(
            subject="Automatická zkratka",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.list_for_coordination(coordination.id)[0]
        self.assertEqual(main.abbreviation, "")
        self.assertEqual(
            employer_abbreviation(main),
            default_abbreviation("Hlavní firma s.r.o."),
        )

    def test_duplicate_abbreviation_rejected(self) -> None:
        settings_service.save_employer(
            ico="12345678",
            name="První firma",
            address="Praha",
            nace="",
            abbreviation="ABC",
        )
        first = settings_service.get_employer()
        assert first is not None

        with get_session() as session:
            second = Employer(
                ico="87654321",
                name="Druhá firma",
                address="Brno",
                nace="",
                abbreviation="",
                active=True,
            )
            session.add(second)
            session.commit()
            session.refresh(second)
            second_id = second.id

        with self.assertRaises(SettingsEmployerError):
            settings_service._validate_abbreviation(
                "ABC",
                exclude_employer_id=second_id,
            )

        # Stejný záznam může zkratku ponechat.
        settings_service.save_employer(
            ico=first.ico,
            name=first.name,
            address=first.address,
            nace=first.nace,
            abbreviation="ABC",
        )


if __name__ == "__main__":
    unittest.main()
