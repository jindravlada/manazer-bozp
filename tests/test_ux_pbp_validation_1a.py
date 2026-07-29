"""UX-PBP-VALIDATION-1a: schválení formulací a plynulé zpracování výsledků."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-pbp-validation-1a-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.modely.pbp_validation_approval import (
        PBP_VALIDATION_RULE_UNSUITABLE_EMPLOYEE,
        PbpValidationApproval,
    )
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_existing_measure_service import (
        hazard_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.pbp_validation_approval_service import (
        approved_text_hash,
        pbp_validation_approval_service,
    )
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
        PravidloBezpecnePrace,
        pravidla_bezpecne_prace_service,
    )
    from moduly.rizeni_rizik.ui.pbp_validation_results_dialog import (
        ALL_OK_MESSAGE,
        APPROVE_UNSAVED_PROMPT,
        COL_AREA,
        COL_STATUS,
        ROLE_MEASURE_ID,
        STATUS_APPROVED,
        STATUS_UNSUITABLE,
        PbpValidationResultsDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class UxPbpValidation1aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(PbpValidationApproval))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.group = ensure_exposed_group("UX-PBP-V1a skupina")
        self.person = person_service.create_person(
            first_name="UX",
            last_name="PbpValidation1a",
        )
        self.operation = settings_service.save_workplace(
            name="UX-PBP-V1a provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="UX-PBP-V1a pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )

    def _create_measure(self, description: str, *, event_name: str):
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            responsible_person_id=self.person.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name=f"Položka {event_name}",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name=event_name,
        )
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description=description,
        )
        return measure, event

    def _warnings_for_group(self):
        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        return pravidla_bezpecne_prace_service.quality_warnings(rules)

    def test_approve_button_visible_when_item_selected(self) -> None:
        self._create_measure("Zajistit přístup", event_name="Událost A")
        warnings = self._warnings_for_group()
        dialog = PbpValidationResultsDialog(warnings=warnings)
        self.assertTrue(dialog.approve_btn.isVisibleTo(dialog))
        self.assertTrue(dialog.approve_btn.isEnabled())
        dialog.table.clearSelection()
        dialog._current_measure_id = None
        dialog._update_action_buttons()
        self.assertFalse(dialog.approve_btn.isEnabled())

    def test_approve_without_text_change_persists_and_removes(self) -> None:
        measure, _ = self._create_measure(
            "Zajistit bezpečný přístup",
            event_name="Událost B",
        )
        warnings = self._warnings_for_group()
        self.assertEqual(len(warnings), 1)
        dialog = PbpValidationResultsDialog(warnings=warnings)
        original = dialog.current_row().original_text
        with patch.object(QMessageBox, "information"):
            self.assertTrue(dialog.approve_as_ok())
        self.assertEqual(dialog.issue_count, 0)
        reloaded = hazard_existing_measure_service.get_by_id(measure.id)
        self.assertEqual(reloaded.description, original.rstrip(".") or original)
        self.assertTrue(
            pbp_validation_approval_service.is_rule_approved(
                PravidloBezpecnePrace(
                    measure_id=measure.id,
                    text=warnings[0].text,
                    unsuitable_for_employee=True,
                )
            )
        )

    def test_auto_select_next_after_approve(self) -> None:
        m1, _ = self._create_measure("Zajistit přístup A", event_name="E1")
        m2, _ = self._create_measure("Provést kontrolu B", event_name="E2")
        warnings = self._warnings_for_group()
        self.assertEqual(len(warnings), 2)
        dialog = PbpValidationResultsDialog(warnings=warnings)
        first_id = dialog.current_row().rule.measure_id
        self.assertTrue(dialog.approve_as_ok())
        self.assertEqual(dialog.issue_count, 1)
        self.assertNotEqual(dialog.current_row().rule.measure_id, first_id)
        self.assertIn(dialog.current_row().rule.measure_id, {m1.id, m2.id})

    def test_recheck_suppresses_valid_approval(self) -> None:
        measure, _ = self._create_measure(
            "Zajistit přístup",
            event_name="E3",
        )
        warnings = self._warnings_for_group()
        rule = warnings[0]
        pbp_validation_approval_service.approve_rule(rule)

        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        filtered = pravidla_bezpecne_prace_service.quality_warnings(rules)
        self.assertEqual(filtered, [])
        with_approved = pravidla_bezpecne_prace_service.quality_warnings(
            rules,
            include_approved=True,
        )
        self.assertEqual(len(with_approved), 1)
        self.assertEqual(with_approved[0].measure_id, measure.id)

    def test_changed_text_invalidates_approval(self) -> None:
        measure, _ = self._create_measure(
            "Zajistit přístup",
            event_name="E4",
        )
        warnings = self._warnings_for_group()
        pbp_validation_approval_service.approve_rule(warnings[0])

        reloaded = hazard_existing_measure_service.get_by_id(measure.id)
        assessment = hazard_risk_assessment_service.get_by_id(
            reloaded.hazard_risk_assessment_id
        )
        event = hazard_event_service.get_by_id(assessment.hazard_event_id)
        item = hazard_inventory_item_service.get_by_id(event.inventory_item_id)
        hazard_existing_measure_service.update_measure(
            measure.id,
            hazard_identification_id=item.hazard_identification_id,
            hazard_risk_assessment_id=reloaded.hazard_risk_assessment_id,
            description="Provést jinou kontrolu přístupu",
        )
        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        filtered = pravidla_bezpecne_prace_service.quality_warnings(rules)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].measure_id, measure.id)

    def test_other_validation_rule_not_suppressed(self) -> None:
        measure, _ = self._create_measure(
            "Zajistit přístup",
            event_name="E5",
        )
        warnings = self._warnings_for_group()
        rule = warnings[0]
        pbp_validation_approval_service.approve_rule(rule)
        self.assertTrue(pbp_validation_approval_service.is_rule_approved(rule))
        self.assertFalse(
            pbp_validation_approval_service.is_rule_approved(
                rule,
                validation_rule_code="other_independent_rule",
            )
        )
        approval = (
            pbp_validation_approval_service.repository.get_for_measure_rule(
                measure.id,
                PBP_VALIDATION_RULE_UNSUITABLE_EMPLOYEE,
            )
        )
        self.assertIsNotNone(approval)
        self.assertEqual(
            approval.approved_text_hash,
            approved_text_hash(rule.text),
        )

    def test_approval_bound_to_measure_id(self) -> None:
        m1, _ = self._create_measure("Zajistit přístup A", event_name="E6a")
        m2, _ = self._create_measure("Zajistit přístup B", event_name="E6b")
        warnings = self._warnings_for_group()
        by_id = {w.measure_id: w for w in warnings}
        pbp_validation_approval_service.approve_rule(by_id[m1.id])
        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        filtered = pravidla_bezpecne_prace_service.quality_warnings(rules)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].measure_id, m2.id)

    def test_ctrl_shift_enter_approves(self) -> None:
        from PySide6.QtGui import QShortcut

        self._create_measure("Zajistit přístup", event_name="E7")
        warnings = self._warnings_for_group()
        dialog = PbpValidationResultsDialog(warnings=warnings)
        approve_shortcuts = [
            child
            for child in dialog.findChildren(QShortcut)
            if child.key().matches(QKeySequence("Ctrl+Shift+Enter"))
            == QKeySequence.SequenceMatch.ExactMatch
            or child.key().matches(QKeySequence("Ctrl+Shift+Return"))
            == QKeySequence.SequenceMatch.ExactMatch
        ]
        self.assertTrue(approve_shortcuts)
        with patch.object(QMessageBox, "information"):
            approve_shortcuts[0].activated.emit()
        self.assertEqual(dialog.issue_count, 0)

    def test_approve_with_unsaved_edit_prompts(self) -> None:
        self._create_measure("Zajistit přístup", event_name="E8")
        warnings = self._warnings_for_group()
        dialog = PbpValidationResultsDialog(warnings=warnings)
        dialog.new_edit.setPlainText("Úplně jiné znění, které nebylo použito.")
        self.assertTrue(dialog.has_unsaved_changes())

        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.No,
        ) as question:
            self.assertFalse(dialog.approve_as_ok())
        self.assertIn(APPROVE_UNSAVED_PROMPT, question.call_args.args[2])
        self.assertEqual(dialog.issue_count, 1)

        with (
            patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch.object(QMessageBox, "information"),
        ):
            self.assertTrue(dialog.approve_as_ok())
        self.assertEqual(dialog.issue_count, 0)

    def test_table_sorting_keeps_measure_binding(self) -> None:
        m_a, _ = self._create_measure("Zajistit přístup Z", event_name="Zebra")
        m_b, _ = self._create_measure("Provést kontrolu A", event_name="Alfa")
        warnings = self._warnings_for_group()
        dialog = PbpValidationResultsDialog(warnings=warnings)
        self.assertEqual(dialog.table.rowCount(), 2)

        dialog.table.sortItems(COL_AREA, Qt.SortOrder.AscendingOrder)
        first_area = dialog.table.item(0, COL_AREA).text()
        second_area = dialog.table.item(1, COL_AREA).text()
        self.assertLessEqual(first_area, second_area)

        dialog.table.selectRow(0)
        selected_id = dialog.current_row().rule.measure_id
        item_id = int(dialog.table.item(0, COL_STATUS).data(ROLE_MEASURE_ID))
        self.assertEqual(selected_id, item_id)
        self.assertIn(selected_id, {m_a.id, m_b.id})

        dialog.new_edit.setPlainText("Dodržuj bezpečný postup.")
        with patch.object(QMessageBox, "information"):
            self.assertTrue(dialog.apply_change())
        updated = hazard_existing_measure_service.get_by_id(selected_id)
        self.assertEqual(updated.description, "Dodržuj bezpečný postup.")

    def test_last_item_shows_processed_message(self) -> None:
        self._create_measure("Zajistit přístup", event_name="E9")
        warnings = self._warnings_for_group()
        dialog = PbpValidationResultsDialog(warnings=warnings)
        with patch.object(QMessageBox, "information") as info:
            self.assertTrue(dialog.approve_as_ok())
        info.assert_called_once()
        self.assertIn(ALL_OK_MESSAGE, info.call_args.args[2])
        self.assertEqual(dialog.issue_count, 0)

    def test_revoke_approval_restores_problem(self) -> None:
        measure, _ = self._create_measure(
            "Zajistit přístup",
            event_name="E10",
        )
        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

        def regenerate(*, include_approved: bool = False):
            refreshed = pravidla_bezpecne_prace_service.generate(
                endangered_group_id=self.group.id,
                operation_id=self.operation.id,
                workplace_id=self.workplace.id,
            )
            return pravidla_bezpecne_prace_service.quality_warnings(
                refreshed,
                include_approved=include_approved,
            )

        dialog = PbpValidationResultsDialog(
            warnings=pravidla_bezpecne_prace_service.quality_warnings(rules),
            regenerate_warnings=regenerate,
        )
        with patch.object(QMessageBox, "information"):
            self.assertTrue(dialog.approve_as_ok())
        self.assertEqual(dialog.issue_count, 0)

        dialog.show_approved_cb.setChecked(True)
        self.assertEqual(dialog.issue_count, 1)
        self.assertEqual(dialog.table.item(0, COL_STATUS).text(), STATUS_APPROVED)
        self.assertTrue(dialog.revoke_btn.isEnabled())
        self.assertTrue(dialog.revoke_approval())
        self.assertEqual(dialog.table.item(0, COL_STATUS).text(), STATUS_UNSUITABLE)
        self.assertFalse(
            pbp_validation_approval_service.is_rule_approved(
                PravidloBezpecnePrace(
                    measure_id=measure.id,
                    text=dialog.current_row().original_text,
                    unsuitable_for_employee=True,
                )
            )
        )

    def test_migration_creates_approvals_table(self) -> None:
        from core.database.session import engine
        from sqlalchemy import inspect

        inspector = inspect(engine)
        self.assertIn("pbp_validation_approvals", inspector.get_table_names())
        columns = {col["name"] for col in inspector.get_columns("pbp_validation_approvals")}
        self.assertTrue(
            {"measure_id", "validation_rule_code", "approved_text_hash"}.issubset(
                columns
            )
        )


if __name__ == "__main__":
    unittest.main()
