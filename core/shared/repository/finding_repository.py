from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database.session import get_session
from core.shared.modely.finding import Finding


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


class FindingRepository:
    def session(self, session: Session | None = None):
        return _open_session(session)

    def get_for_entity(
        self,
        entity_type: str,
        entity_id: int,
        *,
        session: Session | None = None,
    ) -> list[Finding]:
        with _open_session(session) as (sess, owns):
            stmt = (
                select(Finding)
                .where(
                    Finding.entity_type == entity_type,
                    Finding.entity_id == entity_id,
                )
                .order_by(Finding.display_order, Finding.id)
            )
            rows = list(sess.scalars(stmt))
            if owns:
                for row in rows:
                    sess.expunge(row)
            return rows

    def get_for_entities(
        self,
        entity_type: str,
        entity_ids: list[int] | tuple[int, ...],
        *,
        session: Session | None = None,
    ) -> list[Finding]:
        """Hromadné načtení zjištění pro více entit (AUDIT-INTRO-1, bez N+1)."""
        ids = [int(value) for value in entity_ids if value is not None]
        if not ids:
            return []
        with _open_session(session) as (sess, owns):
            stmt = (
                select(Finding)
                .where(
                    Finding.entity_type == entity_type,
                    Finding.entity_id.in_(ids),
                )
                .order_by(Finding.entity_id, Finding.display_order, Finding.id)
            )
            rows = list(sess.scalars(stmt))
            if owns:
                for row in rows:
                    sess.expunge(row)
            return rows

    def get_by_id(
        self,
        finding_id: int,
        *,
        session: Session | None = None,
    ) -> Finding | None:
        with _open_session(session) as (sess, owns):
            record = sess.get(Finding, finding_id)
            if record is not None and owns:
                sess.expunge(record)
            return record

    def get_by_task_id(
        self,
        task_id: int,
        *,
        session: Session | None = None,
    ) -> Finding | None:
        with _open_session(session) as (sess, owns):
            stmt = select(Finding).where(Finding.task_id == task_id)
            record = sess.scalar(stmt)
            if record is not None and owns:
                sess.expunge(record)
            return record

    def save(self, finding: Finding, *, session: Session | None = None) -> Finding:
        """Uloží zjištění. Bez ``session`` vlastní commit; caller-owned jen flush."""
        with _open_session(session) as (sess, owns):
            finding.updated_at = datetime.now()
            if finding.id is None:
                sess.add(finding)
            else:
                finding = sess.merge(finding)
            sess.flush()
            if owns:
                sess.commit()
                sess.refresh(finding)
                sess.expunge(finding)
            return finding

    def save_all(
        self,
        records: Sequence[Finding],
        *,
        session: Session | None = None,
    ) -> list[Finding]:
        """Uloží dávku v jedné transakci. Caller-owned session se necommituje."""
        with _open_session(session) as (sess, owns):
            now = datetime.now()
            stored: list[Finding] = []
            for record in records:
                record.updated_at = now
                if record.id is None:
                    sess.add(record)
                    stored.append(record)
                else:
                    stored.append(sess.merge(record))
            sess.flush()
            if owns:
                sess.commit()
                detached: list[Finding] = []
                for record in stored:
                    sess.refresh(record)
                    sess.expunge(record)
                    detached.append(record)
                return detached
            return stored

    def delete(self, finding_id: int) -> bool:
        with get_session() as session:
            finding = session.get(Finding, finding_id)
            if finding is None:
                return False

            session.delete(finding)
            session.commit()
            return True

    def delete_for_entity(self, entity_type: str, entity_id: int) -> int:
        with get_session() as session:
            stmt = select(Finding).where(
                Finding.entity_type == entity_type,
                Finding.entity_id == entity_id,
            )
            findings = list(session.scalars(stmt))
            for finding in findings:
                session.delete(finding)
            session.commit()
            return len(findings)

    def max_display_order(
        self,
        entity_type: str,
        entity_id: int,
        *,
        session: Session | None = None,
    ) -> int:
        with _open_session(session) as (sess, owns):
            stmt = select(func.max(Finding.display_order)).where(
                Finding.entity_type == entity_type,
                Finding.entity_id == entity_id,
            )
            value = sess.scalar(stmt)
            return int(value or 0)

    def count_for_entity(
        self,
        entity_type: str,
        entity_id: int,
        *,
        status: str | None = None,
        finding_type: str | None = None,
        session: Session | None = None,
    ) -> int:
        with _open_session(session) as (sess, owns):
            stmt = select(func.count(Finding.id)).where(
                Finding.entity_type == entity_type,
                Finding.entity_id == entity_id,
            )
            if status is not None:
                stmt = stmt.where(Finding.status == status)
            if finding_type is not None:
                stmt = stmt.where(Finding.finding_type == finding_type)
            return int(sess.scalar(stmt) or 0)
