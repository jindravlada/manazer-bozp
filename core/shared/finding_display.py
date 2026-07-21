from core.shared.constants import (
    FINDING_STATUS_OTEVRENE,
    FINDING_STATUS_V_PROCESU,
    FINDING_STATUS_VYPORADANO,
    FINDING_TYPE_BEZPROSTREDNI_PRICINA,
    FINDING_TYPE_NEDOSTATEK,
    FINDING_TYPE_NESHODA,
    FINDING_TYPE_OPATRENI,
    FINDING_TYPE_POKYN,
    FINDING_TYPE_POZOROVANI,
    FINDING_TYPE_PORUSENI_PREDPISU,
    FINDING_TYPE_PRILEZITOST,
    FINDING_TYPE_SYSTEMOVA_PRICINA,
    FINDING_TYPE_ZAKLADNI_PRICINA,
    FINDING_TYPE_ZAVADA,
    FINDING_TYPE_ZJISTENI,
)
from core.theme.status_colors import (
    STATUS_DONE_BG,
    STATUS_DONE_TEXT,
    STATUS_IN_PROGRESS_BG,
    STATUS_MISSING_BG,
    STATUS_MISSING_TEXT,
    STATUS_ORANGE_TEXT,
)

FINDING_STATUS_LABELS = {
    FINDING_STATUS_OTEVRENE: "Otevřené",
    FINDING_STATUS_V_PROCESU: "V procesu",
    FINDING_STATUS_VYPORADANO: "Vypořádané",
}

FINDING_TYPE_LABELS = {
    FINDING_TYPE_ZAVADA: "Závada",
    FINDING_TYPE_NEDOSTATEK: "Nedostatek",
    FINDING_TYPE_NESHODA: "Neshoda",
    FINDING_TYPE_PRILEZITOST: "Příležitost ke zlepšování",
    FINDING_TYPE_POZOROVANI: "Pozorování",
    FINDING_TYPE_POKYN: "Pokyn",
    FINDING_TYPE_ZJISTENI: "Zjištění",
    FINDING_TYPE_BEZPROSTREDNI_PRICINA: "Bezprostřední příčina",
    FINDING_TYPE_ZAKLADNI_PRICINA: "Základní příčina",
    FINDING_TYPE_SYSTEMOVA_PRICINA: "Systémová příčina",
    FINDING_TYPE_PORUSENI_PREDPISU: "Porušení předpisu",
    FINDING_TYPE_OPATRENI: "Opatření",
}


def finding_status_label(status: str) -> str:
    return FINDING_STATUS_LABELS.get(status, status)


def finding_type_label(finding_type: str) -> str:
    return FINDING_TYPE_LABELS.get(finding_type, finding_type)


def finding_status_background(status: str) -> str:
    if status == FINDING_STATUS_VYPORADANO:
        return STATUS_DONE_BG
    if status == FINDING_STATUS_V_PROCESU:
        return STATUS_IN_PROGRESS_BG
    return STATUS_MISSING_BG


def finding_status_text_color(status: str) -> str:
    if status == FINDING_STATUS_VYPORADANO:
        return STATUS_DONE_TEXT
    if status == FINDING_STATUS_V_PROCESU:
        return STATUS_ORANGE_TEXT
    return STATUS_MISSING_TEXT
