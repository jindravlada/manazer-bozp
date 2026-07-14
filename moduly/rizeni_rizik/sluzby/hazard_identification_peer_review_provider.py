"""Adaptér oponentního posouzení AI pro identifikaci nebezpečí."""

from __future__ import annotations

from core.ai_oponentni.constants import DEFAULT_AI_PEER_REVIEW_PROMPT
from core.ai_oponentni.sluzby.ai_peer_review_service import AiPeerReviewError
from core.ai_oponentni.types import (
    AiPeerReviewExportContent,
    AiPeerReviewExportOptions,
    AiProposal,
)
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

        data_text = self._build_data_text(
            identification,
            include_responsible_person=options.include_responsible_person,
        )
        overview_text, summary_lines = self._build_overview(identification)

        return AiPeerReviewExportContent(
            source_label=identification.identification_number,
            prompt_text=DEFAULT_AI_PEER_REVIEW_PROMPT,
            data_text=data_text,
            overview_text=overview_text,
            summary_lines=summary_lines,
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
            ("ohrožen", "ohrozen", "osob", "skupin", "rizik"),
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

        # Výchozí: položka analýzy pracoviště
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

    def _build_data_text(self, identification, *, include_responsible_person: bool) -> str:
        lines: list[str] = []
        lines.append("IDENTIFIKACE RIZIK – PODKLADY PRO OPONENTNÍ POSOUZENÍ")
        lines.append("=" * 60)
        lines.append("")
        lines.append("ZÁKLADNÍ ÚDAJE")
        lines.append("-" * 40)
        lines.append(f"Číslo identifikace: {identification.identification_number}")
        lines.append(f"Provoz: {identification.operation_name or '—'}")
        lines.append(f"Pracoviště: {identification.workplace_name or '—'}")
        lines.append(f"Část pracoviště: {identification.workplace_part_name or '—'}")
        if identification.started_at:
            lines.append(f"Datum zahájení: {identification.started_at.strftime('%d.%m.%Y')}")
        else:
            lines.append("Datum zahájení: —")
        if include_responsible_person:
            lines.append(
                f"Odpovědná osoba: {identification.responsible_person_name or '—'}"
            )
        lines.append(
            "Stav: "
            + HAZARD_IDENTIFICATION_STATUS_LABELS.get(
                identification.status,
                identification.status,
            )
        )
        lines.append(f"Poznámka: {identification.note or '—'}")
        lines.append("")

        items = hazard_inventory_item_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        relations = self._relation_service.repository.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        item_names = {item.id: item.name for item in items}
        lines.append("ANALÝZA PRACOVIŠTĚ")
        lines.append("-" * 40)
        if not items:
            lines.append("(žádné aktivní položky)")
        for index, item in enumerate(items, start=1):
            category = HAZARD_INVENTORY_CATEGORY_LABELS.get(item.category, item.category)
            lines.append(f"{index}. {item.name} [{category}]")
            if item.description:
                lines.append(f"   Popis: {item.description}")
            related = [
                relation
                for relation in relations
                if relation.source_item_id == item.id
                and relation.target_item_id in item_names
            ]
            for relation in related:
                rel_label = HAZARD_INVENTORY_RELATION_TYPE_LABELS.get(
                    relation.relation_type,
                    relation.relation_type,
                )
                lines.append(
                    f"   Souvislost: {rel_label} → {item_names[relation.target_item_id]}"
                )
        lines.append("")

        hazard_rows = identified_hazard_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        lines.append("NEBEZPEČÍ")
        lines.append("-" * 40)
        if not hazard_rows:
            lines.append("(žádná aktivní nebezpečí)")
        for index, row in enumerate(hazard_rows, start=1):
            source = IDENTIFIED_HAZARD_SOURCE_LABELS.get(
                row.hazard.source_type,
                row.hazard.source_type,
            )
            lines.append(f"{index}. {row.hazard.name}")
            lines.append(f"   Zdrojová položka: {row.inventory_item_name}")
            lines.append(f"   Původ: {source}")
            if row.hazard.description:
                lines.append(f"   Popis: {row.hazard.description}")
            if row.hazard.note:
                lines.append(f"   Poznámka: {row.hazard.note}")
        lines.append("")

        event_rows = hazard_event_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        lines.append("NEŽÁDOUCÍ UDÁLOSTI")
        lines.append("-" * 40)
        if not event_rows:
            lines.append("(žádné aktivní události)")
        for index, row in enumerate(event_rows, start=1):
            lines.append(f"{index}. {row.event.name}")
            lines.append(f"   Nebezpečí: {row.hazard_name}")
            if row.event.description:
                lines.append(f"   Popis: {row.event.description}")
            if row.event.note:
                lines.append(f"   Poznámka: {row.event.note}")
        lines.append("")

        assessment_rows = hazard_risk_assessment_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        lines.append("POSOUZENÍ RIZIK")
        lines.append("-" * 40)
        if not assessment_rows:
            lines.append("(žádná aktivní posouzení)")
        for index, row in enumerate(assessment_rows, start=1):
            assessment = row.assessment
            status = RISK_ASSESSMENT_STATUS_LABELS.get(
                assessment.assessment_status,
                assessment.assessment_status,
            )
            lines.append(f"{index}. Ohrožená skupina: {assessment.exposed_group}")
            lines.append(f"   Nežádoucí událost: {row.event_name}")
            lines.append(f"   Možný následek: {assessment.consequence or '—'}")
            lines.append(
                f"   Závažnost: {format_risk_severity_label(assessment.severity)}"
            )
            lines.append(f"   Stav posouzení: {status}")
            if assessment.conclusion:
                lines.append(f"   Závěr: {assessment.conclusion}")
            if assessment.note:
                lines.append(f"   Poznámka: {assessment.note}")

            existing = hazard_existing_measure_service.get_for_assessment(
                assessment.id,
                include_inactive=False,
            )
            if existing:
                lines.append("   Existující opatření:")
                for measure in existing:
                    lines.append(f"   - {measure.description}")
            required = hazard_required_measure_service.get_for_assessment(
                assessment.id,
                include_inactive=False,
            )
            if required:
                lines.append("   Potřebná další opatření:")
                for measure in required:
                    lines.append(f"   - {measure.description}")
        lines.append("")
        return "\n".join(lines)

    def _build_overview(self, identification) -> tuple[str, list[str]]:
        items = hazard_inventory_item_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        hazards = identified_hazard_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        events = hazard_event_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        assessments = hazard_risk_assessment_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        existing_count = 0
        required_count = 0
        for row in assessments:
            existing_count += len(
                hazard_existing_measure_service.get_for_assessment(
                    row.assessment.id,
                    include_inactive=False,
                )
            )
            required_count += len(
                hazard_required_measure_service.get_for_assessment(
                    row.assessment.id,
                    include_inactive=False,
                )
            )

        summary_lines = [
            f"Položky analýzy: {len(items)}",
            f"Nebezpečí: {len(hazards)}",
            f"Nežádoucí události: {len(events)}",
            f"Posouzení rizik: {len(assessments)}",
            f"Existující opatření: {existing_count}",
            f"Potřebná opatření: {required_count}",
        ]
        overview = "\n".join(
            [
                "Přehled exportu – oponentní posouzení AI",
                "=======================================",
                "",
                f"Číslo identifikace: {identification.identification_number}",
                f"Pracoviště: {identification.workplace_name or '—'}",
                "",
                *summary_lines,
                "",
                "Soubor slouží pouze pro orientaci uživatele.",
                "",
            ]
        )
        return overview, summary_lines


hazard_identification_peer_review_provider = HazardIdentificationPeerReviewProvider()
