"""Obecná položka a sběr kandidátů pro Analýzu podobností (SIMILARITY-10)."""

from __future__ import annotations

from dataclasses import dataclass

from core.shared.sluzby.similarity_checked_pair_service import (
    SIMILARITY_ENTITY_AUDIT_ASSERTION,
    SIMILARITY_ENTITY_LEGAL_REQUIREMENT,
    SIMILARITY_ENTITY_MEASURE,
    SIMILARITY_ENTITY_PBP,
    SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
    SIMILARITY_ENTITY_RISK,
)
from core.shared.sluzby.similarity_domain import (
    SCOPE_AUDIT,
    SCOPE_LEGAL,
    SCOPE_MEASURES,
    SCOPE_PBP,
    SCOPE_PROVERKY,
    SCOPE_RISKS,
)


@dataclass(frozen=True)
class SimilarityItem:
    """Obecný kandidát podobnosti (text + umístění + typ entity)."""

    entity_type: str
    composite_id: str
    text: str
    location_label: str


def collect_similarity_items(
    scope_key: str,
    *,
    include_inactive: bool = True,
) -> list[SimilarityItem]:
    """Vrátí položky dané oblasti. Neznámý klíč → ValueError."""
    collectors = {
        SCOPE_PROVERKY: _collect_proverky,
        SCOPE_PBP: _collect_pbp,
        SCOPE_AUDIT: _collect_audit,
        SCOPE_RISKS: _collect_risks,
        SCOPE_MEASURES: _collect_measures,
        SCOPE_LEGAL: _collect_legal,
    }
    collector = collectors.get(scope_key)
    if collector is None:
        raise ValueError(f"Neznámá oblast podobností: {scope_key}")
    return collector(include_inactive=include_inactive)


def _collect_proverky(*, include_inactive: bool = True) -> list[SimilarityItem]:
    from moduly.proverky.sluzby.control_point_similarity_service import (
        collect_control_point_candidates,
    )

    return [
        SimilarityItem(
            entity_type=SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
            composite_id=item.composite_id,
            text=item.text,
            location_label=item.location_label,
        )
        for item in collect_control_point_candidates(include_inactive=include_inactive)
    ]


def _collect_audit(*, include_inactive: bool = True) -> list[SimilarityItem]:
    from moduly.audity.constants import MODULE_NAME
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service

    results: list[SimilarityItem] = []
    for process in audit_knowledge_service.get_processes(include_inactive=True):
        if not process.has_knowledge_file:
            continue
        criteria = audit_knowledge_service.list_criteria(
            process.id,
            include_inactive=include_inactive,
        )
        for criterion in criteria:
            if not isinstance(criterion, dict):
                continue
            criterion_id = str(criterion.get("id") or "").strip()
            criterion_name = (
                str(criterion.get("nazev") or criterion_id).strip() or criterion_id
            )
            if not criterion_id:
                continue
            raw_items = criterion.get("auditni_tvrzeni") or []
            items = audit_knowledge_service.normalize_auditni_tvrzeni(list(raw_items))
            for raw in items:
                if not include_inactive and not raw.get("aktivni", True):
                    continue
                item_id = str(raw.get("id") or "").strip()
                text = str(raw.get("text") or raw.get("nazev") or "").strip()
                if not item_id or not text:
                    continue
                results.append(
                    SimilarityItem(
                        entity_type=SIMILARITY_ENTITY_AUDIT_ASSERTION,
                        composite_id=f"{process.id}::{criterion_id}::{item_id}",
                        text=text,
                        location_label=(
                            f"{MODULE_NAME} → {process.nazev} → {criterion_name}"
                        ),
                    )
                )
    return results


def _collect_legal(*, include_inactive: bool = True) -> list[SimilarityItem]:
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
        legal_requirement_service,
    )

    module_name = "Právní požadavky"
    active_only = None if include_inactive else True
    results: list[SimilarityItem] = []
    for req in legal_requirement_service.get_all(active_only=active_only):
        text = str(req.requirement_summary or "").strip()
        if not text:
            text = str(req.title or "").strip()
        if not text:
            continue
        title = str(req.title or "").strip() or f"#{req.id}"
        process = str(req.process_code or "").strip()
        location = f"{module_name} → {process}" if process else module_name
        location = f"{location} → {title}"
        results.append(
            SimilarityItem(
                entity_type=SIMILARITY_ENTITY_LEGAL_REQUIREMENT,
                composite_id=str(req.id),
                text=text,
                location_label=location,
            )
        )
    return results


def _collect_risks(*, include_inactive: bool = True) -> list[SimilarityItem]:
    from moduly.rizeni_rizik.constants import MODULE_NAME
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )

    results: list[SimilarityItem] = []
    for identification in hazard_identification_service.get_all(
        include_inactive=include_inactive
    ):
        ident_label = (
            str(getattr(identification, "identification_number", "") or "").strip()
            or str(identification.id)
        )
        for row in hazard_event_service.get_for_identification(
            identification.id,
            include_inactive=include_inactive,
        ):
            event = row.event
            text = str(event.name or "").strip()
            if not text:
                continue
            source = str(row.inventory_item_name or "").strip()
            location = f"{MODULE_NAME} → {ident_label}"
            if source:
                location = f"{location} → {source}"
            results.append(
                SimilarityItem(
                    entity_type=SIMILARITY_ENTITY_RISK,
                    composite_id=str(event.id),
                    text=text,
                    location_label=location,
                )
            )
    return results


def _collect_measures(*, include_inactive: bool = True) -> list[SimilarityItem]:
    from moduly.rizeni_rizik.constants import MODULE_NAME
    from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
        hazard_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
        hazard_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )

    results: list[SimilarityItem] = []
    for identification in hazard_identification_service.get_all(
        include_inactive=include_inactive
    ):
        ident_label = (
            str(getattr(identification, "identification_number", "") or "").strip()
            or str(identification.id)
        )
        for row in hazard_risk_assessment_service.get_for_identification(
            identification.id,
            include_inactive=include_inactive,
        ):
            event_name = str(getattr(row, "event_name", "") or "").strip()
            base_loc = f"{MODULE_NAME} → {ident_label}"
            if event_name:
                base_loc = f"{base_loc} → {event_name}"

            for measure in hazard_existing_measure_service.get_for_assessment(
                row.assessment.id,
                include_inactive=include_inactive,
            ):
                text = str(measure.description or "").strip()
                if not text:
                    continue
                results.append(
                    SimilarityItem(
                        entity_type=SIMILARITY_ENTITY_MEASURE,
                        composite_id=f"existing:{measure.id}",
                        text=text,
                        location_label=f"{base_loc} → stávající opatření",
                    )
                )

            for measure in hazard_required_measure_service.get_for_assessment(
                row.assessment.id,
                include_inactive=include_inactive,
            ):
                text = str(measure.display_title() or "").strip()
                if not text:
                    text = str(measure.description or "").strip()
                if not text:
                    continue
                results.append(
                    SimilarityItem(
                        entity_type=SIMILARITY_ENTITY_MEASURE,
                        composite_id=f"required:{measure.id}",
                        text=text,
                        location_label=f"{base_loc} → požadované opatření",
                    )
                )
    return results


def _collect_pbp(*, include_inactive: bool = True) -> list[SimilarityItem]:
    """Texty stávajících opatření ve tvaru PBP (normalize_rule_text)."""
    from moduly.rizeni_rizik.constants import MODULE_NAME
    from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
        hazard_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
        normalize_rule_text,
    )

    results: list[SimilarityItem] = []
    seen_texts: set[str] = set()
    for identification in hazard_identification_service.get_all(
        include_inactive=include_inactive
    ):
        ident_label = (
            str(getattr(identification, "identification_number", "") or "").strip()
            or str(identification.id)
        )
        for row in hazard_risk_assessment_service.get_for_identification(
            identification.id,
            include_inactive=False if not include_inactive else include_inactive,
        ):
            for measure in hazard_existing_measure_service.get_for_assessment(
                row.assessment.id,
                include_inactive=include_inactive,
            ):
                text = normalize_rule_text(measure.description or "")
                if not text:
                    continue
                key = text.casefold()
                if key in seen_texts:
                    continue
                seen_texts.add(key)
                results.append(
                    SimilarityItem(
                        entity_type=SIMILARITY_ENTITY_PBP,
                        composite_id=str(measure.id),
                        text=text,
                        location_label=f"{MODULE_NAME} → PBP → {ident_label}",
                    )
                )
    return results
