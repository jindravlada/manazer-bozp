"""Persistence Ročního plánu."""

from __future__ import annotations

from sqlalchemy import select

from core.database.session import get_session
from moduly.rocni_plan.modely.yearly_plan_item import YearlyPlanItem
from moduly.rocni_plan.modely.yearly_plan_item_move import YearlyPlanItemMove


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
