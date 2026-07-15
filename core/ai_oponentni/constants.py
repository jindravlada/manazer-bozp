"""Konstanty obecného modulu AI oponentního posouzení."""

AI_PEER_REVIEW_TAB_TITLE = "Oponentní posouzení AI"

AI_PEER_REVIEW_INTRO_TEXT = (
    "Exportujte podklady pro nezávislé odborné oponentní posouzení externí AI. "
    "AI navrhne možné opomenuté skutečnosti; konečné rozhodnutí vždy provádí uživatel. "
    "AI sama nic do evidence nezapisuje."
)

AI_PEER_REVIEW_EXPORT_BUTTON = "Exportovat podklady pro AI"
AI_PEER_REVIEW_IMPORT_BUTTON = "Načíst odpověď AI"
AI_PEER_REVIEW_DIALOG_TITLE = "Oponentní posouzení AI"

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
        "Navrhnout existující opatření k ověření"
    ),
    AI_PEER_REVIEW_OBJECTIVE_REQUIRED_MEASURES: "Navrhnout další potřebná opatření",
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

AI_PEER_REVIEW_SCHEMA_VERSION = "1.1"
AI_PEER_REVIEW_EXPORT_TYPE = "hazard_identification_ai_peer_review"

AI_PEER_REVIEW_FORMAT_JSON_1_1 = "JSON 1.1"
AI_PEER_REVIEW_FORMAT_TEXT = "Textový formát"
AI_PEER_REVIEW_PARSE_NO_PROPOSALS = (
    "V odpovědi AI se nepodařilo najít žádný platný návrh "
    "ve podporovaném JSON ani textovém formátu."
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
AI_PEER_REVIEW_COL_DATE = 1
AI_PEER_REVIEW_COL_MODEL = 2
AI_PEER_REVIEW_COL_ACCEPTED = 3
AI_PEER_REVIEW_COL_REJECTED = 4
AI_PEER_REVIEW_COL_FILENAME = 5
AI_PEER_REVIEW_COLUMN_COUNT = 6

AI_PEER_REVIEW_TABLE_HEADERS = [
    "ID",
    "Datum",
    "Model AI",
    "Převzato",
    "Zamítnuto",
    "Soubor",
]

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
                        "Nežádoucí událost, Ohrožená skupina, Existující opatření, "
                        "Potřebné opatření."
                    ),
                },
                "name": {
                    "type": "string",
                    "description": "Navržená položka.",
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
