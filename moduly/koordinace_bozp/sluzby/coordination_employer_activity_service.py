"""Služba činností zúčastněných zaměstnavatelů (COORD-008)."""

from __future__ import annotations

from datetime import date, datetime

from moduly.koordinace_bozp.modely.coordination_employer_activity import (
    CoordinationEmployerActivity,
)
from moduly.koordinace_bozp.repository.coordination_employer_activity_repository import (
    CoordinationEmployerActivityRepository,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    coordination_employer_service,
)
from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
    coordination_workplace_service,
)


class CoordinationEmployerActivityError(ValueError):
    pass


def normalize_activity_name(value: str) -> str:
    return " ".join((value or "").strip().split())


class CoordinationEmployerActivityService:
    def __init__(self) -> None:
        self.repository = CoordinationEmployerActivityRepository()

    def list_for_employer(
        self,
        coordination_employer_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationEmployerActivity]:
        return self.repository.list_for_employer(
            coordination_employer_id,
            include_inactive=include_inactive,
        )

    def get_by_id(self, activity_id: int | None) -> CoordinationEmployerActivity | None:
        if not activity_id:
            return None
        return self.repository.get_by_id(activity_id)

    def workplace_label(self, workplace_link_id: int | None) -> str:
        if not workplace_link_id:
            return ""
        place = coordination_workplace_service.get_by_id(workplace_link_id)
        if place is None:
            return ""
        operation, workplace, part = coordination_workplace_service.workplace_display_names(
            place
        )
        parts = [item for item in (operation, workplace, part) if item]
        label = " / ".join(parts)
        if not place.active:
            label = f"{label} (neaktivní)" if label else "(neaktivní)"
        return label

    def add(
        self,
        coordination_employer_id: int,
        *,
        activity_name: str,
        coordination_workplace_id: int | None = None,
        description: str = "",
        planned_from: date | None = None,
        planned_to: date | None = None,
        note: str = "",
        active: bool = True,
    ) -> CoordinationEmployerActivity:
        employer = self._require_active_employer(coordination_employer_id)
        name = self._validate_activity_name(activity_name)
        workplace_id = self._validate_workplace(
            employer.coordination_id,
            coordination_workplace_id,
        )
        self._validate_period(planned_from, planned_to)
        self._ensure_unique(
            coordination_employer_id,
            activity_name=name,
            coordination_workplace_id=workplace_id,
        )
        activity = CoordinationEmployerActivity(
            coordination_employer_id=coordination_employer_id,
            coordination_workplace_id=workplace_id,
            activity_name=name,
            description=(description or "").strip(),
            planned_from=planned_from,
            planned_to=planned_to,
            note=(note or "").strip(),
            active=active,
            sort_order=self.repository.next_sort_order(coordination_employer_id),
        )
        return self.repository.add(activity)

    def update(
        self,
        activity_id: int,
        *,
        coordination_employer_id: int,
        activity_name: str,
        coordination_workplace_id: int | None = None,
        description: str = "",
        planned_from: date | None = None,
        planned_to: date | None = None,
        note: str = "",
    ) -> CoordinationEmployerActivity | None:
        activity = self.repository.get_by_id(activity_id)
        if activity is None:
            return None

        employer = self._require_active_employer(coordination_employer_id)
        name = self._validate_activity_name(activity_name)
        workplace_id = self._validate_workplace(
            employer.coordination_id,
            coordination_workplace_id,
        )
        self._validate_period(planned_from, planned_to)
        self._ensure_unique(
            coordination_employer_id,
            activity_name=name,
            coordination_workplace_id=workplace_id,
            exclude_id=activity.id,
        )

        activity.coordination_employer_id = coordination_employer_id
        activity.coordination_workplace_id = workplace_id
        activity.activity_name = name
        activity.description = (description or "").strip()
        activity.planned_from = planned_from
        activity.planned_to = planned_to
        activity.note = (note or "").strip()
        activity.updated_at = datetime.now()
        return self.repository.update(activity)

    def activate(self, activity_id: int) -> bool:
        activity = self.repository.get_by_id(activity_id)
        if activity is None:
            return False
        employer = self._require_active_employer(activity.coordination_employer_id)
        if activity.coordination_workplace_id is not None:
            self._validate_workplace(
                employer.coordination_id,
                activity.coordination_workplace_id,
            )
        self._ensure_unique(
            activity.coordination_employer_id,
            activity_name=activity.activity_name,
            coordination_workplace_id=activity.coordination_workplace_id,
            exclude_id=activity.id,
            active_only=True,
        )
        activity.active = True
        activity.updated_at = datetime.now()
        self.repository.update(activity)
        return True

    def deactivate(self, activity_id: int) -> bool:
        activity = self.repository.get_by_id(activity_id)
        if activity is None:
            return False
        activity.active = False
        activity.updated_at = datetime.now()
        self.repository.update(activity)
        return True

    def _require_active_employer(self, coordination_employer_id: int):
        if not coordination_employer_id:
            raise CoordinationEmployerActivityError("Zaměstnavatel je povinný.")
        employer = coordination_employer_service.get_by_id(coordination_employer_id)
        if employer is None:
            raise CoordinationEmployerActivityError("Zaměstnavatel nebyl nalezen.")
        if not employer.active:
            raise CoordinationEmployerActivityError(
                "Nelze použít deaktivovaného zaměstnavatele."
            )
        return employer

    def _validate_activity_name(self, activity_name: str) -> str:
        name = normalize_activity_name(activity_name)
        if not name:
            raise CoordinationEmployerActivityError("Název činnosti je povinný.")
        return name

    def _validate_workplace(
        self,
        coordination_id: int,
        coordination_workplace_id: int | None,
    ) -> int | None:
        if not coordination_workplace_id:
            return None
        place = coordination_workplace_service.get_by_id(coordination_workplace_id)
        if place is None:
            raise CoordinationEmployerActivityError("Místo výkonu práce nebylo nalezeno.")
        if place.coordination_id != coordination_id:
            raise CoordinationEmployerActivityError(
                "Místo nepatří k této koordinaci."
            )
        if not place.active:
            raise CoordinationEmployerActivityError(
                "Nelze použít deaktivované místo výkonu práce."
            )
        return place.id

    @staticmethod
    def _validate_period(
        planned_from: date | None,
        planned_to: date | None,
    ) -> None:
        if planned_from is not None and planned_to is not None and planned_to < planned_from:
            raise CoordinationEmployerActivityError(
                "Datum „Do“ nesmí být před datem „Od“."
            )

    def _ensure_unique(
        self,
        coordination_employer_id: int,
        *,
        activity_name: str,
        coordination_workplace_id: int | None,
        exclude_id: int | None = None,
        active_only: bool = False,
    ) -> None:
        needle = normalize_activity_name(activity_name).casefold()
        for item in self.repository.list_for_employer(
            coordination_employer_id,
            include_inactive=not active_only,
        ):
            if exclude_id is not None and item.id == exclude_id:
                continue
            if active_only and not item.active:
                continue
            if (
                normalize_activity_name(item.activity_name).casefold() == needle
                and (item.coordination_workplace_id or None)
                == (coordination_workplace_id or None)
            ):
                raise CoordinationEmployerActivityError(
                    "Stejná činnost je u tohoto zaměstnavatele a místa již evidována."
                )


coordination_employer_activity_service = CoordinationEmployerActivityService()
