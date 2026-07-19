"""UX-COORD-2 – ručně zadaný koordinátor BOZP."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-2-"))
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
    from moduly.koordinace_bozp.sluzby.coordination_coordinator_service import (
        CoordinationCoordinatorError,
        coordination_coordinator_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_participant_service import (
        coordination_participant_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
        coordination_protocol_builder,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
        coordination_protocol_odt_renderer,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.nastaveni.sluzby.settings_service import settings_service


class UxCoord2ManualCoordinatorTestCase(unittest.TestCase):
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

    def _setup(self):
        coordination = bozp_coordination_service.create_coordination(
            subject="UX-COORD-2",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        participant = coordination_participant_service.add_manual(
            main.id,
            full_name="Jan Účastník",
            role="technik",
            phone="+420111",
            email="jan@example.com",
        )
        return coordination, main, participant

    def test_snapshot_columns_exist(self) -> None:
        columns = _table_columns("coordination_coordinators")
        for name in ("full_name", "employer_name", "role", "phone", "email"):
            self.assertIn(name, columns)

    def test_coordinator_from_participant(self) -> None:
        coordination, main, participant = self._setup()
        saved = coordination_coordinator_service.set_coordinator(
            coordination.id,
            employer_id=main.id,
            participant_id=participant.id,
            note="z účastníků",
        )
        self.assertEqual(saved.participant_id, participant.id)
        self.assertEqual(saved.employer_id, main.id)
        self.assertEqual(saved.full_name, "Jan Účastník")
        self.assertEqual(saved.role, "technik")
        self.assertEqual(saved.phone, "+420111")
        self.assertEqual(saved.email, "jan@example.com")
        self.assertEqual(saved.employer_name, "Hlavní firma s.r.o.")
        self.assertEqual(saved.note, "z účastníků")

    def test_manual_coordinator(self) -> None:
        coordination, _main, _participant = self._setup()
        saved = coordination_coordinator_service.set_coordinator(
            coordination.id,
            full_name="Eva Externí",
            employer_name="Externí BOZP s.r.o.",
            role="koordinátor",
            phone="+420999",
            email="eva@example.com",
            note="ručně",
        )
        self.assertIsNone(saved.participant_id)
        self.assertIsNone(saved.employer_id)
        self.assertEqual(saved.full_name, "Eva Externí")
        self.assertEqual(saved.employer_name, "Externí BOZP s.r.o.")
        self.assertEqual(saved.role, "koordinátor")
        self.assertEqual(saved.phone, "+420999")
        self.assertEqual(saved.email, "eva@example.com")
        self.assertEqual(saved.note, "ručně")

        with self.assertRaises(CoordinationCoordinatorError):
            coordination_coordinator_service.set_coordinator(
                coordination.id,
                full_name="   ",
            )

    def test_snapshot_independent_of_participant_change(self) -> None:
        coordination, main, participant = self._setup()
        saved = coordination_coordinator_service.set_coordinator(
            coordination.id,
            employer_id=main.id,
            participant_id=participant.id,
        )
        coordination_participant_service.update_participant(
            participant.id,
            full_name="Změněné Jméno",
            role="jiná role",
            phone="+420000",
            email="nove@example.com",
            note="",
        )
        reloaded = coordination_coordinator_service.get_for_coordination(coordination.id)
        assert reloaded is not None
        self.assertEqual(reloaded.id, saved.id)
        self.assertEqual(reloaded.full_name, "Jan Účastník")
        self.assertEqual(reloaded.role, "technik")
        self.assertEqual(reloaded.phone, "+420111")
        self.assertEqual(reloaded.email, "jan@example.com")

        result = coordination_protocol_builder.build(coordination.id)
        coordinator = result.protocol_data["coordinator"]
        self.assertEqual(coordinator["full_name"], "Jan Účastník")
        self.assertEqual(coordinator["role"], "technik")
        self.assertEqual(coordinator["phone"], "+420111")

    def test_export_both_variants(self) -> None:
        coordination, main, participant = self._setup()
        coordination_coordinator_service.set_coordinator(
            coordination.id,
            employer_id=main.id,
            participant_id=participant.id,
        )
        result = coordination_protocol_builder.build(coordination.id)
        target = _TMP / "coord-from-participant.odt"
        coordination_protocol_odt_renderer.render_from_result(target, result)
        with zipfile.ZipFile(target) as zin:
            content = zin.read("content.xml").decode("utf-8")
        self.assertIn("Jan Účastník", content)
        self.assertIn("Hlavní firma s.r.o.", content)

        coordination_coordinator_service.set_coordinator(
            coordination.id,
            full_name="Ruční Koordinátor",
            employer_name="Firma Ruční",
            role="externí",
            phone="+420555",
            email="rucni@example.com",
        )
        result = coordination_protocol_builder.build(coordination.id)
        self.assertIsNone(result.protocol_data["coordinator"]["participant_id"])
        self.assertEqual(
            result.protocol_data["coordinator"]["full_name"],
            "Ruční Koordinátor",
        )
        target2 = _TMP / "coord-manual.odt"
        coordination_protocol_odt_renderer.render_from_result(target2, result)
        with zipfile.ZipFile(target2) as zin:
            content = zin.read("content.xml").decode("utf-8")
        self.assertIn("Ruční Koordinátor", content)
        self.assertIn("Firma Ruční", content)
        self.assertIn("externí", content)
        # Koordinátor už není Jan – jméno zůstává jen u účastníků.
        self.assertIn("Jméno: Ruční Koordinátor", content)
        self.assertNotIn("Jméno: Jan Účastník", content)

    def test_ui_source_modes(self) -> None:
        coordination, main, participant = self._setup()
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        tab = dialog.coordinator_tab
        self.assertTrue(hasattr(tab, "source_participant"))
        self.assertTrue(hasattr(tab, "source_manual"))
        self.assertEqual(tab.source_participant.text(), "Vybrat z účastníků")
        self.assertEqual(tab.source_manual.text(), "Zadat ručně")

        with patch(
            "moduly.koordinace_bozp.ui.coordination_coordinator_tab.QMessageBox.information"
        ), patch(
            "moduly.koordinace_bozp.ui.coordination_coordinator_tab.QMessageBox.warning"
        ):
            tab.source_manual.setChecked(True)
            tab.full_name.setText("UI Ruční")
            tab.employer_name.setText("Org UI")
            tab.role.setText("role")
            tab.phone.setText("+4201")
            tab.email.setText("ui@example.com")
            tab.save_coordinator()

            loaded = coordination_coordinator_service.get_for_coordination(
                coordination.id
            )
            assert loaded is not None
            self.assertIsNone(loaded.participant_id)
            self.assertEqual(loaded.full_name, "UI Ruční")

            tab.refresh()
            self.assertTrue(tab.source_manual.isChecked())
            self.assertEqual(tab.full_name.text(), "UI Ruční")

            tab.source_participant.setChecked(True)
            tab.employer_combo.setCurrentIndex(tab.employer_combo.findData(main.id))
            tab.participant_combo.setCurrentIndex(
                tab.participant_combo.findData(participant.id)
            )
            tab.save_coordinator()
            loaded = coordination_coordinator_service.get_for_coordination(
                coordination.id
            )
            assert loaded is not None
            self.assertEqual(loaded.participant_id, participant.id)
            self.assertEqual(loaded.full_name, "Jan Účastník")
        dialog.close()


if __name__ == "__main__":
    unittest.main()
