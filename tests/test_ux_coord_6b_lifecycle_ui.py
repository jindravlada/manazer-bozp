"""UX-COORD-6b – ovládání životního cyklu koordinace v UI."""

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
        BOZP_COORDINATION_STATUS_ARCHIVED,
        BOZP_COORDINATION_STATUS_COMPLETED,
        BOZP_COORDINATION_STATUS_DRAFT,
        BOZP_COORDINATION_STATUS_ISSUED,
        BOZP_COORDINATION_STATUS_READY,
        PROTOCOL_VERSION_MARK_DRAFT,
        PROTOCOL_VERSION_MARK_READY,
        STATUS_FILTER_ARCHIVED,
        STATUS_FILTER_DRAFT,
        STATUS_FILTER_ISSUED,
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
    from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
        ProtocolBuildResult,
        ProtocolSummary,
        coordination_protocol_builder,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_odt_renderer import (
        coordination_protocol_odt_renderer,
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
        expected = {
            BOZP_COORDINATION_STATUS_DRAFT: {
                "Připravit k vydání",
                "Archivovat",
            },
            BOZP_COORDINATION_STATUS_READY: {
                "Vrátit k dopracování",
                "Vydat",
                "Archivovat",
            },
            BOZP_COORDINATION_STATUS_ISSUED: {
                "Ukončit",
                "Vrátit k dopracování",
                "Archivovat",
            },
            BOZP_COORDINATION_STATUS_COMPLETED: {
                "Znovu otevřít",
                "Archivovat",
            },
            BOZP_COORDINATION_STATUS_ARCHIVED: {"Obnovit"},
        }
        for status, labels in expected.items():
            actions = coordination_lifecycle_service.list_actions(status)
            self.assertEqual({item.label for item in actions}, labels)

        page = KoordinaceBozpPage()
        created = self._create()
        page.refresh(select_id=created.id)
        page.table.selectRow(0)
        page._update_action_buttons()
        self.assertEqual(
            {btn.text() for btn in page._lifecycle_buttons},
            expected[BOZP_COORDINATION_STATUS_DRAFT],
        )

    def test_readonly_issued_completed_archived(self) -> None:
        for status in (
            BOZP_COORDINATION_STATUS_ISSUED,
            BOZP_COORDINATION_STATUS_COMPLETED,
            BOZP_COORDINATION_STATUS_ARCHIVED,
        ):
            created = self._create(subject=f"RO {status}")
            self._force_status(created.id, status)
            coordination = bozp_coordination_service.get_by_id(created.id)
            dialog = BozpCoordinationDialog(None, coordination=coordination)
            self.assertTrue(dialog.subject.isReadOnly())
            self.assertTrue(dialog.place.isReadOnly())
            self.assertTrue(dialog.note.isReadOnly())
            self.assertFalse(dialog.meeting_date.isEnabled())
            save_btn = dialog.buttons.button(QDialogButtonBox.StandardButton.Save)
            self.assertFalse(save_btn.isEnabled())
            self.assertTrue(dialog.preview_btn.isEnabled())
            self.assertTrue(dialog.employers_tab.add_btn.isEnabled() is False)
            dialog.close()

    def test_ready_edit_reverts_to_draft(self) -> None:
        created = self._create()
        self._prepare_gate(created)
        ready = coordination_lifecycle_service.transition(
            created.id,
            BOZP_COORDINATION_STATUS_READY,
            confirm_warnings=True,
        )
        dialog = BozpCoordinationDialog(None, coordination=ready)
        self.assertEqual(dialog.status_value.text(), "Připraveno k vydání")
        self.assertFalse(dialog.subject.isReadOnly())

        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            dialog.subject.setText("Upravený název")
            dialog._on_content_edited()

        reloaded = bozp_coordination_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, BOZP_COORDINATION_STATUS_DRAFT)
        self.assertEqual(dialog.status_value.text(), "Rozpracováno")
        dialog.close()

    def test_status_filter(self) -> None:
        draft = self._create(subject="Draft filtr")
        issued = self._create(subject="Issued filtr")
        self._force_status(issued.id, BOZP_COORDINATION_STATUS_ISSUED)
        archived = self._create(subject="Archiv filtr")
        self._force_status(archived.id, BOZP_COORDINATION_STATUS_ARCHIVED)

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
        self.assertNotIn(issued.id, ids)
        self.assertNotIn(archived.id, ids)

        page.status_filter.setCurrentIndex(
            page.status_filter.findData(STATUS_FILTER_ISSUED)
        )
        page.refresh()
        ids = {
            int(page.table.item(row, 0).text())
            for row in range(page.table.rowCount())
        }
        self.assertEqual(ids, {issued.id})

        page.status_filter.setCurrentIndex(
            page.status_filter.findData(STATUS_FILTER_ARCHIVED)
        )
        page.refresh()
        ids = {
            int(page.table.item(row, 0).text())
            for row in range(page.table.rowCount())
        }
        self.assertEqual(ids, {archived.id})

    def test_version_mark_in_preview_and_odt(self) -> None:
        self.assertEqual(protocol_version_mark("draft"), PROTOCOL_VERSION_MARK_DRAFT)
        self.assertEqual(protocol_version_mark("ready"), PROTOCOL_VERSION_MARK_READY)
        self.assertIsNone(protocol_version_mark("issued"))
        self.assertIsNone(protocol_version_mark("completed"))
        self.assertIsNone(protocol_version_mark("archived"))

        created = self._create()
        self._prepare_gate(created)
        preview = CoordinationProtocolPreviewDialog(None, coordination_id=created.id)
        self.assertIn(PROTOCOL_VERSION_MARK_DRAFT, preview.status_label.text())
        self.assertTrue(preview.export_btn.isEnabled())
        preview.close()

        ready = coordination_lifecycle_service.transition(
            created.id,
            BOZP_COORDINATION_STATUS_READY,
            confirm_warnings=True,
        )
        preview_ready = CoordinationProtocolPreviewDialog(
            None, coordination_id=ready.id
        )
        self.assertIn(PROTOCOL_VERSION_MARK_READY, preview_ready.status_label.text())
        preview_ready.close()

        result = coordination_protocol_builder.build(ready.id)
        lines = coordination_protocol_odt_renderer._build_document_lines(
            dict(result.protocol_data),
            warnings=[item.to_dict() for item in result.warnings],
            summary=result.summary.to_dict(),
        )
        self.assertIn(PROTOCOL_VERSION_MARK_READY, lines)

        issued = coordination_lifecycle_service.transition(
            ready.id,
            BOZP_COORDINATION_STATUS_ISSUED,
            confirm_warnings=True,
        )
        preview_issued = CoordinationProtocolPreviewDialog(
            None, coordination_id=issued.id
        )
        self.assertNotIn(PROTOCOL_VERSION_MARK_DRAFT, preview_issued.status_label.text())
        self.assertNotIn(PROTOCOL_VERSION_MARK_READY, preview_issued.status_label.text())
        self.assertTrue(preview_issued.export_btn.isEnabled())
        preview_issued.close()

        for status in (
            BOZP_COORDINATION_STATUS_COMPLETED,
            BOZP_COORDINATION_STATUS_ARCHIVED,
        ):
            self._force_status(issued.id, status)
            dialog = CoordinationProtocolPreviewDialog(None, coordination_id=issued.id)
            self.assertTrue(dialog.export_btn.isEnabled())
            dialog.close()

    def test_dialog_change_status_menu(self) -> None:
        created = self._create()
        dialog = BozpCoordinationDialog(None, coordination=created)
        self.assertEqual(dialog.status_value.text(), "Rozpracováno")
        self.assertTrue(dialog.change_status_btn.isEnabled())
        labels = [action.text() for action in dialog.change_status_menu.actions()]
        self.assertEqual(labels, ["Připravit k vydání", "Archivovat"])
        dialog.close()


if __name__ == "__main__":
    unittest.main()
