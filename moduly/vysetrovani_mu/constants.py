from core.shared.constants import ACCIDENT_FINDING_TYPES

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


ISHIKAWA_FALLBACK_CATALOG: dict[str, dict] = {
    "Člověk": {
        "question": "Udělal někdo něco jinak, než měl?",
        "factors": [
            _ishikawa_factor(
                "Nedodržení pracovního postupu",
                "Znal pracovník platný pracovní postup?",
                "Byl postup dodržen v místě a čase události?",
            ),
            _ishikawa_factor(
                "Nesprávné použití zařízení",
                "Bylo zařízení použito podle návodu a určení?",
            ),
            _ishikawa_factor(
                "Nepozornost",
                "Byl pracovník soustředěný na úkol v místě a čase události?",
                "Nebyl rozptylován okolím, kolegy nebo jinými podněty?",
                "Věnoval pozornost viditelným rizikům a varovným signálům?",
                "Nevykonával současně více činností nebo nestíhal sledovat průběh práce?",
                "Neodpovídal průběh práce spíše spěchu, únavě nebo rutině než vědomé chybě?",
                evidence=[
                    "Výpověď dotčené osoby",
                    "Výpovědi svědků",
                    "Záznam z kamery",
                    "Pracovní postup a pokyny",
                    "Fotodokumentace místa",
                    "Záznamy komunikace (telefon, vysílačka)",
                    "Rozpis směn a plnění úkolů",
                ],
                related=["Spěch", "Únava", "Používání telefonu"],
                supports=[
                    "Svědci popisují rozptýlení nebo nedostatek pozornosti",
                    "Pracovník nevnímal viditelné nebezpečí nebo varování",
                    "Souběžně probíhala rušivá činnost (hovor, konverzace, hluk)",
                    "Došlo k přehlédnutí zjevného kroku postupu",
                    "Práce probíhala rutinně bez vědomé kontroly rizik",
                ],
                contradicts=[
                    "Pracovník postupoval systematicky a opakovaně kontroloval rizika",
                    "Svědci potvrdili plné soustředění na úkol",
                    "Chybu lépe vysvětluje technická závada, prostředí nebo nedostatek postupu",
                    "Pracovník jednal v souladu s postupem a přesto došlo k jiné příčině",
                ],
                actions=[
                    "Vyslechnout dotčenou osobu o průběhu práce a vnímání okolí",
                    "Vyslechnout svědky k chování a soustředění pracovníka",
                    "Prověřit záznamy z kamer v čase události",
                    "Porovnat průběh činnosti s pracovním postupem",
                    "Prověřit rušivé vlivy na pracovišti (hluk, pohyb osob, komunikace)",
                    "Zvážit zpřesnění hypotézy podřízeným faktorem (Spěch, Únava, Používání telefonu)",
                ],
                suggest=[
                    {"category": "Organizace práce", "factor": "Dlouhá směna"},
                    {"category": "Prostředí", "factor": "Vysoká teplota"},
                    {"category": "Pracovní postup", "factor": "Jiné"},
                ],
            ),
            _ishikawa_factor("Spěch", parent="Nepozornost"),
            _ishikawa_factor(
                "Únava",
                parent="Nepozornost",
                supports=[
                    "Dlouhá pracovní směna",
                    "Vysoká teplota na pracovišti",
                    "Svědci popsali únavu pracovníka",
                ],
                contradicts=[
                    "Pracovník nastoupil po odpočinku",
                    "Svědci únavu nepotvrdili",
                ],
                actions=[
                    "Prověřit délku směny",
                    "Ověřit rozpis směn za poslední dny",
                    "Vyslechnout svědky k projevu únavy",
                    "Prověřit klimatické podmínky pracoviště",
                ],
                suggest=[
                    {"category": "Prostředí", "factor": "Vysoká teplota"},
                    {"category": "Organizace práce", "factor": "Dlouhá směna"},
                    {"category": "Řízení a kontrola", "factor": "Nedostatečné plánování směn"},
                ],
            ),
            _ishikawa_factor("Stres"),
            _ishikawa_factor("Zdravotní indispozice"),
            _ishikawa_factor("Nedostatečná kvalifikace"),
            _ishikawa_factor("Rutina"),
            _ishikawa_factor("Podcenění rizika"),
            _ishikawa_factor("Používání telefonu", parent="Nepozornost"),
            _ishikawa_factor(ISHIKAWA_OTHER_FACTOR),
        ],
    },
    "Pracovní postup": {
        "question": "Byl pracovní postup jasný, známý, použitelný a dodržený?",
        "factors": [_ishikawa_factor(ISHIKAWA_OTHER_FACTOR)],
    },
    "Technika / zařízení": {
        "question": "Selhalo zařízení, nástroj nebo jeho ochranný prvek?",
        "factors": [_ishikawa_factor(ISHIKAWA_OTHER_FACTOR)],
    },
    "Prostředí": {
        "question": "Ovlivnily průběh události podmínky pracoviště?",
        "factors": [
            _ishikawa_factor("Vysoká teplota"),
            _ishikawa_factor(ISHIKAWA_OTHER_FACTOR),
        ],
    },
    "Organizace práce": {
        "question": "Byla práce organizována tak, aby mohla být provedena bezpečně?",
        "factors": [
            _ishikawa_factor("Dlouhá směna"),
            _ishikawa_factor(ISHIKAWA_OTHER_FACTOR),
        ],
    },
    "Řízení a kontrola": {
        "question": "Byla rizika řízena a kontrolována dostatečně?",
        "factors": [
            _ishikawa_factor("Nedostatečné plánování směn"),
            _ishikawa_factor(ISHIKAWA_OTHER_FACTOR),
        ],
    },
    "Komunikace": {
        "question": "Měli všichni potřebné informace ve správný čas?",
        "factors": [_ishikawa_factor(ISHIKAWA_OTHER_FACTOR)],
    },
    "Ostatní": {
        "question": "Existovala jiná okolnost, která mohla přispět ke vzniku události?",
        "factors": [_ishikawa_factor(ISHIKAWA_OTHER_FACTOR)],
    },
}


def ishikawa_factors_for_category(category: str) -> tuple[str, ...]:
    from moduly.vysetrovani_mu.sluzby.ishikawa_factors_service import ishikawa_factors_service

    return ishikawa_factors_service.get_factors(category)


def ishikawa_question_for_category(category: str) -> str:
    from moduly.vysetrovani_mu.sluzby.ishikawa_factors_service import ishikawa_factors_service

    return ishikawa_factors_service.get_question(category)

YEAR_FILTER_VSE = "Vše"
