"""AUDIT-PROGRAM-STATEMENTS-ODT-1: tisk auditních tvrzení návštěvy do ODT."""

from __future__ import annotations

import importlib
import os
import re
import tempfile
import unittest
import zipfile
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QFileDialog
from sqlalchemy import event, func, select

_TMP = Path(tempfile.mkdtemp(prefix="audit-program-statements-odt-1-"))
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

    from core.database.session import get_session
    from core.services.storage_service import storage_service
    from moduly.audity.constants import (
        AUDIT_PROGRAM_PRINT_STATEMENTS_BUTTON,
        AUDIT_PROGRAM_PRINT_STATEMENTS_EMPTY,
        AUDIT_PROGRAM_PRINT_STATEMENTS_OPEN_FAILED,
        AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_MARKS,
        AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_N,
        AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_NP,
        AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_V,
        AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_VD,
        AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_CURRENT,
        AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_FROZEN,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
        PROCESS_TERM_CRITERION,
        PROCESS_TERM_PROCESS,
        PROCESS_TERM_QUESTION,
    )
    from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
    from moduly.audity.sluzby.audit_knowledge_service import (
        AuditKnowledgeService,
        audit_knowledge_service,
    )
    from moduly.audity.sluzby.audit_program_plan_export_service import (
        audit_program_plan_export_service,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_program_statements_export_context_service import (
        AuditProgramStatementsEmptyError,
        audit_program_statements_export_context_service,
    )
    from moduly.audity.sluzby.audit_program_statements_export_service import (
        audit_program_statements_export_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui.audit_program_manager_dialog import AuditProgramManagerDialog
    from moduly.audity.ui.audit_program_plan_tree_widget import (
        NODE_VISIT,
        AuditProgramPlanTreeWidget,
    )
    from tests.audit_v2a_test_support import prepare_v2_audit_create


REPO_EXPORT = Path(__file__).resolve().parents[1] / "export"
CANARY_TEXT = "CANARY-CHANGED-CATALOG"


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _odt_plain_text(content: str) -> str:
    text = re.sub(r"<text:line-break\s*/>", "\n", content)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _iter_tree_items(item):
    yield item
    for index in range(item.childCount()):
        yield from _iter_tree_items(item.child(index))


class AuditProgramStatementsOdt1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        audit_knowledge_service.ensure_catalogs()

    def setUp(self) -> None:
        self._stack = ExitStack()
        self._system_wp, self._operation_wp = self._stack.enter_context(
            prepare_v2_audit_create(
                system_name="Statements ODT systém",
                operation_name="Statements ODT provoz",
            )
        )
        tree = audit_knowledge_service.get_knowledge_tree(ensure=True)
        self._process_nodes = self._processes_with_questions(tree)
        self.assertGreaterEqual(
            len(self._process_nodes),
            2,
            "Metodika musí mít aspoň dva procesy s tvrzeními.",
        )

    def tearDown(self) -> None:
        self._stack.close()

    def _processes_with_questions(self, tree):
        nodes = []
        for process in tree:
            stack = list(process.children)
            has_questions = False
            while stack:
                node = stack.pop()
                section = node.section if isinstance(node.section, dict) else None
                if section and audit_knowledge_service.get_audit_questions(section):
                    has_questions = True
                    break
                stack.extend(list(node.children))
            if has_questions:
                nodes.append(process)
        return nodes

    def _create_program(self, *, name: str = "Program tvrzení"):
        program = audit_program_service.create_program(
            name=name,
            date_from=date(2026, 1, 1),
            date_to=date(2029, 12, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit_program_service.add_workplace(
            program.id,
            workplace_id=self._operation_wp.id,
            workplace_name=self._operation_wp.name,
            audit_interval_months=12,
        )
        return program

    def _add_visit(self, program_id: int, *, month: int):
        return audit_program_service.add_visit(
            program_id,
            workplace_id=self._operation_wp.id,
            planned_year=2026,
            planned_month=month,
        )

    def _assign_process(self, visit, process_node) -> None:
        audit_program_service.add_visit_process(
            visit.id,
            process_id=process_node.process_id,
            process_name=process_node.process_label or process_node.label,
        )

    def _create_two_visits(self):
        program = self._create_program()
        visit_a = self._add_visit(program.id, month=3)
        visit_b = self._add_visit(program.id, month=10)
        self._assign_process(visit_a, self._process_nodes[0])
        self._assign_process(visit_b, self._process_nodes[1])
        return program, visit_a, visit_b

    def _print(self, visit_id: int) -> Path:
        target = Path(tempfile.mkdtemp()) / "tvrzeni.odt"
        return audit_program_statements_export_service.generate_for_visit(
            visit_id, target
        )

    def _create_dialog(self, program_id: int) -> AuditProgramManagerDialog:
        dialog = AuditProgramManagerDialog()
        dialog._reload_program_list(select_program_id=program_id)
        QApplication.processEvents()
        return dialog

    def _find_visit_item(self, dialog: AuditProgramManagerDialog, visit_id: int):
        tree = dialog._plan_tree
        for row in range(tree.topLevelItemCount()):
            for item in _iter_tree_items(tree.topLevelItem(row)):
                if (
                    AuditProgramPlanTreeWidget.node_type(item) == NODE_VISIT
                    and AuditProgramPlanTreeWidget.node_id(item) == visit_id
                ):
                    return item
        self.fail(f"Návštěva {visit_id} není ve stromu.")

    def _select_visit(self, dialog: AuditProgramManagerDialog, visit_id: int):
        item = self._find_visit_item(dialog, visit_id)
        dialog._plan_tree.setCurrentItem(item)
        QApplication.processEvents()
        return item

    def _snapshot_count(self) -> int:
        with get_session() as session:
            return int(
                session.scalar(select(func.count()).select_from(AuditQuestionSnapshot))
                or 0
            )

    def _export_snapshot(self) -> set[str]:
        paths: set[str] = set()
        exports = storage_service.exports_dir
        if exports.exists():
            paths.update(str(path.resolve()) for path in exports.glob("*.odt"))
        if REPO_EXPORT.exists():
            paths.update(str(path.resolve()) for path in REPO_EXPORT.glob("*.odt"))
        return paths

    def _capture_writes(self):
        writes: list[str] = []

        def _capture(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
            sql = statement.lstrip().upper()
            if sql.startswith(("INSERT", "UPDATE", "DELETE")):
                writes.append(sql)

        event.listen(session_module.engine, "before_cursor_execute", _capture)
        return writes, _capture

    def _poison_catalog(self):
        inner_original = AuditKnowledgeService.get_audit_questions

        def poisoned(self_svc, section):
            items = inner_original(self_svc, section)
            changed = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                row = dict(item)
                row["text"] = CANARY_TEXT
                row["nazev"] = CANARY_TEXT
                changed.append(row)
            return changed

        return patch.object(AuditKnowledgeService, "get_audit_questions", poisoned)

    def test_01_unstarted_visit_creates_no_audit_number_date_or_snapshot(self) -> None:
        _program, visit, _other = self._create_two_visits()
        before_audits = {item.id for item in audit_service.get_all()}
        before_snapshots = self._snapshot_count()
        writes, listener = self._capture_writes()
        try:
            with patch.object(
                audit_program_service,
                "create_audit_from_visit",
                side_effect=AssertionError("tisk nesmí zakládat Audit"),
            ):
                path = self._print(visit.id)
        finally:
            event.remove(session_module.engine, "before_cursor_execute", listener)

        reloaded = audit_program_service.repository.get_visit(visit.id)
        self.assertIsNone(reloaded.audit_id)
        self.assertEqual({item.id for item in audit_service.get_all()}, before_audits)
        self.assertEqual(self._snapshot_count(), before_snapshots)
        self.assertEqual(writes, [])
        self.assertTrue(path.exists())
        plain = _odt_plain_text(_odt_content(path))
        self.assertIn(AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_CURRENT, plain)

    def test_02_unstarted_uses_current_methodology_and_visit_scope(self) -> None:
        _program, visit_a, visit_b = self._create_two_visits()
        context = audit_program_statements_export_context_service.build_for_visit(
            visit_a.id
        )
        self.assertTrue(context.rows)
        self.assertEqual(context.document_status, AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_CURRENT)
        process_a = self._process_nodes[0].process_label or self._process_nodes[0].label
        process_b = self._process_nodes[1].process_label or self._process_nodes[1].label
        path = self._print(visit_a.id)
        plain = _odt_plain_text(_odt_content(path))
        self.assertIn(f"{PROCESS_TERM_PROCESS}: {process_a}", plain)
        self.assertNotIn(f"{PROCESS_TERM_PROCESS}: {process_b}", plain)
        for row in context.rows:
            self.assertIn(row.assertion_text, plain)
            self.assertIn(row.verification_label, plain)

        with self._poison_catalog():
            poisoned_path = self._print(visit_a.id)
        poisoned_plain = _odt_plain_text(_odt_content(poisoned_path))
        self.assertIn(CANARY_TEXT, poisoned_plain)
        self.assertNotIn(CANARY_TEXT, plain)

    def test_03_other_visit_processes_are_excluded(self) -> None:
        _program, visit_a, visit_b = self._create_two_visits()
        rows_a = audit_program_statements_export_context_service.build_for_visit(
            visit_a.id
        ).rows
        rows_b = audit_program_statements_export_context_service.build_for_visit(
            visit_b.id
        ).rows
        unique_b = {row.assertion_text for row in rows_b} - {
            row.assertion_text for row in rows_a
        }
        self.assertTrue(unique_b)
        plain_a = _odt_plain_text(_odt_content(self._print(visit_a.id)))
        for text in unique_b:
            self.assertNotIn(text, plain_a)

    def test_04_and_05_started_audit_uses_snapshot_not_current_catalog(self) -> None:
        _program, visit, _other = self._create_two_visits()
        audit = audit_program_service.create_audit_from_visit(
            visit.id, started_at=date(2026, 3, 15)
        )
        self.assertTrue(audit.number)
        self.assertEqual(audit.started_at, date(2026, 3, 15))
        original = audit_program_statements_export_context_service.build_for_visit(
            visit.id
        )
        self.assertIn(
            AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_FROZEN.format(number=audit.number),
            original.document_status,
        )
        original_texts = [row.assertion_text for row in original.rows]
        self.assertTrue(original_texts)
        self.assertNotIn(CANARY_TEXT, original_texts)

        from moduly.audity.sluzby.audit_question_snapshot_service import (
            audit_question_snapshot_service,
        )
        from moduly.audity.sluzby.system_audit_workplace_service import (
            system_audit_workplace_service,
        )

        with self._poison_catalog():
            live_unstarted = audit_question_snapshot_service.build_v2_preview_drafts(
                workplace_id=int(self._operation_wp.id),
                system_workplace_id=int(
                    system_audit_workplace_service.require_system_audit_workplace_id()
                ),
                planned_process_ids={self._process_nodes[0].process_id},
                ensure=False,
            )
            self.assertTrue(
                any(draft.assertion_text == CANARY_TEXT for draft in live_unstarted)
            )
            path = self._print(visit.id)

        plain = _odt_plain_text(_odt_content(path))
        self.assertNotIn(CANARY_TEXT, plain)
        for text in original_texts:
            self.assertIn(text, plain)
        self.assertIn(
            AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_FROZEN.format(number=audit.number),
            plain,
        )
        self.assertNotIn(AUDIT_PROGRAM_PRINT_STATEMENTS_STATUS_CURRENT, plain)

    def test_06_grouping_and_canonical_order(self) -> None:
        _program, visit, _other = self._create_two_visits()
        context = audit_program_statements_export_context_service.build_for_visit(
            visit.id
        )
        plain = _odt_plain_text(_odt_content(self._print(visit.id)))
        process_order: list[str] = []
        area_order: list[str] = []
        for row in context.rows:
            if row.process_name not in process_order:
                process_order.append(row.process_name)
            if row.area_name not in area_order:
                area_order.append(row.area_name)
        self.assertTrue(process_order)
        self.assertTrue(area_order)
        position = 0
        for name in process_order:
            heading = f"{PROCESS_TERM_PROCESS}: {name}"
            found = plain.find(heading, position)
            self.assertGreaterEqual(found, 0, heading)
            position = found + 1
        position = 0
        for name in area_order:
            heading = f"{PROCESS_TERM_CRITERION}: {name}"
            found = plain.find(heading, position)
            self.assertGreaterEqual(found, 0, heading)
            position = found + 1
        position = 0
        for row in context.rows:
            found = plain.find(row.assertion_text, position)
            self.assertGreaterEqual(found, 0, row.assertion_text)
            position = found + 1

    def test_07_ratings_legend_and_note_space(self) -> None:
        _program, visit, _other = self._create_two_visits()
        content = _odt_content(self._print(visit.id))
        plain = _odt_plain_text(content)
        self.assertIn(AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_V, plain)
        self.assertIn(AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_VD, plain)
        self.assertIn(AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_N, plain)
        self.assertIn(AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_NP, plain)
        self.assertIn(AUDIT_PROGRAM_PRINT_STATEMENTS_RESULT_MARKS, plain)
        self.assertIn("Poznámka", plain)
        self.assertIn(PROCESS_TERM_QUESTION, plain)
        self.assertIn("Způsob ověření", plain)
        self.assertIn("Výsledek", plain)

    def test_08_and_09_no_file_dialog_temp_odt_open_once(self) -> None:
        program, visit, _other = self._create_two_visits()
        dialog = self._create_dialog(program.id)
        self._select_visit(dialog, visit.id)
        self.assertEqual(
            dialog._print_statements_btn.text(), AUDIT_PROGRAM_PRINT_STATEMENTS_BUTTON
        )
        self.assertTrue(dialog._print_statements_btn.isEnabled())
        workplace_item = dialog._plan_tree.topLevelItem(0)
        dialog._plan_tree.setCurrentItem(workplace_item)
        QApplication.processEvents()
        self.assertFalse(dialog._print_statements_btn.isEnabled())
        self._select_visit(dialog, visit.id)

        before_export = self._export_snapshot()
        temp_dir = Path(tempfile.gettempdir()).resolve()
        with patch.object(
            QFileDialog,
            "getSaveFileName",
            side_effect=AssertionError("QFileDialog se nesmí zobrazit"),
        ), patch(
            "moduly.audity.ui.audit_program_manager_dialog.open_local_file",
            return_value=True,
        ) as mock_open:
            dialog._print_statements_for_selection()

        mock_open.assert_called_once()
        opened = Path(mock_open.call_args.args[0]).resolve()
        self.assertTrue(opened.exists())
        self.assertEqual(opened.parent, temp_dir)
        self.assertIn("Auditni_tvrzeni_", opened.name)
        self.assertTrue(opened.name.startswith("manazer-bozp-"))
        self.assertEqual(opened.suffix.lower(), ".odt")
        with zipfile.ZipFile(opened) as zin:
            self.assertIn("content.xml", zin.namelist())
            self.assertEqual(
                zin.read("mimetype").decode("ascii"),
                "application/vnd.oasis.opendocument.text",
            )
        self.assertEqual(self._export_snapshot(), before_export)
        self.assertNotIn(str(opened), before_export)

    def test_10_create_error_does_not_open(self) -> None:
        program, visit, _other = self._create_two_visits()
        dialog = self._create_dialog(program.id)
        self._select_visit(dialog, visit.id)
        with patch.object(
            audit_program_statements_export_service,
            "generate_preview_for_visit",
            side_effect=RuntimeError("tisk selhal"),
        ), patch(
            "moduly.audity.ui.audit_program_manager_dialog.open_local_file",
            return_value=True,
        ) as mock_open, patch(
            "moduly.audity.ui.audit_program_manager_dialog.QMessageBox.warning",
        ):
            dialog._print_statements_for_selection()
        mock_open.assert_not_called()

    def test_11_open_error_keeps_temp_file_and_shows_path(self) -> None:
        program, visit, _other = self._create_two_visits()
        dialog = self._create_dialog(program.id)
        self._select_visit(dialog, visit.id)
        with patch(
            "moduly.audity.ui.audit_program_manager_dialog.open_local_file",
            return_value=False,
        ) as mock_open, patch(
            "moduly.audity.ui.audit_program_manager_dialog.QMessageBox.warning",
        ) as mock_warn:
            dialog._print_statements_for_selection()

        mock_open.assert_called_once()
        opened = Path(mock_open.call_args.args[0])
        self.assertTrue(opened.exists())
        message = mock_warn.call_args.args[2]
        self.assertIn(AUDIT_PROGRAM_PRINT_STATEMENTS_OPEN_FAILED, message)
        self.assertIn(str(opened), message)

    def test_12_empty_visit_shows_warning_and_creates_nothing(self) -> None:
        program = self._create_program()
        visit = self._add_visit(program.id, month=4)
        dialog = self._create_dialog(program.id)
        self._select_visit(dialog, visit.id)
        with self.assertRaises(AuditProgramStatementsEmptyError):
            self._print(visit.id)
        with patch(
            "moduly.audity.ui.audit_program_manager_dialog.open_local_file",
            return_value=True,
        ) as mock_open, patch(
            "moduly.audity.ui.audit_program_manager_dialog.QMessageBox.information",
        ) as mock_info:
            dialog._print_statements_for_selection()
        mock_open.assert_not_called()
        message = mock_info.call_args.args[2]
        self.assertIn(AUDIT_PROGRAM_PRINT_STATEMENTS_EMPTY, message)
        self.assertIsNone(audit_program_service.repository.get_visit(visit.id).audit_id)

    def test_13_plan_export_regression(self) -> None:
        program, _visit, _other = self._create_two_visits()
        target = Path(tempfile.mkdtemp()) / "plan.odt"
        path = audit_program_plan_export_service.generate_for_program(program.id, target)
        self.assertTrue(path.exists())
        plain = _odt_plain_text(_odt_content(path))
        self.assertIn("Plán interních auditů", plain)
        self.assertIn(self._operation_wp.name, plain)


if __name__ == "__main__":
    unittest.main()
