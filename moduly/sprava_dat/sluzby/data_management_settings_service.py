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


@dataclass(frozen=True)
class RegistryExportRecord:
    created_at: str
    path: str
    manifest: dict

    def to_dict(self) -> dict:
        return {
            "created_at": self.created_at,
            "path": self.path,
            "manifest": self.manifest,
        }

    @classmethod
    def from_dict(cls, payload: dict | None) -> "RegistryExportRecord | None":
        if not payload:
            return None
        return cls(
            created_at=str(payload.get("created_at") or ""),
            path=str(payload.get("path") or ""),
            manifest=dict(payload.get("manifest") or {}),
        )


@dataclass(frozen=True)
class RegistryImportRecord:
    created_at: str
    source_path: str
    safety_backup_path: str
    import_result: dict

    def to_dict(self) -> dict:
        return {
            "created_at": self.created_at,
            "source_path": self.source_path,
            "safety_backup_path": self.safety_backup_path,
            "import_result": self.import_result,
        }

    @classmethod
    def from_dict(cls, payload: dict | None) -> "RegistryImportRecord | None":
        if not payload:
            return None
        return cls(
            created_at=str(payload.get("created_at") or ""),
            source_path=str(payload.get("source_path") or ""),
            safety_backup_path=str(payload.get("safety_backup_path") or ""),
            import_result=dict(payload.get("import_result") or {}),
        )


@dataclass(frozen=True)
class CodebooksExportRecord:
    created_at: str
    path: str
    manifest: dict
    export_type: str

    def to_dict(self) -> dict:
        return {
            "created_at": self.created_at,
            "path": self.path,
            "manifest": self.manifest,
            "export_type": self.export_type,
        }

    @classmethod
    def from_dict(cls, payload: dict | None) -> "CodebooksExportRecord | None":
        if not payload:
            return None
        return cls(
            created_at=str(payload.get("created_at") or ""),
            path=str(payload.get("path") or ""),
            manifest=dict(payload.get("manifest") or {}),
            export_type=str(payload.get("export_type") or ""),
        )


@dataclass(frozen=True)
class CodebooksImportRecord:
    created_at: str
    source_path: str
    safety_backup_path: str
    import_result: dict

    def to_dict(self) -> dict:
        return {
            "created_at": self.created_at,
            "source_path": self.source_path,
            "safety_backup_path": self.safety_backup_path,
            "import_result": self.import_result,
        }

    @classmethod
    def from_dict(cls, payload: dict | None) -> "CodebooksImportRecord | None":
        if not payload:
            return None
        return cls(
            created_at=str(payload.get("created_at") or ""),
            source_path=str(payload.get("source_path") or ""),
            safety_backup_path=str(payload.get("safety_backup_path") or ""),
            import_result=dict(payload.get("import_result") or {}),
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

    def get_last_registry_export(self) -> RegistryExportRecord | None:
        return RegistryExportRecord.from_dict(self._load().get("last_registry_export"))

    def save_last_registry_export(self, record: RegistryExportRecord) -> None:
        payload = self._load()
        payload["last_registry_export"] = record.to_dict()
        self._save(payload)

    def get_last_registry_import(self) -> RegistryImportRecord | None:
        return RegistryImportRecord.from_dict(self._load().get("last_registry_import"))

    def save_last_registry_import(self, record: RegistryImportRecord) -> None:
        payload = self._load()
        payload["last_registry_import"] = record.to_dict()
        self._save(payload)

    def get_last_registry_pre_import_backup(self) -> BackupRecord | None:
        return BackupRecord.from_dict(self._load().get("last_registry_pre_import_backup"))

    def save_last_registry_pre_import_backup(self, record: BackupRecord) -> None:
        payload = self._load()
        payload["last_registry_pre_import_backup"] = record.to_dict()
        self._save(payload)

    def get_last_diagnostic(self) -> dict | None:
        payload = self._load().get("last_diagnostic")
        return dict(payload) if isinstance(payload, dict) else None

    def save_last_diagnostic(self, result: dict) -> None:
        payload = self._load()
        payload["last_diagnostic"] = result
        self._save(payload)

    def get_last_codebooks_export(self) -> CodebooksExportRecord | None:
        return CodebooksExportRecord.from_dict(self._load().get("last_codebooks_export"))

    def save_last_codebooks_export(self, record: CodebooksExportRecord) -> None:
        payload = self._load()
        payload["last_codebooks_export"] = record.to_dict()
        self._save(payload)

    def get_last_codebooks_import(self) -> CodebooksImportRecord | None:
        return CodebooksImportRecord.from_dict(self._load().get("last_codebooks_import"))

    def save_last_codebooks_import(self, record: CodebooksImportRecord) -> None:
        payload = self._load()
        payload["last_codebooks_import"] = record.to_dict()
        self._save(payload)

    def get_last_codebooks_pre_import_backup(self) -> BackupRecord | None:
        return BackupRecord.from_dict(self._load().get("last_codebooks_pre_import_backup"))

    def save_last_codebooks_pre_import_backup(self, record: BackupRecord) -> None:
        payload = self._load()
        payload["last_codebooks_pre_import_backup"] = record.to_dict()
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
