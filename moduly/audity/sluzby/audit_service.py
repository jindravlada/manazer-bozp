from datetime import date, datetime

from core.shared.constants import ENTITY_AUDITY
from core.shared.sluzby.finding_service import finding_service
from moduly.audity.constants import (
    AUDIT_SPIS_STATUSES,
    AUDIT_STATUS_DOKONCENO,
    AUDIT_STATUS_PLANOVANO,
    AUDIT_STATUS_PROBIHA,
    AUDIT_TYPES,
    DEFAULT_AUDIT_TYPE,
)
from moduly.audity.modely.audit import Audit
from moduly.audity.repository.audit_repository import AuditRepository
from moduly.audity.sluzby.audit_commission_service import audit_commission_service


class AuditService:
    def __init__(self):
        self.repository = AuditRepository()

    def get_all(self) -> list[Audit]:
        return self.repository.get_all()

    def get_by_id(self, audit_id: int) -> Audit | None:
        return self.repository.get_by_id(audit_id)

    def create_audit(self, **fields) -> Audit:
        data = self._validated_fields(fields)
        audit = Audit(**data)
        saved = self.repository.add(audit)
        saved.number = self._make_number(saved.id, saved.year)
        return self.repository.update(saved)

    def update_audit(self, audit_id: int, **fields) -> Audit | None:
        audit = self.repository.get_by_id(audit_id)
        if audit is None:
            return None

        merged = {
            "year": audit.year,
            "planned_month": audit.planned_month,
            "audit_date": audit.audit_date,
            "started_at": audit.started_at,
            "finished_at": audit.finished_at,
            "audit_type": audit.audit_type,
            "workplace_id": audit.workplace_id,
            "workplace_name": audit.workplace_name,
            "title": audit.title,
        }
        merged.update(fields)
        data = self._validated_fields(merged)
        for key, value in data.items():
            setattr(audit, key, value)
        audit.updated_at = datetime.now()
        return self.repository.update(audit)

    def delete_audit(self, audit_id: int) -> bool:
        finding_service.delete_for_entity(ENTITY_AUDITY, audit_id)
        audit_commission_service.delete_for_audit(audit_id)
        return self.repository.delete(audit_id)

    @staticmethod
    def derive_status(
        started_at: date | None,
        finished_at: date | None,
    ) -> str:
        if finished_at is not None:
            return AUDIT_STATUS_DOKONCENO
        if started_at is not None:
            return AUDIT_STATUS_PROBIHA
        return AUDIT_STATUS_PLANOVANO

    def _validated_fields(self, fields: dict) -> dict:
        data = dict(fields)

        audit_type = data.get("audit_type", DEFAULT_AUDIT_TYPE)
        if audit_type not in AUDIT_TYPES:
            raise ValueError(f"Neplatný typ auditu: {audit_type}")

        if data.get("year") is None:
            data["year"] = date.today().year

        workplace_id = data.get("workplace_id")
        if workplace_id is not None:
            data["workplace_id"] = int(workplace_id)
        else:
            data["workplace_id"] = None

        data["workplace_name"] = str(data.get("workplace_name") or "").strip()
        data["title"] = str(data.get("title") or "").strip()

        started_at = data.get("started_at")
        finished_at = data.get("finished_at")
        status = self.derive_status(started_at, finished_at)
        if status not in AUDIT_SPIS_STATUSES:
            raise ValueError(f"Neplatný stav auditu: {status}")

        return {
            "year": data.get("year"),
            "planned_month": data.get("planned_month"),
            "audit_date": data.get("audit_date"),
            "started_at": started_at,
            "finished_at": finished_at,
            "status": status,
            "audit_type": audit_type,
            "workplace_id": data.get("workplace_id"),
            "workplace_name": data["workplace_name"],
            "title": data["title"],
        }

    @staticmethod
    def _make_number(audit_id: int, year: int | None) -> str:
        number_year = year or date.today().year
        return f"{audit_id}/{number_year}"


audit_service = AuditService()
