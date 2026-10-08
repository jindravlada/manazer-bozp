"""Zápis trvalé historie stavů sdíleného zjištění.

Používají ho Audity, Prověrky BOZP i ostatní moduly nad tabulkou ``findings``.
Samostatná historie pro jednotlivý modul se nezakládá.
"""

from datetime import date, datetime

from sqlalchemy.orm import Session

from core.shared.constants import VALID_FINDING_STATUS_ORIGINS
from core.shared.modely.finding_status_event import FindingStatusEvent
from core.shared.repository.finding_status_event_repository import (
    finding_status_event_repository,
)


class FindingStatusHistoryService:
    def __init__(self) -> None:
        self.repository = finding_status_event_repository

    def record(
        self,
        *,
        session: Session,
        finding_id: int,
        old_status: str,
        new_status: str,
        resolved_at_before: date | None,
        resolved_at_after: date | None,
        origin: str = "",
        changed_at: datetime | None = None,
    ) -> FindingStatusEvent | None:
        """Zapíše změnu stavu. Stejný stav nový řádek nevytvoří."""
        if old_status == new_status:
            return None
        if origin and origin not in VALID_FINDING_STATUS_ORIGINS:
            raise ValueError(f"Neplatný původ změny stavu: {origin}")

        event = FindingStatusEvent(
            finding_id=int(finding_id),
            old_status=old_status,
            new_status=new_status,
            changed_at=changed_at or datetime.now(),
            origin=origin or "",
            resolved_at_before=resolved_at_before,
            resolved_at_after=resolved_at_after,
        )
        return self.repository.add(event, session=session)

    def list_for_finding(
        self,
        finding_id: int,
        *,
        session: Session | None = None,
    ) -> list[FindingStatusEvent]:
        return self.repository.list_for_finding(finding_id, session=session)


finding_status_history_service = FindingStatusHistoryService()
