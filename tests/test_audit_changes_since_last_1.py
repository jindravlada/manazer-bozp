"""AUDIT-CHANGES-SINCE-LAST-1: změny od posledního auditu v obou výstupech."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HOME = Path(tempfile.mkdtemp(prefix="audit-changes-since-last-1-"))
_HOME_PATCHER = patch.object(Path, "home", return_value=_HOME)
_HOME_PATCHER.start()

import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()

import core.database.session as session_module

importlib.reload(session_module)
session_module.reconfigure_database_engine(force=True)

from core.database.database_initializer import initialize_database  # noqa: E402

initialize_database()

from PySide6.QtWidgets import QApplication  # noqa: E402

from moduly.audity.constants import (  # noqa: E402
    AUDIT_INTRO_CHANGES_EMPTY,
    AUDIT_INTRO_CHANGES_LABEL,
    AUDIT_INTRO_EXPORT_SECTION,
)
from moduly.audity.sluzby.audit_service import audit_service  # noqa: E402
from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service  # noqa: E402
from moduly.audity.ui.audit_dialog import AuditDialog  # noqa: E402
from moduly.nastaveni.sluzby.settings_service import settings_service  # noqa: E402

_REPO = Path(__file__).resolve().parents[1]
_TEMPLATES = _REPO / "moduly" / "audity" / "templates" / "exporty"
_PLACEHOLDER = (
    "${clenove_komise_text}</text:p></table:table-cell></table:table-row>"
    "</table:table><text:p text:style-name=\"Standard\">"
    "${zmeny_od_posledniho_auditu_text}</text:p>"
)
_CHANGES = "Nová montážní linka.\n\nDruhá směna zrušena."


def _odt_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


def _commission_table_end(content: str) -> int:
    start = content.find("Členové komise")
    if start < 0:
        raise AssertionError("V dokumentu chybí řádek Členové komise.")
    end = content.find("</table:table>", start)
    if end < 0:
        raise AssertionError("Za členy komise chybí konec tabulky.")
    return end + len("</table:table>")


class AuditChangesSinceLast1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in audit_service.get_all():
            audit_service.delete_audit(audit.id)
        self.workplace = settings_service.save_workplace(name="Provoz změn", active=True)
        self._warning = patch(
            "moduly.audity.ui.audit_dialog.QMessageBox.warning",
            side_effect=AssertionError("neočekávané varování při ukládání auditu"),
        )
        self._warning.start()

    def tearDown(self) -> None:
        self._warning.stop()

    def _create(self, **fields):
        payload = {
            "workplace_id": self.workplace.id,
            "workplace_name": self.workplace.name,
            "year": 2026,
            "planned_month": 4,
            "title": "Původní název auditu",
        }
        payload.update(fields)
        return audit_service.create_audit(**payload)

    def test_template_placeholder_follows_commission_table(self) -> None:
        for name in ("ProtokolAudit.odt", "PodrobnaZpravaAudit.odt"):
            xml = _odt_text(_TEMPLATES / name)
            self.assertIn(_PLACEHOLDER, xml)

    def test_save_reload_keeps_multiline_text(self) -> None:
        audit = self._create()
        dialog = AuditDialog(audit=audit)
        dialog.history_widget._changes_edit.setPlainText(_CHANGES)
        with (
            patch.object(dialog.commission_widget, "validate", return_value=(True, "")),
            patch.object(dialog, "save_commission_members"),
        ):
            self.assertTrue(dialog._persist())

        reloaded = audit_service.get_by_id(audit.id)
        assert reloaded is not None
        self.assertEqual(reloaded.changes_since_last, _CHANGES)
        self.assertEqual(reloaded.workplace_name, self.workplace.name)
        self.assertEqual(reloaded.year, 2026)

        again = AuditDialog(audit=reloaded)
        self.assertEqual(again.history_widget._changes_edit.toPlainText(), _CHANGES)
        self.assertFalse(again._is_dirty())

    def test_legacy_audit_without_value_stays_empty(self) -> None:
        audit = self._create()
        self.assertIsNone(audit.changes_since_last)
        reloaded = audit_service.get_by_id(audit.id)
        assert reloaded is not None
        self.assertIsNone(reloaded.changes_since_last)
        dialog = AuditDialog(audit=reloaded)
        self.assertEqual(dialog.history_widget._changes_edit.toPlainText(), "")
        self.assertFalse(dialog._is_dirty())

    def test_edit_is_deferred_until_save_and_discard_restores(self) -> None:
        audit = self._create(changes_since_last="Uložený text")
        before = audit_service.get_by_id(audit.id)
        assert before is not None
        stamp = before.updated_at

        dialog = AuditDialog(audit=before)
        dialog.history_widget._changes_edit.setPlainText("Rozepsaná změna")
        self.assertTrue(dialog._is_dirty())

        untouched = audit_service.get_by_id(audit.id)
        assert untouched is not None
        self.assertEqual(untouched.changes_since_last, "Uložený text")
        self.assertEqual(untouched.updated_at, stamp)

        with patch(
            "moduly.audity.ui.audit_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(dialog._confirm_close())
        self.assertEqual(dialog.history_widget._changes_edit.toPlainText(), "Uložený text")
        after_discard = audit_service.get_by_id(audit.id)
        assert after_discard is not None
        self.assertEqual(after_discard.changes_since_last, "Uložený text")
        self.assertEqual(after_discard.updated_at, stamp)

    def test_blank_text_is_stored_as_empty_and_omits_section(self) -> None:
        audit = self._create(changes_since_last="Dočasně")
        dialog = AuditDialog(audit=audit)
        dialog.history_widget._changes_edit.setPlainText("   \n  ")
        with (
            patch.object(dialog.commission_widget, "validate", return_value=(True, "")),
            patch.object(dialog, "save_commission_members"),
        ):
            self.assertTrue(dialog._persist())
        reloaded = audit_service.get_by_id(audit.id)
        assert reloaded is not None
        self.assertIsNone(reloaded.changes_since_last)
        self._assert_section_omitted(reloaded)

    def test_section_in_protocol_immediately_after_commission(self) -> None:
        audit = self._create(changes_since_last=_CHANGES)
        content = _odt_text(protokol_audit_service.generate_for_audit(audit))
        self._assert_section_after_commission(content, "CELKOVÉ HODNOCENÍ")
        self.assertNotIn(AUDIT_INTRO_EXPORT_SECTION, content)
        self.assertEqual(content.count("Nová montážní linka."), 1)
        self.assertEqual(content.count("Druhá směna zrušena."), 1)

    def test_section_in_detailed_report_immediately_after_commission(self) -> None:
        audit = self._create(changes_since_last=_CHANGES)
        content = _odt_text(
            protokol_audit_service.generate_detailed_report_for_audit(audit)
        )
        self._assert_section_after_commission(
            content,
            f'text:style-name="H">{AUDIT_INTRO_EXPORT_SECTION}</text:p>',
        )
        self.assertEqual(content.count("Nová montážní linka."), 1)
        self.assertEqual(content.count(AUDIT_INTRO_CHANGES_LABEL), 1)

    def test_empty_value_omits_section_in_both_documents(self) -> None:
        audit = self._create()
        self._assert_section_omitted(audit)

    def _assert_section_after_commission(self, content: str, following: str) -> None:
        table_end = _commission_table_end(content)
        changes = content.find(AUDIT_INTRO_CHANGES_LABEL, table_end)
        next_part = content.find(following, table_end)
        self.assertGreaterEqual(changes, 0)
        self.assertGreater(next_part, changes)
        between_table_and_changes = content[table_end:changes]
        between_table_and_next = content[table_end:next_part]
        for marker in (
            "CELKOVÉ HODNOCENÍ",
            f">{AUDIT_INTRO_EXPORT_SECTION}<",
            "Přehled výsledků",
        ):
            self.assertNotIn(marker, between_table_and_changes)
        self.assertIn(
            f'text:style-name="H">{AUDIT_INTRO_CHANGES_LABEL}</text:p>',
            between_table_and_next,
        )
        self.assertIn("Nová montážní linka.", between_table_and_next)
        self.assertIn("Druhá směna zrušena.", between_table_and_next)
        self.assertNotIn(AUDIT_INTRO_CHANGES_EMPTY, content)

    def _assert_section_omitted(self, audit) -> None:
        protocol = _odt_text(protokol_audit_service.generate_for_audit(audit))
        detailed = _odt_text(
            protokol_audit_service.generate_detailed_report_for_audit(audit)
        )
        for content, following in (
            (protocol, "CELKOVÉ HODNOCENÍ"),
            (detailed, f'text:style-name="H">{AUDIT_INTRO_EXPORT_SECTION}</text:p>'),
        ):
            table_end = _commission_table_end(content)
            next_part = content.find(following, table_end)
            self.assertGreaterEqual(next_part, 0)
            self.assertNotIn(AUDIT_INTRO_CHANGES_LABEL, content[table_end:next_part])
            self.assertNotIn(AUDIT_INTRO_CHANGES_LABEL, content)
            self.assertNotIn(AUDIT_INTRO_CHANGES_EMPTY, content)
            self.assertNotIn("zmeny_od_posledniho_auditu_text", content)
