"""AUDIT-PROGRAM-ODT-EXPORT-1: export plánu interních auditů do ODT."""

from __future__ import annotations

import hashlib
import importlib
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import event

_TMP = Path(tempfile.mkdtemp(prefix="audit-program-odt-export-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    import core.services.editable_catalog_service as editable_catalog_module

    importlib.reload(editable_catalog_module)

    from moduly.audity.constants import (
        AUDIT_PROGRAM_EXPORT_PLAN_BUTTON,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
    )
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_program_plan_export_context_service import (
        MISSING_VISIT_PROCESSES_WARNING,
        audit_program_plan_export_context_service,
    )
    from moduly.audity.sluzby.audit_program_plan_export_service import (
        audit_program_plan_export_service,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.audity.ui.audit_program_manager_dialog import AuditProgramManagerDialog
    from moduly.nastaveni.sluzby.settings_service import settings_service


REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_TEMPLATE = (
    REPO_ROOT / "moduly" / "audity" / "templates" / "exporty" / "ProtokolAudit.odt"
)
DETAILED_TEMPLATE = (
    REPO_ROOT / "moduly" / "audity" / "templates" / "exporty" / "PodrobnaZpravaAudit.odt"
)


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _odt_plain_text(content: str) -> str:
    text = re.sub(r"<text:line-break\s*/>", "\n", content)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find_libreoffice() -> str | None:
    candidates: list[str] = []
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    for extra in (
        Path("/usr/bin/soffice"),
        Path("/usr/bin/libreoffice"),
        Path("/snap/bin/libreoffice"),
    ):
        if extra.exists():
            candidates.append(str(extra))
    for path in candidates:
        if "/snap/" not in path:
            return path
    return candidates[0] if candidates else None


class AuditProgramOdtExportTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        audit_knowledge_service.ensure_catalogs()
        cls._protocol_hash = _file_sha256(PROTOCOL_TEMPLATE)
        cls._detailed_hash = _file_sha256(DETAILED_TEMPLATE)

    def setUp(self) -> None:
        self._workplace_a = settings_service.save_workplace(name="Provoz Alfa")
        self._workplace_b = settings_service.save_workplace(name="Provoz Beta")

    def _create_program(self, *, name: str = "ZX-ZF"):
        return audit_program_service.create_program(
            name=name,
            date_from=date(2026, 1, 1),
            date_to=date(2029, 12, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )

    def _add_workplace(self, program_id: int, workplace) -> None:
        audit_program_service.add_workplace(
            program_id,
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            audit_interval_months=12,
        )

    def _create_dialog(self) -> AuditProgramManagerDialog:
        dialog = AuditProgramManagerDialog()
        QApplication.processEvents()
        return dialog

    def _export(self, program_id: int) -> Path:
        target = Path(tempfile.mkdtemp()) / "plan.odt"
        return audit_program_plan_export_service.generate_for_program(program_id, target)

    def test_button_disabled_without_program_or_visits(self) -> None:
        dialog = self._create_dialog()
        self.assertEqual(dialog._export_plan_btn.text(), AUDIT_PROGRAM_EXPORT_PLAN_BUTTON)
        self.assertFalse(dialog._export_plan_btn.isEnabled())

        program = self._create_program()
        dialog._reload_program_list(select_program_id=program.id)
        QApplication.processEvents()
        self.assertTrue(dialog._final_report_btn.isEnabled())
        self.assertFalse(dialog._export_plan_btn.isEnabled())

        self._add_workplace(program.id, self._workplace_a)
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace_a.id,
            planned_year=2026,
            planned_month=3,
        )
        dialog._reload_program_list(select_program_id=program.id)
        QApplication.processEvents()
        self.assertTrue(dialog._export_plan_btn.isEnabled())
        self.assertIsNone(visit.audit_id)

    def test_header_schedule_process_summary_and_sorting(self) -> None:
        program = self._create_program(name="ZX-ZF")
        self._add_workplace(program.id, self._workplace_a)
        self._add_workplace(program.id, self._workplace_b)
        later = audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace_a.id,
            planned_year=2027,
            planned_month=1,
        )
        first = audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace_b.id,
            planned_year=2026,
            planned_month=12,
        )
        second = audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace_a.id,
            planned_year=2026,
            planned_month=12,
        )
        processes = audit_knowledge_service.get_processes(include_inactive=True)
        self.assertGreaterEqual(len(processes), 2)
        process_a, process_b = processes[0], processes[1]
        audit_program_service.add_visit_process(
            first.id,
            process_id=process_a.id,
            process_name=process_a.nazev,
        )
        audit_program_service.add_visit_process(
            second.id,
            process_id=process_a.id,
            process_name=process_a.nazev,
        )
        audit_program_service.add_visit_process(
            later.id,
            process_id=process_a.id,
            process_name=process_a.nazev,
        )
        audit_program_service.add_visit_process(
            later.id,
            process_id=process_b.id,
            process_name=process_b.nazev,
        )

        context = audit_program_plan_export_context_service.build(program.id)
        self.assertEqual(len(context.schedule_rows), 3)
        self.assertEqual(
            [row.visit_id for row in context.schedule_rows],
            [second.id, first.id, later.id],
        )
        self.assertEqual(context.schedule_rows[0].month_label, "prosinec")
        self.assertEqual(context.schedule_rows[2].month_label, "leden")
        self.assertTrue(all(row.visit_id for row in context.schedule_rows))
        self.assertIsNone(
            audit_program_service.repository.get_visit(first.id).audit_id
        )

        process_ids = [row.process_id for row in context.process_rows]
        self.assertEqual(len(process_ids), len(set(process_ids)))
        self.assertEqual(len(context.process_rows), 2)
        process_a_row = next(
            row for row in context.process_rows if row.process_id == process_a.id
        )
        process_b_row = next(
            row for row in context.process_rows if row.process_id == process_b.id
        )
        self.assertEqual(process_a_row.visit_count, 3)
        self.assertEqual(process_b_row.visit_count, 1)
        self.assertEqual(
            process_a_row.workplaces,
            tuple(sorted({self._workplace_a.name, self._workplace_b.name})),
        )
        self.assertEqual(process_b_row.workplaces, (self._workplace_a.name,))

        path = self._export(program.id)
        with zipfile.ZipFile(path) as zin:
            self.assertIn("content.xml", zin.namelist())
            self.assertEqual(zin.read("mimetype").decode("ascii"), "application/vnd.oasis.opendocument.text")
        content = _odt_content(path)
        plain = _odt_plain_text(content)
        self.assertIn("Plán interních auditů", plain)
        self.assertIn(program.number, plain)
        self.assertIn("ZX-ZF", plain)
        self.assertIn("1. 1. 2026", plain)
        self.assertIn("prosinec", plain)
        self.assertIn("leden", plain)
        self.assertIn(self._workplace_a.name, plain)
        self.assertIn("table:table-header-rows", content)
        self.assertIn("Schváleno představenstvem dne:", plain)
        self.assertIn("Číslo usnesení:", plain)
        self.assertNotIn("None", plain)
        self.assertNotIn("Findings", plain)
        self.assertEqual(content.count('<table:table table:name="Harmonogram"'), 1)
        self.assertEqual(
            content.count('<table:table-row table:style-name="PlanBodyRow">'),
            5,  # 3 harmonogram + 2 souhrn procesů
        )

    def test_visit_without_audit_and_missing_processes_warning(self) -> None:
        program = self._create_program()
        self._add_workplace(program.id, self._workplace_a)
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace_a.id,
            planned_year=2026,
            planned_month=4,
        )
        self.assertIsNone(visit.audit_id)
        path = self._export(program.id)
        plain = _odt_plain_text(_odt_content(path))
        self.assertIn(MISSING_VISIT_PROCESSES_WARNING, plain)
        self.assertIn(self._workplace_a.name, plain)
        self.assertIn("duben", plain)
        self.assertEqual(audit_program_service.repository.get_visit(visit.id).audit_id, None)
        self.assertEqual(len(audit_service.get_all()), 0)

    def test_export_does_not_write_db_or_create_audit(self) -> None:
        program = self._create_program()
        self._add_workplace(program.id, self._workplace_a)
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace_a.id,
            planned_year=2026,
            planned_month=5,
        )
        writes: list[str] = []

        def _capture(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
            sql = statement.lstrip().upper()
            if sql.startswith(("INSERT", "UPDATE", "DELETE")):
                writes.append(sql)

        event.listen(session_module.engine, "before_cursor_execute", _capture)
        try:
            with patch.object(
                audit_program_service,
                "create_audit_from_visit",
                side_effect=AssertionError("export nesmí zakládat Audit"),
            ):
                self._export(program.id)
        finally:
            event.remove(session_module.engine, "before_cursor_execute", _capture)

        self.assertEqual(writes, [])
        self.assertIsNone(audit_program_service.repository.get_visit(visit.id).audit_id)
        self.assertEqual(len(audit_service.get_all()), 0)

    def test_cancel_file_dialog_creates_nothing(self) -> None:
        program = self._create_program()
        self._add_workplace(program.id, self._workplace_a)
        audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace_a.id,
            planned_year=2026,
            planned_month=6,
        )
        dialog = self._create_dialog()
        dialog._reload_program_list(select_program_id=program.id)
        from core.services.storage_service import storage_service

        exports = storage_service.exports_dir
        before = sorted(path.name for path in exports.glob("*.odt")) if exports.exists() else []
        with patch(
            "moduly.audity.ui.audit_program_manager_dialog.open_local_file",
            return_value=True,
        ):
            dialog._export_plan()
        after = sorted(path.name for path in exports.glob("*.odt")) if exports.exists() else []
        self.assertEqual(before, after)

    def test_libreoffice_opens_document_if_available(self) -> None:
        lo = _find_libreoffice()
        if lo is None:
            self.skipTest("LibreOffice není dostupné")
        program = self._create_program()
        self._add_workplace(program.id, self._workplace_a)
        audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace_a.id,
            planned_year=2026,
            planned_month=7,
        )
        path = self._export(program.id)
        out_dir = Path(tempfile.mkdtemp(prefix="plan-odt-lo-"))
        env = os.environ.copy()
        env["HOME"] = str(out_dir / "home")
        (out_dir / "home").mkdir(parents=True, exist_ok=True)
        local_odt = out_dir / path.name
        shutil.copy2(path, local_odt)
        try:
            result = subprocess.run(
                [
                    lo,
                    "--headless",
                    "--nologo",
                    "--nolockcheck",
                    "--nodefault",
                    "--nofirststartwizard",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(out_dir),
                    str(local_odt),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            self.skipTest(f"LibreOffice nelze spustit: {exc}")
        pdfs = list(out_dir.glob("*.pdf"))
        if result.returncode != 0 or not pdfs:
            self.skipTest(
                "LibreOffice nepřipravil PDF "
                f"(code={result.returncode}, stderr={(result.stderr or '')[-400:]})"
            )
        self.assertTrue(pdfs)

    def test_existing_audit_export_templates_unchanged(self) -> None:
        self.assertEqual(_file_sha256(PROTOCOL_TEMPLATE), self._protocol_hash)
        self.assertEqual(_file_sha256(DETAILED_TEMPLATE), self._detailed_hash)
        self.assertEqual(
            protokol_audit_service.TEMPLATE_NAME,
            "ProtokolAudit.odt",
        )
        self.assertEqual(
            protokol_audit_service.DETAILED_REPORT_TEMPLATE_NAME,
            "PodrobnaZpravaAudit.odt",
        )


if __name__ == "__main__":
    unittest.main()
