"""Otevírání konkrétních položek z Analýzy podobností (DATA-QUALITY-UX-1)."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from core.shared.sluzby.similarity_checked_pair_service import (
    SIMILARITY_ENTITY_AUDIT_ASSERTION,
    SIMILARITY_ENTITY_LEGAL_REQUIREMENT,
    SIMILARITY_ENTITY_MEASURE,
    SIMILARITY_ENTITY_PBP,
    SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
    SIMILARITY_ENTITY_RISK,
)
from core.shared.sluzby.similarity_item_collectors import SimilarityItem
from core.widgets.dialog_utils import exec_maximized


class SimilarityItemOpenError(Exception):
    """Položku nelze otevřít — zpráva je určena uživateli."""


_KNOWN_ENTITY_TYPES = (
    SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
    SIMILARITY_ENTITY_AUDIT_ASSERTION,
    SIMILARITY_ENTITY_LEGAL_REQUIREMENT,
    SIMILARITY_ENTITY_RISK,
    SIMILARITY_ENTITY_MEASURE,
    SIMILARITY_ENTITY_PBP,
)


def resolve_item_identity(item: SimilarityItem) -> tuple[str, str]:
    """Vrátí (entity_type, composite_id bez případného type prefixu z cross-domain)."""
    entity_type = str(getattr(item, "entity_type", "") or "").strip()
    composite_id = str(getattr(item, "composite_id", "") or "").strip()

    # Zpětná kompatibilita se staršími kandidáty kontrolních otázek.
    if not entity_type and hasattr(item, "area_id") and hasattr(item, "section_id"):
        entity_type = SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT

    if not entity_type:
        raise SimilarityItemOpenError("Položka nemá typ entity — nelze ji otevřít.")
    if not composite_id:
        raise SimilarityItemOpenError("Položka nemá identifikátor — nelze ji otevřít.")

    typed_prefix = f"{entity_type}::"
    if composite_id.startswith(typed_prefix):
        return entity_type, composite_id[len(typed_prefix) :]

    # Cross-domain storage může mít prefix i při chybějící shodě s entity_type.
    for known in _KNOWN_ENTITY_TYPES:
        prefix = f"{known}::"
        if composite_id.startswith(prefix):
            return known, composite_id[len(prefix) :]
    return entity_type, composite_id


def open_similarity_item(parent: QWidget | None, item) -> None:
    """Otevře editor odpovídající typu položky (modální)."""
    entity_type, composite_id = resolve_item_identity(item)
    opener = _OPENERS.get(entity_type)
    if opener is None:
        raise SimilarityItemOpenError(
            f"Pro oblast „{entity_type}“ není v aplikaci dostupný editor záznamu."
        )
    opener(parent, composite_id)


def _open_proverky(parent: QWidget | None, composite_id: str) -> None:
    from moduly.proverky.sluzby.control_point_similarity_service import (
        parse_control_point_composite_id,
    )
    from moduly.proverky.ui.proverky_knowledge_editor_dialog import (
        ProverkyKnowledgeEditorDialog,
    )

    parsed = parse_control_point_composite_id(composite_id)
    if parsed is None:
        raise SimilarityItemOpenError(
            "Kontrolní otázku nelze otevřít — neplatný identifikátor."
        )
    area_id, section_id, item_id = parsed
    dialog = ProverkyKnowledgeEditorDialog(
        parent,
        area_id=area_id,
        section_id=section_id,
        control_point_id=item_id,
    )
    exec_maximized(dialog)


def _open_audit(parent: QWidget | None, composite_id: str) -> None:
    from moduly.audity.ui.audity_knowledge_editor_dialog import (
        AudityKnowledgeEditorDialog,
    )

    parts = [part.strip() for part in composite_id.split("::")]
    if len(parts) != 3 or not all(parts):
        raise SimilarityItemOpenError(
            "Auditní tvrzení nelze otevřít — neplatný identifikátor."
        )
    process_id, criterion_id, _assertion_id = parts
    dialog = AudityKnowledgeEditorDialog(
        parent,
        process_id=process_id,
        criterion_id=criterion_id,
    )
    exec_maximized(dialog)


def _open_legal(parent: QWidget | None, composite_id: str) -> None:
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
        legal_requirement_service,
    )
    from moduly.pravni_pozadavky.ui.legal_requirement_dialog import (
        LegalRequirementDialog,
    )

    try:
        requirement_id = int(composite_id)
    except (TypeError, ValueError) as error:
        raise SimilarityItemOpenError(
            "Právní požadavek nelze otevřít — neplatný identifikátor."
        ) from error
    requirement = legal_requirement_service.get_by_id(requirement_id)
    if requirement is None:
        raise SimilarityItemOpenError(
            "Právní požadavek nebyl nalezen — možná byl smazán."
        )
    dialog = LegalRequirementDialog(parent, requirement=requirement)
    exec_maximized(dialog)


def _identification_id_for_event(event) -> int:
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )

    inventory_item = hazard_inventory_item_service.get_by_id(event.inventory_item_id)
    if inventory_item is None:
        raise SimilarityItemOpenError(
            "Událost rizika nelze otevřít — chybí zdroj rizika."
        )
    return int(inventory_item.hazard_identification_id)


def _identification_id_for_assessment(assessment_id: int) -> int:
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )

    assessment = hazard_risk_assessment_service.get_by_id(assessment_id)
    if assessment is None:
        raise SimilarityItemOpenError(
            "Opatření nelze otevřít — hodnocení rizika nebylo nalezeno."
        )
    event = hazard_event_service.get_by_id(assessment.hazard_event_id)
    if event is None:
        raise SimilarityItemOpenError(
            "Opatření nelze otevřít — událost rizika nebyla nalezena."
        )
    return _identification_id_for_event(event)


def _open_risk(parent: QWidget | None, composite_id: str) -> None:
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.ui.hazard_event_dialog import HazardEventDialog

    try:
        event_id = int(composite_id)
    except (TypeError, ValueError) as error:
        raise SimilarityItemOpenError(
            "Riziko nelze otevřít — neplatný identifikátor."
        ) from error
    event = hazard_event_service.get_by_id(event_id)
    if event is None:
        raise SimilarityItemOpenError("Událost rizika nebyla nalezena — možná byla smazána.")
    dialog = HazardEventDialog(
        parent,
        hazard_identification_id=_identification_id_for_event(event),
        event=event,
    )
    exec_maximized(dialog)


def _open_existing_measure(parent: QWidget | None, measure_id: int) -> None:
    from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
        hazard_existing_measure_service,
    )
    from moduly.rizeni_rizik.ui.hazard_existing_measure_dialog import (
        HazardExistingMeasureDialog,
    )

    measure = hazard_existing_measure_service.get_by_id(measure_id)
    if measure is None:
        raise SimilarityItemOpenError(
            "Stávající opatření nebylo nalezeno — možná bylo smazáno."
        )
    assessment_id = int(measure.hazard_risk_assessment_id)
    dialog = HazardExistingMeasureDialog(
        parent,
        hazard_identification_id=_identification_id_for_assessment(assessment_id),
        hazard_risk_assessment_id=assessment_id,
        measure=measure,
    )
    exec_maximized(dialog)


def _open_required_measure(parent: QWidget | None, measure_id: int) -> None:
    from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
        hazard_required_measure_service,
    )
    from moduly.rizeni_rizik.ui.hazard_required_measure_dialog import (
        HazardRequiredMeasureDialog,
    )

    measure = hazard_required_measure_service.get_by_id(measure_id)
    if measure is None:
        raise SimilarityItemOpenError(
            "Požadované opatření nebylo nalezeno — možná bylo smazáno."
        )
    assessment_id = int(measure.hazard_risk_assessment_id)
    dialog = HazardRequiredMeasureDialog(
        parent,
        hazard_identification_id=_identification_id_for_assessment(assessment_id),
        hazard_risk_assessment_id=assessment_id,
        measure=measure,
    )
    exec_maximized(dialog)


def _open_measure(parent: QWidget | None, composite_id: str) -> None:
    if composite_id.startswith("existing:"):
        raw = composite_id.split(":", 1)[1]
        try:
            measure_id = int(raw)
        except (TypeError, ValueError) as error:
            raise SimilarityItemOpenError(
                "Opatření nelze otevřít — neplatný identifikátor."
            ) from error
        _open_existing_measure(parent, measure_id)
        return
    if composite_id.startswith("required:"):
        raw = composite_id.split(":", 1)[1]
        try:
            measure_id = int(raw)
        except (TypeError, ValueError) as error:
            raise SimilarityItemOpenError(
                "Opatření nelze otevřít — neplatný identifikátor."
            ) from error
        _open_required_measure(parent, measure_id)
        return
    raise SimilarityItemOpenError(
        "Opatření nelze otevřít — neočekávaný formát identifikátoru."
    )


def _open_pbp(parent: QWidget | None, composite_id: str) -> None:
    try:
        measure_id = int(composite_id)
    except (TypeError, ValueError) as error:
        raise SimilarityItemOpenError(
            "Pravidlo bezpečné práce nelze otevřít — neplatný identifikátor."
        ) from error
    _open_existing_measure(parent, measure_id)


_OPENERS = {
    SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT: _open_proverky,
    SIMILARITY_ENTITY_AUDIT_ASSERTION: _open_audit,
    SIMILARITY_ENTITY_LEGAL_REQUIREMENT: _open_legal,
    SIMILARITY_ENTITY_RISK: _open_risk,
    SIMILARITY_ENTITY_MEASURE: _open_measure,
    SIMILARITY_ENTITY_PBP: _open_pbp,
}
