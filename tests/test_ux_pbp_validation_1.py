"""UX-PBP-VALIDATION-1: výsledkový dialog kontroly pravidel bezpečné práce."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="ux-pbp-validation-1-"))
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
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
        PravidloBezpecnePrace,
        UNSUITABLE_EMPLOYEE_RULE_REASON,
        pravidla_bezpecne_prace_service,
    )
    from moduly.rizeni_rizik.ui.pbp_validation_results_dialog import (
        ALL_OK_MESSAGE,
        PbpValidationResultsDialog,
    )
    from moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog import (
        PravidlaBezpecnePraceDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class UxPbpValidation1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.group = ensure_exposed_group("UX-PBP-V1 skupina")
        self.person = person_service.create_person(
            first_name="UX",
            last_name="PbpValidation",
        )
        self.operation = settings_service.save_workplace(
            name="UX-PBP-V1 provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="UX-PBP-V1 pracoviště",
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

    def test_criteria_dialog_opens_results_dialog(self) -> None:
        dialog = PravidlaBezpecnePraceDialog()
        dialog.set_selected_group_ids([self.group.id])
        dialog.operation.setCurrentIndex(dialog.operation.findData(self.operation.id))

        sample = [
            PravidloBezpecnePrace(
                measure_id=1,
                text="Používej přilbu.",
                unsuitable_for_employee=False,
            ),
            PravidloBezpecnePrace(
                measure_id=2,
                text="Zajistit přístup.",
                unsuitable_for_employee=True,
            ),
            PravidloBezpecnePrace(
                measure_id=3,
                text="Provést kontrolu.",
                unsuitable_for_employee=True,
            ),
        ]

        with (
            patch(
                "moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog.pravidla_bezpecne_prace_service.generate",
                return_value=sample,
            ),
            patch(
                "moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog.pravidla_bezpecne_prace_service.open_document",
                return_value=Path("/tmp/ux-pbp-v1.odt"),
            ),
            patch(
                "moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog.PbpValidationResultsDialog"
            ) as results_cls,
        ):
            instance = results_cls.return_value
            dialog._generate()

        results_cls.assert_called_once()
        kwargs = results_cls.call_args.kwargs
        self.assertEqual(len(kwargs["warnings"]), 2)
        instance.exec.assert_called_once()

    def test_results_dialog_shows_count_reason_and_area(self) -> None:
        measure, event = self._create_measure(
            "Zajistit bezpečný přístup",
            event_name="Pád z výšky",
        )
        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        warnings = pravidla_bezpecne_prace_service.quality_warnings(rules)
        self.assertEqual(len(warnings), 1)

        dialog = PbpValidationResultsDialog(warnings=warnings)
        self.assertEqual(dialog.issue_count, 1)
        self.assertEqual(dialog.table.rowCount(), 1)
        self.assertEqual(dialog.table.item(0, 1).text(), event.name)
        self.assertEqual(dialog.table.item(0, 2).text(), UNSUITABLE_EMPLOYEE_RULE_REASON)
        self.assertIn("Zajistit bezpečný přístup", dialog.table.item(0, 3).text())
        self.assertEqual(dialog.current_row().rule.measure_id, measure.id)

    def test_edit_apply_removes_fixed_item_and_updates_measure(self) -> None:
        measure, _event = self._create_measure(
            "Zajistit bezpečný přístup",
            event_name="Událost A",
        )
        self._create_measure("Provést kontrolu OOPP", event_name="Událost B")
        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        warnings = pravidla_bezpecne_prace_service.quality_warnings(rules)
        self.assertEqual(len(warnings), 2)

        dialog = PbpValidationResultsDialog(warnings=warnings)
        dialog.table.selectRow(0)
        first_id = dialog.current_row().rule.measure_id
        dialog.new_edit.setPlainText("Používej bezpečný přístup.")
        self.assertTrue(dialog.has_unsaved_changes())

        with patch.object(QMessageBox, "information") as info:
            self.assertTrue(dialog.apply_change())

        reloaded = hazard_existing_measure_service.get_by_id(first_id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.description, "Používej bezpečný přístup.")
        self.assertEqual(dialog.issue_count, 1)
        self.assertNotEqual(dialog.current_row().rule.measure_id, first_id)
        info.assert_not_called()

        dialog.table.selectRow(0)
        dialog.new_edit.setPlainText("Dodržuj kontrolu OOPP.")
        with patch.object(QMessageBox, "information") as info_ok:
            self.assertTrue(dialog.apply_change())
        info_ok.assert_called_once()
        self.assertIn(ALL_OK_MESSAGE, info_ok.call_args.args[2])
        self.assertEqual(dialog.issue_count, 0)

    def test_unsaved_changes_prompt_on_close(self) -> None:
        measure, event = self._create_measure(
            "Zajistit přístup",
            event_name="Událost C",
        )
        rules = [
            PravidloBezpecnePrace(
                measure_id=measure.id,
                text="Zajistit přístup.",
                unsuitable_for_employee=True,
                source_event_id=event.id,
                sources=(),
            )
        ]
        dialog = PbpValidationResultsDialog(warnings=rules)
        dialog.show()
        dialog.new_edit.setPlainText("Používej přístup.")
        self.assertTrue(dialog.has_unsaved_changes())

        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.No,
        ) as question:
            dialog.close()
        question.assert_called_once()
        self.assertTrue(dialog.isVisible())

        with patch.object(
            QMessageBox,
            "question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            dialog._request_close()
        from PySide6.QtWidgets import QDialog

        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)

    def test_ctrl_enter_applies_change(self) -> None:
        measure, event = self._create_measure(
            "Kontrolovat stav OOPP",
            event_name="Událost D",
        )
        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        warning = next(rule for rule in rules if rule.measure_id == measure.id)

        dialog = PbpValidationResultsDialog(warnings=[warning])
        dialog.new_edit.setPlainText("Kontroluj stav OOPP.")
        with patch.object(QMessageBox, "information"):
            dialog.apply_change()
        updated = hazard_existing_measure_service.get_by_id(measure.id)
        self.assertEqual(updated.description, "Kontroluj stav OOPP.")
        self.assertEqual(dialog.issue_count, 0)

    def test_recheck_uses_callback_not_partial_list(self) -> None:
        calls: list[int] = []

        def regenerate():
            calls.append(1)
            return []

        warning = PravidloBezpecnePrace(
            measure_id=99,
            text="Zajistit přístup.",
            unsuitable_for_employee=True,
        )
        dialog = PbpValidationResultsDialog(
            warnings=[warning],
            regenerate_warnings=regenerate,
        )
        with patch.object(QMessageBox, "information"):
            dialog.recheck_all()
        self.assertEqual(calls, [1])
        self.assertEqual(dialog.issue_count, 0)


if __name__ == "__main__":
    unittest.main()
