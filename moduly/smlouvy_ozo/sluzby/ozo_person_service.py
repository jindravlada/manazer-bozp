"""Služba údajů odborně způsobilé osoby a historických verzí."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from moduly.smlouvy_ozo.constants import format_ozo_display_name
from moduly.smlouvy_ozo.modely.ozo_person import OzoPerson
from moduly.smlouvy_ozo.modely.ozo_person_period import OzoPersonPeriod
from moduly.smlouvy_ozo.repository.ozo_person_period_repository import (
    OzoPersonPeriodRepository,
)
from moduly.smlouvy_ozo.repository.ozo_person_repository import OzoPersonRepository


class OzoPersonValidationError(Exception):
    pass


def period_covers_calendar_year(period: OzoPersonPeriod, year: int) -> bool:
    """True, pokud verze zasahuje do kalendářního roku R."""
    year = int(year)
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    if period.valid_from is None or period.valid_from > year_end:
        return False
    if period.valid_to is None:
        return True
    return period.valid_to >= year_start


def clip_period_to_year(
    period: OzoPersonPeriod, year: int
) -> tuple[date, date]:
    """Období verze omezené na kalendářní rok R (pro výstup)."""
    year = int(year)
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    start = max(period.valid_from, year_start)
    end = year_end if period.valid_to is None else min(period.valid_to, year_end)
    return start, end


class OzoPersonService:
    def __init__(
        self,
        repository: OzoPersonRepository | None = None,
        period_repository: OzoPersonPeriodRepository | None = None,
    ):
        self.repository = repository or OzoPersonRepository()
        self.period_repository = period_repository or OzoPersonPeriodRepository()

    def get(self) -> OzoPerson | None:
        person = self.repository.get()
        if person is not None:
            self.ensure_migrated(person)
        return person

    def get_or_empty(self) -> OzoPerson:
        person = self.get()
        if person is not None:
            return person
        return OzoPerson()

    def get_open_period(self, person: OzoPerson | None = None) -> OzoPersonPeriod | None:
        person = person if person is not None else self.get()
        if person is None or person.id is None:
            return None
        self.ensure_migrated(person)
        return self.period_repository.get_open(person.id)

    def list_periods(self, person: OzoPerson | None = None) -> list[OzoPersonPeriod]:
        person = person if person is not None else self.get()
        if person is None or person.id is None:
            return []
        self.ensure_migrated(person)
        return self.period_repository.list_for_person(person.id)

    def list_closed_periods(
        self, person: OzoPerson | None = None
    ) -> list[OzoPersonPeriod]:
        return [p for p in self.list_periods(person) if p.valid_to is not None]

    def get_period(self, period_id: int) -> OzoPersonPeriod | None:
        return self.period_repository.get_by_id(period_id)

    def periods_for_year(self, year: int) -> list[OzoPersonPeriod]:
        person = self.get()
        if person is None:
            return []
        rows = [
            period
            for period in self.list_periods(person)
            if period_covers_calendar_year(period, year)
        ]
        rows.sort(key=lambda item: (item.valid_from, item.id or 0))
        return rows

    def ensure_migrated(self, person: OzoPerson | None = None) -> OzoPersonPeriod | None:
        """Zajistí první historickou verzi ze singleton údajů + přesun příloh."""
        person = person if person is not None else self.repository.get()
        if person is None or person.id is None:
            return None
        existing = self.period_repository.get_open(person.id)
        if existing is not None:
            return existing
        if self.period_repository.count_for_person(person.id) > 0:
            # pouze uzavřené – otevři poslední? nemělo by nastat; vrať None
            periods = self.period_repository.list_for_person(person.id)
            return periods[0] if periods else None

        valid_from = self._initial_valid_from(person)
        period = OzoPersonPeriod(
            ozo_person_id=person.id,
            valid_from=valid_from,
            valid_to=None,
            title_before=getattr(person, "title_before", "") or "",
            first_name=person.first_name or "",
            last_name=person.last_name or "",
            title_after=getattr(person, "title_after", "") or "",
            residence_address=person.residence_address or "",
            exam_date=person.exam_date,
            certificate_number=person.certificate_number or "",
            certificate_valid_to=person.certificate_valid_to,
            note=person.note or "",
        )
        period = self.period_repository.add(period)
        self._migrate_person_attachments(person.id, period.id)
        return period

    def save(
        self,
        *,
        title_before: str = "",
        first_name: str = "",
        last_name: str = "",
        title_after: str = "",
        residence_address: str = "",
        exam_date: date | None = None,
        certificate_number: str = "",
        certificate_valid_to: date | None = None,
        note: str = "",
    ) -> OzoPerson:
        person = self.repository.get()
        if person is None:
            person = OzoPerson()

        fields = {
            "title_before": (title_before or "").strip(),
            "first_name": (first_name or "").strip(),
            "last_name": (last_name or "").strip(),
            "title_after": (title_after or "").strip(),
            "residence_address": (residence_address or "").strip(),
            "exam_date": exam_date,
            "certificate_number": (certificate_number or "").strip(),
            "certificate_valid_to": certificate_valid_to,
            "note": (note or "").strip(),
        }

        # Nejdřív uložit osobu (kvůli ID), pak verze.
        self._apply_fields_to_person(person, fields)
        person.updated_at = datetime.now()
        person = self.repository.save(person)

        open_period = self.ensure_migrated(person)
        if open_period is None:
            open_period = self._create_period(person.id, fields, valid_from=None)
        elif self._is_new_exam(open_period, fields):
            new_from = fields["exam_date"]
            assert new_from is not None
            if new_from <= open_period.valid_from:
                raise OzoPersonValidationError(
                    "Datum nové zkoušky musí být později než začátek "
                    "platnosti současné verze údajů OZO."
                )
            open_period.valid_to = new_from - timedelta(days=1)
            # Uzavřenou verzi už jinak nepřepisovat – jen valid_to.
            self.period_repository.update(open_period)
            open_period = self._create_period(person.id, fields, valid_from=new_from)
        else:
            if open_period.valid_to is not None:
                raise OzoPersonValidationError(
                    "Uzavřenou historickou verzi OZO nelze upravovat."
                )
            self._apply_fields_to_period(open_period, fields)
            open_period = self.period_repository.update(open_period)

        self._apply_fields_to_person(person, fields)
        person.updated_at = datetime.now()
        return self.repository.save(person)

    def missing_for_list_output(self, person: OzoPerson | None = None) -> list[str]:
        """Povinné u aktuální otevřené verze."""
        person = person if person is not None else self.get()
        period = self.get_open_period(person) if person is not None else None
        return self._missing_on_period(period)

    def missing_for_year(self, year: int) -> list[str]:
        """Povinné u všech verzí zasahujících do roku R."""
        periods = self.periods_for_year(year)
        if not periods:
            # žádná verze v roce → kontrola aktuální otevřené (prázdná evidence)
            return self.missing_for_list_output()
        missing: list[str] = []
        seen: set[str] = set()
        for period in periods:
            for item in self._missing_on_period(period):
                label = item
                if len(periods) > 1:
                    label = (
                        f"{item} (verze od {period.valid_from.strftime('%d.%m.%Y')})"
                    )
                if label not in seen:
                    seen.add(label)
                    missing.append(label)
        return missing

    def full_name(self, source: OzoPerson | OzoPersonPeriod | None = None) -> str:
        if source is None:
            source = self.get_open_period() or self.get()
        if source is None:
            return ""
        return format_ozo_display_name(
            getattr(source, "title_before", "") or "",
            getattr(source, "first_name", "") or "",
            getattr(source, "last_name", "") or "",
            getattr(source, "title_after", "") or "",
        )

    def _missing_on_period(self, period: OzoPersonPeriod | None) -> list[str]:
        missing: list[str] = []
        if period is None or not (period.first_name or "").strip():
            missing.append("Jméno")
        if period is None or not (period.last_name or "").strip():
            missing.append("Příjmení")
        if period is None or not (period.certificate_number or "").strip():
            missing.append("Číslo osvědčení")
        return missing

    def _is_new_exam(self, open_period: OzoPersonPeriod, fields: dict) -> bool:
        new_exam = fields.get("exam_date")
        if new_exam is None:
            return False
        previous = open_period.exam_date
        if previous is None:
            return new_exam > open_period.valid_from
        return new_exam != previous and new_exam > open_period.valid_from

    def _initial_valid_from(self, person: OzoPerson) -> date:
        if person.exam_date is not None:
            return person.exam_date
        if person.created_at is not None:
            return person.created_at.date()
        return date.today()

    def _create_period(
        self,
        ozo_person_id: int,
        fields: dict,
        *,
        valid_from: date | None,
    ) -> OzoPersonPeriod:
        start = valid_from
        if start is None:
            start = fields.get("exam_date") or date.today()
        period = OzoPersonPeriod(
            ozo_person_id=ozo_person_id,
            valid_from=start,
            valid_to=None,
        )
        self._apply_fields_to_period(period, fields)
        return self.period_repository.add(period)

    @staticmethod
    def _apply_fields_to_period(period: OzoPersonPeriod, fields: dict) -> None:
        period.title_before = fields["title_before"]
        period.first_name = fields["first_name"]
        period.last_name = fields["last_name"]
        period.title_after = fields["title_after"]
        period.residence_address = fields["residence_address"]
        period.exam_date = fields["exam_date"]
        period.certificate_number = fields["certificate_number"]
        period.certificate_valid_to = fields["certificate_valid_to"]
        period.note = fields["note"]

    @staticmethod
    def _apply_fields_to_person(person: OzoPerson, fields: dict) -> None:
        person.title_before = fields["title_before"]
        person.first_name = fields["first_name"]
        person.last_name = fields["last_name"]
        person.title_after = fields["title_after"]
        person.residence_address = fields["residence_address"]
        person.exam_date = fields["exam_date"]
        person.certificate_number = fields["certificate_number"]
        person.certificate_valid_to = fields["certificate_valid_to"]
        person.note = fields["note"]

    def _migrate_person_attachments(self, person_id: int, period_id: int) -> None:
        from core.services.attachment_service import attachment_service
        from moduly.smlouvy_ozo.constants import (
            ENTITY_OZO_PERSON,
            ENTITY_OZO_PERSON_PERIOD,
        )

        attachment_service.rebind_entity(
            ENTITY_OZO_PERSON,
            person_id,
            ENTITY_OZO_PERSON_PERIOD,
            period_id,
        )


ozo_person_service = OzoPersonService()
