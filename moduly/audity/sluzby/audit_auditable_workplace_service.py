"""Jednotný filtr auditovatelných provozů pro modul Audity.

AUDIT-AUDITABLE-WORKPLACES-1: active + typ Provoz (operation) + audit_enabled.
"""

from __future__ import annotations

from moduly.audity.constants import AUDITABLE_WORKPLACE_REQUIRED_MESSAGE
from moduly.nastaveni.constants.workplace_hierarchy_constants import (
    WORKPLACE_ITEM_TYPE_OPERATION,
)
from moduly.nastaveni.modely.workplace import Workplace
from moduly.nastaveni.sluzby.settings_service import settings_service

__all__ = [
    "AUDITABLE_WORKPLACE_REQUIRED_MESSAGE",
    "is_auditable_workplace",
    "is_auditable_workplace_id",
    "list_auditable_workplaces",
    "require_auditable_workplace_id",
]


def is_auditable_workplace(workplace: Workplace | None) -> bool:
    """True, pokud je položka aktivní Provoz se zapnutým Auditovat."""
    if workplace is None:
        return False
    if not bool(workplace.active):
        return False
    item_type = str(getattr(workplace, "item_type", "") or "").strip()
    if item_type != WORKPLACE_ITEM_TYPE_OPERATION:
        return False
    return bool(getattr(workplace, "audit_enabled", False))


def is_auditable_workplace_id(workplace_id: int | None) -> bool:
    if workplace_id is None or int(workplace_id) <= 0:
        return False
    workplace = settings_service.get_workplace_by_id(int(workplace_id))
    return is_auditable_workplace(workplace)


def require_auditable_workplace_id(workplace_id: int | None) -> Workplace:
    """Vrátí auditovatelný Workplace, jinak ValueError se srozumitelnou zprávou."""
    if workplace_id is None or int(workplace_id) <= 0:
        raise ValueError(AUDITABLE_WORKPLACE_REQUIRED_MESSAGE)
    workplace = settings_service.get_workplace_by_id(int(workplace_id))
    if not is_auditable_workplace(workplace):
        raise ValueError(AUDITABLE_WORKPLACE_REQUIRED_MESSAGE)
    assert workplace is not None
    return workplace


def list_auditable_workplaces(
    *,
    include_inactive: bool = False,
) -> list[Workplace]:
    """Seznam provozů použitelných jako nové cíle auditu / mimořádného ověření."""
    workplaces = settings_service.get_workplaces(include_inactive=include_inactive)
    return [
        workplace
        for workplace in workplaces
        if is_auditable_workplace(workplace)
    ]
