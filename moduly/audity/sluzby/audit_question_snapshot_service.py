"""Sestavení snapshotu auditních tvrzení (AUDIT-SNAPSHOT-0 / 1a).

Nespouští se automaticky při otevření auditu. Persist řeší backfill služba.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from core.shared.modely.control_result import ControlResult
from moduly.audity.constants import (
    AUDIT_QUESTION_KIND_LEGACY,
    CONTROL_POINT_SEVERITY_DEFAULT,
)
from moduly.audity.sluzby.audit_knowledge_service import (
    KnowledgeTreeNode,
    audit_knowledge_service,
)
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
    from_control_result: bool = False
    is_orphan: bool = False


def snapshot_key(
    process_id: str,
    section_id: str,
    assertion_id: str,
) -> tuple[str, str, str]:
    return (
        str(process_id or "").strip(),
        str(section_id or "").strip(),
        str(assertion_id or "").strip(),
    )


class AuditQuestionSnapshotService:
    """Sestaví snapshot sady otázek pro audit."""

    def build_snapshot_for_audit(
        self,
        audit_id: int,
        *,
        planned_process_ids: set[str] | tuple[str, ...] | list[str] | None = None,
        ensure: bool = True,
        knowledge_tree: list[KnowledgeTreeNode] | None = None,
    ) -> list[AuditQuestionSnapshotDraft]:
        """
        Sestaví snapshot z aktuální metodiky.

        - respektuje ``planned_process_ids`` (None = všechny aktivní procesy);
        - jen aktivní tvrzení;
        - ``verification_type`` = efektivní typ včetně per-audit override Dok/Terén;
        - ``get_knowledge_tree(ensure=…)`` max. jednou, pokud ``knowledge_tree`` není předán.
        """
        if audit_id is None or int(audit_id) <= 0:
            raise ValueError("audit_id musí být kladné číslo.")

        allowed = self._normalize_planned_ids(planned_process_ids)
        roots = knowledge_tree
        if roots is None:
            roots = audit_knowledge_service.get_knowledge_tree(ensure=ensure)

        overrides = audit_verification_service.overrides_map(audit_id)
        return self._build_from_tree(
            int(audit_id),
            roots=roots,
            allowed=allowed,
            overrides=overrides,
        )

    def build_historical_snapshot_for_audit(
        self,
        audit_id: int,
        *,
        control_results: list[ControlResult],
        planned_process_ids: set[str] | tuple[str, ...] | list[str] | None = None,
        ensure: bool = True,
        knowledge_tree: list[KnowledgeTreeNode] | None = None,
        question_kind: str = AUDIT_QUESTION_KIND_LEGACY,
    ) -> list[AuditQuestionSnapshotDraft]:
        """
        Úplný historický snapshot: efektivní metodika ∪ všechny control_results.

        Text u otázek s výsledkem bere z ``control_results.source_*_label``.
        Orphan výsledky mimo metodiku/plán se přidají, nikoli zahodí.
        """
        methodology = self.build_snapshot_for_audit(
            audit_id,
            planned_process_ids=planned_process_ids,
            ensure=ensure,
            knowledge_tree=knowledge_tree,
        )
        return self.merge_methodology_with_control_results(
            audit_id,
            methodology_drafts=methodology,
            control_results=control_results,
            question_kind=question_kind,
        )

    def merge_methodology_with_control_results(
        self,
        audit_id: int,
        *,
        methodology_drafts: list[AuditQuestionSnapshotDraft],
        control_results: list[ControlResult],
        question_kind: str = AUDIT_QUESTION_KIND_LEGACY,
    ) -> list[AuditQuestionSnapshotDraft]:
        by_id: dict[tuple[str, str, str], AuditQuestionSnapshotDraft] = {}
        for draft in methodology_drafts:
            key = snapshot_key(draft.process_id, draft.section_id, draft.assertion_id)
            by_id[key] = replace(draft, question_kind=question_kind or draft.question_kind)

        # Index výsledků podle id i podle (label, label, assertion_id).
        results_by_id: dict[tuple[str, str, str], ControlResult] = {}
        results_by_label: dict[tuple[str, str, str], ControlResult] = {}
        for row in control_results:
            id_key = snapshot_key(
                row.source_area_id,
                row.source_section_id,
                row.source_control_point_id,
            )
            if id_key[2]:
                results_by_id[id_key] = row
            label_key = (
                str(row.source_area_label or "").strip(),
                str(row.source_section_label or "").strip(),
                str(row.source_control_point_id or "").strip(),
            )
            if label_key[2]:
                results_by_label[label_key] = row

        matched_result_ids: set[int] = set()
        merged: list[AuditQuestionSnapshotDraft] = []

        for key, draft in by_id.items():
            row = results_by_id.get(key)
            if row is None:
                row = results_by_label.get(
                    (
                        draft.process_name.strip(),
                        draft.section_name.strip(),
                        draft.assertion_id.strip(),
                    )
                )
            if row is None:
                merged.append(draft)
                continue
            matched_result_ids.add(int(row.id))
            merged.append(
                replace(
                    draft,
                    process_name=str(row.source_area_label or draft.process_name).strip()
                    or draft.process_name,
                    section_name=str(row.source_section_label or draft.section_name).strip()
                    or draft.section_name,
                    assertion_text=str(
                        row.source_control_point_label or draft.assertion_text
                    ).strip()
                    or draft.assertion_text,
                    from_control_result=True,
                    is_orphan=False,
                    question_kind=question_kind,
                )
            )

        order_base = max((item.display_order for item in merged), default=0) + 10
        orphan_index = 0
        for row in control_results:
            if int(row.id) in matched_result_ids:
                continue
            process_id = str(row.source_area_id or "").strip()
            section_id = str(row.source_section_id or "").strip()
            assertion_id = str(row.source_control_point_id or "").strip()
            process_name = str(row.source_area_label or "").strip()
            section_name = str(row.source_section_label or "").strip()
            assertion_text = str(row.source_control_point_label or "").strip()

            if not assertion_id:
                assertion_id = f"orphan_cr_{row.id}"
            if not process_id:
                process_id = f"orphan_process_{row.id}"
            if not section_id:
                section_id = f"orphan_section_{row.id}"
            if not assertion_text:
                assertion_text = f"(historický výsledek #{row.id})"

            orphan_key = snapshot_key(process_id, section_id, assertion_id)
            if orphan_key in {snapshot_key(m.process_id, m.section_id, m.assertion_id) for m in merged}:
                # Kolize s metodikou — použij unikátní assertion_id.
                assertion_id = f"{assertion_id}__cr{row.id}"
                orphan_key = snapshot_key(process_id, section_id, assertion_id)

            merged.append(
                AuditQuestionSnapshotDraft(
                    audit_id=int(audit_id),
                    process_id=process_id,
                    process_name=process_name or process_id,
                    section_id=section_id,
                    section_name=section_name or section_id,
                    assertion_id=assertion_id,
                    assertion_text=assertion_text,
                    verification_type=audit_verification_service.normalize_verification_type(
                        None
                    ),
                    severity=CONTROL_POINT_SEVERITY_DEFAULT,
                    question_kind=question_kind,
                    display_order=order_base + orphan_index,
                    from_control_result=True,
                    is_orphan=True,
                )
            )
            orphan_index += 1

        merged.sort(
            key=lambda item: (
                item.display_order,
                item.process_name.lower(),
                item.section_name.lower(),
                item.assertion_text.lower(),
                item.assertion_id,
            )
        )
        return merged

    @staticmethod
    def _normalize_planned_ids(
        planned_process_ids: set[str] | tuple[str, ...] | list[str] | None,
    ) -> set[str] | None:
        if planned_process_ids is None:
            return None
        return {
            str(process_id).strip()
            for process_id in planned_process_ids
            if str(process_id).strip()
        }

    def _build_from_tree(
        self,
        audit_id: int,
        *,
        roots: list[KnowledgeTreeNode],
        allowed: set[str] | None,
        overrides: dict[tuple[str, str, str], str],
    ) -> list[AuditQuestionSnapshotDraft]:
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
                audit_id=audit_id,
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
                        display_order = (
                            int(raw_order) if raw_order is not None else order_counter
                        )
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
