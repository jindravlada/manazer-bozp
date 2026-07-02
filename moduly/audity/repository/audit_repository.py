from sqlalchemy import select

from core.database.session import get_session
from moduly.audity.modely.audit import Audit


class AuditRepository:
    def get_all(self) -> list[Audit]:
        with get_session() as session:
            stmt = select(Audit).order_by(
                Audit.audit_date.desc(),
                Audit.id.desc(),
            )
            return list(session.scalars(stmt))

    def get_by_id(self, audit_id: int) -> Audit | None:
        with get_session() as session:
            return session.get(Audit, audit_id)

    def list_for_workplace(
        self,
        workplace_id: int,
        *,
        exclude_audit_id: int | None = None,
    ) -> list[Audit]:
        with get_session() as session:
            stmt = select(Audit).where(Audit.workplace_id == workplace_id)
            if exclude_audit_id is not None:
                stmt = stmt.where(Audit.id != exclude_audit_id)
            stmt = stmt.order_by(
                Audit.audit_date.desc(),
                Audit.finished_at.desc(),
                Audit.started_at.desc(),
                Audit.id.desc(),
            )
            return list(session.scalars(stmt))

    def list_for_program(self, program_id: int) -> list[Audit]:
        with get_session() as session:
            stmt = (
                select(Audit)
                .where(Audit.program_id == program_id)
                .order_by(
                    Audit.audit_date.desc(),
                    Audit.finished_at.desc(),
                    Audit.id.desc(),
                )
            )
            return list(session.scalars(stmt))

    def add(self, audit: Audit) -> Audit:
        with get_session() as session:
            session.add(audit)
            session.commit()
            session.refresh(audit)
            return audit

    def update(self, audit: Audit) -> Audit:
        with get_session() as session:
            audit = session.merge(audit)
            session.commit()
            session.refresh(audit)
            return audit

    def delete(self, audit_id: int) -> bool:
        with get_session() as session:
            audit = session.get(Audit, audit_id)
            if audit is None:
                return False

            session.delete(audit)
            session.commit()
            return True
