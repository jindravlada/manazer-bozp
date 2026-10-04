"""LEGAL-CHANGE-CRASH-2: vlákno Kontroly změn, GUI callbacky a traceback."""

from __future__ import annotations

import importlib
import os
import tempfile
import threading
import time
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

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

    from core.services.app_runtime_service import mark_application_started

    mark_application_started()

    from PySide6.QtCore import QEventLoop, QtMsgType, QThread, QTimer, qInstallMessageHandler
    from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

    from core.services.application_log import application_log_path
    from moduly.pravni_pozadavky.constants import (
        CHECK_RUN_CANCELLED,
        CHECK_RUN_COMPLETED,
        CHECK_RUN_ERROR,
        DOCUMENT_TYPE_ZAKON,
        SECTION_LETTER,
        SECTION_PARAGRAPH,
        SECTION_SUBSECTION,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_client import (
        legal_document_esbirka_opendata_client,
    )
    from moduly.pravni_pozadavky.import_export.legal_document_esbirka_opendata_tree import (
        legal_document_esbirka_opendata_tree_builder,
    )
    from moduly.pravni_pozadavky.sluzby.legal_check_novelization_service import (
        legal_check_novelization_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_check_run_service import legal_check_run_service
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_document_version_service import (
        legal_document_version_service,
    )
    from moduly.pravni_pozadavky.sluzby.legal_section_service import legal_section_service
    from moduly.pravni_pozadavky.ui.legal_check_progress_dialog import LegalCheckProgressDialog
    from moduly.pravni_pozadavky.ui.legal_check_run_worker import (
        active_legal_check_runner_count,
    )
    from tests.legal_opendata_check_fakes import (
        fake_in_force_tree,
        parsed_sections_from_version,
        patch_no_future_wordings,
    )

import shiboken6

_QT_MESSAGES: list[str] = []
_PREVIOUS_QT_HANDLER = None


def _qt_message_handler(mode, _context, message) -> None:
    if mode in (
        QtMsgType.QtWarningMsg,
        QtMsgType.QtCriticalMsg,
        QtMsgType.QtFatalMsg,
    ):
        _QT_MESSAGES.append(str(message))


def _app() -> QApplication:
    application = QApplication.instance()
    if application is None:
        application = QApplication([])
    return application


class _SignalLog:
    def __init__(self, signal) -> None:
        self.items: list[tuple] = []
        signal.connect(self._on)
        self._signal = signal

    def _on(self, *args) -> None:
        self.items.append(args)

    @property
    def count(self) -> int:
        return len(self.items)

    def wait(self, timeout_ms: int = 8000) -> None:
        if self.items:
            return
        loop = QEventLoop()

        def _quit(*_args) -> None:
            loop.quit()

        self._signal.connect(_quit)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(timeout_ms)
        loop.exec()
        self._signal.disconnect(_quit)
        timer.stop()
        if not self.items:
            raise AssertionError("Očekávaný signál nedorazil.")


def _wait_until(predicate, timeout_ms: int = 3000) -> None:
    if predicate():
        return
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(10)

    def _tick() -> None:
        if predicate():
            loop.quit()

    timer.timeout.connect(_tick)
    QTimer.singleShot(timeout_ms, loop.quit)
    timer.start()
    loop.exec()
    timer.stop()
    if not predicate():
        raise AssertionError("Podmínka nenastala včas.")


class _ProbeDialog(LegalCheckProgressDialog):
    def __init__(self, *args, **kwargs) -> None:
        self.callback_threads: list[QThread] = []
        self.worker_alive_at_outcome = None
        self.deletion_scheduled_at_outcome = None
        super().__init__(*args, **kwargs)

    def _remember(self) -> None:
        self.callback_threads.append(QThread.currentThread())
        worker = self._runner.worker
        self.worker_alive_at_outcome = worker is not None and shiboken6.isValid(worker)
        self.deletion_scheduled_at_outcome = self._runner.deletion_scheduled

    def _update_status(self, message: str) -> None:
        self.callback_threads.append(QThread.currentThread())
        super()._update_status(message)

    def _update_progress(self, current: int, total: int, label: str) -> None:
        self.callback_threads.append(QThread.currentThread())
        super()._update_progress(current, total, label)

    def _on_finished(self, result) -> None:
        self._remember()
        super()._on_finished(result)

    def _on_failed(self, message: str) -> None:
        self._remember()
        super()._on_failed(message)

    def _on_cancelled(self) -> None:
        self._remember()
        super()._on_cancelled()


class LegalCheckThreadCrash2TestCase(unittest.TestCase):
    remote_eli = "eli/cz/sb/2021/390/2021-10-11"

    @classmethod
    def setUpClass(cls) -> None:
        global _PREVIOUS_QT_HANDLER
        _PREVIOUS_QT_HANDLER = qInstallMessageHandler(_qt_message_handler)
        cls.app = _app()

    @classmethod
    def tearDownClass(cls) -> None:
        qInstallMessageHandler(_PREVIOUS_QT_HANDLER)

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_change import LegalChange
        from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
        from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalChangeSection))
            session.execute(delete(LegalChange))
            session.execute(delete(LegalCheckRun))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()

        self._qt_mark = len(_QT_MESSAGES)
        self.release = threading.Event()
        self.worker_threads: list[QThread] = []
        no_futures = patch_no_future_wordings()
        no_futures.start()
        self.addCleanup(no_futures.stop)
        self.dialog: _ProbeDialog | None = None

    def tearDown(self) -> None:
        self.release.set()
        application = QApplication.instance()
        if application is not None:
            for _ in range(30):
                application.processEvents()
        fresh = _QT_MESSAGES[self._qt_mark :]
        if fresh:
            self.fail("Qt varování během testu:\n" + "\n".join(fresh))

    def _create_document(self):
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákon č. 390/2021 Sb.",
            number="390/2021 Sb.",
            year=2021,
            short_title="zákon 390/2021",
        )
        version = legal_document_version_service.create(
            legal_document_id=document.id,
            version_name="Aktuální znění",
        )
        paragraph = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_PARAGRAPH,
            paragraph="1",
            title="§ 1",
            text="Působnost",
            sort_order=1,
        )
        subsection = legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_SUBSECTION,
            parent_section_id=paragraph.id,
            section_number="1",
            text="Tento zákon upravuje kontrolu.",
            sort_order=2,
        )
        legal_section_service.create(
            legal_document_id=document.id,
            legal_document_version_id=version.id,
            section_type=SECTION_LETTER,
            parent_section_id=subsection.id,
            item_letter="a",
            text="rozsah povinností",
            sort_order=3,
        )
        sections = legal_section_service.list_by_version(version.id)
        self.assertGreaterEqual(len(sections), 3)
        return document, version

    def _fetch_tree(self, version_id: int, *, block: bool = False):
        def _fetch(**_kwargs):
            self.worker_threads.append(QThread.currentThread())
            if block:
                if not self.release.wait(timeout=8):
                    raise TimeoutError("Zdroj nebyl v testu uvolněn.")
            version = legal_document_version_service.get_current_version(
                legal_document_version_service.get_by_id(version_id).legal_document_id
            )
            current_id = version.id if version is not None else version_id
            return fake_in_force_tree(
                self.remote_eli,
                parsed_sections_from_version(current_id),
                effective_from=date(2021, 10, 11),
            )

        return patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            side_effect=_fetch,
        )

    def _open_dialog(self) -> _ProbeDialog:
        dialog = _ProbeDialog(
            period_from=date(2024, 1, 1),
            period_to=date(2024, 1, 31),
        )
        self.dialog = dialog
        return dialog

    def _finish_cleanup(self, dialog: _ProbeDialog, thread: QThread, worker) -> None:
        cleanup = _SignalLog(dialog._runner.cleanup_finished)
        cleanup.wait()
        self.assertEqual(cleanup.count, 1)
        self.assertFalse(dialog._runner.is_thread_running())
        self.assertEqual(active_legal_check_runner_count(), 0)
        self.assertFalse(shiboken6.isValid(worker))
        self.assertTrue(shiboken6.isValid(thread))
        self.assertFalse(thread.isRunning())
        _wait_until(lambda: not shiboken6.isValid(thread))
        self.assertFalse(shiboken6.isValid(thread))

    def test_a_first_check_completes_on_gui_thread(self) -> None:
        _document, version = self._create_document()
        gui_thread = QThread.currentThread()

        with self._fetch_tree(version.id):
            dialog = self._open_dialog()
            thread = dialog._runner._thread
            worker = dialog._runner.worker
            self.assertIsNotNone(thread)
            self.assertIsNotNone(worker)
            code = dialog.exec()
            self._finish_cleanup(dialog, thread, worker)

        self.assertEqual(code, QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.status_label.text(), "Kontrola dokončena.")
        result = dialog.result_data()
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.is_first_check)
        self.assertEqual(result.changes_count, 0)
        self.assertEqual(result.run.status, CHECK_RUN_COMPLETED)
        self.assertTrue(dialog.callback_threads)
        self.assertTrue(all(item is gui_thread for item in dialog.callback_threads))
        self.assertTrue(self.worker_threads)
        self.assertTrue(all(item is not gui_thread for item in self.worker_threads))
        self.assertTrue(dialog.worker_alive_at_outcome)
        self.assertFalse(dialog.deletion_scheduled_at_outcome)

        stored = legal_document_version_service.get_by_id(version.id)
        assert stored is not None
        self.assertEqual(stored.source_eli, self.remote_eli)
        self.assertEqual(
            stored.checksum,
            legal_document_esbirka_opendata_client.build_version_checksum(self.remote_eli),
        )
        self.assertEqual(stored.effective_from, date(2021, 10, 11))
        runs = legal_check_run_service.list_all()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].status, CHECK_RUN_COMPLETED)

    def test_b_worker_exception_is_logged_without_dialog_traceback(self) -> None:
        _document, version = self._create_document()
        marker = "LEGAL-CHANGE-CRASH-2-kontrolni-vyjimka"
        warnings: list[str] = []

        def _warning(*args, **_kwargs):
            warnings.append(str(args[2]) if len(args) > 2 else "")
            return QMessageBox.StandardButton.Ok

        with self._fetch_tree(version.id):
            with patch.object(
                legal_check_novelization_service,
                "initialize_reference_state",
                side_effect=RuntimeError(marker),
            ):
                with patch(
                    "moduly.pravni_pozadavky.ui.legal_check_progress_dialog.QMessageBox.warning",
                    side_effect=_warning,
                ):
                    dialog = self._open_dialog()
                    thread = dialog._runner._thread
                    worker = dialog._runner.worker
                    failed = _SignalLog(dialog._runner.failed)
                    finished = _SignalLog(dialog._runner.finished)
                    cancelled = _SignalLog(dialog._runner.cancelled)
                    code = dialog.exec()
                    self._finish_cleanup(dialog, thread, worker)

        self.assertEqual(code, QDialog.DialogCode.Rejected)
        self.assertEqual(dialog.status_label.text(), "Kontrola se nezdařila.")
        self.assertIsNone(dialog.result_data())
        self.assertEqual(failed.count, 1)
        self.assertEqual(finished.count, 0)
        self.assertEqual(cancelled.count, 0)
        self.assertEqual(warnings, [marker])
        self.assertNotIn("Traceback", warnings[0])
        self.assertTrue(dialog.worker_alive_at_outcome)
        self.assertFalse(dialog.deletion_scheduled_at_outcome)
        gui_thread = QThread.currentThread()
        self.assertTrue(dialog.callback_threads)
        self.assertTrue(all(item is gui_thread for item in dialog.callback_threads))

        runs = legal_check_run_service.list_all()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].status, CHECK_RUN_ERROR)
        self.assertEqual(runs[0].error_message, marker)
        self.assertNotIn("Traceback", runs[0].error_message or "")

        log_text = application_log_path().read_text(encoding="utf-8")
        self.assertIn("Traceback (most recent call last):", log_text)
        self.assertIn(marker, log_text)
        self.assertIn("RuntimeError", log_text)
        self.assertIn("Kontrola změn právních předpisů selhala.", log_text)

    def test_c_cancel_and_close_finish_the_thread(self) -> None:
        self._assert_stopped_by(lambda dialog: dialog.cancel_btn.click(), cancelled_in_ui=True)
        self._reset_tables()
        self.worker_threads.clear()
        self.release.clear()
        self._assert_stopped_by(lambda dialog: dialog.close(), cancelled_in_ui=False)

    def _assert_stopped_by(self, action, *, cancelled_in_ui: bool) -> None:
        _document, version = self._create_document()
        entered = threading.Event()

        def _fetch(**_kwargs):
            self.worker_threads.append(QThread.currentThread())
            entered.set()
            if not self.release.wait(timeout=8):
                raise TimeoutError("Zdroj nebyl v testu uvolněn.")
            current = legal_document_version_service.get_by_id(version.id)
            current_id = current.id if current is not None else version.id
            return fake_in_force_tree(
                self.remote_eli,
                parsed_sections_from_version(current_id),
                effective_from=date(2021, 10, 11),
            )

        started = time.monotonic()

        def _poke(dialog: _ProbeDialog) -> None:
            if entered.is_set():
                action(dialog)
                self.release.set()
                return
            if time.monotonic() - started > 5:
                self.release.set()
                return
            QTimer.singleShot(20, lambda: _poke(dialog))

        with patch.object(
            legal_document_esbirka_opendata_tree_builder,
            "fetch_in_force_tree",
            side_effect=_fetch,
        ):
            dialog = self._open_dialog()
            thread = dialog._runner._thread
            worker = dialog._runner.worker
            QTimer.singleShot(20, lambda: _poke(dialog))
            code = dialog.exec()
            self._finish_cleanup(dialog, thread, worker)

        self.assertEqual(code, QDialog.DialogCode.Rejected)
        self.assertTrue(self.worker_threads)
        self.assertTrue(all(item is not QThread.currentThread() for item in self.worker_threads))
        runs = legal_check_run_service.list_all()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].status, CHECK_RUN_CANCELLED)
        if cancelled_in_ui:
            self.assertEqual(dialog.status_label.text(), "Kontrola byla zrušena.")
            self.assertTrue(dialog.worker_alive_at_outcome)
            self.assertFalse(dialog.deletion_scheduled_at_outcome)
            self.assertTrue(
                all(item is QThread.currentThread() for item in dialog.callback_threads)
            )

    def _reset_tables(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_change import LegalChange
        from moduly.pravni_pozadavky.modely.legal_change_section import LegalChangeSection
        from moduly.pravni_pozadavky.modely.legal_check_run import LegalCheckRun
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_document_version import LegalDocumentVersion
        from moduly.pravni_pozadavky.modely.legal_section import LegalSection

        with get_session() as session:
            session.execute(delete(LegalChangeSection))
            session.execute(delete(LegalChange))
            session.execute(delete(LegalCheckRun))
            session.execute(delete(LegalSection))
            session.execute(delete(LegalDocumentVersion))
            session.execute(delete(LegalDocument))
            session.commit()


if __name__ == "__main__":
    unittest.main()
