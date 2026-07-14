from sqlalchemy import select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_ai_export import HazardAiExport


class HazardAiExportRepository:
    def get_for_identification(self, hazard_identification_id: int) -> list[HazardAiExport]:
        with get_session() as session:
            stmt = (
                select(HazardAiExport)
                .where(HazardAiExport.hazard_identification_id == hazard_identification_id)
                .order_by(HazardAiExport.exported_at.desc(), HazardAiExport.id.desc())
            )
            return list(session.scalars(stmt))

    def get_by_id(self, export_id: int) -> HazardAiExport | None:
        with get_session() as session:
            return session.get(HazardAiExport, export_id)

    def add(self, export: HazardAiExport) -> HazardAiExport:
        with get_session() as session:
            session.add(export)
            session.commit()
            session.refresh(export)
            return export
