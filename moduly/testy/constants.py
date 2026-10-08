"""Konstanty modulu Testy."""

MODULE_KEY = "testy"
MODULE_NAME = "Testy"
MODULE_DESCRIPTION = (
    "Evidence zaměstnanců, příprava testů a evidence výsledků přezkoušení."
)
PAGE_SUBTITLE = MODULE_DESCRIPTION

ACTION_NEW = "Nový zaměstnanec"
ACTION_EDIT = "Upravit"
SHOW_INACTIVE_LABEL = "Zobrazit neaktivní"
STATUS_ACTIVE_LABEL = "Aktivní"
STATUS_INACTIVE_LABEL = "Neaktivní"
DIALOG_TITLE_NEW = "Nový zaměstnanec"
DIALOG_TITLE_EDIT = "Zaměstnanec"
SEARCH_PLACEHOLDER = "🔍 Hledat zaměstnance..."

COL_ID = 0
COL_PERSONAL_NUMBER = 1
COL_LAST_NAME = 2
COL_FIRST_NAME = 3
COL_ROLES = 4
COL_WORKPLACE = 5
COL_STATUS = 6

COLUMN_HEADERS = [
    "ID",
    "Osobní číslo",
    "Příjmení",
    "Jméno",
    "Funkce / role",
    "Provoz (pracoviště)",
    "Stav",
]

AGENDA_EMPLOYEES = "Zaměstnanci"
AGENDA_WRITTEN_TOPICS = "Okruhy otázek"

TOPIC_ACTION_NEW = "Nový okruh"
TOPIC_DIALOG_TITLE_NEW = "Nový okruh"
TOPIC_DIALOG_TITLE_EDIT = "Okruh"
TOPIC_SEARCH_PLACEHOLDER = "🔍 Hledat okruh..."

TOPIC_COL_ID = 0
TOPIC_COL_NAME = 1
TOPIC_COL_DESCRIPTION = 2
TOPIC_COL_STATUS = 3

TOPIC_COLUMN_HEADERS = [
    "ID",
    "Název",
    "Popis",
    "Stav",
]

AGENDA_QUESTIONS = "Otázky"
QUESTION_ACTION_NEW = "Nová otázka"
QUESTION_DIALOG_TITLE_NEW = "Nová otázka"
QUESTION_DIALOG_TITLE_EDIT = "Otázka"
QUESTION_SEARCH_PLACEHOLDER = "🔍 Hledat otázku..."
QUESTION_TOPIC_FILTER_ALL = "Všechny okruhy"
ANSWER_KIND_TEXT = "text"
ANSWER_KIND_IMAGE = "image"
ANSWER_KIND_TEXT_LABEL = "Textové"
ANSWER_KIND_IMAGE_LABEL = "Obrázkové"
ANSWER_KIND_SWITCH_CONFIRM = (
    "Přepnutí typu odpovědí vymaže již zadané odpovědi A, B a C. Pokračovat?"
)
ANSWER_LETTERS = ("A", "B", "C")

QUESTION_COL_ID = 0
QUESTION_COL_TEXT = 1
QUESTION_COL_TOPIC = 2
QUESTION_COL_KIND = 3
QUESTION_COL_STATUS = 4

QUESTION_COLUMN_HEADERS = [
    "ID",
    "Otázka",
    "Okruh",
    "Typ odpovědí",
    "Stav",
]

AGENDA_ORAL_TOPICS = "Ústní okruhy"
AGENDA_ORAL_QUESTIONS = "Ústní otázky"

ORAL_QUESTION_COL_ID = 0
ORAL_QUESTION_COL_TEXT = 1
ORAL_QUESTION_COL_TOPIC = 2
ORAL_QUESTION_COL_STATUS = 3

ORAL_QUESTION_COLUMN_HEADERS = [
    "ID",
    "Otázka",
    "Okruh",
    "Stav",
]

AGENDA_TESTS = "Testy"
TEST_ACTION_NEW = "Nový test"
STUDY_QUESTIONS_ACTION = "Vytisknout studijní otázky"
STUDY_QUESTIONS_TITLE = "Studijní otázky k přezkoušení"
STUDY_WRITTEN_HEADING = "PÍSEMNÁ ČÁST"
STUDY_ORAL_HEADING = "Ústní otázky"
STUDY_QUESTIONS_EMPTY = (
    "K vybranému testu nejsou dostupné žádné aktivní studijní otázky."
)
TEST_DIALOG_TITLE_NEW = "Nový test"
TEST_DIALOG_TITLE_EDIT = "Test"
TEST_SEARCH_PLACEHOLDER = "🔍 Hledat test..."
PART_YES_LABEL = "Ano"
PART_NO_LABEL = "Ne"
DEFAULT_SECONDS_PER_QUESTION = 30

EXAMINER_MODE_NONE = "none"
EXAMINER_MODE_SINGLE = "single"
EXAMINER_MODE_COMMISSION = "commission"
EXAMINER_MODE_NONE_LABEL = "Bez zkoušejícího / komise"
EXAMINER_MODE_SINGLE_LABEL = "Jeden zkoušející"
EXAMINER_MODE_COMMISSION_LABEL = "Komise"
EXAMINER_MODES = (
    EXAMINER_MODE_NONE,
    EXAMINER_MODE_SINGLE,
    EXAMINER_MODE_COMMISSION,
)
EXAMINER_MODE_LABELS = {
    EXAMINER_MODE_NONE: EXAMINER_MODE_NONE_LABEL,
    EXAMINER_MODE_SINGLE: EXAMINER_MODE_SINGLE_LABEL,
    EXAMINER_MODE_COMMISSION: EXAMINER_MODE_COMMISSION_LABEL,
}

VALIDITY_UNIT_MONTHS = "months"
VALIDITY_UNIT_YEARS = "years"
VALIDITY_UNIT_MONTHS_LABEL = "měsíce"
VALIDITY_UNIT_YEARS_LABEL = "roky"
VALIDITY_UNITS = (
    VALIDITY_UNIT_MONTHS,
    VALIDITY_UNIT_YEARS,
)

TEST_COL_ID = 0
TEST_COL_NAME = 1
TEST_COL_WRITTEN = 2
TEST_COL_ORAL = 3
TEST_COL_QUESTION_COUNT = 4
TEST_COL_VALIDITY = 5
TEST_COL_STATUS = 6

TEST_COLUMN_HEADERS = [
    "ID",
    "Název",
    "Písemná část",
    "Ústní část",
    "Počet otázek",
    "Platnost",
    "Stav",
]

AGENDA_EXAMS = "Zkoušky"
EXAM_ACTION_PREPARE = "Připravit zkoušku"
EXAM_ACTION_BATCH_PAPER = "Hromadná příprava papírových testů"
EXAM_ACTION_DETAIL = "Detail"
EXAM_ACTION_START_WRITTEN = "Zahájit elektronický test"
EXAM_ACTION_CONTINUE_WRITTEN = "Pokračovat v elektronickém testu"
EXAM_ACTION_PRINT_WRITTEN = "Vytisknout písemný test"
EXAM_ACTION_PRINT_PROTOCOL = "Vytisknout protokol o zkoušce"
EXAM_ACTION_ENTER_PAPER = "Zadat odpovědi z papírového testu"
EXAM_ACTION_EVALUATE_PAPER = "Vyhodnotit písemný test"
PAPER_TEST_KEY_OPTION = "Vytvořit také klíč správných odpovědí"
PAPER_BATCH_KEY_OPTION = "Vytvořit také společný klíč správných odpovědí"
PAPER_BATCH_DIALOG_TITLE = "Hromadná příprava papírových testů"
PAPER_TEST_INSTRUCTION = (
    "U každé otázky zakroužkujte jednu správnou odpověď A, B nebo C."
)
EXAM_DIALOG_TITLE = "Připravit zkoušku"
EXAM_DETAIL_TITLE = "Zkouška"
EXAM_PROTOCOL_SECTION = "Podepsaný protokol"
EXAM_PROTOCOL_ATTACHED = "Připojen"
EXAM_PROTOCOL_MISSING = "Nepřipojen"
EXAM_PROTOCOL_NOT_APPLICABLE = "—"
EXAM_PROTOCOL_ACTION_ATTACH = "Připojit PDF"
EXAM_PROTOCOL_ACTION_OPEN = "Otevřít PDF"
EXAM_PROTOCOL_ACTION_REPLACE = "Nahradit PDF"
EXAM_PROTOCOL_ACTION_REMOVE = "Odebrat PDF"
EXAM_PROTOCOL_REPLACE_CONFIRM = (
    "Opravdu chcete nahradit připojený podepsaný protokol jiným PDF?\n\n"
    "Nový dokument se nejprve uloží. Původní soubor zůstane v úložišti, "
    "ke zkoušce se ale přiřadí až ověřená nová kopie."
)
EXAM_PROTOCOL_REMOVE_CONFIRM = (
    "Opravdu chcete odebrat vazbu na podepsaný protokol?\n\n"
    "Zkouška, její výsledek ani uložený soubor se nesmažou."
)
EXAM_PROTOCOL_FILE_FILTER = "PDF (*.pdf)"
EXAM_SEARCH_PLACEHOLDER = "🔍 Hledat zkoušku..."
EXAM_LIST_FILTER_ALL_TESTS = "Všechny testy"
EXAM_LIST_FILTER_ALL = "Vše"
EXAM_LIST_FILTER_STATUS_RUNNING = "Probíhá"
EXAM_LIST_FILTER_RESULT_NONE = "Bez výsledku"
EXAM_LIST_FILTER_ALL_YEARS = "Všechny roky"

EXAM_STATUS_PREPARED = "prepared"
EXAM_STATUS_STARTED = "started"
EXAM_STATUS_COMPLETED = "completed"
EXAM_STATUS_CANCELLED = "cancelled"
EXAM_STATUS_PREPARED_LABEL = "Připraveno"
EXAM_STATUS_STARTED_LABEL = "Zahájeno"
EXAM_STATUS_COMPLETED_LABEL = "Dokončeno"
EXAM_STATUS_CANCELLED_LABEL = "Zrušeno"
EXAM_STATUS_LABELS = {
    EXAM_STATUS_PREPARED: EXAM_STATUS_PREPARED_LABEL,
    EXAM_STATUS_STARTED: EXAM_STATUS_STARTED_LABEL,
    EXAM_STATUS_COMPLETED: EXAM_STATUS_COMPLETED_LABEL,
    EXAM_STATUS_CANCELLED: EXAM_STATUS_CANCELLED_LABEL,
}

EXAM_ROLE_EXAMINER = "examiner"
EXAM_ROLE_CHAIR = "chair"
EXAM_ROLE_MEMBER = "member"
EXAM_ROLE_EXAMINER_LABEL = "Zkoušející"
EXAM_ROLE_CHAIR_LABEL = "Předseda/předsedkyně komise"
EXAM_ROLE_MEMBER_LABEL = "Člen(ka) komise"
EXAM_ROLE_LABELS = {
    EXAM_ROLE_EXAMINER: EXAM_ROLE_EXAMINER_LABEL,
    EXAM_ROLE_CHAIR: EXAM_ROLE_CHAIR_LABEL,
    EXAM_ROLE_MEMBER: EXAM_ROLE_MEMBER_LABEL,
}

EXAM_COL_ID = 0
EXAM_COL_DATE = 1
EXAM_COL_EMPLOYEE = 2
EXAM_COL_TEST = 3
EXAM_COL_VALID_UNTIL = 4
EXAM_COL_STATUS = 5
EXAM_COL_WRITTEN_RESULT = 6
EXAM_COL_EXAM_RESULT = 7
EXAM_COL_PROTOCOL = 8

EXAM_COLUMN_HEADERS = [
    "ID",
    "Datum",
    "Zaměstnanec",
    "Test",
    "Platí do",
    "Stav",
    "Písemná část",
    "Výsledek zkoušky",
    "Podepsaný protokol",
]

AGENDA_EXAM_VALIDITY = "Platnost zkoušek"
EXAM_VALIDITY_SEARCH_PLACEHOLDER = "🔍 Hledat podle osobního čísla, jména nebo testu..."
EXAM_VALIDITY_SHOW_INACTIVE = "Zobrazit neaktivní zaměstnance"
EXAM_VALIDITY_FILTER_ALL_WORKPLACES = "Všechna pracoviště"
EXAM_VALIDITY_FILTER_ALL_TESTS = "Všechny testy"
EXAM_VALIDITY_FILTER_ALL_STATES = "Všechny stavy platnosti"
EXAM_VALIDITY_WARNING_DAYS = 30
EXAM_VALIDITY_ACTION_STOP = "Nesledovat platnost"
EXAM_VALIDITY_ACTION_RESUME = "Obnovit sledování"
EXAM_VALIDITY_STOP_CONFIRM = (
    "Opravdu chcete přestat sledovat platnost vybrané kombinace "
    "zaměstnanec a test?\n\n"
    "Zkoušky, jejich výsledky ani datum platnosti se nezmění a data se nesmažou."
)
EXAM_VALIDITY_TRACKING_ON_LABEL = "Sledovat"
EXAM_VALIDITY_TRACKING_OFF_LABEL = "Nesledovat"
EXAM_VALIDITY_TRACKING_FILTER_ALL = "all"
EXAM_VALIDITY_TRACKING_FILTER_TRACKED = "tracked"
EXAM_VALIDITY_TRACKING_FILTER_UNTRACKED = "untracked"
EXAM_VALIDITY_TRACKING_FILTER_ALL_LABEL = "Vše"
EXAM_VALIDITY_TRACKING_FILTER_TRACKED_LABEL = "Sledované"
EXAM_VALIDITY_TRACKING_FILTER_UNTRACKED_LABEL = "Nesledované"

EXAM_VALIDITY_STATE_VALID = "valid"
EXAM_VALIDITY_STATE_EXPIRING = "expiring"
EXAM_VALIDITY_STATE_EXPIRED = "expired"
EXAM_VALIDITY_STATE_UNLIMITED = "unlimited"
EXAM_VALIDITY_STATE_NO_SUCCESS = "no_success"
EXAM_VALIDITY_STATE_VALID_LABEL = "Platná"
EXAM_VALIDITY_STATE_EXPIRING_LABEL = "Končí platnost"
EXAM_VALIDITY_STATE_EXPIRED_LABEL = "Neplatná"
EXAM_VALIDITY_STATE_UNLIMITED_LABEL = "Bez omezení"
EXAM_VALIDITY_STATE_NO_SUCCESS_LABEL = "Bez úspěšné zkoušky"
EXAM_VALIDITY_STATE_LABELS = {
    EXAM_VALIDITY_STATE_VALID: EXAM_VALIDITY_STATE_VALID_LABEL,
    EXAM_VALIDITY_STATE_EXPIRING: EXAM_VALIDITY_STATE_EXPIRING_LABEL,
    EXAM_VALIDITY_STATE_EXPIRED: EXAM_VALIDITY_STATE_EXPIRED_LABEL,
    EXAM_VALIDITY_STATE_UNLIMITED: EXAM_VALIDITY_STATE_UNLIMITED_LABEL,
    EXAM_VALIDITY_STATE_NO_SUCCESS: EXAM_VALIDITY_STATE_NO_SUCCESS_LABEL,
}
EXAM_VALIDITY_STATE_ORDER = (
    EXAM_VALIDITY_STATE_VALID,
    EXAM_VALIDITY_STATE_EXPIRING,
    EXAM_VALIDITY_STATE_EXPIRED,
    EXAM_VALIDITY_STATE_UNLIMITED,
    EXAM_VALIDITY_STATE_NO_SUCCESS,
)

VALIDITY_COL_PERSONAL_NUMBER = 0
VALIDITY_COL_EMPLOYEE = 1
VALIDITY_COL_WORKPLACE = 2
VALIDITY_COL_TEST = 3
VALIDITY_COL_LAST_SUCCESS = 4
VALIDITY_COL_VALID_UNTIL = 5
VALIDITY_COL_STATE = 6
VALIDITY_COL_PREPARED = 7
VALIDITY_COL_IN_PROGRESS = 8
VALIDITY_COL_TRACKING = 9

VALIDITY_COLUMN_HEADERS = [
    "Osobní číslo",
    "Zaměstnanec",
    "Pracoviště",
    "Test",
    "Poslední úspěšná zkouška",
    "Platnost do",
    "Stav platnosti",
    "Připravené",
    "Rozpracované",
    "Sledování",
]

WRITTEN_RESULT_PASSED = "passed"
WRITTEN_RESULT_FAILED = "failed"
WRITTEN_RESULT_PASSED_LABEL = "Vyhověl(a)"
WRITTEN_RESULT_FAILED_LABEL = "Nevyhověl(a)"
WRITTEN_RESULT_LABELS = {
    WRITTEN_RESULT_PASSED: WRITTEN_RESULT_PASSED_LABEL,
    WRITTEN_RESULT_FAILED: WRITTEN_RESULT_FAILED_LABEL,
}

WRITTEN_OUTCOME_CORRECT = "correct"
WRITTEN_OUTCOME_INCORRECT = "incorrect"
WRITTEN_OUTCOME_UNANSWERED = "unanswered"
WRITTEN_OUTCOME_CORRECT_LABEL = "Správně"
WRITTEN_OUTCOME_INCORRECT_LABEL = "Chybně"
WRITTEN_OUTCOME_UNANSWERED_LABEL = "Nezodpovězeno"
WRITTEN_OUTCOME_LABELS = {
    WRITTEN_OUTCOME_CORRECT: WRITTEN_OUTCOME_CORRECT_LABEL,
    WRITTEN_OUTCOME_INCORRECT: WRITTEN_OUTCOME_INCORRECT_LABEL,
    WRITTEN_OUTCOME_UNANSWERED: WRITTEN_OUTCOME_UNANSWERED_LABEL,
}


def written_result_label(code: str | None) -> str:
    """Prázdný text, dokud písemná část nebo zkouška nemá uložený výsledek."""
    return WRITTEN_RESULT_LABELS.get(str(code or "").strip(), "")


EXAM_ACTION_RECORD_ORAL_FAILURE = "Zaznamenat neúspěch u ústní části"
EXAM_ACTION_CLEAR_ORAL_FAILURE = "Zrušit neúspěch u ústní části"
ORAL_FAILURE_CONFIRM = (
    "Opravdu chcete zaznamenat, že zaměstnanec u ústní části zkoušky nevyhověl(a)? "
    "Celkový výsledek zkoušky bude změněn na Nevyhověl(a)."
)
ORAL_FAILURE_CLEAR_CONFIRM = (
    "Opravdu chcete zrušit evidovaný neúspěch u ústní části? "
    "Jde o opravu evidovaného údaje. "
    "Výsledek zkoušky se vrátí na uložený výsledek písemné části."
)
ORAL_PART_FAILED_LINE = "Ústní část: Nevyhověl(a)"

EXAM_SNAPSHOT_ENTITY = "test_exam_snapshot"

WRITTEN_FINISH_SUBMITTED = "submitted"
WRITTEN_FINISH_EXPIRED = "expired"
WRITTEN_FINISH_PAPER = "paper"

WRITTEN_MODE_ELECTRONIC = "electronic"
WRITTEN_MODE_PAPER = "paper"

PAPER_EVALUATE_INCOMPLETE = (
    "Některé otázky nemají zadanou odpověď. "
    "Nezodpovězené otázky se při vyhodnocení počítají jako chyba. "
    "Opravdu chcete test vyhodnotit?"
)
PAPER_EVALUATE_CONFIRM = "Opravdu chcete písemný test vyhodnotit?"
PAPER_BLOCKS_ELECTRONIC = (
    "Elektronický test nelze zahájit, protože u zkoušky už probíhá "
    "zadávání papírových odpovědí."
)
ELECTRONIC_BLOCKS_PAPER = (
    "Papírové odpovědi nelze zadat, protože elektronický test už byl zahájen."
)
PAPER_ENTRY_LOCKED = "Písemná část už byla dokončena."

WRITTEN_FINISHED_TEXT = "Písemná část testu byla ukončena."
WRITTEN_HANDOVER_TEXT = (
    "Písemná část testu byla ukončena.\n"
    "Předejte počítač zkoušejícímu."
)
WRITTEN_SUBMIT_INCOMPLETE = (
    "Nemáte zodpovězeny všechny otázky. Opravdu chcete test odevzdat?"
)
WRITTEN_SUBMIT_CONFIRM = "Opravdu chcete test odevzdat?"
WRITTEN_PREVIOUS = "Předchozí"
WRITTEN_NEXT = "Další"
WRITTEN_SUBMIT = "Odevzdat test"
