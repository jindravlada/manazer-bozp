"""Business služba evidence Státního dozoru (STATE-SUPERVISION-CORE-1)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Final

from sqlalchemy.orm import Session

from core.models.attachment_staging import AttachmentStagingState
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.statni_dozor.constants import (
    CLOSED_AT_REQUIRED_MESSAGE,
    CLOSED_BEFORE_ENDED_MESSAGE,
    DEFAULT_STATUS,
    ENTITY_STATE_SUPERVISION,
    OBJECTIONS_BEFORE_PROTOCOL_MESSAGE,
    STATE_SUPERVISION_NOTIFICATION_METHODS,
    STATE_SUPERVISION_STATUSES,
    STATUS_CLOSED,
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
    status: str | None = None,
    started_at: datetime | None,
    ended_at: datetime | None,
    closed_at: datetime | None = None,
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
        raise StateSupervisionError(OBJECTIONS_BEFORE_PROTOCOL_MESSAGE)
    if status == STATUS_CLOSED and closed_at is None:
        raise StateSupervisionError(CLOSED_AT_REQUIRED_MESSAGE)
    if ended_at is not None and closed_at is not None and closed_at < ended_at:
        raise StateSupervisionError(CLOSED_BEFORE_ENDED_MESSAGE)


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


logger = logging.getLogger(__name__)


class KeepExisting:
    """Sentinel: podřízená kolekce nebyla předána a existující data se nemění.

    Odlišuje se od prázdného seznamu dokladů / průběhu / účastníků, který
    znamená „deaktivovat všechny aktivní položky této kolekce“. U příloh
    prázdný ``AttachmentStagingState`` existující soubory nedeaktivuje.
    U zjištění prázdný seznam nic nemaže — Finding nemá soft-delete.
    Viz ``save_supervision_bundle``.
    """

    def __repr__(self) -> str:
        return "KEEP_EXISTING"


KEEP_EXISTING: Final = KeepExisting()


class StateSupervisionService:
    def __init__(self) -> None:
        self.repository = StateSupervisionRepository()

    def create_supervision(
        self,
        *,
        authority_name: str,
        status: str = DEFAULT_STATUS,
        session: Session | None = None,
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
            status=payload.get("status"),
            started_at=payload.get("started_at"),
            ended_at=payload.get("ended_at"),
            closed_at=payload.get("closed_at"),
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
        return self.repository.add(record, session=session)

    def get_supervision(
        self,
        supervision_id: int,
        *,
        session: Session | None = None,
    ) -> StateSupervision | None:
        return self.repository.get_by_id(supervision_id, session=session)

    def get_supervisions_by_ids(
        self,
        supervision_ids: list[int] | tuple[int, ...],
        *,
        session: Session | None = None,
    ) -> list[StateSupervision]:
        return self.repository.get_by_ids(supervision_ids, session=session)

    def update_supervision(
        self,
        supervision_id: int,
        *,
        session: Session | None = None,
        **fields: Any,
    ) -> StateSupervision:
        record = self.repository.get_by_id(supervision_id, session=session)
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
            status=merged.get("status"),
            started_at=merged.get("started_at"),
            ended_at=merged.get("ended_at"),
            closed_at=merged.get("closed_at"),
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
        return self.repository.update(record, session=session)

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

    def save_supervision_bundle(
        self,
        *,
        supervision_id: int | None,
        fields: dict[str, Any],
        documents: Sequence[Any] | KeepExisting = KEEP_EXISTING,
        timeline_items: Sequence[Any] | KeepExisting = KEEP_EXISTING,
        participants: Sequence[Any] | KeepExisting = KEEP_EXISTING,
        attachments: AttachmentStagingState | KeepExisting = KEEP_EXISTING,
        findings: Sequence[Any] | KeepExisting = KEEP_EXISTING,
        session: Session | None = None,
    ) -> tuple[StateSupervision, list, list]:
        """Uloží kontrolu, doklady, průběh, účastníky, zjištění a staged přílohy atomicky.

        Návrat zůstává 3-složka ``(kontrola, doklady, průběh)``. Uložená
        zjištění se do návratu nepřidávají — po úspěchu je načtěte přes
        ``list_findings(supervision_id)``.

        ``KEEP_EXISTING`` = kolekce nebyla poskytnuta, existující řádky
        se nenačítají ani nemění. Prázdný seznam dokladů / průběhu /
        účastníků = deaktivovat všechny aktivní položky dané kolekce.
        ``None`` se u příloh i zjištění odmítá.

        ``findings=KEEP_EXISTING`` zjištění nenačítá, nemění a nevolá
        finding batch. Předaná sekvence draftů se vytvoří nebo aktualizuje;
        vynechaná existující zjištění zůstanou. Prázdná sekvence ``[]``
        nic nevytvoří, neaktualizuje, nemaže ani nepřečísluje — Finding
        nemá soft-delete a bundle nevolá fyzický ``delete``.

        ``attachments=KEEP_EXISTING`` přílohy nenačítá ani nemění a nevytváří
        žádný soubor. ``AttachmentStagingState`` aplikuje jen
        ``pending_add_paths`` a ``pending_remove_ids``; prázdný staging
        existující přílohy nedeaktivuje. Úspěšně aplikovaný staging se
        nesmí znovu použít bez obnovení — bundle jej samo nemění ani
        nevolá ``clear()``.

        Pořadí: create/update rodiče, flush ID, doklady, průběh, účastníci,
        zjištění, ``prepare_attachment_staging`` v caller-owned session,
        jeden commit, ``finalize_attachment_changes``. Chyba zjištění
        nastane před kopírováním souborů. Při chybě rollback DB a úklid
        nových kopií; původní odebírané soubory zůstanou. Původní drafty
        zjištění se nemění (žádné DB ID, ``client_key`` ani ``task_id``).
        """
        from core.services.attachment_service import attachment_service
        from moduly.statni_dozor.modely.state_supervision_required_document import (
            StateSupervisionRequiredDocument,
        )
        from moduly.statni_dozor.modely.state_supervision_timeline_item import (
            StateSupervisionTimelineItem,
        )
        from moduly.statni_dozor.sluzby.state_supervision_finding_service import (
            state_supervision_finding_service,
        )
        from moduly.statni_dozor.sluzby.state_supervision_participant_service import (
            state_supervision_participant_service,
        )
        from moduly.statni_dozor.sluzby.state_supervision_required_document_service import (
            state_supervision_required_document_service,
        )
        from moduly.statni_dozor.sluzby.state_supervision_timeline_item_service import (
            state_supervision_timeline_item_service,
        )

        payload = dict(fields)
        save_documents = documents is not KEEP_EXISTING
        save_timeline = timeline_items is not KEEP_EXISTING
        save_participants = participants is not KEEP_EXISTING
        document_drafts = list(documents) if save_documents else []
        timeline_drafts = list(timeline_items) if save_timeline else []
        participant_drafts = list(participants) if save_participants else []
        finding_drafts = _require_findings_argument(findings)
        staging = _require_attachment_argument(attachments)
        prepared = None
        committed = False
        result: tuple[StateSupervision, list, list] | None = None
        try:
            with self.repository.session(session) as (sess, owns):
                if supervision_id is None:
                    record = self.create_supervision(session=sess, **payload)
                else:
                    record = self.update_supervision(
                        int(supervision_id),
                        session=sess,
                        **payload,
                    )
                sess.flush()
                stored_docs: list = []
                stored_timeline: list = []
                if save_documents:
                    stored_docs = (
                        state_supervision_required_document_service.save_document_batch(
                            int(record.id),
                            document_drafts,
                            session=sess,
                            replace_orders=True,
                            deactivate_omitted=True,
                        )
                    )
                if save_timeline:
                    stored_timeline = (
                        state_supervision_timeline_item_service.save_timeline_batch(
                            int(record.id),
                            timeline_drafts,
                            session=sess,
                            replace_orders=True,
                            deactivate_omitted=True,
                        )
                    )
                if save_participants:
                    state_supervision_participant_service.save_participant_batch(
                        int(record.id),
                        participant_drafts,
                        session=sess,
                        replace_orders=True,
                        deactivate_omitted=True,
                    )
                if finding_drafts:
                    state_supervision_finding_service.save_state_supervision_findings_batch(
                        int(record.id),
                        finding_drafts,
                        session=sess,
                        replace_orders=True,
                    )
                if staging is not None and staging.has_changes():
                    prepared = attachment_service.prepare_attachment_staging(
                        ENTITY_STATE_SUPERVISION,
                        int(record.id),
                        staging,
                        sess,
                    )
                if owns:
                    sess.commit()
                    committed = True
                    sess.refresh(record)
                    sess.expunge(record)
                    detached_docs: list[StateSupervisionRequiredDocument] = []
                    for item in stored_docs:
                        sess.refresh(item)
                        sess.expunge(item)
                        detached_docs.append(item)
                    detached_timeline: list[StateSupervisionTimelineItem] = []
                    for item in stored_timeline:
                        sess.refresh(item)
                        sess.expunge(item)
                        detached_timeline.append(item)
                    result = (record, detached_docs, detached_timeline)
                else:
                    result = (record, stored_docs, stored_timeline)
        except Exception:
            if prepared is not None and not committed:
                try:
                    attachment_service.rollback_attachment_changes(prepared)
                except Exception:
                    logger.exception("Úklid připravených příloh kontroly selhal.")
            raise
        assert result is not None
        if prepared is not None and committed:
            warnings = attachment_service.finalize_attachment_changes(prepared)
            for message in warnings:
                logger.warning(
                    "Kontrola %s byla uložena, ale odstranění souboru přílohy selhalo: %s",
                    result[0].id,
                    message,
                )
        return result

    def save_supervision_with_documents(
        self,
        *,
        supervision_id: int | None,
        fields: dict[str, Any],
        documents: Sequence[Any],
        session: Session | None = None,
    ) -> tuple[StateSupervision, list]:
        """Kompatibilní wrapper: uloží kontrolu a doklady, průběh, účastníky a zjištění nemění."""
        record, stored_docs, _timeline = self.save_supervision_bundle(
            supervision_id=supervision_id,
            fields=fields,
            documents=documents,
            timeline_items=KEEP_EXISTING,
            participants=KEEP_EXISTING,
            attachments=KEEP_EXISTING,
            findings=KEEP_EXISTING,
            session=session,
        )
        return record, stored_docs


def _require_attachment_argument(
    attachments: AttachmentStagingState | KeepExisting,
) -> AttachmentStagingState | None:
    if attachments is None:
        raise StateSupervisionError(
            "Parametr attachments nesmí být None. "
            "Použijte KEEP_EXISTING nebo AttachmentStagingState."
        )
    if attachments is KEEP_EXISTING:
        return None
    if not isinstance(attachments, AttachmentStagingState):
        raise StateSupervisionError(
            "Parametr attachments musí být KEEP_EXISTING nebo AttachmentStagingState."
        )
    return attachments


def _require_findings_argument(
    findings: Sequence[Any] | KeepExisting,
) -> list | None:
    if findings is None:
        raise StateSupervisionError(
            "Parametr findings nesmí být None. "
            "Použijte KEEP_EXISTING nebo seznam draftů."
        )
    if findings is KEEP_EXISTING:
        return None
    if isinstance(findings, (str, bytes)):
        raise StateSupervisionError(
            "Parametr findings musí být KEEP_EXISTING nebo seznam draftů."
        )
    try:
        drafts = list(findings)
    except TypeError as exc:
        raise StateSupervisionError(
            "Parametr findings musí být KEEP_EXISTING nebo seznam draftů."
        ) from exc
    from moduly.statni_dozor.modely.state_supervision_finding_draft import (
        StateSupervisionFindingDraft,
    )

    for item in drafts:
        if not isinstance(item, StateSupervisionFindingDraft):
            raise StateSupervisionError(
                "Parametr findings musí obsahovat StateSupervisionFindingDraft."
            )
    return drafts


state_supervision_service = StateSupervisionService()
