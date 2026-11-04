from sqlalchemy import select

from core.database.session import get_session
from moduly.koordinace_bozp.modely.coordination_risk_receipt import (
    CoordinationRiskReceipt,
    CoordinationRiskReceiptHistory,
)


class CoordinationRiskReceiptRepository:
    def get_for_employer(
        self,
        coordination_employer_id: int,
    ) -> CoordinationRiskReceipt | None:
        with get_session() as session:
            stmt = select(CoordinationRiskReceipt).where(
                CoordinationRiskReceipt.coordination_employer_id
                == coordination_employer_id,
            )
            return session.scalars(stmt).first()

    def get_by_id(self, receipt_id: int) -> CoordinationRiskReceipt | None:
        with get_session() as session:
            return session.get(CoordinationRiskReceipt, receipt_id)

    def add(self, receipt: CoordinationRiskReceipt) -> CoordinationRiskReceipt:
        with get_session() as session:
            session.add(receipt)
            session.commit()
            session.refresh(receipt)
            return receipt

    def update_with_history(
        self,
        receipt: CoordinationRiskReceipt,
        history: CoordinationRiskReceiptHistory,
    ) -> CoordinationRiskReceipt:
        """Zapíše opravu a nové aktuální údaje v jednom kroku."""
        with get_session() as session:
            session.add(history)
            receipt = session.merge(receipt)
            session.commit()
            session.refresh(receipt)
            return receipt

    def list_history(
        self,
        receipt_id: int,
    ) -> list[CoordinationRiskReceiptHistory]:
        with get_session() as session:
            stmt = (
                select(CoordinationRiskReceiptHistory)
                .where(CoordinationRiskReceiptHistory.receipt_id == receipt_id)
                .order_by(
                    CoordinationRiskReceiptHistory.changed_at.asc(),
                    CoordinationRiskReceiptHistory.id.asc(),
                )
            )
            return list(session.scalars(stmt).all())
