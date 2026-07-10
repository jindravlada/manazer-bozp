"""Poskytovatel globálního vyhledávání pro modul Kniha úrazů."""

from __future__ import annotations

from moduly.kniha_urazu.sluzby.accident_service import accident_service

from core.search.constants import SOURCE_TYPE_ACCIDENT
from core.search.search_provider import SearchProvider
from core.search.global_search_result import GlobalSearchResult
from core.search.search_utils import contains_query

_PRIORITY_TITLE_MATCH = 100
_PRIORITY_DESCRIPTION_MATCH = 50
_PRIORITY_OTHER_MATCH = 30


class AccidentSearchProvider(SearchProvider):
    provider_key = "accidents"
    module_key = "kniha_urazu"
    module_label = "Kniha úrazů"

    def search(self, query: str, *, limit: int) -> list[GlobalSearchResult]:
        results: list[GlobalSearchResult] = []

        for accident in accident_service.get_all():
            number = accident.number or ""
            employee_name = accident.employee_name
            title = number or f"Úraz {accident.id}"
            if employee_name:
                title = f"{title} — {employee_name}"

            description = (
                accident.popis_urazoveho_deje
                or accident.description
                or ""
            )
            accident_date = (
                accident.accident_date.strftime("%d.%m.%Y")
                if accident.accident_date is not None
                else ""
            )

            priority = self._match_priority(
                query,
                title=number,
                employee_name=employee_name,
                first_name=accident.employee_first_name,
                last_name=accident.employee_last_name,
                description=description,
                workplace_name=accident.workplace_name,
                pracoviste=accident.pracoviste,
                accident_date=accident_date,
            )
            if priority is None:
                continue

            subtitle = " | ".join(
                part
                for part in (
                    employee_name,
                    accident.workplace_name or accident.pracoviste,
                    accident_date,
                    accident.status,
                )
                if part
            )

            results.append(
                GlobalSearchResult(
                    entity_type=SOURCE_TYPE_ACCIDENT,
                    entity_id=accident.id,
                    title=title,
                    subtitle=subtitle,
                    description=description[:120],
                    sort_key=(-priority, title.casefold(), accident.id),
                    module_key=self.module_key,
                    group_label=self.module_label,
                    priority=priority,
                    metadata={"status": accident.status},
                )
            )

        results.sort(
            key=lambda item: item.sort_key or (-item.priority, item.title.casefold(), item.entity_id)
        )
        return results[:limit]

    @staticmethod
    def _match_priority(query: str, **fields: object) -> int | None:
        number = str(fields.get("title") or "")
        employee_name = str(fields.get("employee_name") or "")

        if contains_query(query, number, employee_name):
            return _PRIORITY_TITLE_MATCH

        description = str(fields.get("description") or "")
        if contains_query(query, description):
            return _PRIORITY_DESCRIPTION_MATCH

        other_values = (
            fields.get("first_name"),
            fields.get("last_name"),
            fields.get("workplace_name"),
            fields.get("pracoviste"),
            fields.get("accident_date"),
        )
        if contains_query(query, *other_values):
            return _PRIORITY_OTHER_MATCH

        return None
