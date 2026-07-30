"""COORDINATION-UX-1 – zjednodušení workflow koordinačních schůzek."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMessageBox
from sqlalchemy import delete, text

_TMP = Path(tempfile.mkdtemp(prefix="coordination-ux-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _ensure_bozp_coordinations_table,
        initialize_database,
    )

    initialize_database()

    from core.database.session import get_session
    from moduly.koordinace_bozp.constants import (
        BOZP_COORDINATION_STATUS_CLOSED,
        BOZP_COORDINATION_STATUS_DRAFT,
        PROTOCOL_VERSION_MARK_DRAFT,
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
        close_meeting_action,
        coordination_lifecycle_service,
        is_content_editable,
        is_strict_readonly,
        protocol_version_mark,
    )
    from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
        coordination_workplace_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.koordinace_bozp.ui.coordination_protocol_preview_dialog import (
        CoordinationProtocolPreviewDialog,
    )
    from moduly.koordinace_bozp.ui.koordinace_bozp_page import KoordinaceBozpPage
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class CoordinationUx1TestCase(unittest.TestCase):
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

    def _create(self, **kwargs) -> BozpCoordination:
        payload = {
            "subject": "COORDINATION-UX-1",
            "meeting_date": date(2026, 7, 30),
            "place": "Jednací místnost",
        }
        payload.update(kwargs)
        return bozp_coordination_service.create_coordination(**payload)

    def _prepare_gate(self, coordination: BozpCoordination) -> None:
        operation = settings_service.save_workplace(
            name="ux1 provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="ux1 pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=operation.id,
        )
        coordination_workplace_service.add(
            coordination.id,
            operation_id=operation.id,
            workplace_id=workplace.id,
        )
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        coordination_coordinator_service.set_coordinator(
            coordination.id,
            full_name="Koordinátor UX1",
            role="Koordinátor BOZP",
            employer_name=main.company_name or "Hlavní",
        )

    def test_create_new_meeting_is_draft(self) -> None:
        created = self._create()
        self.assertEqual(created.status, BOZP_COORDINATION_STATUS_DRAFT)
        self.assertTrue(is_content_editable(created.status))
        self.assertFalse(is_strict_readonly(created.status))

    def test_save_keeps_draft_and_editable(self) -> None:
        created = self._create()
        dialog = BozpCoordinationDialog(None, coordination=created)
        dialog.subject.setText("Upravený název")
        dialog.mark_dirty()
        self.assertTrue(dialog._save())
        reloaded = bozp_coordination_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, BOZP_COORDINATION_STATUS_DRAFT)
        self.assertEqual(reloaded.subject, "Upravený název")
        self.assertFalse(dialog.subject.isReadOnly())
        self.assertFalse(dialog.close_meeting_btn.isHidden())
        dialog.close()

    def test_close_locks_edit_and_marks_closed(self) -> None:
        created = self._create()
        self._prepare_gate(created)
        dialog = BozpCoordinationDialog(None, coordination=created)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            dialog._close_meeting()
        reloaded = bozp_coordination_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, BOZP_COORDINATION_STATUS_CLOSED)
        self.assertEqual(dialog.status_value.text(), "Uzavřeno")
        self.assertTrue(dialog.subject.isReadOnly())
        self.assertTrue(dialog.close_meeting_btn.isHidden())
        save_btn = dialog.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.assertTrue(save_btn.isHidden())
        self.assertFalse(is_content_editable(reloaded.status))
        self.assertTrue(is_strict_readonly(reloaded.status))
        dialog.close()

    def test_return_to_draft_from_main_window(self) -> None:
        created = self._create()
        self._prepare_gate(created)
        closed = coordination_lifecycle_service.transition(
            created.id,
            BOZP_COORDINATION_STATUS_CLOSED,
            confirm_warnings=True,
        )
        page = KoordinaceBozpPage()
        page.refresh(select_id=closed.id)
        page.table.selectRow(0)
        page._update_action_buttons()
        self.assertEqual(
            {btn.text() for btn in page._lifecycle_buttons},
            {"Vrátit k dopracování"},
        )
        action = coordination_lifecycle_service.list_actions(closed.status)[0]
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            page._run_lifecycle_action(action)
        reloaded = bozp_coordination_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, BOZP_COORDINATION_STATUS_DRAFT)

        dialog = BozpCoordinationDialog(None, coordination=reloaded)
        self.assertFalse(dialog.subject.isReadOnly())
        self.assertFalse(dialog.close_meeting_btn.isHidden())
        dialog.close()

    def test_preview_does_not_change_status(self) -> None:
        created = self._create()
        self._prepare_gate(created)
        status_before = created.status
        dialog = BozpCoordinationDialog(None, coordination=created)
        with patch.object(CoordinationProtocolPreviewDialog, "exec", return_value=0):
            dialog.open_protocol_preview()
        reloaded = bozp_coordination_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, status_before)
        self.assertEqual(reloaded.status, BOZP_COORDINATION_STATUS_DRAFT)
        dialog.close()

    def test_print_from_main_window(self) -> None:
        created = self._create()
        self._prepare_gate(created)
        closed = coordination_lifecycle_service.transition(
            created.id,
            BOZP_COORDINATION_STATUS_CLOSED,
            confirm_warnings=True,
        )
        page = KoordinaceBozpPage()
        page.refresh(select_id=closed.id)
        page.table.selectRow(0)
        page._update_action_buttons()
        self.assertTrue(page.print_btn.isEnabled())
        self.assertIsNone(protocol_version_mark(closed.status))
        with patch.object(
            CoordinationProtocolPreviewDialog, "exec", return_value=0
        ) as exec_mock:
            page.print_selected_protocol()
            exec_mock.assert_called_once()

        draft_preview = CoordinationProtocolPreviewDialog(
            None, coordination_id=created.id
        )
        # Closed meeting: no working-version mark.
        self.assertNotIn(PROTOCOL_VERSION_MARK_DRAFT, draft_preview.status_label.text())
        draft_preview.close()

    def test_draft_preview_has_working_mark(self) -> None:
        created = self._create()
        preview = CoordinationProtocolPreviewDialog(None, coordination_id=created.id)
        self.assertIn(PROTOCOL_VERSION_MARK_DRAFT, preview.status_label.text())
        preview.close()

    def test_migrate_ready_and_issued_to_closed(self) -> None:
        ready = self._create(subject="ready legacy")
        issued = self._create(subject="issued legacy")
        draft = self._create(subject="draft keep")
        with get_session() as session:
            session.execute(
                text("UPDATE bozp_coordinations SET status = 'ready' WHERE id = :id"),
                {"id": ready.id},
            )
            session.execute(
                text("UPDATE bozp_coordinations SET status = 'issued' WHERE id = :id"),
                {"id": issued.id},
            )
            session.commit()

        _ensure_bozp_coordinations_table()

        ready_reloaded = bozp_coordination_service.get_by_id(ready.id)
        issued_reloaded = bozp_coordination_service.get_by_id(issued.id)
        draft_reloaded = bozp_coordination_service.get_by_id(draft.id)
        assert ready_reloaded is not None
        assert issued_reloaded is not None
        assert draft_reloaded is not None
        self.assertEqual(ready_reloaded.status, BOZP_COORDINATION_STATUS_CLOSED)
        self.assertEqual(issued_reloaded.status, BOZP_COORDINATION_STATUS_CLOSED)
        self.assertEqual(draft_reloaded.status, BOZP_COORDINATION_STATUS_DRAFT)
        self.assertEqual(ready_reloaded.subject, "ready legacy")
        self.assertEqual(issued_reloaded.subject, "issued legacy")

    def test_close_meeting_action_helper(self) -> None:
        action = close_meeting_action()
        self.assertEqual(action.action_id, "close")
        self.assertEqual(action.target_status, BOZP_COORDINATION_STATUS_CLOSED)
        self.assertEqual(action.label, "Uzavřít")


if __name__ == "__main__":
    unittest.main()
