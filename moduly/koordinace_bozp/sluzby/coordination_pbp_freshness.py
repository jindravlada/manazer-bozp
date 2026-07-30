"""Dynamická kontrola aktuálnosti přílohy PBP (COORD-007a).

Stav se neukládá do databáze – počítá se z posledního snapshotu a současných
dat Registru rizik. Kontrola nevytváří ODT ani novou revizi.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from moduly.koordinace_bozp.constants import (
    BOZP_COORDINATION_STATUS_DRAFT,
    PBP_FILTER_ALL,
    PBP_FILTER_CURRENT,
    PBP_FILTER_MISSING,
    PBP_FILTER_NEEDS_UPDATE,
    PBP_FILTER_UNVERIFIABLE,
    PBP_FRESHNESS_COLORS,
    PBP_FRESHNESS_CURRENT,
    PBP_FRESHNESS_DETAIL_MESSAGES,
    PBP_FRESHNESS_LABELS,
    PBP_FRESHNESS_MISSING,
    PBP_FRESHNESS_NEEDS_UPDATE,
    PBP_FRESHNESS_SKIPPED,
    PBP_FRESHNESS_STATES,
    PBP_FRESHNESS_TOOLTIPS,
    PBP_FRESHNESS_UNVERIFIABLE,
)
from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
from moduly.koordinace_bozp.sluzby.coordination_pbp_attachment_service import (
    CoordinationPbpAttachmentError,
    content_hash_for_rules,
    coordination_pbp_attachment_service,
)


@dataclass(frozen=True)
class PbpFreshnessResult:
    state: str
    label: str
    detail_message: str
    tooltip: str
    color: str
    current_hash: str | None = None
    snapshot_hash: str | None = None
    rules_count: int | None = None


def _result_for_state(
    state: str,
    *,
    current_hash: str | None = None,
    snapshot_hash: str | None = None,
    rules_count: int | None = None,
) -> PbpFreshnessResult:
    return PbpFreshnessResult(
        state=state,
        label=PBP_FRESHNESS_LABELS[state],
        detail_message=PBP_FRESHNESS_DETAIL_MESSAGES[state],
        tooltip=PBP_FRESHNESS_TOOLTIPS[state],
        color=PBP_FRESHNESS_COLORS[state],
        current_hash=current_hash,
        snapshot_hash=snapshot_hash,
        rules_count=rules_count,
    )


def is_pbp_freshness_eligible(
    coordination: BozpCoordination,
    *,
    today: date | None = None,
) -> bool:
    """Kontrola jen u aktivních, rozpracovaných a dosud platných koordinací."""
    if not coordination.active:
        return False
    status = (coordination.status or "").strip().lower()
    if status not in (BOZP_COORDINATION_STATUS_DRAFT, "in_progress", ""):
        return False
    if coordination.valid_to is None:
        return False
    current = today or date.today()
    return coordination.valid_to >= current


def evaluate_pbp_freshness(
    coordination: BozpCoordination,
    *,
    today: date | None = None,
) -> PbpFreshnessResult:
    """Porovná poslední snapshot s aktuálním obsahem z Registru rizik (bez zápisu)."""
    if not is_pbp_freshness_eligible(coordination, today=today):
        return _result_for_state(PBP_FRESHNESS_SKIPPED)

    snapshot = coordination_pbp_attachment_service.get_current(coordination.id)
    snapshot_hash = snapshot.content_hash if snapshot is not None else None

    try:
        rules = coordination_pbp_attachment_service.collect_rules_for_coordination(
            coordination.id
        )
    except CoordinationPbpAttachmentError:
        return _result_for_state(
            PBP_FRESHNESS_UNVERIFIABLE,
            snapshot_hash=snapshot_hash,
        )

    if not rules:
        return _result_for_state(
            PBP_FRESHNESS_UNVERIFIABLE,
            snapshot_hash=snapshot_hash,
            rules_count=0,
        )

    digest = content_hash_for_rules(rules)
    if snapshot is None:
        return _result_for_state(
            PBP_FRESHNESS_MISSING,
            current_hash=digest,
            rules_count=len(rules),
        )
    if snapshot.content_hash == digest:
        return _result_for_state(
            PBP_FRESHNESS_CURRENT,
            current_hash=digest,
            snapshot_hash=snapshot_hash,
            rules_count=len(rules),
        )
    return _result_for_state(
        PBP_FRESHNESS_NEEDS_UPDATE,
        current_hash=digest,
        snapshot_hash=snapshot_hash,
        rules_count=len(rules),
    )


def pbp_freshness_sort_order(state: str) -> int:
    try:
        return PBP_FRESHNESS_STATES.index(state)
    except ValueError:
        return len(PBP_FRESHNESS_STATES)


def pbp_freshness_color(state: str) -> str:
    return PBP_FRESHNESS_COLORS.get(state, PBP_FRESHNESS_COLORS[PBP_FRESHNESS_SKIPPED])


class PbpFreshnessCache:
    """Krátkodobá cache v rámci otevřeného okna – bez zápisu do DB."""

    def __init__(self) -> None:
        self._cache: dict[int, PbpFreshnessResult] = {}

    def clear(self) -> None:
        self._cache.clear()

    def evaluate(
        self,
        coordination: BozpCoordination,
        *,
        today: date | None = None,
    ) -> PbpFreshnessResult:
        cached = self._cache.get(coordination.id)
        if cached is not None:
            return cached
        result = evaluate_pbp_freshness(coordination, today=today)
        self._cache[coordination.id] = result
        return result


def filter_by_pbp_freshness(
    items: list[BozpCoordination],
    pbp_filter: str = PBP_FILTER_ALL,
    *,
    today: date | None = None,
    cache: PbpFreshnessCache | None = None,
) -> list[BozpCoordination]:
    """Filtr seznamu. Ukončené koordinace se do problémových filtrů nedostanou."""
    if pbp_filter in ("", PBP_FILTER_ALL, None):
        return list(items)

    allowed = {
        PBP_FILTER_CURRENT,
        PBP_FILTER_NEEDS_UPDATE,
        PBP_FILTER_MISSING,
        PBP_FILTER_UNVERIFIABLE,
    }
    if pbp_filter not in allowed:
        raise ValueError("Neplatný filtr přílohy PBP.")

    resolver = cache or PbpFreshnessCache()
    return [
        item
        for item in items
        if resolver.evaluate(item, today=today).state == pbp_filter
    ]
