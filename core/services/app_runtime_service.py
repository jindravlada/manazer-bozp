from datetime import datetime

APP_STARTED_AT = datetime.now()


def mark_application_started() -> datetime:
    """Zapamatuje čas startu aktuálního běhu aplikace."""
    global APP_STARTED_AT
    APP_STARTED_AT = datetime.now()
    return APP_STARTED_AT


def application_started_at() -> datetime:
    return APP_STARTED_AT
