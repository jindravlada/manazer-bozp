"""PBP-4: normalizace a kontrola kvality pravidel."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="pbp-4-"))
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
        is_unsuitable_employee_rule,
        normalize_rule_text,
        pravidla_bezpecne_prace_service,
    )
    from moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog import (
        PravidlaBezpecnePraceDialog,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class NormalizeRuleTextTestCase(unittest.TestCase):
    def test_collapse_spaces_and_empty_lines(self) -> None:
        self.assertEqual(
            normalize_rule_text("  Používej   helmu  \n\n  vždy  "),
            "Používej helmu.\nvždy.",
        )

    def test_preserves_line_breaks_as_separate_rules(self) -> None:
        self.assertEqual(
            normalize_rule_text(
                "Řádně sledovat provoz.\n"
                "Bezodkladně zastavit.\n"
                "Dodržovat radiovou komunikaci."
            ),
            "Řádně sledovat provoz.\n"
            "Bezodkladně zastavit.\n"
            "Dodržovat radiovou komunikaci.",
        )

    def test_unify_trailing_period(self) -> None:
        self.assertEqual(normalize_rule_text("Používej helmu"), "Používej helmu.")
        self.assertEqual(normalize_rule_text("Používej helmu."), "Používej helmu.")
        self.assertEqual(normalize_rule_text("Používej helmu..."), "Používej helmu.")
        self.assertEqual(normalize_rule_text("Používej helmu!"), "Používej helmu.")

    def test_empty_after_normalization(self) -> None:
        self.assertEqual(normalize_rule_text("  \n\n  "), "")
        self.assertEqual(normalize_rule_text("..."), "")


class UnsuitableEmployeeRuleTestCase(unittest.TestCase):
    def test_detects_unsuitable_prefixes(self) -> None:
        for text in (
            "Zajistit bezpečný přístup.",
            "Provést kontrolu před zahájením.",
            "Kontrolovat stav OOPP.",
            "Zabezpečit pracoviště.",
            "Ověřit funkčnost zařízení.",
            "Dodržování bezpečnostních předpisů.",
        ):
            with self.subTest(text=text):
                self.assertTrue(is_unsuitable_employee_rule(text))

    def test_accepts_employee_oriented_rules(self) -> None:
        for text in (
            "Používej ochrannou přilbu.",
            "Vstupuj jen se souhlasem vedoucího.",
            "Dodržuj bezpečnostní předpisy.",
            "Zákaz vstupu pod břemeno.",
        ):
            with self.subTest(text=text):
                self.assertFalse(is_unsuitable_employee_rule(text))


class PravidlaBezpecnePracePhasePbp4TestCase(unittest.TestCase):
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

        self.group = ensure_exposed_group("PBP4 skupina")
        self.person = person_service.create_person(first_name="PBP4", last_name="Tester")
        self.operation = settings_service.save_workplace(
            name="PBP4 provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="PBP4 pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )

    def _create_measure(self, description: str, *, event_name: str) -> None:
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
        hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description=description,
        )

    def test_dedupe_uses_normalized_text(self) -> None:
        self._create_measure("  Používej   helmu  ", event_name="Norm A")
        self._create_measure("používej helmu...", event_name="Norm B")
        self._create_measure("Jiná ochrana", event_name="Norm C")

        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

        texts = [rule.text for rule in rules]
        self.assertEqual(len(texts), 2)
        self.assertIn("Používej helmu.", texts)
        self.assertIn("Jiná ochrana.", texts)

    def test_unsuitable_rules_are_included_and_flagged(self) -> None:
        self._create_measure("Používej přilbu", event_name="OK")
        self._create_measure("Zajistit bezpečný přístup", event_name="Bad")

        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

        self.assertEqual(len(rules), 2)
        warnings = pravidla_bezpecne_prace_service.quality_warnings(rules)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0].text, "Zajistit bezpečný přístup.")
        self.assertTrue(warnings[0].unsuitable_for_employee)
        self.assertTrue(any(not rule.unsuitable_for_employee for rule in rules))

    def test_dialog_shows_quality_warning(self) -> None:
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
                return_value=Path("/tmp/pbp4.odt"),
            ),
            patch(
                "moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog.PbpValidationResultsDialog"
            ) as results_cls,
        ):
            dialog._generate()

        results_cls.assert_called_once()
        warnings = results_cls.call_args.kwargs["warnings"]
        self.assertEqual(len(warnings), 2)
        results_cls.return_value.exec.assert_called_once()

    def test_dialog_skips_quality_warning_when_all_ok(self) -> None:
        dialog = PravidlaBezpecnePraceDialog()
        dialog.set_selected_group_ids([self.group.id])
        dialog.operation.setCurrentIndex(dialog.operation.findData(self.operation.id))

        sample = [
            PravidloBezpecnePrace(measure_id=1, text="Používej přilbu."),
        ]
        with (
            patch(
                "moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog.pravidla_bezpecne_prace_service.generate",
                return_value=sample,
            ),
            patch(
                "moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog.pravidla_bezpecne_prace_service.open_document",
                return_value=Path("/tmp/pbp4-ok.odt"),
            ),
            patch(
                "moduly.rizeni_rizik.ui.pravidla_bezpecne_prace_dialog.PbpValidationResultsDialog"
            ) as results_cls,
        ):
            dialog._generate()

        results_cls.assert_not_called()


if __name__ == "__main__":
    unittest.main()
