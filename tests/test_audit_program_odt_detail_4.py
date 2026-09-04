"""AUDIT-PROGRAM-ODT-DETAIL-4: procesy u konkrétní návštěvy v harmonogramu."""

from __future__ import annotations

import importlib
import os
import re
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QFileDialog
from sqlalchemy import event

_TMP = Path(tempfile.mkdtemp(prefix="audit-program-odt-detail-4-"))
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

    from core.services.storage_service import storage_service
    from moduly.audity.constants import DEFAULT_AUDIT_PROGRAM_STANDARDS
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_program_plan_export_context_service import (
        VISIT_PROCESSES_NOT_ASSIGNED,
        audit_program_plan_export_context_service,
    )
    from moduly.audity.sluzby.audit_program_plan_export_service import (
        audit_program_plan_export_service,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui.audit_program_manager_dialog import AuditProgramManagerDialog
    from moduly.nastaveni.sluzby.settings_service import settings_service


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _odt_plain_text(content: str) -> str:
    text = re.sub(r"<text:line-break\s*/>", "\n", content)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _cell_paragraphs(cell_xml: str) -> tuple[str, ...]:
    return tuple(re.findall(r"<text:p\b[^>]*>(.*?)</text:p>", cell_xml))


def _harmonogram_body_rows(content: str) -> list[tuple[str, ...]]:
    match = re.search(
        r'<table:table table:name="Harmonogram".*?</table:table>',
        content,
        re.DOTALL,
    )
    if match is None:
        return []
    table = match.group(0)
    rows: list[tuple[str, ...]] = []
    for row_xml in re.findall(
        r'<table:table-row table:style-name="PlanBodyRow">(.*?)</table:table-row>',
        table,
        re.DOTALL,
    ):
        cells = re.findall(
            r"<table:table-cell\b[^>]*>(.*?)</table:table-cell>",
            row_xml,
            re.DOTALL,
        )
        rows.append(tuple(_cell_paragraphs(cell) for cell in cells))
    return rows


class AuditProgramOdtDetail4TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        audit_knowledge_service.ensure_catalogs()

    def setUp(self) -> None:
        self._workplace_a = settings_service.save_workplace(name="Provoz Alfa")
        self._workplace_b = settings_service.save_workplace(name="Provoz Beta")
        processes = audit_knowledge_service.get_processes(include_inactive=True)
        self.assertGreaterEqual(len(processes), 2)
        self._process_a, self._process_b = processes[0], processes[1]

    def _create_program(self):
        return audit_program_service.create_program(
            name="ZX-ZF",
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

    def _export(self, program_id: int) -> Path:
        return audit_program_plan_export_service.generate_for_program(
            program_id,
            Path(tempfile.mkdtemp()) / "plan.odt",
        )

    def test_schedule_row_has_visit_processes_stacked_and_sorted(self) -> None:
        program = self._create_program()
        self._add_workplace(program.id, self._workplace_a)
        self._add_workplace(program.id, self._workplace_b)
        later = audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace_a.id,
            planned_year=2027,
            planned_month=1,
        )
        beta = audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace_b.id,
            planned_year=2026,
            planned_month=12,
        )
        alfa = audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace_a.id,
            planned_year=2026,
            planned_month=12,
        )
        empty = audit_program_service.add_visit(
            program.id,
            workplace_id=self._workplace_b.id,
            planned_year=2028,
            planned_month=2,
        )
        audit_program_service.add_visit_process(
            alfa.id,
            process_id=self._process_a.id,
            process_name=self._process_a.nazev,
        )
        audit_program_service.add_visit_process(
            beta.id,
            process_id=self._process_b.id,
            process_name=self._process_b.nazev,
        )
        audit_program_service.add_visit_process(
            later.id,
            process_id=self._process_b.id,
            process_name=self._process_b.nazev,
        )
        audit_program_service.add_visit_process(
            later.id,
            process_id=self._process_a.id,
            process_name=self._process_a.nazev,
        )

        context = audit_program_plan_export_context_service.build(program.id)
        self.assertEqual(len(context.schedule_rows), 4)
        self.assertEqual(
            [row.visit_id for row in context.schedule_rows],
            [alfa.id, beta.id, later.id, empty.id],
        )
        alfa_row, beta_row, later_row, empty_row = context.schedule_rows
        self.assertEqual(alfa_row.year_label, "2026")
        self.assertEqual(alfa_row.month_label, "prosinec")
        self.assertEqual(alfa_row.workplace_name, self._workplace_a.name)
        self.assertEqual(alfa_row.process_names, (self._process_a.nazev,))
        self.assertEqual(beta_row.process_names, (self._process_b.nazev,))
        self.assertNotIn(self._process_b.nazev, alfa_row.process_names)
        self.assertNotIn(self._process_a.nazev, beta_row.process_names)
        self.assertEqual(
            later_row.process_names,
            (self._process_a.nazev, self._process_b.nazev),
        )
        self.assertEqual(empty_row.process_names, ())
        self.assertEqual(empty_row.process_cell_lines, (VISIT_PROCESSES_NOT_ASSIGNED,))

        path = self._export(program.id)
        content = _odt_content(path)
        plain = _odt_plain_text(content)
        rows = _harmonogram_body_rows(content)
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0][0], ("2026",))
        self.assertEqual(rows[0][1], ("prosinec",))
        self.assertEqual(rows[0][2], (self._workplace_a.name,))
        self.assertEqual(rows[0][3], (self._process_a.nazev,))
        self.assertEqual(rows[1][3], (self._process_b.nazev,))
        self.assertEqual(
            rows[2][3],
            (self._process_a.nazev, self._process_b.nazev),
        )
        self.assertEqual(rows[3][3], (VISIT_PROCESSES_NOT_ASSIGNED,))
        self.assertNotIn("Souhrn auditovaných procesů", plain)
        self.assertNotIn("Počet plánovaných ověření", plain)
        self.assertNotIn("Provozy zahrnuté v plánu", plain)
        self.assertIn("Schváleno představenstvem dne:", plain)

    def test_export_is_read_only_and_temp_preview_still_opens(self) -> None:
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

        dialog = AuditProgramManagerDialog()
        dialog._reload_program_list(select_program_id=program.id)
        QApplication.processEvents()
        before_export = sorted(
            path.name for path in storage_service.exports_dir.glob("*.odt")
        ) if storage_service.exports_dir.exists() else []
        with patch.object(
            QFileDialog,
            "getSaveFileName",
            side_effect=AssertionError("QFileDialog se nesmí zobrazit"),
        ), patch(
            "moduly.audity.ui.audit_program_manager_dialog.open_local_file",
            return_value=True,
        ) as mock_open:
            dialog._export_plan()
        mock_open.assert_called_once()
        opened = Path(mock_open.call_args.args[0])
        self.assertTrue(opened.exists())
        self.assertEqual(opened.parent.resolve(), Path(tempfile.gettempdir()).resolve())
        after_export = sorted(
            path.name for path in storage_service.exports_dir.glob("*.odt")
        ) if storage_service.exports_dir.exists() else []
        self.assertEqual(before_export, after_export)


if __name__ == "__main__":
    unittest.main()
