"""Služba účastníků kontroly státního dozoru."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.statni_dozor.constants import (
    PARTICIPANT_ATTENDANCE_STATUSES,
    PARTICIPANT_CATALOG_DUPLICATE_MESSAGE,
    PARTICIPANT_ROLES,
    PARTICIPANT_SOURCE_PERSON,
    PARTICIPANT_SOURCE_THP_WORKER,
    PARTICIPANT_SOURCE_TYPES,
)
from moduly.statni_dozor.modely.state_supervision_participant import (
    StateSupervisionParticipant,
)
from moduly.statni_dozor.modely.state_supervision_participant_draft import (
    StateSupervisionParticipantDraft,
)
from moduly.statni_dozor.repository.state_supervision_participant_repository import (
    StateSupervisionParticipantRepository,
)
from moduly.statni_dozor.repository.state_supervision_repository import (
    StateSupervisionRepository,
)
from moduly.statni_dozor.sluzby.state_supervision_participant_catalog import (
    has_new_catalog_duplicate,
)
from moduly.statni_dozor.sluzby.state_supervision_service import StateSupervisionError

_UPDATABLE_FIELDS = frozenset(
    {
        "role",
        "source_type",
        "source_id",
        "name_snapshot",
        "organization_snapshot",
        "contact_note",
        "planned",
        "attendance_status",
        "note",
        "display_order",
        "active",
    }
)


def _blank_to_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _require_role(value: Any) -> str:
    role = str(value or "").strip()
    if role not in PARTICIPANT_ROLES:
        raise StateSupervisionError(f"Neplatná role účastníka: {value!r}")
    return role


def _require_name(value: Any) -> str:
    name = str(value or "").strip()
    if not name:
        raise StateSupervisionError("Jméno účastníka je povinné.")
    return name


def _require_display_order(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        raise StateSupervisionError("Pořadí účastníka musí být nezáporné celé číslo.")
    try:
        order = int(value)
    except (TypeError, ValueError) as exc:
        raise StateSupervisionError(
            "Pořadí účastníka musí být nezáporné celé číslo."
        ) from exc
    if order < 0:
        raise StateSupervisionError("Pořadí účastníka nesmí být záporné.")
    return order


def _optional_attendance(value: Any) -> str | None:
    status = _blank_to_none(value)
    if status is None:
        return None
    if status not in PARTICIPANT_ATTENDANCE_STATUSES:
        raise StateSupervisionError(f"Neplatný stav účasti: {value!r}")
    return status


def _resolve_source(
    *,
    source_type: Any,
    source_id: Any,
    existing: StateSupervisionParticipant | None = None,
) -> tuple[str | None, int | None, str | None]:
    type_value = _blank_to_none(source_type)
    id_raw = source_id
    if id_raw in ("", None):
        id_value = None
    else:
        try:
            id_value = int(id_raw)
        except (TypeError, ValueError) as exc:
            raise StateSupervisionError("ID osoby musí být celé číslo.") from exc
        if id_value <= 0:
            id_value = None

    if type_value is None and id_value is None:
        return None, None, None
    if type_value is None or id_value is None:
        raise StateSupervisionError("Typ a ID osoby musí být vyplněny společně.")
    if type_value not in PARTICIPANT_SOURCE_TYPES:
        raise StateSupervisionError(f"Neplatný typ osoby: {source_type!r}")

    same_as_existing = (
        existing is not None
        and existing.source_type == type_value
        and existing.source_id == id_value
    )
    if same_as_existing:
        snapshot = _blank_to_none(existing.name_snapshot)
        if snapshot:
            return type_value, id_value, snapshot

    if type_value == PARTICIPANT_SOURCE_PERSON:
        person = person_service.get_by_id(id_value)
        if person is None:
            raise StateSupervisionError(f"Osoba id={id_value} neexistuje.")
        display = str(
            getattr(person, "display_name", None) or person.full_name or ""
        ).strip()
        if not display:
            display = f"Osoba #{id_value}"
        return type_value, id_value, display

    if type_value == PARTICIPANT_SOURCE_THP_WORKER:
        worker = settings_service.get_worker_by_id(id_value)
        if worker is None:
            raise StateSupervisionError(f"THP pracovník id={id_value} neexistuje.")
        display = str(
            getattr(worker, "display_name", None) or worker.full_name or ""
        ).strip()
        if not display:
            display = f"THP #{id_value}"
        return type_value, id_value, display

    raise StateSupervisionError(f"Neplatný typ osoby: {source_type!r}")


def _normalize_batch_orders(
    drafts: Sequence[StateSupervisionParticipantDraft],
) -> list[tuple[int, StateSupervisionParticipantDraft]]:
    """Duplicitní display_order se seřadí a přepíše na 0, 10, 20, …"""
    decorated: list[tuple[int, int, int, StateSupervisionParticipantDraft]] = []
    for index, draft in enumerate(drafts):
        order = _require_display_order(draft.display_order)
        existing_id = int(draft.id) if draft.id is not None else 10**9 + index
        decorated.append((order, existing_id, index, draft))
    decorated.sort(key=lambda item: (item[0], item[1], item[2]))
    return [(index * 10, item[3]) for index, item in enumerate(decorated)]


class StateSupervisionParticipantService:
    def __init__(self) -> None:
        self.repository = StateSupervisionParticipantRepository()
        self._supervisions = StateSupervisionRepository()

    def _require_supervision(
        self,
        supervision_id: int,
        *,
        session: Session | None = None,
    ) -> None:
        record = self._supervisions.get_by_id(int(supervision_id), session=session)
        if record is None:
            raise StateSupervisionError(
                f"Kontrola státního dozoru {supervision_id} neexistuje."
            )

    def list_participants(
        self,
        supervision_id: int,
        *,
        include_inactive: bool = False,
        session: Session | None = None,
    ) -> list[StateSupervisionParticipant]:
        self._require_supervision(supervision_id, session=session)
        return self.repository.list_for_supervision(
            int(supervision_id),
            include_inactive=include_inactive,
            session=session,
        )

    def get_participant(
        self,
        participant_id: int,
        *,
        session: Session | None = None,
    ) -> StateSupervisionParticipant | None:
        return self.repository.get_by_id(int(participant_id), session=session)

    def create_participant(
        self,
        supervision_id: int,
        *,
        role: str,
        session: Session | None = None,
        **fields: Any,
    ) -> StateSupervisionParticipant:
        allowed = {key: fields[key] for key in fields if key in _UPDATABLE_FIELDS}
        if "display_order" not in allowed:
            existing = self.repository.list_for_supervision(
                int(supervision_id),
                include_inactive=True,
                session=session,
            )
            max_order = max((int(row.display_order) for row in existing), default=-10)
            allowed["display_order"] = max_order + 10
        draft = StateSupervisionParticipantDraft(role=role, **allowed)
        saved = self.save_participant_batch(
            supervision_id,
            [draft],
            session=session,
            replace_orders=False,
            deactivate_omitted=False,
        )
        return saved[0]

    def update_participant(
        self,
        participant_id: int,
        *,
        session: Session | None = None,
        **fields: Any,
    ) -> StateSupervisionParticipant:
        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            names = ", ".join(sorted(unknown))
            raise StateSupervisionError(f"Neznámé pole účastníka: {names}")
        current = self.repository.get_by_id(int(participant_id), session=session)
        if current is None:
            raise StateSupervisionError(f"Účastník {participant_id} neexistuje.")
        draft = self._draft_from_record(current)
        for key, value in fields.items():
            setattr(draft, key, value)
        saved = self.save_participant_batch(
            int(current.state_supervision_id),
            [draft],
            session=session,
            replace_orders=False,
            deactivate_omitted=False,
        )
        return saved[0]

    def deactivate_participant(
        self,
        participant_id: int,
        *,
        session: Session | None = None,
    ) -> StateSupervisionParticipant:
        return self.update_participant(participant_id, session=session, active=False)

    def reactivate_participant(
        self,
        participant_id: int,
        *,
        session: Session | None = None,
    ) -> StateSupervisionParticipant:
        return self.update_participant(participant_id, session=session, active=True)

    def save_participant_batch(
        self,
        supervision_id: int,
        drafts: Sequence[StateSupervisionParticipantDraft],
        *,
        session: Session | None = None,
        replace_orders: bool = True,
        deactivate_omitted: bool | None = None,
    ) -> list[StateSupervisionParticipant]:
        """Uloží dávku účastníků jedné kontroly v jedné transakci.

        Duplicitní ``display_order`` se při ``replace_orders=True`` (výchozí)
        deterministicky přepíše na 0, 10, 20, … podle (order, id, pořadí v dávce).

        Existující záznamy, které v dávce chybí, se při ``deactivate_omitted``
        (výchozí stejně jako ``replace_orders``) skryjí přes ``active=False``.
        Nový draft bez DB ID se při vynechání z dávky do DB nezapisuje.

        Caller-owned ``session`` se necommituje.
        """
        self._require_supervision(supervision_id, session=session)
        hide_omitted = replace_orders if deactivate_omitted is None else bool(
            deactivate_omitted
        )
        if not drafts and not hide_omitted:
            return []

        with self.repository.session(session) as (sess, owns):
            existing_rows = {
                int(row.id): row
                for row in self.repository.list_for_supervision(
                    int(supervision_id),
                    include_inactive=True,
                    session=sess,
                )
            }
            ordered = (
                _normalize_batch_orders(drafts)
                if replace_orders and drafts
                else [
                    (_require_display_order(draft.display_order), draft)
                    for draft in drafts
                ]
            )
            if has_new_catalog_duplicate(
                drafts=[draft for _order, draft in ordered],
                existing_rows=existing_rows,
                hide_omitted=hide_omitted,
            ):
                raise StateSupervisionError(PARTICIPANT_CATALOG_DUPLICATE_MESSAGE)
            prepared: list[StateSupervisionParticipant] = []
            for order, draft in ordered:
                record = self._record_from_draft(
                    supervision_id=int(supervision_id),
                    draft=draft,
                    existing_rows=existing_rows,
                    display_order=order,
                    session=sess,
                )
                prepared.append(record)
            kept_count = len(prepared)
            if hide_omitted:
                kept_ids = {int(draft.id) for draft in drafts if draft.id is not None}
                for row_id, row in existing_rows.items():
                    if row_id in kept_ids:
                        continue
                    if not bool(row.active):
                        continue
                    row.active = False
                    row.updated_at = datetime.now()
                    prepared.append(row)
            if not prepared:
                return []
            stored = self.repository.save_all(prepared, session=sess)
            kept = stored[:kept_count]
            if owns:
                sess.commit()
                detached: list[StateSupervisionParticipant] = []
                for record in kept:
                    sess.refresh(record)
                    sess.expunge(record)
                    detached.append(record)
                return detached
            return kept

    def _draft_from_record(
        self, record: StateSupervisionParticipant
    ) -> StateSupervisionParticipantDraft:
        return StateSupervisionParticipantDraft(
            id=int(record.id),
            role=str(record.role or ""),
            name_snapshot=str(record.name_snapshot or ""),
            source_type=record.source_type,
            source_id=record.source_id,
            organization_snapshot=record.organization_snapshot,
            contact_note=record.contact_note,
            planned=bool(record.planned),
            attendance_status=record.attendance_status,
            note=record.note,
            display_order=int(record.display_order or 0),
            active=bool(record.active),
        )

    def _record_from_draft(
        self,
        *,
        supervision_id: int,
        draft: StateSupervisionParticipantDraft,
        existing_rows: dict[int, StateSupervisionParticipant],
        display_order: int,
        session: Session | None = None,
    ) -> StateSupervisionParticipant:
        existing: StateSupervisionParticipant | None = None
        if draft.id is not None:
            existing = existing_rows.get(int(draft.id))
            if existing is None:
                loaded = self.repository.get_by_id(int(draft.id), session=session)
                if loaded is None:
                    raise StateSupervisionError(f"Účastník {draft.id} neexistuje.")
                if int(loaded.state_supervision_id) != int(supervision_id):
                    raise StateSupervisionError(
                        "Účastník nepatří k této kontrole státního dozoru."
                    )
                existing = loaded
        role = _require_role(draft.role)
        source_type, source_id, catalog_name = _resolve_source(
            source_type=draft.source_type,
            source_id=draft.source_id,
            existing=existing,
        )
        if source_type is None:
            name = _require_name(draft.name_snapshot)
        else:
            name = str(catalog_name or "").strip()
            if not name:
                name = _require_name(draft.name_snapshot)
        organization = _blank_to_none(draft.organization_snapshot)
        contact = _blank_to_none(draft.contact_note)
        note = _blank_to_none(draft.note)
        planned = True if draft.planned is None else bool(draft.planned)
        attendance = _optional_attendance(draft.attendance_status)
        if existing is None:
            return StateSupervisionParticipant(
                state_supervision_id=int(supervision_id),
                role=role,
                source_type=source_type,
                source_id=source_id,
                name_snapshot=name,
                organization_snapshot=organization,
                contact_note=contact,
                planned=planned,
                attendance_status=attendance,
                note=note,
                display_order=display_order,
                active=bool(draft.active),
            )
        existing.role = role
        existing.source_type = source_type
        existing.source_id = source_id
        existing.name_snapshot = name
        existing.organization_snapshot = organization
        existing.contact_note = contact
        existing.planned = planned
        existing.attendance_status = attendance
        existing.note = note
        existing.display_order = display_order
        existing.active = bool(draft.active)
        existing.updated_at = datetime.now()
        return existing


state_supervision_participant_service = StateSupervisionParticipantService()
