from sqlalchemy import select

from core.database.session import get_session
from core.utils.czech_sort import czech_sorted, worker_sort_key
from moduly.nastaveni.modely.employer import Employer
from moduly.nastaveni.modely.thp_worker import ThpWorker
from moduly.nastaveni.modely.workplace import Workplace


class SettingsRepository:
    def get_employer(self) -> Employer | None:
        with get_session() as session:
            stmt = select(Employer).limit(1)
            return session.scalars(stmt).first()

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

    def get_worker_by_id(self, worker_id: int) -> ThpWorker | None:
        with get_session() as session:
            return session.get(ThpWorker, worker_id)

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

        return czech_sorted(workplaces, key=lambda workplace: workplace.name)

    def get_workplace_by_id(self, workplace_id: int) -> Workplace | None:
        with get_session() as session:
            return session.get(Workplace, workplace_id)

    def save_workplace(self, workplace: Workplace) -> Workplace:
        with get_session() as session:
            workplace = session.merge(workplace)
            session.commit()
            session.refresh(workplace)
            return workplace
