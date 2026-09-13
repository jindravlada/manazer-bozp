"""Sdílené testovací prostředí pro fáze 92a/92b – jeden workspace, konzistentní singletony."""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import patch

from tests.temp_dir_helpers import create_tracked_temp_dir

TMP = create_tracked_temp_dir()

_patch = patch.object(Path, "home", return_value=TMP)
_patch.start()

import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()

import core.database.session as session_module

importlib.reload(session_module)

import core.services.attachment_service as attachment_module
import core.services.control_result_photo_service as control_result_photo_module

for module in (
    attachment_module,
    control_result_photo_module,
):
    importlib.reload(module)

import core.services.attachment_backup_diagnostic_service as attachment_diagnostic_module

importlib.reload(attachment_diagnostic_module)

from core.database.database_initializer import initialize_database

initialize_database()

from core.services.attachment_backup_diagnostic_service import (  # noqa: E402
    attachment_backup_diagnostic_service,
)
from core.services.attachment_service import attachment_service  # noqa: E402
from core.services.control_result_photo_service import control_result_photo_service  # noqa: E402
from core.services.storage_service import storage_service  # noqa: E402

__all__ = [
    "TMP",
    "attachment_backup_diagnostic_service",
    "attachment_service",
    "control_result_photo_service",
    "session_module",
    "storage_service",
]
