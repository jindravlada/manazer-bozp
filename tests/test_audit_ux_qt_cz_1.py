"""AUDIT-UX-QT-CZ-1 – Auditoři a české standardní Qt dialogy."""

from __future__ import annotations

import gc
import importlib
import os
import sys
import tempfile
import time
import unittest
import uuid
import weakref
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QDate, QLocale, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QLabel,
    QPushButton,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-ux-qt-cz-1-"))
_REPO = Path(__file__).resolve().parents[1]
_BUNDLED_QTBASE = _REPO / "zdroje" / "preklady" / "qtbase_cs.qm"
_BUNDLED_OVERLAY = _REPO / "zdroje" / "preklady" / "qt_filedialog_cs.qm"

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.i18n.qt_translator import (
        find_qt_translation,
        install_qt_translators,
        installed_qt_translators,
        qt_translation_search_dirs,
        reset_qt_translators,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui.audit_commission_widget import AuditCommissionWidget
    from moduly.audity.ui.audit_dialog import AuditDialog
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _widget_texts(root) -> list[str]:
    texts: list[str] = []
    for widget in root.findChildren(QGroupBox):
        texts.append(widget.title())
    for widget in root.findChildren(QLabel):
        texts.append(widget.text())
    for widget in root.findChildren(QPushButton):
        texts.append(widget.text())
    return texts


def _non_native_folder_dialog(title: str = "Vybrat složku s fotografiemi") -> QFileDialog:
    dialog = QFileDialog()
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dialog.setFileMode(QFileDialog.FileMode.Directory)
    dialog.setWindowTitle(title)
    return dialog


class AuditCommissionAuditoriTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)
        suffix = uuid.uuid4().hex[:6]
        self.auditor_a = settings_service.save_worker(
            first_name="Petr", last_name=f"AuditorA-{suffix}"
        ).id
        self.auditor_b = settings_service.save_worker(
            first_name="Adam", last_name=f"AuditorB-{suffix}"
        ).id
        self.leader_id = settings_service.save_worker(
            first_name="Jan", last_name=f"Vedoucí-{suffix}"
        ).id
        self.workplace_id = settings_service.save_worker(
            first_name="Eva", last_name=f"Provoz-{suffix}"
        ).id
        self.union_id = person_service.create_person(
            first_name="Lucie", last_name=f"Odbory-{suffix}"
        ).id

    def test_commission_tab_uses_auditori_with_hacek(self) -> None:
        widget = AuditCommissionWidget()
        self.assertEqual(widget.members_box.title(), "Auditoři")
        joined = "\n".join(_widget_texts(widget))
        self.assertIn("Auditoři", joined)
        self.assertNotIn("Auditori", joined)
        self.assertIn("jsou povinní", joined)
        self.assertIn("jsou volitelní", joined)

    def test_auditor_buttons_still_follow_selection(self) -> None:
        widget = AuditCommissionWidget()
        widget._members = [
            {
                "thp_worker_id": self.auditor_a,
                "display_name": "A",
                "role_text": "",
                "note_text": "",
            },
            {
                "thp_worker_id": self.auditor_b,
                "display_name": "B",
                "role_text": "",
                "note_text": "",
            },
        ]
        widget._refresh_tables()
        self.assertEqual(widget.members_table.rowCount(), 2)
        self.assertFalse(widget._member_edit_btn.isEnabled())
        widget.members_table.selectRow(0)
        self.assertTrue(widget._member_edit_btn.isEnabled())
        self.assertTrue(widget._member_remove_btn.isEnabled())
        self.assertTrue(widget._member_down_btn.isEnabled())

    def test_opening_audit_dialog_has_no_tracking_regression(self) -> None:
        audit = audit_service.create_audit(title="Komise CZ")
        started = time.perf_counter()
        dialog = AuditDialog(audit=audit)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 5.0)
        self.assertEqual(dialog.commission_widget.members_box.title(), "Auditoři")
        joined = "\n".join(_widget_texts(dialog.commission_widget))
        self.assertNotIn("Auditori", joined)
        source = Path(_REPO / "moduly/audity/ui/audit_dialog.py").read_text(encoding="utf-8")
        self.assertNotIn("install_auto_dirty_tracking", source)
        self.assertNotIn("EditorDialogController(", source)
        dialog.close()


class QtCzechTranslatorTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        reset_qt_translators(self._app)

    def test_translator_loads_from_bundled_resource_path(self) -> None:
        self.assertTrue(_BUNDLED_QTBASE.is_file())
        translators = install_qt_translators(
            self._app,
            search_dirs=[_BUNDLED_QTBASE.parent],
            force=True,
        )
        self.assertGreaterEqual(len(translators), 1)
        self.assertEqual(
            find_qt_translation("qtbase_cs.qm", search_dirs=[_BUNDLED_QTBASE.parent]),
            _BUNDLED_QTBASE,
        )
        self.assertEqual(
            QCoreApplication.translate("QFileDialog", "Look in:"),
            "Hledat v:",
        )

    def test_translator_stays_alive_after_gc(self) -> None:
        translators = install_qt_translators(
            self._app,
            search_dirs=[_BUNDLED_QTBASE.parent],
            force=True,
        )
        held = getattr(self._app, "_manazer_bozp_qt_translators")
        self.assertEqual(list(held), translators)
        self.assertEqual(list(installed_qt_translators()), translators)
        ref = weakref.ref(translators[0])
        del translators
        gc.collect()
        self.assertIsNotNone(ref())
        self.assertEqual(
            QCoreApplication.translate("QFileDialog", "Directory:"),
            "Adresář:",
        )

    def test_non_native_file_dialog_has_czech_labels_and_custom_title(self) -> None:
        install_qt_translators(
            self._app,
            search_dirs=[_BUNDLED_QTBASE.parent],
            force=True,
        )
        dialog = _non_native_folder_dialog()
        self.assertEqual(dialog.windowTitle(), "Vybrat složku s fotografiemi")
        labels = [widget.text() for widget in dialog.findChildren(QLabel)]
        buttons = [widget.text() for widget in dialog.findChildren(QPushButton)]
        self.assertTrue(any("Hledat v:" in text for text in labels))
        self.assertTrue(any(text.startswith("Adresář:") for text in labels))
        self.assertTrue(any("Soubory typu:" in text for text in labels))
        self.assertTrue(any("Vybrat" in text.replace("&", "") for text in buttons))
        self.assertTrue(any(text.replace("&", "") == "Zrušit" for text in buttons))
        self.assertEqual(
            QCoreApplication.translate("QFileSystemModel", "Computer"),
            "Počítač",
        )
        dialog.deleteLater()

    def test_missing_translation_does_not_crash(self) -> None:
        empty = Path(tempfile.mkdtemp(prefix="qt-cs-missing-"))
        with self.assertLogs("core.i18n.qt_translator", level="WARNING") as captured:
            result = install_qt_translators(self._app, search_dirs=[empty], force=True)
        self.assertEqual(result, [])
        self.assertTrue(any("qtbase_cs.qm" in line for line in captured.output))

    def test_source_and_simulated_appimage_resource_path(self) -> None:
        source_dirs = qt_translation_search_dirs()
        self.assertTrue(any(path == _BUNDLED_QTBASE.parent.resolve() or path == _BUNDLED_QTBASE.parent for path in source_dirs))
        self.assertEqual(find_qt_translation("qtbase_cs.qm"), _BUNDLED_QTBASE.resolve())

        fake = Path(tempfile.mkdtemp(prefix="qt-cs-meipass-")) / "meipass"
        dest = fake / "zdroje" / "preklady"
        dest.mkdir(parents=True)
        dest.joinpath("qtbase_cs.qm").write_bytes(_BUNDLED_QTBASE.read_bytes())
        dest.joinpath("qt_filedialog_cs.qm").write_bytes(_BUNDLED_OVERLAY.read_bytes())
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "_MEIPASS", str(fake), create=True):
                found = find_qt_translation("qtbase_cs.qm")
                self.assertIsNotNone(found)
                assert found is not None
                self.assertEqual(found.resolve(), (dest / "qtbase_cs.qm").resolve())
                translators = install_qt_translators(self._app, force=True)
        self.assertGreaterEqual(len(translators), 1)

    def test_build_configuration_includes_czech_qm(self) -> None:
        self.assertTrue(_BUNDLED_QTBASE.is_file())
        self.assertTrue(_BUNDLED_OVERLAY.is_file())
        release = (_REPO / "build_release.sh").read_text(encoding="utf-8")
        old = (_REPO / "build_old_release.sh").read_text(encoding="utf-8")
        spec = (_REPO / "ManazerBOZP.spec").read_text(encoding="utf-8")
        self.assertIn("zdroje:zdroje", release)
        self.assertIn("qtbase_cs.qm", release)
        self.assertIn("zdroje:zdroje", old)
        self.assertIn("qtbase_cs.qm", old)
        self.assertIn("('zdroje', 'zdroje')", spec)

    def test_business_date_storage_format_unchanged(self) -> None:
        locale_before = QLocale().name()
        iso_before = QDate(2026, 3, 10).toString(Qt.DateFormat.ISODate)
        source = Path(_REPO / "core/i18n/qt_translator.py").read_text(encoding="utf-8")
        self.assertNotIn("setDefault", source)
        install_qt_translators(
            self._app,
            search_dirs=[_BUNDLED_QTBASE.parent],
            force=True,
        )
        self.assertEqual(QLocale().name(), locale_before)
        self.assertEqual(iso_before, "2026-03-10")
        self.assertEqual(
            QDate(2026, 3, 10).toString(Qt.DateFormat.ISODate),
            "2026-03-10",
        )
