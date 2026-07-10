from datetime import datetime

from core.widgets.dialog_utils import exec_maximized
from moduly.pravni_pozadavky.sluzby.legal_registry_diagnostic_service import (
    LegalRegistryDiagnosticResult,
    legal_registry_diagnostic_service,
)
from moduly.pravni_pozadavky.ui.legal_registry_diagnostic_dialog import (
    LegalRegistryDiagnosticDialog,
)


def persist_diagnostic_result(result: LegalRegistryDiagnosticResult) -> None:
    from moduly.sprava_dat.sluzby.data_management_settings_service import (
        data_management_settings_service,
    )

    summary = (
        "Registr je konzistentní."
        if result.is_consistent
        else f"Nalezeno {result.issue_count} problémů."
    )
    data_management_settings_service.save_last_diagnostic(
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "summary": summary,
            "issue_count": result.issue_count,
            "is_consistent": result.is_consistent,
        }
    )


def show_legal_registry_diagnostic(parent=None) -> LegalRegistryDiagnosticResult:
    """Spustí diagnostiku registru, uloží výsledek a zobrazí dialog."""
    result = legal_registry_diagnostic_service.run()
    persist_diagnostic_result(result)
    dialog = LegalRegistryDiagnosticDialog(parent, result=result)
    exec_maximized(dialog)
    return result
