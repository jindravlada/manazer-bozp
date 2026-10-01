"""AUDIT-ASSERTION-PRINT-ORDER-2: tisk tvrzení má pořadí stromu provádění auditu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-assertion-print-order-2-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from sqlalchemy import select

    from core.database.session import get_session
    from core.shared.verification_type import VERIFICATION_TYPE_DOCUMENTATION
    from moduly.audity.constants import (
        AUDIT_METHODOLOGY_GENERATION_V2,
        AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
        AUDIT_QUESTION_KIND_EXTRAORDINARY,
        AUDIT_QUESTION_KIND_OPERATION,
        CONTROL_POINT_SEVERITY_NIZKA,
        CONTROL_POINT_SEVERITY_STREDNI,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
        EXTRAORDINARY_CATEGORY_PROCESS_ID,
        PROCESS_TERM_CRITERION,
        PROCESS_TERM_PROCESS,
    )
    from moduly.audity.modely.audit_question_snapshot import AuditQuestionSnapshot
    from moduly.audity.sluzby.audit_extraordinary_question_service import (
        audit_extraordinary_question_service,
    )
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_program_statements_export_context_service import (
        audit_program_statements_export_context_service,
    )
    from moduly.audity.sluzby.audit_question_kind import (
        interpret_question_kind,
        target_kind_for_workplace,
    )
    from moduly.audity.sluzby.audit_question_source_service import (
        audit_question_source_service,
        filter_knowledge_roots_by_question_kind,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.system_audit_workplace_service import (
        system_audit_workplace_service,
    )
    from tests.audit_v2a_test_support import prepare_v2_audit_create


PROCESS_A = "proc-a"
PROCESS_B = "proc-b"
SECTION_A1 = "sec-a1"
SECTION_A2 = "sec-a2"
SECTION_B1 = "sec-b1"
EXTRA_PROCESS = EXTRAORDINARY_CATEGORY_PROCESS_ID
EXTRA_SECTION = "ext-s"

# Pořadí stromu, ne SQL display_order, id.
EXPECTED_TEXTS = (
    "Alfa",
    "Tvrzení A1",
    "Žluťásek",
    "Tvrzení A2",
    "Tvrzení oblasti A2",
    "Tvrzení B1",
    "Mimořádné A",
    "Mimořádné B",
)
SQL_ORDER_TEXTS = (
    "Mimořádné A",
    "Žluťásek",
    "Tvrzení A1",
    "Alfa",
    "Tvrzení B1",
    "Tvrzení oblasti A2",
    "Mimořádné B",
    "Tvrzení A2",
)


def _runs(values):
    result = []
    for value in values:
        if not result or result[-1] != value:
            result.append(value)
    return result


def _snapshot_signature(audit_id: int) -> tuple:
    with get_session() as session:
        rows = list(
            session.scalars(
                select(AuditQuestionSnapshot)
                .where(AuditQuestionSnapshot.audit_id == int(audit_id))
                .order_by(AuditQuestionSnapshot.id)
            )
        )
        return tuple(
            (
                row.id,
                row.process_id,
                row.section_id,
                row.assertion_id,
                row.assertion_text,
                row.display_order,
                row.question_kind,
                row.verification_type,
                row.is_in_scope,
            )
            for row in rows
        )


def _sql_texts(audit_id: int) -> tuple[str, ...]:
    with get_session() as session:
        rows = list(
            session.scalars(
                select(AuditQuestionSnapshot)
                .where(
                    AuditQuestionSnapshot.audit_id == int(audit_id),
                    AuditQuestionSnapshot.is_in_scope.is_(True),
                )
                .order_by(
                    AuditQuestionSnapshot.display_order,
                    AuditQuestionSnapshot.id,
                )
            )
        )
    return tuple(row.assertion_text for row in rows)


def _ui_question_texts(roots) -> tuple[str, ...]:
    texts: list[str] = []
    for process in roots:
        for node in process.children:
            section = node.section if isinstance(node.section, dict) else None
            if section is None:
                continue
            for question in audit_knowledge_service.get_audit_questions(section):
                texts.append(str(question.get("text") or question.get("nazev") or ""))
    return tuple(texts)


class AuditAssertionPrintOrder2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        audit_knowledge_service.ensure_catalogs()

    def setUp(self) -> None:
        self._context = prepare_v2_audit_create(
            system_name="Pořadí tisku systém",
            operation_name="Pořadí tisku provoz",
        )
        self._system_wp, self._operation_wp = self._context.__enter__()

    def tearDown(self) -> None:
        self._context.__exit__(None, None, None)

    def _program_visit(self):
        program = audit_program_service.create_program(
            name="Program pořadí tvrzení",
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
        visit = audit_program_service.add_visit(
            program.id,
            workplace_id=self._operation_wp.id,
            planned_year=2026,
            planned_month=4,
        )
        tree = audit_knowledge_service.get_knowledge_tree(ensure=True)
        node = tree[0]
        audit_program_service.add_visit_process(
            visit.id,
            process_id=node.process_id,
            process_name=node.process_label or node.label,
        )
        return visit, tree

    def _add_snapshot_row(
        self,
        session,
        *,
        audit_id: int,
        process_id: str,
        process_name: str,
        section_id: str,
        section_name: str,
        assertion_id: str,
        assertion_text: str,
        display_order: int,
        question_kind: str,
    ) -> None:
        session.add(
            AuditQuestionSnapshot(
                audit_id=audit_id,
                process_id=process_id,
                process_name=process_name,
                section_id=section_id,
                section_name=section_name,
                assertion_id=assertion_id,
                assertion_text=assertion_text,
                verification_type=VERIFICATION_TYPE_DOCUMENTATION,
                severity=CONTROL_POINT_SEVERITY_NIZKA,
                question_kind=question_kind,
                display_order=display_order,
                is_in_scope=True,
                created_at=datetime.now(),
            )
        )

    def test_prepared_export_follows_execution_tree_not_sql_order(self) -> None:
        visit, _tree = self._program_visit()
        audit = audit_program_service.create_audit_from_visit(visit.id)
        audit_service.repository.update_fields(
            audit.id,
            methodology_source=AUDIT_METHODOLOGY_SOURCE_SNAPSHOT,
            methodology_generation=AUDIT_METHODOLOGY_GENERATION_V2,
            questions_frozen_at=datetime(2026, 4, 1, 8, 0, 0),
        )
        with get_session() as session:
            # Vložení schválně v pořadí, které SQL display_order, id promíchá.
            rows = (
                (PROCESS_A, "Proces A", SECTION_A1, "Oblast A1", "z", "Žluťásek", 10, AUDIT_QUESTION_KIND_OPERATION),
                (PROCESS_A, "Proces A", SECTION_A1, "Oblast A1", "a1", "Tvrzení A1", 10, AUDIT_QUESTION_KIND_OPERATION),
                (PROCESS_A, "Proces A", SECTION_A1, "Oblast A1", "alfa", "Alfa", 10, AUDIT_QUESTION_KIND_OPERATION),
                (PROCESS_B, "Proces B", SECTION_B1, "Oblast B1", "b1", "Tvrzení B1", 20, AUDIT_QUESTION_KIND_OPERATION),
                (PROCESS_A, "Proces A", SECTION_A2, "Oblast A2", "a2s", "Tvrzení oblasti A2", 20, AUDIT_QUESTION_KIND_OPERATION),
                (PROCESS_A, "Proces A", SECTION_A1, "Oblast A1", "a2", "Tvrzení A2", 30, AUDIT_QUESTION_KIND_OPERATION),
                (EXTRA_PROCESS, "Mimořádná ověření", EXTRA_SECTION, "Mimořádná ověření", "ext-b", "Mimořádné B", 20, AUDIT_QUESTION_KIND_EXTRAORDINARY),
                (EXTRA_PROCESS, "Mimořádná ověření", EXTRA_SECTION, "Mimořádná ověření", "ext-a", "Mimořádné A", 5, AUDIT_QUESTION_KIND_EXTRAORDINARY),
            )
            for item in rows:
                self._add_snapshot_row(
                    session,
                    audit_id=audit.id,
                    process_id=item[0],
                    process_name=item[1],
                    section_id=item[2],
                    section_name=item[3],
                    assertion_id=item[4],
                    assertion_text=item[5],
                    display_order=item[6],
                    question_kind=item[7],
                )
            session.commit()

        before = _snapshot_signature(audit.id)
        sql_texts = _sql_texts(audit.id)
        self.assertEqual(sql_texts, SQL_ORDER_TEXTS)
        self.assertNotEqual(sql_texts, EXPECTED_TEXTS)

        source = audit_question_source_service.resolve_for_audit(audit.id)
        standard = filter_knowledge_roots_by_question_kind(
            source.roots, extraordinary_only=False
        )
        extraordinary = filter_knowledge_roots_by_question_kind(
            source.roots, extraordinary_only=True
        )
        ui_texts = _ui_question_texts(standard) + _ui_question_texts(extraordinary)
        self.assertEqual(ui_texts, EXPECTED_TEXTS)

        context = audit_program_statements_export_context_service.build_for_visit(
            visit.id
        )
        export_texts = tuple(row.assertion_text for row in context.rows)
        self.assertEqual(export_texts, EXPECTED_TEXTS)
        self.assertNotEqual(export_texts, sql_texts)
        self.assertEqual(_snapshot_signature(audit.id), before)

        self.assertEqual(
            _runs(row.process_id for row in context.rows),
            [PROCESS_A, PROCESS_B, EXTRA_PROCESS],
        )
        process_a_areas = [
            row.area_name for row in context.rows if row.process_id == PROCESS_A
        ]
        self.assertEqual(_runs(process_a_areas), ["Oblast A1", "Oblast A2"])
        process_b_areas = [
            row.area_name for row in context.rows if row.process_id == PROCESS_B
        ]
        self.assertEqual(process_b_areas, ["Oblast B1"])
        extra_texts = [
            row.assertion_text
            for row in context.rows
            if row.process_id == EXTRA_PROCESS
        ]
        self.assertEqual(extra_texts, ["Mimořádné A", "Mimořádné B"])
        self.assertGreater(
            export_texts.index("Mimořádné A"),
            export_texts.index("Tvrzení B1"),
        )

        plain = str(context.placeholder_values()["tvrzeni_obsah"])
        self.assertEqual(plain.count(f"{PROCESS_TERM_PROCESS}: Proces A"), 1)
        self.assertEqual(plain.count(f"{PROCESS_TERM_PROCESS}: Proces B"), 1)
        self.assertEqual(plain.count(f"{PROCESS_TERM_CRITERION}: Oblast A1"), 1)
        self.assertEqual(plain.count(f"{PROCESS_TERM_CRITERION}: Oblast A2"), 1)
        self.assertLess(
            plain.index(f"{PROCESS_TERM_CRITERION}: Oblast A1"),
            plain.index("Tvrzení A2"),
        )
        self.assertLess(
            plain.index("Tvrzení A2"),
            plain.index(f"{PROCESS_TERM_CRITERION}: Oblast A2"),
        )
        self.assertLess(
            plain.index(f"{PROCESS_TERM_CRITERION}: Oblast A2"),
            plain.index(f"{PROCESS_TERM_PROCESS}: Proces B"),
        )

    def test_unprepared_export_keeps_live_methodology_order(self) -> None:
        visit, tree = self._program_visit()
        planned = {tree[0].process_id}
        if len(tree) > 1:
            planned.add(tree[1].process_id)
            audit_program_service.add_visit_process(
                visit.id,
                process_id=tree[1].process_id,
                process_name=tree[1].process_label or tree[1].label,
            )
        audit_extraordinary_question_service.create_question(
            question_text="Mimořádné živé",
            severity=CONTROL_POINT_SEVERITY_STREDNI,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            workplace_ids=[self._operation_wp.id],
        )
        target_kind = target_kind_for_workplace(
            workplace_id=self._operation_wp.id,
            system_workplace_id=system_audit_workplace_service.require_system_audit_workplace_id(),
        )
        expected = _live_standard_keys(tree, planned, target_kind)
        self.assertGreaterEqual(len(expected), 2)
        expected.append(("extra", "Mimořádné živé"))

        live = audit_program_statements_export_context_service.build_for_visit(visit.id)
        self.assertEqual(
            [(row.process_id, row.assertion_text) for row in live.rows[:-1]],
            expected[:-1],
        )
        self.assertEqual(live.rows[-1].assertion_text, "Mimořádné živé")
        self.assertEqual(live.rows[-1].process_id, EXTRAORDINARY_CATEGORY_PROCESS_ID)

        audit = audit_program_service.create_audit_from_visit(visit.id)
        unfrozen = audit_program_statements_export_context_service.build_for_visit(
            visit.id
        )
        self.assertEqual(
            [(row.process_id, row.assertion_text) for row in unfrozen.rows],
            [(row.process_id, row.assertion_text) for row in live.rows],
        )
        self.assertIsNone(audit.questions_frozen_at)


def _live_standard_keys(tree, planned: set[str], target_kind: str) -> list[tuple[str, str]]:
    """Průchod živé metodiky stejně jako náhled před přípravou, bez druhého řazení."""
    found: list[tuple[str, str]] = []

    def walk(process_id: str, nodes) -> None:
        for node in nodes:
            section = node.section if isinstance(node.section, dict) else None
            if isinstance(section, dict):
                for raw in audit_knowledge_service.get_audit_questions(section):
                    kind = interpret_question_kind(raw.get("question_kind"))
                    if kind != target_kind:
                        continue
                    text = str(raw.get("text") or raw.get("nazev") or "").strip()
                    if text:
                        found.append((process_id, text))
            if node.children:
                walk(process_id, node.children)

    for process in tree:
        process_id = str(process.process_id or "").strip()
        if process_id not in planned:
            continue
        walk(process_id, process.children)
    return found


if __name__ == "__main__":
    unittest.main()
