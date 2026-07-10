import importlib
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_VYHLASKA, SECTION_PARAGRAPH, SECTION_SUBSECTION
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.ui.legal_document_valid_text_dialog import (
        LegalDocumentValidTextDialog,
    )
    from moduly.pravni_pozadavky.ui.legal_document_valid_text_tab import LegalDocumentValidTextTab
    from moduly.pravni_pozadavky.ui.legal_document_version_dialog import LegalDocumentVersionDialog
    from moduly.pravni_pozadavky.ui.pravni_predpisy_tab import PravniPredpisyTab


class LegalDocumentValidTextPhase93bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

        self.document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_VYHLASKA,
            title="Vyhláška č. 262/2006 Sb.",
            number="262",
            year=2006,
        )
        self.version = legal_document_version_service.create(
            legal_document_id=self.document.id,
            version_name="Aktuální znění",
        )
        paragraph = legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="12",
            sort_order=1,
        )
        legal_section_service.create(
            legal_document_id=self.document.id,
            legal_document_version_id=self.version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph.id,
            section_number="1",
            text="Bezpečnost práce musí být zajištěna. Bezpečnost je povinností.",
            sort_order=2,
        )

    def _select_document(self, tab: PravniPredpisyTab) -> None:
        tab.refresh()
        for row in range(tab.table.rowCount()):
            item = tab.table.item(row, 0)
            if item is not None and item.text() == str(self.document.id):
                tab.table.selectRow(row)
                break

    def test_valid_text_button_without_selection_shows_warning(self) -> None:
        tab = PravniPredpisyTab()
        tab.refresh()

        with patch.object(QMessageBox, "information") as mock_info:
            tab.open_valid_text()

        mock_info.assert_called_once()
        self.assertIn("Vyberte právní předpis.", mock_info.call_args[0][2])

    def test_valid_text_button_without_current_version_shows_message(self) -> None:
        tab = PravniPredpisyTab()
        self._select_document(tab)

        with patch.object(
            legal_document_version_service,
            "get_current_version",
            return_value=None,
        ):
            with patch.object(QMessageBox, "information") as mock_info:
                tab.open_valid_text()

        mock_info.assert_called_once()
        self.assertIn("nemá dostupné aktuální znění", mock_info.call_args[0][2])

    def test_valid_text_button_opens_reader_dialog_for_current_version(self) -> None:
        tab = PravniPredpisyTab()
        self._select_document(tab)

        with patch(
            "moduly.pravni_pozadavky.ui.pravni_predpisy_tab.LegalDocumentValidTextDialog"
        ) as mock_dialog_cls:
            mock_dialog = mock_dialog_cls.return_value
            with patch(
                "moduly.pravni_pozadavky.ui.pravni_predpisy_tab.exec_maximized",
                return_value=1,
            ) as mock_exec:
                tab.open_valid_text()

        mock_dialog_cls.assert_called_once()
        call_kwargs = mock_dialog_cls.call_args.kwargs
        self.assertEqual(call_kwargs["version_id"], self.version.id)
        self.assertEqual(call_kwargs["document"].id, self.document.id)
        mock_exec.assert_called_once_with(mock_dialog)

    def test_reader_dialog_loads_content_in_worker_thread(self) -> None:
        worker_threads: list[int] = []
        compose_started = threading.Event()
        compose_release = threading.Event()

        original_compose = __import__(
            "moduly.pravni_pozadavky.sluzby.legal_document_valid_text_service",
            fromlist=["legal_document_valid_text_service"],
        ).legal_document_valid_text_service.compose_version

        def slow_compose(version_id: int):
            worker_threads.append(threading.get_ident())
            compose_started.set()
            compose_release.wait(timeout=5)
            return original_compose(version_id)

        with patch(
            "moduly.pravni_pozadavky.ui.legal_document_valid_text_worker.legal_document_valid_text_service.compose_version",
            side_effect=slow_compose,
        ):
            dialog = LegalDocumentValidTextDialog(
                document=self.document,
                version_id=self.version.id,
            )
            self.assertFalse(dialog.valid_text_tab.is_loaded)
            self.assertFalse(dialog.valid_text_tab.search_input.isEnabled())
            self.assertEqual(dialog.status_label.text(), "Načítám platné znění…")

            self.assertTrue(compose_started.wait(timeout=5))
            main_thread = threading.get_ident()
            self.assertNotEqual(worker_threads[0], main_thread)

            compose_release.set()
            deadline = time.time() + 5
            while time.time() < deadline:
                QApplication.processEvents()
                if dialog.valid_text_tab.is_loaded:
                    break
                time.sleep(0.01)

            self.assertTrue(dialog.valid_text_tab.is_loaded)
            self.assertTrue(dialog.valid_text_tab.search_input.isEnabled())
            self.assertIn("§ 12", dialog.valid_text_tab.text_browser.toPlainText())
            dialog.close()
            dialog._runner.wait()

    def test_reader_dialog_stays_responsive_during_loading(self) -> None:
        compose_release = threading.Event()

        original_compose = __import__(
            "moduly.pravni_pozadavky.sluzby.legal_document_valid_text_service",
            fromlist=["legal_document_valid_text_service"],
        ).legal_document_valid_text_service.compose_version

        def slow_compose(version_id: int):
            compose_release.wait(timeout=5)
            return original_compose(version_id)

        with patch(
            "moduly.pravni_pozadavky.ui.legal_document_valid_text_worker.legal_document_valid_text_service.compose_version",
            side_effect=slow_compose,
        ):
            dialog = LegalDocumentValidTextDialog(
                document=self.document,
                version_id=self.version.id,
            )

            processed = 0
            deadline = time.time() + 1
            while time.time() < deadline:
                QApplication.processEvents()
                processed += 1

            self.assertGreater(processed, 0)
            self.assertFalse(dialog.valid_text_tab.is_loaded)
            compose_release.set()

            load_deadline = time.time() + 5
            while time.time() < load_deadline:
                QApplication.processEvents()
                if dialog.valid_text_tab.is_loaded:
                    break

            self.assertTrue(dialog.valid_text_tab.is_loaded)
            dialog.close()
            dialog._runner.wait()

    def test_reader_dialog_search_and_paragraph_jump_after_load(self) -> None:
        dialog = LegalDocumentValidTextDialog(
            document=self.document,
            version_id=self.version.id,
        )
        deadline = time.time() + 5
        while time.time() < deadline:
            QApplication.processEvents()
            if dialog.valid_text_tab.is_loaded:
                break

        self.assertTrue(dialog.valid_text_tab.is_loaded)
        dialog.valid_text_tab.search_input.setText("bezpečnost")
        dialog.valid_text_tab._find_next()
        first_position = dialog.valid_text_tab.text_browser.textCursor().position()
        self.assertGreater(first_position, 0)

        dialog.valid_text_tab.search_input.setText("§ 12")
        dialog.valid_text_tab._find_next()
        self.assertIn("§ 12", dialog.valid_text_tab.text_browser.textCursor().block().text())
        dialog.close()
        dialog._runner.wait()

    def test_reader_dialog_does_not_reload_already_loaded_content(self) -> None:
        dialog = LegalDocumentValidTextDialog(
            document=self.document,
            version_id=self.version.id,
        )
        deadline = time.time() + 5
        while time.time() < deadline:
            QApplication.processEvents()
            if dialog.valid_text_tab.is_loaded:
                break

        with patch(
            "moduly.pravni_pozadavky.ui.legal_document_valid_text_tab.legal_document_valid_text_service.compose_version"
        ) as mock_compose:
            dialog.valid_text_tab.search_input.setText("bezpečnost")
            dialog.valid_text_tab._find_next()

        mock_compose.assert_not_called()
        dialog.close()
        dialog._runner.wait()

    def test_version_dialog_valid_text_tab_still_works(self) -> None:
        dialog = LegalDocumentVersionDialog(version=self.version)
        dialog.valid_text_tab.refresh()

        plain = dialog.valid_text_tab.text_browser.toPlainText()
        self.assertIn("§ 12", plain)
        self.assertIn("Bezpečnost práce musí být zajištěna.", plain)


if __name__ == "__main__":
    unittest.main()
