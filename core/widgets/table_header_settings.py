"""Persistace šířek sloupců QTableWidget přes QSettings (UX-COORD-4d)."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QSettings
from PySide6.QtWidgets import QTableWidget

from core.services.storage_service import storage_service


def coordination_table_settings() -> QSettings:
    """Ini QSettings v konfiguračním adresáři aplikace."""
    directory = storage_service.config_dir
    directory.mkdir(parents=True, exist_ok=True)
    return QSettings(
        str(directory / "table_headers.ini"),
        QSettings.Format.IniFormat,
    )


def save_table_header(table: QTableWidget, key: str) -> None:
    if getattr(table, "_header_persist_blocked", False):
        return
    settings = coordination_table_settings()
    settings.setValue(key, table.horizontalHeader().saveState())
    settings.sync()


def restore_table_header(table: QTableWidget, key: str) -> bool:
    raw = coordination_table_settings().value(key)
    if raw is None:
        return False
    if isinstance(raw, QByteArray):
        state = raw
    elif isinstance(raw, (bytes, bytearray)):
        state = QByteArray(raw)
    else:
        return False
    if state.isEmpty():
        return False
    return bool(table.horizontalHeader().restoreState(state))


def enable_table_header_persistence(table: QTableWidget, key: str) -> None:
    """Zapíše stav hlavičky po ruční změně šířky (jen jednou na tabulku/klíč)."""
    if getattr(table, "_header_persist_key", None) == key:
        return
    table._header_persist_key = key
    header = table.horizontalHeader()

    def _on_section_resized(*_args) -> None:
        save_table_header(table, key)

    header.sectionResized.connect(_on_section_resized)


def configure_and_persist_table_columns(
    table: QTableWidget,
    profile: str,
    settings_key: str | None = None,
) -> None:
    """Výchozí profil + případné obnovení uložených šířek."""
    from core.widgets.table_utils import configure_table_columns

    table._header_persist_blocked = True
    try:
        configure_table_columns(table, profile)
        if settings_key:
            restore_table_header(table, settings_key)
            enable_table_header_persistence(table, settings_key)
    finally:
        table._header_persist_blocked = False
