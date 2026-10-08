"""Vytvoření jednoho navazujícího úkolu ze zjištění Státního dozoru."""

from __future__ import annotations

import inspect
import logging
from typing import Any

from core.shared.constants import (
    ENTITY_FINDING,
    ENTITY_STATE_SUPERVISION,
    FINDING_STATUS_ORIGIN_TASK,
)
from core.shared.modely.finding import Finding
from core.shared.sluzby.finding_service import finding_service
from core.shared.sluzby.finding_task_service import finding_task_service
from moduly.agenda.constants import PRIORITY_CRITICAL
from moduly.statni_dozor.constants import (
    FINDING_TASK_ALREADY_LINKED_MESSAGE,
    FINDING_TASK_MISSING_TASK_MESSAGE,
    FINDING_TASK_NOT_FOUND_MESSAGE,
    FINDING_TASK_WRONG_ENTITY_MESSAGE,
)
from moduly.statni_dozor.sluzby.state_supervision_service import (
    StateSupervisionError,
    state_supervision_service,
)
from moduly.ukoly.modely.task import Task
from moduly.ukoly.sluzby.task_service import task_service

logger = logging.getLogger(__name__)

_CREATE_TASK_KEYS = frozenset(
    name
    for name in inspect.signature(task_service.create_task).parameters
    if name not in {"self", "session"}
)


class StateSupervisionFindingTaskService:
    """Jedna transakce: Task + Finding.task_id. Bez automatického volání z editoru."""

    def task_defaults_for_finding(self, finding: Finding) -> dict[str, Any]:
        """Předvyplnění budoucího TaskDialogu. Nemění výchozí hodnoty auditů/prověrek."""
        return {
            "title": finding_task_service._task_title(finding),
            "description": finding_task_service._task_description(finding),
            "priority": PRIORITY_CRITICAL,
            "due_date": finding.due_date,
            "responsible_person_id": finding.responsible_person_id,
            "requires_verification": True,
            "completed": False,
            "source_module": ENTITY_FINDING,
            "source_record_id": finding.id,
        }

    def create_task_for_finding(
        self,
        finding_id: int,
        task_fields: dict[str, Any] | None = None,
    ) -> Task:
        """Vytvoří úkol ze uloženého zjištění Státního dozoru.

        Signatura odpovídá budoucímu ``TaskDialog(create_factory=...)``:
        ``create_task_for_finding(finding_id, data)``.
        """
        incoming = dict(task_fields or {})
        with finding_service.repository.session() as (sess, owns):
            finding = finding_service.repository.get_by_id(
                int(finding_id),
                session=sess,
            )
            self._require_creatable_finding(finding, int(finding_id), session=sess)
            assert finding is not None
            payload = self._prepared_task_fields(finding, incoming)
            task = task_service.create_task(**payload, session=sess)
            if finding.responsible_person_name and not task.responsible_person:
                task.responsible_person = finding.responsible_person_name
            finding_service.update(
                int(finding.id),
                session=sess,
                task_id=task.id,
                status_origin=FINDING_STATUS_ORIGIN_TASK,
            )
            if owns:
                sess.commit()
                sess.refresh(task)
                sess.expunge(task)
            return task

    def _require_creatable_finding(
        self,
        finding: Finding | None,
        finding_id: int,
        *,
        session,
    ) -> None:
        if finding is None or finding.id is None:
            raise StateSupervisionError(FINDING_TASK_NOT_FOUND_MESSAGE)
        if finding.entity_type != ENTITY_STATE_SUPERVISION:
            raise StateSupervisionError(FINDING_TASK_WRONG_ENTITY_MESSAGE)
        parent = state_supervision_service.get_supervision(
            finding.entity_id,
            session=session,
        )
        if parent is None:
            raise StateSupervisionError(
                f"Kontrola státního dozoru {finding.entity_id} neexistuje."
            )
        if finding.task_id is None:
            return
        existing = task_service.repository.get_by_id(
            int(finding.task_id),
            session=session,
        )
        if existing is None:
            logger.error(
                "Zjištění %s odkazuje na neexistující task_id %s.",
                finding.id,
                finding.task_id,
            )
            raise StateSupervisionError(FINDING_TASK_MISSING_TASK_MESSAGE)
        raise StateSupervisionError(FINDING_TASK_ALREADY_LINKED_MESSAGE)

    def _prepared_task_fields(
        self,
        finding: Finding,
        incoming: dict[str, Any],
    ) -> dict[str, Any]:
        defaults = self.task_defaults_for_finding(finding)
        merged: dict[str, Any] = {**defaults}
        for key, value in incoming.items():
            if key in _CREATE_TASK_KEYS:
                merged[key] = value
        if not str(merged.get("title") or "").strip():
            merged["title"] = defaults["title"]
        if not str(merged.get("description") or "").strip():
            merged["description"] = defaults["description"]
        if merged.get("requires_verification") is None:
            merged["requires_verification"] = True
        merged["source_module"] = ENTITY_FINDING
        merged["source_record_id"] = finding.id
        merged["priority"] = PRIORITY_CRITICAL
        return {
            key: value
            for key, value in merged.items()
            if key in _CREATE_TASK_KEYS
        }


state_supervision_finding_task_service = StateSupervisionFindingTaskService()
