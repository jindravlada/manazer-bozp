"""Společné určení správné, chybné a nezodpovězené odpovědi.

Detail zkoušky i protokol jen zobrazují tento výsledek. Správnost se bere
ze snapshotové odpovědi a uložené volby, ne z aktuální banky otázek.
"""

from __future__ import annotations

from moduly.testy.constants import ANSWER_KIND_IMAGE

TONE_NEUTRAL = "neutral"
TONE_CORRECT = "correct"
TONE_ERROR = "error"

CORRECT_COLOR = "#15803d"
ERROR_COLOR = "#b91c1c"
ERROR_MARK = "\u2014 chyba"
UNANSWERED_ERROR = "Nezodpovězeno \u2014 chyba"


def answer_caption(question, answer) -> str:
    """Text volby bez hodnocení. U obrázku se nebarví samotný snímek, jen popisek."""
    body = f"{answer.letter})"
    if getattr(question, "answer_kind", "") != ANSWER_KIND_IMAGE and str(answer.text or "").strip():
        body = f"{answer.letter}) {answer.text}"
    return body


def selected_answer(answers, choice):
    """Uložená volba proti řádku snapshotu. Chybějící volba je nezodpovězená."""
    if choice is None:
        return None
    wanted = int(choice.exam_answer_id)
    for answer in answers or []:
        if int(answer.id) == wanted:
            return answer
    return None


def is_incorrect_or_unanswered(selected) -> bool:
    """Správně zvolená odpověď do výpisu chyb nepatří."""
    return selected is None or not bool(getattr(selected, "is_correct", False))


def present_answer(question, answer, selected, *, evaluated: bool) -> tuple[str, str]:
    """Vrátí popisek a tón: neutral, correct, nebo error.

    Před vyhodnocením se správnost neoznačuje. Po něm je zvolená chybná
    odpověď červená s „— chyba“, správná zelená a ostatní beze změny.
    """
    caption = answer_caption(question, answer)
    if not evaluated:
        return caption, TONE_NEUTRAL
    chosen = selected is not None and int(answer.id) == int(selected.id)
    if chosen and answer.is_correct:
        return caption, TONE_CORRECT
    if chosen:
        return f"{caption} {ERROR_MARK}", TONE_ERROR
    if answer.is_correct and (selected is None or not selected.is_correct):
        return caption, TONE_CORRECT
    return caption, TONE_NEUTRAL


def qt_answer_style(tone: str) -> str:
    """Qt podoba tónu. ODT používá stejné barvy, jiný renderer."""
    if tone == TONE_CORRECT:
        return f"color: {CORRECT_COLOR}; font-weight: 700;"
    if tone == TONE_ERROR:
        return f"color: {ERROR_COLOR}; font-weight: 700;"
    return ""
