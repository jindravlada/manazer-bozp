from sqlalchemy import delete, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.hazard_existing_measure_exposed_group import (
    HazardExistingMeasureExposedGroup,
)
from moduly.rizeni_rizik.sluzby.existing_measure_relevance import (
    list_refs_for_measures_in_session,
    list_refs_in_session,
    replace_refs_in_session,
    unique_refs,
)
from moduly.rizeni_rizik.sluzby.exposed_target_ref import ExposedTargetRef


class HazardExistingMeasureExposedGroupRepository:
    model = HazardExistingMeasureExposedGroup

    def list_refs(self, measure_id: int) -> list[ExposedTargetRef]:
        with get_session() as session:
            return list_refs_in_session(session, self.model, measure_id)

    def list_refs_for_measures(
        self,
        measure_ids: list[int] | tuple[int, ...] | None,
    ) -> dict[int, list[ExposedTargetRef]]:
        with get_session() as session:
            return list_refs_for_measures_in_session(
                session,
                self.model,
                [int(measure_id) for measure_id in (measure_ids or ())],
            )

    def replace_refs(self, measure_id: int, refs: list[ExposedTargetRef]) -> None:
        with get_session() as session:
            replace_refs_in_session(session, self.model, measure_id, unique_refs(refs))
            session.commit()

    def delete_for_measures(self, measure_ids: list[int] | tuple[int, ...]) -> None:
        if not measure_ids:
            return
        with get_session() as session:
            session.execute(
                delete(self.model).where(self.model.measure_id.in_(list(measure_ids))),
            )
            session.commit()
