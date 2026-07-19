"""PBP-5b: porovnání vydání Pravidel bezpečné práce."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="pbp-5b-"))
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
        RISK_SEVERITY_CRITICAL,
        RISK_SEVERITY_MINOR,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.modely.pravidla_bezpecne_prace_edition import (
        PravidlaBezpecnePraceEdition,
        PravidlaBezpecnePraceEditionRule,
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
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_comparison import (
        compare_rules_to_edition,
    )
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_edition_service import (
        pravidla_bezpecne_prace_edition_service,
    )
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
        PravidloBezpecnePrace,
        PravidloBezpecnePraceSource,
        pravidla_bezpecne_prace_service,
        severity_rank,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class PravidlaBezpecnePracePhasePbp5bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(PravidlaBezpecnePraceEditionRule))
            session.execute(delete(PravidlaBezpecnePraceEdition))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.group = ensure_exposed_group("PBP5b skupina")
        self.other_group = ensure_exposed_group("PBP5b jiná skupina")
        self.person = person_service.create_person(first_name="PBP5b", last_name="Tester")
        self.operation = settings_service.save_workplace(
            name="PBP5b provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="PBP5b pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )

    def _seed(
        self,
        *,
        description: str = "Používej helmu",
        severity: str = RISK_SEVERITY_MODERATE,
        group_id: int | None = None,
        event_name: str = "Událost",
    ) -> tuple[HazardExistingMeasure, int]:
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
            exposed_group_id=group_id or self.group.id,
            severity=severity,
        )
        measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description=description,
        )
        return measure, identification.id

    def _current_rules(self) -> list[PravidloBezpecnePrace]:
        return pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

    def _record_current(self, *, issued_at: datetime | None = None):
        return pravidla_bezpecne_prace_edition_service.record_edition(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=self._current_rules(),
            issued_at=issued_at or datetime.now(),
        )

    def test_first_edition_has_no_change_sections(self) -> None:
        self._seed()
        comparison = pravidla_bezpecne_prace_edition_service.compare_to_latest(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=self._current_rules(),
        )
        self.assertTrue(comparison.is_first_edition)
        self.assertFalse(comparison.has_changes)
        self.assertEqual(comparison.new_rules, [])
        self.assertEqual(comparison.changed_rules, [])
        self.assertEqual(comparison.removed_rules, [])
        self.assertEqual(len(comparison.unchanged_rules), 1)

    def test_identical_edition_has_no_changes(self) -> None:
        self._seed()
        self._record_current(issued_at=datetime.now() - timedelta(hours=1))
        comparison = pravidla_bezpecne_prace_edition_service.compare_to_latest(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=self._current_rules(),
        )
        self.assertFalse(comparison.is_first_edition)
        self.assertFalse(comparison.has_changes)
        self.assertEqual(comparison.new_rules, [])
        self.assertEqual(comparison.changed_rules, [])
        self.assertEqual(comparison.removed_rules, [])
        self.assertEqual(len(comparison.unchanged_rules), 1)

    def test_new_rule(self) -> None:
        self._seed(description="Používej helmu", event_name="Starý")
        self._record_current(issued_at=datetime.now() - timedelta(hours=1))
        self._seed(description="Používej brýle", event_name="Nový")

        comparison = pravidla_bezpecne_prace_edition_service.compare_to_latest(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=self._current_rules(),
        )
        self.assertTrue(comparison.has_changes)
        self.assertEqual(len(comparison.new_rules), 1)
        self.assertIn("brýle", comparison.new_rules[0].text.casefold())
        self.assertEqual(comparison.removed_rules, [])
        self.assertEqual(comparison.changed_rules, [])
        self.assertEqual(len(comparison.unchanged_rules), 1)

    def test_removed_rule(self) -> None:
        keep, _ = self._seed(description="Používej helmu", event_name="Keep")
        gone, _ = self._seed(description="Používej brýle", event_name="Gone")
        self._record_current(issued_at=datetime.now() - timedelta(hours=1))
        hazard_existing_measure_service.deactivate_measure(gone.id)

        comparison = pravidla_bezpecne_prace_edition_service.compare_to_latest(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=self._current_rules(),
        )
        self.assertTrue(comparison.has_changes)
        self.assertEqual(len(comparison.removed_rules), 1)
        self.assertIn("brýle", comparison.removed_rules[0].display_text.casefold())
        self.assertEqual(comparison.new_rules, [])
        self.assertEqual(comparison.changed_rules, [])
        self.assertEqual(len(comparison.unchanged_rules), 1)
        self.assertEqual(comparison.unchanged_rules[0].measure_id, keep.id)

    def test_changed_text_same_measure_id(self) -> None:
        measure, identification_id = self._seed(
            description="Používej helmu",
            event_name="Změna",
        )
        self._record_current(issued_at=datetime.now() - timedelta(hours=1))

        hazard_existing_measure_service.update_measure(
            measure.id,
            hazard_identification_id=identification_id,
            hazard_risk_assessment_id=measure.hazard_risk_assessment_id,
            description="Používej ochrannou přilbu",
        )

        comparison = pravidla_bezpecne_prace_edition_service.compare_to_latest(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=self._current_rules(),
        )
        self.assertTrue(comparison.has_changes)
        self.assertEqual(len(comparison.changed_rules), 1)
        changed = comparison.changed_rules[0]
        self.assertEqual(changed.previous_text, "Používej helmu.")
        self.assertEqual(changed.current_text, "Používej ochrannou přilbu.")
        self.assertEqual(changed.measure_id, measure.id)
        self.assertEqual(comparison.new_rules, [])
        self.assertEqual(comparison.removed_rules, [])

    def test_similar_texts_without_shared_measure_are_new_and_removed(self) -> None:
        previous_rule = PravidloBezpecnePrace(
            measure_id=101,
            text="Používej helmu.",
            severity=RISK_SEVERITY_MODERATE,
            severity_rank=severity_rank(RISK_SEVERITY_MODERATE),
            sources=(
                PravidloBezpecnePraceSource(
                    measure_id=101,
                    severity=RISK_SEVERITY_MODERATE,
                ),
            ),
        )
        previous = pravidla_bezpecne_prace_edition_service.record_edition(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=[previous_rule],
            issued_at=datetime.now() - timedelta(hours=1),
        )
        current = [
            PravidloBezpecnePrace(
                measure_id=202,
                text="Používej přilbu.",
                severity=RISK_SEVERITY_MODERATE,
                severity_rank=severity_rank(RISK_SEVERITY_MODERATE),
                sources=(
                    PravidloBezpecnePraceSource(
                        measure_id=202,
                        severity=RISK_SEVERITY_MODERATE,
                    ),
                ),
            )
        ]
        comparison = compare_rules_to_edition(current, previous)
        self.assertEqual(len(comparison.new_rules), 1)
        self.assertEqual(len(comparison.removed_rules), 1)
        self.assertEqual(comparison.changed_rules, [])
        self.assertEqual(comparison.unchanged_rules, [])

    def test_severity_only_change_is_not_rule_change(self) -> None:
        self._seed(description="Používej helmu", severity=RISK_SEVERITY_MINOR)
        self._record_current(issued_at=datetime.now() - timedelta(hours=1))

        # Ruční snapshot s vyšší závažností, stejný text / measure_id.
        rules = self._current_rules()
        bumped = [
            PravidloBezpecnePrace(
                measure_id=rules[0].measure_id,
                text=rules[0].text,
                source_hazard_id=rules[0].source_hazard_id,
                source_event_id=rules[0].source_event_id,
                unsuitable_for_employee=rules[0].unsuitable_for_employee,
                severity=RISK_SEVERITY_CRITICAL,
                severity_rank=severity_rank(RISK_SEVERITY_CRITICAL),
                sources=rules[0].sources,
            )
        ]
        comparison = pravidla_bezpecne_prace_edition_service.compare_to_latest(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=bumped,
        )
        self.assertFalse(comparison.has_changes)
        self.assertEqual(len(comparison.unchanged_rules), 1)
        self.assertEqual(comparison.changed_rules, [])

    def test_compares_only_same_scope_latest(self) -> None:
        self._seed(description="Používej helmu", event_name="Scope A")
        own = self._record_current(issued_at=datetime.now() - timedelta(hours=2))

        # Novější vydání jiné skupiny nesmí ovlivnit porovnání.
        other_rules = [
            PravidloBezpecnePrace(
                measure_id=999,
                text="Úplně jiné pravidlo.",
                severity=RISK_SEVERITY_MODERATE,
                severity_rank=severity_rank(RISK_SEVERITY_MODERATE),
                sources=(PravidloBezpecnePraceSource(measure_id=999),),
            )
        ]
        pravidla_bezpecne_prace_edition_service.record_edition(
            endangered_group_id=self.other_group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=other_rules,
            issued_at=datetime.now() - timedelta(minutes=1),
        )

        comparison = pravidla_bezpecne_prace_edition_service.compare_to_latest(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=self._current_rules(),
        )
        self.assertEqual(comparison.previous_edition_id, own.id)
        self.assertFalse(comparison.has_changes)

    def test_export_stores_comparison_before_recording(self) -> None:
        self._seed()
        path = pravidla_bezpecne_prace_service.export_document(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertIsNotNone(path)
        comparison = pravidla_bezpecne_prace_service.last_comparison
        self.assertIsNotNone(comparison)
        assert comparison is not None
        self.assertTrue(comparison.is_first_edition)
        self.assertFalse(comparison.has_changes)


if __name__ == "__main__":
    unittest.main()
