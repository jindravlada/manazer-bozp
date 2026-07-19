"""UX-COORD-6a – životní cyklus koordinace."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete, text

_TMP = Path(tempfile.mkdtemp(prefix="ux-coord-6a-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import (
        _ensure_bozp_coordinations_table,
        _table_columns,
        initialize_database,
    )

    initialize_database()

    from core.database.session import get_session
    from moduly.koordinace_bozp.constants import (
        BOZP_COORDINATION_STATUS_ARCHIVED,
        BOZP_COORDINATION_STATUS_COMPLETED,
        BOZP_COORDINATION_STATUS_DRAFT,
        BOZP_COORDINATION_STATUS_ISSUED,
        BOZP_COORDINATION_STATUS_LABELS,
        BOZP_COORDINATION_STATUS_READY,
        DEFAULT_BOZP_COORDINATION_STATUS,
        PROTOCOL_WARNING_MISSING_MEETING_PLACE,
        PROTOCOL_WARNING_MISSING_PBP_SNAPSHOT,
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
        CoordinationLifecycleError,
        CoordinationLifecycleNeedsConfirmation,
        coordination_lifecycle_service,
        normalize_coordination_status,
    )
    from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
        coordination_workplace_service,
    )
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service


class UxCoord6aLifecycleTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

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

    def _create_draft(self, **kwargs) -> BozpCoordination:
        payload = {
            "subject": "Životní cyklus",
            "meeting_date": date(2026, 7, 19),
            "place": "Jednací místnost",
        }
        payload.update(kwargs)
        return bozp_coordination_service.create_coordination(**payload)

    def _prepare_for_protocol_gate(self, coordination: BozpCoordination) -> None:
        operation = settings_service.save_workplace(
            name="LC provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        workplace = settings_service.save_workplace(
            name="LC pracoviště",
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
            full_name="Koordinátor Test",
            role="Koordinátor BOZP",
            employer_name=main.company_name or "Hlavní",
        )

    def test_default_status_is_draft(self) -> None:
        created = self._create_draft(status=BOZP_COORDINATION_STATUS_ISSUED)
        self.assertEqual(created.status, DEFAULT_BOZP_COORDINATION_STATUS)
        self.assertEqual(
            BOZP_COORDINATION_STATUS_LABELS[created.status],
            "Rozpracováno",
        )
        columns = _table_columns("bozp_coordinations")
        for name in ("ready_at", "issued_at", "completed_at", "archived_at"):
            self.assertIn(name, columns)

    def test_allowed_and_forbidden_transitions(self) -> None:
        created = self._create_draft()
        self._prepare_for_protocol_gate(created)

        with self.assertRaises(CoordinationLifecycleError):
            coordination_lifecycle_service.transition(
                created.id,
                BOZP_COORDINATION_STATUS_ISSUED,
                confirm_warnings=True,
            )

        with self.assertRaises(CoordinationLifecycleNeedsConfirmation):
            coordination_lifecycle_service.transition(
                created.id,
                BOZP_COORDINATION_STATUS_READY,
            )

        ready = coordination_lifecycle_service.transition(
            created.id,
            BOZP_COORDINATION_STATUS_READY,
            confirm_warnings=True,
        )
        self.assertEqual(ready.status, BOZP_COORDINATION_STATUS_READY)
        self.assertIsNotNone(ready.ready_at)

        issued = coordination_lifecycle_service.transition(
            ready.id,
            BOZP_COORDINATION_STATUS_ISSUED,
            confirm_warnings=True,
        )
        self.assertEqual(issued.status, BOZP_COORDINATION_STATUS_ISSUED)
        self.assertIsNotNone(issued.issued_at)

        completed = coordination_lifecycle_service.transition(
            issued.id,
            BOZP_COORDINATION_STATUS_COMPLETED,
        )
        self.assertEqual(completed.status, BOZP_COORDINATION_STATUS_COMPLETED)
        self.assertIsNotNone(completed.completed_at)

        with self.assertRaises(CoordinationLifecycleError):
            coordination_lifecycle_service.transition(
                completed.id,
                BOZP_COORDINATION_STATUS_ISSUED,
            )

    def test_critical_warning_blocks_ready(self) -> None:
        created = self._create_draft(place="")
        self._prepare_for_protocol_gate(created)
        with self.assertRaises(CoordinationLifecycleBlocked) as ctx:
            coordination_lifecycle_service.transition(
                created.id,
                BOZP_COORDINATION_STATUS_READY,
                confirm_warnings=True,
            )
        codes = {item.code for item in ctx.exception.warnings}
        self.assertIn(PROTOCOL_WARNING_MISSING_MEETING_PLACE, codes)
        reloaded = bozp_coordination_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, BOZP_COORDINATION_STATUS_DRAFT)

    def test_warning_requires_confirmation(self) -> None:
        created = self._create_draft()
        self._prepare_for_protocol_gate(created)
        with self.assertRaises(CoordinationLifecycleNeedsConfirmation) as ctx:
            coordination_lifecycle_service.transition(
                created.id,
                BOZP_COORDINATION_STATUS_READY,
            )
        codes = {item.code for item in ctx.exception.warnings}
        self.assertIn(PROTOCOL_WARNING_MISSING_PBP_SNAPSHOT, codes)
        self.assertFalse(ctx.exception.sensitive)

    def test_issue_only_from_ready(self) -> None:
        created = self._create_draft()
        self._prepare_for_protocol_gate(created)
        with self.assertRaises(CoordinationLifecycleError):
            coordination_lifecycle_service.transition(
                created.id,
                BOZP_COORDINATION_STATUS_ISSUED,
                confirm_warnings=True,
            )

    def test_timestamps_updated_not_cleared_on_return(self) -> None:
        created = self._create_draft()
        self._prepare_for_protocol_gate(created)
        ready = coordination_lifecycle_service.transition(
            created.id,
            BOZP_COORDINATION_STATUS_READY,
            confirm_warnings=True,
        )
        first_ready_at = ready.ready_at
        self.assertIsInstance(first_ready_at, datetime)

        draft_again = coordination_lifecycle_service.transition(
            ready.id,
            BOZP_COORDINATION_STATUS_DRAFT,
        )
        self.assertEqual(draft_again.status, BOZP_COORDINATION_STATUS_DRAFT)
        self.assertEqual(draft_again.ready_at, first_ready_at)

        ready_again = coordination_lifecycle_service.transition(
            draft_again.id,
            BOZP_COORDINATION_STATUS_READY,
            confirm_warnings=True,
        )
        self.assertIsNotNone(ready_again.ready_at)
        assert ready_again.ready_at is not None and first_ready_at is not None
        self.assertGreaterEqual(ready_again.ready_at, first_ready_at)

    def test_archive_and_restore(self) -> None:
        created = self._create_draft()
        archived = coordination_lifecycle_service.transition(
            created.id,
            BOZP_COORDINATION_STATUS_ARCHIVED,
        )
        self.assertEqual(archived.status, BOZP_COORDINATION_STATUS_ARCHIVED)
        self.assertIsNotNone(archived.archived_at)

        with self.assertRaises(CoordinationLifecycleNeedsConfirmation):
            coordination_lifecycle_service.transition(
                archived.id,
                BOZP_COORDINATION_STATUS_DRAFT,
            )

        restored = coordination_lifecycle_service.transition(
            archived.id,
            BOZP_COORDINATION_STATUS_DRAFT,
            confirm_sensitive=True,
        )
        self.assertEqual(restored.status, BOZP_COORDINATION_STATUS_DRAFT)
        self.assertIsNotNone(restored.archived_at)

    def test_legacy_status_mapping(self) -> None:
        self.assertEqual(normalize_coordination_status("in_progress"), "draft")
        self.assertEqual(normalize_coordination_status("prepared"), "ready")
        self.assertEqual(normalize_coordination_status("active"), "ready")
        self.assertEqual(normalize_coordination_status("published"), "issued")
        self.assertEqual(normalize_coordination_status("done"), "completed")
        self.assertEqual(normalize_coordination_status("weird_old"), "draft")

        created = self._create_draft()
        with get_session() as session:
            session.execute(
                text(
                    "UPDATE bozp_coordinations SET status = :status WHERE id = :id"
                ),
                {"status": "in_progress", "id": created.id},
            )
            session.commit()

        _ensure_bozp_coordinations_table()
        reloaded = bozp_coordination_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, BOZP_COORDINATION_STATUS_DRAFT)

        with get_session() as session:
            session.execute(
                text(
                    "UPDATE bozp_coordinations SET status = :status WHERE id = :id"
                ),
                {"status": "unknown_legacy", "id": created.id},
            )
            session.commit()
        _ensure_bozp_coordinations_table()
        reloaded = bozp_coordination_service.get_by_id(created.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, BOZP_COORDINATION_STATUS_DRAFT)


if __name__ == "__main__":
    unittest.main()
