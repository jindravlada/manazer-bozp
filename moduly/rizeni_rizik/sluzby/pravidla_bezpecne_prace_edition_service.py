"""Služba evidence vydání Pravidel bezpečné práce (PBP-5a)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from moduly.rizeni_rizik.modely.pravidla_bezpecne_prace_edition import (
    PravidlaBezpecnePraceEdition,
    PravidlaBezpecnePraceEditionRule,
)
from moduly.rizeni_rizik.repository.pravidla_bezpecne_prace_edition_repository import (
    PravidlaBezpecnePraceEditionRepository,
)
from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_comparison import (
    PravidlaBezpecnePraceComparison,
    compare_rules_to_edition,
)
from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
    PravidloBezpecnePrace,
)


class PravidlaBezpecnePraceEditionService:
    """Ukládá a vyhledává vydání PBP podle rozsahu."""

    def __init__(self) -> None:
        self.repository = PravidlaBezpecnePraceEditionRepository()

    def compare_to_latest(
        self,
        *,
        endangered_group_id: int,
        operation_id: int,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
        rules: list[PravidloBezpecnePrace],
    ) -> PravidlaBezpecnePraceComparison:
        """Porovná aktuální pravidla s posledním vydáním stejného rozsahu."""
        previous = self.get_latest_edition(
            endangered_group_id=endangered_group_id,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
        )
        return compare_rules_to_edition(rules, previous)

    def record_edition(
        self,
        *,
        endangered_group_id: int,
        operation_id: int,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
        rules: list[PravidloBezpecnePrace],
        export_path: Path | str | None = None,
        issued_at: datetime | None = None,
    ) -> PravidlaBezpecnePraceEdition:
        """Uloží snapshot vydání. Volat až po úspěšném vytvoření ODT."""
        if workplace_id is None:
            workplace_part_id = None

        edition = PravidlaBezpecnePraceEdition(
            issued_at=issued_at or datetime.now(),
            endangered_group_id=endangered_group_id,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
            export_file_path=str(export_path) if export_path is not None else None,
        )
        for index, rule in enumerate(rules, start=1):
            edition.rules.append(self._rule_snapshot(rule, sort_order=index))
        return self.repository.add(edition)

    def get_latest_edition(
        self,
        *,
        endangered_group_id: int,
        operation_id: int,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
    ) -> PravidlaBezpecnePraceEdition | None:
        """Vrátí poslední vydání stejné kombinace rozsahu, nebo None."""
        if workplace_id is None:
            workplace_part_id = None
        return self.repository.get_latest_for_scope(
            endangered_group_id=endangered_group_id,
            operation_id=operation_id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
        )

    @staticmethod
    def _rule_snapshot(
        rule: PravidloBezpecnePrace,
        *,
        sort_order: int,
    ) -> PravidlaBezpecnePraceEditionRule:
        sources_payload = [
            {
                "measure_id": source.measure_id,
                "source_hazard_id": source.source_hazard_id,
                "source_event_id": source.source_event_id,
                "severity": source.severity,
            }
            for source in rule.sources
        ]
        return PravidlaBezpecnePraceEditionRule(
            sort_order=sort_order,
            display_text=rule.text,
            normalized_text=rule.text.casefold(),
            severity=rule.severity,
            severity_rank=rule.severity_rank,
            measure_id=rule.measure_id,
            unsuitable_for_employee=rule.unsuitable_for_employee,
            sources_json=json.dumps(sources_payload, ensure_ascii=False),
        )


pravidla_bezpecne_prace_edition_service = PravidlaBezpecnePraceEditionService()
