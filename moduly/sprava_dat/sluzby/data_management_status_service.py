from moduly.sprava_dat.sluzby.data_management_settings_service import data_management_settings_service
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
            if not backup.manifest.get("verified"):
                warnings.append("Poslední kompletní záloha nebyla ověřena.")
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
        if export and not data_management_settings_service.file_exists(export.path):
            warnings.append("Soubor posledního exportu registru nebyl nalezen.")

        import_record = data_management_settings_service.get_last_registry_import()
        if import_record and import_record.safety_backup_path:
            if not data_management_settings_service.file_exists(import_record.safety_backup_path):
                warnings.append("Bezpečnostní záloha před importem registru nebyla nalezena.")

        diagnostic = data_management_settings_service.get_last_diagnostic()
        if diagnostic is None:
            warnings.append("Diagnostika registru zatím nebyla spuštěna.")

        return warnings

    def backup_status_text(self) -> str:
        backup = data_management_settings_service.get_last_backup()
        if backup is None:
            return "nikdy nevytvořena"
        if not backup.manifest.get("verified"):
            return "neověřena"
        if not data_management_settings_service.file_exists(backup.path):
            return "soubor nenalezen"
        return "ověřena"

    def restore_status_text(self) -> str:
        restore = data_management_settings_service.get_last_restore_result()
        if not restore:
            return "dosud neprovedena"
        integrity = restore.get("integrity_check") or {}
        if integrity.get("verified"):
            return "úspěšná"
        return "neúspěšná"

    def registry_status_text(self) -> str:
        export = data_management_settings_service.get_last_registry_export()
        import_record = data_management_settings_service.get_last_registry_import()
        if export is None and import_record is None:
            return "dosud neprovedena"
        if export and not data_management_settings_service.file_exists(export.path):
            return "poslední export – soubor nenalezen"
        if import_record and import_record.safety_backup_path:
            if not data_management_settings_service.file_exists(import_record.safety_backup_path):
                return "poslední import – chybí bezpečnostní záloha"
        return "v pořádku"


data_management_status_service = DataManagementStatusService()
