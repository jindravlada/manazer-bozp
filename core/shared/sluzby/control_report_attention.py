"""Text sekce Oblasti vyžadující pozornost.

Bez Qt. Rozhoduje prioritu zdrojů a deduplikaci; nenačítá data z DB.
Kladné znění kontrolní otázky se jako popis problému nepoužívá.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from core.shared.constants import (
    CONTROL_RESULT_NEVYHOVUJE,
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
)

ATTENTION_RESULT_ICON = {
    CONTROL_RESULT_NEVYHOVUJE: "🔴",
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM: "🟡",
}

ATTENTION_RESULT_WORDS = {
    CONTROL_RESULT_NEVYHOVUJE: "Nevyhovuje",
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM: "Vyhovuje s doporučením",
}


def _clean(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def format_neutral_attention_label(
    *,
    area_label: str = "",
    section_label: str = "",
    result: str = "",
) -> str:
    """Identifikace oblasti a sekce s výsledkem, bez znění otázky."""
    area = _clean(area_label)
    section = _clean(section_label)
    result_label = ATTENTION_RESULT_WORDS.get(result, _clean(result))
    if area and section and area != section:
        ident = f"{area} — {section}"
    else:
        ident = area or section
    if ident and result_label:
        return f"{ident} ({result_label})"
    return ident or result_label or "—"


def _point_id(value) -> str:
    return _clean(value)


def _finding_sort_key(finding) -> tuple:
    return (
        int(getattr(finding, "display_order", 0) or 0),
        int(getattr(finding, "id", 0) or 0),
    )


def _result_sort_key(row) -> tuple:
    return (
        0 if getattr(row, "result", "") == CONTROL_RESULT_NEVYHOVUJE else 1,
        _clean(getattr(row, "source_area_label", "")),
        _clean(getattr(row, "source_section_label", "")),
        _clean(getattr(row, "source_control_point_label", "")),
        int(getattr(row, "id", 0) or 0),
    )


def _add_unique(texts: list[str], seen: set[str], value: str) -> None:
    text = _clean(value)
    if not text or text in seen:
        return
    seen.add(text)
    texts.append(text)


def attention_texts_for_point(
    row,
    findings: Sequence,
    *,
    task_title_by_finding_id: Mapping[int, str] | None = None,
) -> list[str]:
    """Vrátí 1–N popisů problému pro jeden kontrolní bod / tvrzení."""
    titles = task_title_by_finding_id or {}
    ordered = sorted(findings, key=_finding_sort_key)

    descriptions: list[str] = []
    seen: set[str] = set()
    for finding in ordered:
        _add_unique(descriptions, seen, getattr(finding, "description", ""))
    if descriptions:
        return descriptions

    note = _clean(getattr(row, "note", ""))
    if note:
        return [note]

    actions: list[str] = []
    seen_actions: set[str] = set()
    for finding in ordered:
        _add_unique(actions, seen_actions, getattr(finding, "recommended_action", ""))
    if actions:
        return actions

    task_titles: list[str] = []
    seen_titles: set[str] = set()
    for finding in ordered:
        finding_id = int(getattr(finding, "id", 0) or 0)
        _add_unique(task_titles, seen_titles, titles.get(finding_id, ""))
    if task_titles:
        return task_titles

    return [
        format_neutral_attention_label(
            area_label=getattr(row, "source_area_label", ""),
            section_label=getattr(row, "source_section_label", ""),
            result=getattr(row, "result", ""),
        )
    ]


def finding_task_ids(findings: Sequence) -> list[int]:
    """Jedinečná ``task_id`` v pořadí Finding, bez prázdných."""
    ids: list[int] = []
    seen: set[int] = set()
    for finding in sorted(findings, key=_finding_sort_key):
        raw = getattr(finding, "task_id", None)
        if not raw:
            continue
        task_id = int(raw)
        if task_id in seen:
            continue
        seen.add(task_id)
        ids.append(task_id)
    return ids


def map_task_titles_by_finding_id(
    findings: Sequence,
    tasks_by_id: Mapping[int, object],
) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for finding in findings:
        finding_id = int(getattr(finding, "id", 0) or 0)
        task_id = getattr(finding, "task_id", None)
        if not finding_id or not task_id:
            continue
        task = tasks_by_id.get(int(task_id))
        title = _clean(getattr(task, "title", "") if task is not None else "")
        if title:
            mapping[finding_id] = title
    return mapping


def group_findings_by_control_point(findings: Sequence) -> dict[str, list]:
    """Seskupí Finding podle source_control_point_id. Prázdné ID se nevážou."""
    grouped: dict[str, list] = {}
    for finding in sorted(findings, key=_finding_sort_key):
        point_id = _point_id(getattr(finding, "source_control_point_id", ""))
        if not point_id:
            continue
        grouped.setdefault(point_id, []).append(finding)
    return grouped


def format_attention_areas_text(
    results: Sequence,
    findings: Sequence,
    *,
    task_title_by_finding_id: Mapping[int, str] | None = None,
) -> str:
    """Sestaví výčet s ikonami. Prázdný výčet → em dash."""
    findings_by_point = group_findings_by_control_point(findings)
    lines: list[str] = []
    for row in sorted(results, key=_result_sort_key):
        result = getattr(row, "result", "")
        icon = ATTENTION_RESULT_ICON.get(result)
        if not icon:
            continue
        point_id = _point_id(getattr(row, "source_control_point_id", ""))
        texts = attention_texts_for_point(
            row,
            findings_by_point.get(point_id, ()),
            task_title_by_finding_id=task_title_by_finding_id,
        )
        for text in texts:
            lines.append(f"{icon} {text}")
    return "\n".join(lines) if lines else "—"
