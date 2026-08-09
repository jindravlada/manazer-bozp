"""Persistence Periodických činností."""

from __future__ import annotations

from sqlalchemy import select

from core.database.session import get_session
from moduly.periodicke_cinnosti.modely.periodic_activity import PeriodicActivity
from moduly.periodicke_cinnosti.modely.periodic_activity_occurrence import (
    PeriodicActivityOccurrence,
)


class PeriodicActivityRepository:
    def get_all(self, *, active_only: bool | None = None) -> list[PeriodicActivity]:
        with get_session() as session:
            stmt = select(PeriodicActivity).order_by(
                PeriodicActivity.next_due_date,
                PeriodicActivity.id,
            )
            if active_only is True:
                stmt = stmt.where(PeriodicActivity.active.is_(True))
            elif active_only is False:
                stmt = stmt.where(PeriodicActivity.active.is_(False))
            return list(session.scalars(stmt))

    def get_by_id(self, activity_id: int) -> PeriodicActivity | None:
        with get_session() as session:
            return session.get(PeriodicActivity, activity_id)

    def add(self, activity: PeriodicActivity) -> PeriodicActivity:
        with get_session() as session:
            session.add(activity)
            session.commit()
            session.refresh(activity)
            return activity

    def update(self, activity: PeriodicActivity) -> PeriodicActivity:
        with get_session() as session:
            activity = session.merge(activity)
            session.commit()
            session.refresh(activity)
            return activity


class PeriodicActivityOccurrenceRepository:
    def list_for_activity(self, activity_id: int) -> list[PeriodicActivityOccurrence]:
        with get_session() as session:
            stmt = (
                select(PeriodicActivityOccurrence)
                .where(PeriodicActivityOccurrence.activity_id == activity_id)
                .order_by(
                    PeriodicActivityOccurrence.performed_at.desc(),
                    PeriodicActivityOccurrence.id.desc(),
                )
            )
            return list(session.scalars(stmt))

    def get_by_id(self, occurrence_id: int) -> PeriodicActivityOccurrence | None:
        with get_session() as session:
            return session.get(PeriodicActivityOccurrence, occurrence_id)

    def add(self, occurrence: PeriodicActivityOccurrence) -> PeriodicActivityOccurrence:
        with get_session() as session:
            session.add(occurrence)
            session.commit()
            session.refresh(occurrence)
            return occurrence
