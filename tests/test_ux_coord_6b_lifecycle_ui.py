"""UX-COORD-6b – ovládání životního cyklu koordinace v UI (COORDINATION-UX-1)."""

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

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-6b-"))
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
        PROTOCOL_VERSION_MARK_DRAFT,
        STATUS_FILTER_CLOSED,
        STATUS_FILTER_DRAFT,
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
        coordination_lifecycle_service,
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


class UxCoord6bLifecycleUiTestCase(unittest.TestCase):
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
            "subject": "UX-COORD-6b",
            "meeting_date": date(2026, 7, 19),
            "place": "Jednací místnost",
        }
        payload.update(kwargs)
        return bozp_coordination_service.create_coordination(**payload)

    def _prepare_gate(self, coordination: BozpCoordination) -> None:
        operation = settings_service.save_workplace(
            name="6b provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="6b pracoviště",
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
            full_name="Koordinátor 6b",
            role="Koordinátor BOZP",
            employer_name=main.company_name or "Hlavní",
        )

    def _force_status(self, coordination_id: int, status: str) -> BozpCoordination:
        item = bozp_coordination_service.get_by_id(coordination_id)
        assert item is not None
        item.status = status
        return bozp_coordination_service.repository.update(item)

    def test_list_actions_per_status(self) -> None:
        self.assertEqual(
            {item.label for item in coordination_lifecycle_service.list_actions("draft")},
            set(),
        )
        self.assertEqual(
            {
                item.label
                for item in coordination_lifecycle_service.list_actions("closed")
            },
            {"Vrátit k dopracování"},
        )

        page = KoordinaceBozpPage()
        created = self._create()
        page.refresh(select_id=created.id)
        page.table.selectRow(0)
        page._update_action_buttons()
        self.assertEqual({btn.text() for btn in page._lifecycle_buttons}, set())

        self._force_status(created.id, BOZP_COORDINATION_STATUS_CLOSED)
        page.refresh(select_id=created.id)
        page.table.selectRow(0)
        page._update_action_buttons()
        self.assertEqual(
            {btn.text() for btn in page._lifecycle_buttons},
            {"Vrátit k dopracování"},
        )

    def test_readonly_closed(self) -> None:
        created = self._create()
        self._force_status(created.id, BOZP_COORDINATION_STATUS_CLOSED)
        coordination = bozp_coordination_service.get_by_id(created.id)
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        self.assertTrue(dialog.subject.isReadOnly())
        self.assertTrue(dialog.place.isReadOnly())
        self.assertTrue(dialog.note.isReadOnly())
        self.assertFalse(dialog.meeting_date.isEnabled())
        save_btn = dialog.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.assertTrue(save_btn.isHidden())
        self.assertTrue(dialog.close_meeting_btn.isHidden())
        self.assertTrue(dialog.preview_btn.isEnabled())
        self.assertTrue(dialog.employers_tab.add_btn.isEnabled() is False)
        dialog.close()

    def test_status_filter(self) -> None:
        draft = self._create(subject="Draft filtr")
        closed = self._create(subject="Closed filtr")
        self._force_status(closed.id, BOZP_COORDINATION_STATUS_CLOSED)

        page = KoordinaceBozpPage()
        page.status_filter.setCurrentIndex(
            page.status_filter.findData(STATUS_FILTER_DRAFT)
        )
        page.refresh()
        ids = {
            int(page.table.item(row, 0).text())
            for row in range(page.table.rowCount())
        }
        self.assertIn(draft.id, ids)
        self.assertNotIn(closed.id, ids)

        page.status_filter.setCurrentIndex(
            page.status_filter.findData(STATUS_FILTER_CLOSED)
        )
        page.refresh()
        ids = {
            int(page.table.item(row, 0).text())
            for row in range(page.table.rowCount())
        }
        self.assertEqual(ids, {closed.id})

    def test_version_mark_in_preview(self) -> None:
        self.assertEqual(protocol_version_mark("draft"), PROTOCOL_VERSION_MARK_DRAFT)
        self.assertIsNone(protocol_version_mark("closed"))
        self.assertIsNone(protocol_version_mark("ready"))
        self.assertIsNone(protocol_version_mark("issued"))

        created = self._create()
        self._prepare_gate(created)
        preview = CoordinationProtocolPreviewDialog(None, coordination_id=created.id)
        self.assertIn(PROTOCOL_VERSION_MARK_DRAFT, preview.status_label.text())
        self.assertTrue(preview.export_btn.isEnabled())
        preview.close()

        closed = coordination_lifecycle_service.transition(
            created.id,
            BOZP_COORDINATION_STATUS_CLOSED,
            confirm_warnings=True,
        )
        preview_closed = CoordinationProtocolPreviewDialog(
            None, coordination_id=closed.id
        )
        self.assertNotIn(PROTOCOL_VERSION_MARK_DRAFT, preview_closed.status_label.text())
        self.assertTrue(preview_closed.export_btn.isEnabled())
        preview_closed.close()

    def test_dialog_footer_buttons(self) -> None:
        created = self._create()
        dialog = BozpCoordinationDialog(None, coordination=created)
        self.assertEqual(dialog.status_value.text(), "Rozpracováno")
        self.assertEqual(dialog.preview_btn.text(), "Náhled protokolu")
        self.assertEqual(dialog.close_meeting_btn.text(), "Uzavřít")
        save_btn = dialog.buttons.button(QDialogButtonBox.StandardButton.Save)
        close_btn = dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.assertEqual(save_btn.text(), "Uložit")
        self.assertEqual(close_btn.text(), "Zavřít")
        self.assertFalse(dialog.close_meeting_btn.isHidden())
        dialog.close()

    def test_print_button_on_page(self) -> None:
        page = KoordinaceBozpPage()
        self.assertEqual(page.print_btn.text(), "Tisk protokolu")
        created = self._create()
        page.refresh(select_id=created.id)
        page.table.selectRow(0)
        page._update_action_buttons()
        self.assertTrue(page.print_btn.isEnabled())

        with patch.object(CoordinationProtocolPreviewDialog, "exec", return_value=0) as exec_mock:
            page.print_selected_protocol()
            exec_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
