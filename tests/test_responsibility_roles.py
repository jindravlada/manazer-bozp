import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.nastaveni.sluzby.responsibility_role_service import responsibility_role_service
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service


class ResponsibilityRoleServiceTestCase(unittest.TestCase):
    def test_default_roles_are_seeded(self) -> None:
        roles = responsibility_role_service.get_all(include_inactive=True)
        names = {role.name for role in roles}
        self.assertIn("Vedoucí provozu", names)
        self.assertIn("OZO BOZP", names)
        self.assertIn("Personalista", names)

    def test_create_update_and_deactivate_role(self) -> None:
        role = responsibility_role_service.create_role(
            name="Koordinátor BOZP test",
            description="Koordinuje činnosti BOZP",
        )
        self.assertEqual(role.name, "Koordinátor BOZP test")

        updated = responsibility_role_service.update_role(
            role.id,
            name="Koordinátor BOZP test",
            description="Aktualizovaný popis",
            active=True,
        )
        assert updated is not None
        self.assertEqual(updated.description, "Aktualizovaný popis")

        self.assertTrue(responsibility_role_service.deactivate(role.id))
        active_roles = responsibility_role_service.get_all(include_inactive=False)
        self.assertNotIn(role.id, [item.id for item in active_roles])

        self.assertTrue(responsibility_role_service.activate(role.id))


class LegalRequirementResponsibleRoleTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement

        with get_session() as session:
            session.execute(delete(LegalRequirement))
            session.commit()

        self.role = responsibility_role_service.create_role(
            name="Vedoucí údržby test",
            description="",
        )

    def test_create_requirement_with_person_and_role(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            regulation_name="Údržba zařízení",
            requirement_summary="Provádět údržbu",
            responsible_role_id=self.role.id,
        )

        self.assertEqual(requirement.responsible_role_id, self.role.id)
        self.assertEqual(requirement.responsible_role_name, "Vedoucí údržby test")
        self.assertIsNone(requirement.responsible_person_id)

    def test_update_requirement_can_clear_role(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            regulation_name="Test",
            responsible_role_id=self.role.id,
        )
        updated = legal_requirement_service.update_requirement(
            requirement.id,
            regulation_name="Test",
            responsible_role_id=None,
        )
        assert updated is not None
        self.assertIsNone(updated.responsible_role_id)
        self.assertEqual(updated.responsible_role_name, "")

    def test_invalid_role_raises_error(self) -> None:
        with self.assertRaises(ValueError):
            legal_requirement_service.create_requirement(
                regulation_name="Test",
                responsible_role_id=99999,
            )


class LegalRequirementResponsibleRoleWidgetTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def test_dialog_shows_responsibility_group(self) -> None:
        from PySide6.QtWidgets import QGroupBox

        from moduly.pravni_pozadavky.ui.legal_requirement_dialog import LegalRequirementDialog

        dialog = LegalRequirementDialog()
        groups = [widget.title() for widget in dialog.findChildren(QGroupBox)]
        self.assertIn("Odpovědnost", groups)

    def test_workbench_editor_shows_responsibility_group(self) -> None:
        from PySide6.QtWidgets import QGroupBox

        from moduly.pravni_pozadavky.ui.legal_requirement_workbench_editor import (
            LegalRequirementWorkbenchEditor,
        )

        editor = LegalRequirementWorkbenchEditor()
        groups = [widget.title() for widget in editor.findChildren(QGroupBox)]
        self.assertIn("Odpovědnost", groups)


if __name__ == "__main__":
    unittest.main()
