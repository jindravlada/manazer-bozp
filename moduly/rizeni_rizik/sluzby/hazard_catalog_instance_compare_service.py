"""Porovnání lokální instance z katalogu s aktuálním Master zdrojem (R18d)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
from moduly.rizeni_rizik.constants_library import (
    CATALOG_COMPARE_KIND_ADDED,
    CATALOG_COMPARE_KIND_CHANGED,
    CATALOG_COMPARE_KIND_REMOVED,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_instance_modification import (
    inventory_item_is_catalog_instance,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
    hazard_existing_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
    hazard_inventory_item_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
    hazard_library_template_assessment_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
    hazard_library_template_event_service,
    normalize_template_event_name,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
    hazard_library_template_existing_measure_service,
    normalize_template_measure_description,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
    hazard_library_template_required_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
    hazard_library_template_service,
)
from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
    hazard_required_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    hazard_risk_assessment_service,
)


class HazardCatalogInstanceCompareError(ValueError):
    pass


@dataclass(frozen=True)
class CatalogCompareLine:
    kind: str
    label: str
    detail: str = ""


@dataclass
class CatalogInstanceCompareResult:
    inventory_item_id: int
    inventory_item_name: str
    template_id: int
    template_name: str
    source_template_version: int | None
    master_version: int | None
    lines: list[CatalogCompareLine] = field(default_factory=list)

    @property
    def has_differences(self) -> bool:
        return bool(self.lines)

    @property
    def master_version_differs(self) -> bool:
        if self.source_template_version is None or self.master_version is None:
            return False
        return self.master_version != self.source_template_version


class HazardCatalogInstanceCompareService:
    def compare(self, inventory_item_id: int) -> CatalogInstanceCompareResult:
        item = hazard_inventory_item_service.get_by_id(inventory_item_id)
        if item is None:
            raise HazardCatalogInstanceCompareError("Položka analýzy neexistuje.")
        if not inventory_item_is_catalog_instance(item.id):
            raise HazardCatalogInstanceCompareError(
                "Porovnání s Masterem je dostupné pouze u zdroje převzatého z katalogu."
            )
        if item.source_template_id is None:
            raise HazardCatalogInstanceCompareError(
                "Položka nemá evidovaný původ z katalogu zdrojů rizik."
            )

        template = hazard_library_template_service.get_by_id(item.source_template_id)
        if template is None:
            raise HazardCatalogInstanceCompareError("Master zdroj rizika již neexistuje.")

        result = CatalogInstanceCompareResult(
            inventory_item_id=item.id,
            inventory_item_name=item.name,
            template_id=template.id,
            template_name=template.name,
            source_template_version=item.source_template_version,
            master_version=template.version_number,
        )
        self._compare_source_header(item, template, result)
        self._compare_events(item.id, template.id, result)
        return result

    def format_lines(self, result: CatalogInstanceCompareResult) -> list[str]:
        return [self.format_line(line) for line in result.lines]

    def format_line(self, line: CatalogCompareLine) -> str:
        if line.detail:
            return f"{line.kind} {line.label} ({line.detail})"
        return f"{line.kind} {line.label}"

    def _compare_source_header(self, item, template, result: CatalogInstanceCompareResult) -> None:
        changes = self._changed_field_details(
            [
                ("název", template.name, item.name),
                ("popis", template.description, item.description),
            ]
        )
        if changes:
            result.lines.append(
                CatalogCompareLine(
                    kind=CATALOG_COMPARE_KIND_CHANGED,
                    label="Zdroj analýzy",
                    detail=changes,
                )
            )

    def _compare_events(
        self,
        inventory_item_id: int,
        template_id: int,
        result: CatalogInstanceCompareResult,
    ) -> None:
        master_events = hazard_library_template_event_service.get_for_template(
            template_id,
            include_inactive=True,
        )
        local_events = hazard_event_service.get_for_inventory_item(
            inventory_item_id,
            include_inactive=True,
        )

        pairs, master_unmatched, local_unmatched = self._match_by_key(
            master_events,
            local_events,
            key_fn=lambda event: normalize_template_event_name(event.name),
            sort_key=lambda event: event.sort_order,
        )

        for master_event, local_event in pairs:
            event_label = f"Událost: {local_event.name}"
            if not local_event.active and master_event.active:
                result.lines.append(
                    CatalogCompareLine(
                        kind=CATALOG_COMPARE_KIND_REMOVED,
                        label=event_label,
                    )
                )
                continue

            changes = self._changed_field_details(
                [
                    ("název", master_event.name, local_event.name),
                    ("popis", master_event.description, local_event.description),
                    ("poznámka", master_event.note, local_event.note),
                ]
            )
            if changes:
                result.lines.append(
                    CatalogCompareLine(
                        kind=CATALOG_COMPARE_KIND_CHANGED,
                        label=event_label,
                        detail=changes,
                    )
                )

            self._compare_assessments(master_event, local_event, result)

        for master_event in master_unmatched:
            result.lines.append(
                CatalogCompareLine(
                    kind=CATALOG_COMPARE_KIND_REMOVED,
                    label=f"Událost: {master_event.name}",
                )
            )
        for local_event in local_unmatched:
            result.lines.append(
                CatalogCompareLine(
                    kind=CATALOG_COMPARE_KIND_ADDED,
                    label=f"Událost: {local_event.name}",
                )
            )

    def _compare_assessments(self, master_event, local_event, result: CatalogInstanceCompareResult) -> None:
        master_assessments = hazard_library_template_assessment_service.repository.get_for_event(
            master_event.id,
            include_inactive=True,
        )
        local_assessments = hazard_risk_assessment_service.repository.get_for_event(
            local_event.id,
            include_inactive=True,
        )

        pairs, master_unmatched, local_unmatched = self._match_by_key(
            master_assessments,
            local_assessments,
            key_fn=lambda assessment: str(assessment.exposed_group_id or ""),
            sort_key=lambda assessment: assessment.id or 0,
        )

        event_label = local_event.name
        for master_assessment, local_assessment in pairs:
            group_name = self._assessment_group_label(local_assessment)
            label = f"Událost: {event_label} / Posouzení: {group_name}"
            if not local_assessment.active and master_assessment.active:
                result.lines.append(
                    CatalogCompareLine(kind=CATALOG_COMPARE_KIND_REMOVED, label=label)
                )
                continue

            changes = self._changed_field_details(
                [
                    ("závažnost", master_assessment.severity, local_assessment.severity),
                    ("poznámka", master_assessment.note, local_assessment.note),
                    ("závěr", master_assessment.conclusion, local_assessment.conclusion),
                ]
            )
            if changes:
                result.lines.append(
                    CatalogCompareLine(
                        kind=CATALOG_COMPARE_KIND_CHANGED,
                        label=label,
                        detail=changes,
                    )
                )

            self._compare_measures(
                event_label=event_label,
                group_name=group_name,
                result=result,
                measure_kind="Existující opatření",
                master_measures=hazard_library_template_existing_measure_service.get_for_assessment(
                    master_assessment.id,
                    include_inactive=True,
                ),
                local_measures=hazard_existing_measure_service.get_for_assessment(
                    local_assessment.id,
                    include_inactive=True,
                ),
                normalize_description=normalize_template_measure_description,
            )
            self._compare_measures(
                event_label=event_label,
                group_name=group_name,
                result=result,
                measure_kind="Potřebné opatření",
                master_measures=hazard_library_template_required_measure_service.get_for_assessment(
                    master_assessment.id,
                    include_inactive=True,
                ),
                local_measures=hazard_required_measure_service.get_for_assessment(
                    local_assessment.id,
                    include_inactive=True,
                ),
                normalize_description=normalize_template_measure_description,
            )

        for master_assessment in master_unmatched:
            group_name = self._assessment_group_label(master_assessment)
            result.lines.append(
                CatalogCompareLine(
                    kind=CATALOG_COMPARE_KIND_REMOVED,
                    label=f"Událost: {event_label} / Posouzení: {group_name}",
                )
            )
        for local_assessment in local_unmatched:
            group_name = self._assessment_group_label(local_assessment)
            result.lines.append(
                CatalogCompareLine(
                    kind=CATALOG_COMPARE_KIND_ADDED,
                    label=f"Událost: {event_label} / Posouzení: {group_name}",
                )
            )

    def _compare_measures(
        self,
        *,
        event_label: str,
        group_name: str,
        result: CatalogInstanceCompareResult,
        measure_kind: str,
        master_measures,
        local_measures,
        normalize_description,
    ) -> None:
        pairs, master_unmatched, local_unmatched = self._match_by_key(
            master_measures,
            local_measures,
            key_fn=lambda measure: normalize_description(measure.description),
            sort_key=lambda measure: measure.sort_order,
        )

        for master_measure, local_measure in pairs:
            label = (
                f"Událost: {event_label} / Posouzení: {group_name} / "
                f"{measure_kind}: {local_measure.description}"
            )
            if not local_measure.active and master_measure.active:
                result.lines.append(
                    CatalogCompareLine(kind=CATALOG_COMPARE_KIND_REMOVED, label=label)
                )
                continue

            changes = self._changed_field_details(
                [
                    ("popis", master_measure.description, local_measure.description),
                    ("poznámka", master_measure.note, local_measure.note),
                ]
            )
            if changes:
                result.lines.append(
                    CatalogCompareLine(
                        kind=CATALOG_COMPARE_KIND_CHANGED,
                        label=label,
                        detail=changes,
                    )
                )

        for master_measure in master_unmatched:
            result.lines.append(
                CatalogCompareLine(
                    kind=CATALOG_COMPARE_KIND_REMOVED,
                    label=(
                        f"Událost: {event_label} / Posouzení: {group_name} / "
                        f"{measure_kind}: {master_measure.description}"
                    ),
                )
            )
        for local_measure in local_unmatched:
            result.lines.append(
                CatalogCompareLine(
                    kind=CATALOG_COMPARE_KIND_ADDED,
                    label=(
                        f"Událost: {event_label} / Posouzení: {group_name} / "
                        f"{measure_kind}: {local_measure.description}"
                    ),
                )
            )

    def _match_by_key(self, master_items, local_items, *, key_fn, sort_key):
        master_groups: dict[str, list] = defaultdict(list)
        local_groups: dict[str, list] = defaultdict(list)
        for item in master_items:
            master_groups[key_fn(item)].append(item)
        for item in local_items:
            local_groups[key_fn(item)].append(item)

        pairs: list[tuple] = []
        master_unmatched = []
        local_unmatched = []
        all_keys = set(master_groups) | set(local_groups)
        for key in all_keys:
            master_list = sorted(master_groups.get(key, []), key=sort_key)
            local_list = sorted(local_groups.get(key, []), key=sort_key)
            for master_item, local_item in zip(master_list, local_list):
                pairs.append((master_item, local_item))
            master_unmatched.extend(master_list[len(local_list) :])
            local_unmatched.extend(local_list[len(master_list) :])
        return pairs, master_unmatched, local_unmatched

    def _assessment_group_label(self, assessment) -> str:
        if assessment.exposed_group_id:
            name = exposed_group_service.display_name(assessment.exposed_group_id)
            if name:
                return name
        if getattr(assessment, "exposed_group", ""):
            return assessment.exposed_group
        return "—"

    def _changed_field_details(self, fields: list[tuple[str, str, str]]) -> str:
        parts: list[str] = []
        for label, master_value, local_value in fields:
            master_text = self._normalize_text(master_value)
            local_text = self._normalize_text(local_value)
            if master_text != local_text:
                parts.append(f"{label}: „{master_text or '—'}“ → „{local_text or '—'}“")
        return "; ".join(parts)

    def _normalize_text(self, value: str | None) -> str:
        return " ".join((value or "").strip().split())


hazard_catalog_instance_compare_service = HazardCatalogInstanceCompareService()
