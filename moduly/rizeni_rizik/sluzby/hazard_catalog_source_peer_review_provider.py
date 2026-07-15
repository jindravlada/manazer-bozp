"""Adaptér oponentního posouzení AI pro katalog zdrojů rizik (R18f)."""

from __future__ import annotations

from datetime import datetime

from core.ai_oponentni.constants import (
    AI_CATALOG_PEER_REVIEW_EXPORT_TYPE,
    AI_PEER_REVIEW_DEFAULT_CHANGE_TRACKING,
    AI_PEER_REVIEW_EXPORT_SCOPE_FULL,
    AI_PEER_REVIEW_FOCUS_AREA_LABELS,
    AI_PEER_REVIEW_OBJECTIVE_LABELS,
    AI_PEER_REVIEW_RESPONSE_SCHEMA,
    AI_PEER_REVIEW_SCHEMA_VERSION,
)
from core.ai_oponentni.modely.ai_unassigned_proposal import (
    UNASSIGNED_PROPOSAL_STATUS,
    AiUnassignedProposal,
)
from core.ai_oponentni.repository.ai_unassigned_proposal_repository import (
    AiUnassignedProposalRepository,
)
from core.ai_oponentni.sluzby.ai_peer_review_service import AiPeerReviewError
from core.ai_oponentni.sluzby.prompt_builder import (
    build_catalog_source_ai_peer_review_prompt,
    normalize_catalog_objectives,
    normalize_focus_areas,
    normalize_opponent_role,
    opponent_role_label,
)
from core.ai_oponentni.types import (
    AiExportSourceChoice,
    AiPeerReviewApplyResult,
    AiPeerReviewBatchContent,
    AiPeerReviewExportContent,
    AiPeerReviewExportOptions,
    AiProposal,
)
from core.version import APP_VERSION
from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_LABELS
from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_LABELS
from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
    hazard_library_template_assessment_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
    hazard_library_template_event_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
    hazard_library_template_existing_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
    hazard_library_template_required_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
    hazard_library_template_service,
)

SOURCE_TYPE_HAZARD_CATALOG_SOURCE = "hazard_catalog_source"


def catalog_source_reference(template_id: int) -> str:
    return f"KZR-{template_id:04d}"


class HazardCatalogSourcePeerReviewProvider:
    source_type = SOURCE_TYPE_HAZARD_CATALOG_SOURCE

    def can_export(self, source_id: int | None) -> bool:
        if not source_id:
            return False
        return hazard_library_template_service.get_by_id(source_id) is not None

    def get_source_label(self, source_id: int) -> str:
        template = hazard_library_template_service.get_by_id(source_id)
        if template is None:
            return ""
        return catalog_source_reference(template.id)

    def get_export_source_choices(self, source_id: int) -> list[AiExportSourceChoice]:
        return []

    def build_export_content(
        self,
        source_id: int,
        *,
        options: AiPeerReviewExportOptions,
    ) -> AiPeerReviewExportContent:
        template = hazard_library_template_service.get_by_id(source_id)
        if template is None:
            raise AiPeerReviewError("Zdroj rizika v katalogu neexistuje.")

        built = self._build_hierarchy(template)
        briefing = self._build_peer_review_briefing(template, options)
        prompt_text = build_catalog_source_ai_peer_review_prompt(
            role=briefing["opponent_role"],
            objectives=briefing["objectives"],
            focus_areas=briefing["focus_areas"],
            general_context=briefing["general_context"],
        )
        hierarchy = {
            "catalog_source": built["catalog_source"],
            "risk_source": built["risk_source"],
            "export_id_map": built["export_id_map"],
            "counts": built["counts"],
        }
        data_text = self._hierarchy_to_data_text(hierarchy)
        overview_text, summary_lines = self._build_overview(hierarchy)
        object_count = self._count_objects(built["risk_source"])
        zadani_json = self._hierarchy_to_zadani_json(
            hierarchy,
            object_count=object_count,
            briefing=briefing,
        )
        batch = AiPeerReviewBatchContent(
            batch_number=1,
            source_count=1,
            object_count=object_count,
            recommended_limit_exceeded=False,
            source_names=[template.name],
            prompt_text=prompt_text,
            data_text=data_text,
            overview_text=overview_text,
            summary_lines=summary_lines,
            zadani_json=zadani_json,
            schema_json=AI_PEER_REVIEW_RESPONSE_SCHEMA,
        )
        return AiPeerReviewExportContent(
            source_label=catalog_source_reference(template.id),
            export_id_map=built["export_id_map"],
            export_scope=AI_PEER_REVIEW_EXPORT_SCOPE_FULL,
            batch_count=1,
            selected_source_count=1,
            total_object_count=object_count,
            batches=[batch],
            change_tracking=dict(AI_PEER_REVIEW_DEFAULT_CHANGE_TRACKING),
        )

    def apply_proposals(
        self,
        source_id: int,
        proposals: list[AiProposal],
        *,
        review_id: int,
        export_id_map: dict[str, dict],
    ) -> AiPeerReviewApplyResult:
        if hazard_library_template_service.get_by_id(source_id) is None:
            raise AiPeerReviewError("Zdroj rizika v katalogu neexistuje.")

        unassigned_models: list[AiUnassignedProposal] = []
        for proposal in proposals:
            unassigned_models.append(
                AiUnassignedProposal(
                    ai_peer_review_id=review_id,
                    source_type=self.source_type,
                    source_id=source_id,
                    area=proposal.area or "",
                    name=proposal.name,
                    reasoning=proposal.reasoning or "",
                    parent_export_id=proposal.parent_export_id or "",
                    status=UNASSIGNED_PROPOSAL_STATUS,
                )
            )
        if unassigned_models:
            AiUnassignedProposalRepository().add_many(unassigned_models)
        return AiPeerReviewApplyResult(
            applied_count=0,
            unassigned_count=len(unassigned_models),
        )

    def _build_hierarchy(self, template) -> dict:
        source_export_id = "SOURCE-001"
        export_id_map: dict[str, dict] = {
            source_export_id: {"kind": "source", "id": template.id},
        }

        events = hazard_library_template_event_service.get_for_template(
            template.id,
            include_inactive=False,
        )
        event_nodes: list[dict] = []
        existing_counter = 0
        required_counter = 0
        assessment_counter = 0

        for event_index, event in enumerate(events, start=1):
            event_export_id = f"EVENT-{event_index:03d}"
            export_id_map[event_export_id] = {"kind": "event", "id": event.id}

            assessment_nodes: list[dict] = []
            assessment_rows = hazard_library_template_assessment_service.get_for_event(
                event.id,
                include_inactive=False,
            )
            for assessment_row in assessment_rows:
                assessment_counter += 1
                assessment = assessment_row.assessment
                assessment_export_id = f"ASSESSMENT-{assessment_counter:03d}"
                export_id_map[assessment_export_id] = {
                    "kind": "assessment",
                    "id": assessment.id,
                }

                existing_measures: list[dict] = []
                for measure in hazard_library_template_existing_measure_service.get_for_assessment(
                    assessment.id,
                    include_inactive=False,
                ):
                    existing_counter += 1
                    measure_export_id = f"EXISTING-MEASURE-{existing_counter:03d}"
                    export_id_map[measure_export_id] = {
                        "kind": "existing_measure",
                        "id": measure.id,
                    }
                    existing_measures.append(
                        {
                            "export_id": measure_export_id,
                            "description": measure.description,
                            "note": measure.note or "",
                        }
                    )

                required_measures: list[dict] = []
                for measure in hazard_library_template_required_measure_service.get_for_assessment(
                    assessment.id,
                    include_inactive=False,
                ):
                    required_counter += 1
                    measure_export_id = f"REQUIRED-MEASURE-{required_counter:03d}"
                    export_id_map[measure_export_id] = {
                        "kind": "required_measure",
                        "id": measure.id,
                    }
                    required_measures.append(
                        {
                            "export_id": measure_export_id,
                            "description": measure.description,
                            "note": measure.note or "",
                        }
                    )

                assessment_nodes.append(
                    {
                        "export_id": assessment_export_id,
                        "exposed_group": assessment_row.exposed_group_name,
                        "consequence": assessment.consequence or "",
                        "severity": assessment.severity,
                        "severity_label": assessment_row.severity_label,
                        "conclusion": assessment.conclusion or "",
                        "note": assessment.note or "",
                        "existing_measures": existing_measures,
                        "required_measures": required_measures,
                    }
                )

            event_nodes.append(
                {
                    "export_id": event_export_id,
                    "name": event.name,
                    "description": event.description or "",
                    "note": event.note or "",
                    "assessments": assessment_nodes,
                }
            )

        risk_source = {
            "export_id": source_export_id,
            "name": template.name,
            "category": template.category,
            "category_label": HAZARD_INVENTORY_CATEGORY_LABELS.get(
                template.category,
                template.category,
            ),
            "description": template.description or "",
            "application_scope": template.application_scope,
            "application_scope_label": HAZARD_LIBRARY_SCOPE_LABELS.get(
                template.application_scope,
                template.application_scope,
            ),
            "version_number": template.version_number,
            "note": template.note or "",
            "events": event_nodes,
        }
        catalog_source = {
            "reference": catalog_source_reference(template.id),
            "name": template.name,
            "category": template.category,
            "category_label": risk_source["category_label"],
            "description": template.description or "",
            "application_scope": template.application_scope,
            "application_scope_label": risk_source["application_scope_label"],
            "version_number": template.version_number,
            "note": template.note or "",
        }
        counts = self._count_nodes(risk_source)
        return {
            "catalog_source": catalog_source,
            "risk_source": risk_source,
            "export_id_map": export_id_map,
            "counts": counts,
        }

    @staticmethod
    def _count_nodes(risk_source: dict) -> dict[str, int]:
        events = 0
        assessments = 0
        existing_measures = 0
        required_measures = 0
        for event_node in risk_source.get("events") or []:
            events += 1
            for assessment_node in event_node.get("assessments") or []:
                assessments += 1
                existing_measures += len(assessment_node.get("existing_measures") or [])
                required_measures += len(assessment_node.get("required_measures") or [])
        return {
            "sources": 1,
            "events": events,
            "assessments": assessments,
            "existing_measures": existing_measures,
            "required_measures": required_measures,
        }

    @staticmethod
    def _count_objects(risk_source: dict) -> int:
        counts = HazardCatalogSourcePeerReviewProvider._count_nodes(risk_source)
        return (
            counts["sources"]
            + counts["events"]
            + counts["assessments"]
            + counts["existing_measures"]
            + counts["required_measures"]
        )

    def _build_peer_review_briefing(self, template, options: AiPeerReviewExportOptions) -> dict:
        role = normalize_opponent_role(options.opponent_role)
        objectives = normalize_catalog_objectives(options.objectives)
        focus_areas = normalize_focus_areas(options.focus_areas)
        general_context = " ".join(
            (options.workplace_characteristics or "").split()
        ).strip()
        return {
            "opponent_role": role,
            "opponent_role_label": opponent_role_label(role),
            "objectives": objectives,
            "focus_areas": focus_areas,
            "general_context": general_context,
            "catalog_source_reference": catalog_source_reference(template.id),
        }

    def _hierarchy_to_zadani_json(
        self,
        hierarchy: dict,
        *,
        object_count: int,
        briefing: dict,
    ) -> dict:
        return {
            "schema_version": AI_PEER_REVIEW_SCHEMA_VERSION,
            "export_type": AI_CATALOG_PEER_REVIEW_EXPORT_TYPE,
            "export_scope": AI_PEER_REVIEW_EXPORT_SCOPE_FULL,
            "batch_number": 1,
            "batch_count": 1,
            "source_count": 1,
            "object_count": object_count,
            "recommended_limit_exceeded": False,
            "change_tracking": dict(AI_PEER_REVIEW_DEFAULT_CHANGE_TRACKING),
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "application_version": APP_VERSION,
            "opponent_role": briefing["opponent_role"],
            "opponent_role_label": briefing["opponent_role_label"],
            "peer_review_objectives": list(briefing["objectives"]),
            "peer_review_objective_labels": [
                AI_PEER_REVIEW_OBJECTIVE_LABELS[item_id]
                for item_id in briefing["objectives"]
            ],
            "peer_review_focus_areas": list(briefing["focus_areas"]),
            "peer_review_focus_area_labels": [
                AI_PEER_REVIEW_FOCUS_AREA_LABELS[item_id]
                for item_id in briefing["focus_areas"]
            ],
            "general_context": briefing["general_context"],
            "catalog_source": dict(hierarchy["catalog_source"]),
            "risk_source": hierarchy["risk_source"],
            "hierarchy": [
                "source",
                "event",
                "assessment",
                "existing_measure",
                "required_measure",
            ],
            "consultation_request": {
                "request_summary": (
                    "Proveď oponentní posouzení katalogového zdroje rizika "
                    "a navrhni možné opomenuté položky."
                ),
                "opponent_role": briefing["opponent_role"],
                "opponent_role_label": briefing["opponent_role_label"],
                "objectives": list(briefing["objectives"]),
                "focus_areas": list(briefing["focus_areas"]),
                "rules": [
                    "Nehodnotit závažnost rizik.",
                    "Neměnit existující položky.",
                    "U návrhů uvádět parent_export_id "
                    "(SOURCE/EVENT/ASSESSMENT/EXISTING-MEASURE/REQUIRED-MEASURE).",
                    "Ke každému návrhu uvést stručné odborné zdůvodnění.",
                    "Posuzovat podle aktuálně platných právních předpisů ČR v oblasti BOZP.",
                ],
            },
        }

    def _hierarchy_to_data_text(self, hierarchy: dict) -> str:
        catalog_source = hierarchy["catalog_source"]
        risk_source = hierarchy["risk_source"]
        lines: list[str] = []
        lines.append("KATALOG ZDROJŮ RIZIK – HIERARCHICKÉ PODKLADY PRO AI")
        lines.append("=" * 60)
        lines.append("")
        lines.append("ZÁKLADNÍ ÚDAJE ZDROJE")
        lines.append("-" * 40)
        lines.append(f"Reference: {catalog_source['reference']}")
        lines.append(f"Název: {catalog_source['name']}")
        lines.append(f"Kategorie: {catalog_source['category_label']}")
        lines.append(f"Popis: {catalog_source['description'] or '—'}")
        lines.append(f"Rozsah použití: {catalog_source['application_scope_label']}")
        lines.append(f"Verze: {catalog_source['version_number']}")
        lines.append(f"Poznámka: {catalog_source['note'] or '—'}")
        lines.append("")
        lines.append("HIERARCHIE")
        lines.append("-" * 40)
        lines.append(
            "Zdroj rizika → Nežádoucí události → Posouzení "
            "→ Existující opatření → Potřebná opatření"
        )
        lines.append("")
        lines.append(f"Zdroj rizika [{risk_source['export_id']}]")
        lines.append(risk_source["name"])
        lines.append(f"    Kategorie: {risk_source['category_label']}")
        if risk_source["description"]:
            lines.append(f"    Popis: {risk_source['description']}")
        if risk_source["note"]:
            lines.append(f"    Poznámka: {risk_source['note']}")

        if not risk_source["events"]:
            lines.append("    Událost: (žádná)")
        for event in risk_source["events"]:
            lines.append("")
            lines.append("    Událost")
            lines.append(f"        [{event['export_id']}] {event['name']}")
            if event["description"]:
                lines.append(f"            Popis: {event['description']}")
            if event["note"]:
                lines.append(f"            Poznámka: {event['note']}")

            if not event["assessments"]:
                lines.append("            Posouzení: (žádné)")
            for assessment in event["assessments"]:
                lines.append("")
                lines.append("            Posouzení")
                lines.append(
                    f"                [{assessment['export_id']}] "
                    f"{assessment['exposed_group']}"
                )
                lines.append(
                    "                    Možný následek: "
                    f"{assessment['consequence'] or '—'}"
                )
                lines.append(
                    "                    Závažnost: "
                    f"{assessment['severity_label']}"
                )
                if assessment["conclusion"]:
                    lines.append(
                        "                    Závěr: "
                        f"{assessment['conclusion']}"
                    )
                if assessment["note"]:
                    lines.append(
                        "                    Poznámka: "
                        f"{assessment['note']}"
                    )

                lines.append("                    Existující opatření")
                if assessment["existing_measures"]:
                    for measure in assessment["existing_measures"]:
                        lines.append(
                            f"                        [{measure['export_id']}] "
                            f"{measure['description']}"
                        )
                else:
                    lines.append("                        (žádná)")

                lines.append("                    Potřebná opatření")
                if assessment["required_measures"]:
                    for measure in assessment["required_measures"]:
                        lines.append(
                            f"                        [{measure['export_id']}] "
                            f"{measure['description']}"
                        )
                else:
                    lines.append("                        (žádná)")
        lines.append("")
        return "\n".join(lines)

    def _build_overview(self, hierarchy: dict) -> tuple[str, list[str]]:
        catalog_source = hierarchy["catalog_source"]
        counts = hierarchy["counts"]
        summary_lines = [
            f"Zdroje rizika: {counts['sources']}",
            f"Nežádoucí události: {counts['events']}",
            f"Posouzení rizik: {counts['assessments']}",
            f"Existující opatření: {counts['existing_measures']}",
            f"Potřebná opatření: {counts['required_measures']}",
        ]
        overview = "\n".join(
            [
                "Přehled exportu – oponentní posouzení katalogového zdroje rizika",
                "===============================================================",
                "",
                f"Reference zdroje: {catalog_source['reference']}",
                f"Název: {catalog_source['name']}",
                "",
                *summary_lines,
                "",
                "Hierarchie: Zdroj → Události → Posouzení → Opatření",
                "",
                "Soubor slouží pouze pro orientaci uživatele.",
                "",
            ]
        )
        return overview, summary_lines


hazard_catalog_source_peer_review_provider = HazardCatalogSourcePeerReviewProvider()
