"""Sdílená generace příloh kontrolních bodů / auditních tvrzení pro ODT exporty."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from core.export.odt_engine import OdtParagraph, OdtRichContent
from core.shared.constants import (
    CONTROL_RESULT_NEKONTROLOVANO,
    CONTROL_RESULT_NELZE_POSOUDIT,
    CONTROL_RESULT_NEVYHOVUJE,
    CONTROL_RESULT_VYHOVUJE,
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
)
from core.shared.control_result_display import control_result_label
from core.shared.section_summary import (
    SECTION_SUMMARY_EXPORT_LABEL,
    normalize_section_summary_text,
)

DEFAULT_RESULT_EMOJI = {
    CONTROL_RESULT_VYHOVUJE: "🟢",
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM: "🟡",
    CONTROL_RESULT_NEVYHOVUJE: "🔴",
    CONTROL_RESULT_NELZE_POSOUDIT: "⚪",
    CONTROL_RESULT_NEKONTROLOVANO: "○",
}

DEFAULT_RESULT_WORDS = {
    CONTROL_RESULT_VYHOVUJE: "Vyhovuje",
    CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM: "Vyhovuje s doporučením",
    CONTROL_RESULT_NEVYHOVUJE: "Nevyhovuje",
    CONTROL_RESULT_NELZE_POSOUDIT: "Nelze posoudit",
    CONTROL_RESULT_NEKONTROLOVANO: "Nehodnoceno",
}


@dataclass(frozen=True)
class ControlPointAppendixItem:
    """Jedna položka podrobné přílohy B (kontrolní bod / auditní tvrzení)."""

    area_label: str
    control_point_label: str
    result: str
    note: str = ""
    recommendation: str = ""
    photo_path: Path | None = None
    photo_paths: tuple[Path, ...] = ()
    section_key: tuple[str, str] | None = None
    section_summary: str = ""

    def resolved_photo_paths(self) -> list[Path]:
        paths: list[Path] = []
        seen: set[str] = set()
        candidates = list(self.photo_paths)
        if self.photo_path is not None:
            candidates.insert(0, self.photo_path)
        for candidate in candidates:
            path = Path(candidate)
            key = str(path.resolve()) if path.exists() else str(path)
            if key in seen:
                continue
            if path.is_file():
                seen.add(key)
                paths.append(path)
        return paths


def build_areas_appendix(
    names: Sequence[str],
    *,
    bold_names: bool = False,
) -> OdtRichContent:
    """Příloha A – přehled oblastí / procesů (volitelně tučné názvy)."""
    cleaned = [str(name or "").strip() for name in names if str(name or "").strip()]
    if not cleaned:
        return OdtRichContent(paragraphs=[OdtParagraph.text("Nejsou evidovány.")])
    if bold_names:
        paragraphs = [OdtParagraph.bullet_bold_name(name) for name in cleaned]
    else:
        paragraphs = [OdtParagraph.text(f"• {name}") for name in cleaned]
    return OdtRichContent(paragraphs=paragraphs)


def section_summary_paragraphs(text: str) -> list[OdtParagraph]:
    """Souhrnné sdělení za okruh — bez prázdného bloku, se zachováním odstavců."""
    cleaned = normalize_section_summary_text(text).strip()
    if not cleaned:
        return []
    paragraphs = [OdtParagraph.text(SECTION_SUMMARY_EXPORT_LABEL, bold=True)]
    for block in cleaned.split("\n"):
        if not block.strip():
            paragraphs.append(OdtParagraph.blank_line())
        else:
            paragraphs.append(OdtParagraph.text(block))
    return paragraphs


def build_detailed_control_points_appendix(
    items: Sequence[ControlPointAppendixItem],
    *,
    result_emoji: Mapping[str, str] | None = None,
    result_words: Mapping[str, str] | None = None,
    note_label: str = "Komentář:",
    include_recommendation: bool = False,
    include_question_notes: bool = True,
    empty_message: str | None = None,
) -> OdtRichContent:
    """Podrobná příloha B: oblast, kontrolní bod, výsledek, komentář, foto."""
    emoji_map = dict(DEFAULT_RESULT_EMOJI)
    if result_emoji:
        emoji_map.update(result_emoji)
    words_map = dict(DEFAULT_RESULT_WORDS)
    if result_words:
        words_map.update(result_words)

    if not items:
        if empty_message:
            return OdtRichContent(paragraphs=[OdtParagraph.text(empty_message)])
        return OdtRichContent()

    paragraphs: list[OdtParagraph] = []
    current_group: object | None = None
    emitted_summaries: set[tuple[str, str]] = set()

    for item in items:
        area = str(item.area_label or "").strip()
        control_point = str(item.control_point_label or "").strip()
        if not area or not control_point:
            continue

        group_id: object = item.section_key if item.section_key else area
        if group_id != current_group:
            if current_group is not None:
                paragraphs.append(OdtParagraph.blank_line())
            paragraphs.append(OdtParagraph.text(area, style="AuditCriterion"))
            current_group = group_id
            if item.section_key and item.section_key not in emitted_summaries:
                paragraphs.extend(section_summary_paragraphs(item.section_summary))
                emitted_summaries.add(item.section_key)

        emoji = emoji_map.get(item.result, "○")
        word = words_map.get(item.result, control_result_label(item.result))
        paragraphs.append(OdtParagraph.text(f"{emoji} {control_point} — {word}"))

        recommendation = str(item.recommendation or "").strip()
        note = str(item.note or "").strip() if include_question_notes else ""
        if (
            include_recommendation
            and not recommendation
            and item.result == CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM
            and note
        ):
            recommendation = note
            note = ""

        if include_recommendation and recommendation and (
            item.result == CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM
        ):
            paragraphs.append(OdtParagraph.text("Doporučení:", bold=True))
            paragraphs.append(OdtParagraph.text(recommendation))

        if note and note != recommendation:
            paragraphs.extend(OdtParagraph.note(note, label=note_label))

        for photo in item.resolved_photo_paths():
            paragraphs.append(OdtParagraph.image(photo))

        paragraphs.append(OdtParagraph.blank_line())

    return OdtRichContent(paragraphs=paragraphs)
