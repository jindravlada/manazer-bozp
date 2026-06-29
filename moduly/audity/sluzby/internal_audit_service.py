from datetime import date, datetime

from core.shared.constants import ENTITY_AUDITY
from core.shared.sluzby.finding_service import finding_service
from moduly.audity.constants import DEFAULT_AUDIT_STATUS, VALID_AUDIT_STATUSES
from moduly.audity.modely.internal_audit import InternalAudit
from moduly.audity.repository.internal_audit_repository import InternalAuditRepository
from moduly.nastaveni.sluzby.settings_service import settings_service


class InternalAuditService:
    def __init__(self):
        self.repository = InternalAuditRepository()

    def get_all(self) -> list[InternalAudit]:
        return self.repository.get_all()

    def get_by_id(self, audit_id: int) -> InternalAudit | None:
        return self.repository.get_by_id(audit_id)

    def create_audit(
        self,
        title: str = "",
        audit_date: date | None = None,
        workplace: str = "",
        status: str = DEFAULT_AUDIT_STATUS,
    ) -> InternalAudit:
        if status not in VALID_AUDIT_STATUSES:
            raise ValueError(f"Neplatný stav auditu: {status}")

        if audit_date is None:
            audit_date = date.today()

        audit = InternalAudit(
            title=title.strip(),
            audit_date=audit_date,
            workplace=workplace.strip(),
            status=status,
        )
        saved = self.repository.add(audit)
        saved.number = self._make_number(saved.id, saved.audit_date.year)
        return self.repository.update(saved)

    def update_audit(
        self,
        audit_id: int,
        title: str = "",
        audit_date: date | None = None,
        workplace: str = "",
        status: str = DEFAULT_AUDIT_STATUS,
    ) -> InternalAudit | None:
        audit = self.repository.get_by_id(audit_id)
        if audit is None:
            return None

        if status not in VALID_AUDIT_STATUSES:
            raise ValueError(f"Neplatný stav auditu: {status}")

        audit.title = title.strip()
        audit.audit_date = audit_date
        audit.workplace = workplace.strip()
        audit.status = status
        audit.updated_at = datetime.now()

        return self.repository.update(audit)

    def delete_audit(self, audit_id: int) -> bool:
        finding_service.delete_for_entity(ENTITY_AUDITY, audit_id)
        return self.repository.delete(audit_id)

    def resolve_workplace_name(self, workplace_id: int | None) -> str:
        if not workplace_id:
            return ""

        workplace = settings_service.get_workplace_by_id(workplace_id)
        return workplace.name if workplace else ""

    def _make_number(self, audit_id: int, year: int) -> str:
        return f"{audit_id}/{year}"


internal_audit_service = InternalAuditService()
