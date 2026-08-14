"""Jednotný zdroj otázek auditu: snapshot vs živá metodika (AUDIT-SNAPSHOT-1b).

Snapshotovaný audit nikdy nepadá tiše na JSON. Live / NULL zachovává dosavadní chování.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Literal

from sqlalchemy import select

from core.database.session import get_session
from core.shared.constants import ENTITY_AUDITY
from core.shared.modely.control_result import ControlResult
from moduly.audity.constants import AUDIT_METHODOLOGY_SOURCE_SNAPSHOT
from moduly.audity.modely.audit import Audit
from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
from moduly.audity.sluzby.audit_knowledge_service import (
    KNOWLEDGE_NODE_PROCESS,
    KNOWLEDGE_NODE_SECTION,
    KnowledgeTreeNode,
)
from moduly.audity.sluzby.audit_question_snapshot_service import snapshot_key

logger = logging.getLogger(__name__)

AuditQuestionSourceMode = Literal["snapshot", "live"]


class AuditQuestionSourceError(Exception):
    """Snapshotovaný audit má nekonzistentní snapshot — bez fallbacku na JSON."""


@dataclass(frozen=True)
class SnapshotAssertionView:
    process_id: str
    process_name: str
    section_id: str
    section_name: str
    assertion_id: str
    assertion_text: str
    verification_type: str
    severity: str
    question_kind: str
    display_order: int

    @property
    def key(self) -> tuple[str, str, str]:
        return snapshot_key(self.process_id, self.section_id, self.assertion_id)


@dataclass(frozen=True)
class AuditQuestionSource:
    """Výsledek volby zdroje otázek pro jeden audit."""

    mode: AuditQuestionSourceMode
    audit_id: int | None
    roots: tuple[KnowledgeTreeNode, ...] = ()
    assertions: tuple[SnapshotAssertionView, ...] = ()
    assertion_keys: frozenset[tuple[str, str, str]] = field(default_factory=frozenset)
    text_by_key: dict[tuple[str, str, str], str] = field(default_factory=dict)
    severity_by_key: dict[tuple[str, str, str], str] = field(default_factory=dict)
    process_names: dict[str, str] = field(default_factory=dict)

    @property
    def is_snapshot(self) -> bool:
        return self.mode == "snapshot"


def _row_to_view(row: AuditQuestionSnapshot) -> SnapshotAssertionView:
    return SnapshotAssertionView(
        process_id=str(row.process_id or "").strip(),
        process_name=str(row.process_name or "").strip(),
        section_id=str(row.section_id or "").strip(),
        section_name=str(row.section_name or "").strip(),
        assertion_id=str(row.assertion_id or "").strip(),
        assertion_text=str(row.assertion_text or "").strip(),
        verification_type=str(row.verification_type or "").strip(),
        severity=str(row.severity or "").strip(),
        question_kind=str(row.question_kind or "").strip(),
        display_order=int(row.display_order or 0),
    )


def build_knowledge_tree_from_snapshot_views(
    views: list[SnapshotAssertionView] | tuple[SnapshotAssertionView, ...],
) -> list[KnowledgeTreeNode]:
    """Sestaví strom kompatibilní s AuditDialogem výhradně ze snapshotových řádků."""
    ordered = sorted(
        views,
        key=lambda item: (
            item.display_order,
            item.process_name.casefold(),
            item.process_id,
            item.section_name.casefold(),
            item.section_id,
            item.assertion_id,
        ),
    )

    processes: dict[str, dict] = {}
    process_order: list[str] = []
    for view in ordered:
        if view.process_id not in processes:
            processes[view.process_id] = {
                "name": view.process_name or view.process_id,
                "sections": {},
                "section_order": [],
            }
            process_order.append(view.process_id)
        pdata = processes[view.process_id]
        if view.process_name and not pdata["name"]:
            pdata["name"] = view.process_name
        if view.section_id not in pdata["sections"]:
            pdata["sections"][view.section_id] = {
                "name": view.section_name or view.section_id,
                "assertions": [],
            }
            pdata["section_order"].append(view.section_id)
        sdata = pdata["sections"][view.section_id]
        if view.section_name and not sdata["name"]:
            sdata["name"] = view.section_name
        sdata["assertions"].append(
            {
                "id": view.assertion_id,
                "text": view.assertion_text,
                "nazev": view.assertion_text,
                "poradi": view.display_order,
                "aktivni": True,
                "zavaznost": view.severity,
                "verification_type": view.verification_type,
                "question_kind": view.question_kind,
            }
        )

    roots: list[KnowledgeTreeNode] = []
    for process_id in process_order:
        pdata = processes[process_id]
        children: list[KnowledgeTreeNode] = []
        for section_id in pdata["section_order"]:
            sdata = pdata["sections"][section_id]
            section = {
                "id": section_id,
                "nazev": sdata["name"],
                "aktivni": True,
                "auditni_tvrzeni": list(sdata["assertions"]),
            }
            children.append(
                KnowledgeTreeNode(
                    node_type=KNOWLEDGE_NODE_SECTION,
                    node_id=section_id,
                    label=sdata["name"],
                    process_id=process_id,
                    process_label=pdata["name"],
                    section=section,
                )
            )
        roots.append(
            KnowledgeTreeNode(
                node_type=KNOWLEDGE_NODE_PROCESS,
                node_id=process_id,
                label=pdata["name"],
                process_id=process_id,
                process_label=pdata["name"],
                children=tuple(children),
            )
        )
    return roots


def _match_result_to_keys(
    result: ControlResult,
    keys: frozenset[tuple[str, str, str]],
    *,
    text_by_key: dict[tuple[str, str, str], str] | None = None,
) -> tuple[str, str, str] | None:
    """Najde snapshotový klíč pro control_result (včetně orphan variant)."""
    id_key = snapshot_key(
        result.source_area_id,
        result.source_section_id,
        result.source_control_point_id,
    )
    if id_key[2] and id_key in keys:
        return id_key

    cp = str(result.source_control_point_id or "").strip()
    label_area = str(result.source_area_label or "").strip()
    label_section = str(result.source_section_label or "").strip()
    if text_by_key:
        for key, text in text_by_key.items():
            if key[2] != cp:
                continue
            # process/section name matching via separate process_names not available here;
            # fall through to synthetic keys.
            _ = (label_area, label_section, text)

    process_id = str(result.source_area_id or "").strip() or f"orphan_process_{result.id}"
    section_id = (
        str(result.source_section_id or "").strip() or f"orphan_section_{result.id}"
    )
    assertion_id = cp or f"orphan_cr_{result.id}"
    for candidate in (
        assertion_id,
        f"{cp}__cr{result.id}" if cp else f"orphan_cr_{result.id}",
        f"orphan_cr_{result.id}",
    ):
        key = snapshot_key(process_id, section_id, candidate)
        if key in keys:
            return key
    return None


def _validate_snapshot_consistency(
    audit,
    *,
    views: list[SnapshotAssertionView],
    control_results: list[ControlResult],
) -> None:
    if audit.questions_frozen_at is None:
        raise AuditQuestionSourceError(
            f"Audit {audit.id}: methodology_source=snapshot, ale chybí questions_frozen_at."
        )
    if not str(audit.methodology_generation or "").strip():
        raise AuditQuestionSourceError(
            f"Audit {audit.id}: methodology_source=snapshot, ale chybí methodology_generation."
        )

    keys = frozenset(view.key for view in views)
    text_by_key = {view.key: view.assertion_text for view in views}
    process_names = {view.process_id: view.process_name for view in views}
    section_names = {
        (view.process_id, view.section_id): view.section_name for view in views
    }

    # Label fallback: assertion_id + process/section names.
    for result in control_results:
        matched = _match_result_to_keys(result, keys, text_by_key=text_by_key)
        if matched is not None:
            continue
        cp = str(result.source_control_point_id or "").strip()
        label_area = str(result.source_area_label or "").strip()
        label_section = str(result.source_section_label or "").strip()
        found = False
        for view in views:
            if view.assertion_id != cp:
                continue
            if (
                view.process_name == label_area
                and view.section_name == label_section
            ):
                found = True
                break
            if (
                process_names.get(view.process_id) == label_area
                and section_names.get((view.process_id, view.section_id)) == label_section
            ):
                found = True
                break
        if not found:
            raise AuditQuestionSourceError(
                f"Audit {audit.id}: control_result id={result.id} "
                f"(cp={result.source_control_point_id!r}) nemá snapshotový protějšek. "
                "Automatický fallback na živou metodiku je zakázán."
            )


class AuditQuestionSourceService:
    """Volba a načtení zdroje otázek pro konkrétní audit."""

    def resolve_for_audit(
        self,
        audit_id: int | None,
        *,
        audit: Audit | None = None,
    ) -> AuditQuestionSource:
        if audit_id is None and audit is None:
            return AuditQuestionSource(mode="live", audit_id=None)

        resolved_id = int(audit.id if audit is not None else audit_id)
        # Preferuj předaný audit jen pro rychlé čtení source markerů mimo session;
        # data vždy načti v aktuální session (bez expunge cizích instancí).
        with get_session() as session:
            db_audit = session.get(Audit, resolved_id)
            if db_audit is None:
                return AuditQuestionSource(mode="live", audit_id=resolved_id)

            source = str(db_audit.methodology_source or "").strip()
            frozen_at = db_audit.questions_frozen_at
            generation = str(db_audit.methodology_generation or "").strip()
            if source != AUDIT_METHODOLOGY_SOURCE_SNAPSHOT:
                if not source:
                    logger.warning(
                        "Audit %s: methodology_source=NULL — legacy živá metodika "
                        "(audit nebyl součástí snapshot backfillu).",
                        resolved_id,
                    )
                return AuditQuestionSource(mode="live", audit_id=resolved_id)

            rows = list(
                session.scalars(
                    select(AuditQuestionSnapshot)
                    .where(AuditQuestionSnapshot.audit_id == resolved_id)
                    .order_by(
                        AuditQuestionSnapshot.display_order,
                        AuditQuestionSnapshot.id,
                    )
                )
            )
            results = list(
                session.scalars(
                    select(ControlResult)
                    .where(
                        ControlResult.entity_type == ENTITY_AUDITY,
                        ControlResult.entity_id == resolved_id,
                    )
                    .order_by(ControlResult.id)
                )
            )
            views = [_row_to_view(row) for row in rows]
            marker_audit = SimpleNamespace(
                id=resolved_id,
                methodology_source=source,
                methodology_generation=generation or None,
                questions_frozen_at=frozen_at,
            )
            _validate_snapshot_consistency(
                marker_audit, views=views, control_results=results
            )

        roots = build_knowledge_tree_from_snapshot_views(views)
        keys = frozenset(view.key for view in views)
        return AuditQuestionSource(
            mode="snapshot",
            audit_id=resolved_id,
            roots=tuple(roots),
            assertions=tuple(views),
            assertion_keys=keys,
            text_by_key={view.key: view.assertion_text for view in views},
            severity_by_key={view.key: view.severity for view in views},
            process_names={
                view.process_id: view.process_name
                for view in views
                if view.process_id
            },
        )

    def assertion_text(
        self,
        source: AuditQuestionSource,
        *,
        process_id: str,
        section_id: str,
        assertion_id: str,
        fallback: str = "",
    ) -> str:
        if not source.is_snapshot:
            return fallback
        key = snapshot_key(process_id, section_id, assertion_id)
        return source.text_by_key.get(key) or fallback


audit_question_source_service = AuditQuestionSourceService()
