"""Porovnání aktuálních Pravidel bezpečné práce s předchozím vydáním (PBP-5b)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime

from moduly.rizeni_rizik.modely.pravidla_bezpecne_prace_edition import (
    PravidlaBezpecnePraceEdition,
    PravidlaBezpecnePraceEditionRule,
)
from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
    PravidloBezpecnePrace,
)


@dataclass(frozen=True)
class PreviousPravidloSnapshot:
    """Pravidlo z předchozího vydání (pro zrušená / změněná)."""

    display_text: str
    normalized_text: str
    severity: str
    sort_order: int
    measure_id: int | None = None
    measure_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class ChangedPravidloBezpecnePrace:
    """Změněné pravidlo se spolehlivou vazbou na stejné opatření."""

    previous_text: str
    current_text: str
    severity: str
    sort_order: int
    measure_id: int | None = None
    previous_normalized_text: str = ""
    current: PravidloBezpecnePrace | None = None


@dataclass
class PravidlaBezpecnePraceComparison:
    """Výsledek porovnání aktuálních pravidel s předchozím vydáním."""

    new_rules: list[PravidloBezpecnePrace] = field(default_factory=list)
    changed_rules: list[ChangedPravidloBezpecnePrace] = field(default_factory=list)
    removed_rules: list[PreviousPravidloSnapshot] = field(default_factory=list)
    unchanged_rules: list[PravidloBezpecnePrace] = field(default_factory=list)
    previous_edition_id: int | None = None
    previous_issued_at: datetime | None = None
    is_first_edition: bool = False

    @property
    def has_changes(self) -> bool:
        return bool(self.new_rules or self.changed_rules or self.removed_rules)


def compare_rules_to_edition(
    current_rules: list[PravidloBezpecnePrace],
    previous: PravidlaBezpecnePraceEdition | None,
) -> PravidlaBezpecnePraceComparison:
    """Porovná aktuální pravidla s snapshotem předchozího vydání.

    První vydání: všechna pravidla jsou nezměněná, bez změnových sekcí.
    """
    if previous is None:
        return PravidlaBezpecnePraceComparison(
            unchanged_rules=list(current_rules),
            is_first_edition=True,
            previous_edition_id=None,
        )

    previous_snaps = [_snapshot_from_edition_rule(rule) for rule in previous.rules]
    previous_by_norm = {snap.normalized_text: snap for snap in previous_snaps}

    unchanged: list[PravidloBezpecnePrace] = []
    remaining_current: list[PravidloBezpecnePrace] = []
    matched_previous_norms: set[str] = set()

    for rule in current_rules:
        norm = _normalized_text(rule)
        if norm in previous_by_norm:
            unchanged.append(rule)
            matched_previous_norms.add(norm)
        else:
            remaining_current.append(rule)

    remaining_previous = [
        snap
        for snap in previous_snaps
        if snap.normalized_text not in matched_previous_norms
    ]

    changed: list[ChangedPravidloBezpecnePrace] = []
    used_previous: set[int] = set()
    used_current: set[int] = set()

    for current_index, current in enumerate(remaining_current):
        current_ids = _current_measure_ids(current)
        if not current_ids:
            continue
        for previous_index, previous_snap in enumerate(remaining_previous):
            if previous_index in used_previous:
                continue
            if not previous_snap.measure_ids:
                continue
            if current_ids.isdisjoint(previous_snap.measure_ids):
                continue
            shared = sorted(current_ids & set(previous_snap.measure_ids))
            changed.append(
                ChangedPravidloBezpecnePrace(
                    previous_text=previous_snap.display_text,
                    current_text=current.text,
                    severity=current.severity,
                    sort_order=current_index + 1,  # provisional; fixed below
                    measure_id=shared[0],
                    previous_normalized_text=previous_snap.normalized_text,
                    current=current,
                )
            )
            used_previous.add(previous_index)
            used_current.add(current_index)
            break

    # Pořadí změněných podle pořadí v aktuálním dokumentu.
    current_order = {id(rule): index for index, rule in enumerate(current_rules, start=1)}
    fixed_changed: list[ChangedPravidloBezpecnePrace] = []
    for item in changed:
        order = current_order.get(id(item.current), item.sort_order) if item.current else item.sort_order
        fixed_changed.append(
            ChangedPravidloBezpecnePrace(
                previous_text=item.previous_text,
                current_text=item.current_text,
                severity=item.severity,
                sort_order=order,
                measure_id=item.measure_id,
                previous_normalized_text=item.previous_normalized_text,
                current=item.current,
            )
        )
    fixed_changed.sort(key=lambda item: item.sort_order)

    new_rules = [
        rule
        for index, rule in enumerate(remaining_current)
        if index not in used_current
    ]
    removed_rules = [
        snap
        for index, snap in enumerate(remaining_previous)
        if index not in used_previous
    ]

    return PravidlaBezpecnePraceComparison(
        new_rules=new_rules,
        changed_rules=fixed_changed,
        removed_rules=removed_rules,
        unchanged_rules=unchanged,
        previous_edition_id=previous.id,
        previous_issued_at=previous.issued_at,
        is_first_edition=False,
    )


def _normalized_text(rule: PravidloBezpecnePrace) -> str:
    return rule.text.casefold()


def _current_measure_ids(rule: PravidloBezpecnePrace) -> set[int]:
    ids: set[int] = set()
    if rule.measure_id:
        ids.add(rule.measure_id)
    for source in rule.sources:
        if source.measure_id:
            ids.add(source.measure_id)
    return ids


def _snapshot_from_edition_rule(
    rule: PravidlaBezpecnePraceEditionRule,
) -> PreviousPravidloSnapshot:
    measure_ids: list[int] = []
    if rule.measure_id:
        measure_ids.append(rule.measure_id)
    try:
        sources = json.loads(rule.sources_json or "[]")
    except json.JSONDecodeError:
        sources = []
    for source in sources:
        measure_id = source.get("measure_id") if isinstance(source, dict) else None
        if measure_id and measure_id not in measure_ids:
            measure_ids.append(int(measure_id))
    return PreviousPravidloSnapshot(
        display_text=rule.display_text,
        normalized_text=rule.normalized_text,
        severity=rule.severity,
        sort_order=rule.sort_order,
        measure_id=rule.measure_id,
        measure_ids=tuple(measure_ids),
    )
