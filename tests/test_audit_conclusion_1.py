"""AUDIT-CONCLUSION-1: povinný závěr auditu a podmíněné silné stránky."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import uuid
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-conclusion-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.verification_type import VERIFICATION_TYPE_DOCUMENTATION
    from moduly.audity.constants import (
        AUDIT_CONCLUSION_EXPORT_SECTION,
        AUDIT_CONCLUSION_REQUIRED_MESSAGE,
        AUDIT_STATUS_DOKONCENO,
        AUDIT_STATUS_PROBIHA,
        AUDIT_STRENGTHS_EXPORT_SECTION,
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
        CONTROL_POINT_SEVERITY_STREDNI,
        EXTRAORDINARY_TARGET_STATUS_PENDING,
    )
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_extraordinary_question_service import (
        audit_extraordinary_question_service,
    )
    from moduly.audity.sluzby.audit_lead_recommendation_service import (
        confirmed_recommendation_fields,
    )
    from moduly.audity.sluzby.audit_service import (
        AuditCompletionError,
        audit_service,
    )
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.audity.ui.audit_dialog import AuditDialog
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


class AuditConclusion1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)
        suffix = uuid.uuid4().hex[:6]
        self.workplace = settings_service.save_workplace(
            name=f"Závěr-WP-{suffix}",
            active=True,
        )
        self.leader = settings_service.save_worker(
            first_name="Jan",
            last_name=f"Závěr-{suffix}",
        )
        self.workplace_rep = settings_service.save_worker(
            first_name="Eva",
            last_name=f"Provoz-{suffix}",
        )
        self.union = person_service.create_person(
            first_name="Lucie",
            last_name=f"Odbory-{suffix}",
        )

    def _create_audit(self, **fields):
        payload = {
            "workplace_id": self.workplace.id,
            "workplace_name": self.workplace.name,
            "year": 2026,
            "started_at": date(2026, 8, 1),
            "title": "Závěr test",
        }
        payload.update(fields)
        audit = audit_service.create_audit(**payload)
        audit_commission_service.save_members(
            audit.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": self.leader.id,
                    "display_name": "Jan Závěr",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": self.workplace_rep.id,
                    "display_name": "Eva Provoz",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "person_id": self.union.id,
                    "display_name": "Lucie Odbory",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
        return audit

    def test_01_schema_column_present(self) -> None:
        from core.database.session import get_session
        from sqlalchemy import text

        with get_session() as session:
            rows = session.execute(text("PRAGMA table_info(audits)")).fetchall()
        columns = {str(row[1]) for row in rows}
        self.assertIn("conclusion_text", columns)

    def test_02_save_multiline_conclusion(self) -> None:
        audit = self._create_audit()
        text = "První odstavec.\n\nDruhý odstavec závěru."
        updated = audit_service.update_audit(audit.id, conclusion_text=text)
        assert updated is not None
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.conclusion_text, text)
        self.assertIsNone(loaded.finished_at)

    def test_03_dirty_and_save_keep_open(self) -> None:
        audit = self._create_audit()
        dialog = AuditDialog(audit=audit)
        self.assertFalse(dialog._is_dirty())
        dialog.conclusion_widget.conclusion_edit.setPlainText("Dirty závěr")
        self.assertTrue(dialog._is_dirty())
        self.assertTrue(dialog._persist())
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.conclusion_text, "Dirty závěr")
        self.assertFalse(dialog._is_dirty())

    def test_04_save_and_close_persists(self) -> None:
        audit = self._create_audit()
        dialog = AuditDialog(audit=audit)
        dialog.conclusion_widget.conclusion_edit.setPlainText("Uložit a zavřít")
        dialog._save_and_close()
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.conclusion_text, "Uložit a zavřít")
        self.assertFalse(dialog.isVisible())

    def test_05_discard_conclusion(self) -> None:
        audit = self._create_audit(conclusion_text="Původní")
        dialog = AuditDialog(audit=audit_service.get_by_id(audit.id))
        dialog.conclusion_widget.conclusion_edit.setPlainText("Zahozeno")
        self.assertTrue(dialog._is_dirty())
        with patch(
            "moduly.audity.ui.audit_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            self.assertTrue(dialog._confirm_close())
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.conclusion_text, "Původní")

    def test_06_interim_save_and_close_without_conclusion_allowed(self) -> None:
        audit = self._create_audit()
        updated = audit_service.update_audit(audit.id, title="Bez závěru")
        assert updated is not None
        self.assertIsNone(updated.conclusion_text)
        dialog = AuditDialog(audit=updated)
        self.assertFalse(dialog._is_dirty())
        self.assertTrue(dialog._confirm_close())

    def test_07_complete_without_conclusion_rejected(self) -> None:
        audit = self._create_audit()
        with self.assertRaises(AuditCompletionError) as ctx:
            audit_service.update_audit(audit.id, finished_at=date(2026, 8, 10))
        self.assertEqual(str(ctx.exception), AUDIT_CONCLUSION_REQUIRED_MESSAGE)
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertIsNone(loaded.finished_at)
        self.assertEqual(loaded.status, AUDIT_STATUS_PROBIHA)

    def test_08_whitespace_conclusion_rejected(self) -> None:
        audit = self._create_audit()
        with self.assertRaises(AuditCompletionError):
            audit_service.update_audit(
                audit.id,
                finished_at=date(2026, 8, 10),
                conclusion_text="  \n\n  ",
            )
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertIsNone(loaded.finished_at)

    def test_09_failed_completion_atomic_no_side_effects(self) -> None:
        question = audit_extraordinary_question_service.create_question(
            question_text="C1 blok závěr",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self.workplace.id],
        )
        targets_before = (
            audit_extraordinary_question_service.repository.list_targets_for_question(
                question.id
            )
        )
        self.assertEqual(targets_before[0].status, EXTRAORDINARY_TARGET_STATUS_PENDING)
        audit = self._create_audit()
        with self.assertRaises(AuditCompletionError):
            audit_service.update_audit(audit.id, finished_at=date(2026, 8, 11))
        targets_after = (
            audit_extraordinary_question_service.repository.list_targets_for_question(
                question.id
            )
        )
        self.assertEqual(targets_after[0].status, EXTRAORDINARY_TARGET_STATUS_PENDING)
        self.assertIsNone(targets_after[0].verified_audit_id)
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertIsNone(loaded.finished_at)
        self.assertEqual(loaded.status, AUDIT_STATUS_PROBIHA)

    def test_10_complete_with_valid_conclusion(self) -> None:
        audit = self._create_audit()
        updated = audit_service.update_audit(
            audit.id,
            finished_at=date(2026, 8, 12),
            conclusion_text="Platný závěr auditu.",
            **confirmed_recommendation_fields(audit.id),
        )
        assert updated is not None
        self.assertEqual(updated.status, AUDIT_STATUS_DOKONCENO)
        self.assertEqual(updated.conclusion_text, "Platný závěr auditu.")

    def test_11_legacy_completed_without_conclusion_open_and_export(self) -> None:
        audit = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2025,
            finished_at=date(2025, 1, 15),
            conclusion_text=None,
            title="Historie bez závěru",
        )
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertEqual(loaded.status, AUDIT_STATUS_DOKONCENO)
        self.assertIsNone(loaded.conclusion_text)
        saved = audit_service.update_audit(loaded.id, title="Historie OK")
        assert saved is not None
        path = protokol_audit_service.generate_for_audit(saved)
        content = _odt_content(path)
        self.assertNotIn(AUDIT_CONCLUSION_EXPORT_SECTION, content)
        detailed = protokol_audit_service.generate_detailed_report_for_audit(saved)
        detailed_content = _odt_content(detailed)
        self.assertNotIn(AUDIT_CONCLUSION_EXPORT_SECTION, detailed_content)

    def test_12_protocol_and_detailed_contain_conclusion_before_signatures(self) -> None:
        audit = self._create_audit(
            conclusion_text="Finální odstavec závěru.\nDruhý řádek.",
            finished_at=date(2026, 8, 13),
        )
        protocol = protokol_audit_service.generate_for_audit(audit)
        content = _odt_content(protocol)
        self.assertIn(AUDIT_CONCLUSION_EXPORT_SECTION, content)
        self.assertIn("Finální odstavec závěru.", content)
        self.assertIn("Druhý řádek.", content)
        self.assertLess(
            content.find(AUDIT_CONCLUSION_EXPORT_SECTION),
            content.find("Podpisy"),
        )
        detailed = protokol_audit_service.generate_detailed_report_for_audit(audit)
        d_content = _odt_content(detailed)
        self.assertIn(AUDIT_CONCLUSION_EXPORT_SECTION, d_content)
        self.assertIn("Finální odstavec závěru.", d_content)
        self.assertLess(
            d_content.find(AUDIT_CONCLUSION_EXPORT_SECTION),
            d_content.find("Příloha A"),
        )

    def test_13_empty_conclusion_no_section(self) -> None:
        audit = self._create_audit()
        content = _odt_content(protokol_audit_service.generate_for_audit(audit))
        self.assertNotIn(AUDIT_CONCLUSION_EXPORT_SECTION, content)
        d_content = _odt_content(
            protokol_audit_service.generate_detailed_report_for_audit(audit)
        )
        self.assertNotIn(AUDIT_CONCLUSION_EXPORT_SECTION, d_content)

    def test_14_filled_strengths_keep_output(self) -> None:
        audit = self._create_audit(
            silne_stranky="Funkční systém řízení.\nDobře vedená dokumentace."
        )
        content = _odt_content(protokol_audit_service.generate_for_audit(audit))
        self.assertIn(AUDIT_STRENGTHS_EXPORT_SECTION, content)
        self.assertIn("✔ Funkční systém řízení.", content)
        self.assertIn("✔ Dobře vedená dokumentace.", content)

    def test_15_empty_strengths_no_heading(self) -> None:
        audit = self._create_audit(silne_stranky="  \n\n  ")
        content = _odt_content(protokol_audit_service.generate_for_audit(audit))
        self.assertNotIn(AUDIT_STRENGTHS_EXPORT_SECTION, content)
        d_content = _odt_content(
            protokol_audit_service.generate_detailed_report_for_audit(audit)
        )
        self.assertNotIn(AUDIT_STRENGTHS_EXPORT_SECTION, d_content)

    def test_16_ui_complete_without_conclusion_shows_message(self) -> None:
        audit = self._create_audit()
        dialog = AuditDialog(audit=audit)
        with patch(
            "moduly.audity.ui.audit_conclusion_widget.QMessageBox.warning"
        ) as mock_warn:
            dialog.conclusion_widget._complete_audit()
            mock_warn.assert_called()
            self.assertEqual(
                mock_warn.call_args.args[2],
                AUDIT_CONCLUSION_REQUIRED_MESSAGE,
            )
        loaded = audit_service.get_by_id(audit.id)
        assert loaded is not None
        self.assertIsNone(loaded.finished_at)

    def test_17_reopen_then_complete_requires_conclusion(self) -> None:
        audit = audit_service.create_audit(
            workplace_id=self.workplace.id,
            workplace_name=self.workplace.name,
            year=2026,
            finished_at=date(2026, 1, 1),
            conclusion_text=None,
        )
        reopened = audit_service.update_audit(audit.id, finished_at=None)
        assert reopened is not None
        self.assertIsNone(reopened.finished_at)
        with self.assertRaises(AuditCompletionError):
            audit_service.update_audit(reopened.id, finished_at=date(2026, 8, 14))
        done = audit_service.update_audit(
            reopened.id,
            finished_at=date(2026, 8, 14),
            conclusion_text="Doplněný závěr po znovuotevření.",
            **confirmed_recommendation_fields(reopened.id),
        )
        assert done is not None
        self.assertEqual(done.status, AUDIT_STATUS_DOKONCENO)


if __name__ == "__main__":
    unittest.main()
