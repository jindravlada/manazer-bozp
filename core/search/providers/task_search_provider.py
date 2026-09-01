"""Poskytovatel globálního vyhledávání pro modul Úkoly."""

from core.search.constants import SOURCE_TYPE_TASK
from core.search.global_search_result import GlobalSearchResult
from core.search.search_provider import SearchProvider
from core.search.search_utils import contains_query
from core.shared.task_source_display import task_source_label, task_source_labels, task_source_short_label, task_source_short_labels
from moduly.ukoly.sluzby.task_service import task_service

_PRIORITY_TITLE_MATCH = 100
_PRIORITY_DESCRIPTION_MATCH = 50
_PRIORITY_OTHER_MATCH = 30


class TaskSearchProvider(SearchProvider):
    provider_key = "tasks"
    module_key = "ukoly"
    module_label = "Úkoly"

    def search(self, query: str, *, limit: int) -> list[GlobalSearchResult]:
        results: list[GlobalSearchResult] = []
        tasks = task_service.get_all_tasks()
        short_labels = task_source_short_labels(tasks)
        long_labels = task_source_labels(tasks)

        for task in tasks:
            source_label = long_labels.get(int(task.id), task_source_label(task))
            source_short = short_labels.get(int(task.id), task_source_short_label(task))
            title = task.title or ""
            description = task.description or ""

            priority = self._match_priority(
                query,
                title=title,
                description=description,
                responsible_person=task.responsible_person,
                workplace_name=task.workplace_name,
                source_label=source_label,
                source_short=source_short,
                note=task.note,
                status=task.computed_status,
            )
            if priority is None:
                continue

            subtitle = f"{task.computed_status} | {task.responsible_person or 'bez osoby'}"
            if source_short and source_short != "—":
                subtitle = f"{subtitle} | {source_short}"

            results.append(
                GlobalSearchResult(
                    entity_type=SOURCE_TYPE_TASK,
                    entity_id=task.id,
                    title=title or "—",
                    subtitle=subtitle,
                    description=(description[:120] if description else ""),
                    search_text=" ".join(
                        value
                        for value in (
                            title,
                            description,
                            task.responsible_person,
                            task.workplace_name,
                            source_label,
                            source_short,
                            task.note,
                            task.computed_status,
                        )
                        if value
                    ),
                    sort_key=(-priority, title.casefold(), task.id),
                    module_key=self.module_key,
                    group_label=self.module_label,
                    priority=priority,
                    metadata={
                        "status": task.computed_status,
                        "source_module": task.source_module or "",
                    },
                )
            )

        results.sort(
            key=lambda item: item.sort_key or (-item.priority, item.title.casefold(), item.entity_id)
        )
        return results[:limit]

    @staticmethod
    def _match_priority(query: str, **fields: object) -> int | None:
        title = str(fields.get("title") or "")
        description = str(fields.get("description") or "")

        if contains_query(query, title):
            return _PRIORITY_TITLE_MATCH
        if contains_query(query, description):
            return _PRIORITY_DESCRIPTION_MATCH

        other_values = (
            fields.get("responsible_person"),
            fields.get("workplace_name"),
            fields.get("source_label"),
            fields.get("source_short"),
            fields.get("note"),
            fields.get("status"),
        )
        if contains_query(query, *other_values):
            return _PRIORITY_OTHER_MATCH

        return None
