"""Generování dokumentu Pravidla bezpečné práce (PBP).

PBP-2: sběr platných (realizovaných) opatření z Registru rizik.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.utils.czech_sort import czech_sorted
from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
    hazard_existing_measure_service,
    normalize_measure_description,
)
from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
    hazard_identification_service,
)
from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
    hazard_risk_assessment_service,
)


@dataclass(frozen=True)
class PravidloBezpecnePrace:
    """Jedno pravidlo bezpečné práce odvozené z existujícího opatření."""

    text: str
    measure_id: int


class PravidlaBezpecnePraceService:
    """Služba pro sestavení a později export Pravidel bezpečné práce."""

    def generate(
        self,
        endangered_group_id: int,
        operation_id: int,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
    ) -> list[PravidloBezpecnePrace]:
        """Vrátí platná pravidla pro zadanou ohroženou skupinu a rozsah pracoviště.

        Platná = aktivní **existující** opatření (realizovaná).
        Potřebná další / neaktivní opatření se nezahrnují.
        """
        if workplace_id is None:
            workplace_part_id = None

        collected: list[PravidloBezpecnePrace] = []
        for identification in hazard_identification_service.get_all(
            include_inactive=False
        ):
            if not self._identification_in_scope(
                identification,
                operation_id=operation_id,
                workplace_id=workplace_id,
                workplace_part_id=workplace_part_id,
            ):
                continue

            for row in hazard_risk_assessment_service.get_for_identification(
                identification.id,
                include_inactive=False,
            ):
                if not self._assessment_matches_group(
                    row.assessment.id,
                    endangered_group_id,
                    legacy_exposed_group_id=row.assessment.exposed_group_id,
                ):
                    continue

                for measure in hazard_existing_measure_service.get_for_assessment(
                    row.assessment.id,
                    include_inactive=False,
                ):
                    text = (measure.description or "").strip()
                    if not text:
                        continue
                    collected.append(
                        PravidloBezpecnePrace(text=text, measure_id=measure.id)
                    )

        # Stabilní „první nalezená“ = nejnižší measure_id (dřívější záznam).
        collected.sort(key=lambda item: item.measure_id)
        return self._dedupe_and_sort(collected)

    @staticmethod
    def _identification_in_scope(
        identification,
        *,
        operation_id: int,
        workplace_id: int | None,
        workplace_part_id: int | None,
    ) -> bool:
        if identification.operation_id != operation_id:
            return False
        if workplace_part_id is not None:
            return identification.workplace_part_id == workplace_part_id
        if workplace_id is not None:
            return identification.workplace_id == workplace_id
        return True

    @staticmethod
    def _assessment_matches_group(
        assessment_id: int,
        endangered_group_id: int,
        *,
        legacy_exposed_group_id: int | None,
    ) -> bool:
        group_ids = hazard_risk_assessment_service.get_group_ids(assessment_id)
        if endangered_group_id in group_ids:
            return True
        if not group_ids and legacy_exposed_group_id == endangered_group_id:
            return True
        return False

    @staticmethod
    def _dedupe_and_sort(
        items: list[PravidloBezpecnePrace],
    ) -> list[PravidloBezpecnePrace]:
        """Odstraní textové duplicity a seřadí abecedně (bez ohledu na velikost písmen)."""
        unique: list[PravidloBezpecnePrace] = []
        seen: set[str] = set()
        for item in items:
            key = normalize_measure_description(item.text)
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return czech_sorted(unique, key=lambda item: item.text.casefold())


pravidla_bezpecne_prace_service = PravidlaBezpecnePraceService()
