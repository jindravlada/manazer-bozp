from sqlalchemy import delete, select

from core.database.session import get_session
from moduly.rizeni_rizik.modely.profession_exposed_group import ProfessionExposedGroup


class ProfessionExposedGroupRepository:
    def list_group_ids(self, profession_id: int) -> list[int]:
        with get_session() as session:
            stmt = (
                select(ProfessionExposedGroup.exposed_group_id)
                .where(ProfessionExposedGroup.profession_id == profession_id)
                .order_by(
                    ProfessionExposedGroup.sort_order,
                    ProfessionExposedGroup.id,
                )
            )
            return [int(value) for value in session.scalars(stmt)]

    def replace_groups(self, profession_id: int, group_ids: list[int]) -> None:
        unique_ids: list[int] = []
        seen: set[int] = set()
        for group_id in group_ids:
            if group_id in seen:
                continue
            seen.add(group_id)
            unique_ids.append(int(group_id))

        with get_session() as session:
            session.execute(
                delete(ProfessionExposedGroup).where(
                    ProfessionExposedGroup.profession_id == profession_id,
                ),
            )
            for sort_order, group_id in enumerate(unique_ids, start=1):
                session.add(
                    ProfessionExposedGroup(
                        profession_id=profession_id,
                        exposed_group_id=group_id,
                        sort_order=sort_order,
                    ),
                )
            session.commit()
