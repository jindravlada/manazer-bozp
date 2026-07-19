"""Služba evidence koordinací BOZP (COORD-001 / COORD-004)."""

from __future__ import annotations

from datetime import date, datetime

from moduly.koordinace_bozp.constants import (
    BOZP_COORDINATION_STATUSES,
    DEFAULT_ACCIDENT_REPORTING,
    DEFAULT_BOZP_COORDINATION_STATUS,
    DEFAULT_EMERGENCY_REPORTING,
    DEFAULT_EVACUATION_INSTRUCTIONS,
    DEFAULT_FIRE_REPORTING,
    PBP_FILTER_ALL,
    SUBJECT_REQUIRED_MESSAGE,
    VALIDITY_FILTER_ALL,
    VALIDITY_FILTER_EXPIRED,
    VALIDITY_FILTER_EXPIRING,
    VALIDITY_FILTER_VALID,
)
from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
from moduly.koordinace_bozp.repository.bozp_coordination_repository import (
    BozpCoordinationRepository,
)
from moduly.koordinace_bozp.sluzby.coordination_pbp_freshness import (
    PbpFreshnessCache,
    filter_by_pbp_freshness,
)
from moduly.koordinace_bozp.sluzby.coordination_validity import (
    coordination_validity_state,
    resolve_validity_dates,
)


class BozpCoordinationError(ValueError):
    pass


class BozpCoordinationService:
    def __init__(self) -> None:
        self.repository = BozpCoordinationRepository()

    def get_all(
        self,
        include_inactive: bool = False,
        *,
        validity_filter: str = VALIDITY_FILTER_ALL,
        pbp_filter: str = PBP_FILTER_ALL,
        today: date | None = None,
        pbp_cache: PbpFreshnessCache | None = None,
    ) -> list[BozpCoordination]:
        items = self.repository.get_all(include_inactive=include_inactive)
        items = self.filter_by_validity(items, validity_filter, today=today)
        return self.filter_by_pbp(items, pbp_filter, today=today, pbp_cache=pbp_cache)

    def filter_by_validity(
        self,
        items: list[BozpCoordination],
        validity_filter: str = VALIDITY_FILTER_ALL,
        *,
        today: date | None = None,
    ) -> list[BozpCoordination]:
        if validity_filter in ("", VALIDITY_FILTER_ALL, None):
            return list(items)
        allowed = {
            VALIDITY_FILTER_VALID,
            VALIDITY_FILTER_EXPIRING,
            VALIDITY_FILTER_EXPIRED,
        }
        if validity_filter not in allowed:
            raise BozpCoordinationError("Neplatný filtr platnosti.")
        return [
            item
            for item in items
            if coordination_validity_state(item.valid_to, today=today) == validity_filter
        ]

    def filter_by_pbp(
        self,
        items: list[BozpCoordination],
        pbp_filter: str = PBP_FILTER_ALL,
        *,
        today: date | None = None,
        pbp_cache: PbpFreshnessCache | None = None,
    ) -> list[BozpCoordination]:
        try:
            return filter_by_pbp_freshness(
                items,
                pbp_filter,
                today=today,
                cache=pbp_cache,
            )
        except ValueError as error:
            raise BozpCoordinationError(str(error)) from error

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
        valid_from: date | None = None,
        valid_to: date | None = None,
        active: bool = True,
        insert_default_measures: bool = False,
        emergency_reporting: str | None = None,
        accident_reporting: str | None = None,
        fire_reporting: str | None = None,
        evacuation_instructions: str | None = None,
    ) -> BozpCoordination:
        normalized_subject = self._validate_subject(subject)
        normalized_status = self._validate_status(status)
        resolved_meeting = meeting_date or date.today()
        resolved_from, resolved_to = resolve_validity_dates(
            resolved_meeting,
            valid_from=valid_from,
            valid_to=valid_to,
        )
        self._validate_validity_range(resolved_from, resolved_to)
        coordination = BozpCoordination(
            coordination_number=self.repository.allocate_next_number(),
            meeting_date=resolved_meeting,
            place=(place or "").strip(),
            subject=normalized_subject,
            status=normalized_status,
            note=(note or "").strip(),
            emergency_reporting=self._default_procedure_text(
                emergency_reporting,
                DEFAULT_EMERGENCY_REPORTING,
            ),
            accident_reporting=self._default_procedure_text(
                accident_reporting,
                DEFAULT_ACCIDENT_REPORTING,
            ),
            fire_reporting=self._default_procedure_text(
                fire_reporting,
                DEFAULT_FIRE_REPORTING,
            ),
            evacuation_instructions=self._default_procedure_text(
                evacuation_instructions,
                DEFAULT_EVACUATION_INSTRUCTIONS,
            ),
            valid_from=resolved_from,
            valid_to=resolved_to,
            active=active,
        )
        created = self.repository.add(coordination)
        from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
            coordination_employer_service,
        )

        coordination_employer_service.ensure_main_employer(created.id)
        if insert_default_measures:
            from moduly.koordinace_bozp.sluzby.coordination_measure_service import (
                coordination_measure_service,
            )

            coordination_measure_service.insert_default_measures(created.id)
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
        valid_from: date | None = None,
        valid_to: date | None = None,
        emergency_reporting: str | None = None,
        accident_reporting: str | None = None,
        fire_reporting: str | None = None,
        evacuation_instructions: str | None = None,
    ) -> BozpCoordination | None:
        coordination = self.repository.get_by_id(coordination_id)
        if coordination is None:
            return None

        coordination.meeting_date = meeting_date or coordination.meeting_date
        coordination.place = (place or "").strip()
        coordination.subject = self._validate_subject(subject)
        coordination.status = self._validate_status(status)
        coordination.note = (note or "").strip()
        if emergency_reporting is not None:
            coordination.emergency_reporting = (emergency_reporting or "").strip()
        if accident_reporting is not None:
            coordination.accident_reporting = (accident_reporting or "").strip()
        if fire_reporting is not None:
            coordination.fire_reporting = (fire_reporting or "").strip()
        if evacuation_instructions is not None:
            coordination.evacuation_instructions = (
                evacuation_instructions or ""
            ).strip()
        if valid_from is not None:
            coordination.valid_from = valid_from
        if valid_to is not None:
            coordination.valid_to = valid_to
        self._validate_validity_range(coordination.valid_from, coordination.valid_to)
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
            raise BozpCoordinationError(SUBJECT_REQUIRED_MESSAGE)
        return normalized

    @staticmethod
    def _validate_status(status: str) -> str:
        if status not in BOZP_COORDINATION_STATUSES:
            raise BozpCoordinationError("Neplatný stav koordinace.")
        return status

    @staticmethod
    def _validate_validity_range(valid_from: date, valid_to: date) -> None:
        if valid_to < valid_from:
            raise BozpCoordinationError(
                "Datum konce platnosti nesmí být dříve než začátek platnosti."
            )

    @staticmethod
    def _default_procedure_text(value: str | None, default: str) -> str:
        text = (value or "").strip()
        return text or default


bozp_coordination_service = BozpCoordinationService()
