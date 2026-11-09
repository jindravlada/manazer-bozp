"""Časové pole vyšetřování MU. Není společný editor celé aplikace."""

from __future__ import annotations

import re

from PySide6.QtWidgets import QLineEdit

_HHMM = re.compile(r"^(\d{1,2})[:.](\d{2})$")
_HHMMSS = re.compile(r"^(\d{1,2})[:.](\d{2})[:.](\d{2})$")

PRECISION_HHMM = "hhmm"
PRECISION_HHMMSS = "hhmmss"


def _in_range(hour: int, minute: int, second: int = 0) -> bool:
    return 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59


def canonical_time(text: str, precision: str) -> str | None:
    """Platný čas ve tvaru HH:MM, nebo HH:MM:SS. Neúplný vstup je neplatný."""
    raw = (text or "").strip()
    if not raw:
        return None

    if precision == PRECISION_HHMM:
        match = _HHMM.fullmatch(raw)
        if match:
            hour, minute = int(match.group(1)), int(match.group(2))
            if _in_range(hour, minute):
                return f"{hour:02d}:{minute:02d}"
            return None
        match = _HHMMSS.fullmatch(raw)
        if match:
            hour, minute, second = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
            if _in_range(hour, minute, second) and second == 0:
                return f"{hour:02d}:{minute:02d}"
        return None

    match = _HHMMSS.fullmatch(raw)
    if not match:
        return None
    hour, minute, second = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    if not _in_range(hour, minute, second):
        return None
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def display_stored_time(raw: str, precision: str) -> tuple[str, bool]:
    """Vrátí text do pole a příznak, že původní zápis nelze bezpečně převést.

    Platný čas a zápis s tečkou se sjednotí. U HH:MM se nuly v sekundách
    zobrazí bez sekund. Ostatní historický text zůstane beze změny.
    """
    text = "" if raw is None else str(raw).strip()
    if not text:
        return "", False
    canonical = canonical_time(text, precision)
    if canonical is not None:
        return canonical, False
    return text, True


def clock_for_instant(text: str) -> str:
    """Čas použitelný pro okamžik. Neúplný zápis nevrací půlnoc ani nuly."""
    hhmm = canonical_time(text, PRECISION_HHMM)
    if hhmm is not None:
        return hhmm
    return canonical_time(text, PRECISION_HHMMSS) or ""


class MuTimeLineEdit(QLineEdit):
    """Jedno časové pole. Prázdné je platné, neupravený historický text se nemaže."""

    def __init__(self, precision: str = PRECISION_HHMM, parent=None):
        super().__init__(parent)
        self._precision = precision
        self._stored_raw = ""
        self._loaded_display = ""
        self._preserved = False
        self._edited = False
        self._loading = False
        self.setPlaceholderText("HH:MM" if precision == PRECISION_HHMM else "HH:MM:SS")
        self.textChanged.connect(self._on_text_changed)
        self.editingFinished.connect(self._canonicalize_if_edited)

    def set_stored_text(self, value: str | None) -> None:
        raw = "" if value is None else str(value)
        display, preserved = display_stored_time(raw, self._precision)
        self._stored_raw = raw
        self._loaded_display = display
        self._preserved = preserved
        self._edited = False
        self._loading = True
        self.setText(display)
        self._loading = False
        self._refresh_mark()

    def value_for_save(self) -> str:
        if not self._edited:
            if self._preserved:
                return self._stored_raw
            return self._loaded_display
        current = self.text().strip()
        if not current:
            return ""
        canonical = canonical_time(current, self._precision)
        if canonical is not None:
            return canonical
        return current

    def blocks_save(self) -> bool:
        if not self._edited:
            return False
        current = self.text().strip()
        if not current:
            return False
        return canonical_time(current, self._precision) is None

    def _on_text_changed(self, _text: str) -> None:
        if self._loading:
            return
        self._edited = self.text() != self._loaded_display
        self._refresh_mark()

    def _canonicalize_if_edited(self) -> None:
        if self._loading or not self._edited:
            return
        canonical = canonical_time(self.text().strip(), self._precision)
        if not canonical or canonical == self.text():
            self._refresh_mark()
            return
        self._loading = True
        self.setText(canonical)
        self._loading = False
        self._edited = canonical != self._loaded_display
        self._refresh_mark()

    def _refresh_mark(self) -> None:
        if self.blocks_save():
            shape = "HH:MM:SS" if self._precision == PRECISION_HHMMSS else "HH:MM"
            self.setStyleSheet(
                "QLineEdit { border: 1px solid #c62828; background-color: #fff4f4; }"
            )
            self.setToolTip(f"Zadejte čas ve tvaru {shape}, nebo pole vymažte.")
            return
        if self._preserved and not self._edited:
            shape = "HH:MM:SS" if self._precision == PRECISION_HHMMSS else "HH:MM"
            self.setStyleSheet(
                "QLineEdit { border: 1px solid #ef6c00; background-color: #fff8e1; }"
            )
            self.setToolTip(
                "Původní zápis nelze bezpečně převést a zůstane uložený. "
                f"Až ho budete měnit, zadejte čas ve tvaru {shape}, nebo pole vymažte."
            )
            return
        self.setStyleSheet("")
        self.setToolTip("")
