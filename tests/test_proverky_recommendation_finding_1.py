"""PROVERKY-RECOMMENDATION-FINDING-1: zjištění u „Vyhovuje s doporučením“."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_TMP = Path(tempfile.mkdtemp(prefix="proverky-recommendation-finding-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QLabel, QPushButton

    from core.shared.constants import (
        CONTROL_RESULT_NEKONTROLOVANO,
        CONTROL_RESULT_NELZE_POSOUDIT,
        CONTROL_RESULT_NEVYHOVUJE,
        CONTROL_RESULT_VYHOVUJE,
        CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        ENTITY_AUDITY,
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_TYPE_ZJISTENI,
    )
    from core.shared.control_result_display import allows_create_finding, allows_finding
    from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_task_service import finding_task_service
    from core.widgets.control_result_selector import ControlResultSelectorWidget
    from moduly.audity.constants import FINDING_CREATE_FROM_CONTROL_POINT_LABEL as AUDIT_CREATE_LABEL
    from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.ui.audit_knowledge_criterion_widget import AuditKnowledgeCriterionWidget
    from moduly.proverky.constants import (
        FINDING_CREATE_FROM_CONTROL_POINT_LABEL,
        FINDING_CREATED_LABEL,
        FINDING_REQUIRES_RESULT_MESSAGE,
        KNOWLEDGE_EDITOR_DEFAULT_AREA_ID,
        KNOWLEDGE_EDITOR_DEFAULT_SECTION_ID,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.sluzby.inspection_deferred_edits import InspectionDeferredEdits
    from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service
    from moduly.proverky.ui.bozp_inspection_dialog import BozpInspectionDialog
    from moduly.proverky.ui.bozp_inspection_findings_widget import BozpInspectionFindingsWidget
    from moduly.proverky.ui.bozp_knowledge_section_widget import BozpKnowledgeSectionWidget


_AREA_ID = KNOWLEDGE_EDITOR_DEFAULT_AREA_ID
_SECTION_ID = KNOWLEDGE_EDITOR_DEFAULT_SECTION_ID
_CONTROL_POINT_ID = "umisteni"


class ProverkyRecommendationFinding1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)
        proverky_knowledge_service.ensure_catalogs()

    def _area_and_section(self):
        area = proverky_knowledge_service.get_area_by_id(_AREA_ID)
        assert area is not None
        section = proverky_knowledge_service.get_section(_AREA_ID, _SECTION_ID)
        assert section is not None
        return area, section

    def _control_point(self, section: dict) -> dict:
        for item in proverky_knowledge_service.get_active_items(section.get("kontrolni_body")):
            if str(item.get("id") or "") == _CONTROL_POINT_ID:
                return item
        raise AssertionError("Kontrolní bod umisteni nebyl nalezen.")

    def _context(self, area, section: dict) -> ControlPointContext:
        control_point = self._control_point(section)
        return ControlPointContext(
            area_id=area.id,
            area_label=area.nazev,
            section_id=str(section.get("id") or ""),
            section_label=str(section.get("nazev") or ""),
            control_point_id=str(control_point.get("id") or ""),
            control_point_label=str(control_point.get("nazev") or ""),
        )

    def _open_section_with_result(self, inspection, result: str, *, deferred=None):
        area, section = self._area_and_section()
        context = self._context(area, section)
        if deferred is None:
            control_result_service.set_result(
                ENTITY_PROVERKY,
                inspection.id,
                context,
                result=result,
            )
        else:
            deferred.set_control_result(
                ENTITY_PROVERKY,
                inspection.id,
                context,
                result=result,
                note="",
                shared_experience=False,
            )

        widget = BozpKnowledgeSectionWidget()
        if deferred is not None:
            widget.set_deferred_edits(deferred)
        widget.set_inspection_id(inspection.id)
        widget.set_section(
            section,
            area_id=area.id,
            area_label=area.nazev,
            section_label=str(section.get("nazev") or ""),
        )
        return widget, context, self._control_point(section)

    def _create_buttons(self, widget):
        return [
            button
            for button in widget.findChildren(QPushButton)
            if button.text() == FINDING_CREATE_FROM_CONTROL_POINT_LABEL
        ]

    def _audit_create_buttons(self, widget):
        return [
            button
            for button in widget.findChildren(QPushButton)
            if button.text() == AUDIT_CREATE_LABEL
        ]

    def _selector_for(self, widget, control_point_id: str) -> ControlResultSelectorWidget:
        for selector in widget.findChildren(ControlResultSelectorWidget):
            context = selector._context
            if context is not None and context.control_point_id == control_point_id:
                return selector
        raise AssertionError(f"Selektor výsledku pro {control_point_id} nebyl nalezen.")

    def _finding_dialog_data(self, context: ControlPointContext, *, description: str) -> dict:
        return {
            "finding_type": FINDING_TYPE_ZJISTENI,
            "reference_label": context.control_point_label,
            "description": description,
            "recommended_action": "Doplnit označení lékárničky.",
            "responsible_person_id": None,
            "responsible_person_name": "",
            "due_date": None,
            "status": FINDING_STATUS_OTEVRENE,
            "resolution_note": "",
        }

    def _mock_finding_dialog(self, mock_dialog_cls, context: ControlPointContext, *, accepted: bool, description: str):
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = accepted
        mock_dialog.get_data.return_value = self._finding_dialog_data(
            context,
            description=description,
        )
        mock_dialog_cls.return_value = mock_dialog
        return mock_dialog

    def test_shared_predicate_allows_recommendation_without_changing_allows_finding(self) -> None:
        self.assertTrue(allows_finding(CONTROL_RESULT_NEVYHOVUJE))
        self.assertFalse(allows_finding(CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM))
        self.assertTrue(allows_create_finding(CONTROL_RESULT_NEVYHOVUJE))
        self.assertTrue(allows_create_finding(CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM))
        for result in (
            CONTROL_RESULT_VYHOVUJE,
            CONTROL_RESULT_NEKONTROLOVANO,
            CONTROL_RESULT_NELZE_POSOUDIT,
        ):
            self.assertFalse(allows_finding(result))
            self.assertFalse(allows_create_finding(result))

    def test_recommendation_result_shows_create_finding_button(self) -> None:
        inspection = bozp_inspection_service.create_inspection()
        widget, _context, _control_point = self._open_section_with_result(
            inspection,
            CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )

        self.assertEqual(len(self._create_buttons(widget)), 1)
        self.assertEqual(finding_service.get_for_entity(ENTITY_PROVERKY, inspection.id), [])

    def test_changing_result_to_recommendation_does_not_auto_create_finding(self) -> None:
        inspection = bozp_inspection_service.create_inspection()
        widget, context, _control_point = self._open_section_with_result(
            inspection,
            CONTROL_RESULT_NEKONTROLOVANO,
        )

        self.assertEqual(len(self._create_buttons(widget)), 0)
        selector = self._selector_for(widget, context.control_point_id)
        selector._radios[CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM].click()

        self.assertEqual(
            control_result_service.current_result(ENTITY_PROVERKY, inspection.id, context),
            CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        self.assertEqual(finding_service.get_for_entity(ENTITY_PROVERKY, inspection.id), [])
        self.assertEqual(len(self._create_buttons(widget)), 1)

    @patch("moduly.proverky.ui.bozp_knowledge_section_widget.FindingDialog")
    def test_cancel_finding_dialog_creates_nothing(self, mock_dialog_cls) -> None:
        inspection = bozp_inspection_service.create_inspection()
        widget, context, control_point = self._open_section_with_result(
            inspection,
            CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        self._mock_finding_dialog(
            mock_dialog_cls,
            context,
            accepted=False,
            description="Nemá se uložit.",
        )

        widget._create_finding(control_point)

        mock_dialog_cls.assert_called_once()
        self.assertEqual(finding_service.get_for_entity(ENTITY_PROVERKY, inspection.id), [])
        self.assertEqual(len(self._create_buttons(widget)), 1)

    @patch("moduly.proverky.ui.bozp_knowledge_section_widget.FindingDialog")
    def test_confirmed_finding_binds_to_inspection_and_question(self, mock_dialog_cls) -> None:
        inspection = bozp_inspection_service.create_inspection()
        widget, context, control_point = self._open_section_with_result(
            inspection,
            CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        self._mock_finding_dialog(
            mock_dialog_cls,
            context,
            accepted=True,
            description="Doporučení k lékárničce.",
        )

        self._create_buttons(widget)[0].click()

        findings = finding_service.get_for_entity(ENTITY_PROVERKY, inspection.id)
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.entity_type, ENTITY_PROVERKY)
        self.assertEqual(finding.entity_id, inspection.id)
        self.assertEqual(finding.source_area_label, context.area_label)
        self.assertEqual(finding.source_section_label, context.section_label)
        self.assertEqual(finding.source_control_point_id, context.control_point_id)
        self.assertEqual(finding.source_control_point_label, context.control_point_label)
        self.assertEqual(finding.description, "Doporučení k lékárničce.")
        linked = bozp_inspection_service.finding_for_control_point(
            inspection.id,
            area_label=context.area_label,
            section_label=context.section_label,
            control_point_id=context.control_point_id,
        )
        self.assertEqual(linked.id, finding.id)

    @patch("moduly.proverky.ui.bozp_knowledge_section_widget.FindingDialog")
    def test_confirmed_finding_appears_on_findings_tab(self, mock_dialog_cls) -> None:
        inspection = bozp_inspection_service.create_inspection()
        widget, context, control_point = self._open_section_with_result(
            inspection,
            CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        self._mock_finding_dialog(
            mock_dialog_cls,
            context,
            accepted=True,
            description="Viditelné v přehledu zjištění.",
        )
        widget._create_finding(control_point)

        findings_widget = BozpInspectionFindingsWidget()
        findings_widget.set_inspection_id(inspection.id)
        self.assertEqual(findings_widget.table.rowCount(), 1)
        self.assertEqual(
            findings_widget.table.item(0, 7).text(),
            "Viditelné v přehledu zjištění.",
        )
        self.assertEqual(findings_widget.table.item(0, 5).text(), context.control_point_label)

    @patch("moduly.proverky.ui.bozp_knowledge_section_widget.FindingDialog")
    def test_dialog_working_copy_shows_finding_and_discard_does_not_persist(
        self, mock_dialog_cls
    ) -> None:
        inspection = bozp_inspection_service.create_inspection()
        deferred = InspectionDeferredEdits()
        widget, context, control_point = self._open_section_with_result(
            inspection,
            CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            deferred=deferred,
        )
        self._mock_finding_dialog(
            mock_dialog_cls,
            context,
            accepted=True,
            description="Jen v pracovní kopii.",
        )
        widget._create_finding(control_point)

        findings_widget = BozpInspectionFindingsWidget()
        findings_widget.set_deferred_edits(deferred)
        findings_widget.set_inspection_id(inspection.id)
        self.assertEqual(findings_widget.table.rowCount(), 1)
        self.assertEqual(finding_service.get_for_entity(ENTITY_PROVERKY, inspection.id), [])

        staged = deferred.finding_for_control_point(
            inspection.id,
            process_label=context.area_label,
            criterion_label=context.section_label,
            question_id=context.control_point_id,
        )
        self.assertIsNotNone(staged)

        deferred.clear()
        findings_widget.refresh()
        self.assertEqual(findings_widget.table.rowCount(), 0)
        self.assertEqual(finding_service.get_for_entity(ENTITY_PROVERKY, inspection.id), [])

    @patch("moduly.proverky.ui.bozp_knowledge_section_widget.FindingDialog")
    def test_dialog_flush_persists_finding_binding(self, mock_dialog_cls) -> None:
        inspection = bozp_inspection_service.create_inspection()
        deferred = InspectionDeferredEdits()
        widget, context, control_point = self._open_section_with_result(
            inspection,
            CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
            deferred=deferred,
        )
        self._mock_finding_dialog(
            mock_dialog_cls,
            context,
            accepted=True,
            description="Po uložení v databázi.",
        )
        widget._create_finding(control_point)
        deferred.flush()

        findings = finding_service.get_for_entity(ENTITY_PROVERKY, inspection.id)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].source_control_point_id, context.control_point_id)
        self.assertEqual(findings[0].description, "Po uložení v databázi.")

    @patch("moduly.proverky.ui.bozp_knowledge_section_widget.FindingDialog")
    def test_noncompliance_still_allows_create_finding(self, mock_dialog_cls) -> None:
        inspection = bozp_inspection_service.create_inspection()
        widget, context, control_point = self._open_section_with_result(
            inspection,
            CONTROL_RESULT_NEVYHOVUJE,
        )
        self.assertEqual(len(self._create_buttons(widget)), 1)
        self._mock_finding_dialog(
            mock_dialog_cls,
            context,
            accepted=True,
            description="Neshoda u lékárničky.",
        )
        widget._create_finding(control_point)

        findings = finding_service.get_for_entity(ENTITY_PROVERKY, inspection.id)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].source_control_point_id, context.control_point_id)

    def test_other_results_do_not_allow_create_finding(self) -> None:
        inspection = bozp_inspection_service.create_inspection()
        _area, section = self._area_and_section()
        control_point = self._control_point(section)
        for result in (
            CONTROL_RESULT_VYHOVUJE,
            CONTROL_RESULT_NEKONTROLOVANO,
            CONTROL_RESULT_NELZE_POSOUDIT,
        ):
            with self.subTest(result=result):
                widget, context, _cp = self._open_section_with_result(inspection, result)
                self.assertEqual(len(self._create_buttons(widget)), 0)
                with patch(
                    "moduly.proverky.ui.bozp_knowledge_section_widget.QMessageBox.information"
                ) as mock_info:
                    widget._create_finding(control_point)
                mock_info.assert_called_once()
                self.assertEqual(mock_info.call_args.args[2], FINDING_REQUIRES_RESULT_MESSAGE)
                self.assertEqual(finding_service.get_for_entity(ENTITY_PROVERKY, inspection.id), [])
                self.assertEqual(
                    control_result_service.current_result(
                        ENTITY_PROVERKY, inspection.id, context
                    ),
                    result,
                )

    @patch("moduly.proverky.ui.bozp_knowledge_section_widget.FindingDialog")
    def test_changing_result_does_not_delete_existing_finding(self, mock_dialog_cls) -> None:
        inspection = bozp_inspection_service.create_inspection()
        widget, context, control_point = self._open_section_with_result(
            inspection,
            CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        self._mock_finding_dialog(
            mock_dialog_cls,
            context,
            accepted=True,
            description="Zjištění musí zůstat.",
        )
        widget._create_finding(control_point)
        finding_id = finding_service.get_for_entity(ENTITY_PROVERKY, inspection.id)[0].id

        selector = self._selector_for(widget, context.control_point_id)
        selector._radios[CONTROL_RESULT_VYHOVUJE].click()

        remaining = finding_service.get_for_entity(ENTITY_PROVERKY, inspection.id)
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].id, finding_id)
        self.assertEqual(remaining[0].source_control_point_id, context.control_point_id)
        self.assertIn(
            FINDING_CREATED_LABEL,
            [label.text() for label in widget.findChildren(QLabel)],
        )
        self.assertEqual(len(self._create_buttons(widget)), 0)
        self.assertEqual(
            control_result_service.current_result(ENTITY_PROVERKY, inspection.id, context),
            CONTROL_RESULT_VYHOVUJE,
        )

    @patch("moduly.proverky.ui.bozp_knowledge_section_widget.QMessageBox.information")
    @patch("moduly.proverky.ui.bozp_knowledge_section_widget.FindingDialog")
    def test_duplicate_click_does_not_create_second_finding(
        self, mock_dialog_cls, mock_info
    ) -> None:
        inspection = bozp_inspection_service.create_inspection()
        widget, context, control_point = self._open_section_with_result(
            inspection,
            CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        self._mock_finding_dialog(
            mock_dialog_cls,
            context,
            accepted=True,
            description="První zjištění.",
        )
        widget._create_finding(control_point)
        self.assertEqual(len(finding_service.get_for_entity(ENTITY_PROVERKY, inspection.id)), 1)

        mock_dialog_cls.reset_mock()
        existing_dialog = MagicMock()
        existing_dialog.exec.return_value = False
        mock_dialog_cls.return_value = existing_dialog
        widget._create_finding(control_point)

        self.assertEqual(len(finding_service.get_for_entity(ENTITY_PROVERKY, inspection.id)), 1)
        mock_info.assert_called()
        existing_dialog.exec.assert_called_once()

    @patch("moduly.proverky.ui.bozp_knowledge_section_widget.FindingDialog")
    def test_task_can_be_created_from_recommendation_finding(self, mock_dialog_cls) -> None:
        inspection = bozp_inspection_service.create_inspection()
        widget, context, control_point = self._open_section_with_result(
            inspection,
            CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        self._mock_finding_dialog(
            mock_dialog_cls,
            context,
            accepted=True,
            description="Zjištění pro úkol.",
        )
        widget._create_finding(control_point)
        finding = finding_service.get_for_entity(ENTITY_PROVERKY, inspection.id)[0]

        self.assertEqual(finding_task_service.get_task_action(finding.id), "create")
        task = finding_task_service.create_task_from_finding(finding.id)
        reloaded = finding_service.get_by_id(finding.id)
        assert reloaded is not None
        self.assertEqual(reloaded.task_id, task.id)
        self.assertEqual(finding_task_service.get_task_action(reloaded.id), "open")

        findings_widget = BozpInspectionFindingsWidget()
        findings_widget.set_inspection_id(inspection.id)
        from PySide6.QtCore import QItemSelectionModel

        index = findings_widget.table.model().index(0, 0)
        findings_widget.table.selectionModel().select(
            index,
            QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
        )
        findings_widget.task_actions.update_state()
        self.assertEqual(findings_widget.task_actions._action, "open")

    def test_audit_regression_create_finding_gate_unchanged(self) -> None:
        audit = audit_service.create_audit(title="Regrese auditu")
        criterion = audit_knowledge_service.get_criterion(
            "urazy_mimo_udalosti",
            "evidence_hlaseni_urazu",
        )
        assert criterion is not None
        questions = audit_knowledge_service.get_audit_questions(criterion)
        question = questions[0]
        context = ControlPointContext(
            area_id="urazy_mimo_udalosti",
            area_label="Řízení pracovních úrazů a mimořádných událostí",
            section_id="evidence_hlaseni_urazu",
            section_label="Evidence a hlášení pracovních úrazů",
            control_point_id=question["id"],
            control_point_label=question.get("nazev") or question.get("text") or "",
        )
        expected = {
            CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM: 1,
            CONTROL_RESULT_NEVYHOVUJE: 1,
            CONTROL_RESULT_VYHOVUJE: 0,
            CONTROL_RESULT_NEKONTROLOVANO: 0,
            CONTROL_RESULT_NELZE_POSOUDIT: 0,
        }
        for result, button_count in expected.items():
            with self.subTest(result=result):
                control_result_service.set_result(
                    ENTITY_AUDITY,
                    audit.id,
                    context,
                    result=result,
                )
                widget = AuditKnowledgeCriterionWidget()
                widget.set_audit_id(audit.id)
                widget.set_criterion(
                    criterion,
                    area_id="urazy_mimo_udalosti",
                    area_label="Řízení pracovních úrazů a mimořádných událostí",
                    section_label="Evidence a hlášení pracovních úrazů",
                )
                self.assertEqual(len(self._audit_create_buttons(widget)), button_count)
                self.assertEqual(finding_service.get_for_entity(ENTITY_AUDITY, audit.id), [])

    @patch("moduly.audity.ui.audit_knowledge_criterion_widget.FindingDialog")
    def test_audit_regression_recommendation_still_creates_finding(
        self, mock_dialog_cls
    ) -> None:
        audit = audit_service.create_audit(title="Regrese PKZ")
        criterion = audit_knowledge_service.get_criterion(
            "urazy_mimo_udalosti",
            "evidence_hlaseni_urazu",
        )
        assert criterion is not None
        question = audit_knowledge_service.get_audit_questions(criterion)[0]
        context = ControlPointContext(
            area_id="urazy_mimo_udalosti",
            area_label="Řízení pracovních úrazů a mimořádných událostí",
            section_id="evidence_hlaseni_urazu",
            section_label="Evidence a hlášení pracovních úrazů",
            control_point_id=question["id"],
            control_point_label=question.get("nazev") or question.get("text") or "",
        )
        control_result_service.set_result(
            ENTITY_AUDITY,
            audit.id,
            context,
            result=CONTROL_RESULT_VYHOVUJE_S_DOPORUCENIM,
        )
        widget = AuditKnowledgeCriterionWidget()
        widget.set_audit_id(audit.id)
        widget.set_criterion(
            criterion,
            area_id="urazy_mimo_udalosti",
            area_label="Řízení pracovních úrazů a mimořádných událostí",
            section_label="Evidence a hlášení pracovních úrazů",
        )
        mock_dialog = MagicMock()
        mock_dialog.exec.return_value = True
        mock_dialog.get_data.return_value = {
            "finding_type": FINDING_TYPE_ZJISTENI,
            "reference_label": context.control_point_label,
            "description": "Auditní doporučení.",
            "recommended_action": "",
            "responsible_person_id": None,
            "responsible_person_name": "",
            "due_date": None,
            "status": FINDING_STATUS_OTEVRENE,
            "resolution_note": "",
        }
        mock_dialog_cls.return_value = mock_dialog
        widget._create_finding(question)

        findings = finding_service.get_for_entity(ENTITY_AUDITY, audit.id)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].source_control_point_id, context.control_point_id)

    def test_dialog_wires_existing_deferred_edits_not_new_controller(self) -> None:
        inspection = bozp_inspection_service.create_inspection()
        dialog = BozpInspectionDialog(inspection=inspection)
        self.assertIsInstance(dialog._deferred, InspectionDeferredEdits)
        self.assertIs(
            dialog.areas_widget.knowledge_widget.section_widget._deferred_edits,
            dialog._deferred,
        )
        self.assertIs(dialog.findings_widget._deferred_edits, dialog._deferred)


if __name__ == "__main__":
    unittest.main()
