"""Persistence ostatních osvědčení."""

from __future__ import annotations

from sqlalchemy import select

from core.database.session import get_session
from moduly.smlouvy_ozo.modely.qualification_certificate import QualificationCertificate


class QualificationCertificateRepository:
    def get_all(self, *, active_only: bool | None = None) -> list[QualificationCertificate]:
        with get_session() as session:
            stmt = select(QualificationCertificate).order_by(
                QualificationCertificate.name,
                QualificationCertificate.id,
            )
            if active_only is True:
                stmt = stmt.where(QualificationCertificate.active.is_(True))
            elif active_only is False:
                stmt = stmt.where(QualificationCertificate.active.is_(False))
            return list(session.scalars(stmt))

    def get_by_id(self, certificate_id: int) -> QualificationCertificate | None:
        with get_session() as session:
            return session.get(QualificationCertificate, certificate_id)

    def add(self, certificate: QualificationCertificate) -> QualificationCertificate:
        with get_session() as session:
            session.add(certificate)
            session.commit()
            session.refresh(certificate)
            return certificate

    def update(self, certificate: QualificationCertificate) -> QualificationCertificate:
        with get_session() as session:
            certificate = session.merge(certificate)
            session.commit()
            session.refresh(certificate)
            return certificate
