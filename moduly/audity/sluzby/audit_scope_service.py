"""Rozsah ručního auditu: vybrané řídicí procesy."""

from __future__ import annotations

from sqlalchemy import delete, select

from core.database.session import get_session
from moduly.audity.constants import (
    AUDIT_SCOPE_REQUIRED_MESSAGE,
    AUDIT_SCOPE_UNAVAILABLE_MESSAGE,
    EXTRAORDINARY_CATEGORY_PROCESS_ID,
)
from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
from moduly.audity.modely.audit_scope_process import AuditScopeProcess
from moduly.audity.sluzby.audit_knowledge_service import (
    KNOWLEDGE_NODE_PROCESS,
    KnowledgeTreeNode,
)


def list_audit_scope_processes(audit_id: int) -> list[AuditScopeProcess]:
    with get_session() as session:
        rows = list(
            session.scalars(
                select(AuditScopeProcess)
                .where(AuditScopeProcess.audit_id == int(audit_id))
                .order_by(AuditScopeProcess.display_order, AuditScopeProcess.id)
            )
        )
        for row in rows:
            session.expunge(row)
        return rows


def snapshot_scope_labels(audit_id: int) -> list[tuple[str, str]]:
    """Procesy skutečně ve snapshotu, v pořadí prvního výskytu."""
    with get_session() as session:
        rows = session.execute(
            select(
                AuditQuestionSnapshot.process_id,
                AuditQuestionSnapshot.process_name,
                AuditQuestionSnapshot.display_order,
            )
            .where(AuditQuestionSnapshot.audit_id == int(audit_id))
            .order_by(AuditQuestionSnapshot.display_order, AuditQuestionSnapshot.id)
        ).all()
    seen: dict[str, str] = {}
    ordered: list[str] = []
    for process_id, process_name, _order in rows:
        key = str(process_id or "").strip()
        if not key or key in seen or key == EXTRAORDINARY_CATEGORY_PROCESS_ID:
            continue
        seen[key] = str(process_name or "").strip() or key
        ordered.append(key)
    return [(key, seen[key]) for key in ordered]


def write_scope_processes(session, audit_id: int, processes: list[dict] | None) -> None:
    """Nahradí rozsah v už otevřené transakci. None nic nezapíše."""
    if processes is None:
        return
    session.execute(
        delete(AuditScopeProcess).where(AuditScopeProcess.audit_id == int(audit_id))
    )
    for index, item in enumerate(processes):
        process_id = str(item.get("process_id") or "").strip()
        if not process_id:
            continue
        session.add(
            AuditScopeProcess(
                audit_id=int(audit_id),
                process_id=process_id,
                process_name=str(item.get("process_name") or "").strip() or process_id,
                display_order=int(item.get("display_order") if item.get("display_order") is not None else index),
            )
        )


def replace_audit_scope_processes(audit_id: int, processes: list[dict]) -> None:
    with get_session() as session:
        try:
            write_scope_processes(session, int(audit_id), processes)
            session.commit()
        except Exception:
            session.rollback()
            raise


def require_manual_planned_process_ids(
    audit_id: int,
    roots: list[KnowledgeTreeNode],
) -> set[str]:
    """Uložený rozsah ručního auditu. Prázdný ani neplatný výběr se nenahrazuje vším."""
    rows = list_audit_scope_processes(int(audit_id))
    if not rows:
        raise ValueError(AUDIT_SCOPE_REQUIRED_MESSAGE)

    active = {
        str(node.process_id or "").strip()
        for node in roots
        if node.node_type == KNOWLEDGE_NODE_PROCESS and str(node.process_id or "").strip()
    }
    missing = [row for row in rows if row.process_id not in active]
    if missing:
        names = ", ".join(row.process_name or row.process_id for row in missing)
        raise ValueError(AUDIT_SCOPE_UNAVAILABLE_MESSAGE.format(names=names))

    return {row.process_id for row in rows}
