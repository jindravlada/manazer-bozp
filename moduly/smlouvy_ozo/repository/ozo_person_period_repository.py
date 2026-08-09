"""Persistence historických verzí OZO."""

from __future__ import annotations

from sqlalchemy import select

from core.database.session import get_session
from moduly.smlouvy_ozo.modely.ozo_person_period import OzoPersonPeriod


class OzoPersonPeriodRepository:
    def list_for_person(self, ozo_person_id: int) -> list[OzoPersonPeriod]:
        with get_session() as session:
            stmt = (
                select(OzoPersonPeriod)
                .where(OzoPersonPeriod.ozo_person_id == ozo_person_id)
                .order_by(OzoPersonPeriod.valid_from.desc(), OzoPersonPeriod.id.desc())
            )
            return list(session.scalars(stmt))

    def get_by_id(self, period_id: int) -> OzoPersonPeriod | None:
        with get_session() as session:
            return session.get(OzoPersonPeriod, period_id)

    def get_open(self, ozo_person_id: int) -> OzoPersonPeriod | None:
        with get_session() as session:
            stmt = (
                select(OzoPersonPeriod)
                .where(
                    OzoPersonPeriod.ozo_person_id == ozo_person_id,
                    OzoPersonPeriod.valid_to.is_(None),
                )
                .order_by(OzoPersonPeriod.valid_from.desc(), OzoPersonPeriod.id.desc())
                .limit(1)
            )
            return session.scalars(stmt).first()

    def add(self, period: OzoPersonPeriod) -> OzoPersonPeriod:
        with get_session() as session:
            session.add(period)
            session.commit()
            session.refresh(period)
            return period

    def update(self, period: OzoPersonPeriod) -> OzoPersonPeriod:
        with get_session() as session:
            period = session.merge(period)
            session.commit()
            session.refresh(period)
            return period

    def count_for_person(self, ozo_person_id: int) -> int:
        return len(self.list_for_person(ozo_person_id))
