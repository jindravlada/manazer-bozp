"""Repository pro evidenci vydání Pravidel bezpečné práce."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database.session import get_session
from moduly.rizeni_rizik.modely.pravidla_bezpecne_prace_edition import (
    PravidlaBezpecnePraceEdition,
)


class PravidlaBezpecnePraceEditionRepository:
    def add(self, edition: PravidlaBezpecnePraceEdition) -> PravidlaBezpecnePraceEdition:
        with get_session() as session:
            session.add(edition)
            session.commit()
            edition_id = edition.id
        loaded = self.get_by_id(edition_id)
        assert loaded is not None
        return loaded

    def get_by_id(self, edition_id: int) -> PravidlaBezpecnePraceEdition | None:
        with get_session() as session:
            stmt = (
                select(PravidlaBezpecnePraceEdition)
                .where(PravidlaBezpecnePraceEdition.id == edition_id)
                .options(selectinload(PravidlaBezpecnePraceEdition.rules))
            )
            return session.scalars(stmt).first()

    def get_latest_for_scope(
        self,
        *,
        endangered_group_id: int,
        operation_id: int,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
    ) -> PravidlaBezpecnePraceEdition | None:
        with get_session() as session:
            stmt = (
                select(PravidlaBezpecnePraceEdition)
                .where(
                    PravidlaBezpecnePraceEdition.endangered_group_id == endangered_group_id,
                    PravidlaBezpecnePraceEdition.operation_id == operation_id,
                )
                .options(selectinload(PravidlaBezpecnePraceEdition.rules))
                .order_by(
                    PravidlaBezpecnePraceEdition.issued_at.desc(),
                    PravidlaBezpecnePraceEdition.id.desc(),
                )
            )
            if workplace_id is None:
                stmt = stmt.where(PravidlaBezpecnePraceEdition.workplace_id.is_(None))
            else:
                stmt = stmt.where(PravidlaBezpecnePraceEdition.workplace_id == workplace_id)

            if workplace_part_id is None:
                stmt = stmt.where(PravidlaBezpecnePraceEdition.workplace_part_id.is_(None))
            else:
                stmt = stmt.where(
                    PravidlaBezpecnePraceEdition.workplace_part_id == workplace_part_id
                )

            return session.scalars(stmt).first()
