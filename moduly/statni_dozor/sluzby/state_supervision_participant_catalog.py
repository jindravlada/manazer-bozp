"""Doplnění a identita účastníka z evidence osob / THP."""

from __future__ import annotations

from typing import Any, Iterable

from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.statni_dozor.constants import (
    PARTICIPANT_SOURCE_PERSON,
    PARTICIPANT_SOURCE_THP_WORKER,
    PARTICIPANT_SOURCE_TYPES,
)


def catalog_identity(
    source_type: Any,
    source_id: Any,
) -> tuple[str, int] | None:
    """Stabilní identita osoby z evidence: (source_type, source_id)."""
    type_value = str(source_type or "").strip()
    if not type_value or type_value not in PARTICIPANT_SOURCE_TYPES:
        return None
    if source_id in ("", None):
        return None
    try:
        id_value = int(source_id)
    except (TypeError, ValueError):
        return None
    if id_value <= 0:
        return None
    return type_value, id_value


def occupied_catalog_identities(
    participants: Iterable[Any],
    *,
    exclude_client_key: str | None = None,
    exclude_id: int | None = None,
) -> set[tuple[str, int]]:
    """Identity aktivních účastníků z evidence, bez vlastního záznamu."""
    occupied: set[tuple[str, int]] = set()
    for item in participants:
        if exclude_client_key is not None:
            if str(getattr(item, "client_key", "") or "") == exclude_client_key:
                continue
        item_id = getattr(item, "id", None)
        if exclude_id is not None and item_id is not None:
            if int(item_id) == int(exclude_id):
                continue
        if hasattr(item, "active") and not bool(item.active):
            continue
        identity = catalog_identity(
            getattr(item, "source_type", None),
            getattr(item, "source_id", None),
        )
        if identity is not None:
            occupied.add(identity)
    return occupied


def catalog_identity_is_occupied(
    occupied: set[tuple[str, int]] | None,
    source_type: Any,
    source_id: Any,
) -> bool:
    identity = catalog_identity(source_type, source_id)
    if identity is None or not occupied:
        return False
    return identity in occupied


def employer_organization_name() -> str:
    employer = settings_service.get_employer()
    if employer is None:
        return ""
    return str(getattr(employer, "name", None) or "").strip()


def format_participant_contact(
    email: str | None = None,
    phone: str | None = None,
) -> str | None:
    """Stejný zápis jako u kontaktů v katalogu orgánů: telefon · e-mail."""
    parts = [
        part
        for part in ((phone or "").strip(), (email or "").strip())
        if part
    ]
    if not parts:
        return None
    return " · ".join(parts)


def catalog_participant_autofill(
    source_type: Any,
    source_id: Any,
) -> tuple[str | None, str | None]:
    """Organizace a kontakt z evidované osoby. Nemění záznam v evidenci."""
    identity = catalog_identity(source_type, source_id)
    if identity is None:
        return None, None
    type_value, id_value = identity
    if type_value == PARTICIPANT_SOURCE_THP_WORKER:
        worker = settings_service.get_worker_by_id(id_value)
        if worker is None:
            return None, None
        organization = employer_organization_name() or None
        contact = format_participant_contact(
            getattr(worker, "email", None),
            getattr(worker, "phone", None),
        )
        return organization, contact
    if type_value == PARTICIPANT_SOURCE_PERSON:
        person = person_service.get_by_id(id_value)
        if person is None:
            return None, None
        own_organization = str(getattr(person, "organization", None) or "").strip()
        if own_organization:
            organization = own_organization
        elif bool(getattr(person, "is_employee", False)):
            organization = employer_organization_name() or None
        else:
            organization = None
        contact = format_participant_contact(
            getattr(person, "email", None),
            getattr(person, "phone", None),
        )
        return organization, contact
    return None, None


def _previous_catalog_identity(item: Any, existing_rows: dict[int, Any]) -> tuple[str, int] | None:
    item_id = getattr(item, "id", None)
    if item_id is None:
        return None
    existing = existing_rows.get(int(item_id))
    if existing is None:
        return None
    return catalog_identity(existing.source_type, existing.source_id)


def has_new_catalog_duplicate(
    *,
    drafts: Iterable[Any],
    existing_rows: dict[int, Any],
    hide_omitted: bool,
) -> bool:
    """True, pokud dávka nově zavádí duplicitní osobu z evidence.

    Již uložené duplicity ponechá; nové přidání nebo změna na obsazenou
    identitu je zakázané. Ruční osoby bez source_id se neporovnávají.
    """
    draft_list = list(drafts)
    incoming_ids = {int(item.id) for item in draft_list if getattr(item, "id", None) is not None}
    active_items: list[Any] = [
        item for item in draft_list if bool(getattr(item, "active", True))
    ]
    if not hide_omitted:
        for row_id, row in existing_rows.items():
            if row_id in incoming_ids:
                continue
            if not bool(getattr(row, "active", True)):
                continue
            active_items.append(row)

    grouped: dict[tuple[str, int], list[Any]] = {}
    for item in active_items:
        identity = catalog_identity(
            getattr(item, "source_type", None),
            getattr(item, "source_id", None),
        )
        if identity is None:
            continue
        grouped.setdefault(identity, []).append(item)

    for identity, items in grouped.items():
        if len(items) < 2:
            continue
        for item in items:
            if _previous_catalog_identity(item, existing_rows) != identity:
                return True
    return False
