"""Zjištění kontroly státního dozoru nad společným modelem Finding."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from core.shared.constants import (
    FINDING_STATUS_VYPORADANO,
    VALID_FINDING_STATUSES,
)
from core.shared.modely.finding import Finding
from core.shared.repository.finding_repository import FindingRepository
from moduly.statni_dozor.constants import (
    ENTITY_STATE_SUPERVISION,
    is_state_supervision_finding_type,
)
from moduly.statni_dozor.modely.state_supervision_finding_draft import (
    StateSupervisionFindingDraft,
)
from moduly.statni_dozor.repository.state_supervision_repository import (
    StateSupervisionRepository,
)
from moduly.statni_dozor.sluzby.state_supervision_service import StateSupervisionError


def _require_description(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise StateSupervisionError("Popis zjištění je povinný.")
    return text


def _require_finding_type(value: Any) -> str:
    code = str(value or "").strip()
    if not is_state_supervision_finding_type(code):
        raise StateSupervisionError(f"Neplatný druh zjištění státního dozoru: {value!r}")
    return code


def _require_status(value: Any) -> str:
    status = str(value or "").strip()
    if status not in VALID_FINDING_STATUSES:
        raise StateSupervisionError(f"Neplatný stav zjištění: {value!r}")
    return status


def _require_display_order(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        raise StateSupervisionError("Pořadí zjištění musí být nezáporné celé číslo.")
    try:
        order = int(value)
    except (TypeError, ValueError) as exc:
        raise StateSupervisionError(
            "Pořadí zjištění musí být nezáporné celé číslo."
        ) from exc
    if order < 0:
        raise StateSupervisionError("Pořadí zjištění nesmí být záporné.")
    return order


def _optional_person_id(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise StateSupervisionError("Odpovědná osoba musí být celé číslo nebo prázdná.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise StateSupervisionError(
            "Odpovědná osoba musí být celé číslo nebo prázdná."
        ) from exc


def _optional_task_id(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise StateSupervisionError("task_id musí být celé číslo nebo prázdné.")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise StateSupervisionError("task_id musí být celé číslo nebo prázdné.") from exc


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _apply_status_side_effects(finding: Finding) -> None:
    if finding.status == FINDING_STATUS_VYPORADANO and finding.resolved_at is None:
        finding.resolved_at = date.today()


def _normalize_batch_orders(
    drafts: Sequence[StateSupervisionFindingDraft],
) -> list[tuple[int, StateSupervisionFindingDraft]]:
    """Duplicitní display_order se seřadí a přepíše na 0, 10, 20, …"""
    decorated: list[tuple[int, int, int, StateSupervisionFindingDraft]] = []
    for index, draft in enumerate(drafts):
        order = _require_display_order(draft.display_order)
        existing_id = int(draft.id) if draft.id is not None else 10**9 + index
        decorated.append((order, existing_id, index, draft))
    decorated.sort(key=lambda item: (item[0], item[1], item[2]))
    return [(index * 10, item[3]) for index, item in enumerate(decorated)]


class StateSupervisionFindingService:
    """Dávkové API zjištění kontroly. Fyzicky nemaže; vynechaná zjištění zůstávají."""

    def __init__(self) -> None:
        self.repository = FindingRepository()
        self._supervisions = StateSupervisionRepository()

    def _require_supervision(
        self,
        supervision_id: int,
        *,
        session: Session | None = None,
    ) -> None:
        record = self._supervisions.get_by_id(int(supervision_id), session=session)
        if record is None:
            raise StateSupervisionError(
                f"Kontrola státního dozoru {supervision_id} neexistuje."
            )

    def list_findings(
        self,
        supervision_id: int,
        *,
        session: Session | None = None,
    ) -> list[Finding]:
        """Vrátí všechna zjištění kontroly včetně vypořádaných. Nic nezapisuje.

        Řazení: ``display_order``, ``id``. Stav kontroly (uzavřená / zrušená)
        zjištění neskrývá. Kontrola bez zjištění vrací prázdný seznam.
        """
        self._require_supervision(supervision_id, session=session)
        return self.repository.get_for_entity(
            ENTITY_STATE_SUPERVISION,
            int(supervision_id),
            session=session,
        )

    def save_state_supervision_findings_batch(
        self,
        supervision_id: int,
        drafts: Sequence[StateSupervisionFindingDraft],
        *,
        session: Session | None = None,
        replace_orders: bool = True,
    ) -> list[Finding]:
        """Uloží dávku zjištění jedné kontroly.

        Drafty v dávce se vytvoří nebo aktualizují. Existující Findings, které
        v dávce chybí, se **nemění a nemažou** — Finding nemá soft-delete.
        Prázdný seznam proto neznamená smazat všechna zjištění. Státní dozor
        v tomto kroku nevolá fyzický ``delete``.

        Při ``replace_orders=True`` se normalizují **pouze předané drafty**
        na 0, 10, 20, … podle (display_order, existující id, pořadí v dávce).
        Vynechaná historická zjištění se nepřečíslovávají. Kolize
        ``display_order`` s vynechaným řádkem se při čtení řeší stabilně
        podle ``(display_order, id)`` — bez mazání.

        ``task_id`` se pouze zapíše, jak je v draftu; úkol se nevytváří
        ani nemění.

        Jedna vlastní session = jeden commit. Caller-owned session se
        necommituje ani nezavírá. Chyba kteréhokoli draftu rollbackuje
        vlastní dávku; u caller-owned session nechá rollback na volajícím.
        DB ID se do původního pracovního draftu nezapisuje.
        """
        if not drafts:
            self._require_supervision(supervision_id, session=session)
            return []

        ordered = (
            _normalize_batch_orders(drafts)
            if replace_orders
            else [
                (_require_display_order(draft.display_order), draft)
                for draft in drafts
            ]
        )

        with self.repository.session(session) as (sess, owns):
            self._require_supervision(int(supervision_id), session=sess)
            existing_rows = {
                int(row.id): row
                for row in self.repository.get_for_entity(
                    ENTITY_STATE_SUPERVISION,
                    int(supervision_id),
                    session=sess,
                )
            }
            resolved: list[tuple[int, StateSupervisionFindingDraft, Finding | None]] = []
            for order, draft in ordered:
                resolved.append(
                    (
                        order,
                        draft,
                        self._existing_for_draft(
                            supervision_id=int(supervision_id),
                            draft=draft,
                            existing_rows=existing_rows,
                            session=sess,
                        ),
                    )
                )
            prepared: list[Finding] = []
            for order, draft, existing in resolved:
                prepared.append(
                    self._record_from_draft(
                        supervision_id=int(supervision_id),
                        draft=draft,
                        existing=existing,
                        display_order=order,
                    )
                )
            stored = self.repository.save_all(prepared, session=sess)
            if owns:
                sess.commit()
                detached: list[Finding] = []
                for record in stored:
                    sess.refresh(record)
                    sess.expunge(record)
                    detached.append(record)
                return detached
            return stored

    def _existing_for_draft(
        self,
        *,
        supervision_id: int,
        draft: StateSupervisionFindingDraft,
        existing_rows: dict[int, Finding],
        session: Session | None = None,
    ) -> Finding | None:
        _require_finding_type(draft.finding_type)
        _require_description(draft.description)
        _require_status(draft.status)
        _optional_person_id(draft.responsible_person_id)
        _optional_task_id(draft.task_id)
        if draft.id is None:
            return None
        existing = existing_rows.get(int(draft.id))
        if existing is not None:
            return existing
        loaded = self.repository.get_by_id(int(draft.id), session=session)
        if loaded is None:
            raise StateSupervisionError(f"Zjištění {draft.id} neexistuje.")
        if (
            str(loaded.entity_type) != ENTITY_STATE_SUPERVISION
            or int(loaded.entity_id) != int(supervision_id)
        ):
            raise StateSupervisionError(
                "Zjištění nepatří k této kontrole státního dozoru."
            )
        return loaded

    def _record_from_draft(
        self,
        *,
        supervision_id: int,
        draft: StateSupervisionFindingDraft,
        existing: Finding | None,
        display_order: int,
    ) -> Finding:
        finding_type = _require_finding_type(draft.finding_type)
        description = _require_description(draft.description)
        status = _require_status(draft.status)
        person_id = _optional_person_id(draft.responsible_person_id)
        task_id = _optional_task_id(draft.task_id)
        source_area = _as_text(draft.source_area_label).strip()
        person_name = _as_text(draft.responsible_person_name).strip()
        recommended = _as_text(draft.recommended_action)
        resolution = _as_text(draft.resolution_note)

        if existing is None:
            finding = Finding(
                entity_type=ENTITY_STATE_SUPERVISION,
                entity_id=int(supervision_id),
                finding_type=finding_type,
                description=description,
                source_area_label=source_area,
                status=status,
                responsible_person_id=person_id,
                responsible_person_name=person_name,
                due_date=draft.due_date,
                recommended_action=recommended,
                resolution_note=resolution,
                resolved_at=draft.resolved_at,
                task_id=task_id,
                display_order=display_order,
            )
            _apply_status_side_effects(finding)
            return finding

        existing.finding_type = finding_type
        existing.description = description
        existing.source_area_label = source_area
        existing.status = status
        existing.responsible_person_id = person_id
        existing.responsible_person_name = person_name
        existing.due_date = draft.due_date
        existing.recommended_action = recommended
        existing.resolution_note = resolution
        existing.resolved_at = draft.resolved_at
        if task_id is not None:
            existing.task_id = task_id
        existing.display_order = display_order
        _apply_status_side_effects(existing)
        return existing


state_supervision_finding_service = StateSupervisionFindingService()


def save_state_supervision_findings_batch(
    supervision_id: int,
    drafts: Sequence[StateSupervisionFindingDraft],
    *,
    session: Session | None = None,
    replace_orders: bool = True,
) -> list[Finding]:
    return state_supervision_finding_service.save_state_supervision_findings_batch(
        supervision_id,
        drafts,
        session=session,
        replace_orders=replace_orders,
    )
