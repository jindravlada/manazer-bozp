"""
Společné stavové barvy aplikace.

Odstíny vycházejí ze stávajícího vzhledu:
- administrativa šetření (odesláno / nevyřízeno / po termínu),
- tabulka úkolů,
- časové rozdíly ve šetření.
"""

# Pozadí stavů
STATUS_DONE_BG = "#d9f0dd"
STATUS_MISSING_BG = "#f8d7da"
STATUS_WARNING_BG = "#fff3cd"
STATUS_IN_PROGRESS_BG = "#ffe0b2"
STATUS_WAITING_BG = "#90caf9"
STATUS_NEUTRAL_BG = "#eeeeee"

# Text stavů
STATUS_DONE_TEXT = "#0b5d1e"
STATUS_MISSING_TEXT = "#842029"
STATUS_WARNING_TEXT = "#7a4b00"
STATUS_ORANGE_TEXT = "#ef6c00"
