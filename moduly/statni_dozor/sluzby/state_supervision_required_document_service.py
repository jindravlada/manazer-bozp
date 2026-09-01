"""Služba požadovaných dokladů kontroly státního dozoru."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.statni_dozor.constants import (
    RESPONSIBLE_SOURCE_PERSON,
    RESPONSIBLE_SOURCE_THP_WORKER,
    RESPONSIBLE_SOURCE_TYPES,
)
from moduly.statni_dozor.modely.state_supervision_required_document import (
    StateSupervisionRequiredDocument,
)
from moduly.statni_dozor.modely.state_supervision_required_document_draft import (
    StateSupervisionRequiredDocumentDraft,
)
from moduly.statni_dozor.repository.state_supervision_required_document_repository import (
    StateSupervisionRequiredDocumentRepository,
)
from moduly.statni_dozor.repository.state_supervision_repository import (
    StateSupervisionRepository,
)
from moduly.statni_dozor.sluzby.state_supervision_service import StateSupervisionError

_UPDATABLE_FIELDS = frozenset(
    {
        "title",
        "responsible_source_type",
        "responsible_source_id",
        "responsible_name_snapshot",
        "due_at",
        "prepared_at",
        "submitted_at",
        "note",
        "display_order",
        "active",
    }
)


def _blank_to_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _require_title(value: Any) -> str:
    title = str(value or "").strip()
    if not title:
        raise StateSupervisionError("Název požadovaného dokladu je povinný.")
    return title


def _require_display_order(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        raise StateSupervisionError("Pořadí dokladu musí být nezáporné celé číslo.")
    try:
        order = int(value)
    except (TypeError, ValueError) as exc:
        raise StateSupervisionError(
            "Pořadí dokladu musí být nezáporné celé číslo."
        ) from exc
    if order < 0:
        raise StateSupervisionError("Pořadí dokladu nesmí být záporné.")
    return order


def _resolve_responsible(
    *,
    source_type: Any,
    source_id: Any,
    existing: StateSupervisionRequiredDocument | None = None,
) -> tuple[str | None, int | None, str | None]:
    type_value = _blank_to_none(source_type)
    id_raw = source_id
    if id_raw in ("", None):
        id_value = None
    else:
        try:
            id_value = int(id_raw)
        except (TypeError, ValueError) as exc:
            raise StateSupervisionError(
                "ID odpovědné osoby musí být celé číslo."
            ) from exc
        if id_value <= 0:
            id_value = None

    if type_value is None and id_value is None:
        return None, None, None
    if type_value is None or id_value is None:
        raise StateSupervisionError(
            "Typ a ID odpovědné osoby musí být vyplněny společně."
        )
    if type_value not in RESPONSIBLE_SOURCE_TYPES:
        raise StateSupervisionError(f"Neplatný typ odpovědné osoby: {source_type!r}")

    same_as_existing = (
        existing is not None
        and existing.responsible_source_type == type_value
        and existing.responsible_source_id == id_value
    )
    if same_as_existing:
        snapshot = _blank_to_none(existing.responsible_name_snapshot)
        if snapshot:
            return type_value, id_value, snapshot

    if type_value == RESPONSIBLE_SOURCE_PERSON:
        person = person_service.get_by_id(id_value)
        if person is None:
            raise StateSupervisionError(f"Osoba id={id_value} neexistuje.")
        display = str(
            getattr(person, "display_name", None) or person.full_name or ""
        ).strip()
        if not display:
            display = f"Osoba #{id_value}"
        return type_value, id_value, display

    if type_value == RESPONSIBLE_SOURCE_THP_WORKER:
        worker = settings_service.get_worker_by_id(id_value)
        if worker is None:
            raise StateSupervisionError(f"THP pracovník id={id_value} neexistuje.")
        display = str(
            getattr(worker, "display_name", None) or worker.full_name or ""
        ).strip()
        if not display:
            display = f"THP #{id_value}"
        return type_value, id_value, display

    raise StateSupervisionError(f"Neplatný typ odpovědné osoby: {source_type!r}")


def _normalize_batch_orders(
    drafts: Sequence[StateSupervisionRequiredDocumentDraft],
) -> list[tuple[int, StateSupervisionRequiredDocumentDraft]]:
    """Duplicitní display_order se seřadí a přepíše na 0, 10, 20, …"""
    decorated: list[tuple[int, int, int, StateSupervisionRequiredDocumentDraft]] = []
    for index, draft in enumerate(drafts):
        order = _require_display_order(draft.display_order)
        existing_id = int(draft.id) if draft.id is not None else 10**9 + index
        decorated.append((order, existing_id, index, draft))
    decorated.sort(key=lambda item: (item[0], item[1], item[2]))
    return [(index * 10, item[3]) for index, item in enumerate(decorated)]


class StateSupervisionRequiredDocumentService:
    def __init__(self) -> None:
        self.repository = StateSupervisionRequiredDocumentRepository()
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

    def list_documents(
        self,
        supervision_id: int,
        *,
        include_inactive: bool = False,
        session: Session | None = None,
    ) -> list[StateSupervisionRequiredDocument]:
        self._require_supervision(supervision_id, session=session)
        return self.repository.list_for_supervision(
            int(supervision_id),
            include_inactive=include_inactive,
            session=session,
        )

    def list_for_supervisions(
        self,
        supervision_ids: Sequence[int],
        *,
        include_inactive: bool = False,
        session: Session | None = None,
    ) -> list[StateSupervisionRequiredDocument]:
        """Dávkové načtení dokladů pro přehled. Nic nezapisuje."""
        return self.repository.list_for_supervisions(
            supervision_ids,
            include_inactive=include_inactive,
            session=session,
        )

    def get_document(
        self,
        document_id: int,
        *,
        session: Session | None = None,
    ) -> StateSupervisionRequiredDocument | None:
        return self.repository.get_by_id(int(document_id), session=session)

    def create_document(
        self,
        supervision_id: int,
        *,
        title: str,
        session: Session | None = None,
        **fields: Any,
    ) -> StateSupervisionRequiredDocument:
        allowed = {key: fields[key] for key in fields if key in _UPDATABLE_FIELDS}
        if "display_order" not in allowed:
            existing = self.repository.list_for_supervision(
                int(supervision_id),
                include_inactive=True,
                session=session,
            )
            max_order = max((int(row.display_order) for row in existing), default=-10)
            allowed["display_order"] = max_order + 10
        draft = StateSupervisionRequiredDocumentDraft(title=title, **allowed)
        saved = self.save_document_batch(
            supervision_id,
            [draft],
            session=session,
            replace_orders=False,
        )
        return saved[0]

    def update_document(
        self,
        document_id: int,
        *,
        session: Session | None = None,
        **fields: Any,
    ) -> StateSupervisionRequiredDocument:
        unknown = set(fields) - _UPDATABLE_FIELDS
        if unknown:
            names = ", ".join(sorted(unknown))
            raise StateSupervisionError(f"Neznámé pole požadovaného dokladu: {names}")
        current = self.repository.get_by_id(int(document_id), session=session)
        if current is None:
            raise StateSupervisionError(
                f"Požadovaný doklad {document_id} neexistuje."
            )
        draft = self._draft_from_record(current)
        for key, value in fields.items():
            setattr(draft, key, value)
        saved = self.save_document_batch(
            int(current.state_supervision_id),
            [draft],
            session=session,
            replace_orders=False,
        )
        return saved[0]

    def deactivate_document(
        self,
        document_id: int,
        *,
        session: Session | None = None,
    ) -> StateSupervisionRequiredDocument:
        return self.update_document(document_id, session=session, active=False)

    def reactivate_document(
        self,
        document_id: int,
        *,
        session: Session | None = None,
    ) -> StateSupervisionRequiredDocument:
        return self.update_document(document_id, session=session, active=True)

    def save_document_batch(
        self,
        supervision_id: int,
        drafts: Sequence[StateSupervisionRequiredDocumentDraft],
        *,
        session: Session | None = None,
        replace_orders: bool = True,
        deactivate_omitted: bool = False,
    ) -> list[StateSupervisionRequiredDocument]:
        """Uloží dávku dokladů jedné kontroly v jedné transakci.

        Duplicitní ``display_order`` se při ``replace_orders=True`` (výchozí)
        deterministicky přepíše na 0, 10, 20, … podle (order, id, pořadí v dávce).

        Při ``deactivate_omitted=True`` se aktivní doklady, které v dávce
        chybí, skryjí přes ``active=False``. Prázdná dávka tak deaktivuje
        všechny aktivní doklady. Výchozí ``False`` zachovává 2C0 chování.
        """
        self._require_supervision(supervision_id, session=session)
        hide_omitted = bool(deactivate_omitted)
        if not drafts and not hide_omitted:
            return []

        with self.repository.session(session) as (sess, owns):
            existing_rows = {
                int(row.id): row
                for row in self.repository.list_for_supervision(
                    int(supervision_id),
                    include_inactive=True,
                    session=sess,
                )
            }
            ordered = (
                _normalize_batch_orders(drafts)
                if replace_orders and drafts
                else [
                    (_require_display_order(draft.display_order), draft)
                    for draft in drafts
                ]
            )
            prepared: list[StateSupervisionRequiredDocument] = []
            for order, draft in ordered:
                record = self._record_from_draft(
                    supervision_id=int(supervision_id),
                    draft=draft,
                    existing_rows=existing_rows,
                    display_order=order,
                    session=sess,
                )
                prepared.append(record)
            kept_count = len(prepared)
            if hide_omitted:
                kept_ids = {int(draft.id) for draft in drafts if draft.id is not None}
                for row_id, row in existing_rows.items():
                    if row_id in kept_ids:
                        continue
                    if not bool(row.active):
                        continue
                    row.active = False
                    row.updated_at = datetime.now()
                    prepared.append(row)
            if not prepared:
                return []
            stored = self.repository.save_all(prepared, session=sess)
            kept = stored[:kept_count]
            if owns:
                sess.commit()
                detached: list[StateSupervisionRequiredDocument] = []
                for record in kept:
                    sess.refresh(record)
                    sess.expunge(record)
                    detached.append(record)
                return detached
            return kept

    def _draft_from_record(
        self, record: StateSupervisionRequiredDocument
    ) -> StateSupervisionRequiredDocumentDraft:
        return StateSupervisionRequiredDocumentDraft(
            id=int(record.id),
            title=str(record.title or ""),
            responsible_source_type=record.responsible_source_type,
            responsible_source_id=record.responsible_source_id,
            responsible_name_snapshot=record.responsible_name_snapshot,
            due_at=record.due_at,
            prepared_at=record.prepared_at,
            submitted_at=record.submitted_at,
            note=record.note,
            display_order=int(record.display_order or 0),
            active=bool(record.active),
        )

    def _record_from_draft(
        self,
        *,
        supervision_id: int,
        draft: StateSupervisionRequiredDocumentDraft,
        existing_rows: dict[int, StateSupervisionRequiredDocument],
        display_order: int,
        session: Session | None = None,
    ) -> StateSupervisionRequiredDocument:
        title = _require_title(draft.title)
        existing: StateSupervisionRequiredDocument | None = None
        if draft.id is not None:
            existing = existing_rows.get(int(draft.id))
            if existing is None:
                loaded = self.repository.get_by_id(int(draft.id), session=session)
                if loaded is None:
                    raise StateSupervisionError(
                        f"Požadovaný doklad {draft.id} neexistuje."
                    )
                if int(loaded.state_supervision_id) != int(supervision_id):
                    raise StateSupervisionError(
                        "Doklad nepatří k této kontrole státního dozoru."
                    )
                existing = loaded
        source_type, source_id, snapshot = _resolve_responsible(
            source_type=draft.responsible_source_type,
            source_id=draft.responsible_source_id,
            existing=existing,
        )
        note = _blank_to_none(draft.note)
        if existing is None:
            return StateSupervisionRequiredDocument(
                state_supervision_id=int(supervision_id),
                title=title,
                responsible_source_type=source_type,
                responsible_source_id=source_id,
                responsible_name_snapshot=snapshot,
                due_at=draft.due_at,
                prepared_at=draft.prepared_at,
                submitted_at=draft.submitted_at,
                note=note,
                display_order=display_order,
                active=bool(draft.active),
            )
        existing.title = title
        existing.responsible_source_type = source_type
        existing.responsible_source_id = source_id
        existing.responsible_name_snapshot = snapshot
        existing.due_at = draft.due_at
        existing.prepared_at = draft.prepared_at
        existing.submitted_at = draft.submitted_at
        existing.note = note
        existing.display_order = display_order
        existing.active = bool(draft.active)
        existing.updated_at = datetime.now()
        return existing


state_supervision_required_document_service = StateSupervisionRequiredDocumentService()
