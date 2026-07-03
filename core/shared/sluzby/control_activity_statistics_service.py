from dataclasses import dataclass

from core.shared.constants import (
    CONTROL_RESULT_NEKONTROLOVANO,
    CONTROL_RESULT_NELZE_POSOUDIT,
    CONTROL_RESULT_NEVYHOVUJE,
    CONTROL_RESULT_PARENT_ENTITY_TYPES,
    CONTROL_RESULT_VYHOVUJE,
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
)
from core.shared.sluzby.control_result_service import control_result_service
from core.shared.sluzby.finding_service import finding_service
from moduly.ukoly.sluzby.task_service import task_service


@dataclass(frozen=True)
class ControlActivityStatistics:
    """Souhrn rozsahu kontroly a výsledků pro prověrku nebo audit."""

    areas_checked: int
    sections_checked: int
    control_points_checked: int
    ratings_vyhovuje: int
    ratings_nevyhovuje: int
    ratings_netyka_se: int
    ratings_nehodnoceno: int
    findings_total: int
    tasks_total: int
    ratings_vyhovuje_s_doporucenim: int = 0

    def format_lines(self) -> list[str]:
        lines = [
            f"Počet kontrolovaných oblastí: {self.areas_checked}",
            f"Počet kontrolovaných sekcí: {self.sections_checked}",
            f"Počet kontrolovaných bodů / tvrzení: {self.control_points_checked}",
            f"Počet hodnocení Vyhovuje: {self.ratings_vyhovuje}",
        ]
        if self.ratings_vyhovuje_s_doporucenim:
            lines.append(
                "Počet hodnocení Vyhovuje s doporučením: "
                f"{self.ratings_vyhovuje_s_doporucenim}"
            )
        lines.extend(
            [
                f"Počet hodnocení Nevyhovuje: {self.ratings_nevyhovuje}",
                f"Počet hodnocení Netýká se: {self.ratings_netyka_se}",
                f"Počet nehodnocených položek: {self.ratings_nehodnoceno}",
                f"Počet zjištění: {self.findings_total}",
                f"Počet úkolů / opatření: {self.tasks_total}",
            ]
        )
        return lines

    def format_text(self) -> str:
        return "\n".join(self.format_lines())


class ControlActivityStatisticsService:
    def compute(self, entity_type: str, entity_id: int) -> ControlActivityStatistics:
        self._validate_entity(entity_type, entity_id)

        results = control_result_service.get_for_entity(entity_type, entity_id)
        areas: set[str] = set()
        sections: set[tuple[str, str]] = set()
        control_points_checked = 0
        ratings_vyhovuje = 0
        ratings_vyhovuje_s_doporucenim = 0
        ratings_nevyhovuje = 0
        ratings_netyka_se = 0
        ratings_nehodnoceno = 0

        for row in results:
            area_label = str(row.source_area_label or "").strip()
            section_label = str(row.source_section_label or "").strip()

            if row.result == CONTROL_RESULT_NEKONTROLOVANO:
                ratings_nehodnoceno += 1
                continue

            control_points_checked += 1
            if area_label:
                areas.add(area_label)
            if area_label or section_label:
                sections.add((area_label, section_label))

            if row.result == CONTROL_RESULT_VYHOVUJE:
                ratings_vyhovuje += 1
            elif row.result == CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM:
                ratings_vyhovuje_s_doporucenim += 1
            elif row.result == CONTROL_RESULT_NEVYHOVUJE:
                ratings_nevyhovuje += 1
            elif row.result == CONTROL_RESULT_NELZE_POSOUDIT:
                ratings_netyka_se += 1

        findings = finding_service.get_for_entity(entity_type, entity_id)
        tasks_total = self._count_linked_tasks(findings)

        return ControlActivityStatistics(
            areas_checked=len(areas),
            sections_checked=len(sections),
            control_points_checked=control_points_checked,
            ratings_vyhovuje=ratings_vyhovuje,
            ratings_vyhovuje_s_doporucenim=ratings_vyhovuje_s_doporucenim,
            ratings_nevyhovuje=ratings_nevyhovuje,
            ratings_netyka_se=ratings_netyka_se,
            ratings_nehodnoceno=ratings_nehodnoceno,
            findings_total=len(findings),
            tasks_total=tasks_total,
        )

    @staticmethod
    def _count_linked_tasks(findings) -> int:
        seen_task_ids: set[int] = set()
        for finding in findings:
            task_id = finding.task_id
            if task_id is None or task_id in seen_task_ids:
                continue
            if task_service.get_task_by_id(task_id) is None:
                continue
            seen_task_ids.add(task_id)
        return len(seen_task_ids)

    @staticmethod
    def _validate_entity(entity_type: str, entity_id: int) -> None:
        if entity_type not in CONTROL_RESULT_PARENT_ENTITY_TYPES:
            raise ValueError(f"Neplatný entity_type pro statistiku kontroly: {entity_type}")
        if entity_id <= 0:
            raise ValueError("entity_id musí být kladné celé číslo.")


control_activity_statistics_service = ControlActivityStatisticsService()
