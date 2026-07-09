import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.audity.ui.audit_knowledge_control_process_combo import (
        populate_control_process_combo,
        selected_control_process_id,
    )
    from moduly.pravni_pozadavky.constants import legal_requirement_merged_target_label
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service


class AuditKnowledgeControlProcessComboTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication, QComboBox

        cls._app = QApplication.instance() or QApplication([])
        cls._ComboBox = QComboBox

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource

        with get_session() as session:
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.commit()

    def test_populate_lists_all_active_control_processes_sorted_by_code(self) -> None:
        process_one = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-005",
        )
        process_two = legal_requirement_service.create_requirement(
            title="Řízení kompetencí",
            process_code="P-003",
        )
        legal_requirement_service.create_requirement(
            title="Podřízený požadavek",
            process_code="P-003.1",
            parent_requirement_id=process_two.id,
        )

        combo = self._ComboBox()
        populate_control_process_combo(combo, None)

        labels = [combo.itemText(index) for index in range(combo.count())]
        self.assertEqual(labels[0], "—")
        self.assertEqual(
            labels[1:],
            [
                legal_requirement_merged_target_label(process_two),
                "P-003.1 – Podřízený požadavek",
                legal_requirement_merged_target_label(process_one),
            ],
        )

    def test_populate_preselects_saved_requirement_id(self) -> None:
        process = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-005",
        )
        legal_requirement_service.create_requirement(
            title="Řízení kompetencí",
            process_code="P-003",
        )

        combo = self._ComboBox()
        populate_control_process_combo(combo, process.id)

        self.assertEqual(selected_control_process_id(combo), process.id)
        self.assertEqual(
            combo.currentText(),
            legal_requirement_merged_target_label(process),
        )

    def test_populate_keeps_inactive_saved_process_in_list(self) -> None:
        process = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-005",
        )
        legal_requirement_service.archive_requirement(process.id)

        combo = self._ComboBox()
        populate_control_process_combo(combo, process.id)

        self.assertEqual(combo.count(), 2)
        self.assertEqual(selected_control_process_id(combo), process.id)
        self.assertEqual(
            combo.itemData(1, Qt.ItemDataRole.UserRole),
            process.id,
        )


if __name__ == "__main__":
    unittest.main()
