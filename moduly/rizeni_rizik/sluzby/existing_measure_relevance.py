"""Relevance zásady bezpečné práce vůči ohroženým skupinám / rolím posouzení."""

from __future__ import annotations

from sqlalchemy import delete, select

from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
    SOURCE_TYPE_HAZARD_GROUP,
    SOURCE_TYPE_ROLE,
    ExposedTargetRef,
)


EXISTING_MEASURE_RELEVANCE_REQUIRED = (
    "Vyberte alespoň jednu ohroženou skupinu nebo roli, pro kterou zásada platí."
)
EXISTING_MEASURE_RELEVANCE_NOT_IN_ASSESSMENT = (
    "Zásada může platit jen pro ohrožené skupiny nebo role tohoto posouzení."
)


def unique_refs(
    refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
) -> list[ExposedTargetRef]:
    unique: list[ExposedTargetRef] = []
    seen: set[tuple[str, int]] = set()
    for ref in refs or ():
        if ref.key in seen:
            continue
        seen.add(ref.key)
        unique.append(ref)
    return unique


def filter_refs_to_allowed(
    refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
    allowed: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
) -> list[ExposedTargetRef]:
    allowed_keys = {ref.key for ref in unique_refs(allowed)}
    return [ref for ref in unique_refs(refs) if ref.key in allowed_keys]


def default_refs_for_assessment(
    assessment_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
) -> list[ExposedTargetRef]:
    return unique_refs(assessment_refs)


def copy_relevance_refs(
    source_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
    assessment_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
) -> list[ExposedTargetRef]:
    """Zkopíruje relevanci; prázdný zdroj (starší data) → všechny skupiny posouzení."""
    allowed = unique_refs(assessment_refs)
    copied = filter_refs_to_allowed(source_refs, allowed)
    return copied if copied else list(allowed)


def apply_assessment_ref_changes(
    measure_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
    *,
    old_assessment_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
    new_assessment_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
) -> list[ExposedTargetRef]:
    """Při přidání skupiny ji doplní; při odebrání odstraní orphan vazby."""
    old_keys = {ref.key for ref in unique_refs(old_assessment_refs)}
    new_refs = unique_refs(new_assessment_refs)
    new_keys = {ref.key for ref in new_refs}
    kept = [ref for ref in unique_refs(measure_refs) if ref.key in new_keys]
    kept_keys = {ref.key for ref in kept}
    for ref in new_refs:
        if ref.key not in old_keys and ref.key not in kept_keys:
            kept.append(ref)
            kept_keys.add(ref.key)
    return kept


def validate_measure_refs(
    refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
    assessment_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
) -> list[ExposedTargetRef]:
    allowed = unique_refs(assessment_refs)
    selected = unique_refs(refs)
    if not allowed:
        return []
    selected = filter_refs_to_allowed(selected, allowed)
    if not selected:
        raise ValueError(EXISTING_MEASURE_RELEVANCE_REQUIRED)
    if len(selected) != len(unique_refs(refs)):
        raise ValueError(EXISTING_MEASURE_RELEVANCE_NOT_IN_ASSESSMENT)
    return selected


def resolve_create_refs(
    target_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
    assessment_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
) -> list[ExposedTargetRef]:
    allowed = unique_refs(assessment_refs)
    if target_refs is None:
        return default_refs_for_assessment(allowed)
    return validate_measure_refs(target_refs, allowed)


def refs_match_targets(
    refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
    *,
    role_ids: set[int],
    group_ids: set[int],
) -> bool:
    for ref in refs or ():
        if ref.source_type == SOURCE_TYPE_ROLE and ref.source_id in role_ids:
            return True
        if ref.source_type == SOURCE_TYPE_HAZARD_GROUP and ref.source_id in group_ids:
            return True
    return False


def rows_to_refs(rows) -> list[ExposedTargetRef]:
    refs: list[ExposedTargetRef] = []
    for source_type, source_id in rows:
        refs.append(
            ExposedTargetRef(
                str(source_type or SOURCE_TYPE_HAZARD_GROUP),
                int(source_id),
            )
        )
    return refs


def replace_refs_in_session(session, model, measure_id: int, refs: list[ExposedTargetRef]) -> None:
    session.execute(delete(model).where(model.measure_id == measure_id))
    for sort_order, ref in enumerate(unique_refs(refs), start=1):
        session.add(
            model(
                measure_id=measure_id,
                exposed_group_id=ref.source_id,
                source_type=ref.source_type,
                sort_order=sort_order,
            )
        )


def list_assessment_refs_in_session(session, model, assessment_id: int) -> list[ExposedTargetRef]:
    stmt = (
        select(model.source_type, model.exposed_group_id)
        .where(model.assessment_id == assessment_id)
        .order_by(model.sort_order, model.id)
    )
    return rows_to_refs(session.execute(stmt))


def attach_default_measure_relevance_in_session(
    session,
    measure_model,
    measure_id: int,
    assessment_refs: list[ExposedTargetRef] | tuple[ExposedTargetRef, ...] | None,
) -> None:
    replace_refs_in_session(
        session,
        measure_model,
        int(measure_id),
        default_refs_for_assessment(assessment_refs),
    )


def list_refs_in_session(session, model, measure_id: int) -> list[ExposedTargetRef]:
    stmt = (
        select(model.source_type, model.exposed_group_id)
        .where(model.measure_id == measure_id)
        .order_by(model.sort_order, model.id)
    )
    return rows_to_refs(session.execute(stmt))


def list_refs_for_measures_in_session(
    session,
    model,
    measure_ids: list[int],
) -> dict[int, list[ExposedTargetRef]]:
    result: dict[int, list[ExposedTargetRef]] = {int(measure_id): [] for measure_id in measure_ids}
    if not measure_ids:
        return result
    stmt = (
        select(model.measure_id, model.source_type, model.exposed_group_id)
        .where(model.measure_id.in_(measure_ids))
        .order_by(model.measure_id, model.sort_order, model.id)
    )
    for measure_id, source_type, source_id in session.execute(stmt):
        result.setdefault(int(measure_id), []).append(
            ExposedTargetRef(
                str(source_type or SOURCE_TYPE_HAZARD_GROUP),
                int(source_id),
            )
        )
    return result
