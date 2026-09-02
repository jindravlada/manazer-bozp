"""Persistence katalogu kontrolních orgánů a pracovišť."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from core.database.session import get_session
from core.utils.czech_sort import czech_sort_key
from moduly.statni_dozor.modely.control_authority import ControlAuthority
from moduly.statni_dozor.modely.control_authority_office import ControlAuthorityOffice


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


def _sort_authorities(records: list[ControlAuthority]) -> list[ControlAuthority]:
    return sorted(
        records,
        key=lambda item: (
            int(item.display_order),
            czech_sort_key(item.name),
            int(item.id or 0),
        ),
    )


def _sort_offices(records: list[ControlAuthorityOffice]) -> list[ControlAuthorityOffice]:
    return sorted(
        records,
        key=lambda item: (
            int(item.display_order),
            czech_sort_key(item.name),
            int(item.id or 0),
        ),
    )


class ControlAuthorityCatalogRepository:
    def session(self, session: Session | None = None):
        return _open_session(session)

    def list_authorities(
        self,
        *,
        include_inactive: bool = False,
        query: str | None = None,
        session: Session | None = None,
    ) -> list[ControlAuthority]:
        with _open_session(session) as (sess, owns):
            stmt = select(ControlAuthority)
            if not include_inactive:
                stmt = stmt.where(ControlAuthority.active.is_(True))
            text_q = str(query or "").strip()
            if text_q:
                like = f"%{text_q}%"
                stmt = stmt.where(
                    or_(
                        ControlAuthority.name.ilike(like),
                        ControlAuthority.abbreviation.ilike(like),
                        ControlAuthority.code.ilike(like),
                    )
                )
            records = list(sess.scalars(stmt))
            if owns:
                for record in records:
                    sess.expunge(record)
            return _sort_authorities(records)

    def get_authority(
        self,
        authority_id: int,
        *,
        session: Session | None = None,
    ) -> ControlAuthority | None:
        with _open_session(session) as (sess, owns):
            record = sess.get(ControlAuthority, int(authority_id))
            if record is not None and owns:
                sess.expunge(record)
            return record

    def get_authority_by_code(
        self,
        code: str,
        *,
        session: Session | None = None,
    ) -> ControlAuthority | None:
        with _open_session(session) as (sess, owns):
            record = sess.scalar(
                select(ControlAuthority).where(ControlAuthority.code == code)
            )
            if record is not None and owns:
                sess.expunge(record)
            return record

    def get_authority_by_external_key(
        self,
        external_key: str,
        *,
        session: Session | None = None,
    ) -> ControlAuthority | None:
        with _open_session(session) as (sess, owns):
            record = sess.scalar(
                select(ControlAuthority).where(
                    ControlAuthority.external_key == external_key
                )
            )
            if record is not None and owns:
                sess.expunge(record)
            return record

    def add_authority(
        self,
        record: ControlAuthority,
        *,
        session: Session | None = None,
    ) -> ControlAuthority:
        with _open_session(session) as (sess, owns):
            sess.add(record)
            sess.flush()
            if owns:
                sess.commit()
                sess.refresh(record)
                sess.expunge(record)
            return record

    def update_authority(
        self,
        record: ControlAuthority,
        *,
        session: Session | None = None,
    ) -> ControlAuthority:
        with _open_session(session) as (sess, owns):
            record = sess.merge(record)
            sess.flush()
            if owns:
                sess.commit()
                sess.refresh(record)
                sess.expunge(record)
            return record

    def count_active_offices(
        self,
        authority_id: int,
        *,
        session: Session | None = None,
    ) -> int:
        with _open_session(session) as (sess, _owns):
            stmt = select(ControlAuthorityOffice).where(
                ControlAuthorityOffice.authority_id == int(authority_id),
                ControlAuthorityOffice.active.is_(True),
            )
            return len(list(sess.scalars(stmt)))

    def list_offices(
        self,
        *,
        authority_id: int | None = None,
        include_inactive: bool = False,
        query: str | None = None,
        session: Session | None = None,
    ) -> list[ControlAuthorityOffice]:
        with _open_session(session) as (sess, owns):
            stmt = select(ControlAuthorityOffice)
            if authority_id is not None:
                stmt = stmt.where(
                    ControlAuthorityOffice.authority_id == int(authority_id)
                )
            if not include_inactive:
                stmt = stmt.where(ControlAuthorityOffice.active.is_(True))
            text_q = str(query or "").strip()
            if text_q:
                like = f"%{text_q}%"
                stmt = stmt.where(
                    or_(
                        ControlAuthorityOffice.name.ilike(like),
                        ControlAuthorityOffice.abbreviation.ilike(like),
                        ControlAuthorityOffice.address.ilike(like),
                        ControlAuthorityOffice.territorial_scope.ilike(like),
                    )
                )
            records = list(sess.scalars(stmt))
            if owns:
                for record in records:
                    sess.expunge(record)
            return _sort_offices(records)

    def get_office(
        self,
        office_id: int,
        *,
        session: Session | None = None,
    ) -> ControlAuthorityOffice | None:
        with _open_session(session) as (sess, owns):
            record = sess.get(ControlAuthorityOffice, int(office_id))
            if record is not None and owns:
                sess.expunge(record)
            return record

    def get_office_by_external_key(
        self,
        external_key: str,
        *,
        session: Session | None = None,
    ) -> ControlAuthorityOffice | None:
        with _open_session(session) as (sess, owns):
            record = sess.scalar(
                select(ControlAuthorityOffice).where(
                    ControlAuthorityOffice.external_key == external_key
                )
            )
            if record is not None and owns:
                sess.expunge(record)
            return record

    def add_office(
        self,
        record: ControlAuthorityOffice,
        *,
        session: Session | None = None,
    ) -> ControlAuthorityOffice:
        with _open_session(session) as (sess, owns):
            sess.add(record)
            sess.flush()
            if owns:
                sess.commit()
                sess.refresh(record)
                sess.expunge(record)
            return record

    def update_office(
        self,
        record: ControlAuthorityOffice,
        *,
        session: Session | None = None,
    ) -> ControlAuthorityOffice:
        with _open_session(session) as (sess, owns):
            record = sess.merge(record)
            sess.flush()
            if owns:
                sess.commit()
                sess.refresh(record)
                sess.expunge(record)
            return record
