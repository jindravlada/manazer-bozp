from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget

from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service


def confirm_and_delete_all_process_requirements(parent: QWidget | None = None) -> bool:
    """Vývojářská operace: nevratně smaže všechny řídicí procesy."""
    first_answer = QMessageBox.warning(
        parent,
        "POZOR!",
        "Operace nevratně odstraní všechny řídicí procesy.\n\n"
        "Tuto operaci používejte pouze při vývoji.",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if first_answer != QMessageBox.Yes:
        return False

    second_answer = QMessageBox.critical(
        parent,
        "Potvrzení vymazání",
        "Opravdu vymazat všechny řídicí procesy?\n\n"
        "Smažou se požadavky, právní podklady, ověření plnění a sankce.\n"
        "Právní předpisy a jejich struktura zůstanou zachovány.\n\n"
        "Tuto akci nelze vrátit.",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )
    if second_answer != QMessageBox.Yes:
        return False

    counts = legal_requirement_service.delete_all_process_requirements()
    QMessageBox.information(
        parent,
        "Řídicí procesy",
        "Řídicí procesy byly vymazány.\n\n"
        f"Požadavky: {counts['requirements']}\n"
        f"Právní podklady: {counts['sources']}\n"
        f"Ověření plnění: {counts['checks']}\n"
        f"Sankce: {counts['sanctions']}",
    )
    return True
