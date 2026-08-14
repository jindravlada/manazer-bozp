"""Typ ověření auditních tvrzení (Dokumentace / Terén) pro metodiku i audit."""

from __future__ import annotations

from dataclasses import dataclass

from core.shared.verification_type import (
    VERIFICATION_TYPE_DEFAULT,
    VERIFICATION_TYPE_DOCUMENTATION,
    VERIFICATION_TYPE_TERRAIN,
    methodology_verification_type as shared_methodology_verification_type,
    normalize_verification_type as shared_normalize_verification_type,
)
from moduly.audity.repository.audit_verification_override_repository import (
    AuditVerificationOverrideRepository,
)
from moduly.audity.sluzby.audit_knowledge_service import (
    KnowledgeTreeNode,
    audit_knowledge_service,
)


@dataclass(frozen=True)
class AuditAssertionRef:
    """Auditní tvrzení v kontextu auditu včetně efektivního typu ověření."""

    area_id: str
    area_label: str
    section_id: str
    section_label: str
    control_point_id: str
    control_point_label: str
    control_point: dict
    methodology_verification_type: str
    effective_verification_type: str


class AuditVerificationService:
    def __init__(self) -> None:
        self.repository = AuditVerificationOverrideRepository()

    @staticmethod
    def normalize_verification_type(value) -> str:
        return shared_normalize_verification_type(value)

    def methodology_verification_type(self, item: dict | None) -> str:
        return shared_methodology_verification_type(item)

    def overrides_map(self, audit_id: int | None) -> dict[tuple[str, str, str], str]:
        if audit_id is None:
            return {}
        result: dict[tuple[str, str, str], str] = {}
        for row in self.repository.list_for_audit(audit_id):
            key = (
                str(row.source_area_id or "").strip(),
                str(row.source_section_id or "").strip(),
                str(row.source_control_point_id or "").strip(),
            )
            result[key] = self.normalize_verification_type(
                row.override_verification_type
            )
        return result

    def effective_verification_type(
        self,
        audit_id: int | None,
        *,
        area_id: str,
        section_id: str,
        control_point_id: str,
        methodology_type: str | None = None,
        item: dict | None = None,
        overrides: dict[tuple[str, str, str], str] | None = None,
    ) -> str:
        methodology = (
            self.normalize_verification_type(methodology_type)
            if methodology_type is not None
            else self.methodology_verification_type(item)
        )
        mapping = overrides if overrides is not None else self.overrides_map(audit_id)
        override = mapping.get(
            (
                str(area_id or "").strip(),
                str(section_id or "").strip(),
                str(control_point_id or "").strip(),
            )
        )
        if override is None:
            return methodology
        return override

    def set_override(
        self,
        audit_id: int,
        *,
        area_id: str,
        section_id: str,
        control_point_id: str,
        verification_type: str,
        methodology_type: str | None = None,
        item: dict | None = None,
    ) -> str:
        """Nastaví typ ověření pro audit. Vrací efektivní typ.

        Pokud odpovídá metodice, výjimku smaže.
        """
        target = self.normalize_verification_type(verification_type)
        methodology = (
            self.normalize_verification_type(methodology_type)
            if methodology_type is not None
            else self.methodology_verification_type(item)
        )
        area = str(area_id or "").strip()
        section = str(section_id or "").strip()
        point = str(control_point_id or "").strip()
        if not audit_id or not point:
            raise ValueError("Chybí identifikace auditu nebo auditního tvrzení.")

        if target == methodology:
            self.repository.delete(
                audit_id,
                area_id=area,
                section_id=section,
                control_point_id=point,
            )
            return methodology

        self.repository.upsert(
            audit_id,
            area_id=area,
            section_id=section,
            control_point_id=point,
            override_verification_type=target,
        )
        return target

    def filter_assertions(
        self,
        items: list | None,
        *,
        audit_id: int | None,
        area_id: str,
        section_id: str,
        verification_type: str,
        overrides: dict[tuple[str, str, str], str] | None = None,
    ) -> list[dict]:
        wanted = self.normalize_verification_type(verification_type)
        mapping = overrides if overrides is not None else self.overrides_map(audit_id)
        result: list[dict] = []
        for item in audit_knowledge_service.get_active_items(items or []):
            if not isinstance(item, dict):
                continue
            cp_id = str(item.get("id") or "").strip()
            if not cp_id:
                continue
            effective = self.effective_verification_type(
                audit_id,
                area_id=area_id,
                section_id=section_id,
                control_point_id=cp_id,
                item=item,
                overrides=mapping,
            )
            if effective == wanted:
                result.append(item)
        return result

    def list_assertions(
        self,
        audit_id: int | None = None,
        *,
        verification_type: str | None = None,
        process_ids: set[str] | tuple[str, ...] | list[str] | None = None,
        question_source=None,
    ) -> list[AuditAssertionRef]:
        """Aktivní auditní tvrzení s efektivním typem pro audit.

        Při ``question_source.is_snapshot`` bere výhradně snapshot (bez živé metodiky).
        """
        from moduly.audity.sluzby.audit_question_source_service import (
            AuditQuestionSourceError,
            audit_question_source_service,
        )

        wanted = (
            self.normalize_verification_type(verification_type)
            if verification_type is not None
            else None
        )
        allowed = (
            {str(pid).strip() for pid in process_ids if str(pid).strip()}
            if process_ids is not None
            else None
        )
        overrides = self.overrides_map(audit_id)

        source = question_source
        if source is None and audit_id is not None:
            try:
                source = audit_question_source_service.resolve_for_audit(audit_id)
            except AuditQuestionSourceError:
                raise

        if source is not None and source.is_snapshot:
            return self._list_assertions_from_snapshot(
                source,
                audit_id=audit_id,
                overrides=overrides,
                wanted=wanted,
                # Snapshot už je kompletní sada — planned filtr neaplikovat.
                allowed=None,
            )

        items: list[AuditAssertionRef] = []
        for process_node in audit_knowledge_service.get_knowledge_tree():
            process_id = str(process_node.process_id or "").strip()
            if allowed is not None and process_id not in allowed:
                continue
            self._collect_from_nodes(
                process_node.children,
                area_id=process_id,
                area_label=str(process_node.process_label or process_node.label or ""),
                audit_id=audit_id,
                overrides=overrides,
                wanted=wanted,
                sink=items,
            )
        return items

    def _list_assertions_from_snapshot(
        self,
        source,
        *,
        audit_id: int | None,
        overrides: dict[tuple[str, str, str], str],
        wanted: str | None,
        allowed: set[str] | None,
    ) -> list[AuditAssertionRef]:
        items: list[AuditAssertionRef] = []
        for view in source.assertions:
            if allowed is not None and view.process_id not in allowed:
                continue
            methodology = self.normalize_verification_type(view.verification_type)
            effective = self.effective_verification_type(
                audit_id,
                area_id=view.process_id,
                section_id=view.section_id,
                control_point_id=view.assertion_id,
                methodology_type=methodology,
                overrides=overrides,
            )
            if wanted is not None and effective != wanted:
                continue
            raw = {
                "id": view.assertion_id,
                "text": view.assertion_text,
                "nazev": view.assertion_text,
                "zavaznost": view.severity,
                "verification_type": view.verification_type,
                "question_kind": view.question_kind,
                "poradi": view.display_order,
                "aktivni": True,
            }
            items.append(
                AuditAssertionRef(
                    area_id=view.process_id,
                    area_label=view.process_name,
                    section_id=view.section_id,
                    section_label=view.section_name,
                    control_point_id=view.assertion_id,
                    control_point_label=view.assertion_text,
                    control_point=raw,
                    methodology_verification_type=methodology,
                    effective_verification_type=effective,
                )
            )
        return items

    def _collect_from_nodes(
        self,
        nodes: tuple[KnowledgeTreeNode, ...] | list[KnowledgeTreeNode],
        *,
        area_id: str,
        area_label: str,
        audit_id: int | None,
        overrides: dict[tuple[str, str, str], str],
        wanted: str | None,
        sink: list[AuditAssertionRef],
    ) -> None:
        for node in nodes:
            section = node.section
            if isinstance(section, dict):
                section_id = str(section.get("id") or node.node_id or "").strip()
                section_label = str(section.get("nazev") or node.label or "").strip()
                for raw in audit_knowledge_service.get_audit_questions(section):
                    if not isinstance(raw, dict):
                        continue
                    cp_id = str(raw.get("id") or "").strip()
                    cp_label = str(raw.get("nazev") or raw.get("text") or "").strip()
                    if not cp_id or not cp_label:
                        continue
                    methodology = self.methodology_verification_type(raw)
                    effective = self.effective_verification_type(
                        audit_id,
                        area_id=area_id,
                        section_id=section_id,
                        control_point_id=cp_id,
                        methodology_type=methodology,
                        overrides=overrides,
                    )
                    if wanted is not None and effective != wanted:
                        continue
                    sink.append(
                        AuditAssertionRef(
                            area_id=area_id,
                            area_label=area_label,
                            section_id=section_id,
                            section_label=section_label,
                            control_point_id=cp_id,
                            control_point_label=cp_label,
                            control_point=raw,
                            methodology_verification_type=methodology,
                            effective_verification_type=effective,
                        )
                    )
            if node.children:
                self._collect_from_nodes(
                    node.children,
                    area_id=area_id,
                    area_label=area_label,
                    audit_id=audit_id,
                    overrides=overrides,
                    wanted=wanted,
                    sink=sink,
                )


audit_verification_service = AuditVerificationService()

# Re-export for callers that import constants from the service module.
__all__ = [
    "AuditAssertionRef",
    "AuditVerificationService",
    "VERIFICATION_TYPE_DEFAULT",
    "VERIFICATION_TYPE_DOCUMENTATION",
    "VERIFICATION_TYPE_TERRAIN",
    "audit_verification_service",
]
