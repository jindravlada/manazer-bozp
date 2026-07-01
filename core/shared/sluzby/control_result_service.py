from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.shared.constants import (
    CONTROL_RESULT_NEKONTROLOVANO,
    CONTROL_RESULT_PARENT_ENTITY_TYPES,
    VALID_CONTROL_RESULTS,
)
from core.shared.modely.control_result import ControlResult
from core.shared.repository.control_result_repository import ControlResultRepository
from core.services.control_result_photo_service import control_result_photo_service


@dataclass(frozen=True)
class ControlPointContext:
    area_id: str
    area_label: str
    section_id: str
    section_label: str
    control_point_id: str
    control_point_label: str


class ControlResultService:
    def __init__(self):
        self.repository = ControlResultRepository()

    def get_for_entity(self, entity_type: str, entity_id: int) -> list[ControlResult]:
        self._validate_entity(entity_type, entity_id)
        return self.repository.get_for_entity(entity_type, entity_id)

    def get_for_control_point(
        self,
        entity_type: str,
        entity_id: int,
        context: ControlPointContext,
    ) -> ControlResult | None:
        self._validate_entity(entity_type, entity_id)
        if not context.control_point_id:
            return None

        return self.repository.get_for_control_point(
            entity_type,
            entity_id,
            area_label=context.area_label,
            section_label=context.section_label,
            control_point_id=context.control_point_id,
        )

    def current_result(
        self,
        entity_type: str,
        entity_id: int,
        context: ControlPointContext,
    ) -> str:
        row = self.get_for_control_point(entity_type, entity_id, context)
        if row is None:
            return CONTROL_RESULT_NEKONTROLOVANO
        return row.result

    def set_result(
        self,
        entity_type: str,
        entity_id: int,
        context: ControlPointContext,
        *,
        result: str,
        note: str = "",
        recorded_by_name: str = "",
        shared_experience: bool | None = None,
        photo_path: str | None = None,
    ) -> ControlResult:
        self._validate_entity(entity_type, entity_id)
        if result not in VALID_CONTROL_RESULTS:
            raise ValueError(f"Neplatný výsledek kontroly: {result}")

        existing = self.get_for_control_point(entity_type, entity_id, context)
        now = datetime.now()

        if existing is None:
            control_result = ControlResult(
                entity_type=entity_type,
                entity_id=entity_id,
                source_area_id=context.area_id.strip(),
                source_area_label=context.area_label.strip(),
                source_section_id=context.section_id.strip(),
                source_section_label=context.section_label.strip(),
                source_control_point_id=context.control_point_id.strip(),
                source_control_point_label=context.control_point_label.strip(),
                result=result,
                note=note.strip(),
                shared_experience=bool(shared_experience) if shared_experience is not None else False,
                photo_path=photo_path or "",
                recorded_by_name=recorded_by_name.strip(),
                recorded_at=now,
            )
        else:
            control_result = existing
            control_result.result = result
            control_result.note = note.strip()
            if shared_experience is not None:
                control_result.shared_experience = shared_experience
            if photo_path is not None:
                control_result.photo_path = photo_path.strip()
            control_result.recorded_by_name = recorded_by_name.strip() or control_result.recorded_by_name
            control_result.recorded_at = now

        return self.repository.save(control_result)

    def attach_photo(
        self,
        entity_type: str,
        entity_id: int,
        context: ControlPointContext,
        source_path: Path,
    ) -> ControlResult:
        self._validate_entity(entity_type, entity_id)

        existing = self.get_for_control_point(entity_type, entity_id, context)
        if existing is not None and existing.photo_path:
            control_result_photo_service.delete_photo(existing.photo_path)

        relative_path = control_result_photo_service.save_optimized(
            source_path,
            entity_type=entity_type,
            entity_id=entity_id,
            area_id=context.area_id,
            section_id=context.section_id,
            control_point_id=context.control_point_id,
        )

        if existing is None:
            return self.set_result(
                entity_type,
                entity_id,
                context,
                result=CONTROL_RESULT_NEKONTROLOVANO,
                photo_path=relative_path,
            )

        existing.photo_path = relative_path
        return self.repository.save(existing)

    def remove_photo(
        self,
        entity_type: str,
        entity_id: int,
        context: ControlPointContext,
    ) -> ControlResult | None:
        self._validate_entity(entity_type, entity_id)

        existing = self.get_for_control_point(entity_type, entity_id, context)
        if existing is None or not existing.photo_path:
            return existing

        control_result_photo_service.delete_photo(existing.photo_path)
        existing.photo_path = ""
        return self.repository.save(existing)

    def resolve_photo_path(self, control_result: ControlResult | None) -> Path | None:
        if control_result is None or not control_result.photo_path:
            return None

        path = control_result_photo_service.absolute_photo_path(control_result.photo_path)
        return path if path.is_file() else None

    def delete_for_entity(self, entity_type: str, entity_id: int) -> int:
        self._validate_entity(entity_type, entity_id)
        for row in self.get_for_entity(entity_type, entity_id):
            if row.photo_path:
                control_result_photo_service.delete_photo(row.photo_path)
        return self.repository.delete_for_entity(entity_type, entity_id)

    def _validate_entity(self, entity_type: str, entity_id: int) -> None:
        if entity_type not in CONTROL_RESULT_PARENT_ENTITY_TYPES:
            raise ValueError(f"Neplatný entity_type pro výsledek kontroly: {entity_type}")
        if entity_id <= 0:
            raise ValueError("entity_id musí být kladné celé číslo.")


control_result_service = ControlResultService()
