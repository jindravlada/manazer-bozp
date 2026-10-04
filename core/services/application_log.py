"""Souborový log aplikace ve standardním adresáři logů.

Linux: ``~/.local/share/manazer-bozp/logy/app.log``
Windows: ``%LOCALAPPDATA%\\manazer-bozp\\logy\\app.log``

Používá standardní modul ``logging``. Handler se připojí k root loggeru
až při prvním zajištění, ne při importu.
"""

from __future__ import annotations

import logging
from pathlib import Path

from core.services.storage_service import storage_service

_LOG_FILE_NAME = "app.log"
_HANDLER_MARKER = "_manazer_bozp_application_log"
_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def application_log_path() -> Path:
    """Cesta k aplikačnímu logu. Adresář vytvoří, soubor ještě ne."""
    storage_service.ensure_structure()
    return storage_service.logs_dir / _LOG_FILE_NAME


def ensure_application_file_logging() -> Path:
    """Připojí jeden file handler na root logger a vrátí cestu k souboru."""
    path = application_log_path()
    root = logging.getLogger()
    for handler in root.handlers:
        if getattr(handler, _HANDLER_MARKER, False):
            return path

    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setLevel(logging.ERROR)
    handler.setFormatter(logging.Formatter(_FORMAT))
    setattr(handler, _HANDLER_MARKER, True)
    root.addHandler(handler)
    return path
