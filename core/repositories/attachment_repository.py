from sqlalchemy import select

from core.database.session import get_session
from core.models.attachment import Attachment


class AttachmentRepository:
    def get_for_entity(self, entity_type: str, entity_id: int) -> list[Attachment]:
        with get_session() as session:
            stmt = (
                select(Attachment)
                .where(
                    Attachment.entity_type == entity_type,
                    Attachment.entity_id == entity_id,
                )
                .order_by(Attachment.created_at, Attachment.id)
            )
            return list(session.scalars(stmt))

    def add(self, attachment: Attachment) -> Attachment:
        with get_session() as session:
            session.add(attachment)
            session.commit()
            session.refresh(attachment)
            return attachment

    def update(self, attachment: Attachment) -> Attachment:
        with get_session() as session:
            attachment = session.merge(attachment)
            session.commit()
            session.refresh(attachment)
            return attachment

    def delete(self, attachment_id: int) -> bool:
        with get_session() as session:
            attachment = session.get(Attachment, attachment_id)
            if attachment is None:
                return False

            session.delete(attachment)
            session.commit()
            return True
