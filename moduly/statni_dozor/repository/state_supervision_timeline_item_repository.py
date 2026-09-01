"""Persistence záznamů průběhu kontroly státního dozoru."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database.session import get_session
from moduly.statni_dozor.modely.state_supervision_timeline_item import (
    StateSupervisionTimelineItem,
)


@contextmanager
def _open_session(session: Session | None) -> Iterator[tuple[Session, bool]]:
    owns = session is None
    current = get_session() if owns else session
    try:
        yield current, owns
    except Exception:
        if owns:
            current.rollback()
        raise
    finally:
        if owns:
            current.close()


class StateSupervisionTimelineItemRepository:
    def session(self, session: Session | None = None):
        return _open_session(session)

    def get_by_id(
        self,
        item_id: int,
        *,
        session: Session | None = None,
    ) -> StateSupervisionTimelineItem | None:
        with _open_session(session) as (sess, owns):
            record = sess.get(StateSupervisionTimelineItem, item_id)
            if record is not None and owns:
                sess.expunge(record)
            return record

    def list_for_supervision(
        self,
        supervision_id: int,
        *,
        include_inactive: bool = False,
        session: Session | None = None,
    ) -> list[StateSupervisionTimelineItem]:
        with _open_session(session) as (sess, owns):
            stmt = (
                select(StateSupervisionTimelineItem)
                .where(
                    StateSupervisionTimelineItem.state_supervision_id
                    == int(supervision_id)
                )
                .order_by(
                    StateSupervisionTimelineItem.display_order.asc(),
                    StateSupervisionTimelineItem.id.asc(),
                )
            )
            if not include_inactive:
                stmt = stmt.where(StateSupervisionTimelineItem.active.is_(True))
            records = list(sess.scalars(stmt))
            if owns:
                for record in records:
                    sess.expunge(record)
            return records

    def add(
        self,
        record: StateSupervisionTimelineItem,
        *,
        session: Session | None = None,
    ) -> StateSupervisionTimelineItem:
        with _open_session(session) as (sess, owns):
            sess.add(record)
            sess.flush()
            if owns:
                sess.commit()
                sess.refresh(record)
                sess.expunge(record)
            return record

    def update(
        self,
        record: StateSupervisionTimelineItem,
        *,
        session: Session | None = None,
    ) -> StateSupervisionTimelineItem:
        with _open_session(session) as (sess, owns):
            record = sess.merge(record)
            sess.flush()
            if owns:
                sess.commit()
                sess.refresh(record)
                sess.expunge(record)
            return record

    def save_all(
        self,
        records: Sequence[StateSupervisionTimelineItem],
        *,
        session: Session | None = None,
    ) -> list[StateSupervisionTimelineItem]:
        """Uloží dávku v jedné transakci. Caller-owned session se necommituje."""
        with _open_session(session) as (sess, owns):
            stored: list[StateSupervisionTimelineItem] = []
            for record in records:
                if record.id is None:
                    sess.add(record)
                    stored.append(record)
                else:
                    stored.append(sess.merge(record))
            sess.flush()
            if owns:
                sess.commit()
                detached: list[StateSupervisionTimelineItem] = []
                for record in stored:
                    sess.refresh(record)
                    sess.expunge(record)
                    detached.append(record)
                return detached
            return stored
