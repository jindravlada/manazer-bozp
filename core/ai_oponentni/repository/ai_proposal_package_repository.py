import json

from sqlalchemy import delete, select

from core.ai_oponentni.modely.ai_proposal_package import (
    AiProposalPackageRecord,
    PACKAGE_STATUS_PENDING,
)
from core.ai_oponentni.proposal_package_types import AiProposalPackage
from core.database.session import get_session


class AiProposalPackageRepository:
    def get_for_review(self, ai_peer_review_id: int) -> list[AiProposalPackageRecord]:
        with get_session() as session:
            stmt = (
                select(AiProposalPackageRecord)
                .where(AiProposalPackageRecord.ai_peer_review_id == ai_peer_review_id)
                .order_by(AiProposalPackageRecord.id)
            )
            return list(session.scalars(stmt))

    def get_by_id(self, package_record_id: int) -> AiProposalPackageRecord | None:
        with get_session() as session:
            return session.get(AiProposalPackageRecord, package_record_id)

    def delete_for_review(self, ai_peer_review_id: int) -> None:
        with get_session() as session:
            session.execute(
                delete(AiProposalPackageRecord).where(
                    AiProposalPackageRecord.ai_peer_review_id == ai_peer_review_id,
                ),
            )
            session.commit()

    def add_many(
        self,
        records: list[AiProposalPackageRecord],
    ) -> list[AiProposalPackageRecord]:
        if not records:
            return []
        with get_session() as session:
            session.add_all(records)
            session.commit()
            for record in records:
                session.refresh(record)
            return records

    def update(self, record: AiProposalPackageRecord) -> AiProposalPackageRecord:
        with get_session() as session:
            record = session.merge(record)
            session.commit()
            session.refresh(record)
            return record

    @staticmethod
    def package_from_record(record: AiProposalPackageRecord) -> AiProposalPackage:
        try:
            payload = json.loads(record.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return AiProposalPackage.from_storage_dict(payload)

    @staticmethod
    def record_from_package(
        *,
        review_id: int,
        source_type: str,
        source_id: int,
        package: AiProposalPackage,
        status: str,
    ) -> AiProposalPackageRecord:
        return AiProposalPackageRecord(
            ai_peer_review_id=review_id,
            source_type=source_type,
            source_id=source_id,
            package_id=package.package_id,
            package_type=package.package_type,
            target_event_export_id=package.target_event_export_id or "",
            payload_json=json.dumps(package.to_storage_dict(), ensure_ascii=False),
            status=status,
        )

    def get_pending_for_review(self, ai_peer_review_id: int) -> list[AiProposalPackageRecord]:
        with get_session() as session:
            stmt = (
                select(AiProposalPackageRecord)
                .where(
                    AiProposalPackageRecord.ai_peer_review_id == ai_peer_review_id,
                    AiProposalPackageRecord.status == PACKAGE_STATUS_PENDING,
                )
                .order_by(AiProposalPackageRecord.id)
            )
            return list(session.scalars(stmt))
