from sqlalchemy import delete, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
from moduly.rizeni_rizik.modely.hazard_library_template_operation import (
    HazardLibraryTemplateOperation,
)


class HazardLibraryTemplateRepository:
    def get_all(self, include_inactive: bool = False) -> list[HazardLibraryTemplate]:
        """Načte katalogové zdroje z DB v nové session (bez cache / snapshotu)."""
        with get_session() as session:
            # Nová session + populate_existing: vždy aktuální řádky z DB
            # (žádný dlouho žijící identity map / stale snapshot).
            stmt = select(HazardLibraryTemplate).execution_options(
                populate_existing=True,
            )
            if not include_inactive:
                stmt = stmt.where(HazardLibraryTemplate.active == True)  # noqa: E712
            stmt = stmt.order_by(
                HazardLibraryTemplate.name,
                HazardLibraryTemplate.version_number.desc(),
            )
            templates = list(session.scalars(stmt))
            # Odpoj od session se zachovanými atributy (po close jsou bezpečně čitelné).
            session.expunge_all()
            return templates

    def get_by_id(self, template_id: int) -> HazardLibraryTemplate | None:
        with get_session() as session:
            return session.get(HazardLibraryTemplate, template_id)

    def add(self, template: HazardLibraryTemplate) -> HazardLibraryTemplate:
        with get_session() as session:
            session.add(template)
            session.commit()
            session.refresh(template)
            return template

    def update(self, template: HazardLibraryTemplate) -> HazardLibraryTemplate:
        with get_session() as session:
            template = session.merge(template)
            session.commit()
            session.refresh(template)
            return template

    def activate(self, template_id: int) -> bool:
        return self._set_active(template_id, True)

    def deactivate(self, template_id: int) -> bool:
        return self._set_active(template_id, False)

    def _set_active(self, template_id: int, active: bool) -> bool:
        with get_session() as session:
            template = session.get(HazardLibraryTemplate, template_id)
            if template is None:
                return False
            template.active = active
            session.commit()
            return True


class HazardLibraryTemplateOperationRepository:
    def get_operation_ids(self, template_id: int) -> list[int]:
        with get_session() as session:
            stmt = (
                select(HazardLibraryTemplateOperation.operation_id)
                .where(HazardLibraryTemplateOperation.template_id == template_id)
                .order_by(HazardLibraryTemplateOperation.operation_id)
            )
            return list(session.scalars(stmt))

    def get_counts_by_templates(self, template_ids: list[int]) -> dict[int, int]:
        if not template_ids:
            return {}
        with get_session() as session:
            rows = session.execute(
                select(
                    HazardLibraryTemplateOperation.template_id,
                    HazardLibraryTemplateOperation.operation_id,
                ).where(HazardLibraryTemplateOperation.template_id.in_(template_ids)),
            ).all()
        counts: dict[int, int] = {}
        for template_id, _operation_id in rows:
            counts[template_id] = counts.get(template_id, 0) + 1
        return counts

    def replace_operations(self, template_id: int, operation_ids: list[int]) -> None:
        unique_ids = sorted(set(operation_ids))
        with get_session() as session:
            session.execute(
                delete(HazardLibraryTemplateOperation).where(
                    HazardLibraryTemplateOperation.template_id == template_id,
                ),
            )
            for operation_id in unique_ids:
                session.add(
                    HazardLibraryTemplateOperation(
                        template_id=template_id,
                        operation_id=operation_id,
                    ),
                )
            session.commit()

    def clear_operations(self, template_id: int) -> None:
        with get_session() as session:
            session.execute(
                delete(HazardLibraryTemplateOperation).where(
                    HazardLibraryTemplateOperation.template_id == template_id,
                ),
            )
            session.commit()

    def has_link(self, template_id: int, operation_id: int) -> bool:
        with get_session() as session:
            stmt = select(HazardLibraryTemplateOperation.id).where(
                HazardLibraryTemplateOperation.template_id == template_id,
                HazardLibraryTemplateOperation.operation_id == operation_id,
            )
            return session.scalar(stmt) is not None
