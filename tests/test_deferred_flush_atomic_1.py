"""AUDIT-DEFERRED-ATOMIC-1: atomický flush zjištění a úkolů u auditů a prověrek."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="deferred-flush-atomic-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    import core.shared.sluzby.deferred_finding_task_flush as flush_module
    from core.shared.constants import (
        ENTITY_AUDITY,
        ENTITY_FINDING,
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_NESHODA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.sluzby.audit_deferred_edits import AuditDeferredEdits
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.proverky.sluzby.inspection_deferred_edits import InspectionDeferredEdits
    from moduly.ukoly.sluzby.task_service import task_service


def _finding(entity_type: str, entity_id: int, label: str, *, person_id: int | None = None):
    return finding_service.create(
        entity_type,
        entity_id,
        finding_type=FINDING_TYPE_NESHODA,
        description=label,
        recommended_action=f"opatření {label}",
        status=FINDING_STATUS_OTEVRENE,
        source_control_point_id=label,
        responsible_person_id=person_id,
        responsible_person_name="Jan Novak" if person_id else "",
    )


def _stage_new(deferred, entity_type: str, entity_id: int, label: str, *, person_id: int | None = None) -> int:
    return deferred.stage_finding_create(
        entity_type,
        entity_id,
        {
            "finding_type": FINDING_TYPE_NESHODA,
            "description": label,
            "recommended_action": f"opatření {label}",
            "status": FINDING_STATUS_OTEVRENE,
            "source_control_point_id": label,
            "responsible_person_id": person_id,
            "responsible_person_name": "Jan Novak" if person_id else "",
        },
    )


def _ids_for(entity_type: str, entity_id: int, label: str) -> list[int]:
    return [
        finding.id
        for finding in finding_service.get_for_entity(entity_type, entity_id)
        if finding.source_control_point_id == label
    ]


def _task_ids(finding_id: int) -> list[int]:
    return [
        task.id
        for task in task_service.list_by_source(ENTITY_FINDING, finding_id)
    ]


class DeferredFlushAtomicTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.worker = settings_service.save_worker(
            first_name="Jan",
            last_name="Novak",
            title_before="",
            title_after="",
            position="",
            phone="",
            email="",
            active=True,
            performs_controls=False,
        )

    def test_audit_incident_then_second_save(self) -> None:
        self._assert_incident(AuditDeferredEdits, ENTITY_AUDITY, 801)

    def test_inspection_incident_then_second_save(self) -> None:
        self._assert_incident(InspectionDeferredEdits, ENTITY_PROVERKY, 803)

    def test_audit_rollback_then_retry(self) -> None:
        self._assert_rollback(AuditDeferredEdits, ENTITY_AUDITY, 802)

    def test_inspection_rollback_then_retry(self) -> None:
        self._assert_rollback(InspectionDeferredEdits, ENTITY_PROVERKY, 804)

    def _prepare(self, deferred_cls, entity_type: str, entity_id: int):
        deferred = deferred_cls()
        person_id = int(self.worker.id)
        finding_a = _finding(entity_type, entity_id, "A")
        finding_b = _finding(entity_type, entity_id, "B")
        finding_c = _finding(entity_type, entity_id, "C")
        task_a = finding_task_service.create_task_from_finding(finding_a.id)
        task_b = finding_task_service.create_task_from_finding(finding_b.id)

        deferred.stage_task_from_finding(finding_c.id)
        _stage_new(deferred, entity_type, entity_id, "D", person_id=person_id)
        temp_d = next(
            temp_id
            for temp_id, data in deferred._finding_creates.items()
            if data.get("source_control_point_id") == "D"
        )
        deferred.stage_task_from_finding(temp_d)
        _stage_new(deferred, entity_type, entity_id, "E")
        _stage_new(deferred, entity_type, entity_id, "F")
        deferred.stage_finding_delete(finding_c.id)

        temp_g = _stage_new(deferred, entity_type, entity_id, "G")
        deferred.stage_task_from_finding(temp_g)
        deferred.stage_finding_delete(temp_g)

        pending_findings = {
            int(pending["finding_id"]) for pending in deferred._task_creates.values()
        }
        self.assertNotIn(finding_c.id, pending_findings)
        self.assertNotIn(temp_g, pending_findings)
        self.assertIn(temp_d, pending_findings)
        return deferred, finding_a, finding_b, finding_c, task_a, task_b

    def _assert_incident(self, deferred_cls, entity_type: str, entity_id: int) -> None:
        deferred, finding_a, finding_b, finding_c, task_a, task_b = self._prepare(
            deferred_cls,
            entity_type,
            entity_id,
        )
        deferred.flush(entity_id=entity_id)

        self.assertEqual(_ids_for(entity_type, entity_id, "C"), [])
        self.assertEqual(_ids_for(entity_type, entity_id, "G"), [])
        self.assertEqual(len(_ids_for(entity_type, entity_id, "D")), 1)
        self.assertEqual(len(_ids_for(entity_type, entity_id, "E")), 1)
        self.assertEqual(len(_ids_for(entity_type, entity_id, "F")), 1)
        self.assertEqual(_task_ids(finding_c.id), [])
        self.assertEqual(_task_ids(finding_a.id), [task_a.id])
        self.assertEqual(_task_ids(finding_b.id), [task_b.id])
        finding_d_id = _ids_for(entity_type, entity_id, "D")[0]
        self.assertEqual(len(_task_ids(finding_d_id)), 1)
        self.assertFalse(deferred.has_changes())

        deferred.flush(entity_id=entity_id)

        self.assertEqual(len(_ids_for(entity_type, entity_id, "D")), 1)
        self.assertEqual(len(_ids_for(entity_type, entity_id, "E")), 1)
        self.assertEqual(len(_ids_for(entity_type, entity_id, "F")), 1)
        self.assertEqual(_task_ids(finding_a.id), [task_a.id])
        self.assertEqual(_task_ids(finding_b.id), [task_b.id])
        self.assertEqual(len(_task_ids(finding_d_id)), 1)

        deferred._task_creates[-5] = {
            "finding_id": finding_a.id,
            "data": {
                "title": task_a.title,
                "description": task_a.description or "",
                "priority": "Normální",
                "due_date": task_a.due_date,
                "remind_from": None,
                "responsible_person_id": None,
                "workplace_id": None,
                "completed": False,
                "completed_date": None,
                "requires_verification": True,
                "check_due_date": None,
                "checked_date": None,
                "checked_by_id": None,
                "canceled": False,
                "note": "",
            },
        }
        deferred.flush(entity_id=entity_id)
        self.assertEqual(_task_ids(finding_a.id), [task_a.id])

    def _assert_rollback(self, deferred_cls, entity_type: str, entity_id: int) -> None:
        deferred, finding_a, finding_b, finding_c, task_a, task_b = self._prepare(
            deferred_cls,
            entity_type,
            entity_id,
        )
        deferred.stage_finding_update(finding_a.id, {"description": "A-zmena"})
        before = {
            "A": finding_service.get_by_id(finding_a.id).description,
            "labels": sorted(
                finding.source_control_point_id
                for finding in finding_service.get_for_entity(entity_type, entity_id)
            ),
            "tasks_a": _task_ids(finding_a.id),
            "tasks_b": _task_ids(finding_b.id),
            "tasks_c": _task_ids(finding_c.id),
        }

        with patch.object(flush_module.finding_service, "delete", side_effect=RuntimeError("flush-boom")):
            with self.assertRaises(RuntimeError):
                deferred.flush(entity_id=entity_id)

        self.assertEqual(finding_service.get_by_id(finding_a.id).description, before["A"])
        self.assertEqual(
            sorted(
                finding.source_control_point_id
                for finding in finding_service.get_for_entity(entity_type, entity_id)
            ),
            before["labels"],
        )
        self.assertEqual(_ids_for(entity_type, entity_id, "D"), [])
        self.assertEqual(_ids_for(entity_type, entity_id, "E"), [])
        self.assertEqual(_ids_for(entity_type, entity_id, "F"), [])
        self.assertEqual(_task_ids(finding_a.id), before["tasks_a"])
        self.assertEqual(_task_ids(finding_b.id), before["tasks_b"])
        self.assertEqual(_task_ids(finding_c.id), before["tasks_c"])
        self.assertIn(finding_c.id, deferred._finding_deletes)
        self.assertTrue(any(
            data.get("source_control_point_id") == "D"
            for data in deferred._finding_creates.values()
        ))
        self.assertTrue(deferred.has_changes())

        deferred.flush(entity_id=entity_id)

        self.assertEqual(finding_service.get_by_id(finding_a.id).description, "A-zmena")
        self.assertEqual(_ids_for(entity_type, entity_id, "C"), [])
        self.assertEqual(len(_ids_for(entity_type, entity_id, "D")), 1)
        self.assertEqual(len(_ids_for(entity_type, entity_id, "E")), 1)
        self.assertEqual(len(_ids_for(entity_type, entity_id, "F")), 1)
        self.assertEqual(_task_ids(finding_c.id), [])
        self.assertEqual(_task_ids(finding_a.id), [task_a.id])
        self.assertEqual(_task_ids(finding_b.id), [task_b.id])
        self.assertEqual(len(_task_ids(_ids_for(entity_type, entity_id, "D")[0])), 1)

        deferred.flush(entity_id=entity_id)
        self.assertEqual(len(_ids_for(entity_type, entity_id, "D")), 1)
        self.assertEqual(len(_ids_for(entity_type, entity_id, "E")), 1)
        self.assertEqual(len(_ids_for(entity_type, entity_id, "F")), 1)
        self.assertEqual(len(_task_ids(_ids_for(entity_type, entity_id, "D")[0])), 1)


if __name__ == "__main__":
    unittest.main()
