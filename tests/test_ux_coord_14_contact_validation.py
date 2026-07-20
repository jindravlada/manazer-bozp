"""UX-COORD-14 – validace důležitých kontaktů."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-14-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.koordinace_bozp.constants import CONTACT_TYPE_TECHNICAL
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
        CoordinationRiskSubmissionHistory,
    )
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
        CoordinationPbpRevision,
    )
    from moduly.koordinace_bozp.modely.coordination_workplace import (
        CoordinationWorkplace,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_contact_service import (
        CoordinationContactError,
        coordination_contact_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class UxCoord14ContactValidationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationRiskSubmissionHistory))
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationContact))
            session.execute(delete(CoordinationEmployerActivity))
            session.execute(delete(CoordinationMeasure))
            session.execute(delete(CoordinationWorkplace))
            session.execute(delete(CoordinationCoordinator))
            session.execute(delete(CoordinationParticipant))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.commit()

        settings_service.save_employer(
            ico="12345678",
            name="Hlavní firma s.r.o.",
            address="Praha",
            nace="",
        )

    def _setup(self):
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-14",
            meeting_date=date.today(),
        )
        employer = coordination_employer_service.ensure_main_employer(coordination.id)
        return coordination, employer

    def test_name_and_phone_ok(self) -> None:
        coordination, employer = self._setup()
        contact = coordination_contact_service.add(
            coordination.id,
            employer_id=employer.id,
            contact_type=CONTACT_TYPE_TECHNICAL,
            custom_name="Jan Novák",
            role="",
            phone="777 111 222",
        )
        self.assertEqual(contact.custom_name, "Jan Novák")
        self.assertEqual(contact.role, "")
        self.assertEqual(contact.phone, "777 111 222")

    def test_role_and_phone_ok(self) -> None:
        coordination, employer = self._setup()
        contact = coordination_contact_service.add(
            coordination.id,
            employer_id=employer.id,
            custom_name="",
            role="Hradlař T1",
            phone="777 111 222",
        )
        self.assertEqual(contact.custom_name, "")
        self.assertEqual(contact.role, "Hradlař T1")
        self.assertEqual(contact.phone, "777 111 222")

    def test_name_role_and_phone_ok(self) -> None:
        coordination, employer = self._setup()
        contact = coordination_contact_service.add(
            coordination.id,
            employer_id=employer.id,
            custom_name="Jan Novák",
            role="Hradlař T1",
            phone="777 111 222",
        )
        self.assertEqual(contact.custom_name, "Jan Novák")
        self.assertEqual(contact.role, "Hradlař T1")

    def test_without_name_and_role_fails(self) -> None:
        coordination, employer = self._setup()
        with self.assertRaises(CoordinationContactError) as ctx:
            coordination_contact_service.add(
                coordination.id,
                employer_id=employer.id,
                custom_name="",
                role="",
                phone="777 111 222",
            )
        self.assertIn("jméno", str(ctx.exception).casefold())
        self.assertIn("funkci", str(ctx.exception).casefold())

    def test_without_phone_fails(self) -> None:
        coordination, employer = self._setup()
        with self.assertRaises(CoordinationContactError) as ctx:
            coordination_contact_service.add(
                coordination.id,
                employer_id=employer.id,
                custom_name="Jan Novák",
                phone="",
                email="jan@example.com",
            )
        self.assertEqual(str(ctx.exception), "Telefon je povinný.")

    def test_email_optional(self) -> None:
        coordination, employer = self._setup()
        contact = coordination_contact_service.add(
            coordination.id,
            employer_id=employer.id,
            custom_name="Jan Novák",
            phone="777 111 222",
            email="",
        )
        self.assertEqual(contact.email, "")

    def test_note_optional(self) -> None:
        coordination, employer = self._setup()
        contact = coordination_contact_service.add(
            coordination.id,
            employer_id=employer.id,
            role="Dispečer",
            phone="777 111 222",
            note="",
        )
        self.assertEqual(contact.note, "")


if __name__ == "__main__":
    unittest.main()
