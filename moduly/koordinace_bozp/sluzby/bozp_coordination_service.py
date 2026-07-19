"""Služba evidence koordinací BOZP (COORD-001)."""

from __future__ import annotations

from datetime import date, datetime

from moduly.koordinace_bozp.constants import (
    BOZP_COORDINATION_STATUSES,
    DEFAULT_BOZP_COORDINATION_STATUS,
)
from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
from moduly.koordinace_bozp.repository.bozp_coordination_repository import (
    BozpCoordinationRepository,
)


class BozpCoordinationError(ValueError):
    pass


class BozpCoordinationService:
    def __init__(self) -> None:
        self.repository = BozpCoordinationRepository()

    def get_all(self, include_inactive: bool = False) -> list[BozpCoordination]:
        return self.repository.get_all(include_inactive=include_inactive)

    def get_by_id(self, coordination_id: int | None) -> BozpCoordination | None:
        if not coordination_id:
            return None
        return self.repository.get_by_id(coordination_id)

    def preview_next_number(self, year: int | None = None) -> str:
        return self.repository.allocate_next_number(year=year)

    def create_coordination(
        self,
        *,
        meeting_date: date | None = None,
        place: str = "",
        subject: str = "",
        status: str = DEFAULT_BOZP_COORDINATION_STATUS,
        note: str = "",
        active: bool = True,
    ) -> BozpCoordination:
        normalized_subject = self._validate_subject(subject)
        normalized_status = self._validate_status(status)
        coordination = BozpCoordination(
            coordination_number=self.repository.allocate_next_number(),
            meeting_date=meeting_date or date.today(),
            place=(place or "").strip(),
            subject=normalized_subject,
            status=normalized_status,
            note=(note or "").strip(),
            active=active,
        )
        created = self.repository.add(coordination)
        from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
            coordination_employer_service,
        )

        coordination_employer_service.ensure_main_employer(created.id)
        return created

    def update_coordination(
        self,
        coordination_id: int,
        *,
        meeting_date: date | None = None,
        place: str = "",
        subject: str = "",
        status: str = DEFAULT_BOZP_COORDINATION_STATUS,
        note: str = "",
    ) -> BozpCoordination | None:
        coordination = self.repository.get_by_id(coordination_id)
        if coordination is None:
            return None

        coordination.meeting_date = meeting_date or coordination.meeting_date
        coordination.place = (place or "").strip()
        coordination.subject = self._validate_subject(subject)
        coordination.status = self._validate_status(status)
        coordination.note = (note or "").strip()
        coordination.updated_at = datetime.now()
        return self.repository.update(coordination)

    def activate(self, coordination_id: int) -> bool:
        coordination = self.repository.get_by_id(coordination_id)
        if coordination is None:
            return False
        coordination.active = True
        coordination.updated_at = datetime.now()
        self.repository.update(coordination)
        return True

    def deactivate(self, coordination_id: int) -> bool:
        coordination = self.repository.get_by_id(coordination_id)
        if coordination is None:
            return False
        coordination.active = False
        coordination.updated_at = datetime.now()
        self.repository.update(coordination)
        return True

    @staticmethod
    def _validate_subject(subject: str) -> str:
        normalized = " ".join((subject or "").strip().split())
        if not normalized:
            raise BozpCoordinationError("Předmět koordinace je povinný.")
        return normalized

    @staticmethod
    def _validate_status(status: str) -> str:
        if status not in BOZP_COORDINATION_STATUSES:
            raise BozpCoordinationError("Neplatný stav koordinace.")
        return status


bozp_coordination_service = BozpCoordinationService()
