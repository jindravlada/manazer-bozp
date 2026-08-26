"""Společný režim poznámek Auditů a Prověrek (AUDIT-PROVERKY-SECTION-NOTE-1).

NULL / chybějící hodnota = legacy poznámky u jednotlivých otázek.
``section-summary-v1`` = jedno souhrnné sdělení za okruh.
"""

from __future__ import annotations

NOTES_MODE_SECTION_SUMMARY_V1 = "section-summary-v1"

SECTION_SUMMARY_LABEL = "Souhrnné sdělení"
SECTION_SUMMARY_EXPORT_LABEL = "Souhrnné sdělení:"


def uses_section_summary_notes_mode(value) -> bool:
    return str(value or "").strip() == NOTES_MODE_SECTION_SUMMARY_V1


def normalize_notes_mode(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text == NOTES_MODE_SECTION_SUMMARY_V1:
        return NOTES_MODE_SECTION_SUMMARY_V1
    raise ValueError(f"Neplatný režim poznámek: {text}")


def section_summary_key(scope_id: str, section_id: str) -> tuple[str, str]:
    return (str(scope_id or "").strip(), str(section_id or "").strip())


def normalize_section_summary_text(value) -> str:
    if value is None:
        return ""
    return str(value).replace("\r\n", "\n").replace("\r", "\n")
