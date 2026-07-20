"""Služba evidence koordinací BOZP (COORD-001 / COORD-004)."""

from __future__ import annotations

from datetime import date, datetime

from moduly.koordinace_bozp.constants import (
    DEFAULT_ACCIDENT_REPORTING,
    DEFAULT_BOZP_COORDINATION_STATUS,
    DEFAULT_EMERGENCY_REPORTING,
    DEFAULT_EVACUATION_INSTRUCTIONS,
    DEFAULT_FIRE_REPORTING,
    PBP_FILTER_ALL,
    STATUS_FILTER_ALL,
    STATUS_FILTERS,
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
        status_filter: str = STATUS_FILTER_ALL,
        today: date | None = None,
        pbp_cache: PbpFreshnessCache | None = None,
    ) -> list[BozpCoordination]:
        items = self.repository.get_all(include_inactive=include_inactive)
        items = self.filter_by_validity(items, validity_filter, today=today)
        items = self.filter_by_status(items, status_filter)
        return self.filter_by_pbp(items, pbp_filter, today=today, pbp_cache=pbp_cache)

    def filter_by_status(
        self,
        items: list[BozpCoordination],
        status_filter: str = STATUS_FILTER_ALL,
    ) -> list[BozpCoordination]:
        if status_filter in ("", STATUS_FILTER_ALL, None):
            return list(items)
        if status_filter not in STATUS_FILTERS:
            raise BozpCoordinationError("Neplatný filtr stavu.")
        from moduly.koordinace_bozp.sluzby.coordination_lifecycle_service import (
            normalize_coordination_status,
        )

        return [
            item
            for item in items
            if normalize_coordination_status(item.status) == status_filter
        ]

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
        place: str | None = None,
        subject: str = "",
        status: str = DEFAULT_BOZP_COORDINATION_STATUS,
        note: str = "",
        valid_from: date | None = None,
        valid_to: date | None = None,
        active: bool = True,
        emergency_reporting: str | None = None,
        accident_reporting: str | None = None,
        fire_reporting: str | None = None,
        evacuation_instructions: str | None = None,
        work_intent_information_text: str = "",
        ppe_text: str = "",
        workplace_handover_text: str = "",
        final_provisions_text: str = "",
    ) -> BozpCoordination:
        normalized_subject = self._validate_subject(subject)
        # UX-COORD-6a: nová koordinace vždy startuje jako Rozpracováno.
        resolved_meeting = meeting_date or date.today()
        resolved_from, resolved_to = resolve_validity_dates(
            resolved_meeting,
            valid_from=valid_from,
            valid_to=valid_to,
        )
        self._validate_validity_range(resolved_from, resolved_to)
        # UX-COORD-9e: výchozí místo jen při vzniku; explicitní "" nepřepisovat.
        if place is None:
            resolved_place = default_meeting_place_from_settings()
        else:
            resolved_place = (place or "").strip()
        coordination = BozpCoordination(
            coordination_number=self.repository.allocate_next_number(),
            meeting_date=resolved_meeting,
            place=resolved_place,
            subject=normalized_subject,
            status=DEFAULT_BOZP_COORDINATION_STATUS,
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
            work_intent_information_text=(work_intent_information_text or "").strip(),
            ppe_text=(ppe_text or "").strip(),
            workplace_handover_text=(workplace_handover_text or "").strip(),
            final_provisions_text=(final_provisions_text or "").strip(),
            valid_from=resolved_from,
            valid_to=resolved_to,
            active=active,
        )
        created = self.repository.add(coordination)
        from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
            coordination_employer_service,
        )
        from moduly.koordinace_bozp.sluzby.coordination_measure_service import (
            coordination_measure_service,
        )

        coordination_employer_service.ensure_main_employer(created.id)
        coordination_measure_service.ensure_default_common_rules(created.id)
        return created

    def update_coordination(
        self,
        coordination_id: int,
        *,
        meeting_date: date | None = None,
        place: str = "",
        subject: str = "",
        status: str | None = None,
        note: str = "",
        valid_from: date | None = None,
        valid_to: date | None = None,
        emergency_reporting: str | None = None,
        accident_reporting: str | None = None,
        fire_reporting: str | None = None,
        evacuation_instructions: str | None = None,
        work_intent_information_text: str | None = None,
        ppe_text: str | None = None,
        workplace_handover_text: str | None = None,
        final_provisions_text: str | None = None,
    ) -> BozpCoordination | None:
        coordination = self.repository.get_by_id(coordination_id)
        if coordination is None:
            return None

        coordination.meeting_date = meeting_date or coordination.meeting_date
        coordination.place = (place or "").strip()
        coordination.subject = self._validate_subject(subject)
        # UX-COORD-6a: stav se mění jen přes coordination_lifecycle_service.
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
        if work_intent_information_text is not None:
            coordination.work_intent_information_text = (
                work_intent_information_text or ""
            ).strip()
        if ppe_text is not None:
            coordination.ppe_text = (ppe_text or "").strip()
        if workplace_handover_text is not None:
            coordination.workplace_handover_text = (
                workplace_handover_text or ""
            ).strip()
        if final_provisions_text is not None:
            coordination.final_provisions_text = (
                final_provisions_text or ""
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
    def _validate_validity_range(valid_from: date, valid_to: date) -> None:
        if valid_to < valid_from:
            raise BozpCoordinationError(
                "Datum konce platnosti nesmí být dříve než začátek platnosti."
            )

    @staticmethod
    def _default_procedure_text(value: str | None, default: str) -> str:
        text = (value or "").strip()
        return text or default


def compose_company_seat_address(
    *,
    street: str = "",
    postal_code: str = "",
    city: str = "",
) -> str:
    """Sestaví čitelnou adresu sídla bez prázdných částí a nadbytečných čárek."""
    street_part = " ".join((street or "").split())
    postal_part = " ".join((postal_code or "").split())
    city_part = " ".join((city or "").split())
    locality = " ".join(part for part in (postal_part, city_part) if part)
    return ", ".join(part for part in (street_part, locality) if part)


def default_meeting_place_from_settings() -> str:
    """Adresa sídla z Nastavení → Zaměstnavatel (nebo prázdný řetězec)."""
    from moduly.nastaveni.sluzby.settings_service import settings_service

    employer = settings_service.get_employer()
    if employer is None:
        return ""
    address = (employer.address or "").strip()
    if not address:
        return ""
    # Uložená adresa je už jeden text (např. z ARES); nepoužívat doslovné „sídlo“.
    return address


bozp_coordination_service = BozpCoordinationService()
