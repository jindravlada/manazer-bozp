"""Pracovní kopie editoru Identifikace nebezpečí (UX-SAVE-1c).

Veškeré změny obsahu během editace probíhají pouze v paměti.
Do DB se zapisuje až při finálním Uložit v jedné transakci.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select

from core.services.storage_service import storage_service
from core.utils.czech_sort import czech_sorted
from core.database.session import get_session
from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
from moduly.rizeni_rizik.constants import (
    DEFAULT_RISK_ASSESSMENT_STATUS,
    HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
    HAZARD_IDENTIFICATION_STATUSES,
    HAZARD_INVENTORY_CATEGORIES,
    HAZARD_INVENTORY_CATEGORY_LABELS,
    RISK_ASSESSMENT_STATUS_COMPLETED,
    RISK_ASSESSMENT_STATUSES,
    RISK_SEVERITIES,
    format_risk_assessment_status_label,
    format_risk_severity_label,
)
from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
from moduly.rizeni_rizik.modely.hazard_identification_photo import HazardIdentificationPhoto
from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
    HazardRiskAssessmentExposedGroup,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import (
    HazardEventError,
    normalize_event_name,
)
from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
    HazardExistingMeasureError,
    normalize_measure_description,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_photo_service import (
    ALLOWED_PHOTO_EXTENSIONS,
    HazardIdentificationPhotoError,
    hazard_identification_photo_service,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    HazardIdentificationError,
    hazard_identification_service,
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
    HazardInventoryItemError,
    normalize_inventory_name,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_apply_service import (
    HazardLibraryTemplateApplyError,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
    hazard_library_template_assessment_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
    hazard_library_template_event_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
    hazard_library_template_existing_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
    hazard_library_template_required_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
    hazard_library_template_service,
)
from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
    HazardRequiredMeasureError,
    normalize_required_measure_description,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    HazardRiskAssessmentError,
    HazardRiskAssessmentRow,
)


@dataclass
class IdWcMeasure:
    id: int
    hazard_risk_assessment_id: int
    description: str
    note: str = ""
    active: bool = True
    modified: bool = False
    sort_order: int = 0


@dataclass
class IdWcAssessment:
    id: int
    hazard_event_id: int
    exposed_group_id: int | None = None
    exposed_group_ids: list[int] = field(default_factory=list)
    exposed_group: str = ""
    severity: str = ""
    note: str = ""
    assessment_status: str = DEFAULT_RISK_ASSESSMENT_STATUS
    conclusion: str = ""
    completed_at: datetime | None = None
    active: bool = True
    modified: bool = False
    existing_measures: list[IdWcMeasure] = field(default_factory=list)
    required_measures: list[IdWcMeasure] = field(default_factory=list)


@dataclass
class IdWcEvent:
    id: int
    inventory_item_id: int
    name: str
    description: str = ""
    note: str = ""
    active: bool = True
    modified: bool = False
    sort_order: int = 0
    assessments: list[IdWcAssessment] = field(default_factory=list)


@dataclass
class IdWcInventoryItem:
    id: int
    hazard_identification_id: int
    category: str
    name: str
    description: str = ""
    active: bool = True
    sort_order: int = 0
    source_template_id: int | None = None
    source_template_version: int | None = None
    events: list[IdWcEvent] = field(default_factory=list)


@dataclass
class IdWcPhoto:
    id: int
    hazard_identification_id: int
    filename: str = ""
    stored_filename: str = ""
    relative_path: str = ""
    caption: str = ""
    note: str = ""
    taken_at: datetime | None = None
    file_size: int = 0
    width: int = 0
    height: int = 0
    active: bool = True
    sort_order: int = 0
    staged_source_path: str | None = None


@dataclass
class IdApplyResult:
    item: IdWcInventoryItem
    template: HazardLibraryTemplate
    event_count: int
    assessment_count: int
    existing_measure_count: int
    required_measure_count: int


class HazardIdentificationWorkingCopy:
    """In-memory strom obsahu identifikace nebezpečí."""

    def __init__(self, identification_id: int):
        self.identification_id = identification_id
        self.items: list[IdWcInventoryItem] = []
        self.photos: list[IdWcPhoto] = []
        self._next_temp_id = -1
        self._dirty = False

    @classmethod
    def load(cls, identification_id: int) -> HazardIdentificationWorkingCopy:
        wc = cls(identification_id)
        session = get_session()
        try:
            db_items = list(
                session.scalars(
                    select(HazardInventoryItem)
                    .where(HazardInventoryItem.hazard_identification_id == identification_id)
                    .order_by(
                        HazardInventoryItem.category,
                        HazardInventoryItem.sort_order,
                        HazardInventoryItem.name,
                        HazardInventoryItem.id,
                    ),
                ),
            )
            db_items = czech_sorted(
                db_items,
                key=lambda item: (item.category, item.sort_order, item.name),
            )
            for db_item in db_items:
                wc_item = IdWcInventoryItem(
                    id=int(db_item.id),
                    hazard_identification_id=identification_id,
                    category=db_item.category,
                    name=db_item.name,
                    description=db_item.description or "",
                    active=bool(db_item.active),
                    sort_order=int(db_item.sort_order or 0),
                    source_template_id=db_item.source_template_id,
                    source_template_version=db_item.source_template_version,
                )
                db_events = list(
                    session.scalars(
                        select(HazardEvent)
                        .where(HazardEvent.inventory_item_id == db_item.id)
                        .order_by(HazardEvent.sort_order, HazardEvent.name, HazardEvent.id),
                    ),
                )
                for db_event in db_events:
                    wc_event = IdWcEvent(
                        id=int(db_event.id),
                        inventory_item_id=int(db_item.id),
                        name=db_event.name,
                        description=db_event.description or "",
                        note=db_event.note or "",
                        active=bool(db_event.active),
                        modified=bool(db_event.modified),
                        sort_order=int(db_event.sort_order or 0),
                    )
                    db_assessments = list(
                        session.scalars(
                            select(HazardRiskAssessment)
                            .where(HazardRiskAssessment.hazard_event_id == db_event.id)
                            .order_by(
                                HazardRiskAssessment.exposed_group,
                                HazardRiskAssessment.id,
                            ),
                        ),
                    )
                    for db_assessment in db_assessments:
                        group_ids = list(
                            session.scalars(
                                select(HazardRiskAssessmentExposedGroup.exposed_group_id)
                                .where(
                                    HazardRiskAssessmentExposedGroup.assessment_id
                                    == db_assessment.id,
                                )
                                .order_by(HazardRiskAssessmentExposedGroup.sort_order),
                            ),
                        )
                        if not group_ids and db_assessment.exposed_group_id:
                            group_ids = [int(db_assessment.exposed_group_id)]
                        wc_assessment = IdWcAssessment(
                            id=int(db_assessment.id),
                            hazard_event_id=int(db_event.id),
                            exposed_group_id=int(group_ids[0]) if group_ids else None,
                            exposed_group_ids=[int(g) for g in group_ids],
                            exposed_group=db_assessment.exposed_group or "",
                            severity=db_assessment.severity or "",
                            note=db_assessment.note or "",
                            assessment_status=db_assessment.assessment_status
                            or DEFAULT_RISK_ASSESSMENT_STATUS,
                            conclusion=db_assessment.conclusion or "",
                            completed_at=db_assessment.completed_at,
                            active=bool(db_assessment.active),
                            modified=bool(db_assessment.modified),
                        )
                        existing = list(
                            session.scalars(
                                select(HazardExistingMeasure)
                                .where(
                                    HazardExistingMeasure.hazard_risk_assessment_id
                                    == db_assessment.id,
                                )
                                .order_by(
                                    HazardExistingMeasure.sort_order,
                                    HazardExistingMeasure.description,
                                    HazardExistingMeasure.id,
                                ),
                            ),
                        )
                        for measure in existing:
                            wc_assessment.existing_measures.append(
                                IdWcMeasure(
                                    id=int(measure.id),
                                    hazard_risk_assessment_id=int(db_assessment.id),
                                    description=measure.description or "",
                                    note=measure.note or "",
                                    active=bool(measure.active),
                                    modified=bool(measure.modified),
                                    sort_order=int(measure.sort_order or 0),
                                ),
                            )
                        required = list(
                            session.scalars(
                                select(HazardRequiredMeasure)
                                .where(
                                    HazardRequiredMeasure.hazard_risk_assessment_id
                                    == db_assessment.id,
                                )
                                .order_by(
                                    HazardRequiredMeasure.sort_order,
                                    HazardRequiredMeasure.description,
                                    HazardRequiredMeasure.id,
                                ),
                            ),
                        )
                        for measure in required:
                            wc_assessment.required_measures.append(
                                IdWcMeasure(
                                    id=int(measure.id),
                                    hazard_risk_assessment_id=int(db_assessment.id),
                                    description=measure.description or "",
                                    note=measure.note or "",
                                    active=bool(measure.active),
                                    modified=bool(measure.modified),
                                    sort_order=int(measure.sort_order or 0),
                                ),
                            )
                        wc_event.assessments.append(wc_assessment)
                    wc_item.events.append(wc_event)
                wc.items.append(wc_item)

            db_photos = list(
                session.scalars(
                    select(HazardIdentificationPhoto)
                    .where(
                        HazardIdentificationPhoto.hazard_identification_id
                        == identification_id,
                    )
                    .order_by(
                        HazardIdentificationPhoto.sort_order,
                        HazardIdentificationPhoto.id,
                    ),
                ),
            )
            for db_photo in db_photos:
                wc.photos.append(
                    IdWcPhoto(
                        id=int(db_photo.id),
                        hazard_identification_id=identification_id,
                        filename=db_photo.filename or "",
                        stored_filename=db_photo.stored_filename or "",
                        relative_path=db_photo.relative_path or "",
                        caption=db_photo.caption or "",
                        note=db_photo.note or "",
                        taken_at=db_photo.taken_at,
                        file_size=int(db_photo.file_size or 0),
                        width=int(db_photo.width or 0),
                        height=int(db_photo.height or 0),
                        active=bool(db_photo.active),
                        sort_order=int(db_photo.sort_order or 0),
                    ),
                )
        finally:
            session.close()
        wc._dirty = False
        return wc

    @property
    def is_dirty(self) -> bool:
        return self._dirty

    def mark_clean(self) -> None:
        self._dirty = False

    def _touch(self) -> None:
        self._dirty = True

    def _alloc_id(self) -> int:
        value = self._next_temp_id
        self._next_temp_id -= 1
        return value

    # --- Inventory items --------------------------------------------------------

    def get_item(self, item_id: int | None) -> IdWcInventoryItem | None:
        if not item_id:
            return None
        for item in self.items:
            if item.id == item_id:
                return item
        return None

    def get_items(
        self,
        *,
        category: str | None = None,
        include_inactive: bool = True,
    ) -> list[IdWcInventoryItem]:
        rows = self.items
        if category is not None:
            rows = [item for item in rows if item.category == category]
        if not include_inactive:
            rows = [item for item in rows if item.active]
        return sorted(
            rows,
            key=lambda row: (row.category, row.sort_order, row.name.casefold(), row.id),
        )

    def count_active_by_category(self) -> dict[str, int]:
        counts = {category: 0 for category in HAZARD_INVENTORY_CATEGORIES}
        for item in self.items:
            if item.active and item.category in counts:
                counts[item.category] += 1
        return counts

    def create_item(
        self,
        *,
        category: str,
        name: str,
        description: str = "",
        active: bool = True,
    ) -> IdWcInventoryItem:
        normalized_name = name.strip()
        if not normalized_name:
            raise HazardInventoryItemError("Název je povinný.")
        self._validate_category(category)
        self._validate_unique_active_item_name(
            category=category,
            name=normalized_name,
            exclude_item_id=None,
            active=active,
        )
        category_items = [item for item in self.items if item.category == category]
        sort_order = max((item.sort_order for item in category_items), default=0) + 1
        item = IdWcInventoryItem(
            id=self._alloc_id(),
            hazard_identification_id=self.identification_id,
            category=category,
            name=normalized_name,
            description=description.strip(),
            active=active,
            sort_order=sort_order,
        )
        self.items.append(item)
        self._touch()
        return item

    def update_item(
        self,
        item_id: int,
        *,
        category: str,
        name: str,
        description: str = "",
        active: bool = True,
    ) -> IdWcInventoryItem | None:
        item = self.get_item(item_id)
        if item is None:
            return None
        normalized_name = name.strip()
        if not normalized_name:
            raise HazardInventoryItemError("Název je povinný.")
        self._validate_category(category)
        self._validate_unique_active_item_name(
            category=category,
            name=normalized_name,
            exclude_item_id=item_id,
            active=active,
        )
        item.category = category
        item.name = normalized_name
        item.description = description.strip()
        item.active = active
        self._touch()
        return item

    def activate_item(self, item_id: int) -> bool:
        item = self.get_item(item_id)
        if item is None:
            return False
        self._validate_unique_active_item_name(
            category=item.category,
            name=item.name,
            exclude_item_id=item_id,
            active=True,
        )
        item.active = True
        self._touch()
        return True

    def deactivate_item(self, item_id: int) -> bool:
        item = self.get_item(item_id)
        if item is None:
            return False
        item.active = False
        self._touch()
        return True

    def _validate_category(self, category: str) -> None:
        if category not in HAZARD_INVENTORY_CATEGORIES:
            raise HazardInventoryItemError("Neplatná kategorie položky analýzy.")

    def _validate_unique_active_item_name(
        self,
        *,
        category: str,
        name: str,
        exclude_item_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return
        normalized = normalize_inventory_name(name)
        for item in self.items:
            if item.id == exclude_item_id:
                continue
            if not item.active:
                continue
            if item.category != category:
                continue
            if normalize_inventory_name(item.name) == normalized:
                label = HAZARD_INVENTORY_CATEGORY_LABELS.get(category, category)
                raise HazardInventoryItemError(
                    f"V kategorii {label} již existuje aktivní položka "
                    f"s názvem „{name.strip()}“.",
                )

    def _item_is_catalog_instance(self, inventory_item_id: int | None) -> bool:
        item = self.get_item(inventory_item_id)
        return item is not None and item.source_template_id is not None

    # --- Events -----------------------------------------------------------------

    def get_event(self, event_id: int | None) -> IdWcEvent | None:
        if not event_id:
            return None
        for item in self.items:
            for event in item.events:
                if event.id == event_id:
                    return event
        return None

    def get_events_for_item(
        self,
        inventory_item_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[IdWcEvent]:
        item = self.get_item(inventory_item_id)
        if item is None:
            return []
        rows = item.events
        if not include_inactive:
            rows = [event for event in rows if event.active]
        return sorted(rows, key=lambda row: (row.sort_order, row.name.casefold(), row.id))

    def count_active_by_inventory_items(self) -> dict[int, int]:
        counts: dict[int, int] = {}
        for item in self.items:
            if not item.active:
                continue
            for event in item.events:
                if event.active:
                    counts[item.id] = counts.get(item.id, 0) + 1
        return counts

    def create_event(
        self,
        *,
        inventory_item_id: int,
        name: str,
        description: str = "",
        note: str = "",
        active: bool = True,
    ) -> IdWcEvent:
        normalized_name = name.strip()
        if not normalized_name:
            raise HazardEventError("Název události je povinný.")
        self._validate_inventory_item(inventory_item_id)
        self._validate_unique_active_event_name(
            inventory_item_id,
            name=normalized_name,
            exclude_event_id=None,
            active=active,
        )
        item = self.get_item(inventory_item_id)
        assert item is not None
        sort_order = max((event.sort_order for event in item.events), default=0) + 1
        event = IdWcEvent(
            id=self._alloc_id(),
            inventory_item_id=inventory_item_id,
            name=normalized_name,
            description=description.strip(),
            note=note.strip(),
            active=active,
            sort_order=sort_order,
        )
        self._mark_event_modified(event)
        item.events.append(event)
        self._touch()
        return event

    def _find_item_containing_event(self, event_id: int) -> IdWcInventoryItem | None:
        for item in self.items:
            for event in item.events:
                if event.id == event_id:
                    return item
        return None

    def update_event(
        self,
        event_id: int,
        *,
        inventory_item_id: int,
        name: str,
        description: str = "",
        note: str = "",
        active: bool = True,
    ) -> IdWcEvent | None:
        event = self.get_event(event_id)
        if event is None:
            return None
        normalized_name = name.strip()
        if not normalized_name:
            raise HazardEventError("Název události je povinný.")
        self._validate_inventory_item(inventory_item_id)
        self._validate_unique_active_event_name(
            inventory_item_id,
            name=normalized_name,
            exclude_event_id=event_id,
            active=active,
        )
        current_item = self._find_item_containing_event(event_id)
        target_item = self.get_item(inventory_item_id)
        if (
            current_item is not None
            and target_item is not None
            and current_item.id != target_item.id
        ):
            current_item.events = [row for row in current_item.events if row.id != event_id]
            target_item.events.append(event)
        event.inventory_item_id = inventory_item_id
        event.name = normalized_name
        event.description = description.strip()
        event.note = note.strip()
        event.active = active
        self._mark_event_modified(event)
        self._touch()
        return event

    def activate_event(self, event_id: int) -> bool:
        event = self.get_event(event_id)
        if event is None:
            return False
        self._validate_unique_active_event_name(
            event.inventory_item_id,
            name=event.name,
            exclude_event_id=event_id,
            active=True,
        )
        event.active = True
        self._mark_event_modified(event)
        self._touch()
        return True

    def deactivate_event(self, event_id: int) -> bool:
        event = self.get_event(event_id)
        if event is None:
            return False
        event.active = False
        self._mark_event_modified(event)
        self._touch()
        return True

    def _validate_inventory_item(self, inventory_item_id: int) -> None:
        item = self.get_item(inventory_item_id)
        if item is None:
            raise HazardEventError("Zdroj rizika neexistuje.")
        if item.hazard_identification_id != self.identification_id:
            raise HazardEventError("Zdroj rizika musí patřit ke stejné identifikaci.")
        if not item.active:
            raise HazardEventError("Lze vybrat pouze aktivní zdroj rizika.")

    def _validate_unique_active_event_name(
        self,
        inventory_item_id: int,
        *,
        name: str,
        exclude_event_id: int | None,
        active: bool,
    ) -> None:
        if not active:
            return
        normalized = normalize_event_name(name)
        item = self.get_item(inventory_item_id)
        if item is None:
            return
        for event in item.events:
            if exclude_event_id is not None and event.id == exclude_event_id:
                continue
            if not event.active:
                continue
            if normalize_event_name(event.name) == normalized:
                raise HazardEventError(
                    f"U vybraného zdroje analýzy již existuje aktivní nežádoucí událost "
                    f"s názvem „{name.strip()}“.",
                )

    def _mark_event_modified(self, event: IdWcEvent) -> None:
        if self._item_is_catalog_instance(event.inventory_item_id):
            event.modified = True

    # --- Assessments ------------------------------------------------------------

    def get_assessment(self, assessment_id: int | None) -> IdWcAssessment | None:
        if not assessment_id:
            return None
        for item in self.items:
            for event in item.events:
                for assessment in event.assessments:
                    if assessment.id == assessment_id:
                        return assessment
        return None

    def list_assessment_rows(
        self,
        *,
        include_inactive: bool = True,
    ) -> list[HazardRiskAssessmentRow]:
        rows: list[HazardRiskAssessmentRow] = []
        for item in self.items:
            for event in item.events:
                for assessment in event.assessments:
                    if not include_inactive and not assessment.active:
                        continue
                    rows.append(self._to_assessment_row(assessment, item, event))
        return czech_sorted(
            rows,
            key=lambda row: (
                row.inventory_item_name.casefold(),
                row.event_name.casefold(),
                row.exposed_group_name.casefold(),
            ),
        )

    def count_active_by_events(self) -> dict[int, int]:
        counts: dict[int, int] = {}
        for item in self.items:
            for event in item.events:
                if event.active:
                    counts[event.id] = sum(
                        1 for assessment in event.assessments if assessment.active
                    )
        return counts

    def get_active_status_summary(self) -> dict[str, int]:
        total = draft_count = completed_count = 0
        for item in self.items:
            for event in item.events:
                for assessment in event.assessments:
                    if not assessment.active:
                        continue
                    total += 1
                    if assessment.assessment_status == RISK_ASSESSMENT_STATUS_COMPLETED:
                        completed_count += 1
                    else:
                        draft_count += 1
        return {
            "total": total,
            "draft": draft_count,
            "completed": completed_count,
        }

    def create_assessment(
        self,
        *,
        hazard_event_id: int,
        exposed_group_ids: list[int] | tuple[int, ...] | None = None,
        exposed_group_id: int | None = None,
        severity: str,
        note: str = "",
        assessment_status: str = DEFAULT_RISK_ASSESSMENT_STATUS,
        conclusion: str = "",
        active: bool = True,
    ) -> HazardRiskAssessment:
        event = self.get_event(hazard_event_id)
        if event is None:
            raise HazardRiskAssessmentError("Nežádoucí událost neexistuje.")
        group_ids = self._validate_exposed_group_ids(exposed_group_ids, exposed_group_id)
        normalized_severity = self._validate_severity(severity)
        self._validate_event_for_assessment(event)
        self._validate_unique_active_groups(
            hazard_event_id,
            group_ids,
            exclude_assessment_id=None,
            active=active,
        )
        assessment = IdWcAssessment(
            id=self._alloc_id(),
            hazard_event_id=hazard_event_id,
            exposed_group_id=group_ids[0],
            exposed_group_ids=list(group_ids),
            severity=normalized_severity,
            note=note.strip(),
            conclusion=conclusion.strip(),
            active=active,
        )
        self._apply_assessment_status(
            assessment,
            assessment_status=assessment_status,
            hazard_event_id=hazard_event_id,
            exposed_group_ids=group_ids,
            severity=normalized_severity,
        )
        self._mark_assessment_modified(assessment, event)
        event.assessments.append(assessment)
        self._touch()
        return self._assessment_proxy(assessment)

    def _find_event_containing_assessment(self, assessment_id: int) -> IdWcEvent | None:
        for item in self.items:
            for event in item.events:
                for assessment in event.assessments:
                    if assessment.id == assessment_id:
                        return event
        return None

    def update_assessment(
        self,
        assessment_id: int,
        *,
        hazard_event_id: int,
        exposed_group_ids: list[int] | tuple[int, ...] | None = None,
        exposed_group_id: int | None = None,
        severity: str,
        note: str = "",
        assessment_status: str = DEFAULT_RISK_ASSESSMENT_STATUS,
        conclusion: str = "",
        active: bool = True,
    ) -> HazardRiskAssessment | None:
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return None
        if assessment.hazard_event_id != hazard_event_id:
            raise HazardRiskAssessmentError(
                "Posouzení nepatří do zvolené nežádoucí události.",
            )
        event = self.get_event(hazard_event_id)
        if event is None:
            raise HazardRiskAssessmentError("Nežádoucí událost neexistuje.")
        group_ids = self._validate_exposed_group_ids(exposed_group_ids, exposed_group_id)
        normalized_severity = self._validate_severity(severity)
        self._validate_event_for_assessment(event)
        self._validate_unique_active_groups(
            hazard_event_id,
            group_ids,
            exclude_assessment_id=assessment_id,
            active=active,
        )
        current_event = self._find_event_containing_assessment(assessment_id)
        if current_event is not None and current_event.id != hazard_event_id:
            current_event.assessments = [
                row for row in current_event.assessments if row.id != assessment_id
            ]
            event.assessments.append(assessment)
        assessment.hazard_event_id = hazard_event_id
        assessment.exposed_group_id = group_ids[0]
        assessment.exposed_group_ids = list(group_ids)
        assessment.severity = normalized_severity
        assessment.note = note.strip()
        assessment.conclusion = conclusion.strip()
        assessment.active = active
        self._apply_assessment_status(
            assessment,
            assessment_status=assessment_status,
            hazard_event_id=hazard_event_id,
            exposed_group_ids=group_ids,
            severity=normalized_severity,
        )
        self._mark_assessment_modified(assessment, event)
        self._touch()
        return self._assessment_proxy(assessment)

    def activate_assessment(self, assessment_id: int) -> bool:
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return False
        if not assessment.exposed_group_ids and not assessment.exposed_group_id:
            raise HazardRiskAssessmentError("Posouzení nemá přiřazenou ohroženou skupinu.")
        group_ids = list(assessment.exposed_group_ids)
        if not group_ids and assessment.exposed_group_id:
            group_ids = [assessment.exposed_group_id]
        self._validate_unique_active_groups(
            assessment.hazard_event_id,
            group_ids,
            exclude_assessment_id=assessment_id,
            active=True,
        )
        assessment.active = True
        event = self.get_event(assessment.hazard_event_id)
        if event is not None:
            self._mark_assessment_modified(assessment, event)
        self._touch()
        return True

    def deactivate_assessment(self, assessment_id: int) -> bool:
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return False
        assessment.active = False
        event = self.get_event(assessment.hazard_event_id)
        if event is not None:
            self._mark_assessment_modified(assessment, event)
        self._touch()
        return True

    def _to_assessment_row(
        self,
        assessment: IdWcAssessment,
        item: IdWcInventoryItem,
        event: IdWcEvent,
    ) -> HazardRiskAssessmentRow:
        names = [
            exposed_group_service.display_name(group_id) or f"#{group_id}"
            for group_id in assessment.exposed_group_ids
        ]
        if not names and assessment.exposed_group_id:
            names = [
                exposed_group_service.display_name(assessment.exposed_group_id)
                or f"#{assessment.exposed_group_id}",
            ]
        exposed_group_name = ", ".join(names) if names else (assessment.exposed_group or "—")
        return HazardRiskAssessmentRow(
            assessment=self._assessment_proxy(assessment),
            event_name=event.name,
            inventory_item_name=item.name,
            exposed_group_name=exposed_group_name,
            severity_label=format_risk_severity_label(assessment.severity),
            status_label=format_risk_assessment_status_label(assessment.assessment_status),
            exposed_group_ids=tuple(assessment.exposed_group_ids),
        )

    def _assessment_proxy(self, assessment: IdWcAssessment) -> HazardRiskAssessment:
        return HazardRiskAssessment(
            id=assessment.id,
            hazard_event_id=assessment.hazard_event_id,
            exposed_group_id=assessment.exposed_group_id,
            exposed_group=assessment.exposed_group,
            severity=assessment.severity,
            note=assessment.note,
            assessment_status=assessment.assessment_status,
            conclusion=assessment.conclusion,
            completed_at=assessment.completed_at,
            active=assessment.active,
            modified=assessment.modified,
        )

    def _validate_exposed_group_ids(
        self,
        exposed_group_ids: list[int] | tuple[int, ...] | None,
        legacy_single_id: int | None,
    ) -> list[int]:
        values = list(exposed_group_ids or [])
        if not values and legacy_single_id is not None:
            values = [legacy_single_id]
        if not values:
            raise HazardRiskAssessmentError("Vyberte alespoň jednu ohroženou skupinu.")
        validated: list[int] = []
        seen: set[int] = set()
        for group_id in values:
            if group_id in seen:
                continue
            group = exposed_group_service.get_by_id(group_id)
            if group is None:
                raise HazardRiskAssessmentError("Vybraná ohrožená skupina neexistuje.")
            if not group.active:
                raise HazardRiskAssessmentError(
                    "Lze vybrat pouze aktivní ohroženou skupinu z číselníku.",
                )
            seen.add(group.id)
            validated.append(group.id)
        return validated

    def _validate_severity(self, severity: str) -> str:
        if severity not in RISK_SEVERITIES:
            raise HazardRiskAssessmentError("Neplatná závažnost následku.")
        return severity

    def _apply_assessment_status(
        self,
        assessment: IdWcAssessment,
        *,
        assessment_status: str,
        hazard_event_id: int,
        exposed_group_ids: list[int],
        severity: str,
    ) -> None:
        if assessment_status not in RISK_ASSESSMENT_STATUSES:
            raise HazardRiskAssessmentError("Neplatný stav posouzení.")
        if assessment_status == RISK_ASSESSMENT_STATUS_COMPLETED:
            event = self.get_event(hazard_event_id)
            if event is None:
                raise HazardRiskAssessmentError("Nežádoucí událost neexistuje.")
            self._validate_event_for_assessment(event)
            self._validate_exposed_group_ids(exposed_group_ids, legacy_single_id=None)
            self._validate_severity(severity)
            assessment.completed_at = datetime.now()
        else:
            assessment.completed_at = None
        assessment.assessment_status = assessment_status

    def _validate_event_for_assessment(self, event: IdWcEvent) -> None:
        item = self.get_item(event.inventory_item_id)
        if item is None:
            raise HazardRiskAssessmentError("Nežádoucí událost neexistuje.")
        if item.hazard_identification_id != self.identification_id:
            raise HazardRiskAssessmentError(
                "Nežádoucí událost musí patřit ke stejné identifikaci.",
            )
        if not event.active:
            raise HazardRiskAssessmentError("Lze vybrat pouze aktivní nežádoucí událost.")

    def _validate_unique_active_groups(
        self,
        hazard_event_id: int,
        group_ids: list[int],
        *,
        exclude_assessment_id: int | None,
        active: bool,
    ) -> None:
        if not active or not group_ids:
            return
        event = self.get_event(hazard_event_id)
        if event is None:
            return
        wanted = set(group_ids)
        for assessment in event.assessments:
            if exclude_assessment_id is not None and assessment.id == exclude_assessment_id:
                continue
            if not assessment.active:
                continue
            other_ids = set(assessment.exposed_group_ids)
            if not other_ids and assessment.exposed_group_id:
                other_ids = {assessment.exposed_group_id}
            overlap = wanted.intersection(other_ids)
            if overlap:
                group_name = exposed_group_service.display_name(next(iter(overlap))) or "—"
                raise HazardRiskAssessmentError(
                    f"U vybrané nežádoucí události již existuje aktivní ohrožená skupina "
                    f"„{group_name}“.",
                )

    def _mark_assessment_modified(
        self,
        assessment: IdWcAssessment,
        event: IdWcEvent,
    ) -> None:
        if self._item_is_catalog_instance(event.inventory_item_id):
            assessment.modified = True

    # --- Measures ---------------------------------------------------------------

    def get_existing_measures_for_assessment(
        self,
        assessment_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[IdWcMeasure]:
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return []
        rows = assessment.existing_measures
        if not include_inactive:
            rows = [row for row in rows if row.active]
        return sorted(rows, key=lambda row: (row.sort_order, row.description.casefold(), row.id))

    def get_required_measures_for_assessment(
        self,
        assessment_id: int,
        *,
        include_inactive: bool = True,
    ) -> list[IdWcMeasure]:
        assessment = self.get_assessment(assessment_id)
        if assessment is None:
            return []
        rows = assessment.required_measures
        if not include_inactive:
            rows = [row for row in rows if row.active]
        return sorted(rows, key=lambda row: (row.sort_order, row.description.casefold(), row.id))

    def _get_existing_measure(self, measure_id: int | None) -> IdWcMeasure | None:
        if not measure_id:
            return None
        for item in self.items:
            for event in item.events:
                for assessment in event.assessments:
                    for measure in assessment.existing_measures:
                        if measure.id == measure_id:
                            return measure
        return None

    def _get_required_measure(self, measure_id: int | None) -> IdWcMeasure | None:
        if not measure_id:
            return None
        for item in self.items:
            for event in item.events:
                for assessment in event.assessments:
                    for measure in assessment.required_measures:
                        if measure.id == measure_id:
                            return measure
        return None

    def create_existing_measure(
        self,
        *,
        hazard_risk_assessment_id: int,
        description: str,
        note: str = "",
        active: bool = True,
    ) -> IdWcMeasure:
        return self._create_measure(
            hazard_risk_assessment_id,
            description=description,
            note=note,
            active=active,
            existing=True,
        )

    def create_required_measure(
        self,
        *,
        hazard_risk_assessment_id: int,
        description: str,
        note: str = "",
        active: bool = True,
    ) -> IdWcMeasure:
        return self._create_measure(
            hazard_risk_assessment_id,
            description=description,
            note=note,
            active=active,
            existing=False,
        )

    def update_existing_measure(
        self,
        measure_id: int,
        *,
        hazard_risk_assessment_id: int,
        description: str,
        note: str = "",
        active: bool = True,
    ) -> IdWcMeasure | None:
        return self._update_measure(
            measure_id,
            hazard_risk_assessment_id=hazard_risk_assessment_id,
            description=description,
            note=note,
            active=active,
            existing=True,
        )

    def update_required_measure(
        self,
        measure_id: int,
        *,
        hazard_risk_assessment_id: int,
        description: str,
        note: str = "",
        active: bool = True,
    ) -> IdWcMeasure | None:
        return self._update_measure(
            measure_id,
            hazard_risk_assessment_id=hazard_risk_assessment_id,
            description=description,
            note=note,
            active=active,
            existing=False,
        )

    def activate_existing_measure(self, measure_id: int) -> bool:
        return self._set_measure_active(measure_id, True, existing=True)

    def deactivate_existing_measure(self, measure_id: int) -> bool:
        return self._set_measure_active(measure_id, False, existing=True)

    def activate_required_measure(self, measure_id: int) -> bool:
        return self._set_measure_active(measure_id, True, existing=False)

    def deactivate_required_measure(self, measure_id: int) -> bool:
        return self._set_measure_active(measure_id, False, existing=False)

    def _create_measure(
        self,
        hazard_risk_assessment_id: int,
        *,
        description: str,
        note: str,
        active: bool,
        existing: bool,
    ) -> IdWcMeasure:
        assessment = self.get_assessment(hazard_risk_assessment_id)
        if assessment is None:
            raise (
                HazardExistingMeasureError
                if existing
                else HazardRequiredMeasureError
            )("Posouzení rizika neexistuje.")
        self._validate_assessment_for_measure(assessment)
        normalized = description.strip()
        if not normalized:
            raise (
                HazardExistingMeasureError
                if existing
                else HazardRequiredMeasureError
            )("Popis opatření je povinný.")
        bucket = assessment.existing_measures if existing else assessment.required_measures
        self._validate_unique_measure(
            bucket,
            description=normalized,
            exclude_measure_id=None,
            active=active,
            existing=existing,
        )
        sort_order = max((row.sort_order for row in bucket), default=0) + 1
        measure = IdWcMeasure(
            id=self._alloc_id(),
            hazard_risk_assessment_id=hazard_risk_assessment_id,
            description=normalized,
            note=note.strip(),
            active=active,
            sort_order=sort_order,
        )
        self._mark_measure_modified(measure, assessment)
        bucket.append(measure)
        self._touch()
        return measure

    def _find_assessment_containing_measure(
        self,
        measure_id: int,
        *,
        existing: bool,
    ) -> IdWcAssessment | None:
        for item in self.items:
            for event in item.events:
                for assessment in event.assessments:
                    bucket = (
                        assessment.existing_measures if existing else assessment.required_measures
                    )
                    for measure in bucket:
                        if measure.id == measure_id:
                            return assessment
        return None

    def _update_measure(
        self,
        measure_id: int,
        *,
        hazard_risk_assessment_id: int,
        description: str,
        note: str,
        active: bool,
        existing: bool,
    ) -> IdWcMeasure | None:
        measure = (
            self._get_existing_measure(measure_id)
            if existing
            else self._get_required_measure(measure_id)
        )
        if measure is None:
            return None
        assessment = self.get_assessment(hazard_risk_assessment_id)
        if assessment is None or measure.hazard_risk_assessment_id != hazard_risk_assessment_id:
            raise (
                HazardExistingMeasureError
                if existing
                else HazardRequiredMeasureError
            )("Opatření nepatří do zvoleného posouzení.")
        self._validate_assessment_for_measure(assessment)
        normalized = description.strip()
        if not normalized:
            raise (
                HazardExistingMeasureError
                if existing
                else HazardRequiredMeasureError
            )("Popis opatření je povinný.")
        bucket = assessment.existing_measures if existing else assessment.required_measures
        self._validate_unique_measure(
            bucket,
            description=normalized,
            exclude_measure_id=measure_id,
            active=active,
            existing=existing,
        )
        current_assessment = self._find_assessment_containing_measure(
            measure_id,
            existing=existing,
        )
        if (
            current_assessment is not None
            and current_assessment.id != hazard_risk_assessment_id
        ):
            if existing:
                current_assessment.existing_measures = [
                    row for row in current_bucket if row.id != measure_id
                ]
                assessment.existing_measures.append(measure)
            else:
                current_assessment.required_measures = [
                    row for row in current_bucket if row.id != measure_id
                ]
                assessment.required_measures.append(measure)
            measure.hazard_risk_assessment_id = hazard_risk_assessment_id
        measure.description = normalized
        measure.note = note.strip()
        measure.active = active
        self._mark_measure_modified(measure, assessment)
        self._touch()
        return measure

    def _set_measure_active(self, measure_id: int, active: bool, *, existing: bool) -> bool:
        measure = (
            self._get_existing_measure(measure_id)
            if existing
            else self._get_required_measure(measure_id)
        )
        if measure is None:
            return False
        assessment = self.get_assessment(measure.hazard_risk_assessment_id)
        if assessment is None:
            return False
        if active:
            bucket = assessment.existing_measures if existing else assessment.required_measures
            self._validate_unique_measure(
                bucket,
                description=measure.description,
                exclude_measure_id=measure_id,
                active=True,
                existing=existing,
            )
        measure.active = active
        self._mark_measure_modified(measure, assessment)
        self._touch()
        return True

    def _validate_assessment_for_measure(self, assessment: IdWcAssessment) -> None:
        event = self.get_event(assessment.hazard_event_id)
        if event is None:
            raise HazardExistingMeasureError("Posouzení rizika neexistuje.")
        item = self.get_item(event.inventory_item_id)
        if item is None:
            raise HazardExistingMeasureError("Posouzení rizika neexistuje.")
        if item.hazard_identification_id != self.identification_id:
            raise HazardExistingMeasureError(
                "Posouzení rizika musí patřit ke stejné identifikaci.",
            )

    def _validate_unique_measure(
        self,
        bucket: list[IdWcMeasure],
        *,
        description: str,
        exclude_measure_id: int | None,
        active: bool,
        existing: bool,
    ) -> None:
        if not active:
            return
        normalize_fn = (
            normalize_measure_description if existing else normalize_required_measure_description
        )
        key = normalize_fn(description)
        for measure in bucket:
            if exclude_measure_id is not None and measure.id == exclude_measure_id:
                continue
            if not measure.active:
                continue
            if normalize_fn(measure.description) == key:
                message = (
                    f"U vybraného posouzení již existuje aktivní opatření "
                    f"s popisem „{description.strip()}“."
                    if existing
                    else f"U vybraného posouzení již existuje aktivní potřebné opatření "
                    f"s popisem „{description.strip()}“."
                )
                raise (
                    HazardExistingMeasureError if existing else HazardRequiredMeasureError
                )(message)

    def _mark_measure_modified(
        self,
        measure: IdWcMeasure,
        assessment: IdWcAssessment,
    ) -> None:
        event = self.get_event(assessment.hazard_event_id)
        if event is not None and self._item_is_catalog_instance(event.inventory_item_id):
            measure.modified = True

    # --- Photos -----------------------------------------------------------------

    def get_photos(self, *, include_inactive: bool = True) -> list[IdWcPhoto]:
        rows = self.photos
        if not include_inactive:
            rows = [photo for photo in rows if photo.active]
        return sorted(rows, key=lambda row: (row.sort_order, row.id))

    def get_photo(self, photo_id: int | None) -> IdWcPhoto | None:
        if not photo_id:
            return None
        for photo in self.photos:
            if photo.id == photo_id:
                return photo
        return None

    def create_photo(
        self,
        *,
        source_path: str | Path,
        caption: str = "",
        note: str = "",
        taken_at: date | datetime | None = None,
        active: bool = True,
    ) -> IdWcPhoto:
        source = Path(source_path)
        if not source.is_file():
            raise HazardIdentificationPhotoError("Vybraný soubor neexistuje.")
        suffix = source.suffix.lower()
        if suffix not in ALLOWED_PHOTO_EXTENSIONS:
            raise HazardIdentificationPhotoError(
                "Podporované formáty fotografií jsou JPG, JPEG, PNG a WEBP.",
            )
        optimized = hazard_identification_photo_service._optimize(source)
        resolved_taken_at = hazard_identification_photo_service._normalize_taken_at(taken_at)
        if resolved_taken_at is None and optimized.taken_at is not None:
            resolved_taken_at = optimized.taken_at
        sort_order = max((photo.sort_order for photo in self.photos), default=0) + 1
        photo = IdWcPhoto(
            id=self._alloc_id(),
            hazard_identification_id=self.identification_id,
            filename=source.name,
            caption=(caption or "").strip(),
            note=(note or "").strip(),
            taken_at=resolved_taken_at,
            file_size=len(optimized.data),
            width=optimized.width,
            height=optimized.height,
            active=active,
            sort_order=sort_order,
            staged_source_path=str(source),
        )
        self.photos.append(photo)
        self._touch()
        return photo

    def update_photo(
        self,
        photo_id: int,
        *,
        caption: str = "",
        note: str = "",
        taken_at: date | datetime | None = None,
        active: bool = True,
    ) -> IdWcPhoto | None:
        photo = self.get_photo(photo_id)
        if photo is None:
            return None
        if photo.hazard_identification_id != self.identification_id:
            raise HazardIdentificationPhotoError(
                "Fotografie nepatří k aktuální identifikaci.",
            )
        photo.caption = (caption or "").strip()
        photo.note = (note or "").strip()
        photo.taken_at = hazard_identification_photo_service._normalize_taken_at(taken_at)
        photo.active = active
        self._touch()
        return photo

    def activate_photo(self, photo_id: int) -> bool:
        photo = self.get_photo(photo_id)
        if photo is None:
            return False
        photo.active = True
        self._touch()
        return True

    def deactivate_photo(self, photo_id: int) -> bool:
        photo = self.get_photo(photo_id)
        if photo is None:
            return False
        photo.active = False
        self._touch()
        return True

    # --- Apply from catalog template --------------------------------------------

    def apply_from_template(
        self,
        template_id: int,
        *,
        include_inactive: bool = False,
    ) -> IdApplyResult:
        identification = hazard_identification_service.get_by_id(self.identification_id)
        if identification is None:
            raise HazardLibraryTemplateApplyError("Identifikace neexistuje.")
        if identification.status == HAZARD_IDENTIFICATION_STATUS_ARCHIVED:
            raise HazardLibraryTemplateApplyError(
                "U archivované identifikace nelze převzít zdroj z katalogu.",
            )

        template = hazard_library_template_service.get_by_id(template_id)
        if template is None:
            raise HazardLibraryTemplateApplyError("Zdroj rizika neexistuje.")
        if not template.active:
            raise HazardLibraryTemplateApplyError(
                "Lze převzít pouze aktivní zdroj rizika z katalogu.",
            )

        applied_ids = {
            item.source_template_id
            for item in self.items
            if item.active and item.source_template_id is not None
        }
        if template.id in applied_ids:
            raise HazardLibraryTemplateApplyError(
                "Tento zdroj rizika z katalogu už je v identifikaci převzatý.",
            )

        try:
            self._validate_category(template.category)
            self._validate_unique_active_item_name(
                category=template.category,
                name=template.name,
                exclude_item_id=None,
                active=True,
            )
        except HazardInventoryItemError as error:
            raise HazardLibraryTemplateApplyError(str(error)) from error

        events = [
            event
            for event in hazard_library_template_event_service.get_for_template(
                template_id,
                include_inactive=True,
            )
            if include_inactive or event.active
        ]

        event_assessments: dict[int, list] = {}
        for event in events:
            assessments = [
                assessment
                for assessment in hazard_library_template_assessment_service.repository.get_for_event(
                    event.id,
                    include_inactive=True,
                )
                if include_inactive or assessment.active
            ]
            for assessment in assessments:
                if assessment.exposed_group_id is None:
                    raise HazardLibraryTemplateApplyError(
                        f"Posouzení události „{event.name}“ nemá přiřazenou ohroženou skupinu.",
                    )
            event_assessments[event.id] = assessments

        assessment_measures: dict[int, tuple[list, list]] = {}
        for event in events:
            for assessment in event_assessments[event.id]:
                existing = [
                    measure
                    for measure in hazard_library_template_existing_measure_service.get_for_assessment(
                        assessment.id,
                        include_inactive=True,
                    )
                    if include_inactive or measure.active
                ]
                required = [
                    measure
                    for measure in hazard_library_template_required_measure_service.get_for_assessment(
                        assessment.id,
                        include_inactive=True,
                    )
                    if include_inactive or measure.active
                ]
                assessment_measures[assessment.id] = (existing, required)

        category_items = [item for item in self.items if item.category == template.category]
        sort_order = max((item.sort_order for item in category_items), default=0) + 1
        wc_item = IdWcInventoryItem(
            id=self._alloc_id(),
            hazard_identification_id=self.identification_id,
            category=template.category,
            name=template.name.strip(),
            description=template.description or "",
            active=True,
            sort_order=sort_order,
            source_template_id=template.id,
            source_template_version=template.version_number,
        )

        event_count = 0
        assessment_count = 0
        existing_measure_count = 0
        required_measure_count = 0

        for event in events:
            wc_event = IdWcEvent(
                id=self._alloc_id(),
                inventory_item_id=wc_item.id,
                name=event.name,
                description=event.description or "",
                note=event.note or "",
                active=event.active if include_inactive else True,
                modified=False,
                sort_order=event.sort_order,
            )
            event_count += 1

            for assessment in event_assessments[event.id]:
                group_ids = hazard_library_template_assessment_service.get_group_ids(
                    assessment.id,
                )
                if not group_ids and assessment.exposed_group_id:
                    group_ids = [assessment.exposed_group_id]
                wc_assessment = IdWcAssessment(
                    id=self._alloc_id(),
                    hazard_event_id=wc_event.id,
                    exposed_group_id=group_ids[0] if group_ids else None,
                    exposed_group_ids=[int(g) for g in group_ids],
                    severity=assessment.severity,
                    note=assessment.note or "",
                    conclusion=assessment.conclusion or "",
                    assessment_status=DEFAULT_RISK_ASSESSMENT_STATUS,
                    completed_at=None,
                    active=assessment.active if include_inactive else True,
                    modified=False,
                )
                assessment_count += 1

                existing_measures, required_measures = assessment_measures[assessment.id]
                for measure in existing_measures:
                    wc_assessment.existing_measures.append(
                        IdWcMeasure(
                            id=self._alloc_id(),
                            hazard_risk_assessment_id=wc_assessment.id,
                            description=measure.description,
                            note=measure.note or "",
                            active=measure.active if include_inactive else True,
                            modified=False,
                            sort_order=measure.sort_order,
                        ),
                    )
                    existing_measure_count += 1
                for measure in required_measures:
                    wc_assessment.required_measures.append(
                        IdWcMeasure(
                            id=self._alloc_id(),
                            hazard_risk_assessment_id=wc_assessment.id,
                            description=measure.description,
                            note=measure.note or "",
                            active=measure.active if include_inactive else True,
                            modified=False,
                            sort_order=measure.sort_order,
                        ),
                    )
                    required_measure_count += 1
                wc_event.assessments.append(wc_assessment)
            wc_item.events.append(wc_event)

        self.items.append(wc_item)
        self._touch()
        return IdApplyResult(
            item=wc_item,
            template=template,
            event_count=event_count,
            assessment_count=assessment_count,
            existing_measure_count=existing_measure_count,
            required_measure_count=required_measure_count,
        )

    def sync_item_from_template(
        self,
        item_id: int,
        *,
        include_inactive: bool = False,
    ) -> IdApplyResult:
        """Obnoví aktivní instanci z aktuálního Masteru (ponechá ID položky)."""
        item = self.get_item(item_id)
        if item is None:
            raise HazardLibraryTemplateApplyError("Položka analýzy neexistuje.")
        if item.source_template_id is None:
            raise HazardLibraryTemplateApplyError(
                "Položka není převzata z katalogu zdrojů rizik.",
            )

        template = hazard_library_template_service.get_by_id(item.source_template_id)
        if template is None:
            raise HazardLibraryTemplateApplyError("Zdroj rizika neexistuje.")
        if not template.active:
            raise HazardLibraryTemplateApplyError(
                "Lze synchronizovat pouze z aktivního zdroje rizika z katalogu.",
            )

        try:
            self._validate_category(template.category)
            self._validate_unique_active_item_name(
                category=template.category,
                name=template.name,
                exclude_item_id=item.id,
                active=True,
            )
        except HazardInventoryItemError as error:
            raise HazardLibraryTemplateApplyError(str(error)) from error

        # Znovu sestav strom jako při převzetí, ale zachovej item.id / sort_order / active.
        events = [
            event
            for event in hazard_library_template_event_service.get_for_template(
                template.id,
                include_inactive=True,
            )
            if include_inactive or event.active
        ]
        event_assessments: dict[int, list] = {}
        for event in events:
            assessments = [
                assessment
                for assessment in hazard_library_template_assessment_service.repository.get_for_event(
                    event.id,
                    include_inactive=True,
                )
                if include_inactive or assessment.active
            ]
            for assessment in assessments:
                if assessment.exposed_group_id is None:
                    raise HazardLibraryTemplateApplyError(
                        f"Posouzení události „{event.name}“ nemá přiřazenou ohroženou skupinu.",
                    )
            event_assessments[event.id] = assessments

        assessment_measures: dict[int, tuple[list, list]] = {}
        for event in events:
            for assessment in event_assessments[event.id]:
                existing = [
                    measure
                    for measure in hazard_library_template_existing_measure_service.get_for_assessment(
                        assessment.id,
                        include_inactive=True,
                    )
                    if include_inactive or measure.active
                ]
                required = [
                    measure
                    for measure in hazard_library_template_required_measure_service.get_for_assessment(
                        assessment.id,
                        include_inactive=True,
                    )
                    if include_inactive or measure.active
                ]
                assessment_measures[assessment.id] = (existing, required)

        item.category = template.category
        item.name = template.name.strip()
        item.description = template.description or ""
        item.source_template_id = template.id
        item.source_template_version = template.version_number
        item.events = []

        event_count = 0
        assessment_count = 0
        existing_measure_count = 0
        required_measure_count = 0

        for event in events:
            wc_event = IdWcEvent(
                id=self._alloc_id(),
                inventory_item_id=item.id,
                name=event.name,
                description=event.description or "",
                note=event.note or "",
                active=event.active if include_inactive else True,
                modified=False,
                sort_order=event.sort_order,
            )
            event_count += 1
            for assessment in event_assessments[event.id]:
                group_ids = hazard_library_template_assessment_service.get_group_ids(
                    assessment.id,
                )
                if not group_ids and assessment.exposed_group_id:
                    group_ids = [assessment.exposed_group_id]
                wc_assessment = IdWcAssessment(
                    id=self._alloc_id(),
                    hazard_event_id=wc_event.id,
                    exposed_group_id=group_ids[0] if group_ids else None,
                    exposed_group_ids=[int(g) for g in group_ids],
                    severity=assessment.severity,
                    note=assessment.note or "",
                    conclusion=assessment.conclusion or "",
                    assessment_status=DEFAULT_RISK_ASSESSMENT_STATUS,
                    completed_at=None,
                    active=assessment.active if include_inactive else True,
                    modified=False,
                )
                assessment_count += 1
                existing_measures, required_measures = assessment_measures[assessment.id]
                for measure in existing_measures:
                    wc_assessment.existing_measures.append(
                        IdWcMeasure(
                            id=self._alloc_id(),
                            hazard_risk_assessment_id=wc_assessment.id,
                            description=measure.description,
                            note=measure.note or "",
                            active=measure.active if include_inactive else True,
                            modified=False,
                            sort_order=measure.sort_order,
                        ),
                    )
                    existing_measure_count += 1
                for measure in required_measures:
                    wc_assessment.required_measures.append(
                        IdWcMeasure(
                            id=self._alloc_id(),
                            hazard_risk_assessment_id=wc_assessment.id,
                            description=measure.description,
                            note=measure.note or "",
                            active=measure.active if include_inactive else True,
                            modified=False,
                            sort_order=measure.sort_order,
                        ),
                    )
                    required_measure_count += 1
                wc_event.assessments.append(wc_assessment)
            item.events.append(wc_event)

        self._touch()
        return IdApplyResult(
            item=item,
            template=template,
            event_count=event_count,
            assessment_count=assessment_count,
            existing_measure_count=existing_measure_count,
            required_measure_count=required_measure_count,
        )

    def apply_or_sync_template(
        self,
        template_id: int,
        *,
        include_inactive: bool = False,
    ) -> IdApplyResult:
        """Převzít Master, nebo synchronizovat existující aktivní instanci."""
        for item in self.items:
            if item.active and item.source_template_id == template_id:
                return self.sync_item_from_template(
                    item.id,
                    include_inactive=include_inactive,
                )
        return self.apply_from_template(
            template_id,
            include_inactive=include_inactive,
        )

    # --- Commit -----------------------------------------------------------------

    def commit(self, basics: dict[str, Any] | None = None) -> HazardIdentification:
        """Zapíše pracovní kopii do DB v jedné transakci."""
        session = get_session()
        try:
            identification = session.get(HazardIdentification, self.identification_id)
            if identification is None:
                raise ValueError("Identifikace neexistuje.")

            if basics is not None:
                self._apply_basics(identification, basics)

            id_map: dict[int, int] = {}
            self._commit_items(session, id_map)
            self._commit_photos(session, identification)

            session.commit()
            session.refresh(identification)
            result = HazardIdentification(
                id=int(identification.id),
                identification_number=identification.identification_number,
                operation_id=identification.operation_id,
                operation_name=identification.operation_name or "",
                workplace_id=identification.workplace_id,
                workplace_name=identification.workplace_name or "",
                workplace_part_id=identification.workplace_part_id,
                workplace_part_name=identification.workplace_part_name or "",
                responsible_person_id=identification.responsible_person_id,
                responsible_person_name=identification.responsible_person_name or "",
                started_at=identification.started_at,
                status=identification.status,
                note=identification.note or "",
                active=bool(identification.active),
            )
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        self.mark_clean()
        reloaded = HazardIdentificationWorkingCopy.load(self.identification_id)
        self.items = reloaded.items
        self.photos = reloaded.photos
        self._next_temp_id = reloaded._next_temp_id
        return result

    def _apply_basics(self, identification: HazardIdentification, data: dict[str, Any]) -> None:
        operation_id = data.get("operation_id", identification.operation_id)
        workplace_id = data.get("workplace_id", identification.workplace_id)
        workplace_part_id = data.get("workplace_part_id", identification.workplace_part_id)
        status = data.get("status", identification.status)
        if status not in HAZARD_IDENTIFICATION_STATUSES:
            raise HazardIdentificationError("Neplatný stav identifikace.")
        hazard_identification_service.validate_workplace_selection(
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
        )
        identification.operation_id = operation_id
        identification.operation_name = hazard_identification_service._workplace_name(operation_id)
        identification.workplace_id = workplace_id
        identification.workplace_name = hazard_identification_service._workplace_name(workplace_id)
        identification.workplace_part_id = workplace_part_id
        identification.workplace_part_name = hazard_identification_service._workplace_name(
            workplace_part_id,
        )
        identification.responsible_person_id = data.get(
            "responsible_person_id",
            identification.responsible_person_id,
        )
        identification.responsible_person_name = hazard_identification_service._person_name(
            identification.responsible_person_id,
        )
        identification.started_at = data.get("started_at", identification.started_at)
        identification.status = status
        identification.note = str(data.get("note", identification.note)).strip()
        if "active" in data:
            identification.active = bool(data["active"])
        identification.updated_at = datetime.now()

    def _commit_items(self, session, id_map: dict[int, int]) -> None:
        for item in self.items:
            if item.id > 0:
                db_item = session.get(HazardInventoryItem, item.id)
                if db_item is None:
                    continue
                db_item.category = item.category
                db_item.name = item.name
                db_item.description = item.description
                db_item.active = item.active
                db_item.sort_order = item.sort_order
                db_item.source_template_id = item.source_template_id
                db_item.source_template_version = item.source_template_version
                db_item.updated_at = datetime.now()
                item_db_id = int(db_item.id)
            else:
                db_item = HazardInventoryItem(
                    hazard_identification_id=self.identification_id,
                    category=item.category,
                    name=item.name,
                    description=item.description,
                    active=item.active,
                    sort_order=item.sort_order,
                    source_template_id=item.source_template_id,
                    source_template_version=item.source_template_version,
                )
                session.add(db_item)
                session.flush()
                item_db_id = int(db_item.id)
                id_map[item.id] = item_db_id

            for event in item.events:
                self._commit_event(session, event, item_db_id, id_map)

    def _commit_event(
        self,
        session,
        event: IdWcEvent,
        item_db_id: int,
        id_map: dict[int, int],
    ) -> None:
        inventory_item_id = item_db_id
        if event.id > 0:
            db_event = session.get(HazardEvent, event.id)
            if db_event is None:
                return
            db_event.inventory_item_id = inventory_item_id
            db_event.name = event.name
            db_event.description = event.description
            db_event.note = event.note
            db_event.active = event.active
            db_event.modified = event.modified
            db_event.sort_order = event.sort_order
            db_event.updated_at = datetime.now()
            event_db_id = int(db_event.id)
        else:
            db_event = HazardEvent(
                inventory_item_id=inventory_item_id,
                name=event.name,
                description=event.description,
                note=event.note,
                active=event.active,
                modified=event.modified,
                sort_order=event.sort_order,
            )
            session.add(db_event)
            session.flush()
            event_db_id = int(db_event.id)
            id_map[event.id] = event_db_id

        for assessment in event.assessments:
            self._commit_assessment(session, assessment, event_db_id, id_map)

    def _commit_assessment(
        self,
        session,
        assessment: IdWcAssessment,
        event_db_id: int,
        id_map: dict[int, int],
    ) -> None:
        if assessment.id > 0:
            db_assessment = session.get(HazardRiskAssessment, assessment.id)
            if db_assessment is None:
                return
            db_assessment.hazard_event_id = event_db_id
            db_assessment.exposed_group_id = assessment.exposed_group_id
            db_assessment.exposed_group = assessment.exposed_group
            db_assessment.severity = assessment.severity
            db_assessment.note = assessment.note
            db_assessment.assessment_status = assessment.assessment_status
            db_assessment.conclusion = assessment.conclusion
            db_assessment.completed_at = assessment.completed_at
            db_assessment.active = assessment.active
            db_assessment.modified = assessment.modified
            db_assessment.updated_at = datetime.now()
            assessment_db_id = int(db_assessment.id)
        else:
            db_assessment = HazardRiskAssessment(
                hazard_event_id=event_db_id,
                exposed_group_id=assessment.exposed_group_id,
                exposed_group=assessment.exposed_group,
                severity=assessment.severity,
                note=assessment.note,
                assessment_status=assessment.assessment_status,
                conclusion=assessment.conclusion,
                completed_at=assessment.completed_at,
                active=assessment.active,
                modified=assessment.modified,
            )
            session.add(db_assessment)
            session.flush()
            assessment_db_id = int(db_assessment.id)
            id_map[assessment.id] = assessment_db_id

        session.execute(
            delete(HazardRiskAssessmentExposedGroup).where(
                HazardRiskAssessmentExposedGroup.assessment_id == assessment_db_id,
            ),
        )
        for sort_order, group_id in enumerate(assessment.exposed_group_ids, start=1):
            session.add(
                HazardRiskAssessmentExposedGroup(
                    assessment_id=assessment_db_id,
                    exposed_group_id=group_id,
                    sort_order=sort_order,
                ),
            )

        for measure in assessment.existing_measures:
            self._commit_measure(
                session,
                measure,
                assessment_db_id,
                existing=True,
                id_map=id_map,
            )
        for measure in assessment.required_measures:
            self._commit_measure(
                session,
                measure,
                assessment_db_id,
                existing=False,
                id_map=id_map,
            )

    def _commit_measure(
        self,
        session,
        measure: IdWcMeasure,
        assessment_db_id: int,
        *,
        existing: bool,
        id_map: dict[int, int],
    ) -> None:
        model_cls = HazardExistingMeasure if existing else HazardRequiredMeasure
        if measure.id > 0:
            db_measure = session.get(model_cls, measure.id)
            if db_measure is None:
                return
            db_measure.hazard_risk_assessment_id = assessment_db_id
            db_measure.description = measure.description
            db_measure.note = measure.note
            db_measure.active = measure.active
            db_measure.modified = measure.modified
            db_measure.sort_order = measure.sort_order
            db_measure.updated_at = datetime.now()
            return
        db_measure = model_cls(
            hazard_risk_assessment_id=assessment_db_id,
            description=measure.description,
            note=measure.note,
            active=measure.active,
            modified=measure.modified,
            sort_order=measure.sort_order,
        )
        session.add(db_measure)
        session.flush()
        id_map[measure.id] = int(db_measure.id)

    def _commit_photos(self, session, identification: HazardIdentification) -> None:
        identification_number = identification.identification_number or str(identification.id)
        for photo in self.photos:
            if photo.staged_source_path:
                self._finalize_staged_photo(photo, identification_number)
            if photo.id > 0:
                db_photo = session.get(HazardIdentificationPhoto, photo.id)
                if db_photo is None:
                    continue
                db_photo.filename = photo.filename
                db_photo.stored_filename = photo.stored_filename
                db_photo.relative_path = photo.relative_path
                db_photo.caption = photo.caption
                db_photo.note = photo.note
                db_photo.taken_at = photo.taken_at
                db_photo.file_size = photo.file_size
                db_photo.width = photo.width
                db_photo.height = photo.height
                db_photo.active = photo.active
                db_photo.sort_order = photo.sort_order
                db_photo.updated_at = datetime.now()
                photo.staged_source_path = None
                continue
            session.add(
                HazardIdentificationPhoto(
                    hazard_identification_id=self.identification_id,
                    filename=photo.filename,
                    stored_filename=photo.stored_filename,
                    relative_path=photo.relative_path,
                    caption=photo.caption,
                    note=photo.note,
                    taken_at=photo.taken_at,
                    file_size=photo.file_size,
                    width=photo.width,
                    height=photo.height,
                    active=photo.active,
                    sort_order=photo.sort_order,
                ),
            )
            photo.staged_source_path = None

    def _finalize_staged_photo(self, photo: IdWcPhoto, identification_number: str) -> None:
        source = Path(photo.staged_source_path or "")
        if not source.is_file():
            raise HazardIdentificationPhotoError("Vybraný soubor neexistuje.")
        optimized = hazard_identification_photo_service._optimize(source)
        relative_dir = (
            Path("rizeni_rizik")
            / hazard_identification_photo_service._safe_folder_name(identification_number)
            / "fotografie"
        )
        stored_filename = (
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
        )
        relative_path = relative_dir / stored_filename
        absolute = storage_service.attachment_absolute(str(relative_path))
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_bytes(optimized.data)
        photo.filename = photo.filename or source.name
        photo.stored_filename = stored_filename
        photo.relative_path = str(relative_path).replace("\\", "/")
        photo.file_size = len(optimized.data)
        photo.width = optimized.width
        photo.height = optimized.height
        if photo.taken_at is None and optimized.taken_at is not None:
            photo.taken_at = optimized.taken_at


def find_identification_working_copy(widget) -> HazardIdentificationWorkingCopy | None:
    """Najde pracovní kopii na rodičovském editoru identifikace."""
    current = widget
    while current is not None:
        for attr in ("_identification_store", "_content_store"):
            store = getattr(current, attr, None)
            if isinstance(store, HazardIdentificationWorkingCopy):
                return store
        parent_fn = getattr(current, "parent", None)
        current = parent_fn() if callable(parent_fn) else None
    return None
