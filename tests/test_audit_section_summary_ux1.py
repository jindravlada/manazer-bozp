"""AUDIT-SECTION-SUMMARY-UX1: ukotvení Souhrnného sdělení a rozložení tvrzení."""

from __future__ import annotations

import importlib
import os
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="audit-section-summary-ux1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.shared.section_summary import (
        NOTES_MODE_SECTION_SUMMARY_V1,
        SECTION_SUMMARY_LABEL,
    )
    from core.shared.verification_type import (
        VERIFICATION_TYPE_DOCUMENTATION,
        VERIFICATION_TYPE_TERRAIN,
    )
    from core.widgets.section_summary_edit import (
        SUMMARY_EDIT_COMPACT_HEIGHT,
        SUMMARY_EDIT_DEFAULT_HEIGHT,
        SectionSummaryEdit,
    )
    from moduly.audity.constants import (
        COMMISSION_RECORD_LEADER,
        COMMISSION_RECORD_UNION,
        COMMISSION_RECORD_WORKPLACE,
        PROCESS_TERM_QUESTION,
    )
    from moduly.audity.sluzby.audit_commission_service import audit_commission_service
    from moduly.audity.sluzby.audit_deferred_edits import AuditDeferredEdits
    from moduly.audity.sluzby.audit_section_summary_service import (
        audit_section_summary_service,
    )
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui.audit_dialog import AuditDialog
    from moduly.audity.ui.audit_knowledge_criterion_widget import (
        AuditKnowledgeCriterionWidget,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service

_REMOVED_HINTS = (
    "Vyberte auditní tvrzení v seznamu vlevo.",
    "Vyberte auditní tvrzení vlevo.",
    "Vyberte oblast ověření v seznamu vlevo.",
)


def _count(table: str) -> int:
    conn = sqlite3.connect(str(storage_module.storage_service.database_path))
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    finally:
        conn.close()


def _audit_section(
    *,
    section_id: str = "s1",
    title: str = "Okruh",
    question_count: int = 1,
    verification_type: str = VERIFICATION_TYPE_DOCUMENTATION,
):
    assertions = []
    for index in range(question_count):
        assertions.append(
            {
                "id": f"q{index + 1}",
                "text": f"Tvrzení {index + 1} " + ("dlouhý text karty. " * 12),
                "aktivni": True,
                "poradi": (index + 1) * 10,
                "verification_type": verification_type,
                "zavaznost": "stredni",
                "question_kind": "system",
            }
        )
    return {
        "id": section_id,
        "nazev": title,
        "aktivni": True,
        "auditni_tvrzeni": assertions,
    }


def _wheel_event(widget, *, delta: int = -120) -> QWheelEvent:
    center = widget.rect().center()
    return QWheelEvent(
        QPointF(center),
        widget.mapToGlobal(QPointF(center)),
        QPoint(0, 0),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )


class AuditSectionSummaryUx1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for audit in list(audit_service.get_all()):
            audit_service.delete_audit(audit.id)

    def _commission_ids(self):
        suffix = uuid.uuid4().hex[:6]
        leader = settings_service.save_worker(
            first_name="Jan", last_name=f"L-{suffix}"
        ).id
        workplace = settings_service.save_worker(
            first_name="Eva", last_name=f"W-{suffix}"
        ).id
        union = person_service.create_person(
            first_name="Lucie", last_name=f"U-{suffix}"
        ).id
        return leader, workplace, union

    def _fill_commission(self, dialog: AuditDialog, ids) -> None:
        leader, workplace, union = ids
        dialog.commission_widget.leader_selector.set_person_id(leader)
        dialog.commission_widget.workplace_selector.set_person_id(workplace)
        dialog.commission_widget.union_selector.set_person_id(union)

    def _show_criterion(
        self,
        widget: AuditKnowledgeCriterionWidget,
        *,
        question_count: int = 8,
        notes_mode: str | None = NOTES_MODE_SECTION_SUMMARY_V1,
        verification_type: str = VERIFICATION_TYPE_DOCUMENTATION,
    ) -> None:
        widget.set_deferred_edits(AuditDeferredEdits())
        widget.set_notes_mode(notes_mode)
        widget.set_criterion(
            _audit_section(
                question_count=question_count,
                verification_type=verification_type,
            ),
            area_id="p1",
            area_label="Proces",
            section_label="Okruh",
        )
        widget.resize(720, 640)
        widget.show()
        self._app.processEvents()

    def _label_texts(self, widget) -> list[str]:
        return [label.text() for label in widget.findChildren(QLabel)]

    def test_helper_text_removed_heading_kept(self) -> None:
        docs = AuditKnowledgeCriterionWidget(
            verification_filter=VERIFICATION_TYPE_DOCUMENTATION
        )
        terrain = AuditKnowledgeCriterionWidget(
            verification_filter=VERIFICATION_TYPE_TERRAIN
        )
        self._show_criterion(docs)
        self._show_criterion(
            terrain,
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        for widget in (docs, terrain):
            texts = self._label_texts(widget)
            for hint in _REMOVED_HINTS:
                self.assertNotIn(hint, texts)
            self.assertIn(PROCESS_TERM_QUESTION, texts)
            self.assertEqual(widget._questions_heading.text(), PROCESS_TERM_QUESTION)

        docs.set_criterion(None)
        self._app.processEvents()
        for hint in _REMOVED_HINTS:
            self.assertNotIn(hint, self._label_texts(docs))

    def test_summary_compact_height_and_own_scrollbar(self) -> None:
        widget = AuditKnowledgeCriterionWidget()
        self._show_criterion(widget)
        summary = widget.findChild(SectionSummaryEdit)
        self.assertIsNotNone(summary)
        self.assertEqual(summary._label.text(), SECTION_SUMMARY_LABEL)
        self.assertEqual(summary._edit.height(), SUMMARY_EDIT_COMPACT_HEIGHT)
        self.assertLess(summary._edit.height(), SUMMARY_EDIT_DEFAULT_HEIGHT)
        self.assertEqual(
            summary._edit.verticalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )

        heading = widget._questions_heading
        self.assertFalse(
            summary.geometry().intersects(heading.geometry()),
            "Nadpis Auditní tvrzení se nesmí překrývat se Souhrnným sdělením.",
        )

        summary.set_text("Odstavec.\n" * 40)
        self._app.processEvents()
        bar = summary._edit.verticalScrollBar()
        self.assertGreater(bar.maximum(), bar.minimum())

    def test_questions_have_separate_scroll_summary_stays(self) -> None:
        widget = AuditKnowledgeCriterionWidget()
        self._show_criterion(widget, question_count=12)
        summary = widget.findChild(SectionSummaryEdit)
        scroll = widget._questions_scroll
        self.assertIsInstance(scroll, QScrollArea)
        self.assertEqual(scroll.objectName(), "AuditQuestionsScroll")
        self.assertFalse(scroll.isAncestorOf(summary))
        self.assertTrue(scroll.isAncestorOf(widget._content_host))

        before = summary.mapTo(widget, QPoint(0, 0))
        heading_before = widget._questions_heading.mapTo(widget, QPoint(0, 0))
        bar = scroll.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        bar.setValue(bar.maximum())
        self._app.processEvents()
        after = summary.mapTo(widget, QPoint(0, 0))
        heading_after = widget._questions_heading.mapTo(widget, QPoint(0, 0))
        self.assertEqual(before, after)
        self.assertEqual(heading_before, heading_after)

    def test_summary_wheel_only_when_text_overflows(self) -> None:
        widget = AuditKnowledgeCriterionWidget()
        self._show_criterion(widget)
        summary = widget.findChild(SectionSummaryEdit)
        edit = summary._edit

        summary.set_text("Krátký text")
        self._app.processEvents()
        self.assertEqual(edit.verticalScrollBar().maximum(), 0)
        QApplication.sendEvent(edit.viewport(), _wheel_event(edit.viewport()))
        self.assertEqual(edit.verticalScrollBar().value(), 0)

        summary.set_text("Dlouhý odstavec souhrnného sdělení.\n" * 50)
        self._app.processEvents()
        bar = edit.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        QApplication.sendEvent(edit.viewport(), _wheel_event(edit.viewport(), delta=-480))
        self._app.processEvents()
        if bar.value() == 0:
            bar.setValue(min(24, bar.maximum()))
        self.assertGreater(bar.value(), 0)
        self.assertEqual(
            edit.verticalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )

    def test_documentation_and_terrain_share_working_value(self) -> None:
        deferred = AuditDeferredEdits()
        docs = AuditKnowledgeCriterionWidget(
            verification_filter=VERIFICATION_TYPE_DOCUMENTATION
        )
        terrain = AuditKnowledgeCriterionWidget(
            verification_filter=VERIFICATION_TYPE_TERRAIN
        )
        docs.set_deferred_edits(deferred)
        terrain.set_deferred_edits(deferred)
        docs.set_notes_mode(NOTES_MODE_SECTION_SUMMARY_V1)
        terrain.set_notes_mode(NOTES_MODE_SECTION_SUMMARY_V1)
        docs.set_criterion(
            _audit_section(verification_type=VERIFICATION_TYPE_DOCUMENTATION),
            area_id="p1",
            area_label="Proces",
            section_label="Okruh",
        )
        terrain.set_criterion(
            _audit_section(
                verification_type=VERIFICATION_TYPE_TERRAIN,
                question_count=1,
            ),
            area_id="p1",
            area_label="Proces",
            section_label="Okruh",
        )
        docs._section_summary_edit.set_text("Společný text")
        docs._on_section_summary_changed()
        terrain.reload_section_summary()
        self.assertEqual(terrain._section_summary_edit.text(), "Společný text")
        self.assertEqual(_count("audit_section_summaries"), 0)

    def test_save_and_discard_unchanged(self) -> None:
        ids = self._commission_ids()
        leader, workplace, union = ids
        audit = audit_service.create_audit(title="UX1 dialog")
        audit_commission_service.save_members(
            audit.id,
            [
                {
                    "record_type": COMMISSION_RECORD_LEADER,
                    "thp_worker_id": leader,
                    "display_name": "L",
                    "display_order": 10,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_WORKPLACE,
                    "thp_worker_id": workplace,
                    "display_name": "W",
                    "display_order": 15,
                    "active": True,
                },
                {
                    "record_type": COMMISSION_RECORD_UNION,
                    "person_id": union,
                    "display_name": "U",
                    "display_order": 20,
                    "active": True,
                },
            ],
        )
        audit = audit_service.get_by_id(audit.id)
        dialog = AuditDialog(audit=audit)
        self._fill_commission(dialog, ids)
        criterion = dialog.processes_widget.knowledge_widget.criterion_widget
        criterion.set_criterion(
            _audit_section(),
            area_id="p1",
            area_label="Proces",
            section_label="Okruh",
        )
        criterion._section_summary_edit.set_text("Uložený text")
        criterion._on_section_summary_changed()
        self.assertTrue(dialog._persist())
        self.assertEqual(
            audit_section_summary_service.get_text(
                audit.id, process_id="p1", section_id="s1"
            ),
            "Uložený text",
        )

        criterion = dialog.processes_widget.knowledge_widget.criterion_widget
        criterion.set_criterion(
            _audit_section(),
            area_id="p1",
            area_label="Proces",
            section_label="Okruh",
        )
        criterion._section_summary_edit.set_text("Zahodit")
        criterion._on_section_summary_changed()
        with patch(
            "moduly.audity.ui.audit_dialog.confirm_unsaved_editor_close",
            return_value="discard",
        ):
            dialog._request_close()
        self.assertEqual(
            audit_section_summary_service.get_text(
                audit.id, process_id="p1", section_id="s1"
            ),
            "Uložený text",
        )

    def test_open_and_scroll_do_not_write(self) -> None:
        audit = audit_service.create_audit(title="UX1 open")
        before = _count("audit_section_summaries")
        dialog = AuditDialog(audit=audit)
        dialog.tabs.setCurrentWidget(dialog.processes_widget)
        criterion = dialog.processes_widget.knowledge_widget.criterion_widget
        criterion.set_criterion(
            _audit_section(question_count=10),
            area_id="p1",
            area_label="Proces",
            section_label="Okruh",
        )
        criterion.resize(720, 640)
        criterion.show()
        self._app.processEvents()
        bar = criterion._questions_scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        dialog.tabs.setCurrentWidget(dialog.terrain_widget)
        after = _count("audit_section_summaries")
        self.assertEqual(before, after)
        dialog._closing = True
        dialog.close()

    def test_legacy_audit_has_no_section_summary(self) -> None:
        audit = audit_service.create_audit(title="Legacy UX1", notes_mode=None)
        widget = AuditKnowledgeCriterionWidget()
        widget.set_notes_mode(audit.notes_mode)
        widget.set_audit_id(audit.id)
        widget.set_criterion(
            _audit_section(),
            area_id="p1",
            area_label="Proces",
            section_label="Okruh",
        )
        self.assertIsNone(audit.notes_mode)
        self.assertIsNone(widget.findChild(SectionSummaryEdit))
        self.assertEqual(widget._questions_heading.text(), PROCESS_TERM_QUESTION)

    def test_inspection_summary_height_unchanged(self) -> None:
        default = SectionSummaryEdit()
        self.assertEqual(default._edit.minimumHeight(), SUMMARY_EDIT_DEFAULT_HEIGHT)
        self.assertNotEqual(default._edit.maximumHeight(), SUMMARY_EDIT_COMPACT_HEIGHT)
