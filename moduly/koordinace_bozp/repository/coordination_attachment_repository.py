from sqlalchemy import select

from core.database.session import get_session
from moduly.koordinace_bozp.modely.coordination_attachment import CoordinationAttachment


class CoordinationAttachmentRepository:
    def list_for_employer(
        self,
        coordination_employer_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationAttachment]:
        with get_session() as session:
            stmt = select(CoordinationAttachment).where(
                CoordinationAttachment.coordination_employer_id
                == coordination_employer_id,
            )
            if not include_inactive:
                stmt = stmt.where(CoordinationAttachment.active == True)  # noqa: E712
            stmt = stmt.order_by(
                CoordinationAttachment.id.desc(),
            )
            return list(session.scalars(stmt))

    def list_for_coordination(
        self,
        coordination_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[CoordinationAttachment]:
        with get_session() as session:
            stmt = select(CoordinationAttachment).where(
                CoordinationAttachment.coordination_id == coordination_id,
            )
            if not include_inactive:
                stmt = stmt.where(CoordinationAttachment.active == True)  # noqa: E712
            stmt = stmt.order_by(CoordinationAttachment.id.desc())
            return list(session.scalars(stmt))

    def get_by_id(self, attachment_id: int) -> CoordinationAttachment | None:
        with get_session() as session:
            return session.get(CoordinationAttachment, attachment_id)

    def add(self, attachment: CoordinationAttachment) -> CoordinationAttachment:
        with get_session() as session:
            session.add(attachment)
            session.commit()
            session.refresh(attachment)
            return attachment

    def update(self, attachment: CoordinationAttachment) -> CoordinationAttachment:
        with get_session() as session:
            attachment = session.merge(attachment)
            session.commit()
            session.refresh(attachment)
            return attachment
