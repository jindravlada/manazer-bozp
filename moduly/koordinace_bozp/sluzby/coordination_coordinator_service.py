"""Služba pověřeného koordinátora BOZP (COORD-005 / UX-COORD-2)."""

from __future__ import annotations

from datetime import datetime

from moduly.koordinace_bozp.modely.coordination_coordinator import (
    CoordinationCoordinator,
)
from moduly.koordinace_bozp.repository.coordination_coordinator_repository import (
    CoordinationCoordinatorRepository,
)
from moduly.koordinace_bozp.repository.coordination_employer_repository import (
    CoordinationEmployerRepository,
)
from moduly.koordinace_bozp.repository.coordination_participant_repository import (
    CoordinationParticipantRepository,
)


class CoordinationCoordinatorError(ValueError):
    pass


def normalize_coordinator_name(value: str) -> str:
    return " ".join((value or "").strip().split())


class CoordinationCoordinatorService:
    def __init__(self) -> None:
        self.repository = CoordinationCoordinatorRepository()
        self.employer_repository = CoordinationEmployerRepository()
        self.participant_repository = CoordinationParticipantRepository()

    def get_for_coordination(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = False,
    ) -> CoordinationCoordinator | None:
        return self.repository.get_for_coordination(
            coordination_id,
            include_inactive=include_inactive,
        )

    def is_participant_coordinator(self, participant_id: int) -> bool:
        if not participant_id:
            return False
        return self.repository.find_by_participant(participant_id) is not None

    def snapshot_from_participant(self, participant_id: int) -> dict:
        """Snapshot aktivního účastníka pro uložení / předvyplnění."""
        participant = self.participant_repository.get_by_id(participant_id)
        if participant is None:
            raise CoordinationCoordinatorError("Účastník nebyl nalezen.")
        if not participant.active:
            raise CoordinationCoordinatorError(
                "Koordinátor musí být aktivní účastník schůzky."
            )
        employer = self.employer_repository.get_by_id(
            participant.coordination_employer_id
        )
        if employer is None:
            raise CoordinationCoordinatorError("Zaměstnavatel nebyl nalezen.")
        if not employer.active:
            raise CoordinationCoordinatorError(
                "Nelze vybrat deaktivovaného zaměstnavatele."
            )
        return {
            "participant_id": participant.id,
            "employer_id": employer.id,
            "full_name": participant.full_name or "",
            "role": participant.role or "",
            "phone": participant.phone or "",
            "email": participant.email or "",
            "employer_name": employer.company_name or "",
        }

    def set_coordinator(
        self,
        coordination_id: int,
        *,
        participant_id: int | None = None,
        employer_id: int | None = None,
        full_name: str = "",
        role: str = "",
        phone: str = "",
        email: str = "",
        employer_name: str = "",
        note: str = "",
    ) -> CoordinationCoordinator:
        if not coordination_id:
            raise CoordinationCoordinatorError("Koordinace je povinná.")

        if participant_id:
            snapshot = self.snapshot_from_participant(participant_id)
            if employer_id is not None and employer_id != snapshot["employer_id"]:
                raise CoordinationCoordinatorError(
                    "Účastník nepatří k vybranému zaměstnavateli."
                )
            resolved = {
                "participant_id": snapshot["participant_id"],
                "employer_id": snapshot["employer_id"],
                "full_name": snapshot["full_name"],
                "role": snapshot["role"],
                "phone": snapshot["phone"],
                "email": snapshot["email"],
                "employer_name": snapshot["employer_name"],
            }
        else:
            name = normalize_coordinator_name(full_name)
            if not name:
                raise CoordinationCoordinatorError("Jméno koordinátora je povinné.")
            resolved = {
                "participant_id": None,
                "employer_id": None,
                "full_name": name,
                "role": (role or "").strip(),
                "phone": (phone or "").strip(),
                "email": (email or "").strip(),
                "employer_name": (employer_name or "").strip(),
            }

        existing = self.repository.get_for_coordination(
            coordination_id,
            include_inactive=True,
        )
        if existing is not None:
            existing.employer_id = resolved["employer_id"]
            existing.participant_id = resolved["participant_id"]
            existing.full_name = resolved["full_name"]
            existing.role = resolved["role"]
            existing.phone = resolved["phone"]
            existing.email = resolved["email"]
            existing.employer_name = resolved["employer_name"]
            existing.note = (note or "").strip()
            existing.active = True
            existing.updated_at = datetime.now()
            return self.repository.update(existing)

        coordinator = CoordinationCoordinator(
            coordination_id=coordination_id,
            employer_id=resolved["employer_id"],
            participant_id=resolved["participant_id"],
            full_name=resolved["full_name"],
            role=resolved["role"],
            phone=resolved["phone"],
            email=resolved["email"],
            employer_name=resolved["employer_name"],
            note=(note or "").strip(),
            active=True,
        )
        return self.repository.add(coordinator)


coordination_coordinator_service = CoordinationCoordinatorService()
