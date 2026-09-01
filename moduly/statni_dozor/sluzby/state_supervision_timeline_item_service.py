"""Služba záznamů průběhu kontroly státního dozoru."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from moduly.statni_dozor.modely.state_supervision_timeline_item import (
    StateSupervisionTimelineItem,
)
from moduly.statni_dozor.modely.state_supervision_timeline_item_draft import (
    StateSupervisionTimelineItemDraft,
)
from moduly.statni_dozor.repository.state_supervision_repository import (
    StateSupervisionRepository,
)
from moduly.statni_dozor.repository.state_supervision_timeline_item_repository import (
    StateSupervisionTimelineItemRepository,
)
from moduly.statni_dozor.sluzby.state_supervision_service import StateSupervisionError

_UPDATABLE_FIELDS = frozenset(
    {
        "occurred_at",
        "title",
        "place",
        "notes",
        "display_order",
        "active",
    }
)


def _blank_to_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _require_title(value: Any) -> str:
    title = str(value or "").strip()
    if not title:
        raise StateSupervisionError("Název záznamu průběhu je povinný.")
    return title


def _require_display_order(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        raise StateSupervisionError("Pořadí záznamu průběhu musí být nezáporné celé číslo.")
    try:
        order = int(value)
    except (TypeError, ValueError) as exc:
        raise StateSupervisionError(
            "Pořadí záznamu průběhu musí být nezáporné celé číslo."
        ) from exc
    if order < 0:
        raise StateSupervisionError("Pořadí záznamu průběhu nesmí být záporné.")
    return order


def _normalize_batch_orders(
    drafts: Sequence[StateSupervisionTimelineItemDraft],
) -> list[tuple[int, StateSupervisionTimelineItemDraft]]:
    """Duplicitní display_order se seřadí a přepíše na 0, 10, 20, …"""
    decorated: list[tuple[int, int, int, StateSupervisionTimelineItemDraft]] = []
    for index, draft in enumerate(drafts):
        order = _require_display_order(draft.display_order)
        existing_id = int(draft.id) if draft.id is not None else 10**9 + index
        decorated.append((order, existing_id, index, draft))
    decorated.sort(key=lambda item: (item[0], item[1], item[2]))
    return [(index * 10, item[3]) for index, item in enumerate(decorated)]


class StateSupervisionTimelineItemService:
    def __init__(self) -> None:
        self.repository = StateSupervisionTimelineItemRepository()
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

    def list_timeline_items(
        self,
        supervision_id: int,
        *,
        include_inactive: bool = False,
        session: Session | None = None,
    ) -> list[StateSupervisionTimelineItem]:
        self._require_supervision(supervision_id, session=session)
        return self.repository.list_for_supervision(
            int(supervision_id),
            include_inactive=include_inactive,
            session=session,
        )

    def get_timeline_item(
        self,
        item_id: int,
        *,
        session: Session | None = None,
    ) -> StateSupervisionTimelineItem | None:
        return self.repository.get_by_id(int(item_id), session=session)

    def create_timeline_item(
        self,
        supervision_id: int,
        *,
        title: str,
        session: Session | None = None,
        **fields: Any,
    ) -> StateSupervisionTimelineItem:
        allowed = {key: fields[key] for key in fields if key in _UPDATABLE_FIELDS}
        if "display_order" not in allowed:
            existing = self.repository.list_for_supervision(
                int(supervision_id),
                include_inactive=True,
                session=session,
            )
            max_order = max((int(row.display_order) for row in existing), default=-10)
            allowed["display_order"] = max_order + 10
        draft = StateSupervisionTimelineItemDraft(title=title, **allowed)
        saved = self.save_timeline_batch(
            supervision_id,
            [draft],
            session=session,
            replace_orders=False,
            deactivate_omitted=False,
        )
        return saved[0]

    def update_timeline_item(
        self,
        item_id: int,
        *,
        session: Session | None = None,
        **fields: Any,
    ) -> StateSupervisionTimelineItem:
        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            names = ", ".join(sorted(unknown))
            raise StateSupervisionError(f"Neznámé pole záznamu průběhu: {names}")
        current = self.repository.get_by_id(int(item_id), session=session)
        if current is None:
            raise StateSupervisionError(f"Záznam průběhu {item_id} neexistuje.")
        draft = self._draft_from_record(current)
        for key, value in fields.items():
            setattr(draft, key, value)
        saved = self.save_timeline_batch(
            int(current.state_supervision_id),
            [draft],
            session=session,
            replace_orders=False,
            deactivate_omitted=False,
        )
        return saved[0]

    def deactivate_timeline_item(
        self,
        item_id: int,
        *,
        session: Session | None = None,
    ) -> StateSupervisionTimelineItem:
        return self.update_timeline_item(item_id, session=session, active=False)

    def reactivate_timeline_item(
        self,
        item_id: int,
        *,
        session: Session | None = None,
    ) -> StateSupervisionTimelineItem:
        return self.update_timeline_item(item_id, session=session, active=True)

    def save_timeline_batch(
        self,
        supervision_id: int,
        drafts: Sequence[StateSupervisionTimelineItemDraft],
        *,
        session: Session | None = None,
        replace_orders: bool = True,
        deactivate_omitted: bool | None = None,
    ) -> list[StateSupervisionTimelineItem]:
        """Uloží dávku záznamů průběhu jedné kontroly v jedné transakci.

        Duplicitní ``display_order`` se při ``replace_orders=True`` (výchozí)
        deterministicky přepíše na 0, 10, 20, … podle (order, id, pořadí v dávce).

        Existující záznamy, které v dávce chybí, se při ``deactivate_omitted``
        (výchozí stejně jako ``replace_orders``) skryjí přes ``active=False``.
        Nový draft bez DB ID se při vynechání z dávky do DB nezapisuje.

        Caller-owned ``session`` se necommituje — napojeno do
        ``save_supervision_bundle``.
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
            prepared: list[StateSupervisionTimelineItem] = []
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
                detached: list[StateSupervisionTimelineItem] = []
                for record in kept:
                    sess.refresh(record)
                    sess.expunge(record)
                    detached.append(record)
                return detached
            return kept

    def _draft_from_record(
        self, record: StateSupervisionTimelineItem
    ) -> StateSupervisionTimelineItemDraft:
        return StateSupervisionTimelineItemDraft(
            id=int(record.id),
            title=str(record.title or ""),
            occurred_at=record.occurred_at,
            place=record.place,
            notes=record.notes,
            display_order=int(record.display_order or 0),
            active=bool(record.active),
        )

    def _record_from_draft(
        self,
        *,
        supervision_id: int,
        draft: StateSupervisionTimelineItemDraft,
        existing_rows: dict[int, StateSupervisionTimelineItem],
        display_order: int,
        session: Session | None = None,
    ) -> StateSupervisionTimelineItem:
        title = _require_title(draft.title)
        existing: StateSupervisionTimelineItem | None = None
        if draft.id is not None:
            existing = existing_rows.get(int(draft.id))
            if existing is None:
                loaded = self.repository.get_by_id(int(draft.id), session=session)
                if loaded is None:
                    raise StateSupervisionError(
                        f"Záznam průběhu {draft.id} neexistuje."
                    )
                if int(loaded.state_supervision_id) != int(supervision_id):
                    raise StateSupervisionError(
                        "Záznam průběhu nepatří k této kontrole státního dozoru."
                    )
                existing = loaded
        place = _blank_to_none(draft.place)
        notes = _blank_to_none(draft.notes)
        if existing is None:
            return StateSupervisionTimelineItem(
                state_supervision_id=int(supervision_id),
                occurred_at=draft.occurred_at,
                title=title,
                place=place,
                notes=notes,
                display_order=display_order,
                active=bool(draft.active),
            )
        existing.occurred_at = draft.occurred_at
        existing.title = title
        existing.place = place
        existing.notes = notes
        existing.display_order = display_order
        existing.active = bool(draft.active)
        existing.updated_at = datetime.now()
        return existing


state_supervision_timeline_item_service = StateSupervisionTimelineItemService()
