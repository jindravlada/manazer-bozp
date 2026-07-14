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
)

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

Na základě svých odborných znalostí navrhni pouze položky, které mohly být opomenuty.

Posuzuj zejména:

- zdroje nebezpečí
- nebezpečí
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

Formát odpovědi (použij přesně tuto strukturu u každého návrhu):

Oblast: <název oblasti>
Návrh: <navržená položka>
Zdůvodnění: <stručné odborné zdůvodnění>

Odděl jednotlivé návrhy prázdným řádkem.
"""
