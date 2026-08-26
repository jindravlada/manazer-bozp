from datetime import datetime

from sqlalchemy import select

from core.database.session import get_session
from core.shared.section_summary import (
    normalize_section_summary_text,
    section_summary_key,
)
from moduly.proverky.modely.inspection_section_summary import InspectionSectionSummary


class InspectionSectionSummaryRepository:
    def get_for_inspection(self, inspection_id: int) -> list[InspectionSectionSummary]:
        with get_session() as session:
            stmt = select(InspectionSectionSummary).where(
                InspectionSectionSummary.inspection_id == int(inspection_id)
            )
            rows = list(session.scalars(stmt))
            for row in rows:
                session.expunge(row)
            return rows

    def get_for_section(
        self,
        inspection_id: int,
        *,
        area_id: str,
        section_id: str,
    ) -> InspectionSectionSummary | None:
        area_id, section_id = section_summary_key(area_id, section_id)
        with get_session() as session:
            stmt = select(InspectionSectionSummary).where(
                InspectionSectionSummary.inspection_id == int(inspection_id),
                InspectionSectionSummary.area_id == area_id,
                InspectionSectionSummary.section_id == section_id,
            )
            row = session.scalars(stmt).first()
            if row is None:
                return None
            session.expunge(row)
            return row

    def upsert(
        self,
        inspection_id: int,
        *,
        area_id: str,
        section_id: str,
        summary_text: str,
    ) -> InspectionSectionSummary | None:
        area_id, section_id = section_summary_key(area_id, section_id)
        text = normalize_section_summary_text(summary_text)
        if not area_id or not section_id:
            return None
        now = datetime.now()
        with get_session() as session:
            stmt = select(InspectionSectionSummary).where(
                InspectionSectionSummary.inspection_id == int(inspection_id),
                InspectionSectionSummary.area_id == area_id,
                InspectionSectionSummary.section_id == section_id,
            )
            row = session.scalars(stmt).first()
            if not text.strip():
                if row is not None:
                    session.delete(row)
                    session.commit()
                return None
            if row is None:
                row = InspectionSectionSummary(
                    inspection_id=int(inspection_id),
                    area_id=area_id,
                    section_id=section_id,
                    summary_text=text,
                    created_at=now,
                    updated_at=now,
                )
                session.add(row)
            else:
                row.summary_text = text
                row.updated_at = now
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def delete_for_inspection(self, inspection_id: int) -> None:
        with get_session() as session:
            rows = list(
                session.scalars(
                    select(InspectionSectionSummary).where(
                        InspectionSectionSummary.inspection_id == int(inspection_id)
                    )
                )
            )
            for row in rows:
                session.delete(row)
            session.commit()
