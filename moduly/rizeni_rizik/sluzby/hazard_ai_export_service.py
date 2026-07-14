"""Export podkladů identifikace nebezpečí pro konzultaci s externí AI."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.version import APP_VERSION
from moduly.rizeni_rizik.constants import (
    AI_CONSULTATION_EXPORT_TYPE,
    AI_CONSULTATION_SCHEMA_VERSION,
    AI_CONSULTATION_ZIP_FILES,
    HAZARD_IDENTIFICATION_STATUS_LABELS,
    HAZARD_INVENTORY_CATEGORY_LABELS,
    HAZARD_INVENTORY_RELATION_TYPE_LABELS,
    IDENTIFIED_HAZARD_SOURCE_LABELS,
    RISK_ASSESSMENT_STATUS_LABELS,
    format_risk_severity_label,
)
from moduly.rizeni_rizik.modely.hazard_ai_export import HazardAiExport
from moduly.rizeni_rizik.repository.hazard_ai_export_repository import (
    HazardAiExportRepository,
)
from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
    hazard_existing_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    hazard_identification_service,
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
    hazard_inventory_item_service,
)
from moduly.rizeni_rizik.sluzby.hazard_inventory_relation_service import (
    HazardInventoryRelationService,
)
from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
    hazard_required_measure_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    hazard_risk_assessment_service,
)
from moduly.rizeni_rizik.sluzby.identified_hazard_service import identified_hazard_service


class HazardAiExportError(ValueError):
    pass


@dataclass
class HazardAiExportResult:
    export: HazardAiExport
    file_path: Path
    item_count: int
    hazard_count: int
    event_count: int
    assessment_count: int
    existing_measure_count: int
    required_measure_count: int


CONSULTATION_INSTRUCTION_TEXT = """\
Pokyn pro konzultaci s AI – identifikace nebezpečí a řízení rizik

Účel
====
Na základě přiloženého souboru zadani.json navrhni možné doplnění evidence.
Finální odborné rozhodnutí vždy provádí uživatel. Návrhy nejsou úplné ani definitivní.

Co navrhni
==========
- možné chybějící položky analýzy pracoviště
- možná chybějící nebezpečí
- možné další nežádoucí události
- možné další ohrožené skupiny osob
- možné následky
- existující opatření, která je vhodné na pracovišti ověřit
- potřebná další opatření
- možné související aktuální právní předpisy a konkrétní ustanovení

Pravidla
========
1. Nevydávej návrhy za úplné ani definitivní.
2. Nevytvářej číselné hodnocení rizika (skóre, priorita, barva).
3. Neměň existující záznamy – navrhuj pouze nové položky.
4. Jasně odděl existující data od nových návrhů.
5. U každého návrhu uveď zdůvodnění (reasoning).
6. Právní vazby označ jako návrhy k odbornému ověření
   (requires_verification = true).
7. Odpověď vrať výhradně podle přiloženého schématu schema_odpovedi.json.
8. Používej exportní identifikátory (ITEM-…, HAZARD-…, EVENT-…, ASSESSMENT-…)
   jako parent_export_id, nikoli interní databázová ID.

Formát odpovědi
===============
JSON odpovídající schema_odpovedi.json. Doplň source_identification_number
z identification.identification_number v souboru zadani.json.
"""


RESPONSE_SCHEMA = {
    "schema_version": "1.0",
    "description": (
        "Očekávaný formát odpovědi AI pro import návrhů (fáze R12). "
        "Soubor musí být platný JSON."
    ),
    "type": "object",
    "required": [
        "schema_version",
        "source_identification_number",
        "generated_at",
        "proposals",
    ],
    "properties": {
        "schema_version": {
            "type": "string",
            "const": "1.0",
            "description": "Verze schématu odpovědi.",
        },
        "source_identification_number": {
            "type": "string",
            "description": "Číslo identifikace z zadani.json.",
        },
        "generated_at": {
            "type": "string",
            "format": "date-time",
            "description": "Čas vygenerování odpovědi (ISO 8601).",
        },
        "proposals": {
            "type": "array",
            "items": {"$ref": "#/$defs/proposal"},
        },
    },
    "$defs": {
        "proposal": {
            "type": "object",
            "required": [
                "proposal_id",
                "proposal_type",
                "parent_export_id",
                "name",
                "description",
                "reasoning",
                "confidence",
                "legal_candidates",
            ],
            "properties": {
                "proposal_id": {
                    "type": "string",
                    "description": "Stabilní identifikátor návrhu v rámci odpovědi.",
                },
                "proposal_type": {
                    "type": "string",
                    "enum": [
                        "workplace_analysis_item",
                        "hazard",
                        "event",
                        "exposed_group",
                        "consequence",
                        "existing_measure",
                        "required_measure",
                        "legal_link",
                    ],
                },
                "parent_export_id": {
                    "type": ["string", "null"],
                    "description": (
                        "Exportní ID nadřazené položky (ITEM/HAZARD/EVENT/ASSESSMENT), "
                        "nebo null u položek bez rodiče."
                    ),
                },
                "name": {"type": "string"},
                "description": {"type": "string"},
                "reasoning": {"type": "string"},
                "confidence": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
                "legal_candidates": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/legal_candidate"},
                },
            },
        },
        "legal_candidate": {
            "type": "object",
            "required": [
                "document_number",
                "provision",
                "relation_description",
                "reasoning",
                "confidence",
                "requires_verification",
            ],
            "properties": {
                "document_number": {"type": "string"},
                "provision": {"type": "string"},
                "relation_description": {"type": "string"},
                "reasoning": {"type": "string"},
                "confidence": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                },
                "requires_verification": {
                    "type": "boolean",
                    "const": True,
                },
            },
        },
    },
}


class HazardAiExportService:
    def __init__(self):
        self.repository = HazardAiExportRepository()
        self._relation_service = HazardInventoryRelationService()

    def get_for_identification(self, hazard_identification_id: int) -> list[HazardAiExport]:
        return self.repository.get_for_identification(hazard_identification_id)

    def default_export_filename(self, identification_number: str, exported_at: datetime) -> str:
        stamp = exported_at.strftime("%Y-%m-%d_%H%M")
        safe_number = identification_number.replace("/", "-").replace(" ", "_")
        return f"AI_konzultace_{safe_number}_{stamp}.zip"

    def export_consultation_package(
        self,
        hazard_identification_id: int | None,
        target_path: Path | str,
        *,
        include_responsible_person: bool = False,
    ) -> HazardAiExportResult:
        if not hazard_identification_id:
            raise HazardAiExportError(
                "Export je možné provést až po prvním uložení identifikace."
            )

        identification = hazard_identification_service.get_by_id(hazard_identification_id)
        if identification is None:
            raise HazardAiExportError("Identifikace nebezpečí neexistuje.")

        exported_at = datetime.now()
        payload = self._build_payload(
            identification,
            exported_at=exported_at,
            include_responsible_person=include_responsible_person,
        )
        counts = {
            "item_count": len(payload["workplace_analysis"]),
            "hazard_count": len(payload["hazards"]),
            "event_count": len(payload["events"]),
            "assessment_count": len(payload["risk_assessments"]),
            "existing_measure_count": sum(
                len(item.get("existing_measures") or [])
                for item in payload["risk_assessments"]
            ),
            "required_measure_count": sum(
                len(item.get("required_measures") or [])
                for item in payload["risk_assessments"]
            ),
        }

        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        overview = self._build_overview(payload, counts)
        try:
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(
                    "zadani.json",
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                )
                zf.writestr("pokyn_pro_AI.txt", CONSULTATION_INSTRUCTION_TEXT)
                zf.writestr(
                    "schema_odpovedi.json",
                    json.dumps(RESPONSE_SCHEMA, ensure_ascii=False, indent=2) + "\n",
                )
                zf.writestr("prehled.txt", overview)
        except OSError as error:
            if target.exists():
                target.unlink(missing_ok=True)
            raise HazardAiExportError(f"Nepodařilo se vytvořit exportní soubor: {error}") from error

        names = set()
        try:
            with zipfile.ZipFile(target, "r") as zf:
                names = set(zf.namelist())
        except zipfile.BadZipFile as error:
            target.unlink(missing_ok=True)
            raise HazardAiExportError("Vytvořený exportní ZIP je neplatný.") from error

        if names != set(AI_CONSULTATION_ZIP_FILES):
            target.unlink(missing_ok=True)
            raise HazardAiExportError("Exportní balíček neobsahuje očekávané soubory.")

        try:
            record = HazardAiExport(
                hazard_identification_id=identification.id,
                schema_version=AI_CONSULTATION_SCHEMA_VERSION,
                exported_at=exported_at,
                file_path=str(target.resolve()),
                item_count=counts["item_count"],
                hazard_count=counts["hazard_count"],
                event_count=counts["event_count"],
                assessment_count=counts["assessment_count"],
            )
            saved = self.repository.add(record)
        except Exception:
            target.unlink(missing_ok=True)
            raise

        return HazardAiExportResult(
            export=saved,
            file_path=target,
            item_count=counts["item_count"],
            hazard_count=counts["hazard_count"],
            event_count=counts["event_count"],
            assessment_count=counts["assessment_count"],
            existing_measure_count=counts["existing_measure_count"],
            required_measure_count=counts["required_measure_count"],
        )

    def build_payload_for_tests(
        self,
        hazard_identification_id: int,
        *,
        include_responsible_person: bool = False,
        exported_at: datetime | None = None,
    ) -> dict:
        identification = hazard_identification_service.get_by_id(hazard_identification_id)
        if identification is None:
            raise HazardAiExportError("Identifikace nebezpečí neexistuje.")
        return self._build_payload(
            identification,
            exported_at=exported_at or datetime.now(),
            include_responsible_person=include_responsible_person,
        )

    def _build_payload(
        self,
        identification,
        *,
        exported_at: datetime,
        include_responsible_person: bool,
    ) -> dict:
        items = hazard_inventory_item_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        item_export_ids: dict[int, str] = {
            item.id: f"ITEM-{index:03d}" for index, item in enumerate(items, start=1)
        }

        relations = self._relation_service.repository.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        relations_by_source: dict[int, list] = {}
        for relation in relations:
            if relation.source_item_id not in item_export_ids:
                continue
            if relation.target_item_id not in item_export_ids:
                continue
            relations_by_source.setdefault(relation.source_item_id, []).append(relation)

        workplace_analysis = []
        for item in items:
            related = []
            for relation in relations_by_source.get(item.id, []):
                related.append(
                    {
                        "relation_type": relation.relation_type,
                        "relation_type_label": HAZARD_INVENTORY_RELATION_TYPE_LABELS.get(
                            relation.relation_type,
                            relation.relation_type,
                        ),
                        "target_export_id": item_export_ids[relation.target_item_id],
                        "note": relation.note or "",
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
                }
            )

        hazard_rows = identified_hazard_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        hazard_export_ids: dict[int, str] = {
            row.hazard.id: f"HAZARD-{index:03d}"
            for index, row in enumerate(hazard_rows, start=1)
        }
        hazards = []
        for row in hazard_rows:
            hazards.append(
                {
                    "export_id": hazard_export_ids[row.hazard.id],
                    "source_item_export_id": item_export_ids.get(row.hazard.inventory_item_id),
                    "name": row.hazard.name,
                    "description": row.hazard.description or "",
                    "note": row.hazard.note or "",
                    "source_type": row.hazard.source_type,
                    "source_type_label": IDENTIFIED_HAZARD_SOURCE_LABELS.get(
                        row.hazard.source_type,
                        row.hazard.source_type,
                    ),
                }
            )

        event_rows = hazard_event_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        event_export_ids: dict[int, str] = {
            row.event.id: f"EVENT-{index:03d}"
            for index, row in enumerate(event_rows, start=1)
        }
        events = []
        for row in event_rows:
            events.append(
                {
                    "export_id": event_export_ids[row.event.id],
                    "hazard_export_id": hazard_export_ids.get(row.event.identified_hazard_id),
                    "name": row.event.name,
                    "description": row.event.description or "",
                    "note": row.event.note or "",
                }
            )

        assessment_rows = hazard_risk_assessment_service.get_for_identification(
            identification.id,
            include_inactive=False,
        )
        risk_assessments = []
        for index, row in enumerate(assessment_rows, start=1):
            assessment = row.assessment
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
            risk_assessments.append(
                {
                    "export_id": f"ASSESSMENT-{index:03d}",
                    "event_export_id": event_export_ids.get(assessment.hazard_event_id),
                    "exposed_group": assessment.exposed_group,
                    "consequence": assessment.consequence or "",
                    "severity": assessment.severity,
                    "severity_label": format_risk_severity_label(assessment.severity),
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

        return {
            "schema_version": AI_CONSULTATION_SCHEMA_VERSION,
            "export_type": AI_CONSULTATION_EXPORT_TYPE,
            "exported_at": exported_at.isoformat(timespec="seconds"),
            "application_version": APP_VERSION,
            "identification": identification_block,
            "workplace_analysis": workplace_analysis,
            "hazards": hazards,
            "events": events,
            "risk_assessments": risk_assessments,
            "consultation_request": {
                "request_summary": (
                    "Navrhni možné doplnění evidence identifikace nebezpečí "
                    "podle pravidel v pokyn_pro_AI.txt."
                ),
                "requested_proposal_types": [
                    "workplace_analysis_item",
                    "hazard",
                    "event",
                    "exposed_group",
                    "consequence",
                    "existing_measure",
                    "required_measure",
                    "legal_link",
                ],
                "rules": [
                    "Nevydávat návrhy za úplné ani definitivní.",
                    "Nevytvářet číselné hodnocení rizika.",
                    "Neměnit existující záznamy.",
                    "Jasně oddělit existující data od nových návrhů.",
                    "U každého návrhu uvést zdůvodnění.",
                    "Právní vazby označit jako návrhy k odbornému ověření.",
                    "Odpověď vrátit pouze podle přiloženého schématu.",
                ],
            },
        }

    def _build_overview(self, payload: dict, counts: dict[str, int]) -> str:
        identification = payload["identification"]
        lines = [
            "Přehled exportu podkladů pro konzultaci s AI",
            "============================================",
            "",
            f"Číslo identifikace: {identification.get('identification_number', '')}",
            f"Provoz: {identification.get('operation', '')}",
            f"Pracoviště: {identification.get('workplace', '')}",
            f"Část pracoviště: {identification.get('workplace_part', '') or '—'}",
            "",
            f"Položky analýzy pracoviště: {counts['item_count']}",
            f"Nebezpečí: {counts['hazard_count']}",
            f"Nežádoucí události: {counts['event_count']}",
            f"Posouzení rizik: {counts['assessment_count']}",
            f"Existující opatření: {counts['existing_measure_count']}",
            f"Potřebná další opatření: {counts['required_measure_count']}",
            "",
            "Soubor slouží pouze pro orientaci uživatele.",
            "",
        ]
        return "\n".join(lines)


hazard_ai_export_service = HazardAiExportService()
