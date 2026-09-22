from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from moduly.rizeni_rizik.sluzby.exposed_target_ref import SOURCE_TYPE_HAZARD_GROUP


class HazardExistingMeasureExposedGroup(Base):
    """M:N vazba zásady bezpečné práce na ohrožené skupiny / role posouzení."""

    __tablename__ = "hazard_existing_measure_exposed_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    measure_id: Mapped[int] = mapped_column(Integer, nullable=False)
    exposed_group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SOURCE_TYPE_HAZARD_GROUP,
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    @property
    def source_id(self) -> int:
        return int(self.exposed_group_id)
