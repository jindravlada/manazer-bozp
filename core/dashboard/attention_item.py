"""Prezentační model položky panelu Nadcházející události a úkoly."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


ITEM_TYPE_TASK = "task"
ITEM_TYPE_AUDIT = "audit"
ITEM_TYPE_EXTERNAL_AUDIT = "external_audit"
ITEM_TYPE_EXTERNAL_AUDIT_NC = "external_audit_nonconformity"
ITEM_TYPE_EXTERNAL_AUDIT_PKZ = "external_audit_improvement"
ITEM_TYPE_INSPECTION = "inspection"
ITEM_TYPE_MEETING = "meeting"
ITEM_TYPE_PERIODIC = "periodic"
ITEM_TYPE_YEARLY_PLAN_MONTH = "yearly_plan_month"
ITEM_TYPE_OZO_CONTRACT = "ozo_contract"
ITEM_TYPE_OZO_PERSON_CERTIFICATE = "ozo_person_certificate"
ITEM_TYPE_QUALIFICATION_CERTIFICATE = "qualification_certificate"
ITEM_TYPE_STATE_SUPERVISION = "state_supervision"
ITEM_TYPE_ACCIDENT_DPN_RECORD_UPDATE = "accident_dpn_record_update"
# Zpětná kompatibilita staršího interního názvu.
ITEM_TYPE_BOZP_INSPECTION = ITEM_TYPE_INSPECTION

TYPE_LABEL_TASK_CONTROL = "Kontrola úkolu"

TYPE_LABELS = {
    ITEM_TYPE_TASK: "Úkol",
    ITEM_TYPE_AUDIT: "Audit",
    ITEM_TYPE_EXTERNAL_AUDIT: "Audit",
    ITEM_TYPE_EXTERNAL_AUDIT_NC: "Neshoda",
    ITEM_TYPE_EXTERNAL_AUDIT_PKZ: "PKZ",
    ITEM_TYPE_INSPECTION: "Prověrka",
    ITEM_TYPE_MEETING: "Událost",
    ITEM_TYPE_PERIODIC: "Periodická činnost",
    ITEM_TYPE_YEARLY_PLAN_MONTH: "Roční plán",
    ITEM_TYPE_OZO_CONTRACT: "Smlouva OZO",
    ITEM_TYPE_OZO_PERSON_CERTIFICATE: "Osvědčení OZO",
    ITEM_TYPE_QUALIFICATION_CERTIFICATE: "Osvědčení",
    ITEM_TYPE_STATE_SUPERVISION: "Státní dozor",
    ITEM_TYPE_ACCIDENT_DPN_RECORD_UPDATE: "Aktualizace záznamu",
}

SOURCE_LABEL_AUDIT = "Audit systému řízení"
SOURCE_LABEL_EXTERNAL_AUDIT = "Externí audit"
SOURCE_LABEL_INSPECTION = "Prověrka BOZP"
SOURCE_LABEL_PERIODIC = "Periodická činnost"
SOURCE_LABEL_YEARLY_PLAN = "Roční plán"
SOURCE_LABEL_OZO_CONTRACT = "Smlouvy OZO"
SOURCE_LABEL_OZO_PERSON = "Odborně způsobilá osoba"
SOURCE_LABEL_QUALIFICATION = "Ostatní osvědčení"
SOURCE_LABEL_STATE_SUPERVISION = "Státní dozor"
SOURCE_LABEL_KNIHA_URAZU = "Kniha úrazů"

PRIORITY_RANK = {
    "Kritická": 0,
    "Vysoká": 1,
    "Normální": 2,
    "Nízká": 3,
}


def meeting_dashboard_source_label(meeting) -> str:
    """Zdroj události pro Dashboard: provoz/místo, bez organizátora."""
    location = (getattr(meeting, "location", None) or "").strip()
    if location:
        return location
    return TYPE_LABELS[ITEM_TYPE_MEETING]


@dataclass(frozen=True)
class AttentionItem:
    item_type: str
    source_id: int
    title: str
    date: date | None
    subtitle: str
    status: str
    source_type: str = ""
    priority: str = ""
    event_at: datetime | None = None
    ends_at: datetime | None = None
    open_metadata: dict[str, Any] = field(default_factory=dict)
    sort_key: tuple = ()
    detail_tooltip: str = ""
    identity_key: str = ""
    type_label_override: str | None = None

    @property
    def type_label(self) -> str:
        override = (self.type_label_override or "").strip()
        if override:
            return override
        return TYPE_LABELS.get(self.item_type, self.item_type)

    @property
    def entity_id(self) -> int:
        """Zpětná kompatibilita pro starší volání."""
        return self.source_id

    @property
    def due_date(self) -> date | None:
        """Zpětná kompatibilita pro starší volání."""
        return self.date

    @property
    def source_label(self) -> str:
        """Zpětná kompatibilita pro starší volání."""
        return self.subtitle


def attention_item_is_overdue(
    item: AttentionItem,
    *,
    today: date | None = None,
) -> bool:
    """Kalendářní „Po termínu“: termín dříve než dnes; dnešek není po termínu."""
    today = today or date.today()
    if item.event_at is not None:
        due = item.event_at.date()
    else:
        due = item.due_date
    if due is None:
        return False
    return due < today


def attention_item_identity(item: AttentionItem) -> tuple:
    """Stabilní identita řádku Nadcházejících (vícedenní položka = samostatné dny)."""
    if item.identity_key:
        return ("identity_key", item.identity_key)
    visit = ""
    metadata = item.open_metadata or {}
    raw_visit = metadata.get("visit_date")
    if raw_visit:
        visit = str(raw_visit)
    return (item.item_type, int(item.source_id), visit)
