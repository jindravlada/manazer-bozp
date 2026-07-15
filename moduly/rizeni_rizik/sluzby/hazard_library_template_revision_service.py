from dataclasses import dataclass
from datetime import datetime

from moduly.rizeni_rizik.constants_library import (
    HAZARD_LIBRARY_REVISION_REASON_LABELS,
)
from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
    HazardLibraryTemplateRevision,
)
from moduly.rizeni_rizik.repository.hazard_library_template_revision_repository import (
    HazardLibraryTemplateRevisionRepository,
)


@dataclass(frozen=True)
class HazardLibraryTemplateRevisionRow:
    revision_number: int
    created_at: datetime
    reason_label: str


class HazardLibraryTemplateRevisionService:
    def __init__(self):
        self.repository = HazardLibraryTemplateRevisionRepository()

    def record_revision(
        self,
        template_id: int,
        *,
        revision_number: int,
        change_reason: str,
        created_at: datetime | None = None,
    ) -> HazardLibraryTemplateRevision:
        revision = HazardLibraryTemplateRevision(
            template_id=template_id,
            revision_number=revision_number,
            change_reason=change_reason,
        )
        if created_at is not None:
            revision.created_at = created_at
        return self.repository.add(revision)

    def get_rows(self, template_id: int) -> list[HazardLibraryTemplateRevisionRow]:
        revisions = self.repository.get_for_template(template_id)
        return [
            HazardLibraryTemplateRevisionRow(
                revision_number=revision.revision_number,
                created_at=revision.created_at,
                reason_label=self.format_reason_label(revision.change_reason),
            )
            for revision in revisions
        ]

    def format_reason_label(self, change_reason: str) -> str:
        return HAZARD_LIBRARY_REVISION_REASON_LABELS.get(change_reason, change_reason)


hazard_library_template_revision_service = HazardLibraryTemplateRevisionService()
