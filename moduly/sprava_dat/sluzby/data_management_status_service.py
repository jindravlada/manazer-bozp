from datetime import datetime

from core.backup.completeness import VERDICT_COMPLETE_WITH_LIMITATIONS, VERDICT_INCOMPLETE
from core.backup.constants import INTEGRITY_VALID_WITH_WARNINGS
from core.backup.workspace_roots import (
    SNAPSHOT_SUPPORT_PHOTOS_LIMITATION,
    UNKNOWN_ROOTS_MESSAGE_PREFIX,
)
from moduly.sprava_dat.sluzby.data_management_settings_service import (
    BackupRecord,
    CodebooksExportRecord,
    CodebooksImportRecord,
    RegistryExportRecord,
    RegistryImportRecord,
    data_management_settings_service,
)
from moduly.sprava_dat.ui.manifest_presenter import STATUS_ATTENTION, STATUS_OK


class DataManagementStatusService:
    """Odvození jednoduchého stavu dat pro záložku Souhrn."""

    def compute_status(self) -> tuple[str, list[str]]:
        warnings = self.collect_warnings()
        if warnings:
            return STATUS_ATTENTION, warnings
        return STATUS_OK, []

    def collect_warnings(self) -> list[str]:
        warnings: list[str] = []

        backup = data_management_settings_service.get_last_backup()
        if backup is None:
            warnings.append("Kompletní záloha dosud nebyla vytvořena.")
        else:
            manifest = backup.manifest or {}
            if not manifest.get("verified"):
                warnings.append("Poslední kompletní záloha nebyla ověřena.")
            elif manifest.get("coverage_verdict") == VERDICT_INCOMPLETE:
                unknown = [
                    str(item)
                    for item in (manifest.get("unknown_workspace_roots") or [])
                    if str(item).strip()
                ]
                if unknown:
                    warnings.append(f"{UNKNOWN_ROOTS_MESSAGE_PREFIX}: {', '.join(unknown)}.")
                else:
                    warnings.append(
                        "Poslední úplná záloha je INCOMPLETE kvůli neznámému datovému kořenu."
                    )
            elif manifest.get("backup_health") == "warning":
                warnings.append("Poslední záloha neobsahuje všechny evidované přílohy.")
                for item in manifest.get("attachment_warnings") or []:
                    if item not in warnings:
                        warnings.append(item)
            if not data_management_settings_service.file_exists(backup.path):
                warnings.append("Soubor poslední kompletní zálohy nebyl nalezen.")

        restore = data_management_settings_service.get_last_restore_result()
        if restore:
            integrity = restore.get("integrity_check") or {}
            if not integrity.get("verified"):
                warnings.append("Poslední obnova neprošla kontrolou integrity.")

        export = data_management_settings_service.get_last_registry_export()
        if export and not export.manifest.get("verified"):
            warnings.append("Poslední export registru nebyl ověřen.")

        import_record = data_management_settings_service.get_last_registry_import()
        if self._import_failed(import_record.import_result if import_record else None):
            warnings.append("Poslední import registru se nezdařil.")
        elif self._missing_registry_preimport_backup_requires_attention(import_record):
            warnings.append("Bezpečnostní záloha před importem registru nebyla nalezena.")

        diagnostic = data_management_settings_service.get_last_diagnostic()
        if self._diagnostic_inconsistent(diagnostic):
            warnings.append("Diagnostika registru našla nekonzistence.")

        attachment_diagnostic = data_management_settings_service.get_last_attachment_diagnostic()
        if self._diagnostic_inconsistent(attachment_diagnostic):
            warnings.append("Kontrola příloh našla nekonzistence.")

        codebooks_export = data_management_settings_service.get_last_codebooks_export()
        if codebooks_export and not codebooks_export.manifest.get("verified"):
            warnings.append("Poslední export číselníků nebyl ověřen.")

        codebooks_import = data_management_settings_service.get_last_codebooks_import()
        if self._import_failed(codebooks_import.import_result if codebooks_import else None):
            warnings.append("Poslední import číselníků se nezdařil.")
        elif codebooks_import and codebooks_import.safety_backup_path:
            if not data_management_settings_service.file_exists(
                codebooks_import.safety_backup_path
            ):
                warnings.append("Bezpečnostní záloha před importem číselníků nebyla nalezena.")

        return warnings

    def backup_status_text(self) -> str:
        backup = data_management_settings_service.get_last_backup()
        if backup is None:
            return "nikdy nevytvořena"
        manifest = backup.manifest or {}
        if not manifest.get("verified"):
            return "neověřena"
        if not data_management_settings_service.file_exists(backup.path):
            return "soubor nenalezen"
        if manifest.get("coverage_verdict") == VERDICT_INCOMPLETE:
            return "neúplná"
        if manifest.get("backup_health") == "warning":
            return "vytvořena s upozorněním"
        if self._backup_has_valid_limitations(manifest):
            return "ověřena s omezením"
        return "ověřena"

    def backup_limitation_text(self) -> str | None:
        """Omezení platné zálohy (VALID_WITH_WARNINGS) – nepatří mezi hlavní důvody stavu."""
        backup = data_management_settings_service.get_last_backup()
        if backup is None:
            return None
        manifest = backup.manifest or {}
        if not manifest.get("verified"):
            return None
        if manifest.get("coverage_verdict") == VERDICT_INCOMPLETE:
            return None
        if not self._backup_has_valid_limitations(manifest):
            return None
        stored = str(manifest.get("coverage_limitation") or "").strip()
        if stored:
            return stored
        return SNAPSHOT_SUPPORT_PHOTOS_LIMITATION

    def restore_status_text(self) -> str:
        restore = data_management_settings_service.get_last_restore_result()
        if not restore:
            return "dosud neprovedena"
        integrity = restore.get("integrity_check") or {}
        if integrity.get("verified"):
            return "úspěšná"
        return "neúspěšná"

    def registry_status_text(self) -> str:
        return self._transfer_status_text(
            data_management_settings_service.get_last_registry_export(),
            data_management_settings_service.get_last_registry_import(),
        )

    def codebooks_status_text(self) -> str:
        return self._transfer_status_text(
            data_management_settings_service.get_last_codebooks_export(),
            data_management_settings_service.get_last_codebooks_import(),
        )

    @staticmethod
    def _backup_has_valid_limitations(manifest: dict) -> bool:
        if manifest.get("coverage_verdict") == VERDICT_COMPLETE_WITH_LIMITATIONS:
            return True
        return manifest.get("integrity_status") == INTEGRITY_VALID_WITH_WARNINGS

    @staticmethod
    def _diagnostic_inconsistent(payload: dict | None) -> bool:
        if not payload:
            return False
        if payload.get("is_consistent") is False:
            return True
        issue_count = payload.get("issue_count")
        return isinstance(issue_count, int) and issue_count > 0

    def _missing_registry_preimport_backup_requires_attention(
        self,
        import_record: RegistryImportRecord | None,
    ) -> bool:
        if import_record is None or not import_record.safety_backup_path:
            return False
        if data_management_settings_service.file_exists(import_record.safety_backup_path):
            return False
        if self._preimport_backup_superseded_by_newer_full_backup(import_record):
            return False
        return True

    def _preimport_backup_superseded_by_newer_full_backup(
        self,
        import_record: RegistryImportRecord,
    ) -> bool:
        if not self._import_succeeded(import_record.import_result):
            return False
        if self._diagnostic_inconsistent(
            data_management_settings_service.get_last_diagnostic()
        ):
            return False
        if self._diagnostic_inconsistent(
            data_management_settings_service.get_last_attachment_diagnostic()
        ):
            return False
        backup = self._verified_available_complete_backup()
        if backup is None:
            return False
        backup_at = self._parse_timestamp(backup.created_at)
        import_at = self._parse_timestamp(import_record.created_at)
        if backup_at is None or import_at is None:
            return False
        return backup_at > import_at

    def _verified_available_complete_backup(self) -> BackupRecord | None:
        backup = data_management_settings_service.get_last_backup()
        if backup is None:
            return None
        manifest = backup.manifest or {}
        if not manifest.get("verified"):
            return None
        if manifest.get("coverage_verdict") == VERDICT_INCOMPLETE:
            return None
        if not data_management_settings_service.file_exists(backup.path):
            return None
        return backup

    @classmethod
    def _import_failed(cls, import_result: dict | None) -> bool:
        if not isinstance(import_result, dict) or not import_result:
            return False
        if import_result.get("verified") is False:
            return True
        if import_result.get("success") is False:
            return True
        error_count = import_result.get("error_count")
        if isinstance(error_count, int) and error_count > 0:
            return True
        nested = import_result.get("import_result")
        if isinstance(nested, dict) and nested is not import_result:
            return cls._import_failed(nested)
        return False

    @classmethod
    def _import_succeeded(cls, import_result: dict | None) -> bool:
        if not isinstance(import_result, dict) or not import_result:
            return False
        if cls._import_failed(import_result):
            return False
        if import_result.get("success") is True:
            return True
        if import_result.get("verified") is True:
            return True
        if isinstance(import_result.get("record_counts"), dict):
            return True
        error_count = import_result.get("error_count")
        if isinstance(error_count, int):
            return True
        nested = import_result.get("import_result")
        if isinstance(nested, dict) and nested is not import_result:
            return cls._import_succeeded(nested)
        return False

    @staticmethod
    def _parse_timestamp(value: str) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _transfer_status_text(
        export: RegistryExportRecord | CodebooksExportRecord | None,
        import_record: RegistryImportRecord | CodebooksImportRecord | None,
    ) -> str:
        if export is None and import_record is None:
            return "dosud neprovedena"
        if export is not None and not export.manifest.get("verified"):
            return "poslední export – neověřen"
        if export is not None and not data_management_settings_service.file_exists(
            export.path
        ):
            return "poslední export – soubor nenalezen"
        if DataManagementStatusService._import_failed(
            import_record.import_result if import_record else None
        ):
            return "poslední import – neúspěšný"
        if import_record is not None and import_record.safety_backup_path:
            if not data_management_settings_service.file_exists(
                import_record.safety_backup_path
            ):
                return "poslední import – chybí bezpečnostní záloha"
        return "v pořádku"


data_management_status_service = DataManagementStatusService()
