"""Služba pověřeného koordinátora BOZP (COORD-005)."""

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
        return self.repository.find_by_participant(participant_id) is not None

    def set_coordinator(
        self,
        coordination_id: int,
        *,
        employer_id: int,
        participant_id: int,
        note: str = "",
    ) -> CoordinationCoordinator:
        employer = self.employer_repository.get_by_id(employer_id)
        if employer is None:
            raise CoordinationCoordinatorError("Zaměstnavatel nebyl nalezen.")
        if employer.coordination_id != coordination_id:
            raise CoordinationCoordinatorError(
                "Zaměstnavatel nepatří k této koordinaci."
            )
        if not employer.active:
            raise CoordinationCoordinatorError(
                "Nelze vybrat deaktivovaného zaměstnavatele."
            )

        participant = self.participant_repository.get_by_id(participant_id)
        if participant is None:
            raise CoordinationCoordinatorError("Účastník nebyl nalezen.")
        if participant.coordination_employer_id != employer.id:
            raise CoordinationCoordinatorError(
                "Účastník nepatří k vybranému zaměstnavateli."
            )
        if not participant.active:
            raise CoordinationCoordinatorError(
                "Koordinátor musí být aktivní účastník schůzky."
            )

        existing = self.repository.get_for_coordination(
            coordination_id,
            include_inactive=True,
        )
        if existing is not None:
            existing.employer_id = employer.id
            existing.participant_id = participant.id
            existing.note = (note or "").strip()
            existing.active = True
            existing.updated_at = datetime.now()
            return self.repository.update(existing)

        coordinator = CoordinationCoordinator(
            coordination_id=coordination_id,
            employer_id=employer.id,
            participant_id=participant.id,
            note=(note or "").strip(),
            active=True,
        )
        return self.repository.add(coordinator)


coordination_coordinator_service = CoordinationCoordinatorService()
