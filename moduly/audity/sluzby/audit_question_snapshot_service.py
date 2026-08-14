"""Sestavení snapshotu auditních tvrzení z aktuální metodiky (AUDIT-SNAPSHOT-0).

V této fázi služba pouze sestaví sadu v paměti. Nespouští se automaticky
při startu, otevření ani vytvoření auditu. Neprovádí backfill.
"""

from __future__ import annotations

from dataclasses import dataclass

from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_verification_service import (
    audit_verification_service,
)


@dataclass(frozen=True)
class AuditQuestionSnapshotDraft:
    """Jedno tvrzení připravené ke zmrazení (zatím bez zápisu do DB)."""

    audit_id: int
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


class AuditQuestionSnapshotService:
    """Sestaví snapshot sady otázek pro audit z živé metodiky."""

    def build_snapshot_for_audit(
        self,
        audit_id: int,
        *,
        planned_process_ids: set[str] | tuple[str, ...] | list[str] | None = None,
        ensure: bool = True,
    ) -> list[AuditQuestionSnapshotDraft]:
        """
        Sestaví snapshot z aktuální metodiky.

        - respektuje ``planned_process_ids`` (None = všechny aktivní procesy);
        - jen aktivní tvrzení;
        - ``verification_type`` = efektivní typ včetně per-audit override Dok/Terén;
        - ``get_knowledge_tree(ensure=…)`` max. jednou (AUDIT-HANG-FIX-1).
        """
        if audit_id is None or int(audit_id) <= 0:
            raise ValueError("audit_id musí být kladné číslo.")

        allowed: set[str] | None
        if planned_process_ids is None:
            allowed = None
        else:
            allowed = {
                str(process_id).strip()
                for process_id in planned_process_ids
                if str(process_id).strip()
            }

        # Jedno načtení stromu — stejná optimalizace jako c952bf6.
        roots = audit_knowledge_service.get_knowledge_tree(ensure=ensure)
        overrides = audit_verification_service.overrides_map(audit_id)

        drafts: list[AuditQuestionSnapshotDraft] = []
        order_counter = 0
        for process_node in roots:
            process_id = str(process_node.process_id or "").strip()
            if allowed is not None and process_id not in allowed:
                continue
            process_name = str(
                process_node.process_label or process_node.label or ""
            ).strip()
            order_counter = self._collect_from_nodes(
                process_node.children,
                audit_id=int(audit_id),
                process_id=process_id,
                process_name=process_name,
                overrides=overrides,
                drafts=drafts,
                order_counter=order_counter,
            )
        return drafts

    def _collect_from_nodes(
        self,
        nodes,
        *,
        audit_id: int,
        process_id: str,
        process_name: str,
        overrides: dict[tuple[str, str, str], str],
        drafts: list[AuditQuestionSnapshotDraft],
        order_counter: int,
    ) -> int:
        for node in nodes:
            section = node.section
            if isinstance(section, dict):
                section_id = str(section.get("id") or node.node_id or "").strip()
                section_name = str(section.get("nazev") or node.label or "").strip()
                for raw in audit_knowledge_service.get_audit_questions(section):
                    if not isinstance(raw, dict):
                        continue
                    assertion_id = str(raw.get("id") or "").strip()
                    assertion_text = str(
                        raw.get("text") or raw.get("nazev") or ""
                    ).strip()
                    if not assertion_id or not assertion_text:
                        continue

                    methodology = audit_verification_service.methodology_verification_type(
                        raw
                    )
                    effective = audit_verification_service.effective_verification_type(
                        audit_id,
                        area_id=process_id,
                        section_id=section_id,
                        control_point_id=assertion_id,
                        methodology_type=methodology,
                        overrides=overrides,
                    )
                    severity = audit_knowledge_service.get_control_point_severity(raw)
                    question_kind = str(raw.get("question_kind") or "").strip()
                    raw_order = raw.get("poradi")
                    try:
                        display_order = int(raw_order) if raw_order is not None else order_counter
                    except (TypeError, ValueError):
                        display_order = order_counter
                    order_counter += 1

                    drafts.append(
                        AuditQuestionSnapshotDraft(
                            audit_id=audit_id,
                            process_id=process_id,
                            process_name=process_name,
                            section_id=section_id,
                            section_name=section_name,
                            assertion_id=assertion_id,
                            assertion_text=assertion_text,
                            verification_type=effective,
                            severity=severity,
                            question_kind=question_kind,
                            display_order=display_order,
                        )
                    )

            if node.children:
                order_counter = self._collect_from_nodes(
                    node.children,
                    audit_id=audit_id,
                    process_id=process_id,
                    process_name=process_name,
                    overrides=overrides,
                    drafts=drafts,
                    order_counter=order_counter,
                )
        return order_counter


audit_question_snapshot_service = AuditQuestionSnapshotService()
