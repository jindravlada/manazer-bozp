"""Koordinované rozdělení řídicích procesů mezi audity provozů.

Každý provoz během svého cyklu dostane každý požadovaný proces právě jednou
a na jednu návštěvu připadne stejný počet procesů jako při původním
rovnoměrném rozdělení. Výběr konkrétních procesů navíc zohledňuje, kolikrát
už jsou v tom samém kalendářním roce naplánované u ostatních provozů, aby
provozy nezačínaly všechny od stejného začátku seznamu.
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PlannedVisitSlot:
    visit_id: int
    year: int | None
    month: int | None


@dataclass(frozen=True)
class WorkplaceProcessPlan:
    """Provoz v pořadí, podle kterého se při shodě střídá vůči ostatním."""

    ordinal: int
    visits: tuple[PlannedVisitSlot, ...]
    fill: bool = True
    assigned_process_ids: frozenset[str] = frozenset()
    assigned_by_visit: tuple[tuple[int, frozenset[str]], ...] = ()


@dataclass(frozen=True)
class PlannedProcessAssignment:
    visit_id: int
    process_id: str


@dataclass(frozen=True)
class _VisitFill:
    year_missing: int
    year_sort: int
    month_missing: int
    month_sort: int
    ordinal: int
    visit_id: int
    workplace_index: int
    capacity: int
    offset: int
    year: int | None


def per_visit_process_quotas(process_count: int, visit_count: int) -> list[int]:
    """Stejné počty jako původní rozdělení ``index % počet návštěv``."""

    if visit_count <= 0:
        return []
    if process_count <= 0:
        return [0] * visit_count
    base, extra = divmod(process_count, visit_count)
    return [base + (1 if index < extra else 0) for index in range(visit_count)]


def plan_coordinated_process_distribution(
    process_ids: Sequence[str],
    workplaces: Sequence[WorkplaceProcessPlan],
) -> tuple[PlannedProcessAssignment, ...]:
    ordered_ids = _unique_process_ids(process_ids)
    index_by_id = {process_id: index for index, process_id in enumerate(ordered_ids)}
    process_count = len(ordered_ids)
    known_ids = set(ordered_ids)

    visit_year = {
        visit.visit_id: visit.year
        for workplace in workplaces
        for visit in workplace.visits
    }
    year_counts: dict[tuple[int | None, str], int] = {}
    for workplace in workplaces:
        for visit_id, assigned_ids in workplace.assigned_by_visit:
            year = visit_year.get(visit_id)
            for process_id in assigned_ids:
                if process_id not in known_ids:
                    continue
                key = (year, process_id)
                year_counts[key] = year_counts.get(key, 0) + 1

    remaining_by_workplace: dict[int, list[str]] = {}
    work: list[_VisitFill] = []

    for workplace_index, workplace in enumerate(workplaces):
        visits = tuple(
            sorted(
                workplace.visits,
                key=lambda item: (
                    item.year is None,
                    item.year or 0,
                    item.month is None,
                    item.month or 0,
                    item.visit_id,
                ),
            )
        )
        if not workplace.fill or not visits or process_count == 0:
            continue

        assigned = {
            process_id
            for process_id in workplace.assigned_process_ids
            if process_id in known_ids
        }
        remaining = [process_id for process_id in ordered_ids if process_id not in assigned]
        remaining_by_workplace[workplace_index] = remaining

        assigned_on_visit = {
            visit_id: {process_id for process_id in process_ids_on_visit if process_id in known_ids}
            for visit_id, process_ids_on_visit in workplace.assigned_by_visit
        }
        quotas = per_visit_process_quotas(process_count, len(visits))
        occupied = [
            len(assigned_on_visit.get(visit.visit_id, set()))
            for visit in visits
        ]
        capacities = _fit_capacities(quotas, occupied, len(remaining))
        offset = _rotation_offset(workplace.ordinal, process_count, len(visits))

        for visit_index, visit in enumerate(visits):
            capacity = capacities[visit_index]
            if capacity <= 0:
                continue
            work.append(
                _VisitFill(
                    year_missing=1 if visit.year is None else 0,
                    year_sort=visit.year or 0,
                    month_missing=1 if visit.month is None else 0,
                    month_sort=visit.month or 0,
                    ordinal=workplace.ordinal,
                    visit_id=visit.visit_id,
                    workplace_index=workplace_index,
                    capacity=capacity,
                    offset=offset,
                    year=visit.year,
                )
            )

    work.sort(
        key=lambda item: (
            item.year_missing,
            item.year_sort,
            item.month_missing,
            item.month_sort,
            item.ordinal,
            item.visit_id,
        )
    )
    assignments: list[PlannedProcessAssignment] = []

    for item in work:
        remaining = remaining_by_workplace[item.workplace_index]
        if not remaining or item.capacity <= 0:
            continue

        chosen = sorted(
            remaining,
            key=lambda process_id: _selection_rank(
                process_id,
                year=item.year,
                offset=item.offset,
                process_count=process_count,
                index_by_id=index_by_id,
                year_counts=year_counts,
            ),
        )[: item.capacity]
        for process_id in sorted(chosen, key=index_by_id.__getitem__):
            assignments.append(
                PlannedProcessAssignment(visit_id=item.visit_id, process_id=process_id)
            )
            key = (item.year, process_id)
            year_counts[key] = year_counts.get(key, 0) + 1
            remaining.remove(process_id)

    for remaining in remaining_by_workplace.values():
        if remaining:
            raise ValueError(
                "Rozdělení procesů nepokrylo všechny procesy provozu."
            )

    return tuple(assignments)


def _unique_process_ids(process_ids: Sequence[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for process_id in process_ids:
        if process_id in seen:
            continue
        seen.add(process_id)
        ordered.append(process_id)
    return ordered


def _fit_capacities(
    quotas: list[int],
    occupied: list[int],
    remaining_count: int,
) -> list[int]:
    capacities = [
        max(0, quota - used)
        for quota, used in zip(quotas, occupied, strict=True)
    ]
    delta = remaining_count - sum(capacities)
    if delta > 0 and capacities:
        index = 0
        while delta > 0:
            capacities[index % len(capacities)] += 1
            index += 1
            delta -= 1
    elif delta < 0:
        surplus = -delta
        for index in range(len(capacities) - 1, -1, -1):
            if surplus <= 0:
                break
            take = min(capacities[index], surplus)
            capacities[index] -= take
            surplus -= take
    return capacities


def _rotation_offset(ordinal: int, process_count: int, visit_count: int) -> int:
    if process_count <= 0:
        return 0
    slot = max(process_count // max(visit_count, 1), 1)
    return (ordinal * slot) % process_count


def _selection_rank(
    process_id: str,
    *,
    year: int | None,
    offset: int,
    process_count: int,
    index_by_id: dict[str, int],
    year_counts: dict[tuple[int | None, str], int],
) -> tuple[int, int, int]:
    index = index_by_id[process_id]
    usage = year_counts.get((year, process_id), 0)
    rotation = (index - offset) % process_count if process_count else 0
    return usage, rotation, index
