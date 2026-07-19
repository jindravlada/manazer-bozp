"""Generování dokumentu Pravidla bezpečné práce (PBP).

PBP-1: pouze veřejné API a stub bez logiky sestavení pravidel.
"""

from __future__ import annotations


class PravidlaBezpecnePraceService:
    """Služba pro sestavení a později export Pravidel bezpečné práce."""

    def generate(
        self,
        endangered_group_id: int,
        operation_id: int,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
    ) -> list:
        """Vrátí seznam pravidel pro zadaný filtr.

        V PBP-1 zatím vrací prázdný seznam – logika generování přijde později.
        """
        _ = (
            endangered_group_id,
            operation_id,
            workplace_id,
            workplace_part_id,
        )
        return []


pravidla_bezpecne_prace_service = PravidlaBezpecnePraceService()
