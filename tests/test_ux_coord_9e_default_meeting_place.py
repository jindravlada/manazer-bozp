"""UX-COORD-9e – výchozí místo schůzky ze sídla společnosti."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete, text

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-9e-"))
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
        compose_company_seat_address,
        default_meeting_place_from_settings,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import (
        BozpCoordinationDialog,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class UxCoord9eDefaultMeetingPlaceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

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

    def test_compose_full_address(self) -> None:
        self.assertEqual(
            compose_company_seat_address(
                street="Průmyslová 123",
                postal_code="432 01",
                city="Kadaň",
            ),
            "Průmyslová 123, 432 01 Kadaň",
        )

    def test_compose_address_without_postal_code(self) -> None:
        self.assertEqual(
            compose_company_seat_address(
                street="Průmyslová 123",
                postal_code="",
                city="Kadaň",
            ),
            "Průmyslová 123, Kadaň",
        )
        self.assertEqual(
            compose_company_seat_address(street="", postal_code="", city=""),
            "",
        )
        self.assertEqual(
            compose_company_seat_address(
                street="  ",
                postal_code="432 01",
                city="",
            ),
            "432 01",
        )

    def test_new_coordination_takes_full_employer_address(self) -> None:
        address = "Průmyslová 123, 432 01 Kadaň"
        settings_service.save_employer(
            ico="12345678",
            name="Firma s.r.o.",
            address=address,
            nace="",
        )
        self.assertEqual(default_meeting_place_from_settings(), address)
        created = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9e plná adresa",
            meeting_date=date.today(),
        )
        self.assertEqual(created.place, address)

        dialog = BozpCoordinationDialog(None)
        self.assertEqual(dialog.place.text(), address)
        dialog.close()

    def test_empty_employer_address_leaves_place_empty(self) -> None:
        settings_service.save_employer(
            ico="12345678",
            name="Firma s.r.o.",
            address="",
            nace="",
        )
        self.assertEqual(default_meeting_place_from_settings(), "")
        created = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9e bez adresy",
            meeting_date=date.today(),
        )
        self.assertEqual(created.place, "")

        dialog = BozpCoordinationDialog(None)
        self.assertEqual(dialog.place.text(), "")
        dialog.close()

    def test_manual_place_not_overwritten(self) -> None:
        settings_service.save_employer(
            ico="12345678",
            name="Firma s.r.o.",
            address="Průmyslová 123, 432 01 Kadaň",
            nace="",
        )
        created = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9e ruční",
            meeting_date=date.today(),
            place="Jednací místnost A",
        )
        self.assertEqual(created.place, "Jednací místnost A")

        updated = bozp_coordination_service.update_coordination(
            created.id,
            meeting_date=created.meeting_date,
            place="Upravené místo",
            subject=created.subject,
            note="",
        )
        assert updated is not None
        self.assertEqual(updated.place, "Upravené místo")

        reloaded = bozp_coordination_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertEqual(reloaded.place, "Upravené místo")

        dialog = BozpCoordinationDialog(None, coordination=reloaded)
        self.assertEqual(dialog.place.text(), "Upravené místo")
        dialog.close()

        # Explicitní prázdné místo při vytvoření se nevyplní z nastavení.
        cleared = bozp_coordination_service.create_coordination(
            subject="UX-COORD-9e vymazáno",
            meeting_date=date.today(),
            place="",
        )
        self.assertEqual(cleared.place, "")

    def test_old_coordination_unchanged(self) -> None:
        settings_service.save_employer(
            ico="12345678",
            name="Firma s.r.o.",
            address="Průmyslová 123, 432 01 Kadaň",
            nace="",
        )
        with get_session() as session:
            session.execute(
                text(
                    """
                    INSERT INTO bozp_coordinations (
                        coordination_number, meeting_date, place, subject,
                        status, note, active, created_at, updated_at,
                        valid_from, valid_to
                    ) VALUES (
                        'LEGACY-9e', :meeting_date, 'Staré místo',
                        'Stará koordinace', 'draft', '', 1,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
                        :meeting_date, :meeting_date
                    )
                    """
                ),
                {"meeting_date": date.today().isoformat()},
            )
            session.commit()
            legacy_id = session.execute(
                text(
                    "SELECT id FROM bozp_coordinations "
                    "WHERE coordination_number = 'LEGACY-9e'"
                )
            ).scalar_one()

        legacy = bozp_coordination_service.get_by_id(legacy_id)
        assert legacy is not None
        self.assertEqual(legacy.place, "Staré místo")

        bozp_coordination_service.update_coordination(
            legacy_id,
            meeting_date=date.today(),
            place=legacy.place,
            subject=legacy.subject,
            note="",
            valid_from=date.today(),
            valid_to=date.today(),
        )
        reloaded = bozp_coordination_service.get_by_id(legacy_id)
        assert reloaded is not None
        self.assertEqual(reloaded.place, "Staré místo")


if __name__ == "__main__":
    unittest.main()
