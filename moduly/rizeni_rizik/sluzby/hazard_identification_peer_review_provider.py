"""Adaptér oponentního posouzení AI pro identifikaci nebezpečí."""

from __future__ import annotations

from datetime import datetime

from core.ai_oponentni.constants import (
    AI_PEER_REVIEW_EXPORT_TYPE,
    AI_PEER_REVIEW_RESPONSE_SCHEMA,
    AI_PEER_REVIEW_SCHEMA_VERSION,
    DEFAULT_AI_PEER_REVIEW_PROMPT,
)
from core.ai_oponentni.sluzby.ai_peer_review_service import AiPeerReviewError
from core.ai_oponentni.types import (
    AiPeerReviewExportContent,
    AiPeerReviewExportOptions,
    AiProposal,
)
from core.version import APP_VERSION
from moduly.rizeni_rizik.constants import (
    HAZARD_IDENTIFICATION_STATUS_LABELS,
    HAZARD_INVENTORY_CATEGORY_LABELS,
    HAZARD_INVENTORY_CATEGORY_OTHER,
    HAZARD_INVENTORY_RELATION_TYPE_LABELS,
    IDENTIFIED_HAZARD_SOURCE_AI,
    IDENTIFIED_HAZARD_SOURCE_LABELS,
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
from moduly.rizeni_rizik.sluzby.hazard_inventory_relation_service import (
    HazardInventoryRelationService,
)
from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
    HazardRequiredMeasureError,
    hazard_required_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    HazardRiskAssessmentError,
    hazard_risk_assessment_service,
)
from moduly.rizeni_rizik.sluzby.identified_hazard_service import (
    IdentifiedHazardError,
    identified_hazard_service,
)

SOURCE_TYPE_HAZARD_IDENTIFICATION = "hazard_identification"


class HazardIdentificationPeerReviewProvider:
    source_type = SOURCE_TYPE_HAZARD_IDENTIFICATION

    def __init__(self):
        self._relation_service = HazardInventoryRelationService()

    def can_export(self, source_id: int | None) -> bool:
        if not source_id:
            return False
        return hazard_identification_service.get_by_id(source_id) is not None

    def build_export_content(
        self,
        source_id: int,
        *,
        options: AiPeerReviewExportOptions,
    ) -> AiPeerReviewExportContent:
        identification = hazard_identification_service.get_by_id(source_id)
        if identification is None:
            raise AiPeerReviewError("Identifikace nebezpečí neexistuje.")

        hierarchy = self._build_hierarchy(
            identification,
            include_responsible_person=options.include_responsible_person,
        )
        data_text = self._hierarchy_to_data_text(hierarchy)
        overview_text, summary_lines = self._build_overview(hierarchy)
        zadani_json = self._hierarchy_to_zadani_json(hierarchy)

        return AiPeerReviewExportContent(
            source_label=identification.identification_number,
            prompt_text=DEFAULT_AI_PEER_REVIEW_PROMPT,
            data_text=data_text,
            overview_text=overview_text,
            summary_lines=summary_lines,
            zadani_json=zadani_json,
            schema_json=AI_PEER_REVIEW_RESPONSE_SCHEMA,
        )

    def apply_proposals(self, source_id: int, proposals: list[AiProposal]) -> int:
        identification = hazard_identification_service.get_by_id(source_id)
        if identification is None:
            raise AiPeerReviewError("Identifikace nebezpečí neexistuje.")

        applied = 0
        for proposal in proposals:
            try:
                if self._apply_one(source_id, proposal):
                    applied += 1
            except (
                HazardInventoryItemError,
                IdentifiedHazardError,
                HazardEventError,
                HazardRiskAssessmentError,
                HazardExistingMeasureError,
                HazardRequiredMeasureError,
                ValueError,
            ):
                continue
        return applied

    def _apply_one(self, source_id: int, proposal: AiProposal) -> bool:
        area = proposal.area.casefold()
        note = f"Návrh z AI oponentního posouzení.\n{proposal.reasoning}".strip()

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
            hazard_inventory_item_service.create_item(
                hazard_identification_id=source_id,
                category=HAZARD_INVENTORY_CATEGORY_OTHER,
                name=proposal.name,
                description=note,
            )
            return True

        if self._area_matches(area, ("nebezpeč", "nebezpec")):
            item = self._ensure_anchor_item(source_id)
            identified_hazard_service.create_hazard(
                hazard_identification_id=source_id,
                inventory_item_id=item.id,
                name=proposal.name,
                description=proposal.reasoning,
                note=note,
                source_type=IDENTIFIED_HAZARD_SOURCE_AI,
            )
            return True

        if self._area_matches(area, ("událost", "udalost", "nežádouc", "nezadouc")):
            hazard = self._ensure_anchor_hazard(source_id)
            hazard_event_service.create_event(
                hazard_identification_id=source_id,
                identified_hazard_id=hazard.id,
                name=proposal.name,
                description=proposal.reasoning,
                note=note,
            )
            return True

        if self._area_matches(
            area,
            ("ohrožen", "ohrozen", "osob", "skupin", "rizik", "posouzen"),
        ):
            event = self._ensure_anchor_event(source_id)
            hazard_risk_assessment_service.create_assessment(
                hazard_identification_id=source_id,
                hazard_event_id=event.id,
                exposed_group=proposal.name,
                consequence=proposal.reasoning or "Dle návrhu AI",
                severity=RISK_SEVERITY_MODERATE,
                note=note,
            )
            return True

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
            ),
        ):
            assessment = self._ensure_anchor_assessment(source_id)
            if self._area_matches(area, ("potřeb", "potreb", "dalš", "dals")):
                hazard_required_measure_service.create_measure(
                    hazard_identification_id=source_id,
                    hazard_risk_assessment_id=assessment.id,
                    description=proposal.name,
                    note=note,
                )
            else:
                hazard_existing_measure_service.create_measure(
                    hazard_identification_id=source_id,
                    hazard_risk_assessment_id=assessment.id,
                    description=proposal.name,
                    note=note,
                )
            return True

        if self._area_matches(area, ("potřeb", "potreb", "opatřen", "opatren")):
            assessment = self._ensure_anchor_assessment(source_id)
            hazard_required_measure_service.create_measure(
                hazard_identification_id=source_id,
                hazard_risk_assessment_id=assessment.id,
                description=proposal.name,
                note=note,
            )
            return True

        hazard_inventory_item_service.create_item(
            hazard_identification_id=source_id,
            category=HAZARD_INVENTORY_CATEGORY_OTHER,
            name=proposal.name,
            description=note,
        )
        return True

    @staticmethod
    def _area_matches(area: str, needles: tuple[str, ...]) -> bool:
        return any(needle in area for needle in needles)

    def _ensure_anchor_item(self, source_id: int):
        items = hazard_inventory_item_service.get_for_identification(
            source_id,
            include_inactive=False,
        )
        if items:
            return items[0]
        return hazard_inventory_item_service.create_item(
            hazard_identification_id=source_id,
            category=HAZARD_INVENTORY_CATEGORY_OTHER,
            name="Podklady z AI oponentního posouzení",
            description="Automaticky vytvořená položka jako kotva pro návrhy AI.",
        )

    def _ensure_anchor_hazard(self, source_id: int):
        rows = identified_hazard_service.get_for_identification(
            source_id,
            include_inactive=False,
        )
        if rows:
            return rows[0].hazard
        item = self._ensure_anchor_item(source_id)
        return identified_hazard_service.create_hazard(
            hazard_identification_id=source_id,
            inventory_item_id=item.id,
            name="Podklady z AI oponentního posouzení",
            note="Automaticky vytvořené nebezpečí jako kotva pro návrhy AI.",
            source_type=IDENTIFIED_HAZARD_SOURCE_AI,
        )

    def _ensure_anchor_event(self, source_id: int):
        rows = hazard_event_service.get_for_identification(
            source_id,
            include_inactive=False,
        )
        if rows:
            return rows[0].event
        hazard = self._ensure_anchor_hazard(source_id)
        return hazard_event_service.create_event(
            hazard_identification_id=source_id,
            identified_hazard_id=hazard.id,
            name="Podklady z AI oponentního posouzení",
            note="Automaticky vytvořená událost jako kotva pro návrhy AI.",
        )

    def _ensure_anchor_assessment(self, source_id: int):
        rows = hazard_risk_assessment_service.get_for_identification(
            source_id,
            include_inactive=False,
        )
        if rows:
            return rows[0].assessment
        event = self._ensure_anchor_event(source_id)
        return hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=source_id,
            hazard_event_id=event.id,
            exposed_group="Obecná ohrožená skupina",
            consequence="Dle návrhu AI",
            severity=RISK_SEVERITY_MODERATE,
            note="Automaticky vytvořené posouzení jako kotva pro návrhy AI.",
        )

    def _build_hierarchy(self, identification, *, include_responsible_person: bool) -> dict:
        items = hazard_inventory_item_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        item_export_ids = {
            item.id: f"ITEM-{index:03d}" for index, item in enumerate(items, start=1)
        }
        item_names = {item.id: item.name for item in items}

        relations = self._relation_service.repository.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        relations_by_source: dict[int, list] = {}
        for relation in relations:
            if (
                relation.source_item_id not in item_export_ids
                or relation.target_item_id not in item_export_ids
            ):
                continue
            relations_by_source.setdefault(relation.source_item_id, []).append(relation)

        hazard_rows = identified_hazard_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        hazard_export_ids = {
            row.hazard.id: f"HAZARD-{index:03d}"
            for index, row in enumerate(hazard_rows, start=1)
        }
        hazards_by_item: dict[int, list] = {}
        for row in hazard_rows:
            hazards_by_item.setdefault(row.hazard.inventory_item_id, []).append(row)

        event_rows = hazard_event_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        event_export_ids = {
            row.event.id: f"EVENT-{index:03d}"
            for index, row in enumerate(event_rows, start=1)
        }
        events_by_hazard: dict[int, list] = {}
        for row in event_rows:
            events_by_hazard.setdefault(row.event.identified_hazard_id, []).append(row)

        assessment_rows = hazard_risk_assessment_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        assessments_by_event: dict[int, list] = {}
        for index, row in enumerate(assessment_rows, start=1):
            assessments_by_event.setdefault(row.assessment.hazard_event_id, []).append(
                (f"ASSESSMENT-{index:03d}", row)
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
            related = [
                {
                    "relation_type": relation.relation_type,
                    "relation_type_label": HAZARD_INVENTORY_RELATION_TYPE_LABELS.get(
                        relation.relation_type,
                        relation.relation_type,
                    ),
                    "target_export_id": item_export_ids[relation.target_item_id],
                    "target_name": item_names[relation.target_item_id],
                    "note": relation.note or "",
                }
                for relation in relations_by_source.get(item.id, [])
            ]

            hazard_nodes = []
            for hazard_row in hazards_by_item.get(item.id, []):
                event_nodes = []
                for event_row in events_by_hazard.get(hazard_row.hazard.id, []):
                    assessment_nodes = []
                    for export_id, assessment_row in assessments_by_event.get(
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

                hazard_nodes.append(
                    {
                        "export_id": hazard_export_ids[hazard_row.hazard.id],
                        "name": hazard_row.hazard.name,
                        "description": hazard_row.hazard.description or "",
                        "note": hazard_row.hazard.note or "",
                        "source_type": hazard_row.hazard.source_type,
                        "source_type_label": IDENTIFIED_HAZARD_SOURCE_LABELS.get(
                            hazard_row.hazard.source_type,
                            hazard_row.hazard.source_type,
                        ),
                        "events": event_nodes,
                    }
                )

            workplace_analysis.append(
                {
                    "export_id": item_export_ids[item.id],
                    "category": item.category,
                    "category_label": HAZARD_INVENTORY_CATEGORY_LABELS.get(
                        item.category,
                        item.category,
                    ),
                    "name": item.name,
                    "description": item.description or "",
                    "relations": related,
                    "hazards": hazard_nodes,
                }
            )

        return {
            "identification": identification_block,
            "workplace_analysis": workplace_analysis,
            "counts": {
                "items": len(items),
                "hazards": len(hazard_rows),
                "events": len(event_rows),
                "assessments": len(assessment_rows),
                "existing_measures": sum(
                    len(node["existing_measures"])
                    for item_node in workplace_analysis
                    for hazard_node in item_node["hazards"]
                    for event_node in hazard_node["events"]
                    for node in event_node["assessments"]
                ),
                "required_measures": sum(
                    len(node["required_measures"])
                    for item_node in workplace_analysis
                    for hazard_node in item_node["hazards"]
                    for event_node in hazard_node["events"]
                    for node in event_node["assessments"]
                ),
            },
        }

    def _hierarchy_to_zadani_json(self, hierarchy: dict) -> dict:
        return {
            "schema_version": AI_PEER_REVIEW_SCHEMA_VERSION,
            "export_type": AI_PEER_REVIEW_EXPORT_TYPE,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "application_version": APP_VERSION,
            "identification": hierarchy["identification"],
            "workplace_analysis": hierarchy["workplace_analysis"],
            "hierarchy": [
                "workplace_analysis_item",
                "hazard",
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
                    "U návrhů uvádět parent_export_id (ITEM/HAZARD/EVENT/ASSESSMENT).",
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
            "Analýza pracoviště → Nebezpečí → Nežádoucí události → Posouzení "
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
            for relation in item["relations"]:
                lines.append(
                    f"    Souvislost: {relation['relation_type_label']} → "
                    f"{relation['target_name']} [{relation['target_export_id']}]"
                )

            if not item["hazards"]:
                lines.append("    Nebezpečí: (žádná)")
            for hazard in item["hazards"]:
                lines.append("")
                lines.append("    Nebezpečí")
                lines.append(f"        [{hazard['export_id']}] {hazard['name']}")
                lines.append(f"            Původ: {hazard['source_type_label']}")
                if hazard["description"]:
                    lines.append(f"            Popis: {hazard['description']}")
                if hazard["note"]:
                    lines.append(f"            Poznámka: {hazard['note']}")

                if not hazard["events"]:
                    lines.append("            Událost: (žádná)")
                for event in hazard["events"]:
                    lines.append("")
                    lines.append("            Událost")
                    lines.append(f"                [{event['export_id']}] {event['name']}")
                    if event["description"]:
                        lines.append(f"                    Popis: {event['description']}")
                    if event["note"]:
                        lines.append(f"                    Poznámka: {event['note']}")

                    if not event["assessments"]:
                        lines.append("                    Posouzení: (žádné)")
                    for assessment in event["assessments"]:
                        lines.append("")
                        lines.append("                    Posouzení")
                        lines.append(
                            f"                        [{assessment['export_id']}] "
                            f"{assessment['exposed_group']}"
                        )
                        lines.append(
                            "                            Možný následek: "
                            f"{assessment['consequence'] or '—'}"
                        )
                        lines.append(
                            "                            Závažnost: "
                            f"{assessment['severity_label']}"
                        )
                        lines.append(
                            "                            Stav: "
                            f"{assessment['assessment_status_label']}"
                        )
                        if assessment["conclusion"]:
                            lines.append(
                                "                            Závěr: "
                                f"{assessment['conclusion']}"
                            )

                        lines.append("                            Existující opatření")
                        if assessment["existing_measures"]:
                            for measure in assessment["existing_measures"]:
                                lines.append(
                                    f"                                - {measure['description']}"
                                )
                        else:
                            lines.append("                                (žádná)")

                        lines.append("                            Potřebná opatření")
                        if assessment["required_measures"]:
                            for measure in assessment["required_measures"]:
                                lines.append(
                                    f"                                - {measure['description']}"
                                )
                        else:
                            lines.append("                                (žádná)")
            lines.append("")

        return "\n".join(lines)

    def _build_overview(self, hierarchy: dict) -> tuple[str, list[str]]:
        identification = hierarchy["identification"]
        counts = hierarchy["counts"]
        summary_lines = [
            f"Položky analýzy: {counts['items']}",
            f"Nebezpečí: {counts['hazards']}",
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
                "",
                *summary_lines,
                "",
                "Hierarchie: Analýza → Nebezpečí → Události → Posouzení → Opatření",
                "",
                "Soubor slouží pouze pro orientaci uživatele.",
                "",
            ]
        )
        return overview, summary_lines


hazard_identification_peer_review_provider = HazardIdentificationPeerReviewProvider()
