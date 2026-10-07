from sqlalchemy import select
from sqlalchemy.orm import Session

from core.database.session import get_session, open_session
from core.utils.czech_sort import czech_sorted, worker_sort_key
from moduly.nastaveni.modely.employer import Employer
from moduly.nastaveni.modely.thp_worker import ThpWorker
from moduly.nastaveni.modely.workplace import Workplace


class SettingsRepository:
    def get_employer(self) -> Employer | None:
        with get_session() as session:
            stmt = select(Employer).limit(1)
            return session.scalars(stmt).first()

    def list_employers(self) -> list[Employer]:
        with get_session() as session:
            return list(session.scalars(select(Employer)))

    def save_employer(self, employer: Employer) -> Employer:
        with get_session() as session:
            employer = session.merge(employer)
            session.commit()
            session.refresh(employer)
            return employer

    def get_workers(self, include_inactive: bool = False) -> list[ThpWorker]:
        with get_session() as session:
            stmt = select(ThpWorker)
            if not include_inactive:
                stmt = stmt.where(ThpWorker.active == True)  # noqa: E712

            workers = list(session.scalars(stmt))

        return czech_sorted(workers, key=worker_sort_key)

    def get_workers_for_controls(self) -> list[ThpWorker]:
        with get_session() as session:
            stmt = select(ThpWorker).where(
                ThpWorker.active == True,  # noqa: E712
                ThpWorker.performs_controls == True,  # noqa: E712
            )
            workers = list(session.scalars(stmt))

        return czech_sorted(workers, key=worker_sort_key)

    def get_worker_by_id(
        self,
        worker_id: int,
        *,
        session: Session | None = None,
    ) -> ThpWorker | None:
        with open_session(session) as (current, owns):
            worker = current.get(ThpWorker, worker_id)
            if worker is not None and owns:
                current.expunge(worker)
            return worker

    def save_worker(self, worker: ThpWorker) -> ThpWorker:
        with get_session() as session:
            worker = session.merge(worker)
            session.commit()
            session.refresh(worker)
            return worker

    def get_workplaces(self, include_inactive: bool = False) -> list[Workplace]:
        with get_session() as session:
            stmt = select(Workplace)
            if not include_inactive:
                stmt = stmt.where(Workplace.active == True)  # noqa: E712

            workplaces = list(session.scalars(stmt))

        return workplaces

    def get_all_workplaces(self, include_inactive: bool = False) -> list[Workplace]:
        return self.get_workplaces(include_inactive=include_inactive)

    def get_workplace_by_id(
        self,
        workplace_id: int,
        *,
        session: Session | None = None,
    ) -> Workplace | None:
        with open_session(session) as (current, owns):
            workplace = current.get(Workplace, workplace_id)
            if workplace is not None and owns:
                current.expunge(workplace)
            return workplace

    def save_workplace(self, workplace: Workplace) -> Workplace:
        with get_session() as session:
            workplace = session.merge(workplace)
            session.commit()
            session.refresh(workplace)
            return workplace
