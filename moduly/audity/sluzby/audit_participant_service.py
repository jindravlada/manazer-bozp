from moduly.audity.modely.audit_participant import AuditParticipant
from moduly.audity.repository.audit_participant_repository import AuditParticipantRepository


class AuditParticipantService:
    def __init__(self):
        self.repository = AuditParticipantRepository()

    def get_for_audit(self, audit_id: int) -> list[AuditParticipant]:
        return self.repository.get_for_audit(audit_id)

    def get_by_id(self, participant_id: int) -> AuditParticipant | None:
        return self.repository.get_by_id(participant_id)

    def create_participant(
        self,
        audit_id: int,
        name: str = "",
        role: str = "",
        organization: str = "",
        person_id: int | None = None,
    ) -> AuditParticipant:
        participant = AuditParticipant(
            audit_id=audit_id,
            person_id=person_id,
            name=name.strip(),
            role=role.strip(),
            organization=organization.strip(),
            display_order=self.repository.max_display_order(audit_id) + 1,
        )
        return self.repository.add(participant)

    def update_participant(
        self,
        participant_id: int,
        name: str = "",
        role: str = "",
        organization: str = "",
        person_id: int | None = None,
    ) -> AuditParticipant | None:
        participant = self.repository.get_by_id(participant_id)
        if participant is None:
            return None

        participant.person_id = person_id
        participant.name = name.strip()
        participant.role = role.strip()
        participant.organization = organization.strip()
        return self.repository.update(participant)

    def delete_participant(self, participant_id: int) -> bool:
        return self.repository.delete(participant_id)

    def delete_for_audit(self, audit_id: int) -> int:
        return self.repository.delete_for_audit(audit_id)


audit_participant_service = AuditParticipantService()
