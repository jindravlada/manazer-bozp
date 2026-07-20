"""Fáze COORD-010 – kontakty a postupy při mimořádných událostech."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="coord-010-"))
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
    from moduly.koordinace_bozp.constants import (
        CONTACT_TYPE_EMERGENCY,
        CONTACT_TYPE_FIRE,
        DEFAULT_ACCIDENT_REPORTING,
        DEFAULT_EMERGENCY_REPORTING,
        DEFAULT_EVACUATION_INSTRUCTIONS,
        DEFAULT_FIRE_REPORTING,
        TAB_CONTACTS,
    )
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
    from moduly.koordinace_bozp.sluzby.coordination_participant_service import (
        coordination_participant_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.nastaveni.sluzby.settings_service import settings_service


class KoordinaceBozpPhaseCoord010TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
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

    def _create_coordination(self, **kwargs):
        return bozp_coordination_service.create_coordination(
            subject="COORD-010",
            meeting_date=date.today(),
            **kwargs,
        )

    def _create_participant(self, coordination_id: int, **kwargs):
        employer = coordination_employer_service.ensure_main_employer(coordination_id)
        return coordination_participant_service.add_manual(
            employer.id,
            full_name=kwargs.get("full_name", "Jan Novák"),
            role=kwargs.get("role", "stavbyvedoucí"),
            phone=kwargs.get("phone", "+420111222333"),
            email=kwargs.get("email", "jan@example.com"),
            note=kwargs.get("note", ""),
        )

    def _main_employer_id(self, coordination_id: int) -> int:
        return coordination_employer_service.ensure_main_employer(coordination_id).id

    def test_model_and_columns(self) -> None:
        contact_columns = _table_columns("coordination_contacts")
        for name in (
            "id",
            "coordination_id",
            "participant_id",
            "employer_id",
            "contact_type",
            "custom_name",
            "employer_name",
            "role",
            "phone",
            "email",
            "note",
            "active",
            "sort_order",
        ):
            self.assertIn(name, contact_columns)
        coordination_columns = _table_columns("bozp_coordinations")
        for name in (
            "emergency_reporting",
            "accident_reporting",
            "fire_reporting",
            "evacuation_instructions",
        ):
            self.assertIn(name, coordination_columns)

    def test_contact_from_participant(self) -> None:
        coordination = self._create_coordination()
        participant = self._create_participant(coordination.id)
        snapshot = coordination_contact_service.snapshot_from_participant(participant.id)
        contact = coordination_contact_service.add(
            coordination.id,
            contact_type=CONTACT_TYPE_EMERGENCY,
            participant_id=participant.id,
            employer_id=snapshot["employer_id"],
            **{k: snapshot[k] for k in ("custom_name", "role", "phone", "email")},
        )
        self.assertEqual(contact.participant_id, participant.id)
        self.assertEqual(contact.employer_id, snapshot["employer_id"])
        self.assertEqual(contact.custom_name, "Jan Novák")
        self.assertEqual(contact.phone, "+420111222333")

    def test_manual_contact(self) -> None:
        coordination = self._create_coordination()
        employer_id = self._main_employer_id(coordination.id)
        contact = coordination_contact_service.add(
            coordination.id,
            contact_type=CONTACT_TYPE_FIRE,
            employer_id=employer_id,
            custom_name="Petr Hasič",
            role="ohlašovna",
            phone="+420999888777",
            email="",
        )
        self.assertIsNone(contact.participant_id)
        self.assertEqual(contact.employer_id, employer_id)
        self.assertEqual(contact.custom_name, "Petr Hasič")
        self.assertEqual(contact.contact_type, CONTACT_TYPE_FIRE)

    def test_snapshot_independent_of_participant_change(self) -> None:
        coordination = self._create_coordination()
        participant = self._create_participant(
            coordination.id,
            full_name="Původní Jméno",
            phone="+420100200300",
            email="puvodni@example.com",
        )
        snapshot = coordination_contact_service.snapshot_from_participant(participant.id)
        contact = coordination_contact_service.add(
            coordination.id,
            participant_id=participant.id,
            employer_id=snapshot["employer_id"],
            **{k: snapshot[k] for k in ("custom_name", "role", "phone", "email")},
        )
        coordination_participant_service.update_participant(
            participant.id,
            full_name="Nové Jméno",
            role="jiná role",
            phone="+420000000000",
            email="nove@example.com",
            note="",
        )
        reloaded = coordination_contact_service.get_by_id(contact.id)
        self.assertEqual(reloaded.custom_name, "Původní Jméno")
        self.assertEqual(reloaded.phone, "+420100200300")
        self.assertEqual(reloaded.email, "puvodni@example.com")

    def test_require_phone_and_name_or_role(self) -> None:
        coordination = self._create_coordination()
        employer_id = self._main_employer_id(coordination.id)
        with self.assertRaises(CoordinationContactError) as ctx:
            coordination_contact_service.add(
                coordination.id,
                employer_id=employer_id,
                custom_name="Bez telefonu",
                phone="",
                email="a@b.cz",
            )
        self.assertIn("telefon", str(ctx.exception).casefold())
        with self.assertRaises(CoordinationContactError) as identity_ctx:
            coordination_contact_service.add(
                coordination.id,
                employer_id=employer_id,
                custom_name="",
                role="",
                phone="+420111",
            )
        self.assertIn("jméno", str(identity_ctx.exception).casefold())
        with self.assertRaises(CoordinationContactError) as employer_ctx:
            coordination_contact_service.add(
                coordination.id,
                custom_name="Bez zaměstnavatele",
                phone="+420111",
            )
        self.assertIn("zaměstnavatel", str(employer_ctx.exception).casefold())
        # UX-COORD-14: stačí funkce + telefon (bez jména).
        role_only = coordination_contact_service.add(
            coordination.id,
            employer_id=employer_id,
            custom_name="",
            role="Hradlař T1",
            phone="+420111",
        )
        self.assertEqual(role_only.role, "Hradlař T1")
        self.assertEqual(role_only.custom_name, "")

    def test_reject_inactive_participant_selection(self) -> None:
        coordination = self._create_coordination()
        participant = self._create_participant(coordination.id)
        employer_id = self._main_employer_id(coordination.id)
        coordination_participant_service.deactivate(participant.id)
        with self.assertRaises(CoordinationContactError) as ctx:
            coordination_contact_service.add(
                coordination.id,
                participant_id=participant.id,
                employer_id=employer_id,
                custom_name="Jan Novák",
                phone="+420111222333",
            )
        self.assertIn("deaktivovaného", str(ctx.exception).casefold())

    def test_keep_contact_after_participant_deactivate(self) -> None:
        coordination = self._create_coordination()
        participant = self._create_participant(coordination.id)
        snapshot = coordination_contact_service.snapshot_from_participant(participant.id)
        contact = coordination_contact_service.add(
            coordination.id,
            participant_id=participant.id,
            employer_id=snapshot["employer_id"],
            **{k: snapshot[k] for k in ("custom_name", "role", "phone", "email")},
        )
        coordination_participant_service.deactivate(participant.id)
        reloaded = coordination_contact_service.get_by_id(contact.id)
        self.assertIsNotNone(reloaded)
        self.assertTrue(reloaded.active)
        self.assertEqual(reloaded.custom_name, "Jan Novák")
        # update stále možné se stejným participant_id
        updated = coordination_contact_service.update(
            contact.id,
            contact_type=CONTACT_TYPE_EMERGENCY,
            participant_id=participant.id,
            employer_id=contact.employer_id,
            custom_name="Jan Novák",
            role="stavbyvedoucí",
            phone="+420111222333",
            email="jan@example.com",
        )
        self.assertEqual(updated.participant_id, participant.id)

    def test_move_order(self) -> None:
        coordination = self._create_coordination()
        employer_id = self._main_employer_id(coordination.id)
        first = coordination_contact_service.add(
            coordination.id,
            employer_id=employer_id,
            custom_name="A",
            phone="1",
        )
        second = coordination_contact_service.add(
            coordination.id,
            employer_id=employer_id,
            custom_name="B",
            phone="2",
        )
        self.assertTrue(coordination_contact_service.move_up(second.id))
        names = [
            item.custom_name
            for item in coordination_contact_service.list_for_coordination(
                coordination.id
            )
        ]
        self.assertEqual(names, ["B", "A"])
        self.assertFalse(coordination_contact_service.move_up(second.id))
        self.assertEqual(first.id, first.id)

    def test_deactivate_reactivate(self) -> None:
        coordination = self._create_coordination()
        contact = coordination_contact_service.add(
            coordination.id,
            employer_id=self._main_employer_id(coordination.id),
            custom_name="Kontakt",
            phone="+420111222333",
            email="a@b.cz",
        )
        self.assertTrue(coordination_contact_service.deactivate(contact.id))
        self.assertFalse(coordination_contact_service.get_by_id(contact.id).active)
        self.assertTrue(coordination_contact_service.activate(contact.id))
        self.assertTrue(coordination_contact_service.get_by_id(contact.id).active)

    def test_default_procedures_prefilled(self) -> None:
        coordination = self._create_coordination()
        self.assertEqual(coordination.emergency_reporting, DEFAULT_EMERGENCY_REPORTING)
        self.assertEqual(coordination.accident_reporting, DEFAULT_ACCIDENT_REPORTING)
        self.assertEqual(coordination.fire_reporting, DEFAULT_FIRE_REPORTING)
        self.assertEqual(
            coordination.evacuation_instructions,
            DEFAULT_EVACUATION_INSTRUCTIONS,
        )

    def test_update_procedures(self) -> None:
        coordination = self._create_coordination()
        updated = bozp_coordination_service.update_coordination(
            coordination.id,
            meeting_date=coordination.meeting_date,
            place=coordination.place or "",
            subject=coordination.subject,
            status=coordination.status,
            note=coordination.note or "",
            valid_from=coordination.valid_from,
            valid_to=coordination.valid_to,
            emergency_reporting="Upravený postup MU.",
            accident_reporting="Upravený postup úrazu.",
            fire_reporting="Upravený postup požáru.",
            evacuation_instructions="Upravená evakuace.",
        )
        self.assertEqual(updated.emergency_reporting, "Upravený postup MU.")
        self.assertEqual(updated.accident_reporting, "Upravený postup úrazu.")
        self.assertEqual(updated.fire_reporting, "Upravený postup požáru.")
        self.assertEqual(updated.evacuation_instructions, "Upravená evakuace.")

    def test_ui_tab(self) -> None:
        coordination = self._create_coordination()
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        labels = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertIn(TAB_CONTACTS, labels)
        self.assertFalse(dialog.contacts_tab.content.isHidden())
        dialog.contacts_tab.refresh()
        self.assertIn(
            "mimořádnou událost",
            dialog.contacts_tab.emergency_reporting.toPlainText().casefold(),
        )
        data = dialog.get_data()
        self.assertIn("emergency_reporting", data)
        self.assertEqual(data["emergency_reporting"], DEFAULT_EMERGENCY_REPORTING)


if __name__ == "__main__":
    unittest.main()
