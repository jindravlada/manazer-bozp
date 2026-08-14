"""Propojení THP pracovníků s číselníkem Osoby (shoda jména / e-mailu)."""

from __future__ import annotations

from moduly.nastaveni.modely.person import Person
from moduly.nastaveni.modely.thp_worker import ThpWorker
from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service


def _norm(value: str | None) -> str:
    return " ".join((value or "").strip().split()).casefold()


def find_person_matching_thp(worker: ThpWorker) -> Person | None:
    first = _norm(worker.first_name)
    last = _norm(worker.last_name)
    email = _norm(worker.email)
    if not first or not last:
        return None

    matches: list[Person] = []
    for person in person_service.get_all(include_inactive=True):
        if _norm(person.first_name) != first or _norm(person.last_name) != last:
            continue
        if email and _norm(person.email) and _norm(person.email) != email:
            continue
        matches.append(person)

    if not matches:
        return None
    active = [person for person in matches if person.active]
    return (active or matches)[0]


def ensure_person_for_thp_worker(worker: ThpWorker) -> Person:
    """LEGACY – nevytvářet z produkčního UI.

    Zachováno pro starší testy / jednorázovou diagnostiku.
    PERSON-THP-SEPARATION-1: Schůzky už tuto funkci nevolají.
    """
    existing = find_person_matching_thp(worker)
    if existing is not None:
        return existing
    return person_service.create_person(
        title_before=worker.title_before or "",
        first_name=worker.first_name or "",
        last_name=worker.last_name or "",
        title_after=worker.title_after or "",
        job_title=worker.position or "",
        email=worker.email or "",
        phone=worker.phone or "",
        active=True,
        is_employee=True,
    )


def find_thp_worker_for_person(person: Person | None) -> ThpWorker | None:
    if person is None:
        return None
    first = _norm(person.first_name)
    last = _norm(person.last_name)
    email = _norm(person.email)
    if not first or not last:
        return None

    matches: list[ThpWorker] = []
    for worker in settings_service.get_workers(include_inactive=True):
        if _norm(worker.first_name) != first or _norm(worker.last_name) != last:
            continue
        if email and _norm(worker.email) and _norm(worker.email) != email:
            continue
        matches.append(worker)

    if not matches:
        return None
    active = [worker for worker in matches if worker.active]
    return (active or matches)[0]


def person_list_label(person: Person | None, *, fallback_id: int | None = None) -> str:
    if person is None:
        return f"#{fallback_id}" if fallback_id is not None else "—"
    parts = [person.display_name]
    detail = (person.job_title or person.organization or "").strip()
    if detail:
        parts.append(detail)
    label = " – ".join(parts)
    if not person.active:
        label = f"{label} (neaktivní)"
    return label
