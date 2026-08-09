"""Persistence smluv OZO."""

from __future__ import annotations

from sqlalchemy import select

from core.database.session import get_session
from moduly.smlouvy_ozo.modely.ozo_contract import OzoContract


class OzoContractRepository:
    def get_all(self, *, active_only: bool | None = None) -> list[OzoContract]:
        with get_session() as session:
            stmt = select(OzoContract).order_by(
                OzoContract.employer_name,
                OzoContract.id,
            )
            if active_only is True:
                stmt = stmt.where(OzoContract.active.is_(True))
            elif active_only is False:
                stmt = stmt.where(OzoContract.active.is_(False))
            return list(session.scalars(stmt))

    def get_by_id(self, contract_id: int) -> OzoContract | None:
        with get_session() as session:
            return session.get(OzoContract, contract_id)

    def add(self, contract: OzoContract) -> OzoContract:
        with get_session() as session:
            session.add(contract)
            session.commit()
            session.refresh(contract)
            return contract

    def update(self, contract: OzoContract) -> OzoContract:
        with get_session() as session:
            contract = session.merge(contract)
            session.commit()
            session.refresh(contract)
            return contract
