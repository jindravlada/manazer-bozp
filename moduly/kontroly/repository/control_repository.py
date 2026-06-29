from sqlalchemy import select

from core.database.session import get_session
from moduly.kontroly.modely.control import Control


class ControlRepository:
    def get_all(self) -> list[Control]:
        with get_session() as session:
            stmt = select(Control).order_by(
                Control.inspection_date.desc(),
                Control.id.desc(),
            )
            return list(session.scalars(stmt))

    def get_by_id(self, control_id: int) -> Control | None:
        with get_session() as session:
            return session.get(Control, control_id)

    def add(self, control: Control) -> Control:
        with get_session() as session:
            session.add(control)
            session.commit()
            session.refresh(control)
            return control

    def update(self, control: Control) -> Control:
        with get_session() as session:
            control = session.merge(control)
            session.commit()
            session.refresh(control)
            return control
