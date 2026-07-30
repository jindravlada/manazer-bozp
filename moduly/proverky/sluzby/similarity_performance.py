"""SIMILARITY-PERF-1: diagnostika výkonu načítání výsledků podobností.

Měření probíhá pouze v DEBUG režimu (`__debug__` a logger na úrovni DEBUG).
Výsledek pro uživatele se nemění.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_LABEL_WIDTH = 26


def similarity_perf_enabled() -> bool:
    """True jen v DEBUG režimu — jinak se vůbec neměří."""
    return bool(__debug__) and logger.isEnabledFor(logging.DEBUG)


@dataclass
class SimilarityPerformanceTimings:
    """Časy jednotlivých fází načtení výsledků (sekundy)."""

    db_s: float = 0.0
    checked_s: float = 0.0
    prepare_s: float = 0.0
    table_s: float = 0.0
    _t0: float = field(default=0.0, repr=False)

    def mark_start(self) -> None:
        self._t0 = time.perf_counter()

    def take(self) -> float:
        now = time.perf_counter()
        elapsed = now - self._t0
        self._t0 = now
        return elapsed

    @property
    def total_s(self) -> float:
        return self.db_s + self.checked_s + self.prepare_s + self.table_s

    def format_report(self) -> str:
        lines = [
            "SIMILARITY PERFORMANCE",
            "",
            _format_line("Načtení DB", self.db_s),
            _format_line("Načtení checked", self.checked_s),
            _format_line("Příprava dat", self.prepare_s),
            _format_line("Vytvoření tabulky", self.table_s),
            "",
            _format_line("Celkem", self.total_s),
        ]
        return "\n".join(lines)

    def log(self) -> None:
        if not similarity_perf_enabled():
            return
        logger.debug("\n%s", self.format_report())


def _format_line(label: str, seconds: float) -> str:
    pad = "." * max(2, _LABEL_WIDTH - len(label))
    return f"{label} {pad} {seconds:.3f} s"


def new_timings_if_enabled() -> SimilarityPerformanceTimings | None:
    if not similarity_perf_enabled():
        return None
    timings = SimilarityPerformanceTimings()
    timings.mark_start()
    return timings
