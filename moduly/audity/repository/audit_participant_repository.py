from sqlalchemy import func, select

from core.database.session import get_session
from moduly.audity.modely.audit_participant import AuditParticipant


class AuditParticipantRepository:
    def get_for_audit(self, audit_id: int) -> list[AuditParticipant]:
        with get_session() as session:
            stmt = (
                select(AuditParticipant)
                .where(AuditParticipant.audit_id == audit_id)
                .order_by(AuditParticipant.display_order, AuditParticipant.id)
            )
            return list(session.scalars(stmt))

    def get_by_id(self, participant_id: int) -> AuditParticipant | None:
        with get_session() as session:
            return session.get(AuditParticipant, participant_id)

    def add(self, participant: AuditParticipant) -> AuditParticipant:
        with get_session() as session:
            session.add(participant)
            session.commit()
            session.refresh(participant)
            return participant

    def update(self, participant: AuditParticipant) -> AuditParticipant:
        with get_session() as session:
            participant = session.merge(participant)
            session.commit()
            session.refresh(participant)
            return participant

    def delete(self, participant_id: int) -> bool:
        with get_session() as session:
            participant = session.get(AuditParticipant, participant_id)
            if participant is None:
                return False

            session.delete(participant)
            session.commit()
            return True

    def delete_for_audit(self, audit_id: int) -> int:
        with get_session() as session:
            stmt = select(AuditParticipant).where(AuditParticipant.audit_id == audit_id)
            participants = list(session.scalars(stmt))
            for participant in participants:
                session.delete(participant)
            session.commit()
            return len(participants)

    def max_display_order(self, audit_id: int) -> int:
        with get_session() as session:
            stmt = select(func.max(AuditParticipant.display_order)).where(
                AuditParticipant.audit_id == audit_id,
            )
            value = session.scalar(stmt)
            return int(value or 0)
