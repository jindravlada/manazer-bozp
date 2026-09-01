from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database.session import get_session
from core.models.attachment import Attachment
from core.models.attachment_staging import AttachmentStagingError


@contextmanager
def _open_session(session: Session | None) -> Iterator[tuple[Session, bool]]:
    owns = session is None
    current = get_session() if owns else session
    try:
        yield current, owns
    except Exception:
        if owns:
            current.rollback()
        raise
    finally:
        if owns:
            current.close()


class AttachmentRepository:
    def get_for_entity(
        self,
        entity_type: str,
        entity_id: int,
        *,
        session: Session | None = None,
    ) -> list[Attachment]:
        with _open_session(session) as (sess, owns):
            stmt = (
                select(Attachment)
                .where(
                    Attachment.entity_type == entity_type,
                    Attachment.entity_id == entity_id,
                )
                .order_by(Attachment.created_at, Attachment.id)
            )
            rows = list(sess.scalars(stmt))
            if owns:
                for row in rows:
                    sess.expunge(row)
            return rows

    def get_by_id(
        self,
        attachment_id: int,
        *,
        session: Session | None = None,
    ) -> Attachment | None:
        with _open_session(session) as (sess, owns):
            record = sess.get(Attachment, int(attachment_id))
            if record is not None and owns:
                sess.expunge(record)
            return record

    def add(
        self,
        attachment: Attachment,
        *,
        session: Session | None = None,
    ) -> Attachment:
        with _open_session(session) as (sess, owns):
            sess.add(attachment)
            sess.flush()
            if owns:
                sess.commit()
                sess.refresh(attachment)
                sess.expunge(attachment)
            return attachment

    def update(
        self,
        attachment: Attachment,
        *,
        session: Session | None = None,
    ) -> Attachment:
        with _open_session(session) as (sess, owns):
            attachment = sess.merge(attachment)
            sess.flush()
            if owns:
                sess.commit()
                sess.refresh(attachment)
                sess.expunge(attachment)
            return attachment

    def delete(
        self,
        attachment_id: int,
        *,
        session: Session | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
    ) -> bool:
        """Smaže DB řádek. Bez ``session`` zachová vlastní commit.

        Caller-owned session se necommituje. Pokud je zadán rodič
        (``entity_type`` + ``entity_id``), cizí příloha se odmítne.
        Fyzický soubor se nemaže.
        """
        with _open_session(session) as (sess, owns):
            attachment = sess.get(Attachment, int(attachment_id))
            if attachment is None:
                if owns:
                    return False
                raise AttachmentStagingError(
                    f"Příloha {attachment_id} neexistuje."
                )
            if not owns and (entity_type is None or entity_id is None):
                raise AttachmentStagingError(
                    "Odložené odebrání přílohy vyžaduje typ a ID rodiče."
                )
            if entity_type is not None or entity_id is not None:
                if entity_type is None or entity_id is None:
                    raise AttachmentStagingError(
                        "Typ a ID rodiče musí být vyplněny společně."
                    )
                if (
                    str(attachment.entity_type) != str(entity_type)
                    or int(attachment.entity_id) != int(entity_id)
                ):
                    raise AttachmentStagingError(
                        "Příloha nepatří k ukládanému záznamu."
                    )
            sess.delete(attachment)
            if owns:
                sess.commit()
            else:
                sess.flush()
            return True
