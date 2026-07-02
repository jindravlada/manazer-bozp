import importlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QDialog

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.audity.constants import (
        AUDIT_PROGRAM_BUTTON_LABEL,
        AUDIT_PROGRAM_MANAGER_BANNER_TITLE,
        AUDIT_PROGRAM_MANAGER_NO_PROGRAM_TEXT,
        AUDIT_PROGRAM_MANAGER_OPEN_BUTTON,
        AUDIT_PROGRAM_STATUS_APPROVED,
        AUDIT_PROGRAM_STATUS_DRAFT,
        AUDIT_PROGRAM_STATUS_RUNNING,
        AUDIT_PROGRAM_WINDOW_TITLE,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
    )
    from moduly.audity.sluzby.audit_program_service import (
        AuditProgramBannerInfo,
        audit_program_service,
    )
    from moduly.audity.ui.audit_program_manager_banner_widget import (
        AuditProgramManagerBannerWidget,
    )
    from moduly.audity.ui.audit_program_manager_dialog import AuditProgramManagerDialog
    from moduly.audity.ui.audity_page import AudityPage


class AuditProgramBannerServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_get_active_program_prefers_running_over_approved(self) -> None:
        audit_program_service.create_program(
            name="Schválený program",
            date_from=date(2028, 1, 1),
            date_to=date(2031, 12, 31),
            status=AUDIT_PROGRAM_STATUS_APPROVED,
        )
        running = audit_program_service.create_program(
            name="Běžící program",
            date_from=date(2026, 1, 1),
            date_to=date(2029, 12, 31),
            status=AUDIT_PROGRAM_STATUS_RUNNING,
        )

        active = audit_program_service.get_active_program()
        assert active is not None
        self.assertEqual(active.id, running.id)

    def test_get_banner_info_without_program(self) -> None:
        with patch.object(
            audit_program_service,
            "list_programs",
            return_value=[],
        ):
            info = audit_program_service.get_banner_info()
        self.assertFalse(info.has_program)

    def test_get_banner_info_shows_nearest_visit(self) -> None:
        program = audit_program_service.create_program(
            name="ZX-ZF 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
            status=AUDIT_PROGRAM_STATUS_RUNNING,
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=10,
            workplace_name="Provoz A",
            audit_interval_months=6,
        )
        audit_program_service.add_visit(
            program.id,
            workplace_id=10,
            planned_year=2026,
            planned_month=10,
        )
        audit_program_service.add_visit(
            program.id,
            workplace_id=10,
            planned_year=2026,
            planned_month=7,
            planned_date=date(2026, 7, 15),
        )

        info = audit_program_service.get_banner_info()

        self.assertTrue(info.has_program)
        self.assertEqual(info.program_name, "ZX-ZF 2026–2029")
        self.assertIn("2026", info.period_label)
        self.assertEqual(info.nearest_visit_term, "15. 7. 2026")
        self.assertEqual(info.nearest_visit_workplace, "Provoz A")


class AudityPageManagerBannerTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _create_page(self) -> AudityPage:
        return AudityPage()

    def test_toolbar_button_is_renamed(self) -> None:
        page = self._create_page()
        self.assertEqual(page.program_btn.text(), AUDIT_PROGRAM_BUTTON_LABEL)
        self.assertEqual(AUDIT_PROGRAM_BUTTON_LABEL, "Manažer auditů")

    @patch("moduly.audity.ui.audity_page.exec_maximized")
    def test_toolbar_button_opens_manager(self, mock_exec) -> None:
        page = self._create_page()
        page.open_program_manager()

        mock_exec.assert_called_once()
        self.assertIsInstance(mock_exec.call_args.args[0], AuditProgramManagerDialog)

    def test_banner_is_visible_on_page(self) -> None:
        page = self._create_page()
        self.assertTrue(hasattr(page, "_program_manager_banner"))
        self.assertIsInstance(page._program_manager_banner, AuditProgramManagerBannerWidget)
        self.assertEqual(
            page._program_manager_banner._title_label.text(),
            AUDIT_PROGRAM_MANAGER_BANNER_TITLE,
        )

    def test_banner_shows_no_program_state(self) -> None:
        widget = AuditProgramManagerBannerWidget()
        empty_info = AuditProgramBannerInfo(
            has_program=False,
            program_id=None,
            program_name="",
            period_label="",
            completion_percent=None,
            nearest_visit_term=None,
            nearest_visit_workplace=None,
        )
        with patch.object(
            audit_program_service,
            "get_banner_info",
            return_value=empty_info,
        ):
            widget.refresh()
        self.assertIn(
            AUDIT_PROGRAM_MANAGER_NO_PROGRAM_TEXT,
            widget._detail_label.text(),
        )
        self.assertEqual(
            widget._open_btn.text(),
            AUDIT_PROGRAM_MANAGER_OPEN_BUTTON,
        )

    def test_banner_shows_active_program(self) -> None:
        program = audit_program_service.create_program(
            name="Program auditů 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            status=AUDIT_PROGRAM_STATUS_RUNNING,
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=20,
            workplace_name="Provoz Gamma",
            audit_interval_months=6,
        )
        audit_program_service.add_visit(
            program.id,
            workplace_id=20,
            planned_year=2026,
            planned_month=8,
            planned_date=date(2026, 8, 12),
        )

        widget = AuditProgramManagerBannerWidget()
        widget.refresh()

        text = widget._detail_label.text()
        self.assertIn("Program auditů 2026–2029", text)
        self.assertIn("Období:", text)
        self.assertIn("Plnění:", text)
        self.assertIn("Nejbližší návštěva:", text)
        self.assertIn("12. 8. 2026", text)
        self.assertIn("Provoz Gamma", text)

    @patch("moduly.audity.ui.audity_page.exec_maximized")
    def test_banner_button_opens_manager(self, mock_exec) -> None:
        page = self._create_page()
        page._program_manager_banner._open_btn.click()

        mock_exec.assert_called_once()
        dialog = mock_exec.call_args.args[0]
        self.assertIsInstance(dialog, AuditProgramManagerDialog)
        self.assertEqual(dialog.windowTitle(), AUDIT_PROGRAM_WINDOW_TITLE)


if __name__ == "__main__":
    unittest.main()
