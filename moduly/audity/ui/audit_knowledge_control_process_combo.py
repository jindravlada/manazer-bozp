from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox

from moduly.audity.constants import KNOWLEDGE_EDITOR_SECTION_CONTROL_PROCESS_EMPTY
from moduly.audity.sluzby.audit_knowledge_editor_service import audit_knowledge_editor_service
from moduly.pravni_pozadavky.constants import legal_requirement_merged_target_label
from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service


def populate_control_process_combo(
    combo: QComboBox,
    selected_id: int | None,
) -> None:
    combo.blockSignals(True)
    try:
        combo.clear()
        combo.addItem(KNOWLEDGE_EDITOR_SECTION_CONTROL_PROCESS_EMPTY)
        combo.setItemData(0, None, Qt.ItemDataRole.UserRole)

        processes = legal_requirement_service.list_active_processes()
        selected_in_list = False
        for process in processes:
            index = combo.count()
            combo.addItem(legal_requirement_merged_target_label(process))
            combo.setItemData(index, process.id, Qt.ItemDataRole.UserRole)
            if selected_id == process.id:
                selected_in_list = True

        if selected_id is not None and not selected_in_list:
            requirement = legal_requirement_service.get_by_id(selected_id)
            if requirement is not None:
                index = combo.count()
                combo.addItem(legal_requirement_merged_target_label(requirement))
                combo.setItemData(index, requirement.id, Qt.ItemDataRole.UserRole)

        target_index = 0
        for index in range(combo.count()):
            if combo.itemData(index, Qt.ItemDataRole.UserRole) == selected_id:
                target_index = index
                break
        combo.setCurrentIndex(target_index)
    finally:
        combo.blockSignals(False)


def selected_control_process_id(combo: QComboBox) -> int | None:
    return audit_knowledge_editor_service.normalize_legal_requirement_id(
        combo.currentData(Qt.ItemDataRole.UserRole),
    )
