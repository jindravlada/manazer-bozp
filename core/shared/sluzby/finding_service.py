from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from core.shared.constants import (
    FINDING_STATUS_ORIGIN_MANUAL,
    FINDING_STATUS_ORIGIN_TASK,
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
    FINDING_STATUS_VYPORADANO,
    VALID_ENTITY_TYPES,
    VALID_FINDING_STATUS_ORIGINS,
    VALID_FINDING_STATUSES,
    VALID_FINDING_TYPES,
)
from core.shared.modely.finding import Finding
from core.shared.repository.finding_repository import FindingRepository
from core.shared.sluzby.finding_status_history import finding_status_history_service


class FindingService:
    def __init__(self):
        self.repository = FindingRepository()

    def get_for_entity(self, entity_type: str, entity_id: int) -> list[Finding]:
        self._validate_entity(entity_type, entity_id)
        return self.repository.get_for_entity(entity_type, entity_id)

    def get_for_entities(
        self,
        entity_type: str,
        entity_ids: list[int] | tuple[int, ...],
    ) -> list[Finding]:
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(f"Neplatný typ entity: {entity_type}")
        return self.repository.get_for_entities(entity_type, entity_ids)

    def get_by_id(self, finding_id: int, *, session: Session | None = None) -> Finding | None:
        return self.repository.get_by_id(finding_id, session=session)

    def get_by_ids(self, finding_ids: list[int] | tuple[int, ...]) -> list[Finding]:
        return self.repository.get_by_ids(finding_ids)

    def get_by_task_id(self, task_id: int, *, session: Session | None = None) -> Finding | None:
        return self.repository.get_by_task_id(task_id, session=session)

    def create(
        self,
        entity_type: str,
        entity_id: int,
        *,
        session: Session | None = None,
        **fields,
    ) -> Finding:
        self._validate_entity(entity_type, entity_id)
        display_order = fields.pop("display_order", None)
        data = self._validated_fields(fields)

        if display_order is None:
            display_order = self.repository.max_display_order(
                entity_type,
                entity_id,
                session=session,
            ) + 1

        finding = Finding(
            entity_type=entity_type,
            entity_id=entity_id,
            display_order=int(display_order),
            **data,
        )
        self._apply_status_side_effects(finding)
        return self.repository.save(finding, session=session)

    def update(
        self,
        finding_id: int,
        *,
        session: Session | None = None,
        status_origin: str | None = None,
        **fields,
    ) -> Finding | None:
        """Uloží zjištění. Změna stavu, datum vypořádání a historie jsou jedna transakce."""
        if status_origin is not None and status_origin not in VALID_FINDING_STATUS_ORIGINS:
            raise ValueError(f"Neplatný původ změny stavu: {status_origin}")

        with self.repository.session(session) as (sess, owns):
            finding = self.repository.get_by_id(finding_id, session=sess)
            if finding is None:
                return None

            if "entity_type" in fields or "entity_id" in fields:
                raise ValueError("entity_type a entity_id zjištění nelze měnit.")

            data = self._validated_fields(fields, partial=True)
            data.pop("resolved_at", None)
            status_explicit = "status" in data
            task_id_explicit = "task_id" in data
            old_status = finding.status
            old_resolved_at = finding.resolved_at

            if task_id_explicit and not status_explicit:
                if data["task_id"]:
                    if finding.status != FINDING_STATUS_VYPORADANO:
                        data["status"] = FINDING_STATUS_V_PROCESU
                elif finding.status == FINDING_STATUS_V_PROCESU:
                    data["status"] = FINDING_STATUS_OTEVRENE

            new_status = data.get("status", old_status)
            for key, value in data.items():
                if key == "status":
                    continue
                setattr(finding, key, value)

            if new_status != old_status:
                finding.status = new_status
                finding.resolved_at = resolved_at_after_status_change(
                    old_status,
                    new_status,
                    old_resolved_at,
                )
                origin = self._status_change_origin(
                    requested=status_origin,
                    status_explicit=status_explicit,
                    task_id_explicit=task_id_explicit,
                    old_status=old_status,
                    new_status=new_status,
                    task_id=data.get("task_id"),
                )
            else:
                finding.status = old_status
                finding.resolved_at = old_resolved_at
                origin = ""

            saved = self.repository.save(finding, session=sess)
            if new_status != old_status:
                finding_status_history_service.record(
                    session=sess,
                    finding_id=int(saved.id),
                    old_status=old_status,
                    new_status=new_status,
                    resolved_at_before=old_resolved_at,
                    resolved_at_after=saved.resolved_at,
                    origin=origin,
                )
            if owns:
                sess.commit()
                sess.refresh(saved)
                sess.expunge(saved)
            return saved

    def delete(self, finding_id: int, *, session: Session | None = None) -> bool:
        return self.repository.delete(finding_id, session=session)

    def delete_for_entity(self, entity_type: str, entity_id: int) -> int:
        self._validate_entity(entity_type, entity_id)
        return self.repository.delete_for_entity(entity_type, entity_id)

    def summarize(self, entity_type: str, entity_id: int) -> dict[str, int]:
        self._validate_entity(entity_type, entity_id)
        findings = self.repository.get_for_entity(entity_type, entity_id)

        summary = {
            "total": len(findings),
            FINDING_STATUS_OTEVRENE: 0,
            FINDING_STATUS_V_PROCESU: 0,
            FINDING_STATUS_VYPORADANO: 0,
        }
        for finding in findings:
            if finding.status in summary:
                summary[finding.status] += 1

        for finding_type in VALID_FINDING_TYPES:
            summary[finding_type] = sum(1 for finding in findings if finding.finding_type == finding_type)

        return summary

    def has_unresolved(self, entity_type: str, entity_id: int) -> bool:
        self._validate_entity(entity_type, entity_id)
        open_count = self.repository.count_for_entity(entity_type, entity_id)
        resolved_count = self.repository.count_for_entity(
            entity_type,
            entity_id,
            status=FINDING_STATUS_VYPORADANO,
        )
        return open_count > resolved_count

    def _validate_entity(self, entity_type: str, entity_id: int) -> None:
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(f"Neplatný entity_type: {entity_type}")
        if entity_id <= 0:
            raise ValueError("entity_id musí být kladné celé číslo.")

    def _validated_fields(self, fields: dict, *, partial: bool = False) -> dict:
        data = dict(fields)

        if "display_order" in data:
            data["display_order"] = int(data["display_order"])

        if "finding_type" in data and data["finding_type"] not in VALID_FINDING_TYPES:
            raise ValueError(f"Neplatný finding_type: {data['finding_type']}")

        if "status" in data and data["status"] not in VALID_FINDING_STATUSES:
            raise ValueError(f"Neplatný status: {data['status']}")

        if "responsible_person_id" in data and data["responsible_person_id"] is not None:
            data["responsible_person_id"] = int(data["responsible_person_id"])

        if "task_id" in data and data["task_id"] is not None:
            data["task_id"] = int(data["task_id"])

        if not partial:
            if "finding_type" not in data:
                data.pop("finding_type", None)
            if "status" not in data:
                data.pop("status", None)

        return data

    def status_history(self, finding_id: int, *, session: Session | None = None):
        return finding_status_history_service.list_for_finding(finding_id, session=session)

    def count_resolution_inconsistencies(self, *, session: Session | None = None) -> int:
        """Počet zjištění, kde stav a resolved_at spolu nesedí. Nic nezapisuje."""
        inconsistent = or_(
            and_(
                Finding.status == FINDING_STATUS_VYPORADANO,
                Finding.resolved_at.is_(None),
            ),
            and_(
                Finding.status != FINDING_STATUS_VYPORADANO,
                Finding.resolved_at.is_not(None),
            ),
        )
        with self.repository.session(session) as (sess, _owns):
            value = sess.scalar(select(func.count(Finding.id)).where(inconsistent))
            return int(value or 0)

    def _status_change_origin(
        self,
        *,
        requested: str | None,
        status_explicit: bool,
        task_id_explicit: bool,
        old_status: str,
        new_status: str,
        task_id: int | None,
    ) -> str:
        if requested:
            return requested
        if task_id_explicit and not status_explicit:
            return FINDING_STATUS_ORIGIN_TASK
        if (
            task_id_explicit
            and new_status == FINDING_STATUS_V_PROCESU
            and task_id
        ):
            return FINDING_STATUS_ORIGIN_TASK
        if (
            task_id_explicit
            and new_status == FINDING_STATUS_OTEVRENE
            and not task_id
            and old_status == FINDING_STATUS_V_PROCESU
        ):
            return FINDING_STATUS_ORIGIN_TASK
        if status_explicit:
            return FINDING_STATUS_ORIGIN_MANUAL
        return ""

    def _apply_status_side_effects(self, finding: Finding) -> None:
        if finding.status == FINDING_STATUS_VYPORADANO and finding.resolved_at is None:
            finding.resolved_at = date.today()


def resolved_at_after_status_change(
    old_status: str,
    new_status: str,
    resolved_at: date | None,
) -> date | None:
    """Aktuální datum vypořádání po skutečné změně stavu.

    Přechod do Vypořádané nastaví dnešek. Odchod z Vypořádané datum smaže.
    Přechod Otevřené ↔ V procesu existující datum nemění a nové nevytváří.
    """
    if new_status == old_status:
        return resolved_at
    if new_status == FINDING_STATUS_VYPORADANO:
        return date.today()
    if old_status == FINDING_STATUS_VYPORADANO and new_status in (
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
    ):
        return None
    return resolved_at


finding_service = FindingService()
