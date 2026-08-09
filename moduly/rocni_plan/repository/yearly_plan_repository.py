"""Persistence Ročního plánu."""

from __future__ import annotations

from sqlalchemy import or_, select

from core.database.session import get_session
from moduly.rocni_plan.constants import DEFAULT_REPEAT_EVERY, REPEAT_UNIT_NONE
from moduly.rocni_plan.modely.yearly_plan_item import YearlyPlanItem
from moduly.rocni_plan.modely.yearly_plan_item_move import YearlyPlanItemMove
from moduly.rocni_plan.modely.yearly_plan_month_status import YearlyPlanMonthStatus
from moduly.rocni_plan.modely.yearly_plan_occurrence import YearlyPlanOccurrence


class YearlyPlanItemRepository:
    def get_by_id(self, item_id: int) -> YearlyPlanItem | None:
        with get_session() as session:
            return session.get(YearlyPlanItem, item_id)

    def list_for_month(self, year: int, month: int) -> list[YearlyPlanItem]:
        with get_session() as session:
            stmt = (
                select(YearlyPlanItem)
                .where(
                    YearlyPlanItem.year == year,
                    YearlyPlanItem.month == month,
                )
                .order_by(YearlyPlanItem.id)
            )
            return list(session.scalars(stmt))

    def list_oneshots_for_month(self, year: int, month: int) -> list[YearlyPlanItem]:
        with get_session() as session:
            stmt = (
                select(YearlyPlanItem)
                .where(
                    YearlyPlanItem.year == year,
                    YearlyPlanItem.month == month,
                    or_(
                        YearlyPlanItem.repeat_every <= 0,
                        YearlyPlanItem.repeat_unit == REPEAT_UNIT_NONE,
                    ),
                )
                .order_by(YearlyPlanItem.id)
            )
            return list(session.scalars(stmt))

    def list_repeating(self) -> list[YearlyPlanItem]:
        with get_session() as session:
            stmt = (
                select(YearlyPlanItem)
                .where(
                    YearlyPlanItem.repeat_every > DEFAULT_REPEAT_EVERY,
                    YearlyPlanItem.repeat_unit != REPEAT_UNIT_NONE,
                )
                .order_by(YearlyPlanItem.id)
            )
            return list(session.scalars(stmt))

    def list_for_year(self, year: int) -> list[YearlyPlanItem]:
        with get_session() as session:
            stmt = (
                select(YearlyPlanItem)
                .where(YearlyPlanItem.year == year)
                .order_by(YearlyPlanItem.month, YearlyPlanItem.id)
            )
            return list(session.scalars(stmt))

    def add(self, item: YearlyPlanItem) -> YearlyPlanItem:
        with get_session() as session:
            session.add(item)
            session.commit()
            session.refresh(item)
            return item

    def update(self, item: YearlyPlanItem) -> YearlyPlanItem:
        with get_session() as session:
            item = session.merge(item)
            session.commit()
            session.refresh(item)
            return item


class YearlyPlanItemMoveRepository:
    def list_for_item(self, item_id: int) -> list[YearlyPlanItemMove]:
        with get_session() as session:
            stmt = (
                select(YearlyPlanItemMove)
                .where(YearlyPlanItemMove.item_id == item_id)
                .order_by(YearlyPlanItemMove.moved_at.asc(), YearlyPlanItemMove.id.asc())
            )
            return list(session.scalars(stmt))

    def add(self, move: YearlyPlanItemMove) -> YearlyPlanItemMove:
        with get_session() as session:
            session.add(move)
            session.commit()
            session.refresh(move)
            return move


class YearlyPlanMonthStatusRepository:
    def get_for_month(self, year: int, month: int) -> YearlyPlanMonthStatus | None:
        with get_session() as session:
            stmt = select(YearlyPlanMonthStatus).where(
                YearlyPlanMonthStatus.year == year,
                YearlyPlanMonthStatus.month == month,
            )
            return session.scalars(stmt).first()

    def add(self, status: YearlyPlanMonthStatus) -> YearlyPlanMonthStatus:
        with get_session() as session:
            session.add(status)
            session.commit()
            session.refresh(status)
            return status

    def delete_for_month(self, year: int, month: int) -> None:
        with get_session() as session:
            row = session.scalars(
                select(YearlyPlanMonthStatus).where(
                    YearlyPlanMonthStatus.year == year,
                    YearlyPlanMonthStatus.month == month,
                )
            ).first()
            if row is not None:
                session.delete(row)
                session.commit()


class YearlyPlanOccurrenceRepository:
    def get_slot(
        self,
        definition_id: int,
        year: int,
        month: int,
    ) -> YearlyPlanOccurrence | None:
        with get_session() as session:
            stmt = select(YearlyPlanOccurrence).where(
                YearlyPlanOccurrence.definition_id == definition_id,
                YearlyPlanOccurrence.year == year,
                YearlyPlanOccurrence.month == month,
            )
            return session.scalars(stmt).first()

    def list_for_definition(self, definition_id: int) -> list[YearlyPlanOccurrence]:
        with get_session() as session:
            stmt = (
                select(YearlyPlanOccurrence)
                .where(YearlyPlanOccurrence.definition_id == definition_id)
                .order_by(
                    YearlyPlanOccurrence.year,
                    YearlyPlanOccurrence.month,
                    YearlyPlanOccurrence.id,
                )
            )
            return list(session.scalars(stmt))

    def list_displayed_in_month(
        self,
        year: int,
        month: int,
    ) -> list[YearlyPlanOccurrence]:
        with get_session() as session:
            stmt = (
                select(YearlyPlanOccurrence)
                .where(
                    YearlyPlanOccurrence.display_year == year,
                    YearlyPlanOccurrence.display_month == month,
                )
                .order_by(YearlyPlanOccurrence.id)
            )
            return list(session.scalars(stmt))

    def add(self, occurrence: YearlyPlanOccurrence) -> YearlyPlanOccurrence:
        with get_session() as session:
            session.add(occurrence)
            session.commit()
            session.refresh(occurrence)
            return occurrence

    def update(self, occurrence: YearlyPlanOccurrence) -> YearlyPlanOccurrence:
        with get_session() as session:
            occurrence = session.merge(occurrence)
            session.commit()
            session.refresh(occurrence)
            return occurrence
