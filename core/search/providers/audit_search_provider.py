"""Poskytovatel globálního vyhledávání pro modul Audity."""

from __future__ import annotations

from moduly.audity.constants import PLANNED_MONTH_NAMES
from moduly.audity.sluzby.audit_service import audit_service

from core.search.constants import SOURCE_TYPE_AUDIT
from core.search.search_provider import SearchProvider
from core.search.global_search_result import GlobalSearchResult
from core.search.search_utils import contains_query

_PRIORITY_TITLE_MATCH = 100
_PRIORITY_DESCRIPTION_MATCH = 50
_PRIORITY_OTHER_MATCH = 30


class AuditSearchProvider(SearchProvider):
    provider_key = "audits"
    module_key = "audity"
    module_label = "Audity"

    def search(self, query: str, *, limit: int) -> list[GlobalSearchResult]:
        results: list[GlobalSearchResult] = []

        for audit in audit_service.get_all():
            number = audit.number or ""
            title = number or f"Audit {audit.id}"
            status = audit_service.derive_status(audit.started_at, audit.finished_at)
            planned_month = self._planned_month_label(audit.planned_month)
            conclusion = self._conclusion_text(audit, status)
            note = audit.title or ""

            priority = self._match_priority(
                query,
                title=number,
                description=note,
                workplace_name=audit.workplace_name,
                planned_month=planned_month,
                planned_month_number=audit.planned_month,
                audit_type=audit.audit_type,
                status=status,
                conclusion=conclusion,
            )
            if priority is None:
                continue

            subtitle = " | ".join(
                part
                for part in (
                    status,
                    audit.workplace_name,
                    audit.audit_type,
                )
                if part
            )
            description = note or conclusion

            results.append(
                GlobalSearchResult(
                    entity_type=SOURCE_TYPE_AUDIT,
                    entity_id=audit.id,
                    title=title,
                    subtitle=subtitle,
                    description=description[:120],
                    sort_key=(-priority, title.casefold(), audit.id),
                    module_key=self.module_key,
                    group_label=self.module_label,
                    priority=priority,
                    metadata={"status": status},
                )
            )

        results.sort(
            key=lambda item: item.sort_key or (-item.priority, item.title.casefold(), item.entity_id)
        )
        return results[:limit]

    @staticmethod
    def _planned_month_label(planned_month: int | None) -> str:
        if planned_month is None or planned_month < 1 or planned_month > 12:
            return ""
        return PLANNED_MONTH_NAMES[planned_month - 1]

    @staticmethod
    def _conclusion_text(audit, status: str) -> str:
        summary = audit_service.get_conclusion_summary(audit.id)
        parts = [status]
        if summary["findings_open"]:
            parts.append(f"{summary['findings_open']} otevřených zjištění")
        if summary["tasks_active"]:
            parts.append(f"{summary['tasks_active']} aktivních úkolů")
        return " — ".join(parts)

    @staticmethod
    def _match_priority(query: str, **fields: object) -> int | None:
        title = str(fields.get("title") or "")
        description = str(fields.get("description") or "")

        if contains_query(query, title):
            return _PRIORITY_TITLE_MATCH
        if contains_query(query, description):
            return _PRIORITY_DESCRIPTION_MATCH

        planned_month_number = fields.get("planned_month_number")
        other_values = (
            fields.get("workplace_name"),
            fields.get("planned_month"),
            str(planned_month_number) if planned_month_number is not None else "",
            fields.get("audit_type"),
            fields.get("status"),
            fields.get("conclusion"),
        )
        if contains_query(query, *other_values):
            return _PRIORITY_OTHER_MATCH

        return None
