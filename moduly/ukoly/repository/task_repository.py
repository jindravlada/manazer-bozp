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
