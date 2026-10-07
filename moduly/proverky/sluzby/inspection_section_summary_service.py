"""Služba souhrnných sdělení za okruh prověrky."""

from __future__ import annotations

from moduly.proverky.modely.inspection_section_summary import InspectionSectionSummary
from moduly.proverky.repository.inspection_section_summary_repository import (
    InspectionSectionSummaryRepository,
)


class InspectionSectionSummaryService:
    def __init__(self) -> None:
        self.repository = InspectionSectionSummaryRepository()

    def get_text(
        self,
        inspection_id: int | None,
        *,
        area_id: str,
        section_id: str,
    ) -> str:
        if inspection_id is None:
            return ""
        row = self.repository.get_for_section(
            int(inspection_id),
            area_id=area_id,
            section_id=section_id,
        )
        return str(row.summary_text or "") if row is not None else ""

    def map_for_inspection(self, inspection_id: int | None) -> dict[tuple[str, str], str]:
        if inspection_id is None:
            return {}
        mapping: dict[tuple[str, str], str] = {}
        for row in self.repository.get_for_inspection(int(inspection_id)):
            key = (str(row.area_id or "").strip(), str(row.section_id or "").strip())
            if key[0] and key[1]:
                mapping[key] = str(row.summary_text or "")
        return mapping

    def set_text(
        self,
        inspection_id: int,
        *,
        area_id: str,
        section_id: str,
        summary_text: str,
        session=None,
    ) -> InspectionSectionSummary | None:
        return self.repository.upsert(
            int(inspection_id),
            area_id=area_id,
            section_id=section_id,
            summary_text=summary_text,
            session=session,
        )

    def delete_for_inspection(self, inspection_id: int) -> None:
        self.repository.delete_for_inspection(int(inspection_id))


inspection_section_summary_service = InspectionSectionSummaryService()
