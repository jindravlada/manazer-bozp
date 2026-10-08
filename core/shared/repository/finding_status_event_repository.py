from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database.session import get_session
from core.shared.modely.finding_status_event import FindingStatusEvent


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


class FindingStatusEventRepository:
    def add(
        self,
        event: FindingStatusEvent,
        *,
        session: Session,
    ) -> FindingStatusEvent:
        """Vloží řádek do už otevřené transakce. Sám necommituje."""
        session.add(event)
        session.flush()
        return event

    def list_for_finding(
        self,
        finding_id: int,
        *,
        session: Session | None = None,
    ) -> list[FindingStatusEvent]:
        with _open_session(session) as (sess, owns):
            stmt = (
                select(FindingStatusEvent)
                .where(FindingStatusEvent.finding_id == int(finding_id))
                .order_by(FindingStatusEvent.id)
            )
            rows = list(sess.scalars(stmt))
            if owns:
                for row in rows:
                    sess.expunge(row)
            return rows


finding_status_event_repository = FindingStatusEventRepository()
