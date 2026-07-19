"""Životní cyklus koordinace BOZP (UX-COORD-6a)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from moduly.koordinace_bozp.constants import (
    BOZP_COORDINATION_LIFECYCLE_ACTIONS,
    BOZP_COORDINATION_STATUS_ARCHIVED,
    BOZP_COORDINATION_STATUS_COMPLETED,
    BOZP_COORDINATION_STATUS_DRAFT,
    BOZP_COORDINATION_STATUS_ISSUED,
    BOZP_COORDINATION_STATUS_LABELS,
    BOZP_COORDINATION_STATUS_LEGACY_MAP,
    BOZP_COORDINATION_STATUS_READY,
    BOZP_COORDINATION_STATUS_TRANSITIONS,
    BOZP_COORDINATION_STATUSES,
    BOZP_COORDINATION_STATUSES_REQUIRING_PROTOCOL_CHECK,
    DEFAULT_BOZP_COORDINATION_STATUS,
    PROTOCOL_WARNING_SEVERITY_CRITICAL,
    PROTOCOL_WARNING_SEVERITY_WARNING,
)
from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
    bozp_coordination_service,
)
from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
    ProtocolWarning,
    coordination_protocol_builder,
)


class CoordinationLifecycleError(ValueError):
    pass


class CoordinationLifecycleBlocked(CoordinationLifecycleError):
    """Přechod zablokován critical warnings."""

    def __init__(self, message: str, warnings: list[ProtocolWarning]):
        super().__init__(message)
        self.warnings = list(warnings)


class CoordinationLifecycleNeedsConfirmation(CoordinationLifecycleError):
    """Přechod vyžaduje potvrzení (warning nebo citlivý návrat)."""

    def __init__(
        self,
        message: str,
        *,
        warnings: list[ProtocolWarning] | None = None,
        sensitive: bool = False,
    ):
        super().__init__(message)
        self.warnings = list(warnings or [])
        self.sensitive = sensitive


@dataclass(frozen=True)
class LifecycleAction:
    action_id: str
    target_status: str
    label: str
    requires_sensitive_confirm: bool


def normalize_coordination_status(value: str | None) -> str:
    """Převede legacy / neznámý status na kanonickou hodnotu."""
    raw = (value or "").strip().lower()
    if raw in BOZP_COORDINATION_STATUSES:
        return raw
    mapped = BOZP_COORDINATION_STATUS_LEGACY_MAP.get(raw)
    if mapped:
        return mapped
    return DEFAULT_BOZP_COORDINATION_STATUS


def status_label(status: str | None) -> str:
    normalized = normalize_coordination_status(status)
    return BOZP_COORDINATION_STATUS_LABELS.get(normalized, normalized)


class CoordinationLifecycleService:
    def list_actions(self, status: str | None) -> list[LifecycleAction]:
        current = normalize_coordination_status(status)
        actions: list[LifecycleAction] = []
        for from_status, to_status, action_id, label, sensitive in (
            BOZP_COORDINATION_LIFECYCLE_ACTIONS
        ):
            if from_status != current:
                continue
            actions.append(
                LifecycleAction(
                    action_id=action_id,
                    target_status=to_status,
                    label=label,
                    requires_sensitive_confirm=sensitive,
                )
            )
        return actions

    def can_transition(self, from_status: str | None, to_status: str) -> bool:
        current = normalize_coordination_status(from_status)
        target = normalize_coordination_status(to_status)
        allowed = BOZP_COORDINATION_STATUS_TRANSITIONS.get(current, frozenset())
        return target in allowed

    def transition(
        self,
        coordination_id: int,
        target_status: str,
        *,
        confirm_warnings: bool = False,
        confirm_sensitive: bool = False,
    ) -> BozpCoordination:
        coordination = bozp_coordination_service.get_by_id(coordination_id)
        if coordination is None:
            raise CoordinationLifecycleError("Koordinace nebyla nalezena.")

        current = normalize_coordination_status(coordination.status)
        target = normalize_coordination_status(target_status)
        if current == target:
            return coordination
        if not self.can_transition(current, target):
            raise CoordinationLifecycleError(
                f"Přechod ze stavu „{status_label(current)}“ "
                f"do „{status_label(target)}“ není povolen."
            )

        action = self._action_for(current, target)
        if action is not None and action.requires_sensitive_confirm and not confirm_sensitive:
            raise CoordinationLifecycleNeedsConfirmation(
                self._sensitive_confirm_message(current, target),
                sensitive=True,
            )

        if target in BOZP_COORDINATION_STATUSES_REQUIRING_PROTOCOL_CHECK:
            if (
                target == BOZP_COORDINATION_STATUS_ISSUED
                and current != BOZP_COORDINATION_STATUS_READY
            ):
                raise CoordinationLifecycleError(
                    "Vydat lze pouze ze stavu Připraveno k vydání."
                )
            self._validate_protocol_gate(
                coordination_id,
                confirm_warnings=confirm_warnings,
            )

        now = datetime.now()
        coordination.status = target
        if target == BOZP_COORDINATION_STATUS_READY:
            coordination.ready_at = now
        elif target == BOZP_COORDINATION_STATUS_ISSUED:
            coordination.issued_at = now
        elif target == BOZP_COORDINATION_STATUS_COMPLETED:
            coordination.completed_at = now
        elif target == BOZP_COORDINATION_STATUS_ARCHIVED:
            coordination.archived_at = now
        coordination.updated_at = now
        return bozp_coordination_service.repository.update(coordination)

    def _action_for(
        self,
        from_status: str,
        to_status: str,
    ) -> LifecycleAction | None:
        for action in self.list_actions(from_status):
            if action.target_status == to_status:
                return action
        return None

    def _sensitive_confirm_message(self, from_status: str, to_status: str) -> str:
        if from_status == BOZP_COORDINATION_STATUS_ISSUED:
            return (
                "Koordinace je ve stavu Vydáno. "
                "Opravdu ji vrátit k dopracování?"
            )
        if from_status == BOZP_COORDINATION_STATUS_COMPLETED:
            return (
                "Koordinace je ukončená. "
                "Opravdu ji znovu otevřít do stavu Rozpracováno?"
            )
        if from_status == BOZP_COORDINATION_STATUS_ARCHIVED:
            return (
                "Koordinace je archivovaná. "
                "Opravdu ji obnovit do stavu Rozpracováno?"
            )
        return (
            f"Opravdu provést přechod ze stavu „{status_label(from_status)}“ "
            f"do „{status_label(to_status)}“?"
        )

    def _validate_protocol_gate(
        self,
        coordination_id: int,
        *,
        confirm_warnings: bool,
    ) -> None:
        result = coordination_protocol_builder.build(coordination_id)
        critical = [
            item
            for item in result.warnings
            if item.severity == PROTOCOL_WARNING_SEVERITY_CRITICAL
        ]
        warnings = [
            item
            for item in result.warnings
            if item.severity == PROTOCOL_WARNING_SEVERITY_WARNING
        ]
        if critical:
            lines = "\n".join(f"• {item.message}" for item in critical)
            raise CoordinationLifecycleBlocked(
                "Přechod nelze dokončit kvůli kritickým problémům:\n" + lines,
                critical,
            )
        if warnings and not confirm_warnings:
            lines = "\n".join(f"• {item.message}" for item in warnings)
            raise CoordinationLifecycleNeedsConfirmation(
                "Koordinace má varování. Opravdu pokračovat?\n" + lines,
                warnings=warnings,
                sensitive=False,
            )


coordination_lifecycle_service = CoordinationLifecycleService()
