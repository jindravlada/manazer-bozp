"""Zobrazení úkolů v tabulce a příprava pro budoucí ikonové typy."""

from __future__ import annotations

from moduly.ukoly.constants import (
    DEFAULT_TASK_TYPE,
    TASK_TYPE_ADMINISTRATIVE,
    TASK_TYPE_AUDIT,
    TASK_TYPE_CONTROL,
    TASK_TYPE_CORRECTIVE,
    TASK_TYPE_INVESTIGATION_ACTION,
    TASK_TYPE_LABELS,
)

# Sloupce tabulky Úkoly (index 0 = skryté ID).
COL_ID = 0
COL_INDICATOR = 1
COL_DESCRIPTION = 2
COL_DUE_DATE = 3
COL_RESPONSIBLE = 4
COL_WORKPLACE = 5
COL_SOURCE = 6
COL_SOURCE_RECORD = 7
COL_TYPE = 8

COLUMN_COUNT = 9

# Přepínač pro budoucí ikony před popisem; sloupec Typ pak lze skrýt.
TASK_TYPE_ICONS_ENABLED = False

# Klíče ikon pro budoucí zobrazení (emoji nebo Qt theme icon name).
TASK_TYPE_ICON_KEYS: dict[str, str | None] = {
    TASK_TYPE_CORRECTIVE: "corrective",
    TASK_TYPE_INVESTIGATION_ACTION: "investigation",
    TASK_TYPE_ADMINISTRATIVE: "administrative",
    TASK_TYPE_CONTROL: "control",
    TASK_TYPE_AUDIT: "audit",
}


def task_type_key(task) -> str:
    return getattr(task, "task_type", "") or DEFAULT_TASK_TYPE


def task_type_table_label(task) -> str:
    return TASK_TYPE_LABELS.get(task_type_key(task), task_type_key(task) or "—")


def task_description_icon(task) -> str:
    """Budoucí ikona před popisem. Zatím prázdné."""
    if not TASK_TYPE_ICONS_ENABLED:
        return ""

    icon_key = TASK_TYPE_ICON_KEYS.get(task_type_key(task))
    if not icon_key:
        return ""

    # Připraveno pro mapování klíč -> emoji/Qt ikona.
    return ""


def task_description_table_text(task) -> str:
    title = (getattr(task, "title", "") or "—").strip()
    icon = task_description_icon(task)
    if icon:
        return f"{icon}  {title}"
    return title
