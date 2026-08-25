"""Souhrnné systémové úkoly pro ohlašovací povinnosti pracovního úrazu (KU-UX-13)."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from core.shared.constants import ENTITY_ACCIDENT
from moduly.kniha_urazu.sluzby.accident_reporting_obligations import (
    SECTION_ODESLANI,
    SECTION_OHLASENI,
    SECTION_PREDANI,
    SECTION_ZAZNAM,
    applicable_obligations,
    obligation_default_deadline,
    obligation_notification_date,
    obligation_rows_for_summary,
    row_is_done,
)


OHLASENI_TASK_TITLE_PREFIX = "Termín ohlášení pracovního úrazu"
ZAZNAM_TASK_TITLE_PREFIX = "Termín odeslání Záznamu o pracovním úrazu"

_RECORD_SECTIONS = frozenset({SECTION_ZAZNAM, SECTION_ODESLANI, SECTION_PREDANI})


def ohlaseni_task_title(number: str) -> str:
    return f"{OHLASENI_TASK_TITLE_PREFIX} č. {number}"


def zaznam_task_title(number: str) -> str:
    return f"{ZAZNAM_TASK_TITLE_PREFIX} č. {number}"


def is_ohlaseni_reporting_task_title(title: str) -> bool:
    text = (title or "").strip()
    return text == OHLASENI_TASK_TITLE_PREFIX or text.startswith(
        f"{OHLASENI_TASK_TITLE_PREFIX} č."
    )


def is_zaznam_reporting_task_title(title: str) -> bool:
    text = (title or "").strip()
    return text == ZAZNAM_TASK_TITLE_PREFIX or text.startswith(
        f"{ZAZNAM_TASK_TITLE_PREFIX} č."
    )


def is_accident_reporting_task_title(title: str) -> bool:
    return is_ohlaseni_reporting_task_title(title) or is_zaznam_reporting_task_title(title)


class AccidentReportingTaskService:
    def sync_for_accident(
        self,
        accident,
        saved_data: dict[str, Any] | None = None,
    ) -> None:
        """Vytvoří / aktualizuje / dokončí souhrnné úkoly podle aktuálních povinností."""
        if accident is None or getattr(accident, "id", None) is None:
            return

        data = saved_data if saved_data is not None else self._load_saved_data(accident.id)
        obligations = applicable_obligations(accident, saved_data=data)
        rows = obligation_rows_for_summary(accident, data)
        rows_by_key = {
            (row.get("key") or "").strip(): row
            for row in rows
            if (row.get("key") or "").strip()
        }
        notification_date = obligation_notification_date(accident, data)
        number = (getattr(accident, "number", "") or "").strip() or str(accident.id)

        ohlaseni = [item for item in obligations if item.section == SECTION_OHLASENI]
        record = [item for item in obligations if item.section in _RECORD_SECTIONS]

        self._sync_group(
            accident=accident,
            obligations=ohlaseni,
            rows_by_key=rows_by_key,
            notification_date=notification_date,
            title=ohlaseni_task_title(number),
            title_matcher=is_ohlaseni_reporting_task_title,
            deadline_section=SECTION_OHLASENI,
            description_intro=(
                f"Společný termín ohlášení pracovního úrazu č. {number}."
            ),
        )
        self._sync_group(
            accident=accident,
            obligations=record,
            rows_by_key=rows_by_key,
            notification_date=notification_date,
            title=zaznam_task_title(number),
            title_matcher=is_zaznam_reporting_task_title,
            deadline_section=SECTION_ZAZNAM,
            description_intro=(
                f"Společný termín vyhotovení, odeslání a předání "
                f"Záznamu o pracovním úrazu č. {number}."
            ),
        )

    def _sync_group(
        self,
        *,
        accident,
        obligations: list,
        rows_by_key: dict[str, dict[str, Any]],
        notification_date: date | None,
        title: str,
        title_matcher,
        deadline_section: str,
        description_intro: str,
    ) -> None:
        from moduly.ukoly.sluzby.task_service import task_service

        open_task = self._find_open_task(accident.id, title_matcher)

        if not obligations:
            if open_task is not None:
                task_service.mark_completed(open_task.id)
            return

        all_done = all(
            row_is_done(rows_by_key.get(item.key, {"key": item.key}))
            for item in obligations
        )
        if all_done:
            if open_task is not None:
                task_service.mark_completed(open_task.id)
            return

        due_date = obligation_default_deadline(
            notification_date,
            section=deadline_section,
        )
        description = self._build_description(description_intro, obligations)

        if open_task is not None:
            task_service.update_task(
                open_task.id,
                title=title,
                description=description,
                priority=open_task.priority or "Normální",
                due_date=due_date,
                responsible_person_id=open_task.responsible_person_id,
                workplace_id=open_task.workplace_id or getattr(accident, "workplace_id", None),
                completed=False,
                note=open_task.note or "",
                requires_verification=False,
            )
            return

        task_service.create_task(
            title=title,
            description=description,
            due_date=due_date,
            workplace_id=getattr(accident, "workplace_id", None),
            source_module=ENTITY_ACCIDENT,
            source_record_id=accident.id,
            requires_verification=False,
        )

    def _build_description(self, intro: str, obligations: list) -> str:
        lines = [intro, "", "Zahrnuté povinnosti:"]
        for item in obligations:
            lines.append(f"• {item.label}")
        return "\n".join(lines)

    def _find_open_task(self, accident_id: int, title_matcher):
        from moduly.ukoly.sluzby.task_service import task_service

        for task in task_service.repository.list_by_source(
            source_module=ENTITY_ACCIDENT,
            source_record_id=accident_id,
        ):
            if task.completed or task.canceled:
                continue
            if title_matcher(task.title):
                return task
        return None

    def _load_saved_data(self, accident_id: int) -> dict[str, Any]:
        from moduly.kniha_urazu.sluzby.investigation_service import investigation_service

        investigation = investigation_service.get_or_create(accident_id)
        raw = getattr(investigation, "zajisteni_dukazu_json", "") or ""
        if not raw.strip():
            return {}
        try:
            data = json.loads(raw)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}


accident_reporting_task_service = AccidentReportingTaskService()
