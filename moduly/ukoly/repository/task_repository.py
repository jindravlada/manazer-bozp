from sqlalchemy import select

from core.database.session import get_session
from moduly.ukoly.modely.task import Task


class TaskRepository:
    def get_all(self) -> list[Task]:
        with get_session() as session:
            stmt = select(Task).order_by(Task.completed, Task.due_date, Task.id)
            return list(session.scalars(stmt))

    def get_by_id(self, task_id: int) -> Task | None:
        with get_session() as session:
            return session.get(Task, task_id)

    def find_open_by_source(
        self,
        *,
        source_module: str,
        source_record_id: int,
        task_type: str | None = None,
        title: str | None = None,
    ) -> Task | None:
        with get_session() as session:
            stmt = (
                select(Task)
                .where(
                    Task.source_module == source_module,
                    Task.source_record_id == source_record_id,
                    Task.canceled.is_(False),
                    Task.completed.is_(False),
                )
                .order_by(Task.id.desc())
            )
            if task_type:
                stmt = stmt.where(Task.task_type == task_type)
            if title is not None:
                stmt = stmt.where(Task.title == title)
            return session.scalars(stmt).first()

    def add(self, task: Task) -> Task:
        with get_session() as session:
            session.add(task)
            session.commit()
            session.refresh(task)
            return task

    def update(self, task: Task) -> Task:
        with get_session() as session:
            task = session.merge(task)
            session.commit()
            session.refresh(task)
            return task
