"""Adaptér oponentního posouzení AI pro katalog zdrojů rizik (R18f)."""

from __future__ import annotations

from core.ai_oponentni.constants import (
    AI_PEER_REVIEW_DEFAULT_CHANGE_TRACKING,
    AI_PEER_REVIEW_EXPORT_SCOPE_FULL,
    AI_PEER_REVIEW_RESPONSE_SCHEMA_2_0,
    AI_PEER_REVIEW_SCHEMA_VERSION_2_0,
    AI_REVIEW_REQUEST_USER_INSTRUCTION,
    AI_REVIEW_RESPONSE_FILENAME,
)
from core.ai_oponentni.modely.ai_proposal_package import (
    PACKAGE_STATUS_PENDING,
    AiProposalPackageRecord,
)
from core.ai_oponentni.modely.ai_unassigned_proposal import (
    PROPOSAL_STATUS_PENDING,
    AiUnassignedProposal,
)
from core.ai_oponentni.repository.ai_proposal_package_repository import (
    AiProposalPackageRepository,
)
from core.ai_oponentni.repository.ai_unassigned_proposal_repository import (
    AiUnassignedProposalRepository,
)
from core.ai_oponentni.sluzby.ai_peer_review_service import AiPeerReviewError
from core.ai_oponentni.sluzby.prompt_builder import (
    build_catalog_ai_instruction,
    build_catalog_source_ai_peer_review_prompt,
    normalize_catalog_objectives,
    normalize_focus_areas,
    normalize_opponent_role,
    opponent_role_label,
)
from core.ai_oponentni.proposal_package_types import AiProposalPackage
from core.ai_oponentni.types import (
    AiExportSourceChoice,
    AiPeerReviewApplyResult,
    AiPeerReviewBatchContent,
    AiPeerReviewExportContent,
    AiPeerReviewExportOptions,
    AiProposal,
)
from moduly.rizeni_rizik.sluzby.hazard_source_category_service import (
    hazard_source_category_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
    hazard_library_template_assessment_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
    hazard_library_template_event_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
    hazard_library_template_existing_measure_service,
)
from moduly.pravni_pozadavky.constants import legal_document_catalog_link_label
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.rizeni_rizik.sluzby.hazard_library_template_legal_link_service import (
    hazard_library_template_legal_link_service,
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
    evidence_only_import = True
    uses_proposal_packages = True
    exports_single_request_json = True

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
        zadani_json = self._build_request_json(
            hierarchy,
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
            schema_json=AI_PEER_REVIEW_RESPONSE_SCHEMA_2_0,
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

    def apply_proposal_packages(
        self,
        source_id: int,
        packages: list[AiProposalPackage],
        *,
        review_id: int,
    ) -> AiPeerReviewApplyResult:
        if hazard_library_template_service.get_by_id(source_id) is None:
            raise AiPeerReviewError("Zdroj rizika v katalogu neexistuje.")

        records = [
            AiProposalPackageRepository.record_from_package(
                review_id=review_id,
                source_type=self.source_type,
                source_id=source_id,
                package=package,
                status=PACKAGE_STATUS_PENDING,
            )
            for package in packages
            if package.requires_user_decision
        ]
        if records:
            AiProposalPackageRepository().add_many(records)
        return AiPeerReviewApplyResult(
            applied_count=0,
            pending_count=len(records),
            unassigned_count=0,
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
                    proposal_id=(proposal.proposal_id or "").strip(),
                    area=proposal.area or "",
                    name=proposal.name,
                    reasoning=proposal.reasoning or "",
                    parent_export_id=proposal.parent_export_id or "",
                    status=PROPOSAL_STATUS_PENDING,
                )
            )
        if unassigned_models:
            AiUnassignedProposalRepository().add_many(unassigned_models)
        return AiPeerReviewApplyResult(
            applied_count=0,
            pending_count=len(unassigned_models),
            unassigned_count=0,
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
        legal_link_nodes: list[dict] = []
        existing_counter = 0
        required_counter = 0
        assessment_counter = 0
        legal_counter = 0

        for link in hazard_library_template_legal_link_service.get_for_template(
            template.id,
            include_inactive=False,
        ):
            legal_counter += 1
            legal_export_id = f"LEGAL-LINK-{legal_counter:03d}"
            document = None
            if link.legal_document_id is not None:
                document = legal_document_service.get_by_id(link.legal_document_id)
            export_id_map[legal_export_id] = {
                "kind": "legal_link",
                "id": link.id,
            }
            legal_link_nodes.append(
                {
                    "export_id": legal_export_id,
                    "legal_document_id": link.legal_document_id,
                    "legal_document_label": (
                        legal_document_catalog_link_label(document)
                        if document is not None
                        else "—"
                    ),
                    "legal_requirement_id": link.legal_requirement_id,
                    "note": link.note or "",
                }
            )

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
            "category_label": hazard_source_category_service.label_for(
                template.category,
            ),
            "description": template.description or "",
            "version_number": template.version_number,
            "note": template.note or "",
            "events": event_nodes,
            "legal_links": legal_link_nodes,
        }
        catalog_source = {
            "reference": catalog_source_reference(template.id),
            "name": template.name,
            "category": template.category,
            "category_label": risk_source["category_label"],
            "description": template.description or "",
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
        legal_links = len(risk_source.get("legal_links") or [])
        return {
            "sources": 1,
            "events": events,
            "assessments": assessments,
            "existing_measures": existing_measures,
            "required_measures": required_measures,
            "legal_links": legal_links,
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

    def _build_request_json(
        self,
        hierarchy: dict,
        *,
        briefing: dict,
    ) -> dict:
        catalog_source = dict(hierarchy["catalog_source"])
        catalog_source["general_context"] = briefing["general_context"]
        counts = hierarchy["counts"]
        return {
            "schema_version": AI_PEER_REVIEW_SCHEMA_VERSION_2_0,
            "user_instruction": AI_REVIEW_REQUEST_USER_INSTRUCTION,
            "ai_instruction": build_catalog_ai_instruction(
                role=briefing["opponent_role"],
                objectives=briefing["objectives"],
                focus_areas=briefing["focus_areas"],
            ),
            "processing": {
                "output_filename": AI_REVIEW_RESPONSE_FILENAME,
                "language": "cs",
            },
            "response_schema": AI_PEER_REVIEW_RESPONSE_SCHEMA_2_0,
            "source_data": {
                "catalog_source": catalog_source,
                "risk_source": self._public_risk_source(hierarchy["risk_source"]),
                "counts": {
                    "events": counts["events"],
                    "assessments": counts["assessments"],
                    "existing_measures": counts["existing_measures"],
                    "required_measures": counts["required_measures"],
                    "legal_links": counts["legal_links"],
                },
            },
        }

    @staticmethod
    def _public_measure(node: dict) -> dict:
        return {
            "export_id": node.get("export_id") or "",
            "description": node.get("description") or "",
            "note": node.get("note") or "",
        }

    @staticmethod
    def _public_legal_link(node: dict) -> dict:
        reference = (
            str(node.get("legal_document_label") or "").strip()
            or str(node.get("reference") or "").strip()
        )
        return {
            "export_id": node.get("export_id") or "",
            "reference": reference,
            "note": node.get("note") or "",
        }

    @classmethod
    def _public_assessment(cls, node: dict) -> dict:
        return {
            "export_id": node.get("export_id") or "",
            "exposed_group": node.get("exposed_group") or "",
            "severity": node.get("severity") or "",
            "severity_label": node.get("severity_label") or "",
            "conclusion": node.get("conclusion") or "",
            "note": node.get("note") or "",
            "existing_measures": [
                cls._public_measure(measure)
                for measure in node.get("existing_measures") or []
            ],
            "required_measures": [
                cls._public_measure(measure)
                for measure in node.get("required_measures") or []
            ],
        }

    @classmethod
    def _public_event(cls, node: dict) -> dict:
        return {
            "export_id": node.get("export_id") or "",
            "name": node.get("name") or "",
            "description": node.get("description") or "",
            "note": node.get("note") or "",
            "assessments": [
                cls._public_assessment(assessment)
                for assessment in node.get("assessments") or []
            ],
        }

    @classmethod
    def _public_risk_source(cls, risk_source: dict) -> dict:
        return {
            "export_id": risk_source.get("export_id") or "",
            "name": risk_source.get("name") or "",
            "events": [
                cls._public_event(event) for event in risk_source.get("events") or []
            ],
            "legal_links": [
                cls._public_legal_link(link)
                for link in risk_source.get("legal_links") or []
            ],
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
        lines.append(f"Revize: {catalog_source['version_number']}")
        lines.append(f"Poznámka: {catalog_source['note'] or '—'}")
        lines.append("")
        lines.append("HIERARCHIE")
        lines.append("-" * 40)
        lines.append(
            "Zdroj rizika → Právní vazby → Nežádoucí události → Posouzení "
            "→ Zásady bezpečné práce → Kontrolní otázky pro revizi rizik"
        )
        lines.append("")
        lines.append(f"Zdroj rizika [{risk_source['export_id']}]")
        lines.append(risk_source["name"])
        lines.append(f"    Kategorie: {risk_source['category_label']}")
        if risk_source["description"]:
            lines.append(f"    Popis: {risk_source['description']}")
        if risk_source["note"]:
            lines.append(f"    Poznámka: {risk_source['note']}")

        lines.append("")
        lines.append("    Právní vazby")
        if not risk_source.get("legal_links"):
            lines.append("        (žádné)")
        for legal_link in risk_source.get("legal_links") or []:
            label = (
                str(legal_link.get("legal_document_label") or "").strip()
                or str(legal_link.get("legal_requirement_label") or "").strip()
                or "—"
            )
            lines.append(
                f"        [{legal_link.get('export_id') or '—'}] {label}"
            )
            if legal_link.get("note"):
                lines.append(f"            Poznámka: {legal_link['note']}")

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

                lines.append("                    Zásady bezpečné práce")
                if assessment["existing_measures"]:
                    for measure in assessment["existing_measures"]:
                        lines.append(
                            f"                        [{measure['export_id']}] "
                            f"{measure['description']}"
                        )
                else:
                    lines.append("                        (žádná)")

                lines.append("                    Kontrolní otázky pro revizi rizik")
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
            f"Zásady bezpečné práce: {counts['existing_measures']}",
            f"Kontrolní otázky: {counts['required_measures']}",
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
