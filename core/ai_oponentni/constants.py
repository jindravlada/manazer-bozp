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
AI_PEER_REVIEW_INCLUDE_RESPONSIBLE_PERSON = "Zahrnout jméno odpovědné osoby"

AI_PEER_REVIEW_ZIP_FILES = (
    "pokyn_pro_AI.txt",
    "data.txt",
    "prehled.txt",
    "zadani.json",
    "schema_odpovedi.json",
)

AI_PEER_REVIEW_SCHEMA_VERSION = "1.1"
AI_PEER_REVIEW_EXPORT_TYPE = "hazard_identification_ai_peer_review"

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

DEFAULT_AI_PEER_REVIEW_PROMPT = """\
Jsi zkušený odborník BOZP.

Proveď odborné oponentní posouzení poskytnutých podkladů.

Podklady jsou hierarchické:

Analýza pracoviště → Nežádoucí události → Posouzení
→ Existující opatření → Potřebná opatření

Každý objekt má stabilní exportní ID (ITEM-…, EVENT-…, ASSESSMENT-…).
Při návrhu doplnění uveď rodiče pomocí tohoto ID (pole Rodič).

Na základě svých odborných znalostí navrhni pouze položky, které mohly být opomenuty.

Posuzuj zejména:

- zdroje analýzy / zdroje nebezpečí
- nežádoucí události
- rizika
- ohrožené osoby
- ochranná opatření
- organizační opatření
- OOPP
- technické bariéry

Pravidla:

- Nehodnoť závažnost rizik.
- Neměň existující položky.
- Nevydávej návrhy za úplné ani definitivní.
- Ke každému návrhu napiš stručné odborné zdůvodnění.
- Odpověď strukturoj podle schema_odpovedi.json (nebo použij textový formát níže).

Formát odpovědi (použij přesně tuto strukturu u každého návrhu):

Oblast: <název oblasti>
Návrh: <navržená položka>
Rodič: <exportní ID rodiče, nebo —>
Zdůvodnění: <stručné odborné zdůvodnění>

Odděl jednotlivé návrhy prázdným řádkem.
"""

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
