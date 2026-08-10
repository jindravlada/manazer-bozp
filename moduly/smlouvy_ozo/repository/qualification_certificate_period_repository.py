"""Persistence historických verzí ostatních osvědčení."""

from __future__ import annotations

from sqlalchemy import select

from core.database.session import get_session
from moduly.smlouvy_ozo.modely.qualification_certificate_period import (
    QualificationCertificatePeriod,
)


class QualificationCertificatePeriodRepository:
    def list_for_certificate(
        self, certificate_id: int
    ) -> list[QualificationCertificatePeriod]:
        with get_session() as session:
            stmt = (
                select(QualificationCertificatePeriod)
                .where(QualificationCertificatePeriod.certificate_id == certificate_id)
                .order_by(
                    QualificationCertificatePeriod.valid_from.desc(),
                    QualificationCertificatePeriod.id.desc(),
                )
            )
            return list(session.scalars(stmt))

    def get_by_id(self, period_id: int) -> QualificationCertificatePeriod | None:
        with get_session() as session:
            return session.get(QualificationCertificatePeriod, period_id)

    def get_open(self, certificate_id: int) -> QualificationCertificatePeriod | None:
        with get_session() as session:
            stmt = (
                select(QualificationCertificatePeriod)
                .where(
                    QualificationCertificatePeriod.certificate_id == certificate_id,
                    QualificationCertificatePeriod.valid_to_period.is_(None),
                )
                .order_by(
                    QualificationCertificatePeriod.valid_from.desc(),
                    QualificationCertificatePeriod.id.desc(),
                )
                .limit(1)
            )
            return session.scalars(stmt).first()

    def add(
        self, period: QualificationCertificatePeriod
    ) -> QualificationCertificatePeriod:
        with get_session() as session:
            session.add(period)
            session.commit()
            session.refresh(period)
            return period

    def update(
        self, period: QualificationCertificatePeriod
    ) -> QualificationCertificatePeriod:
        with get_session() as session:
            period = session.merge(period)
            session.commit()
            session.refresh(period)
            return period
