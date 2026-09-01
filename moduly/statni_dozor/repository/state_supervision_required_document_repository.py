"""Persistence požadovaných dokladů státního dozoru."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database.session import get_session
from moduly.statni_dozor.modely.state_supervision_required_document import (
    StateSupervisionRequiredDocument,
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


class StateSupervisionRequiredDocumentRepository:
    def session(self, session: Session | None = None):
        return _open_session(session)

    def get_by_id(
        self,
        document_id: int,
        *,
        session: Session | None = None,
    ) -> StateSupervisionRequiredDocument | None:
        with _open_session(session) as (sess, owns):
            record = sess.get(StateSupervisionRequiredDocument, document_id)
            if record is not None and owns:
                sess.expunge(record)
            return record

    def list_for_supervision(
        self,
        supervision_id: int,
        *,
        include_inactive: bool = False,
        session: Session | None = None,
    ) -> list[StateSupervisionRequiredDocument]:
        with _open_session(session) as (sess, owns):
            stmt = (
                select(StateSupervisionRequiredDocument)
                .where(
                    StateSupervisionRequiredDocument.state_supervision_id
                    == int(supervision_id)
                )
                .order_by(
                    StateSupervisionRequiredDocument.display_order.asc(),
                    StateSupervisionRequiredDocument.id.asc(),
                )
            )
            if not include_inactive:
                stmt = stmt.where(StateSupervisionRequiredDocument.active.is_(True))
            records = list(sess.scalars(stmt))
            if owns:
                for record in records:
                    sess.expunge(record)
            return records

    def list_for_supervisions(
        self,
        supervision_ids: Sequence[int],
        *,
        include_inactive: bool = False,
        session: Session | None = None,
    ) -> list[StateSupervisionRequiredDocument]:
        ids = [int(value) for value in supervision_ids if value is not None]
        if not ids:
            return []
        with _open_session(session) as (sess, owns):
            stmt = (
                select(StateSupervisionRequiredDocument)
                .where(
                    StateSupervisionRequiredDocument.state_supervision_id.in_(ids)
                )
                .order_by(
                    StateSupervisionRequiredDocument.state_supervision_id.asc(),
                    StateSupervisionRequiredDocument.display_order.asc(),
                    StateSupervisionRequiredDocument.id.asc(),
                )
            )
            if not include_inactive:
                stmt = stmt.where(StateSupervisionRequiredDocument.active.is_(True))
            records = list(sess.scalars(stmt))
            if owns:
                for record in records:
                    sess.expunge(record)
            return records

    def add(
        self,
        record: StateSupervisionRequiredDocument,
        *,
        session: Session | None = None,
    ) -> StateSupervisionRequiredDocument:
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
        record: StateSupervisionRequiredDocument,
        *,
        session: Session | None = None,
    ) -> StateSupervisionRequiredDocument:
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
        records: Sequence[StateSupervisionRequiredDocument],
        *,
        session: Session | None = None,
    ) -> list[StateSupervisionRequiredDocument]:
        """Uloží dávku v jedné transakci. Caller-owned session se necommituje."""
        with _open_session(session) as (sess, owns):
            stored: list[StateSupervisionRequiredDocument] = []
            for record in records:
                if record.id is None:
                    sess.add(record)
                    stored.append(record)
                else:
                    stored.append(sess.merge(record))
            sess.flush()
            if owns:
                sess.commit()
                detached: list[StateSupervisionRequiredDocument] = []
                for record in stored:
                    sess.refresh(record)
                    sess.expunge(record)
                    detached.append(record)
                return detached
            return stored
