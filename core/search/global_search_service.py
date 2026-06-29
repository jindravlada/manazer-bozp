from dataclasses import dataclass

from moduly.kniha_urazu.sluzby.accident_service import accident_service
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.ukoly.sluzby.task_service import task_service


@dataclass
class SearchResult:
    module_key: str
    category: str
    title: str
    subtitle: str = ""
    record_id: int | None = None
    record_type: str = ""

    @property
    def display(self) -> str:
        if self.subtitle:
            return f"{self.category}: {self.title} — {self.subtitle}"
        return f"{self.category}: {self.title}"


class GlobalSearchService:
    def search(self, text: str, limit: int = 30) -> list[SearchResult]:
        query = text.strip().lower()

        if len(query) < 2:
            return []

        results: list[SearchResult] = []

        results.extend(self._search_accidents(query))
        results.extend(self._search_tasks(query))
        results.extend(self._search_workers(query))
        results.extend(self._search_workplaces(query))
        results.extend(self._search_employer(query))

        return results[:limit]

    def _contains(self, query: str, *values) -> bool:
        haystack = " ".join(str(value or "") for value in values).lower()
        return query in haystack

    def _search_accidents(self, query: str) -> list[SearchResult]:
        results = []

        for accident in accident_service.get_all():
            if self._contains(
                query,
                accident.number,
                accident.employee_name,
                accident.workplace_name,
                accident.description,
                accident.injury_type,
                accident.injured_body_part,
            ):
                results.append(
                    SearchResult(
                        module_key="kniha_urazu",
                        category="Kniha úrazů",
                        title=f"{accident.number or 'bez čísla'} | {accident.employee_name or 'bez osoby'}",
                        subtitle=accident.description[:80] if accident.description else "",
                        record_id=accident.id,
                        record_type="accident",
                    )
                )

        return results

    def _search_tasks(self, query: str) -> list[SearchResult]:
        results = []

        for task in task_service.get_all_tasks():
            if self._contains(
                query,
                task.title,
                task.responsible_person,
                task.workplace_name,
                task.priority,
                task.computed_status,
                task.note,
            ):
                results.append(
                    SearchResult(
                        module_key="ukoly",
                        category="Úkoly",
                        title=task.title or "—",
                        subtitle=f"{task.computed_status} | {task.responsible_person or 'bez osoby'}",
                        record_id=task.id,
                        record_type="task",
                    )
                )

        return results

    def _search_workers(self, query: str) -> list[SearchResult]:
        results = []

        for worker in settings_service.get_workers(include_inactive=True):
            if self._contains(
                query,
                worker.display_name,
                worker.position,
                worker.phone,
                worker.email,
            ):
                results.append(
                    SearchResult(
                        module_key="nastaveni",
                        category="THP",
                        title=worker.display_name,
                        subtitle=worker.position or "bez funkce",
                        record_id=worker.id,
                        record_type="worker",
                    )
                )

        return results

    def _search_workplaces(self, query: str) -> list[SearchResult]:
        results = []

        for workplace in settings_service.get_workplaces(include_inactive=True):
            if self._contains(
                query,
                workplace.name,
                workplace.address,
                workplace.note,
            ):
                results.append(
                    SearchResult(
                        module_key="nastaveni",
                        category="Pracoviště",
                        title=workplace.name,
                        subtitle=workplace.address or "",
                    )
                )

        return results

    def _search_employer(self, query: str) -> list[SearchResult]:
        employer = settings_service.get_employer()

        if employer is None:
            return []

        if self._contains(
            query,
            employer.ico,
            employer.name,
            employer.address,
            employer.nace,
        ):
            return [
                SearchResult(
                    module_key="nastaveni",
                    category="Zaměstnavatel",
                    title=employer.name or "Zaměstnavatel",
                    subtitle=employer.ico or "",
                )
            ]

        return []


global_search_service = GlobalSearchService()
