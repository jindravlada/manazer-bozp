from sqlalchemy import select

from core.database.session import get_session
from moduly.audity.modely.audit_process_maturity_snapshot import AuditProcessMaturitySnapshot


class AuditProcessMaturitySnapshotRepository:
    def get_for_year_program_process(
        self,
        *,
        year: int,
        audit_program_id: int | None,
        process_id: str,
    ) -> AuditProcessMaturitySnapshot | None:
        with get_session() as session:
            stmt = select(AuditProcessMaturitySnapshot).where(
                AuditProcessMaturitySnapshot.year == year,
                AuditProcessMaturitySnapshot.process_id == process_id,
            )
            if audit_program_id is None:
                stmt = stmt.where(AuditProcessMaturitySnapshot.audit_program_id.is_(None))
            else:
                stmt = stmt.where(AuditProcessMaturitySnapshot.audit_program_id == audit_program_id)
            return session.scalars(stmt).first()

    def list_for_process(
        self,
        process_id: str,
        *,
        audit_program_id: int | None = None,
    ) -> list[AuditProcessMaturitySnapshot]:
        with get_session() as session:
            stmt = (
                select(AuditProcessMaturitySnapshot)
                .where(AuditProcessMaturitySnapshot.process_id == process_id)
                .order_by(AuditProcessMaturitySnapshot.year.asc())
            )
            if audit_program_id is not None:
                stmt = stmt.where(AuditProcessMaturitySnapshot.audit_program_id == audit_program_id)
            return list(session.scalars(stmt).all())

    def list_for_year(
        self,
        year: int,
        *,
        audit_program_id: int | None = None,
    ) -> list[AuditProcessMaturitySnapshot]:
        with get_session() as session:
            stmt = select(AuditProcessMaturitySnapshot).where(
                AuditProcessMaturitySnapshot.year == year,
            )
            if audit_program_id is None:
                stmt = stmt.where(AuditProcessMaturitySnapshot.audit_program_id.is_(None))
            else:
                stmt = stmt.where(AuditProcessMaturitySnapshot.audit_program_id == audit_program_id)
            stmt = stmt.order_by(AuditProcessMaturitySnapshot.process_name)
            return list(session.scalars(stmt).all())

    def save(self, snapshot: AuditProcessMaturitySnapshot) -> AuditProcessMaturitySnapshot:
        with get_session() as session:
            existing = session.scalars(
                select(AuditProcessMaturitySnapshot).where(
                    AuditProcessMaturitySnapshot.year == snapshot.year,
                    AuditProcessMaturitySnapshot.process_id == snapshot.process_id,
                    (
                        AuditProcessMaturitySnapshot.audit_program_id.is_(None)
                        if snapshot.audit_program_id is None
                        else AuditProcessMaturitySnapshot.audit_program_id == snapshot.audit_program_id
                    ),
                )
            ).first()
            if existing is None:
                session.add(snapshot)
                session.commit()
                session.refresh(snapshot)
                return snapshot

            for field in (
                "process_name",
                "maturity_level",
                "maturity_emoji",
                "maturity_label",
                "weighted_score",
                "audits_count",
                "control_points_count",
                "nevyhovuje_count",
                "doporuceni_count",
                "open_measures_count",
                "overdue_measures_count",
                "trend_direction",
                "trend_label",
                "note",
            ):
                setattr(existing, field, getattr(snapshot, field))
            session.commit()
            session.refresh(existing)
            return existing
