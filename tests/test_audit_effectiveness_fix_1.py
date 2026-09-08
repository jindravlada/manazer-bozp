"""AUDIT-EFFECTIVENESS-FIX-1: nápravné opatření z auditu v Kontrole účinnosti."""

from __future__ import annotations

import importlib
import os
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.temp_dir_helpers import create_tracked_temp_dir

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)
    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import ITEM_TYPE_TASK, TYPE_LABEL_TASK_CONTROL
    from core.dashboard.attention_service import get_attention_items
    from core.shared.constants import (
        ENTITY_AUDITY,
        ENTITY_FINDING,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_NESHODA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.agenda.constants import ITEM_TYPE_TASK as AGENDA_ITEM_TYPE_TASK
    from moduly.agenda.constants import TYPE_LABEL_TASK, TYPE_LABEL_TASK_CONTROL as AGENDA_TYPE_CONTROL
    from moduly.agenda.sluzby.agenda_service import agenda_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.ukoly.constants import TASK_STATUS_WAITING_CHECK
    from moduly.ukoly.sluzby.task_deadline import is_waiting_effectiveness_check
    from moduly.ukoly.sluzby.task_service import task_service


_COMPLETED = date(2026, 8, 27)
_CHECK_DUE = date(2026, 9, 11)


def _agenda_item(task_id: int):
    matches = [
        item
        for item in agenda_service.get_items()
        if item.item_type == AGENDA_ITEM_TYPE_TASK and item.source_id == task_id
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise AssertionError(f"Očekáván 1 řádek úkolu {task_id}, je {len(matches)}")
    return matches[0]


def _attention_item(task_id: int):
    matches = [
        item
        for item in get_attention_items()
        if item.item_type == ITEM_TYPE_TASK and item.source_id == task_id
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise AssertionError(f"Očekáván 1 řádek úkolu {task_id} v Nadcházejících, je {len(matches)}")
    return matches[0]


class AuditEffectivenessFix1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for task in list(task_service.get_all_tasks()):
            if task.computed_status != "Zrušeno":
                task_service.cancel_task(task.id)
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)

    def _audit_finding_task(self, *, description: str = "Chybí záznam školení"):
        audit = audit_service.create_audit()
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description=description,
            recommended_action=description,
            status=FINDING_STATUS_OTEVRENE,
        )
        task = finding_task_service.create_task_from_finding(finding.id)
        reloaded_finding = finding_service.get_by_id(finding.id)
        assert reloaded_finding is not None
        return audit, reloaded_finding, task

    def test_waiting_check_audit_corrective_appears_in_effectiveness_agenda(self) -> None:
        _audit, finding, task = self._audit_finding_task()
        self.assertEqual(task.source_module, ENTITY_FINDING)
        self.assertEqual(task.source_record_id, finding.id)
        self.assertEqual(finding.task_id, task.id)
        self.assertTrue(finding_task_service.is_audit_finding_corrective_task(task))
        self.assertTrue(task.requires_verification)
        self.assertFalse(is_waiting_effectiveness_check(task))

        task_service.mark_completed(task.id)
        waiting = task_service.get_task_by_id(task.id)
        assert waiting is not None
        self.assertEqual(waiting.computed_status, TASK_STATUS_WAITING_CHECK)
        self.assertTrue(is_waiting_effectiveness_check(waiting))
        self.assertTrue(finding_task_service.is_audit_finding_corrective_task(waiting))

        agenda_item = _agenda_item(waiting.id)
        self.assertIsNotNone(agenda_item)
        self.assertEqual(agenda_item.type_label, AGENDA_TYPE_CONTROL)
        self.assertEqual(agenda_item.status, TASK_STATUS_WAITING_CHECK)
        self.assertEqual(agenda_item.source, "Audit")

        attention_item = _attention_item(waiting.id)
        self.assertIsNotNone(attention_item)
        self.assertEqual(attention_item.type_label, TYPE_LABEL_TASK_CONTROL)
        self.assertEqual(attention_item.status, TASK_STATUS_WAITING_CHECK)
        self.assertEqual(attention_item.subtitle, "Audit")

    def test_active_audit_corrective_is_not_effectiveness_check(self) -> None:
        _audit, _finding, task = self._audit_finding_task(description="Aktivní opatření")
        self.assertEqual(task.computed_status, "Aktivní")
        self.assertFalse(is_waiting_effectiveness_check(task))

        agenda_item = _agenda_item(task.id)
        self.assertIsNotNone(agenda_item)
        self.assertEqual(agenda_item.type_label, TYPE_LABEL_TASK)
        self.assertNotEqual(agenda_item.type_label, AGENDA_TYPE_CONTROL)

        attention_item = _attention_item(task.id)
        self.assertIsNotNone(attention_item)
        self.assertNotEqual(attention_item.type_label, TYPE_LABEL_TASK_CONTROL)

    def test_completed_without_verification_is_not_in_effectiveness_queue(self) -> None:
        _audit, _finding, task = self._audit_finding_task(description="Bez ověření")
        task_service.update_task(
            task.id,
            title=task.title,
            completed=True,
            completed_date=_COMPLETED,
            requires_verification=False,
        )
        closed = task_service.get_task_by_id(task.id)
        assert closed is not None
        self.assertEqual(closed.computed_status, "Ukončeno")
        self.assertFalse(is_waiting_effectiveness_check(closed))
        self.assertIsNone(_agenda_item(closed.id))
        self.assertIsNone(_attention_item(closed.id))

    def test_checked_audit_corrective_leaves_effectiveness_agenda(self) -> None:
        _audit, _finding, task = self._audit_finding_task(description="Po kontrole")
        task_service.mark_completed(task.id)
        waiting = task_service.get_task_by_id(task.id)
        assert waiting is not None
        self.assertIsNotNone(_agenda_item(waiting.id))

        task_service.update_task(
            waiting.id,
            title=waiting.title,
            completed=True,
            completed_date=waiting.completed_date,
            requires_verification=True,
            check_due_date=waiting.check_due_date or _CHECK_DUE,
            checked_date=date(2026, 9, 10),
        )
        closed = task_service.get_task_by_id(waiting.id)
        assert closed is not None
        self.assertEqual(closed.computed_status, "Ukončeno")
        self.assertFalse(is_waiting_effectiveness_check(closed))
        self.assertIsNone(_agenda_item(closed.id))
        self.assertIsNone(_attention_item(closed.id))

    def test_canceled_audit_corrective_is_hidden(self) -> None:
        _audit, _finding, task = self._audit_finding_task(description="Zrušené opatření")
        task_service.mark_completed(task.id)
        task_service.cancel_task(task.id)
        canceled = task_service.get_task_by_id(task.id)
        assert canceled is not None
        self.assertEqual(canceled.computed_status, "Zrušeno")
        self.assertFalse(is_waiting_effectiveness_check(canceled))
        self.assertIsNone(_agenda_item(canceled.id))
        self.assertIsNone(_attention_item(canceled.id))


if __name__ == "__main__":
    unittest.main()
