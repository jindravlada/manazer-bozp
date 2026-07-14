"""Adaptér oponentního posouzení AI pro identifikaci nebezpečí."""

from __future__ import annotations

from datetime import datetime

from core.ai_oponentni.constants import (
    AI_PEER_REVIEW_DEFAULT_CHANGE_TRACKING,
    AI_PEER_REVIEW_EXPORT_SCOPE_FULL,
    AI_PEER_REVIEW_EXPORT_SCOPE_SELECTED,
    AI_PEER_REVIEW_EXPORT_TYPE,
    AI_PEER_REVIEW_MAX_OBJECTS_PER_BATCH,
    AI_PEER_REVIEW_MAX_SOURCES_PER_BATCH,
    AI_PEER_REVIEW_RESPONSE_SCHEMA,
    AI_PEER_REVIEW_SCHEMA_VERSION,
    DEFAULT_AI_PEER_REVIEW_PROMPT,
)
from core.ai_oponentni.modely.ai_unassigned_proposal import (
    UNASSIGNED_PROPOSAL_STATUS,
    AiUnassignedProposal,
)
from core.ai_oponentni.repository.ai_unassigned_proposal_repository import (
    AiUnassignedProposalRepository,
)
from core.ai_oponentni.sluzby.ai_peer_review_service import AiPeerReviewError
from core.ai_oponentni.sluzby.batch_planner import (
    ExportBranch,
    count_hierarchy_objects,
    plan_export_batches,
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
from moduly.rizeni_rizik.constants import (
    HAZARD_IDENTIFICATION_STATUS_LABELS,
    HAZARD_INVENTORY_CATEGORIES,
    HAZARD_INVENTORY_CATEGORY_LABELS,
    HAZARD_INVENTORY_CATEGORY_OTHER,
    RISK_ASSESSMENT_STATUS_LABELS,
    RISK_SEVERITY_MODERATE,
    format_risk_severity_label,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import (
    HazardEventError,
    hazard_event_service,
)
from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
    HazardExistingMeasureError,
    hazard_existing_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    hazard_identification_service,
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
    HazardInventoryItemError,
    hazard_inventory_item_service,
)
from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
    HazardRequiredMeasureError,
    hazard_required_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    HazardRiskAssessmentError,
    hazard_risk_assessment_service,
)

SOURCE_TYPE_HAZARD_IDENTIFICATION = "hazard_identification"


class HazardIdentificationPeerReviewProvider:
    source_type = SOURCE_TYPE_HAZARD_IDENTIFICATION

    def can_export(self, source_id: int | None) -> bool:
        if not source_id:
            return False
        return hazard_identification_service.get_by_id(source_id) is not None

    def get_export_source_choices(self, source_id: int) -> list[AiExportSourceChoice]:
        items = hazard_inventory_item_service.get_for_identification(
            source_id,
            include_inactive=False,
        )
        sorted_items = self._sort_analysis_sources(items)
        return [
            AiExportSourceChoice(
                id=item.id,
                label=item.name,
                category_label=HAZARD_INVENTORY_CATEGORY_LABELS.get(
                    item.category,
                    item.category,
                ),
            )
            for item in sorted_items
        ]

    def build_export_content(
        self,
        source_id: int,
        *,
        options: AiPeerReviewExportOptions,
    ) -> AiPeerReviewExportContent:
        identification = hazard_identification_service.get_by_id(source_id)
        if identification is None:
            raise AiPeerReviewError("Identifikace nebezpečí neexistuje.")

        export_scope = (options.export_scope or AI_PEER_REVIEW_EXPORT_SCOPE_FULL).strip()
        if export_scope not in (
            AI_PEER_REVIEW_EXPORT_SCOPE_FULL,
            AI_PEER_REVIEW_EXPORT_SCOPE_SELECTED,
        ):
            export_scope = AI_PEER_REVIEW_EXPORT_SCOPE_FULL

        all_items = hazard_inventory_item_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        sorted_items = self._sort_analysis_sources(all_items)

        if export_scope == AI_PEER_REVIEW_EXPORT_SCOPE_SELECTED:
            selected_ids = {
                int(item_id) for item_id in (options.selected_source_ids or [])
            }
            if not selected_ids:
                raise AiPeerReviewError("Vyberte alespoň jeden zdroj analýzy.")
            items = [item for item in sorted_items if item.id in selected_ids]
            if not items:
                raise AiPeerReviewError(
                    "Vybrané zdroje analýzy nejsou aktivní nebo neexistují."
                )
        else:
            items = sorted_items

        if not items:
            raise AiPeerReviewError(
                "Identifikace neobsahuje žádný aktivní zdroj analýzy. "
                "Export nelze vytvořit."
            )

        built = self._build_hierarchy(
            identification,
            items=items,
            include_responsible_person=options.include_responsible_person,
        )
        branches = [
            ExportBranch(
                source_id=item_node["_source_id"],
                source_name=item_node["name"],
                object_count=count_hierarchy_objects(item_node),
                node=item_node,
            )
            for item_node in built["workplace_analysis"]
        ]
        plans = plan_export_batches(branches)
        batch_count = len(plans)
        change_tracking = dict(AI_PEER_REVIEW_DEFAULT_CHANGE_TRACKING)

        batches: list[AiPeerReviewBatchContent] = []
        for plan in plans:
            batch_nodes = [self._strip_internal_node_fields(branch.node) for branch in plan.branches]
            hierarchy = {
                "identification": built["identification"],
                "workplace_analysis": batch_nodes,
                "export_id_map": built["export_id_map"],
                "counts": self._count_nodes(batch_nodes),
            }
            data_text = self._hierarchy_to_data_text(hierarchy)
            overview_text, summary_lines = self._build_overview(
                hierarchy,
                batch_number=plan.batch_number,
                batch_count=batch_count,
            )
            zadani_json = self._hierarchy_to_zadani_json(
                hierarchy,
                export_scope=export_scope,
                batch_number=plan.batch_number,
                batch_count=batch_count,
                source_count=plan.source_count,
                object_count=plan.object_count,
                recommended_limit_exceeded=plan.recommended_limit_exceeded,
                change_tracking=change_tracking,
            )
            batches.append(
                AiPeerReviewBatchContent(
                    batch_number=plan.batch_number,
                    source_count=plan.source_count,
                    object_count=plan.object_count,
                    recommended_limit_exceeded=plan.recommended_limit_exceeded,
                    source_names=list(plan.source_names),
                    prompt_text=DEFAULT_AI_PEER_REVIEW_PROMPT,
                    data_text=data_text,
                    overview_text=overview_text,
                    summary_lines=summary_lines,
                    zadani_json=zadani_json,
                    schema_json=AI_PEER_REVIEW_RESPONSE_SCHEMA,
                )
            )

        total_object_count = sum(batch.object_count for batch in batches)
        overview_batches = self._build_batches_overview(
            identification_number=identification.identification_number,
            batches=batches,
            export_scope=export_scope,
        )

        return AiPeerReviewExportContent(
            source_label=identification.identification_number,
            export_id_map=built["export_id_map"],
            export_scope=export_scope,
            batch_count=batch_count,
            selected_source_count=len(items),
            total_object_count=total_object_count,
            batches=batches,
            batches_overview_text=overview_batches,
            change_tracking=change_tracking,
        )

    def apply_proposals(
        self,
        source_id: int,
        proposals: list[AiProposal],
        *,
        review_id: int,
        export_id_map: dict[str, dict],
    ) -> AiPeerReviewApplyResult:
        identification = hazard_identification_service.get_by_id(source_id)
        if identification is None:
            raise AiPeerReviewError("Identifikace nebezpečí neexistuje.")

        applied = 0
        unassigned_models: list[AiUnassignedProposal] = []
        for proposal in proposals:
            try:
                outcome = self._apply_one(source_id, proposal, export_id_map)
            except (
                HazardInventoryItemError,
                HazardEventError,
                HazardRiskAssessmentError,
                HazardExistingMeasureError,
                HazardRequiredMeasureError,
                ValueError,
            ):
                outcome = "unassigned"
            if outcome == "applied":
                applied += 1
            else:
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
            applied_count=applied,
            unassigned_count=len(unassigned_models),
        )

    def _apply_one(
        self,
        source_id: int,
        proposal: AiProposal,
        export_id_map: dict[str, dict],
    ) -> str:
        """Vrátí 'applied' nebo 'unassigned'. Nikdy nepřipojuje k prvnímu nalezenému."""
        area = (proposal.area or "").casefold()
        note = f"Návrh z AI oponentního posouzení.\n{proposal.reasoning}".strip()
        parent_id = (proposal.parent_export_id or "").strip()
        parent = export_id_map.get(parent_id) if parent_id else None

        # Nová položka analýzy pracoviště – kořen, rodič není povinný.
        if self._area_matches(
            area,
            (
                "zdroj",
                "analýza",
                "analyza",
                "zařízení",
                "zarizeni",
                "činnost",
                "cinnost",
                "položka",
                "polozka",
            ),
        ):
            if parent_id and parent is None:
                return "unassigned"
            if parent_id and parent is not None and parent.get("kind") != "item":
                # Rodič uveden, ale není položka analýzy – nezařazeno
                # (nová položka nemá rodiče v této hierarchii)
                pass
            hazard_inventory_item_service.create_item(
                hazard_identification_id=source_id,
                category=HAZARD_INVENTORY_CATEGORY_OTHER,
                name=proposal.name,
                description=note,
            )
            return "applied"

        # Entita Nebezpečí odstraněna (R12) – návrhy v této oblasti nezařazovat.
        if self._area_matches(area, ("nebezpeč", "nebezpec")):
            return "unassigned"

        # Souvislosti odstraněny (R14) – návrhy v této oblasti nezařazovat.
        if self._area_matches(area, ("souvislost", "souvislosti")):
            return "unassigned"

        if self._area_matches(area, ("událost", "udalost", "nežádouc", "nezadouc")):
            if parent is None or parent.get("kind") != "item":
                return "unassigned"
            hazard_event_service.create_event(
                hazard_identification_id=source_id,
                inventory_item_id=int(parent["id"]),
                name=proposal.name,
                description=proposal.reasoning,
                note=note,
            )
            return "applied"

        if self._area_matches(
            area,
            ("ohrožen", "ohrozen", "osob", "skupin", "rizik", "posouzen"),
        ):
            if parent is None or parent.get("kind") != "event":
                return "unassigned"
            hazard_risk_assessment_service.create_assessment(
                hazard_identification_id=source_id,
                hazard_event_id=int(parent["id"]),
                exposed_group=proposal.name,
                consequence=proposal.reasoning or "Dle návrhu AI",
                severity=RISK_SEVERITY_MODERATE,
                note=note,
            )
            return "applied"

        if self._area_matches(area, ("potřeb", "potreb", "dalš", "dals")):
            if parent is None or parent.get("kind") != "assessment":
                return "unassigned"
            hazard_required_measure_service.create_measure(
                hazard_identification_id=source_id,
                hazard_risk_assessment_id=int(parent["id"]),
                description=proposal.name,
                note=note,
            )
            return "applied"

        if self._area_matches(
            area,
            (
                "existujíc",
                "existujic",
                "ochrann",
                "organizač",
                "organizac",
                "oopp",
                "bariér",
                "barier",
                "technick",
                "opatřen",
                "opatren",
            ),
        ):
            if parent is None or parent.get("kind") != "assessment":
                return "unassigned"
            hazard_existing_measure_service.create_measure(
                hazard_identification_id=source_id,
                hazard_risk_assessment_id=int(parent["id"]),
                description=proposal.name,
                note=note,
            )
            return "applied"

        # Neznámá oblast bez jednoznačného rodiče → nezařazené
        return "unassigned"

    @staticmethod
    def _area_matches(area: str, needles: tuple[str, ...]) -> bool:
        return any(needle in area for needle in needles)

    @staticmethod
    def _category_sort_key(category: str) -> int:
        try:
            return HAZARD_INVENTORY_CATEGORIES.index(category)
        except ValueError:
            return len(HAZARD_INVENTORY_CATEGORIES)

    @classmethod
    def _sort_analysis_sources(cls, items: list) -> list:
        return sorted(
            items,
            key=lambda item: (
                cls._category_sort_key(item.category),
                item.sort_order,
                item.name.casefold(),
                item.id,
            ),
        )

    @staticmethod
    def _strip_internal_node_fields(node: dict) -> dict:
        cleaned = dict(node)
        cleaned.pop("_source_id", None)
        return cleaned

    @staticmethod
    def _count_nodes(workplace_analysis: list[dict]) -> dict[str, int]:
        events = 0
        assessments = 0
        existing_measures = 0
        required_measures = 0
        for item_node in workplace_analysis:
            for event_node in item_node.get("events") or []:
                events += 1
                for assessment_node in event_node.get("assessments") or []:
                    assessments += 1
                    existing_measures += len(
                        assessment_node.get("existing_measures") or []
                    )
                    required_measures += len(
                        assessment_node.get("required_measures") or []
                    )
        return {
            "items": len(workplace_analysis),
            "events": events,
            "assessments": assessments,
            "existing_measures": existing_measures,
            "required_measures": required_measures,
        }

    def _build_hierarchy(
        self,
        identification,
        *,
        items: list,
        include_responsible_person: bool,
    ) -> dict:
        item_ids = {item.id for item in items}
        item_export_ids = {
            item.id: f"ITEM-{index:03d}" for index, item in enumerate(items, start=1)
        }
        export_id_map: dict[str, dict] = {
            export_id: {"kind": "item", "id": item_id}
            for item_id, export_id in item_export_ids.items()
        }

        event_rows = hazard_event_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        event_rows = [
            row for row in event_rows if row.event.inventory_item_id in item_ids
        ]
        events_by_item: dict[int, list] = {}
        for row in event_rows:
            events_by_item.setdefault(row.event.inventory_item_id, []).append(row)
        ordered_event_rows = []
        for item in items:
            ordered_event_rows.extend(events_by_item.get(item.id, []))
        event_export_ids = {
            row.event.id: f"EVENT-{index:03d}"
            for index, row in enumerate(ordered_event_rows, start=1)
        }
        for event_id, export_id in event_export_ids.items():
            export_id_map[export_id] = {"kind": "event", "id": event_id}

        assessment_rows = hazard_risk_assessment_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        assessment_rows = [
            row
            for row in assessment_rows
            if row.assessment.hazard_event_id in event_export_ids
        ]
        assessments_by_event: dict[int, list] = {}
        for row in assessment_rows:
            assessments_by_event.setdefault(row.assessment.hazard_event_id, []).append(row)
        ordered_assessment_rows = []
        for event_row in ordered_event_rows:
            ordered_assessment_rows.extend(
                assessments_by_event.get(event_row.event.id, [])
            )
        assessment_pairs: list[tuple[str, object]] = []
        for index, row in enumerate(ordered_assessment_rows, start=1):
            export_id = f"ASSESSMENT-{index:03d}"
            export_id_map[export_id] = {"kind": "assessment", "id": row.assessment.id}
            assessment_pairs.append((export_id, row))
        assessments_by_event_mapped: dict[int, list] = {}
        for export_id, row in assessment_pairs:
            assessments_by_event_mapped.setdefault(row.assessment.hazard_event_id, []).append(
                (export_id, row)
            )

        identification_block = {
            "identification_number": identification.identification_number,
            "operation": identification.operation_name or "",
            "workplace": identification.workplace_name or "",
            "workplace_part": identification.workplace_part_name or "",
            "started_at": (
                identification.started_at.isoformat() if identification.started_at else None
            ),
            "status": identification.status,
            "status_label": HAZARD_IDENTIFICATION_STATUS_LABELS.get(
                identification.status,
                identification.status,
            ),
            "note": identification.note or "",
        }
        if include_responsible_person:
            identification_block["responsible_person"] = (
                identification.responsible_person_name or ""
            )

        workplace_analysis = []
        for item in items:
            event_nodes = []
            for event_row in events_by_item.get(item.id, []):
                assessment_nodes = []
                for export_id, assessment_row in assessments_by_event_mapped.get(
                    event_row.event.id,
                    [],
                ):
                    assessment = assessment_row.assessment
                    existing_measures = [
                        {
                            "description": measure.description,
                            "note": measure.note or "",
                        }
                        for measure in hazard_existing_measure_service.get_for_assessment(
                            assessment.id,
                            include_inactive=False,
                        )
                    ]
                    required_measures = [
                        {
                            "description": measure.description,
                            "note": measure.note or "",
                        }
                        for measure in hazard_required_measure_service.get_for_assessment(
                            assessment.id,
                            include_inactive=False,
                        )
                    ]
                    assessment_nodes.append(
                        {
                            "export_id": export_id,
                            "exposed_group": assessment.exposed_group,
                            "consequence": assessment.consequence or "",
                            "severity": assessment.severity,
                            "severity_label": format_risk_severity_label(
                                assessment.severity
                            ),
                            "conclusion": assessment.conclusion or "",
                            "assessment_status": assessment.assessment_status,
                            "assessment_status_label": RISK_ASSESSMENT_STATUS_LABELS.get(
                                assessment.assessment_status,
                                assessment.assessment_status,
                            ),
                            "note": assessment.note or "",
                            "existing_measures": existing_measures,
                            "required_measures": required_measures,
                        }
                    )

                event_nodes.append(
                    {
                        "export_id": event_export_ids[event_row.event.id],
                        "name": event_row.event.name,
                        "description": event_row.event.description or "",
                        "note": event_row.event.note or "",
                        "assessments": assessment_nodes,
                    }
                )

            workplace_analysis.append(
                {
                    "_source_id": item.id,
                    "export_id": item_export_ids[item.id],
                    "category": item.category,
                    "category_label": HAZARD_INVENTORY_CATEGORY_LABELS.get(
                        item.category,
                        item.category,
                    ),
                    "name": item.name,
                    "description": item.description or "",
                    "events": event_nodes,
                }
            )

        return {
            "identification": identification_block,
            "workplace_analysis": workplace_analysis,
            "export_id_map": export_id_map,
            "counts": self._count_nodes(
                [self._strip_internal_node_fields(node) for node in workplace_analysis]
            ),
        }

    def _hierarchy_to_zadani_json(
        self,
        hierarchy: dict,
        *,
        export_scope: str,
        batch_number: int,
        batch_count: int,
        source_count: int,
        object_count: int,
        recommended_limit_exceeded: bool,
        change_tracking: dict,
    ) -> dict:
        return {
            "schema_version": AI_PEER_REVIEW_SCHEMA_VERSION,
            "export_type": AI_PEER_REVIEW_EXPORT_TYPE,
            "export_scope": export_scope,
            "batch_number": batch_number,
            "batch_count": batch_count,
            "source_count": source_count,
            "object_count": object_count,
            "recommended_limit_exceeded": recommended_limit_exceeded,
            "change_tracking": dict(change_tracking),
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "application_version": APP_VERSION,
            "identification": hierarchy["identification"],
            "workplace_analysis": hierarchy["workplace_analysis"],
            "hierarchy": [
                "workplace_analysis_item",
                "event",
                "assessment",
                "existing_measures",
                "required_measures",
            ],
            "consultation_request": {
                "request_summary": (
                    "Proveď oponentní posouzení hierarchické identifikace rizik "
                    "a navrhni možné opomenuté položky."
                ),
                "rules": [
                    "Nehodnotit závažnost rizik.",
                    "Neměnit existující položky.",
                    "U návrhů uvádět parent_export_id (ITEM/EVENT/ASSESSMENT).",
                    "Ke každému návrhu uvést stručné odborné zdůvodnění.",
                ],
            },
        }

    def _hierarchy_to_data_text(self, hierarchy: dict) -> str:
        identification = hierarchy["identification"]
        lines: list[str] = []
        lines.append("IDENTIFIKACE RIZIK – HIERARCHICKÉ PODKLADY PRO AI")
        lines.append("=" * 60)
        lines.append("")
        lines.append("ZÁKLADNÍ ÚDAJE")
        lines.append("-" * 40)
        lines.append(f"Číslo identifikace: {identification['identification_number']}")
        lines.append(f"Provoz: {identification['operation'] or '—'}")
        lines.append(f"Pracoviště: {identification['workplace'] or '—'}")
        lines.append(f"Část pracoviště: {identification['workplace_part'] or '—'}")
        if identification.get("started_at"):
            lines.append(f"Datum zahájení: {identification['started_at']}")
        else:
            lines.append("Datum zahájení: —")
        if "responsible_person" in identification:
            lines.append(f"Odpovědná osoba: {identification['responsible_person'] or '—'}")
        lines.append(f"Stav: {identification['status_label']}")
        lines.append(f"Poznámka: {identification['note'] or '—'}")
        lines.append("")
        lines.append("HIERARCHIE")
        lines.append("-" * 40)
        lines.append(
            "Analýza pracoviště → Nežádoucí události → Posouzení "
            "→ Existující opatření → Potřebná opatření"
        )
        lines.append("")

        items = hierarchy["workplace_analysis"]
        if not items:
            lines.append("(žádné aktivní položky analýzy)")
            lines.append("")
            return "\n".join(lines)

        for item in items:
            lines.append(f"Zdroj analýzy [{item['export_id']}]")
            lines.append(item["name"])
            lines.append(f"    Kategorie: {item['category_label']}")
            if item["description"]:
                lines.append(f"    Popis: {item['description']}")

            if not item["events"]:
                lines.append("    Událost: (žádná)")
            for event in item["events"]:
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
                    lines.append(
                        "                    Stav: "
                        f"{assessment['assessment_status_label']}"
                    )
                    if assessment["conclusion"]:
                        lines.append(
                            "                    Závěr: "
                            f"{assessment['conclusion']}"
                        )

                    lines.append("                    Existující opatření")
                    if assessment["existing_measures"]:
                        for measure in assessment["existing_measures"]:
                            lines.append(
                                f"                        - {measure['description']}"
                            )
                    else:
                        lines.append("                        (žádná)")

                    lines.append("                    Potřebná opatření")
                    if assessment["required_measures"]:
                        for measure in assessment["required_measures"]:
                            lines.append(
                                f"                        - {measure['description']}"
                            )
                    else:
                        lines.append("                        (žádná)")
            lines.append("")

        return "\n".join(lines)

    def _build_overview(
        self,
        hierarchy: dict,
        *,
        batch_number: int,
        batch_count: int,
    ) -> tuple[str, list[str]]:
        identification = hierarchy["identification"]
        counts = hierarchy["counts"]
        summary_lines = [
            f"Položky analýzy: {counts['items']}",
            f"Nežádoucí události: {counts['events']}",
            f"Posouzení rizik: {counts['assessments']}",
            f"Existující opatření: {counts['existing_measures']}",
            f"Potřebná opatření: {counts['required_measures']}",
        ]
        overview = "\n".join(
            [
                "Přehled exportu – hierarchické oponentní posouzení AI",
                "====================================================",
                "",
                f"Číslo identifikace: {identification['identification_number']}",
                f"Pracoviště: {identification['workplace'] or '—'}",
                f"Dávka: {batch_number} / {batch_count}",
                "",
                *summary_lines,
                "",
                "Hierarchie: Analýza → Události → Posouzení → Opatření",
                "",
                "Soubor slouží pouze pro orientaci uživatele.",
                "",
            ]
        )
        return overview, summary_lines

    def _build_batches_overview(
        self,
        *,
        identification_number: str,
        batches: list[AiPeerReviewBatchContent],
        export_scope: str,
    ) -> str:
        lines = [
            "Přehled dávek – oponentní posouzení AI",
            "======================================",
            "",
            f"Číslo identifikace: {identification_number}",
            f"Rozsah exportu: {export_scope}",
            f"Celkový počet dávek: {len(batches)}",
            (
                "Limity dělení: max. "
                f"{AI_PEER_REVIEW_MAX_SOURCES_PER_BATCH} zdrojů analýzy / "
                f"{AI_PEER_REVIEW_MAX_OBJECTS_PER_BATCH} objektů na dávku"
            ),
            "",
            "Seznam dávek:",
        ]
        for batch in batches:
            lines.append("")
            lines.append(f"Dávka {batch.batch_number:03d}")
            lines.append(f"  Soubor: davka_{batch.batch_number:03d}.zip")
            lines.append(f"  Počet zdrojů analýzy: {batch.source_count}")
            lines.append(f"  Počet objektů: {batch.object_count}")
            lines.append("  Zdroje analýzy:")
            for name in batch.source_names:
                lines.append(f"    - {name}")
            if batch.recommended_limit_exceeded:
                lines.append(
                    "  UPOZORNĚNÍ: větev překročila doporučený limit počtu objektů; "
                    "zdroj byl exportován samostatně bez rozdělení hierarchie."
                )
        lines.append("")
        return "\n".join(lines)


hazard_identification_peer_review_provider = HazardIdentificationPeerReviewProvider()
