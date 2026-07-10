"""Přístup k oficiální historii verzí projektu."""

from __future__ import annotations

import sys
from pathlib import Path

CHANGELOG_FILENAME = "CHANGELOG.md"


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def changelog_path() -> Path:
    candidates = [project_root() / CHANGELOG_FILENAME]

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        candidates.extend(
            [
                meipass / CHANGELOG_FILENAME,
                meipass.parent / CHANGELOG_FILENAME,
            ]
        )

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    return candidates[0].resolve()


def changelog_exists() -> bool:
    return changelog_path().is_file()


def load_changelog_text() -> str:
    path = changelog_path()
    if not path.is_file():
        return f"Soubor {CHANGELOG_FILENAME} nebyl nalezen:\n{path}"
    return path.read_text(encoding="utf-8")
