"""Konstanty obecného modulu AI oponentního posouzení."""

AI_PEER_REVIEW_TAB_TITLE = "Oponentní posouzení AI"

AI_PEER_REVIEW_INTRO_TEXT = (
    "Exportujte podklady pro nezávislé odborné oponentní posouzení externí AI. "
    "Katalog zdrojů rizik uloží jeden soubor JSON; v Copilotu stačí zadat: "
    "Zpracuj dle instrukcí. "
    "AI navrhne možné opomenuté skutečnosti; konečné rozhodnutí vždy provádí uživatel. "
    "AI sama nic do evidence nezapisuje."
)

AI_PEER_REVIEW_EXPORT_BUTTON = "Exportovat podklady pro AI"
AI_PEER_REVIEW_IMPORT_BUTTON = "Načíst odpověď AI"
AI_PEER_REVIEW_DIALOG_TITLE = "Oponentní posouzení AI"
AI_PEER_REVIEW_INTERNAL_DATA_ERROR = (
    "Interní data AI oponentury jsou neúplná nebo poškozená. "
    "Zkuste obnovit export a načíst odpověď znovu."
)


def format_ai_peer_review_user_error(error: BaseException) -> str:
    """Srozumitelná zpráva pro UI – nikdy nevrací surový název interního pole."""
    if isinstance(error, KeyError):
        return AI_PEER_REVIEW_INTERNAL_DATA_ERROR
    text = str(error).strip()
    if not text:
        return AI_PEER_REVIEW_INTERNAL_DATA_ERROR
    # KeyError často končí jako „'field_name'“ bez dalšího textu.
    if len(text) >= 3 and text[0] == text[-1] == "'" and " " not in text:
        return AI_PEER_REVIEW_INTERNAL_DATA_ERROR
    return text


AI_PEER_REVIEW_RESPONSE_DIALOG_TITLE = "Načíst odpověď AI"
AI_PEER_REVIEW_RESPONSE_PLACEHOLDER = (
    "Vložte odpověď AI ve formátu JSON 2.0 (návrhové balíky), "
    "nebo načtěte soubor .json, .txt či .zip."
)

# Role odborného oponenta (R11.8)
AI_PEER_REVIEW_ROLE_QUICK = "quick_check"
AI_PEER_REVIEW_ROLE_SAFETY_TECHNICIAN = "experienced_safety_technician"
AI_PEER_REVIEW_ROLE_OIP_INSPECTOR = "oip_inspector"
AI_PEER_REVIEW_ROLE_ISO_AUDITOR = "iso_45001_auditor"
AI_PEER_REVIEW_ROLE_MAINTENANCE = "maintenance_technician"
AI_PEER_REVIEW_ROLE_ACCIDENT_INVESTIGATOR = "accident_investigator"
AI_PEER_REVIEW_ROLE_DEVILS_ADVOCATE = "devils_advocate"

AI_PEER_REVIEW_DEFAULT_ROLE = AI_PEER_REVIEW_ROLE_SAFETY_TECHNICIAN

AI_PEER_REVIEW_ROLES = (
    AI_PEER_REVIEW_ROLE_QUICK,
    AI_PEER_REVIEW_ROLE_SAFETY_TECHNICIAN,
    AI_PEER_REVIEW_ROLE_OIP_INSPECTOR,
    AI_PEER_REVIEW_ROLE_ISO_AUDITOR,
    AI_PEER_REVIEW_ROLE_MAINTENANCE,
    AI_PEER_REVIEW_ROLE_ACCIDENT_INVESTIGATOR,
    AI_PEER_REVIEW_ROLE_DEVILS_ADVOCATE,
)

AI_PEER_REVIEW_ROLE_LABELS = {
    AI_PEER_REVIEW_ROLE_QUICK: "Rychlá kontrola",
    AI_PEER_REVIEW_ROLE_SAFETY_TECHNICIAN: "Zkušený bezpečnostní technik",
    AI_PEER_REVIEW_ROLE_OIP_INSPECTOR: "Inspektor OIP",
    AI_PEER_REVIEW_ROLE_ISO_AUDITOR: "Auditor ISO 45001",
    AI_PEER_REVIEW_ROLE_MAINTENANCE: "Technik údržby",
    AI_PEER_REVIEW_ROLE_ACCIDENT_INVESTIGATOR: "Vyšetřovatel pracovního úrazu",
    AI_PEER_REVIEW_ROLE_DEVILS_ADVOCATE: "Ďáblův advokát",
}

# Hlavní cíle oponentury (výchozí: všechny zapnuté)
AI_PEER_REVIEW_OBJECTIVE_MISSING_SOURCES = "missing_analysis_sources"
AI_PEER_REVIEW_OBJECTIVE_MISSING_EVENTS = "missing_undesired_events"
AI_PEER_REVIEW_OBJECTIVE_MISSING_GROUPS = "missing_exposed_groups"
AI_PEER_REVIEW_OBJECTIVE_EXISTING_MEASURES = "propose_existing_measures"
AI_PEER_REVIEW_OBJECTIVE_REQUIRED_MEASURES = "propose_required_measures"
AI_PEER_REVIEW_OBJECTIVE_LEGAL_REQUIREMENTS = "propose_legal_requirements"
AI_PEER_REVIEW_OBJECTIVE_COMPLETENESS = "verify_identification_completeness"

AI_PEER_REVIEW_OBJECTIVES = (
    AI_PEER_REVIEW_OBJECTIVE_MISSING_SOURCES,
    AI_PEER_REVIEW_OBJECTIVE_MISSING_EVENTS,
    AI_PEER_REVIEW_OBJECTIVE_MISSING_GROUPS,
    AI_PEER_REVIEW_OBJECTIVE_EXISTING_MEASURES,
    AI_PEER_REVIEW_OBJECTIVE_REQUIRED_MEASURES,
    AI_PEER_REVIEW_OBJECTIVE_LEGAL_REQUIREMENTS,
    AI_PEER_REVIEW_OBJECTIVE_COMPLETENESS,
)

AI_PEER_REVIEW_DEFAULT_OBJECTIVES = AI_PEER_REVIEW_OBJECTIVES

AI_PEER_REVIEW_OBJECTIVE_LABELS = {
    AI_PEER_REVIEW_OBJECTIVE_MISSING_SOURCES: "Hledat chybějící zdroje analýzy",
    AI_PEER_REVIEW_OBJECTIVE_MISSING_EVENTS: "Hledat chybějící nežádoucí události",
    AI_PEER_REVIEW_OBJECTIVE_MISSING_GROUPS: "Hledat chybějící ohrožené skupiny",
    AI_PEER_REVIEW_OBJECTIVE_EXISTING_MEASURES: (
        "Posoudit Zásady bezpečné práce a navrhnout úpravy, jsou-li potřeba"
    ),
    AI_PEER_REVIEW_OBJECTIVE_REQUIRED_MEASURES: (
        "Posoudit Navazující opatření a navrhnout úpravy nebo doplnění"
    ),
    AI_PEER_REVIEW_OBJECTIVE_LEGAL_REQUIREMENTS: (
        "Navrhnout související právní požadavky"
    ),
    AI_PEER_REVIEW_OBJECTIVE_COMPLETENESS: "Ověřit úplnost identifikace",
}

# Doplňující zaměření (výchozí: vypnuto)
AI_PEER_REVIEW_FOCUS_EMERGENCY = "emergency_situations"
AI_PEER_REVIEW_FOCUS_MAINTENANCE = "maintenance"
AI_PEER_REVIEW_FOCUS_CONTRACTORS = "contractors"
AI_PEER_REVIEW_FOCUS_VISITORS = "visitors"

AI_PEER_REVIEW_FOCUS_AREAS = (
    AI_PEER_REVIEW_FOCUS_EMERGENCY,
    AI_PEER_REVIEW_FOCUS_MAINTENANCE,
    AI_PEER_REVIEW_FOCUS_CONTRACTORS,
    AI_PEER_REVIEW_FOCUS_VISITORS,
)

AI_PEER_REVIEW_FOCUS_AREA_LABELS = {
    AI_PEER_REVIEW_FOCUS_EMERGENCY: "Zaměřit se na mimořádné situace",
    AI_PEER_REVIEW_FOCUS_MAINTENANCE: "Zaměřit se na údržbu",
    AI_PEER_REVIEW_FOCUS_CONTRACTORS: "Zaměřit se na dodavatele",
    AI_PEER_REVIEW_FOCUS_VISITORS: "Zaměřit se na návštěvy",
}

AI_PEER_REVIEW_IDENTIFICATION_KIND_FIRST = "first"
AI_PEER_REVIEW_IDENTIFICATION_KIND_REVISION = "revision"

AI_PEER_REVIEW_ZIP_FILES = (
    "pokyn_pro_AI.txt",
    "data.txt",
    "prehled.txt",
    "zadani.json",
    "schema_odpovedi.json",
)

# RISK-AI-17: soubory exportu zadání nejsou odpovědí AI.
AI_PEER_REVIEW_EXPORT_RESPONSE_BASENAMES = frozenset(
    name.casefold() for name in AI_PEER_REVIEW_ZIP_FILES
)

AI_REVIEW_REQUEST_FILENAME_PREFIX = "AI_REVIEW_REQUEST"
AI_REVIEW_REQUEST_USER_INSTRUCTION = "Zpracuj dle instrukcí."
AI_REVIEW_RESPONSE_FILENAME = "AI_REVIEW_RESPONSE.json"
AI_PEER_REVIEW_JSON_FILE_FILTER = "JSON soubory (*.json)"
AI_PEER_REVIEW_ZIP_FILE_FILTER = "ZIP soubory (*.zip)"

AI_PEER_REVIEW_NOT_AI_RESPONSE = (
    "Vybrali jste exportní podklady pro AI, nikoli odpověď. "
    "Pro import výsledků vyberte soubor AI_REVIEW_RESPONSE.json "
    "nebo *_odpoved.json."
)

AI_PEER_REVIEW_SCHEMA_VERSION = "1.1"
AI_PEER_REVIEW_EXPORT_TYPE = "hazard_identification_ai_peer_review"
AI_CATALOG_PEER_REVIEW_EXPORT_TYPE = "hazard_catalog_source_ai_peer_review"

# Cíle oponentury katalogu zdrojů rizik (bez „chybějících zdrojů analýzy“)
AI_CATALOG_PEER_REVIEW_OBJECTIVES = (
    AI_PEER_REVIEW_OBJECTIVE_MISSING_EVENTS,
    AI_PEER_REVIEW_OBJECTIVE_MISSING_GROUPS,
    AI_PEER_REVIEW_OBJECTIVE_EXISTING_MEASURES,
    AI_PEER_REVIEW_OBJECTIVE_REQUIRED_MEASURES,
    AI_PEER_REVIEW_OBJECTIVE_LEGAL_REQUIREMENTS,
    AI_PEER_REVIEW_OBJECTIVE_COMPLETENESS,
)

AI_CATALOG_PEER_REVIEW_DEFAULT_OBJECTIVES = AI_CATALOG_PEER_REVIEW_OBJECTIVES

AI_CATALOG_PEER_REVIEW_CONTEXT_LABEL = "Obecný kontext zdroje rizika (volitelné):"
AI_CATALOG_PEER_REVIEW_CONTEXT_PLACEHOLDER = (
    "Např. Typické použití zdroje v provozu, specifika technologie, "
    "provozní režim nebo další odborný kontext pro posouzení katalogového zdroje."
)

AI_CATALOG_PEER_REVIEW_SCOPE_FULL_LABEL = "Celý zdroj rizika"

AI_PEER_REVIEW_SCHEMA_VERSION = "1.1"
AI_PEER_REVIEW_SCHEMA_VERSION_2_0 = "2.0"

AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT = "new_event"
AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT = "extend_event"

# RISK-AI-12 – doporučení k opatřením (revize stávajících / nové)
AI_MEASURE_REC_NO_CHANGE = "beze_zmen"
AI_MEASURE_REC_EDIT_REQUIRED = "upravit_navazujici_opatreni"
AI_MEASURE_REC_EDIT_EXISTING = "upravit_zasady_bezpecne_prace"
AI_MEASURE_REC_NEW_REQUIRED = "nove_navazujici_opatreni"

# RISK-AI-14 – doporučení beze změn nepatří do fronty ke zpracování.
AI_PEER_REVIEW_NO_CHANGE_FOUND_MESSAGE = "AI nenašla žádné návrhy změn."
AI_PEER_REVIEW_NO_CHANGE_CANNOT_DECIDE_MESSAGE = (
    "Doporučení „Beze změn“ nevyžaduje převzetí ani zamítnutí."
)

AI_MEASURE_RECOMMENDATION_TYPES = (
    AI_MEASURE_REC_NO_CHANGE,
    AI_MEASURE_REC_EDIT_REQUIRED,
    AI_MEASURE_REC_EDIT_EXISTING,
    AI_MEASURE_REC_NEW_REQUIRED,
)

AI_PEER_REVIEW_PACKAGE_TYPE_LABELS = {
    AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT: "Nová událost",
    AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT: "Doplnění události",
    AI_MEASURE_REC_NO_CHANGE: "Beze změn",
    AI_MEASURE_REC_EDIT_REQUIRED: "Úprava Navazujícího opatření",
    AI_MEASURE_REC_EDIT_EXISTING: "Úprava Zásad bezpečné práce",
    AI_MEASURE_REC_NEW_REQUIRED: "Nové Navazující opatření",
}

AI_PEER_REVIEW_FORMAT_JSON_1_1 = "JSON 1.1"
AI_PEER_REVIEW_FORMAT_JSON_2_0 = "JSON 2.0"
AI_PEER_REVIEW_FORMAT_TEXT = "Textový formát"
AI_PEER_REVIEW_FORMAT_TEXT_2_0 = "Textový formát 2.0"
AI_PEER_REVIEW_PARSE_NO_PROPOSALS = (
    "V odpovědi AI se nepodařilo najít žádný platný návrh "
    "ve podporovaném JSON ani textovém formátu."
)
AI_PEER_REVIEW_PARSE_NO_PACKAGES = (
    "V odpovědi AI se nepodařilo najít žádný platný návrhový balík "
    "ani doporučení k opatřením ve formátu schema 2.0."
)
AI_PEER_REVIEW_CATALOG_REQUIRES_SCHEMA_2_0 = (
    "Katalog zdrojů rizik vyžaduje odpověď ve formátu schema 2.0 "
    "(ucelené návrhové balíky). Atomizovaný formát schema 1.1 nelze načíst."
)
AI_PEER_REVIEW_IMPORT_INTRO_PACKAGES = (
    "Označte návrhové balíky k uložení do evidence ke zpracování. "
    "Neoznačené balíky budou evidovány jako zamítnuté."
)

AI_PEER_REVIEW_RESPONSE_ZIP_PREFERRED_NAMES = (
    "odpoved_AI.json",
    "odpoved.json",
    "response.json",
)
AI_PEER_REVIEW_RESPONSE_ZIP_MAX_UNCOMPRESSED_BYTES = 10 * 1024 * 1024
AI_PEER_REVIEW_ZIP_CORRUPT = "ZIP archiv je poškozený nebo nelze otevřít."
AI_PEER_REVIEW_ZIP_NO_RESPONSE = (
    "ZIP archiv neobsahuje žádnou podporovanou odpověď (.json nebo .txt)."
)
AI_PEER_REVIEW_ZIP_SIZE_EXCEEDED = (
    "Obsah ZIP archivu překračuje povolený limit velikosti."
)

# Dávkový export (R11.7)
AI_PEER_REVIEW_EXPORT_SCOPE_FULL = "full"
AI_PEER_REVIEW_EXPORT_SCOPE_SELECTED = "selected"
AI_PEER_REVIEW_DEFAULT_EXPORT_SCOPE = AI_PEER_REVIEW_EXPORT_SCOPE_FULL
AI_PEER_REVIEW_DEFAULT_BATCH_NUMBER = 1
AI_PEER_REVIEW_DEFAULT_BATCH_COUNT = 1
AI_PEER_REVIEW_MAX_SOURCES_PER_BATCH = 10
AI_PEER_REVIEW_MAX_OBJECTS_PER_BATCH = 200

AI_PEER_REVIEW_SCOPE_FULL_LABEL = "Celá identifikace – automaticky rozdělit do dávek"
AI_PEER_REVIEW_SCOPE_SELECTED_LABEL = "Pouze vybrané zdroje analýzy"

# Příprava změnového exportu (R11.6) – zatím vždy režim „full“.
AI_PEER_REVIEW_CHANGE_MODE_FULL = "full"
AI_PEER_REVIEW_DEFAULT_CHANGE_TRACKING = {
    "mode": AI_PEER_REVIEW_CHANGE_MODE_FULL,
    "base_export": None,
    "changed_objects": [],
}

AI_PEER_REVIEW_COL_ID = 0
AI_PEER_REVIEW_COL_EXPORT_DATE = 1
AI_PEER_REVIEW_COL_RESPONSE_DATE = 2
AI_PEER_REVIEW_COL_MODEL = 3
AI_PEER_REVIEW_COL_LOADED = 4
AI_PEER_REVIEW_COL_PENDING = 5
AI_PEER_REVIEW_COL_ACCEPTED = 6
AI_PEER_REVIEW_COL_REJECTED = 7
AI_PEER_REVIEW_COL_UNASSIGNED = 8
AI_PEER_REVIEW_COL_FILENAME = 9
AI_PEER_REVIEW_COLUMN_COUNT = 10

# Zpětná kompatibilita starých indexů sloupců
AI_PEER_REVIEW_COL_DATE = AI_PEER_REVIEW_COL_EXPORT_DATE

AI_PEER_REVIEW_TABLE_HEADERS = [
    "ID",
    "Datum exportu",
    "Datum načtení odpovědi",
    "Model AI",
    "Načteno návrhů",
    "Čeká na odborné posouzení",
    "Převzato",
    "Zamítnuto",
    "Nezařazeno",
    "Soubor",
]

AI_PEER_REVIEW_IMPORT_INTRO_EVIDENCE = (
    "Označte návrhy k uložení do evidence ke zpracování. "
    "Neoznačené návrhy budou evidovány jako zamítnuté."
)

# Zachováno pro zpětnou kompatibilitu importů; obsah se sestavuje dynamicky (R11.8).
DEFAULT_AI_PEER_REVIEW_PROMPT = (
    "Jsi zkušený bezpečnostní technik.\n"
    "Proveď odborné oponentní posouzení poskytnutých podkladů.\n"
)

AI_PEER_REVIEW_RESPONSE_SCHEMA = {
    "schema_version": "1.1",
    "description": (
        "Očekávaný formát odpovědi AI pro oponentní posouzení. "
        "Návrhy se vážou na hierarchická exportní ID z zadani.json."
    ),
    "type": "object",
    "required": [
        "schema_version",
        "source_identification_number",
        "generated_at",
        "proposals",
    ],
    "properties": {
        "schema_version": {
            "type": "string",
            "const": "1.1",
        },
        "source_identification_number": {
            "type": "string",
            "description": "Číslo identifikace z zadani.json.",
        },
        "generated_at": {
            "type": "string",
            "format": "date-time",
        },
        "proposals": {
            "type": "array",
            "items": {"$ref": "#/$defs/proposal"},
        },
    },
    "$defs": {
        "proposal": {
            "type": "object",
            "required": [
                "proposal_id",
                "area",
                "name",
                "parent_export_id",
                "reasoning",
            ],
            "properties": {
                "proposal_id": {
                    "type": "string",
                    "description": "Stabilní identifikátor návrhu v rámci odpovědi.",
                },
                "area": {
                    "type": "string",
                    "description": (
                        "Oblast návrhu, např. Analýza pracoviště, "
                        "Nežádoucí událost, Ohrožená skupina, "
                        "Zásady bezpečné práce, Navazující opatření."
                    ),
                },
                "name": {
                    "type": "string",
                    "description": "Navržená položka.",
                },
                "typ": {
                    "type": "string",
                    "enum": [
                        "beze_zmen",
                        "upravit_navazujici_opatreni",
                        "upravit_zasady_bezpecne_prace",
                        "nove_navazujici_opatreni",
                    ],
                    "description": (
                        "Volitelný typ doporučení k opatřením (RISK-AI-12). "
                        "Zpětně kompatibilní – starší odpovědi pole nemají."
                    ),
                },
                "parent_export_id": {
                    "type": ["string", "null"],
                    "description": (
                        "Exportní ID rodiče v hierarchii "
                        "(ITEM-… / EVENT-… / ASSESSMENT-…), "
                        "nebo null u nové položky analýzy pracoviště."
                    ),
                },
                "reasoning": {
                    "type": "string",
                    "description": "Stručné odborné zdůvodnění.",
                },
            },
        },
    },
}

AI_PEER_REVIEW_RESPONSE_SCHEMA_2_0 = {
    "schema_version": "2.0",
    "description": (
        "Očekávaný formát odpovědi AI pro oponentní posouzení katalogu zdrojů rizik. "
        "Návrhové balíky (událost / posouzení) a/nebo doporučení k opatřením "
        "(revize Zásad bezpečné práce a Navazujících opatření)."
    ),
    "type": "object",
    "required": [
        "schema_version",
        "source_reference",
    ],
    "properties": {
        "schema_version": {
            "type": "string",
            "const": "2.0",
        },
        "source_reference": {
            "type": "string",
            "description": "Reference zdroje z zadani.json (např. KZR-0002).",
        },
        "generated_at": {
            "type": "string",
            "format": "date-time",
        },
        "proposal_packages": {
            "type": "array",
            "items": {"$ref": "#/$defs/proposal_package"},
            "description": (
                "Ucelené balíky pro nové nebo doplněné události. "
                "Volitelné, pokud jsou vyplněna measure_recommendations."
            ),
        },
        "measure_recommendations": {
            "type": "array",
            "items": {"$ref": "#/$defs/measure_recommendation"},
            "description": (
                "Doporučení k stávajícím nebo novým opatřením "
                "(Zásady bezpečné práce / Navazující opatření)."
            ),
        },
    },
    "$defs": {
        "measure_recommendation": {
            "type": "object",
            "required": ["recommendation_id", "typ", "reasoning"],
            "properties": {
                "recommendation_id": {
                    "type": "string",
                    "description": "Stabilní identifikátor doporučení v rámci odpovědi.",
                },
                "typ": {
                    "type": "string",
                    "enum": [
                        "beze_zmen",
                        "upravit_navazujici_opatreni",
                        "upravit_zasady_bezpecne_prace",
                        "nove_navazujici_opatreni",
                    ],
                },
                "target_export_id": {
                    "type": ["string", "null"],
                    "description": (
                        "Exportní ID stávajícího opatření "
                        "(REQUIRED-MEASURE-… / EXISTING-MEASURE-…) "
                        "nebo posouzení (ASSESSMENT-…) u nového Navazujícího opatření."
                    ),
                },
                "proposed_text": {
                    "type": "string",
                    "description": (
                        "Navrhované nové znění nebo text nového opatření "
                        "(u typu beze_zmen může zůstat prázdné)."
                    ),
                },
                "reasoning": {
                    "type": "string",
                    "description": "Stručné odborné zdůvodnění.",
                },
            },
        },
        "measure": {
            "type": "object",
            "required": ["description"],
            "properties": {
                "description": {"type": "string"},
                "note": {"type": "string"},
            },
        },
        "assessment": {
            "type": "object",
            "required": [
                "exposed_group",
                "severity",
            ],
            "properties": {
                "exposed_group": {"type": "string"},
                "exposed_groups": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "severity": {
                    "type": "string",
                    "enum": [
                        "negligible",
                        "minor",
                        "moderate",
                        "serious",
                        "critical",
                    ],
                },
                "conclusion": {"type": "string"},
                "existing_measures": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/measure"},
                },
                "required_measures": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/measure"},
                },
            },
        },
        "legal_link": {
            "type": "object",
            "required": ["reference"],
            "properties": {
                "reference": {"type": "string"},
                "reasoning": {"type": "string"},
            },
        },
        "proposal_package": {
            "type": "object",
            "required": [
                "package_id",
                "package_type",
                "assessments",
            ],
            "properties": {
                "package_id": {"type": "string"},
                "package_type": {
                    "type": "string",
                    "enum": ["new_event", "extend_event"],
                },
                "target_event_export_id": {
                    "type": ["string", "null"],
                },
                "event": {
                    "type": ["object", "null"],
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "note": {"type": "string"},
                    },
                },
                "assessments": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"$ref": "#/$defs/assessment"},
                },
                "legal_links": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/legal_link"},
                },
                "reasoning": {"type": "string"},
            },
        },
    },
}
