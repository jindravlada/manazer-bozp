"""Úkol nesmí blokovat okno zdrojového záznamu (TASK-SOURCE-WINDOW-1)."""

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.navigation.source_navigator import source_navigator
    from core.shared.constants import (
        ENTITY_ACCIDENT,
        ENTITY_AUDITY,
        ENTITY_MU_INVESTIGATION,
        ENTITY_STATE_SUPERVISION,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_NESHODA,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.constants import FINDING_SOURCE_LABEL
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.kniha_urazu.sluzby.accident_reporting_task_service import (
        ohlaseni_task_title,
    )
    from moduly.ukoly.sluzby.task_service import task_service


def _run_with_source_probe(task_dialog, bucket: dict, action) -> None:
    """Spustí akci a uvnitř skutečného exec_maximized změří modální zásobník."""
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication, QDialog

    import core.widgets.dialog_utils as dialog_utils

    real_exec_maximized = dialog_utils.exec_maximized
    real_exec = QDialog.exec

    def marking(dialog) -> int:
        dialog.setProperty("probe_source", True)
        return real_exec_maximized(dialog)

    def probe_exec(self) -> int:
        if not self.property("probe_source"):
            return real_exec(self)

        def capture() -> None:
            active = QApplication.activeModalWidget()
            bucket["window_title"] = self.windowTitle()
            bucket["source_visible"] = self.isVisible()
            bucket["source_maximized"] = bool(self.windowState() & Qt.WindowState.WindowMaximized)
            bucket["source_is_active_modal"] = active is self
            bucket["task_is_active_modal"] = active is task_dialog
            bucket["task_visible"] = task_dialog.isVisible()
            bucket["task_title"] = task_dialog.title_edit.toPlainText()
            QDialog.reject(self)

        QTimer.singleShot(0, capture)
        return real_exec(self)

    with (
        patch("moduly.audity.ui.audity_page.exec_maximized", marking),
        patch("core.widgets.dialog_utils.exec_maximized", marking),
        patch.object(QDialog, "exec", probe_exec),
    ):
        action()


class TaskSourceWindow1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        source_navigator.configure(None)

    def test_audit_opened_from_task_is_not_blocked_and_draft_survives(self) -> None:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtWidgets import QDialog, QStackedWidget, QWidget

        from moduly.audity.ui.audity_page import AudityPage
        from moduly.ukoly.ui.task_dialog import TaskDialog

        audit = audit_service.create_audit(title="Zdrojový audit")
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Chybí postup",
            status=FINDING_STATUS_OTEVRENE,
        )
        task = finding_task_service.create_task_from_finding(finding.id)
        stored_title = task.title

        stack = QStackedWidget()
        task_page = QWidget()
        audit_page = AudityPage()
        stack.addWidget(task_page)
        stack.addWidget(audit_page)
        stack.resize(960, 720)
        stack.show()

        host = MagicMock()
        host._page_widgets = {"audity": audit_page}

        def _show(key: str) -> None:
            self.assertEqual(key, "audity")
            stack.setCurrentWidget(audit_page)

        host._show.side_effect = _show
        source_navigator.configure(host)

        dialog = TaskDialog(task_page, task=task)
        self.assertFalse(dialog.source_panel.open_button.isHidden())
        dialog.title_edit.setPlainText("Rozpracované opatření")
        self.assertTrue(dialog._is_dirty())
        bucket: dict = {}
        error: list[BaseException] = []

        def click() -> None:
            try:
                _run_with_source_probe(
                    dialog,
                    bucket,
                    dialog.source_panel.open_button.click,
                )
                bucket["after_title"] = dialog.title_edit.toPlainText()
                bucket["after_dirty"] = dialog._is_dirty()
                bucket["after_visible"] = dialog.isVisible()
                bucket["after_modality"] = dialog.windowModality()
                bucket["after_closing"] = dialog._closing
                bucket["parent_page_visible"] = task_page.isVisible()
                self.assertEqual(task_service.get_task_by_id(task.id).title, stored_title)
                with patch("moduly.ukoly.ui.task_dialog._exec_message_box", return_value=0):
                    dialog._save_keep_open()
                bucket["saved_title"] = task_service.get_task_by_id(task.id).title
                bucket["still_open"] = dialog.isVisible() and not dialog._closing
            except BaseException as exc:
                error.append(exc)
            finally:
                QTimer.singleShot(0, lambda: QDialog.reject(dialog))

        QTimer.singleShot(0, click)
        dialog.exec()
        stack.close()

        if error:
            raise error[0]

        self.assertEqual(bucket["window_title"], FINDING_SOURCE_LABEL)
        self.assertTrue(bucket["source_visible"])
        self.assertTrue(bucket["source_maximized"])
        self.assertTrue(bucket["source_is_active_modal"])
        self.assertFalse(bucket["task_is_active_modal"])
        self.assertTrue(bucket["task_visible"])
        self.assertEqual(bucket["task_title"], "Rozpracované opatření")
        self.assertEqual(bucket["after_title"], "Rozpracované opatření")
        self.assertTrue(bucket["after_dirty"])
        self.assertTrue(bucket["after_visible"])
        self.assertEqual(bucket["after_modality"], Qt.WindowModality.ApplicationModal)
        self.assertFalse(bucket["after_closing"])
        self.assertFalse(bucket["parent_page_visible"])
        self.assertEqual(bucket["saved_title"], "Rozpracované opatření")
        self.assertTrue(bucket["still_open"])

    def test_other_task_sources_are_not_blocked_by_task_dialog(self) -> None:
        cases = (
            ("supervision", self._supervision_task(), "agenda"),
            ("accident", self._accident_task(), "kniha_urazu"),
            ("reporting", self._reporting_task(), "kniha_urazu"),
            ("mu", self._mu_task(), "vysetrovani_mu"),
        )
        for name, task, module_key in cases:
            with self.subTest(name=name):
                self._assert_source_not_blocked(task, module_key)

    def test_failed_open_restores_visible_task_dialog(self) -> None:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

        from moduly.ukoly.ui.task_dialog import TaskDialog

        audit = audit_service.create_audit(title="Bez stránky")
        finding = finding_service.create(
            ENTITY_AUDITY,
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Bez modulu",
            status=FINDING_STATUS_OTEVRENE,
        )
        task = finding_task_service.create_task_from_finding(finding.id)
        page = QWidget()
        host = MagicMock()
        host._page_widgets = {"audity": page}
        host._show = MagicMock()
        source_navigator.configure(host)

        dialog = TaskDialog(page, task=task)
        dialog.title_edit.setPlainText("Zůstane v editoru")
        warnings: list[tuple] = []
        error: list[BaseException] = []

        def click() -> None:
            try:
                source_navigator.configure(None)
                with patch.object(
                    QMessageBox,
                    "warning",
                    side_effect=lambda *args: warnings.append(args) or 0,
                ):
                    dialog.source_panel.open_button.click()
                self.assertEqual(dialog.title_edit.toPlainText(), "Zůstane v editoru")
                self.assertTrue(dialog.isVisible())
                self.assertTrue(dialog._is_dirty())
                self.assertFalse(dialog._closing)
            except BaseException as exc:
                error.append(exc)
            finally:
                QTimer.singleShot(0, lambda: QDialog.reject(dialog))

        QTimer.singleShot(0, click)
        dialog.exec()

        if error:
            raise error[0]
        self.assertEqual(len(warnings), 1)
        self.assertIs(warnings[0][0], dialog)
        page.close()

    def _assert_source_not_blocked(self, task, module_key: str) -> None:
        from PySide6.QtCore import Qt, QTimer
        from PySide6.QtWidgets import QDialog, QStackedWidget, QWidget

        from moduly.ukoly.ui.task_dialog import TaskDialog

        holder: dict = {"dialog": None, "bucket": {}, "module": None}
        stack = QStackedWidget()
        task_page = QWidget()
        source_page = QWidget()
        stack.addWidget(task_page)
        stack.addWidget(source_page)
        stack.resize(800, 600)
        stack.show()

        def opener(_entity_id, **_kwargs) -> None:
            import core.widgets.dialog_utils as dialog_utils

            source = QDialog(source_page)
            source.setWindowTitle("Zdrojový záznam")
            dialog_utils.exec_maximized(source)

        source_page.open_supervision = opener
        source_page.open_accident = opener
        source_page.open_investigation = opener
        source_page.open_mu_investigation = opener

        host = MagicMock()
        host._page_widgets = {
            "audity": source_page,
            "agenda": source_page,
            "kniha_urazu": source_page,
            "vysetrovani_mu": source_page,
        }

        def _show(key: str) -> None:
            holder["module"] = key
            stack.setCurrentWidget(source_page)

        host._show.side_effect = _show
        source_navigator.configure(host)

        dialog = TaskDialog(task_page, task=task)
        holder["dialog"] = dialog
        self.assertFalse(dialog.source_panel.open_button.isHidden())
        dialog.title_edit.setPlainText("Rozpracováno")
        error: list[BaseException] = []

        def click() -> None:
            try:
                _run_with_source_probe(
                    dialog,
                    holder["bucket"],
                    dialog.source_panel.open_button.click,
                )
                holder["after_visible"] = dialog.isVisible()
                holder["after_modality"] = dialog.windowModality()
                holder["after_title"] = dialog.title_edit.toPlainText()
                holder["after_dirty"] = dialog._is_dirty()
                holder["after_closing"] = dialog._closing
            except BaseException as exc:
                error.append(exc)
            finally:
                QTimer.singleShot(0, lambda: QDialog.reject(dialog))

        QTimer.singleShot(0, click)
        dialog.exec()
        stack.close()

        if error:
            raise error[0]
        bucket = holder["bucket"]
        self.assertEqual(holder["module"], module_key)
        self.assertEqual(bucket["window_title"], "Zdrojový záznam")
        self.assertTrue(bucket["source_visible"])
        self.assertTrue(bucket["source_maximized"])
        self.assertTrue(bucket["source_is_active_modal"])
        self.assertFalse(bucket["task_is_active_modal"])
        self.assertTrue(bucket["task_visible"])
        self.assertEqual(bucket["task_title"], "Rozpracováno")
        self.assertTrue(holder["after_visible"])
        self.assertEqual(holder["after_modality"], Qt.WindowModality.ApplicationModal)
        self.assertEqual(holder["after_title"], "Rozpracováno")
        self.assertTrue(holder["after_dirty"])
        self.assertFalse(holder["after_closing"])

    def _supervision_task(self):
        finding = finding_service.create(
            ENTITY_STATE_SUPERVISION,
            1,
            finding_type=FINDING_TYPE_NESHODA,
            description="Kontrola orgánu",
            status=FINDING_STATUS_OTEVRENE,
        )
        return finding_task_service.create_task_from_finding(finding.id)

    def _accident_task(self):
        return task_service.create_task(
            title="Opatření po úrazu",
            source_module=ENTITY_ACCIDENT,
            source_record_id=1,
        )

    def _reporting_task(self):
        return task_service.create_task(
            title=ohlaseni_task_title("12"),
            source_module=ENTITY_ACCIDENT,
            source_record_id=1,
        )

    def _mu_task(self):
        return task_service.create_task(
            title="Vyšetřovací úkon",
            source_module=ENTITY_MU_INVESTIGATION,
            source_record_id=1,
        )


if __name__ == "__main__":
    unittest.main()
