"""Centrální definice verze aplikace Manažer BOZP."""

APP_NAME = "Manažer BOZP"
APP_EXE_NAME = "ManazerBOZP"
APP_VERSION = "3.2.0"
APP_AUTHOR = "Ing. Vladimír Jindra"
APP_COPYRIGHT = "© 2026 Ing. Vladimír Jindra"


def app_display_name() -> str:
    return f"{APP_NAME} {APP_VERSION}"


def app_brand_label() -> str:
    return f"<b>{app_display_name()}</b>"


def app_about_text() -> str:
    return f"{app_display_name()}\n\n{APP_AUTHOR}\n{APP_COPYRIGHT}"


def installer_output_basename() -> str:
    return f"Manazer_BOZP_{APP_VERSION.replace('.', '_')}_Setup"


def is_compatible_application_name(name: str) -> bool:
    normalized = (name or "").strip()
    if not normalized:
        return True
    if normalized == app_display_name():
        return True
    return normalized.startswith(f"{APP_NAME} ")
