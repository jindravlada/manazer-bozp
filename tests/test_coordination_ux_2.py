"""COORDINATION-UX-2 – oddělení uložení od validačních podmínek."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="coordination-ux-2-"))
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
        BOZP_COORDINATION_STATUS_CLOSED,
        BOZP_COORDINATION_STATUS_DRAFT,
        PROTOCOL_WARNING_MISSING_COORDINATOR,
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
    from moduly.koordinace_bozp.sluzby.coordination_lifecycle_service import (
        CoordinationLifecycleBlocked,
        coordination_lifecycle_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
        coordination_workplace_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class CoordinationUx2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationContact))
            session.execute(delete(CoordinationEmployerActivity))
            session.execute(delete(CoordinationMeasure))
            session.execute(delete(CoordinationWorkplace))
            session.execute(delete(CoordinationCoordinator))
            session.execute(delete(CoordinationParticipant))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.commit()

    def _prepare_gate_without_coordinator(self, coordination: BozpCoordination) -> None:
        operation = settings_service.save_workplace(
            name="ux2 provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="ux2 pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        coordination_workplace_service.add(
            coordination.id,
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        coordination_employer_service.ensure_main_employer(coordination.id)

    def test_new_meeting_saves_without_coordinator(self) -> None:
        dialog = BozpCoordinationDialog(None)
        dialog.subject.setText("Bez koordinátora")
        dialog.place.setText("Jednací místnost")
        self.assertTrue(dialog._save())
        assert dialog.coordination is not None
        self.assertEqual(dialog.coordination.status, BOZP_COORDINATION_STATUS_DRAFT)
        coordinator = coordination_coordinator_service.get_for_coordination(
            dialog.coordination.id
        )
        self.assertIsNone(coordinator)
        save_btn = dialog.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.assertFalse(save_btn.isHidden())
        self.assertTrue(save_btn.isEnabled())
        dialog.close()

    def test_draft_can_be_saved_repeatedly(self) -> None:
        created = bozp_coordination_service.create_coordination(
            subject="",
            meeting_date=date(2026, 7, 30),
            place="Místnost",
        )
        dialog = BozpCoordinationDialog(None, coordination=created)
        save_btn = dialog.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.assertTrue(save_btn.isEnabled())

        dialog.subject.setText("První uložení")
        self.assertTrue(dialog._save())
        dialog.note.setPlainText("Poznámka po přerušení")
        dialog.mark_dirty()
        self.assertTrue(dialog._save())
        self.assertTrue(dialog._save())  # i bez dirty zůstává aktivní

        reloaded = bozp_coordination_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, BOZP_COORDINATION_STATUS_DRAFT)
        self.assertEqual(reloaded.subject, "První uložení")
        self.assertEqual(reloaded.note, "Poznámka po přerušení")
        dialog.close()

    def test_close_without_coordinator_fails_with_validation(self) -> None:
        created = bozp_coordination_service.create_coordination(
            subject="UX-2 uzavření",
            meeting_date=date(2026, 7, 30),
            place="Jednací místnost",
        )
        self._prepare_gate_without_coordinator(created)

        with self.assertRaises(CoordinationLifecycleBlocked) as ctx:
            coordination_lifecycle_service.transition(
                created.id,
                BOZP_COORDINATION_STATUS_CLOSED,
                confirm_warnings=True,
            )
        codes = {item.code for item in ctx.exception.warnings}
        self.assertIn(PROTOCOL_WARNING_MISSING_COORDINATOR, codes)
        self.assertIn("koordinátor", str(ctx.exception).lower())

        reloaded = bozp_coordination_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, BOZP_COORDINATION_STATUS_DRAFT)

        dialog = BozpCoordinationDialog(None, coordination=created)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes), patch.object(
            QMessageBox, "warning"
        ) as warning_mock:
            dialog._close_meeting()
        warning_mock.assert_called()
        message = str(warning_mock.call_args[0][2])
        self.assertIn("nelze uzavřít", message.lower())
        self.assertIn("koordinátor", message.lower())

        reloaded = bozp_coordination_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, BOZP_COORDINATION_STATUS_DRAFT)
        dialog.close()

    def test_close_succeeds_after_coordinator_is_set(self) -> None:
        created = bozp_coordination_service.create_coordination(
            subject="UX-2 s koordinátorem",
            meeting_date=date(2026, 7, 30),
            place="Jednací místnost",
        )
        self._prepare_gate_without_coordinator(created)
        main = coordination_employer_service.ensure_main_employer(created.id)
        coordination_coordinator_service.set_coordinator(
            created.id,
            full_name="Koordinátor UX2",
            role="Koordinátor BOZP",
            employer_name=main.company_name or "Hlavní",
        )

        closed = coordination_lifecycle_service.transition(
            created.id,
            BOZP_COORDINATION_STATUS_CLOSED,
            confirm_warnings=True,
        )
        self.assertEqual(closed.status, BOZP_COORDINATION_STATUS_CLOSED)

        dialog = BozpCoordinationDialog(None, coordination=closed)
        self.assertTrue(dialog.subject.isReadOnly())
        self.assertTrue(dialog.close_meeting_btn.isHidden())
        dialog.close()


if __name__ == "__main__":
    unittest.main()
