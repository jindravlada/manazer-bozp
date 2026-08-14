from collections.abc import Collection
from datetime import datetime

from sqlalchemy import select

from core.database.session import get_session
from moduly.audity.modely.audit import Audit


def _expunge(session, audit: Audit | None) -> Audit | None:
    """Odpojí audit od session — editor nikdy nedrží připojenou ORM instanci."""
    if audit is None:
        return None
    session.expunge(audit)
    return audit


class AuditRepository:
    def get_all(self) -> list[Audit]:
        with get_session() as session:
            stmt = select(Audit).order_by(
                Audit.audit_date.desc(),
                Audit.id.desc(),
            )
            audits = list(session.scalars(stmt))
            for audit in audits:
                session.expunge(audit)
            return audits

    def get_by_id(self, audit_id: int) -> Audit | None:
        with get_session() as session:
            audit = session.get(Audit, audit_id)
            return _expunge(session, audit)

    def list_for_workplace(
        self,
        workplace_id: int,
        *,
        exclude_audit_id: int | None = None,
        exclude_audit_ids: Collection[int] | None = None,
    ) -> list[Audit]:
        excluded: set[int] = set()
        if exclude_audit_id is not None:
            excluded.add(int(exclude_audit_id))
        if exclude_audit_ids:
            excluded.update(int(item) for item in exclude_audit_ids)
        with get_session() as session:
            stmt = select(Audit).where(Audit.workplace_id == workplace_id)
            if excluded:
                stmt = stmt.where(Audit.id.notin_(sorted(excluded)))
            stmt = stmt.order_by(
                Audit.audit_date.desc(),
                Audit.finished_at.desc(),
                Audit.started_at.desc(),
                Audit.id.desc(),
            )
            audits = list(session.scalars(stmt))
            for audit in audits:
                session.expunge(audit)
            return audits

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
            audits = list(session.scalars(stmt))
            for audit in audits:
                session.expunge(audit)
            return audits

    def add(self, audit: Audit) -> Audit:
        with get_session() as session:
            session.add(audit)
            session.commit()
            session.refresh(audit)
            return _expunge(session, audit)

    def update_fields(self, audit_id: int, **fields) -> Audit | None:
        """Zapíše pole do DB podle id. Nemergeuje instanci z editoru."""
        with get_session() as session:
            audit = session.get(Audit, audit_id)
            if audit is None:
                return None
            for key, value in fields.items():
                setattr(audit, key, value)
            if "updated_at" not in fields:
                audit.updated_at = datetime.now()
            session.commit()
            session.refresh(audit)
            return _expunge(session, audit)

    def update(self, audit: Audit) -> Audit:
        """Zpětná kompatibilita — uložení přes id, ne přes merge UI instance."""
        payload = {
            "number": audit.number,
            "year": audit.year,
            "planned_month": audit.planned_month,
            "audit_date": audit.audit_date,
            "started_at": audit.started_at,
            "finished_at": audit.finished_at,
            "status": audit.status,
            "audit_type": audit.audit_type,
            "workplace_id": audit.workplace_id,
            "workplace_name": audit.workplace_name,
            "title": audit.title,
            "program_id": audit.program_id,
            "program_visit_id": audit.program_visit_id,
            "silne_stranky": audit.silne_stranky,
            "changes_since_last": getattr(audit, "changes_since_last", None),
            "conclusion_text": getattr(audit, "conclusion_text", None),
            "updated_at": getattr(audit, "updated_at", None) or datetime.now(),
        }
        updated = self.update_fields(audit.id, **payload)
        if updated is None:
            raise ValueError(f"Audit id={audit.id} neexistuje.")
        return updated

    def delete(self, audit_id: int) -> bool:
        with get_session() as session:
            audit = session.get(Audit, audit_id)
            if audit is None:
                return False

            session.delete(audit)
            session.commit()
            return True
