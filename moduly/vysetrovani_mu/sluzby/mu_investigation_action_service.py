"""Vytváření vyšetřovacích úkonů z Kontroly spisu MU."""

from __future__ import annotations

from dataclasses import dataclass

from core.shared.constants import ENTITY_MU_INVESTIGATION
from moduly.ukoly.constants import TASK_TYPE_INVESTIGATION_ACTION
from moduly.ukoly.sluzby.task_service import task_service
from moduly.vysetrovani_mu.sluzby.mu_investigation_check import InvestigationCheckResult

_CHECK_PRIORITY_TO_TASK = {
    "low": "Nízká",
    "normal": "Normální",
    "high": "Vysoká",
    "critical": "Kritická",
}


@dataclass(frozen=True)
class InvestigationActionCreateResult:
    created: bool
    task_id: int
    duplicate: bool = False


class MuInvestigationActionService:
    def find_open_duplicate(
        self,
        investigation_id: int,
        result: InvestigationCheckResult,
    ):
        return task_service.find_open_investigation_action(
            investigation_id,
            result.suggested_task_title,
        )

    def create_from_check_result(
        self,
        investigation_id: int,
        result: InvestigationCheckResult,
    ) -> InvestigationActionCreateResult:
        title = (result.suggested_task_title or "").strip()
        if not title:
            raise ValueError("Chybí název doporučeného kroku.")

        existing = self.find_open_duplicate(investigation_id, result)
        if existing is not None:
            return InvestigationActionCreateResult(
                created=False,
                task_id=existing.id,
                duplicate=True,
            )

        task = task_service.create_task(
            title=title,
            description=(result.suggested_task_description or "").strip(),
            priority=_CHECK_PRIORITY_TO_TASK.get(result.suggested_priority, "Normální"),
            source_module=ENTITY_MU_INVESTIGATION,
            source_record_id=investigation_id,
            task_type=TASK_TYPE_INVESTIGATION_ACTION,
            source_check_code=result.check_code,
            requires_verification=False,
        )
        return InvestigationActionCreateResult(created=True, task_id=task.id)


mu_investigation_action_service = MuInvestigationActionService()
