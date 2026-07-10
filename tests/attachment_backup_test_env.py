"""Sdílené testovací prostředí pro fáze 92a/92b – jeden workspace, konzistentní singletony."""

from __future__ import annotations

import importlib
import tempfile
from pathlib import Path
from unittest.mock import patch

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(dir=_PROJECT_ROOT))

_patch = patch.object(Path, "home", return_value=TMP)
_patch.start()

import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()

import core.database.session as session_module

importlib.reload(session_module)

import core.services.attachment_service as attachment_module
import core.services.backup_manifest_service as backup_manifest_module
import core.services.backup_service as backup_module
import core.services.control_result_photo_service as control_result_photo_module

for module in (
    attachment_module,
    backup_module,
    backup_manifest_module,
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
from core.services.backup_manifest_service import backup_manifest_service  # noqa: E402
from core.services.backup_service import BACKUP_TYPE_FULL, backup_service  # noqa: E402
from core.services.control_result_photo_service import control_result_photo_service  # noqa: E402
from core.services.storage_service import storage_service  # noqa: E402

__all__ = [
    "BACKUP_TYPE_FULL",
    "TMP",
    "attachment_backup_diagnostic_service",
    "attachment_service",
    "backup_manifest_service",
    "backup_service",
    "control_result_photo_service",
    "session_module",
    "storage_service",
]
