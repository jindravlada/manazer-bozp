"""Persistence Státního dozoru."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session

from core.database.session import get_session
from moduly.statni_dozor.modely.state_supervision import StateSupervision


def _effective_start_expr():
    return func.coalesce(
        StateSupervision.started_at,
        StateSupervision.planned_start_at,
        StateSupervision.created_at,
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


class StateSupervisionRepository:
    def session(self, session: Session | None = None):
        return _open_session(session)

    def get_by_id(
        self,
        supervision_id: int,
        *,
        session: Session | None = None,
    ) -> StateSupervision | None:
        with _open_session(session) as (sess, owns):
            record = sess.get(StateSupervision, supervision_id)
            if record is not None and owns:
                sess.expunge(record)
            return record

    def add(
        self,
        record: StateSupervision,
        *,
        session: Session | None = None,
    ) -> StateSupervision:
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
        record: StateSupervision,
        *,
        session: Session | None = None,
    ) -> StateSupervision:
        with _open_session(session) as (sess, owns):
            record = sess.merge(record)
            sess.flush()
            if owns:
                sess.commit()
                sess.refresh(record)
                sess.expunge(record)
            return record

    def list_all(
        self,
        *,
        status: str | None = None,
        year: int | None = None,
        authority: str | None = None,
        workplace_id: int | None = None,
        query: str | None = None,
        session: Session | None = None,
    ) -> list[StateSupervision]:
        effective = _effective_start_expr()
        with _open_session(session) as (sess, owns):
            stmt = select(StateSupervision).order_by(
                effective.desc(),
                StateSupervision.id.desc(),
            )
            if status:
                stmt = stmt.where(StateSupervision.status == status)
            if year is not None:
                stmt = stmt.where(extract("year", effective) == int(year))
            if workplace_id is not None:
                stmt = stmt.where(StateSupervision.workplace_id == workplace_id)
            authority_q = str(authority or "").strip()
            if authority_q:
                like = f"%{authority_q}%"
                stmt = stmt.where(
                    or_(
                        StateSupervision.authority_name.ilike(like),
                        StateSupervision.authority_ico.ilike(like),
                    )
                )
            text_q = str(query or "").strip()
            if text_q:
                like = f"%{text_q}%"
                stmt = stmt.where(
                    or_(
                        StateSupervision.authority_name.ilike(like),
                        StateSupervision.authority_ico.ilike(like),
                        StateSupervision.file_number.ilike(like),
                        StateSupervision.subject.ilike(like),
                        StateSupervision.workplace_name_snapshot.ilike(like),
                        StateSupervision.result.ilike(like),
                        StateSupervision.protocol_number.ilike(like),
                    )
                )
            records = list(sess.scalars(stmt))
            if owns:
                for record in records:
                    sess.expunge(record)
            return records
