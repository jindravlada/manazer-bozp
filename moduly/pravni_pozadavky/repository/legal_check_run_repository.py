from sqlalchemy import select

from core.database.session import get_session
from moduly.pravni_pozadavky.constants import CHECK_RUN_COMPLETED
from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun


class LegalCheckRunRepository:
    def _ordered(self, stmt):
        return stmt.order_by(
            LegalCheckRun.checked_at.desc().nullslast(),
            LegalCheckRun.id.desc(),
        )

    def list_all(self, *, include_inactive: bool = False) -> list[LegalCheckRun]:
        with get_session() as session:
            stmt = self._ordered(select(LegalCheckRun))
            if not include_inactive:
                stmt = stmt.where(LegalCheckRun.active.is_(True))
            return list(session.scalars(stmt))

    def get_by_id(self, run_id: int) -> LegalCheckRun | None:
        with get_session() as session:
            return session.get(LegalCheckRun, run_id)

    def get_last_completed(self) -> LegalCheckRun | None:
        with get_session() as session:
            stmt = (
                self._ordered(select(LegalCheckRun))
                .where(LegalCheckRun.active.is_(True))
                .where(LegalCheckRun.status == CHECK_RUN_COMPLETED)
                .limit(1)
            )
            return session.scalar(stmt)

    def create(self, run: LegalCheckRun) -> LegalCheckRun:
        with get_session() as session:
            session.add(run)
            session.commit()
            session.refresh(run)
            return run

    def update(self, run: LegalCheckRun) -> LegalCheckRun:
        with get_session() as session:
            run = session.merge(run)
            session.commit()
            session.refresh(run)
            return run

    def deactivate(self, run_id: int) -> LegalCheckRun | None:
        run = self.get_by_id(run_id)
        if run is None:
            return None
        run.active = False
        return self.update(run)

    def restore(self, run_id: int) -> LegalCheckRun | None:
        run = self.get_by_id(run_id)
        if run is None:
            return None
        run.active = True
        return self.update(run)
