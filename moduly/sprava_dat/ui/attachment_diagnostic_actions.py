from datetime import datetime

from core.services.attachment_backup_diagnostic_service import (
    AttachmentBackupDiagnostic,
    attachment_backup_diagnostic_service,
)
from core.widgets.dialog_utils import exec_maximized
from moduly.sprava_dat.ui.attachment_diagnostic_dialog import AttachmentDiagnosticDialog


def persist_attachment_diagnostic_result(diagnostic: AttachmentBackupDiagnostic) -> None:
    from moduly.sprava_dat.sluzby.data_management_settings_service import (
        data_management_settings_service,
    )

    issues = diagnostic.attachment_files_missing + diagnostic.control_result_photos_missing
    summary = (
        "Přílohy a fotografie jsou v pořádku."
        if issues == 0
        else f"Nalezeno {issues} chybějících souborů."
    )
    data_management_settings_service.save_last_attachment_diagnostic(
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "summary": summary,
            "issue_count": issues,
            "is_consistent": issues == 0,
            "diagnostic": diagnostic.to_dict(),
        }
    )


def show_attachment_diagnostic(parent=None) -> AttachmentBackupDiagnostic:
    """Spustí read-only kontrolu příloh, uloží výsledek a zobrazí dialog."""
    diagnostic = attachment_backup_diagnostic_service.diagnose_workspace()
    persist_attachment_diagnostic_result(diagnostic)
    dialog = AttachmentDiagnosticDialog(parent, diagnostic=diagnostic)
    exec_maximized(dialog)
    return diagnostic
