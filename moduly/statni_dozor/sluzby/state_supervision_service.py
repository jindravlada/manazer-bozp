"""Business služba evidence Státního dozoru (STATE-SUPERVISION-CORE-1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.statni_dozor.constants import (
    DEFAULT_STATUS,
    STATE_SUPERVISION_NOTIFICATION_METHODS,
    STATE_SUPERVISION_STATUSES,
)
from moduly.statni_dozor.modely.state_supervision import StateSupervision
from moduly.statni_dozor.repository.state_supervision_repository import (
    StateSupervisionRepository,
)

_EMPTY_OPTIONAL_STRINGS = (
    "authority_ico",
    "authority_address",
    "notification_method",
    "notification_note",
    "planned_start_place",
    "planned_control_place",
    "file_number",
    "subject",
    "initial_information",
    "preparation_note",
    "power_of_attorney_note",
    "result",
    "final_summary",
    "protocol_number",
    "objections_note",
)

_UPDATABLE_FIELDS = frozenset(
    {
        "status",
        "authority_ico",
        "authority_name",
        "authority_address",
        "workplace_id",
        "workplace_name_snapshot",
        "workplace_address_snapshot",
        "notification_method",
        "announced_at",
        "notification_note",
        "trade_union_notified_at",
        "management_notified_at",
        "planned_start_at",
        "planned_start_place",
        "planned_control_place",
        "started_at",
        "ended_at",
        "closed_at",
        "file_number",
        "subject",
        "initial_information",
        "preparation_note",
        "power_of_attorney_required",
        "power_of_attorney_note",
        "result",
        "final_summary",
        "protocol_number",
        "protocol_received_at",
        "objections_due_at",
        "objections_submitted_at",
        "objections_note",
        "completion_evidence_sent_at",
        "authority_confirmation_at",
    }
)


class StateSupervisionError(ValueError):
    """Validační / business chyba státního dozoru."""


def _blank_to_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _require_authority_name(value: Any) -> str:
    name = str(value or "").strip()
    if not name:
        raise StateSupervisionError("Název kontrolního orgánu je povinný.")
    return name


def _require_status(value: Any) -> str:
    status = str(value or "").strip()
    if status not in STATE_SUPERVISION_STATUSES:
        raise StateSupervisionError(f"Neplatný stav státního dozoru: {value!r}")
    return status


def _optional_notification_method(value: Any) -> str | None:
    method = _blank_to_none(value)
    if method is None:
        return None
    if method not in STATE_SUPERVISION_NOTIFICATION_METHODS:
        raise StateSupervisionError(f"Neplatný způsob ohlášení: {value!r}")
    return method


def _validate_date_order(
    *,
    started_at: datetime | None,
    ended_at: datetime | None,
    protocol_received_at: datetime | None,
    objections_submitted_at: datetime | None,
) -> None:
    if started_at is not None and ended_at is not None and ended_at < started_at:
        raise StateSupervisionError(
            "Datum ukončení nesmí být dříve než datum zahájení."
        )
    if (
        protocol_received_at is not None
        and objections_submitted_at is not None
        and objections_submitted_at < protocol_received_at
    ):
        raise StateSupervisionError(
            "Datum podání námitek nesmí být dříve než datum doručení protokolu."
        )


def _workplace_snapshots(
    *,
    workplace_id: int | None,
    name_snapshot: str | None,
    address_snapshot: str | None,
    fill_from_workplace: bool,
) -> tuple[str, str]:
    name = str(name_snapshot or "").strip()
    address = str(address_snapshot or "").strip()
    if fill_from_workplace and workplace_id and (not name or not address):
        workplace = settings_service.get_workplace_by_id(workplace_id)
        if workplace is not None:
            if not name:
                name = str(workplace.name or "").strip()
            if not address:
                address = str(workplace.address or "").strip()
    return name, address


def _normalize_payload(fields: dict[str, Any]) -> dict[str, Any]:
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise StateSupervisionError(f"Neznámé pole státního dozoru: {names}")

    payload = dict(fields)
    if "authority_name" in payload:
        payload["authority_name"] = _require_authority_name(payload["authority_name"])
    if "status" in payload:
        payload["status"] = _require_status(payload["status"])
    if "notification_method" in payload:
        payload["notification_method"] = _optional_notification_method(
            payload["notification_method"]
        )
    for key in _EMPTY_OPTIONAL_STRINGS:
        if key in payload and key != "notification_method":
            payload[key] = _blank_to_none(payload[key])
    if "workplace_id" in payload:
        workplace_id = payload["workplace_id"]
        payload["workplace_id"] = int(workplace_id) if workplace_id else None
    if "power_of_attorney_required" in payload:
        payload["power_of_attorney_required"] = bool(
            payload["power_of_attorney_required"]
        )
    return payload


class StateSupervisionService:
    def __init__(self) -> None:
        self.repository = StateSupervisionRepository()

    def create_supervision(
        self,
        *,
        authority_name: str,
        status: str = DEFAULT_STATUS,
        **fields: Any,
    ) -> StateSupervision:
        payload = _normalize_payload(
            {
                "authority_name": authority_name,
                "status": status,
                **fields,
            }
        )
        _validate_date_order(
            started_at=payload.get("started_at"),
            ended_at=payload.get("ended_at"),
            protocol_received_at=payload.get("protocol_received_at"),
            objections_submitted_at=payload.get("objections_submitted_at"),
        )
        name_snap, addr_snap = _workplace_snapshots(
            workplace_id=payload.get("workplace_id"),
            name_snapshot=payload.get("workplace_name_snapshot"),
            address_snapshot=payload.get("workplace_address_snapshot"),
            fill_from_workplace=True,
        )
        payload["workplace_name_snapshot"] = name_snap
        payload["workplace_address_snapshot"] = addr_snap
        payload.setdefault("power_of_attorney_required", False)
        record = StateSupervision(**payload)
        return self.repository.add(record)

    def get_supervision(self, supervision_id: int) -> StateSupervision | None:
        return self.repository.get_by_id(supervision_id)

    def update_supervision(
        self,
        supervision_id: int,
        **fields: Any,
    ) -> StateSupervision:
        record = self.repository.get_by_id(supervision_id)
        if record is None:
            raise StateSupervisionError(
                f"Kontrola státního dozoru {supervision_id} neexistuje."
            )
        payload = _normalize_payload(fields)
        previous_workplace_id = record.workplace_id
        workplace_changed = (
            "workplace_id" in payload
            and payload["workplace_id"] != previous_workplace_id
        )
        fill_from_workplace = workplace_changed and not (
            "workplace_name_snapshot" in payload
            and "workplace_address_snapshot" in payload
        )
        merged = {key: getattr(record, key) for key in _UPDATABLE_FIELDS}
        merged.update(payload)
        _validate_date_order(
            started_at=merged.get("started_at"),
            ended_at=merged.get("ended_at"),
            protocol_received_at=merged.get("protocol_received_at"),
            objections_submitted_at=merged.get("objections_submitted_at"),
        )
        name_snap, addr_snap = _workplace_snapshots(
            workplace_id=merged.get("workplace_id"),
            name_snapshot=merged.get("workplace_name_snapshot"),
            address_snapshot=merged.get("workplace_address_snapshot"),
            fill_from_workplace=fill_from_workplace,
        )
        merged["workplace_name_snapshot"] = name_snap
        merged["workplace_address_snapshot"] = addr_snap
        for key, value in merged.items():
            setattr(record, key, value)
        return self.repository.update(record)

    def list_supervisions(
        self,
        *,
        status: str | None = None,
        year: int | None = None,
        authority: str | None = None,
        workplace_id: int | None = None,
        query: str | None = None,
    ) -> list[StateSupervision]:
        status_filter = str(status).strip() if status else None
        if status_filter and status_filter not in STATE_SUPERVISION_STATUSES:
            raise StateSupervisionError(
                f"Neplatný stav státního dozoru: {status!r}"
            )
        return self.repository.list_all(
            status=status_filter,
            year=year,
            authority=authority,
            workplace_id=workplace_id,
            query=query,
        )


state_supervision_service = StateSupervisionService()
