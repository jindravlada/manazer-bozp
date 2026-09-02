"""Řádky Přehledu výsledků pro prověrky a audity.

Bez Qt. Nesestavuje CELKOVÉ HODNOCENÍ ani přílohy.
"""

from __future__ import annotations

import logging

from core.shared.sluzby.control_activity_statistics_service import (
    ControlActivityStatistics,
)

logger = logging.getLogger(__name__)

NELZE_POSOUDIT_OVERVIEW_LABEL = "Nelze posoudit"


def rating_category_sum(stats: ControlActivityStatistics) -> int:
    """Součet kategorií, které patří do počtu hodnocených bodů."""
    return (
        stats.ratings_vyhovuje
        + stats.ratings_vyhovuje_s_doporucenim
        + stats.ratings_nevyhovuje
        + stats.ratings_netyka_se
    )


def warn_if_checked_points_mismatch(stats: ControlActivityStatistics) -> bool:
    """Zaloguje nesoulad invariantu; data nemění. True = nesoulad."""
    total = rating_category_sum(stats)
    if total == stats.control_points_checked:
        return False
    logger.warning(
        "Nesoulad součtu výsledků kontroly: "
        "control_points_checked=%s vyhovuje=%s "
        "vyhovuje_s_doporucenim=%s nevyhovuje=%s "
        "nelze_posoudit=%s soucet_kategorii=%s",
        stats.control_points_checked,
        stats.ratings_vyhovuje,
        stats.ratings_vyhovuje_s_doporucenim,
        stats.ratings_nevyhovuje,
        stats.ratings_netyka_se,
        total,
    )
    return True


def format_result_overview_rating_lines(
    stats: ControlActivityStatistics,
    *,
    scope_label: str,
    scope_count: int,
    points_label: str,
) -> list[str]:
    """Společné řádky přehledu včetně vždy zobrazeného Nelze posoudit."""
    warn_if_checked_points_mismatch(stats)
    return [
        f"{scope_label}: {scope_count}",
        f"{points_label}: {stats.control_points_checked}",
        f"Vyhovuje: {stats.ratings_vyhovuje}",
        f"Vyhovuje s doporučením: {stats.ratings_vyhovuje_s_doporucenim}",
        f"Nevyhovuje: {stats.ratings_nevyhovuje}",
        f"{NELZE_POSOUDIT_OVERVIEW_LABEL}: {stats.ratings_netyka_se}",
    ]
