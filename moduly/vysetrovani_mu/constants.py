from core.shared.constants import ACCIDENT_FINDING_TYPES
import json
from pathlib import Path

MU_STATUS_PROBIHA = "Probíhá"
MU_STATUS_DOKONCENO = "Dokončeno"
MU_STATUS_ODLOZENO = "Odloženo"

DEFAULT_MU_STATUS = MU_STATUS_PROBIHA

VALID_MU_STATUSES = frozenset(
    {
        MU_STATUS_PROBIHA,
        MU_STATUS_DOKONCENO,
        MU_STATUS_ODLOZENO,
    }
)

MU_STATUS_FILTER_PROBIHA = "Probíhá"
MU_STATUS_FILTER_DOKONCENO = "Dokončeno"
MU_STATUS_FILTER_ODLOZENO = "Odloženo"
MU_STATUS_FILTER_VSE = "Vše"

DEFAULT_MU_STATUS_FILTER = MU_STATUS_FILTER_PROBIHA

MU_STATUS_BY_FILTER = {
    MU_STATUS_FILTER_PROBIHA: MU_STATUS_PROBIHA,
    MU_STATUS_FILTER_DOKONCENO: MU_STATUS_DOKONCENO,
    MU_STATUS_FILTER_ODLOZENO: MU_STATUS_ODLOZENO,
}

EVENT_CHARACTER_URAZ = "Úraz"
EVENT_CHARACTER_POSKOZENI_ZARIZENI = "Poškození zařízení"
EVENT_CHARACTER_NEHODA_ZELEZNICE = "Nehoda na železnici"
EVENT_CHARACTER_PORUSENI_BOZP = "Porušení BOZP"
EVENT_CHARACTER_JINA_MU = "Jiná mimořádná událost"

DEFAULT_EVENT_CHARACTER = EVENT_CHARACTER_JINA_MU

EVENT_CHARACTERS = (
    EVENT_CHARACTER_URAZ,
    EVENT_CHARACTER_POSKOZENI_ZARIZENI,
    EVENT_CHARACTER_NEHODA_ZELEZNICE,
    EVENT_CHARACTER_PORUSENI_BOZP,
    EVENT_CHARACTER_JINA_MU,
)

SOURCE_TYPE_ACCIDENT = "accident"
SOURCE_TYPE_AUDIT = "audit"
SOURCE_TYPE_CONTROL = "control"
SOURCE_TYPE_MANUAL = "manual"
SOURCE_TYPE_OTHER = "other"

DEFAULT_SOURCE_TYPE = SOURCE_TYPE_MANUAL

SOURCE_TYPE_LABELS = {
    SOURCE_TYPE_ACCIDENT: "Kniha úrazů",
    SOURCE_TYPE_AUDIT: "Audit",
    SOURCE_TYPE_CONTROL: "Kontrola",
    SOURCE_TYPE_OTHER: "Jiný podnět",
    SOURCE_TYPE_MANUAL: "Ruční založení",
}

SOURCE_TYPES = (
    SOURCE_TYPE_ACCIDENT,
    SOURCE_TYPE_AUDIT,
    SOURCE_TYPE_CONTROL,
    SOURCE_TYPE_OTHER,
    SOURCE_TYPE_MANUAL,
)

SOURCE_TYPES_WITH_RECORD = frozenset(
    {
        SOURCE_TYPE_ACCIDENT,
        SOURCE_TYPE_AUDIT,
        SOURCE_TYPE_CONTROL,
    }
)

SOURCE_TYPES_WITH_TEXT = frozenset(
    {
        SOURCE_TYPE_OTHER,
    }
)

MU_INVESTIGATION_FINDING_TYPES = ACCIDENT_FINDING_TYPES

ISHIKAWA_CATEGORIES = (
    "Člověk",
    "Pracovní postup",
    "Technika / zařízení",
    "Prostředí",
    "Organizace práce",
    "Řízení a kontrola",
    "Komunikace",
    "Ostatní",
)

ISHIKAWA_STATUS_HYPOTEZA = "hypoteza"
ISHIKAWA_STATUS_POTVRZENO = "potvrzeno"
ISHIKAWA_STATUS_VYVRACENO = "vyvraceno"

ISHIKAWA_STATUS_LABELS = {
    ISHIKAWA_STATUS_HYPOTEZA: "Hypotéza",
    ISHIKAWA_STATUS_POTVRZENO: "Potvrzeno",
    ISHIKAWA_STATUS_VYVRACENO: "Vyvráceno",
}

ISHIKAWA_STATUSES = (
    ISHIKAWA_STATUS_HYPOTEZA,
    ISHIKAWA_STATUS_POTVRZENO,
    ISHIKAWA_STATUS_VYVRACENO,
)

ISHIKAWA_LEVEL_BEZPROSTREDNI = "bezprostredni"
ISHIKAWA_LEVEL_ZAKLADNI = "zakladni"
ISHIKAWA_LEVEL_SYSTEMOVA = "systemova"

ISHIKAWA_LEVEL_LABELS = {
    ISHIKAWA_LEVEL_BEZPROSTREDNI: "Bezprostřední příčina",
    ISHIKAWA_LEVEL_ZAKLADNI: "Základní příčina",
    ISHIKAWA_LEVEL_SYSTEMOVA: "Systémová příčina",
}

ISHIKAWA_LEVELS = (
    ISHIKAWA_LEVEL_BEZPROSTREDNI,
    ISHIKAWA_LEVEL_ZAKLADNI,
    ISHIKAWA_LEVEL_SYSTEMOVA,
)

ISHIKAWA_OTHER_FACTOR = "Jiné"
ISHIKAWA_TRIGGER_NONE_LABEL = "Žádná"


def _ishikawa_factor(
    name: str,
    *questions: str,
    evidence: list[str] | None = None,
    related: list[str] | None = None,
    parent: str = "",
    supports: list[str] | None = None,
    contradicts: list[str] | None = None,
    actions: list[str] | None = None,
    suggest: list[dict] | None = None,
) -> dict:
    return {
        "name": name,
        "questions": list(questions),
        "evidence": list(evidence or []),
        "related": list(related or []),
        "parent": parent.strip(),
        "supports": list(supports or []),
        "contradicts": list(contradicts or []),
        "actions": list(actions or []),
        "suggest": [dict(item) for item in (suggest or [])],
    }


_ISHIKAWA_SEED_PATH = (
    Path(__file__).resolve().parents[2]
    / "ciselniky/modulove/vysetrovani_mu/ishikawa_faktory.json"
)


def _ishikawa_minimal_fallback_catalog() -> dict[str, dict]:
    return {
        category: {
            "question": "Existovala jiná okolnost, která mohla přispět ke vzniku události?",
            "factors": [_ishikawa_factor(ISHIKAWA_OTHER_FACTOR)],
        }
        for category in ISHIKAWA_CATEGORIES
    }


def _load_ishikawa_fallback_catalog() -> dict[str, dict]:
    if _ISHIKAWA_SEED_PATH.is_file():
        return json.loads(_ISHIKAWA_SEED_PATH.read_text(encoding="utf-8"))
    return _ishikawa_minimal_fallback_catalog()


ISHIKAWA_FALLBACK_CATALOG: dict[str, dict] = _load_ishikawa_fallback_catalog()


def ishikawa_factors_for_category(category: str) -> tuple[str, ...]:
    from moduly.vysetrovani_mu.sluzby.ishikawa_factors_service import ishikawa_factors_service

    return ishikawa_factors_service.get_factors(category)


def ishikawa_question_for_category(category: str) -> str:
    from moduly.vysetrovani_mu.sluzby.ishikawa_factors_service import ishikawa_factors_service

    return ishikawa_factors_service.get_question(category)

YEAR_FILTER_VSE = "Vše"
