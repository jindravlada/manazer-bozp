from datetime import date

from core.shared.constants import (
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
    FINDING_STATUS_VYPORADANO,
    VALID_ENTITY_TYPES,
    VALID_FINDING_STATUSES,
    VALID_FINDING_TYPES,
)
from core.shared.modely.finding import Finding
from core.shared.repository.finding_repository import FindingRepository


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

    def get_by_id(self, finding_id: int) -> Finding | None:
        return self.repository.get_by_id(finding_id)

    def get_by_task_id(self, task_id: int) -> Finding | None:
        return self.repository.get_by_task_id(task_id)

    def create(self, entity_type: str, entity_id: int, **fields) -> Finding:
        self._validate_entity(entity_type, entity_id)
        display_order = fields.pop("display_order", None)
        data = self._validated_fields(fields)

        if display_order is None:
            display_order = self.repository.max_display_order(entity_type, entity_id) + 1

        finding = Finding(
            entity_type=entity_type,
            entity_id=entity_id,
            display_order=int(display_order),
            **data,
        )
        self._apply_status_side_effects(finding)
        return self.repository.save(finding)

    def update(self, finding_id: int, **fields) -> Finding | None:
        finding = self.repository.get_by_id(finding_id)
        if finding is None:
            return None

        if "entity_type" in fields or "entity_id" in fields:
            raise ValueError("entity_type a entity_id zjištění nelze měnit.")

        data = self._validated_fields(fields, partial=True)

        if "task_id" in data and "status" not in data:
            if data["task_id"]:
                if finding.status != FINDING_STATUS_VYPORADANO:
                    data["status"] = FINDING_STATUS_V_PROCESU
            elif finding.status == FINDING_STATUS_V_PROCESU:
                data["status"] = FINDING_STATUS_OTEVRENE

        for key, value in data.items():
            setattr(finding, key, value)

        if "resolved_at" in fields:
            finding.resolved_at = fields["resolved_at"]

        self._apply_status_side_effects(finding)
        return self.repository.save(finding)

    def delete(self, finding_id: int) -> bool:
        return self.repository.delete(finding_id)

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

    def _apply_status_side_effects(self, finding: Finding) -> None:
        if finding.status == FINDING_STATUS_VYPORADANO and finding.resolved_at is None:
            finding.resolved_at = date.today()


finding_service = FindingService()
