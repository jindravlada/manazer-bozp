"""Služba účastníků koordinační schůzky (COORD-003)."""

from __future__ import annotations

from datetime import datetime

from moduly.koordinace_bozp.constants import (
    COORDINATION_PARTICIPANT_SOURCE_EMPLOYEE,
    COORDINATION_PARTICIPANT_SOURCE_MANUAL,
    COORDINATION_PARTICIPANT_SOURCE_TYPES,
)
from moduly.koordinace_bozp.modely.coordination_participant import (
    CoordinationParticipant,
)
from moduly.koordinace_bozp.repository.coordination_employer_repository import (
    CoordinationEmployerRepository,
)
from moduly.koordinace_bozp.repository.coordination_participant_repository import (
    CoordinationParticipantRepository,
)
from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
    coordination_employer_service,
    employer_abbreviation,
)
from moduly.nastaveni.sluzby.settings_service import settings_service


class CoordinationParticipantError(ValueError):
    pass


def normalize_participant_name(full_name: str) -> str:
    return " ".join((full_name or "").strip().split())


def snapshot_from_employee(employee_id: int) -> dict:
    """Načte snapshot údajů z evidence THP (nemění evidenci)."""
    worker = settings_service.get_worker_by_id(employee_id)
    if worker is None:
        raise CoordinationParticipantError("Vybraný pracovník nebyl v evidenci nalezen.")
    return {
        "person_source_type": COORDINATION_PARTICIPANT_SOURCE_EMPLOYEE,
        "employee_id": worker.id,
        "full_name": worker.display_name or normalize_participant_name(
            f"{worker.first_name} {worker.last_name}"
        ),
        "role": (worker.position or "").strip(),
        "phone": (worker.phone or "").strip(),
        "email": (worker.email or "").strip(),
    }


class CoordinationParticipantService:
    def __init__(self) -> None:
        self.repository = CoordinationParticipantRepository()
        self.employer_repository = CoordinationEmployerRepository()

    def list_for_employer(
        self,
        coordination_employer_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationParticipant]:
        return self.repository.list_for_employer(
            coordination_employer_id,
            include_inactive=include_inactive,
        )

    def list_for_coordination(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationParticipant]:
        """Účastníci všech zaměstnavatelů koordinace (UX-COORD-12a)."""
        if not coordination_id:
            return []
        items = self.repository.list_for_coordination(
            coordination_id,
            include_inactive=include_inactive,
        )
        employers = {
            employer.id: employer
            for employer in coordination_employer_service.list_for_coordination(
                coordination_id,
                include_inactive=True,
            )
        }

        def sort_key(item: CoordinationParticipant) -> tuple:
            employer = employers.get(item.coordination_employer_id)
            if employer is None:
                employer_key = (10_000, "", item.coordination_employer_id or 0)
            else:
                employer_key = (
                    int(employer.sort_order or 0),
                    (employer.company_name or "").casefold(),
                    int(employer.id),
                )
            return (
                employer_key,
                normalize_participant_name(item.full_name).casefold(),
                (item.role or "").strip().casefold(),
                item.id,
            )

        return sorted(items, key=sort_key)

    def get_by_id(self, participant_id: int | None) -> CoordinationParticipant | None:
        if not participant_id:
            return None
        return self.repository.get_by_id(participant_id)

    def employer_short_label(self, coordination_employer_id: int | None) -> str:
        """Zkratka zaměstnavatele (ne zkratka i název současně)."""
        if not coordination_employer_id:
            return ""
        employer = coordination_employer_service.get_by_id(coordination_employer_id)
        if employer is None:
            return ""
        label = employer_abbreviation(employer).strip()
        if not label:
            label = (employer.company_name or "").strip()
        if not employer.active:
            label = f"{label} (neaktivní)" if label else "(neaktivní)"
        return label

    def default_employer_id(self, coordination_id: int) -> int | None:
        """První aktivní zúčastněný, jinak hlavní zaměstnavatel."""
        employers = coordination_employer_service.list_for_coordination(
            coordination_id,
            include_inactive=True,
        )
        active = [item for item in employers if item.active]
        for employer in active:
            if not employer.is_main:
                return employer.id
        for employer in active:
            if employer.is_main:
                return employer.id
        return active[0].id if active else None

    def add_from_employee(
        self,
        coordination_employer_id: int,
        employee_id: int,
        *,
        full_name: str | None = None,
        role: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        note: str = "",
        active: bool = True,
    ) -> CoordinationParticipant:
        employer = self._require_active_employer(coordination_employer_id)
        if not employer.is_main:
            raise CoordinationParticipantError(
                "Výběr z evidence THP je dostupný pouze u hlavního zaměstnavatele."
            )
        snapshot = snapshot_from_employee(employee_id)
        return self._create_participant(
            coordination_employer_id=coordination_employer_id,
            person_source_type=COORDINATION_PARTICIPANT_SOURCE_EMPLOYEE,
            employee_id=snapshot["employee_id"],
            full_name=full_name if full_name is not None else snapshot["full_name"],
            role=role if role is not None else snapshot["role"],
            phone=phone if phone is not None else snapshot["phone"],
            email=email if email is not None else snapshot["email"],
            note=note,
            active=active,
        )

    def add_manual(
        self,
        coordination_employer_id: int,
        *,
        full_name: str,
        role: str = "",
        phone: str = "",
        email: str = "",
        note: str = "",
        active: bool = True,
    ) -> CoordinationParticipant:
        self._require_active_employer(coordination_employer_id)
        return self._create_participant(
            coordination_employer_id=coordination_employer_id,
            person_source_type=COORDINATION_PARTICIPANT_SOURCE_MANUAL,
            employee_id=None,
            full_name=full_name,
            role=role,
            phone=phone,
            email=email,
            note=note,
            active=active,
        )

    def update_participant(
        self,
        participant_id: int,
        *,
        full_name: str | None = None,
        role: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        note: str | None = None,
    ) -> CoordinationParticipant | None:
        participant = self.repository.get_by_id(participant_id)
        if participant is None:
            return None

        if full_name is not None:
            participant.full_name = self._validate_full_name(
                full_name,
                coordination_employer_id=participant.coordination_employer_id,
                exclude_participant_id=participant.id,
            )
        if role is not None:
            participant.role = (role or "").strip()
        if phone is not None:
            participant.phone = (phone or "").strip()
        if email is not None:
            participant.email = (email or "").strip()
        if note is not None:
            participant.note = (note or "").strip()
        participant.updated_at = datetime.now()
        return self.repository.update(participant)

    def activate(self, participant_id: int) -> bool:
        participant = self.repository.get_by_id(participant_id)
        if participant is None:
            return False
        participant.active = True
        participant.updated_at = datetime.now()
        self.repository.update(participant)
        return True

    def deactivate(self, participant_id: int) -> bool:
        participant = self.repository.get_by_id(participant_id)
        if participant is None:
            return False
        participant.active = False
        participant.updated_at = datetime.now()
        self.repository.update(participant)
        return True

    def _create_participant(
        self,
        *,
        coordination_employer_id: int,
        person_source_type: str,
        employee_id: int | None,
        full_name: str,
        role: str,
        phone: str,
        email: str,
        note: str,
        active: bool,
    ) -> CoordinationParticipant:
        if person_source_type not in COORDINATION_PARTICIPANT_SOURCE_TYPES:
            raise CoordinationParticipantError("Neplatný zdroj osoby.")
        normalized_name = self._validate_full_name(
            full_name,
            coordination_employer_id=coordination_employer_id,
        )
        participant = CoordinationParticipant(
            coordination_employer_id=coordination_employer_id,
            person_source_type=person_source_type,
            employee_id=employee_id,
            full_name=normalized_name,
            role=(role or "").strip(),
            phone=(phone or "").strip(),
            email=(email or "").strip(),
            note=(note or "").strip(),
            active=active,
            sort_order=self.repository.next_sort_order(coordination_employer_id),
        )
        return self.repository.add(participant)

    def _require_active_employer(self, coordination_employer_id: int):
        employer = self.employer_repository.get_by_id(coordination_employer_id)
        if employer is None:
            raise CoordinationParticipantError("Zaměstnavatel nebyl nalezen.")
        if not employer.active:
            raise CoordinationParticipantError(
                "K deaktivovanému zaměstnavateli nelze přidat účastníka."
            )
        return employer

    def _validate_full_name(
        self,
        full_name: str,
        *,
        coordination_employer_id: int,
        exclude_participant_id: int | None = None,
    ) -> str:
        normalized = normalize_participant_name(full_name)
        if not normalized:
            raise CoordinationParticipantError("Jméno a příjmení jsou povinné.")

        key = normalized.casefold()
        for item in self.repository.list_for_employer(
            coordination_employer_id,
            include_inactive=True,
        ):
            if exclude_participant_id is not None and item.id == exclude_participant_id:
                continue
            if normalize_participant_name(item.full_name).casefold() == key:
                raise CoordinationParticipantError(
                    f"Účastník „{normalized}“ je u tohoto zaměstnavatele již evidován."
                )
        return normalized


coordination_participant_service = CoordinationParticipantService()
