"""Uzavření případu pracovního úrazu podle stavu ZoÚ a ukončení DPN."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
    AccidentLike,
    has_pn,
    is_dpn_ended,
    obligation_rows_for_summary,
    row_is_done,
)


CASE_CLOSED_YES = "ANO"
CASE_CLOSED_NO = "NE"
CLOSURE_DATE_LABEL = "Datum uzavření"
CASE_CLOSED_LABEL = "Případ uzavřen"

DPN_NOT_ENDED_CLOSURE_MESSAGE = (
    "DPN dosud není ukončena. Případ nelze uzavřít, dokud není vyplněno "
    "datum konce DPN."
)

ZOU_NOT_DONE_CLOSURE_INTRO = (
    "Případ nelze uzavřít, protože nejsou splněny všechny povinnosti "
    "záznamu o úrazu:"
)

CLOSURE_BLOCKED_TITLE = "Případ nelze uzavřít"


@dataclass(frozen=True)
class AccidentCaseClosureCheck:
    allowed: bool
    dpn_not_ended: bool = False
    unfinished_labels: tuple[str, ...] = ()

    @property
    def message(self) -> str:
        parts: list[str] = []
        if self.dpn_not_ended:
            parts.append(DPN_NOT_ENDED_CLOSURE_MESSAGE)
        if self.unfinished_labels:
            items = "\n".join(f"• {label}" for label in self.unfinished_labels)
            parts.append(f"{ZOU_NOT_DONE_CLOSURE_INTRO}\n\n{items}")
        return "\n\n".join(parts)


def is_saved_case_closed(
    saved_data: dict[str, Any] | None,
    accident: AccidentLike | None = None,
) -> bool:
    if str((saved_data or {}).get("admin_pripad_uzavren") or "").strip().upper() == CASE_CLOSED_YES:
        return True
    return bool(getattr(accident, "closed", False)) if accident is not None else False


def zou_unfinished_obligation_labels(
    accident: AccidentLike | None,
    saved_data: dict[str, Any] | None,
    *,
    union_organization_active: bool | None = None,
) -> tuple[str, ...]:
    """Povinnosti vstupující do ZoÚ, které ještě nejsou splněné."""
    labels: list[str] = []
    seen: set[str] = set()
    for row in obligation_rows_for_summary(
        accident,
        saved_data,
        union_organization_active=union_organization_active,
    ):
        if row_is_done(row):
            continue
        label = str(row.get("nazev") or row.get("key") or "").strip()
        if not label or label in seen:
            continue
        seen.add(label)
        labels.append(label)
    return tuple(labels)


def evaluate_accident_case_closure(
    accident: AccidentLike | None,
    *,
    saved_data: dict[str, Any] | None = None,
    today: date | None = None,
    union_organization_active: bool | None = None,
) -> AccidentCaseClosureCheck:
    """Nový pokus o uzavření. Historicky uzavřené případy se zde neposuzují."""
    del today  # čekající i po termínu blokují stejně
    dpn_not_ended = has_pn(accident) and not is_dpn_ended(
        getattr(accident, "dpn_do", None) if accident is not None else None
    )
    unfinished = zou_unfinished_obligation_labels(
        accident,
        saved_data,
        union_organization_active=union_organization_active,
    )
    return AccidentCaseClosureCheck(
        allowed=not dpn_not_ended and not unfinished,
        dpn_not_ended=dpn_not_ended,
        unfinished_labels=unfinished,
    )
