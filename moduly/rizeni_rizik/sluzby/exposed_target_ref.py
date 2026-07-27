"""Polymorfní odkaz na ohroženou skupinu / funkci-roli (RISK-UX-6)."""

from __future__ import annotations

from dataclasses import dataclass

SOURCE_TYPE_ROLE = "role"
SOURCE_TYPE_HAZARD_GROUP = "hazard_group"

EXPOSED_TARGET_SOURCE_TYPES = frozenset({SOURCE_TYPE_ROLE, SOURCE_TYPE_HAZARD_GROUP})

SECTION_LABEL_ROLES = "Funkce / role"
SECTION_LABEL_HAZARD_GROUPS = "Ostatní ohrožené skupiny"


@dataclass(frozen=True)
class ExposedTargetRef:
    """Vazba na položku číselníku – ne textový název."""

    source_type: str
    source_id: int

    def __post_init__(self) -> None:
        if self.source_type not in EXPOSED_TARGET_SOURCE_TYPES:
            raise ValueError(f"Neplatný source_type: {self.source_type}")
        object.__setattr__(self, "source_id", int(self.source_id))

    @property
    def key(self) -> tuple[str, int]:
        return (self.source_type, self.source_id)


def hazard_group_ref(group_id: int) -> ExposedTargetRef:
    return ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, int(group_id))


def role_ref(role_id: int) -> ExposedTargetRef:
    return ExposedTargetRef(SOURCE_TYPE_ROLE, int(role_id))


def refs_from_legacy_group_ids(
    group_ids: list[int] | tuple[int, ...] | None,
    *,
    legacy_single_id: int | None = None,
) -> list[ExposedTargetRef]:
    values = list(group_ids or [])
    if not values and legacy_single_id is not None:
        values = [legacy_single_id]
    refs: list[ExposedTargetRef] = []
    seen: set[tuple[str, int]] = set()
    for group_id in values:
        ref = hazard_group_ref(group_id)
        if ref.key in seen:
            continue
        seen.add(ref.key)
        refs.append(ref)
    return refs


def legacy_exposed_group_id(refs: list[ExposedTargetRef]) -> int | None:
    """Pro sloupec hazard_risk_assessments.exposed_group_id – jen hazard_group."""
    for ref in refs:
        if ref.source_type == SOURCE_TYPE_HAZARD_GROUP:
            return ref.source_id
    return None


def resolve_exposed_target_display_name(ref: ExposedTargetRef) -> str:
    if ref.source_type == SOURCE_TYPE_ROLE:
        from moduly.nastaveni.sluzby.responsibility_role_service import (
            responsibility_role_service,
        )

        return responsibility_role_service.display_name(ref.source_id) or f"#{ref.source_id}"
    from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service

    return exposed_group_service.display_name(ref.source_id) or f"#{ref.source_id}"


def format_exposed_target_names(refs: list[ExposedTargetRef]) -> str:
    names = [resolve_exposed_target_display_name(ref) for ref in refs]
    return ", ".join(names) if names else ""
