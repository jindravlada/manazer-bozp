"""Persistence Státního dozoru."""

from __future__ import annotations

from sqlalchemy import extract, func, or_, select

from core.database.session import get_session
from moduly.statni_dozor.modely.state_supervision import StateSupervision


def _effective_start_expr():
    return func.coalesce(
        StateSupervision.started_at,
        StateSupervision.planned_start_at,
        StateSupervision.created_at,
    )


class StateSupervisionRepository:
    def get_by_id(self, supervision_id: int) -> StateSupervision | None:
        with get_session() as session:
            record = session.get(StateSupervision, supervision_id)
            if record is not None:
                session.expunge(record)
            return record

    def add(self, record: StateSupervision) -> StateSupervision:
        with get_session() as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            session.expunge(record)
            return record

    def update(self, record: StateSupervision) -> StateSupervision:
        with get_session() as session:
            record = session.merge(record)
            session.commit()
            session.refresh(record)
            session.expunge(record)
            return record

    def list_all(
        self,
        *,
        status: str | None = None,
        year: int | None = None,
        authority: str | None = None,
        workplace_id: int | None = None,
        query: str | None = None,
    ) -> list[StateSupervision]:
        effective = _effective_start_expr()
        with get_session() as session:
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
            records = list(session.scalars(stmt))
            for record in records:
                session.expunge(record)
            return records
