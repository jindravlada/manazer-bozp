import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.services.storage_service import storage_service

SETTINGS_FILE = "sprava_dat.json"


@dataclass(frozen=True)
class BackupRecord:
    created_at: str
    path: str
    manifest: dict
    backup_type: str

    def to_dict(self) -> dict:
        return {
            "created_at": self.created_at,
            "path": self.path,
            "manifest": self.manifest,
            "backup_type": self.backup_type,
        }

    @classmethod
    def from_dict(cls, payload: dict | None) -> "BackupRecord | None":
        if not payload:
            return None
        return cls(
            created_at=str(payload.get("created_at") or ""),
            path=str(payload.get("path") or ""),
            manifest=dict(payload.get("manifest") or {}),
            backup_type=str(payload.get("backup_type") or ""),
        )


class DataManagementSettingsService:
    """Perzistence informací o zálohách ve Správě dat."""

    def settings_path(self) -> Path:
        return storage_service.config_dir / SETTINGS_FILE

    def _load(self) -> dict:
        path = self.settings_path()
        if not path.is_file():
            return {}
        try:
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
            return payload if isinstance(payload, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, payload: dict) -> None:
        storage_service.ensure_structure()
        path = self.settings_path()
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def get_last_backup(self) -> BackupRecord | None:
        return BackupRecord.from_dict(self._load().get("last_backup"))

    def save_last_backup(self, record: BackupRecord) -> None:
        payload = self._load()
        payload["last_backup"] = record.to_dict()
        self._save(payload)

    def get_last_pre_restore_backup(self) -> BackupRecord | None:
        return BackupRecord.from_dict(self._load().get("last_pre_restore_backup"))

    def save_last_pre_restore_backup(self, record: BackupRecord) -> None:
        payload = self._load()
        payload["last_pre_restore_backup"] = record.to_dict()
        self._save(payload)

    def get_last_restore_result(self) -> dict | None:
        payload = self._load().get("last_restore_result")
        return dict(payload) if isinstance(payload, dict) else None

    def save_last_restore_result(self, result: dict) -> None:
        payload = self._load()
        payload["last_restore_result"] = result
        self._save(payload)

    @staticmethod
    def format_timestamp(value: str) -> str:
        if not value:
            return "—"
        try:
            parsed = datetime.fromisoformat(value)
            return parsed.strftime("%d.%m.%Y %H:%M:%S")
        except ValueError:
            return value

    @staticmethod
    def file_exists(path: str) -> bool:
        return bool(path) and Path(path).is_file()


data_management_settings_service = DataManagementSettingsService()
