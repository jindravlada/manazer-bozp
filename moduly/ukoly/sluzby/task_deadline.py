from datetime import date

from moduly.ukoly.constants import (
    TASK_STATUS_CANCELED,
    TASK_STATUS_CLOSED,
    TASK_STATUS_WAITING_CHECK,
)

_CLOSED_STATUSES = {TASK_STATUS_CLOSED, TASK_STATUS_CANCELED}


def is_waiting_effectiveness_check(task) -> bool:
    """Úkol čeká na kontrolu účinnosti (stav Splněno - čeká na kontrolu)."""
    return getattr(task, "computed_status", None) == TASK_STATUS_WAITING_CHECK


def task_urgency_due_date(task) -> date | None:
    """Rozhodný termín podle aktuální fáze úkolu (Nadcházející i Připomínky)."""
    status = task.computed_status
    if status in _CLOSED_STATUSES:
        return None
    if is_waiting_effectiveness_check(task):
        return task.check_due_date
    return task.due_date
