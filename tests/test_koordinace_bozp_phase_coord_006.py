"""Fáze COORD-006 – místa koordinace a předání rizik dodavatelů."""

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

_TMP = Path(tempfile.mkdtemp(prefix="coord-006-"))
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
        RISK_HANDOVER_STATUS_UNSET,
        RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
        RISK_SUBMISSION_STATUS_STATED_AT_MEETING,
        RISK_SUBMISSION_STATUS_WILL_EMAIL,
        TAB_RISK_SUBMISSIONS,
        TAB_WORKPLACES,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
        CoordinationPbpRevision,
    )
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
        CoordinationRiskSubmissionHistory,
    )
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.modely.coordination_workplace import (
        CoordinationWorkplace,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_attachment_service import (
        coordination_attachment_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_risk_submission_service import (
        CoordinationRiskSubmissionError,
        coordination_risk_submission_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
        CoordinationWorkplaceError,
        coordination_workplace_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.koordinace_bozp.ui.coordination_workplace_dialog import (
        CoordinationWorkplaceDialog,
    )
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
        WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class KoordinaceBozpPhaseCoord006TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationRiskSubmissionHistory))
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
            address="Praha 1",
            nace="",
        )
        self.operation = settings_service.save_workplace(
            name="COORD provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="COORD pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.part = settings_service.save_workplace(
            name="COORD část",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=self.workplace.id,
        )
        self.other_workplace = settings_service.save_workplace(
            name="COORD druhé pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )

    def _create_coordination(self):
        return bozp_coordination_service.create_coordination(
            subject="COORD-006",
            meeting_date=date.today(),
        )

    def test_tables_exist(self) -> None:
        for table, columns in (
            (
                "coordination_workplaces",
                (
                    "id",
                    "coordination_id",
                    "operation_id",
                    "workplace_id",
                    "workplace_part_id",
                    "note",
                    "active",
                    "sort_order",
                ),
            ),
            (
                "coordination_employer_risk_submissions",
                (
                    "id",
                    "coordination_employer_id",
                    "submission_method",
                    "submission_date",
                    "document_reference",
                    "note",
                    "active",
                ),
            ),
            (
                "coordination_attachments",
                (
                    "id",
                    "coordination_id",
                    "coordination_employer_id",
                    "attachment_type",
                    "original_filename",
                    "stored_filename",
                    "file_path",
                    "description",
                    "active",
                ),
            ),
        ):
            existing = _table_columns(table)
            for name in columns:
                self.assertIn(name, existing)

    def test_add_operation_and_hierarchy_filter(self) -> None:
        coordination = self._create_coordination()
        only_operation = coordination_workplace_service.add(
            coordination.id,
            operation_id=self.operation.id,
        )
        self.assertEqual(only_operation.operation_id, self.operation.id)
        self.assertIsNone(only_operation.workplace_id)

        dialog = CoordinationWorkplaceDialog(None)
        dialog.operation.setCurrentIndex(dialog.operation.findData(self.operation.id))
        workplace_ids = [
            dialog.workplace.itemData(i)
            for i in range(dialog.workplace.count())
            if isinstance(dialog.workplace.itemData(i), int)
        ]
        self.assertIn(self.workplace.id, workplace_ids)
        self.assertIn(self.other_workplace.id, workplace_ids)

        dialog.workplace.setCurrentIndex(dialog.workplace.findData(self.workplace.id))
        part_ids = [
            dialog.workplace_part.itemData(i)
            for i in range(dialog.workplace_part.count())
            if isinstance(dialog.workplace_part.itemData(i), int)
        ]
        self.assertEqual(part_ids, [self.part.id])

    def test_multiple_places_and_duplicate_forbidden(self) -> None:
        coordination = self._create_coordination()
        first = coordination_workplace_service.add(
            coordination.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        second = coordination_workplace_service.add(
            coordination.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=self.part.id,
        )
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(
            len(coordination_workplace_service.list_for_coordination(coordination.id)),
            2,
        )
        with self.assertRaises(CoordinationWorkplaceError):
            coordination_workplace_service.add(
                coordination.id,
                operation_id=self.operation.id,
                workplace_id=self.workplace.id,
            )

    def test_deactivate_and_reactivate_place(self) -> None:
        coordination = self._create_coordination()
        item = coordination_workplace_service.add(
            coordination.id,
            operation_id=self.operation.id,
            workplace_id=self.other_workplace.id,
        )
        self.assertTrue(coordination_workplace_service.deactivate(item.id))
        reloaded = coordination_workplace_service.get_by_id(item.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)
        self.assertTrue(coordination_workplace_service.activate(item.id))
        again = coordination_workplace_service.get_by_id(item.id)
        assert again is not None
        self.assertTrue(again.active)

    def test_main_employer_cannot_have_risk_submission(self) -> None:
        coordination = self._create_coordination()
        main = next(
            item
            for item in coordination_employer_service.list_for_coordination(
                coordination.id
            )
            if item.is_main
        )
        with self.assertRaises(CoordinationRiskSubmissionError):
            coordination_risk_submission_service.save_submission(
                main.id,
                submission_method=RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
            )

    def test_save_submission_and_statuses(self) -> None:
        coordination = self._create_coordination()
        contractor = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Dodavatel s.r.o.",
            abbreviation="DOD",
        )
        self.assertEqual(
            coordination_risk_submission_service.handover_status(contractor.id),
            RISK_HANDOVER_STATUS_UNSET,
        )
        coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
            submission_date=date(2026, 7, 10),
            document_reference="e-mail č. 12",
        )
        self.assertEqual(
            coordination_risk_submission_service.handover_status(contractor.id),
            RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
        )

        source = _TMP / "rizika-dodavatele.pdf"
        source.write_bytes(b"%PDF-1.4 test")
        attachment = coordination_attachment_service.add_file(
            coordination_id=coordination.id,
            coordination_employer_id=contractor.id,
            source_path=source,
        )
        self.assertEqual(attachment.original_filename, "rizika-dodavatele.pdf")
        stored = coordination_attachment_service.resolve_path(attachment)
        self.assertTrue(stored.exists())
        self.assertEqual(stored.read_bytes(), source.read_bytes())
        self.assertNotEqual(stored.resolve(), source.resolve())
        self.assertFalse(Path(attachment.file_path).is_absolute())
        self.assertEqual(
            coordination_risk_submission_service.handover_status(contractor.id),
            RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
        )

        coordination_attachment_service.deactivate(attachment.id)
        self.assertTrue(stored.exists())
        reloaded = coordination_attachment_service.get_by_id(attachment.id)
        assert reloaded is not None
        self.assertFalse(reloaded.active)
        self.assertEqual(
            coordination_risk_submission_service.handover_status(contractor.id),
            RISK_SUBMISSION_STATUS_EMAIL_BEFORE,
        )

    def test_open_attachment_resolves_copied_file(self) -> None:
        coordination = self._create_coordination()
        contractor = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Partner",
            abbreviation="PAR",
        )
        source = _TMP / "priloha.odt"
        source.write_text("odt-content")
        attachment = coordination_attachment_service.add_file(
            coordination_id=coordination.id,
            coordination_employer_id=contractor.id,
            source_path=source,
        )
        path = coordination_attachment_service.resolve_path(attachment)
        self.assertEqual(path.read_text(), "odt-content")
        self.assertEqual(attachment.stored_filename, "priloha.odt")

        with patch(
            "moduly.koordinace_bozp.sluzby.coordination_attachment_service.open_local_file",
            return_value=True,
        ) as mocked_open:
            opened = coordination_attachment_service.open_attachment(attachment.id)
        self.assertTrue(opened)
        mocked_open.assert_called_once()
        self.assertEqual(Path(mocked_open.call_args.args[0]), path)

    def test_dialog_tabs(self) -> None:
        coordination = self._create_coordination()
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        labels = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertIn(TAB_WORKPLACES, labels)
        self.assertIn(TAB_RISK_SUBMISSIONS, labels)
        self.assertFalse(dialog.workplaces_tab.content.isHidden())
        self.assertFalse(dialog.risk_submissions_tab.content.isHidden())


if __name__ == "__main__":
    unittest.main()
