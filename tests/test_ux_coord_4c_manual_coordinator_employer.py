"""UX-COORD-4c – výběr zaměstnavatele ručního koordinátora."""

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

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-4c-"))
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
    from moduly.koordinace_bozp.constants import (
        COORDINATOR_MANUAL_OTHER_ORGANIZATION,
        COORDINATOR_MANUAL_OTHER_ORGANIZATION_LABEL,
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
    from moduly.koordinace_bozp.sluzby.coordination_coordinator_service import (
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


class UxCoord4cManualCoordinatorEmployerTestCase(unittest.TestCase):
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
            subject="UX-COORD-4c",
            meeting_date=date.today(),
        )
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        supplier = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Dodavatel Stavby a.s.",
            abbreviation="DS",
        )
        coordination_participant_service.add_manual(
            main.id,
            full_name="Jan Účastník",
            role="technik",
        )
        return coordination, main, supplier

    def _open_manual_tab(self, coordination):
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        tab = dialog.coordinator_tab
        tab.source_manual.setChecked(True)
        return dialog, tab

    def test_manual_with_main_employer(self) -> None:
        coordination, main, _supplier = self._setup()
        dialog, tab = self._open_manual_tab(coordination)
        with patch(
            "moduly.koordinace_bozp.ui.coordination_coordinator_tab.QMessageBox.information"
        ), patch(
            "moduly.koordinace_bozp.ui.coordination_coordinator_tab.QMessageBox.warning"
        ):
            self.assertEqual(tab.employer_combo.currentData(), main.id)
            tab.full_name.setText("Koordinátor Hlavní")
            tab.role.setText("koordinátor BOZP")
            tab.phone.setText("+420100")
            tab.email.setText("hlavni@example.com")
            self.assertTrue(dialog._save())

            loaded = coordination_coordinator_service.get_for_coordination(
                coordination.id
            )
            assert loaded is not None
            self.assertIsNone(loaded.participant_id)
            self.assertIsNone(loaded.employer_id)
            self.assertEqual(loaded.full_name, "Koordinátor Hlavní")
            self.assertEqual(loaded.employer_name, main.company_name)
            self.assertEqual(loaded.role, "koordinátor BOZP")
        dialog.mark_clean()
        dialog.close()

    def test_manual_with_supplier(self) -> None:
        coordination, _main, supplier = self._setup()
        dialog, tab = self._open_manual_tab(coordination)
        with patch(
            "moduly.koordinace_bozp.ui.coordination_coordinator_tab.QMessageBox.information"
        ), patch(
            "moduly.koordinace_bozp.ui.coordination_coordinator_tab.QMessageBox.warning"
        ):
            index = tab.employer_combo.findData(supplier.id)
            self.assertGreaterEqual(index, 0)
            tab.employer_combo.setCurrentIndex(index)
            tab.full_name.setText("Koordinátor Dodavatel")
            self.assertTrue(dialog._save())

            loaded = coordination_coordinator_service.get_for_coordination(
                coordination.id
            )
            assert loaded is not None
            self.assertIsNone(loaded.employer_id)
            self.assertEqual(loaded.employer_name, "Dodavatel Stavby a.s.")
            self.assertEqual(loaded.full_name, "Koordinátor Dodavatel")
        dialog.mark_clean()
        dialog.close()

    def test_manual_with_other_organization(self) -> None:
        coordination, _main, _supplier = self._setup()
        dialog, tab = self._open_manual_tab(coordination)
        with patch(
            "moduly.koordinace_bozp.ui.coordination_coordinator_tab.QMessageBox.information"
        ), patch(
            "moduly.koordinace_bozp.ui.coordination_coordinator_tab.QMessageBox.warning"
        ) as warning:
            other_index = tab.employer_combo.findData(
                COORDINATOR_MANUAL_OTHER_ORGANIZATION
            )
            self.assertGreaterEqual(other_index, 0)
            self.assertEqual(
                tab.employer_combo.itemText(other_index),
                COORDINATOR_MANUAL_OTHER_ORGANIZATION_LABEL,
            )
            tab.employer_combo.setCurrentIndex(other_index)
            self.assertTrue(tab.employer_name.isEnabled())
            tab.full_name.setText("Externí Koordinátor")
            tab.employer_name.setText("Externí BOZP s.r.o.")
            tab.role.setText("externí")
            self.assertTrue(dialog._save())

            loaded = coordination_coordinator_service.get_for_coordination(
                coordination.id
            )
            assert loaded is not None
            self.assertIsNone(loaded.employer_id)
            self.assertEqual(loaded.employer_name, "Externí BOZP s.r.o.")
            self.assertEqual(loaded.full_name, "Externí Koordinátor")

            tab.employer_name.clear()
            self.assertFalse(dialog._save())
            warning.assert_called()
        dialog.mark_clean()
        dialog.close()

    def test_deactivated_employer_not_in_manual_combo(self) -> None:
        coordination, _main, supplier = self._setup()
        coordination_employer_service.deactivate(supplier.id)
        dialog, tab = self._open_manual_tab(coordination)
        values = [
            tab.employer_combo.itemData(i) for i in range(tab.employer_combo.count())
        ]
        self.assertNotIn(supplier.id, values)
        self.assertIn(COORDINATOR_MANUAL_OTHER_ORGANIZATION, values)
        dialog.mark_clean()
        dialog.close()

    def test_snapshot_preserved_after_employer_deactivation(self) -> None:
        coordination, _main, supplier = self._setup()
        saved = coordination_coordinator_service.set_coordinator(
            coordination.id,
            full_name="Snapshot Koordinátor",
            employer_name=supplier.company_name,
            role="koordinátor",
            phone="+420777",
            email="snap@example.com",
        )
        coordination_employer_service.deactivate(supplier.id)

        reloaded = coordination_coordinator_service.get_for_coordination(coordination.id)
        assert reloaded is not None
        self.assertEqual(reloaded.id, saved.id)
        self.assertEqual(reloaded.employer_name, "Dodavatel Stavby a.s.")
        self.assertEqual(reloaded.full_name, "Snapshot Koordinátor")
        self.assertIsNone(reloaded.employer_id)

        dialog, tab = self._open_manual_tab(coordination)
        self.assertTrue(tab.source_manual.isChecked())
        self.assertEqual(
            tab.employer_combo.currentData(),
            COORDINATOR_MANUAL_OTHER_ORGANIZATION,
        )
        self.assertEqual(tab.employer_name.text(), "Dodavatel Stavby a.s.")
        self.assertEqual(tab.full_name.text(), "Snapshot Koordinátor")
        dialog.mark_clean()
        dialog.close()

    def test_edit_restores_employer_selection(self) -> None:
        coordination, main, supplier = self._setup()
        coordination_coordinator_service.set_coordinator(
            coordination.id,
            full_name="Obnovený",
            employer_name=supplier.company_name,
            role="role",
        )
        dialog, tab = self._open_manual_tab(coordination)
        self.assertEqual(tab.employer_combo.currentData(), supplier.id)
        self.assertFalse(tab.employer_name.isEnabled())
        self.assertEqual(tab.full_name.text(), "Obnovený")

        coordination_coordinator_service.set_coordinator(
            coordination.id,
            full_name="Jiná org",
            employer_name="Neznámá firma s.r.o.",
        )
        tab.refresh()
        self.assertTrue(tab.source_manual.isChecked())
        self.assertEqual(
            tab.employer_combo.currentData(),
            COORDINATOR_MANUAL_OTHER_ORGANIZATION,
        )
        self.assertEqual(tab.employer_name.text(), "Neznámá firma s.r.o.")

        coordination_coordinator_service.set_coordinator(
            coordination.id,
            full_name="Hlavní opět",
            employer_name=main.company_name,
        )
        tab.refresh()
        self.assertEqual(tab.employer_combo.currentData(), main.id)
        dialog.mark_clean()
        dialog.close()

    def test_preview_and_odt_show_organization(self) -> None:
        coordination, main, supplier = self._setup()
        for full_name, employer_name in (
            ("Koord Hlavní", main.company_name),
            ("Koord Dodavatel", supplier.company_name),
            ("Koord Externí", "Cizí organizace s.r.o."),
        ):
            coordination_coordinator_service.set_coordinator(
                coordination.id,
                full_name=full_name,
                employer_name=employer_name,
                role="koordinátor",
            )
            result = coordination_protocol_builder.build(coordination.id)
            coordinator = result.protocol_data["coordinator"]
            self.assertEqual(coordinator["full_name"], full_name)
            self.assertEqual(coordinator["employer_name"], employer_name)

            target = _TMP / f"{full_name.replace(' ', '_')}.odt"
            coordination_protocol_odt_renderer.render_from_result(target, result)
            with zipfile.ZipFile(target) as zin:
                content = zin.read("content.xml").decode("utf-8")
            self.assertIn(full_name, content)
            self.assertIn(employer_name, content)


if __name__ == "__main__":
    unittest.main()
