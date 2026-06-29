from sqlalchemy import select

from core.database.session import get_session
from moduly.audity.modely.internal_audit import InternalAudit


class InternalAuditRepository:
    def get_all(self) -> list[InternalAudit]:
        with get_session() as session:
            stmt = select(InternalAudit).order_by(
                InternalAudit.audit_date.desc(),
                InternalAudit.id.desc(),
            )
            return list(session.scalars(stmt))

    def get_by_id(self, audit_id: int) -> InternalAudit | None:
        with get_session() as session:
            return session.get(InternalAudit, audit_id)

    def add(self, audit: InternalAudit) -> InternalAudit:
        with get_session() as session:
            session.add(audit)
            session.commit()
            session.refresh(audit)
            return audit

    def update(self, audit: InternalAudit) -> InternalAudit:
        with get_session() as session:
            audit = session.merge(audit)
            session.commit()
            session.refresh(audit)
            return audit

    def delete(self, audit_id: int) -> bool:
        with get_session() as session:
            audit = session.get(InternalAudit, audit_id)
            if audit is None:
                return False

            session.delete(audit)
            session.commit()
            return True
