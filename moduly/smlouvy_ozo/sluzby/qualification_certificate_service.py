"""Služba evidence ostatních osvědčení / odborných způsobilostí."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from moduly.smlouvy_ozo.constants import NOTIFY_UNITS, UNIT_DAYS
from moduly.smlouvy_ozo.modely.qualification_certificate import QualificationCertificate
from moduly.smlouvy_ozo.modely.qualification_certificate_period import (
    QualificationCertificatePeriod,
)
from moduly.smlouvy_ozo.repository.qualification_certificate_period_repository import (
    QualificationCertificatePeriodRepository,
)
from moduly.smlouvy_ozo.repository.qualification_certificate_repository import (
    QualificationCertificateRepository,
)


class QualificationCertificateValidationError(Exception):
    pass


class QualificationCertificateService:
    def __init__(
        self,
        repository: QualificationCertificateRepository | None = None,
        period_repository: QualificationCertificatePeriodRepository | None = None,
    ):
        self.repository = repository or QualificationCertificateRepository()
        self.period_repository = (
            period_repository or QualificationCertificatePeriodRepository()
        )

    def get_all(self, *, active_only: bool | None = True) -> list[QualificationCertificate]:
        return self.repository.get_all(active_only=active_only)

    def get_by_id(self, certificate_id: int) -> QualificationCertificate | None:
        return self.repository.get_by_id(certificate_id)

    def get_open_period(
        self, certificate: QualificationCertificate | int | None
    ) -> QualificationCertificatePeriod | None:
        certificate_id = self._certificate_id(certificate)
        if certificate_id is None:
            return None
        return self.period_repository.get_open(certificate_id)

    def list_periods(
        self, certificate: QualificationCertificate | int
    ) -> list[QualificationCertificatePeriod]:
        certificate_id = self._certificate_id(certificate)
        if certificate_id is None:
            return []
        return self.period_repository.list_for_certificate(certificate_id)

    def list_closed_periods(
        self, certificate: QualificationCertificate | int
    ) -> list[QualificationCertificatePeriod]:
        return [p for p in self.list_periods(certificate) if p.valid_to_period is not None]

    def get_period(self, period_id: int) -> QualificationCertificatePeriod | None:
        return self.period_repository.get_by_id(period_id)

    def save(
        self,
        *,
        certificate_id: int | None = None,
        name: str = "",
        certificate_number: str = "",
        exam_date: date | None = None,
        indefinite: bool = False,
        certificate_valid_to: date | None = None,
        notify_before_value: int = 0,
        notify_before_unit: str = UNIT_DAYS,
        note: str = "",
        active: bool = True,
    ) -> QualificationCertificate:
        name = (name or "").strip()
        if not name:
            raise QualificationCertificateValidationError(
                "Vyplňte název odborné způsobilosti / osvědčení."
            )

        indefinite = bool(indefinite)
        if indefinite:
            certificate_valid_to = None
            notify_before_value = 0
            notify_before_unit = UNIT_DAYS
        elif certificate_valid_to is None:
            raise QualificationCertificateValidationError(
                "U osvědčení na dobu určitou vyplňte platnost do."
            )

        notify_value = int(notify_before_value or 0)
        if notify_value < 0:
            raise QualificationCertificateValidationError(
                "Předstih upozornění nesmí být záporný."
            )
        unit = (notify_before_unit or UNIT_DAYS).strip()
        if unit not in NOTIFY_UNITS:
            raise QualificationCertificateValidationError(
                f"Jednotka předstihu musí být jedna z: {', '.join(NOTIFY_UNITS)}."
            )

        fields = {
            "certificate_number": (certificate_number or "").strip(),
            "exam_date": exam_date,
            "indefinite": indefinite,
            "certificate_valid_to": certificate_valid_to,
            "notify_before_value": notify_value,
            "notify_before_unit": unit,
            "note": (note or "").strip(),
        }

        if certificate_id is None:
            certificate = QualificationCertificate(name=name, active=bool(active))
            certificate = self.repository.add(certificate)
            self._create_period(certificate.id, fields, valid_from=None)
            return certificate

        certificate = self.repository.get_by_id(certificate_id)
        if certificate is None:
            raise QualificationCertificateValidationError(
                "Osvědčení nebylo nalezeno."
            )
        certificate.name = name
        certificate.active = bool(active)
        certificate.updated_at = datetime.now()
        certificate = self.repository.update(certificate)

        open_period = self.period_repository.get_open(certificate.id)
        if open_period is None:
            self._create_period(certificate.id, fields, valid_from=None)
        else:
            if open_period.valid_to_period is not None:
                raise QualificationCertificateValidationError(
                    "Uzavřenou historickou verzi osvědčení nelze upravovat."
                )
            self._apply_fields_to_period(open_period, fields)
            self.period_repository.update(open_period)

        certificate.updated_at = datetime.now()
        return self.repository.update(certificate)

    def renew(
        self,
        certificate_id: int,
        *,
        name: str = "",
        certificate_number: str = "",
        exam_date: date | None = None,
        indefinite: bool = False,
        certificate_valid_to: date | None = None,
        notify_before_value: int = 0,
        notify_before_unit: str = UNIT_DAYS,
        note: str = "",
    ) -> QualificationCertificate:
        """Nová zkouška stejné odborné způsobilosti → nová historická verze."""
        certificate = self.repository.get_by_id(certificate_id)
        if certificate is None:
            raise QualificationCertificateValidationError(
                "Osvědčení nebylo nalezeno."
            )
        if exam_date is None:
            raise QualificationCertificateValidationError(
                "Pro obnovení osvědčení vyplňte datum nové zkoušky."
            )

        name = (name or "").strip() or (certificate.name or "").strip()
        if not name:
            raise QualificationCertificateValidationError(
                "Vyplňte název odborné způsobilosti / osvědčení."
            )

        indefinite = bool(indefinite)
        if indefinite:
            certificate_valid_to = None
            notify_before_value = 0
            notify_before_unit = UNIT_DAYS
        elif certificate_valid_to is None:
            raise QualificationCertificateValidationError(
                "U osvědčení na dobu určitou vyplňte platnost do."
            )

        notify_value = int(notify_before_value or 0)
        if notify_value < 0:
            raise QualificationCertificateValidationError(
                "Předstih upozornění nesmí být záporný."
            )
        unit = (notify_before_unit or UNIT_DAYS).strip()
        if unit not in NOTIFY_UNITS:
            raise QualificationCertificateValidationError(
                f"Jednotka předstihu musí být jedna z: {', '.join(NOTIFY_UNITS)}."
            )

        fields = {
            "certificate_number": (certificate_number or "").strip(),
            "exam_date": exam_date,
            "indefinite": indefinite,
            "certificate_valid_to": certificate_valid_to,
            "notify_before_value": notify_value,
            "notify_before_unit": unit,
            "note": (note or "").strip(),
        }

        open_period = self.period_repository.get_open(certificate.id)
        if open_period is None:
            raise QualificationCertificateValidationError(
                "Nelze obnovit osvědčení bez aktuální verze."
            )
        if exam_date <= open_period.valid_from:
            raise QualificationCertificateValidationError(
                "Datum nové zkoušky musí být později než začátek "
                "platnosti současné verze osvědčení."
            )

        open_period.valid_to_period = exam_date - timedelta(days=1)
        self.period_repository.update(open_period)
        self._create_period(certificate.id, fields, valid_from=exam_date)

        certificate.name = name
        certificate.updated_at = datetime.now()
        return self.repository.update(certificate)

    def deactivate(self, certificate_id: int) -> QualificationCertificate:
        certificate = self.repository.get_by_id(certificate_id)
        if certificate is None:
            raise QualificationCertificateValidationError("Osvědčení nebylo nalezeno.")
        certificate.active = False
        certificate.updated_at = datetime.now()
        return self.repository.update(certificate)

    def activate(self, certificate_id: int) -> QualificationCertificate:
        certificate = self.repository.get_by_id(certificate_id)
        if certificate is None:
            raise QualificationCertificateValidationError("Osvědčení nebylo nalezeno.")
        certificate.active = True
        certificate.updated_at = datetime.now()
        return self.repository.update(certificate)

    def _certificate_id(
        self, certificate: QualificationCertificate | int | None
    ) -> int | None:
        if certificate is None:
            return None
        if isinstance(certificate, int):
            return certificate
        return certificate.id

    def _create_period(
        self,
        certificate_id: int,
        fields: dict,
        *,
        valid_from: date | None,
    ) -> QualificationCertificatePeriod:
        start = valid_from or fields.get("exam_date") or date.today()
        period = QualificationCertificatePeriod(
            certificate_id=certificate_id,
            valid_from=start,
            valid_to_period=None,
        )
        self._apply_fields_to_period(period, fields)
        return self.period_repository.add(period)

    @staticmethod
    def _apply_fields_to_period(
        period: QualificationCertificatePeriod, fields: dict
    ) -> None:
        period.certificate_number = fields["certificate_number"]
        period.exam_date = fields["exam_date"]
        period.indefinite = fields["indefinite"]
        period.certificate_valid_to = fields["certificate_valid_to"]
        period.notify_before_value = fields["notify_before_value"]
        period.notify_before_unit = fields["notify_before_unit"]
        period.note = fields["note"]


qualification_certificate_service = QualificationCertificateService()
