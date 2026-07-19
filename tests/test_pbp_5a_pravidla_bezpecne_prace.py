"""PBP-5a: evidence vydání Pravidel bezpečné práce."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="pbp-5a-"))
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
        WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
    )
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_CRITICAL,
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
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_edition_service import (
        pravidla_bezpecne_prace_edition_service,
    )
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
        pravidla_bezpecne_prace_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class PravidlaBezpecnePracePhasePbp5aTestCase(unittest.TestCase):
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

        self.group_a = ensure_exposed_group("PBP5a skupina A")
        self.group_b = ensure_exposed_group("PBP5a skupina B")
        self.person = person_service.create_person(first_name="PBP5a", last_name="Tester")
        self.operation = settings_service.save_workplace(
            name="PBP5a provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="PBP5a pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.part = settings_service.save_workplace(
            name="PBP5a část",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=self.workplace.id,
        )

    def _seed_rule(
        self,
        *,
        group_id: int,
        workplace_id: int | None = None,
        workplace_part_id: int | None = None,
        description: str = "Používej ochrannou přilbu",
        severity: str = RISK_SEVERITY_MODERATE,
        event_name: str = "Událost",
    ) -> None:
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=workplace_id or self.workplace.id,
            workplace_part_id=workplace_part_id,
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
            exposed_group_id=group_id,
            severity=severity,
        )
        hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description=description,
        )

    def test_first_edition_has_no_predecessor(self) -> None:
        previous = pravidla_bezpecne_prace_edition_service.get_latest_edition(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertIsNone(previous)

        self._seed_rule(group_id=self.group_a.id, workplace_id=self.workplace.id)
        path = pravidla_bezpecne_prace_service.export_document(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertIsNotNone(path)

        latest = pravidla_bezpecne_prace_edition_service.get_latest_edition(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest.endangered_group_id, self.group_a.id)
        self.assertEqual(latest.operation_id, self.operation.id)
        self.assertEqual(latest.workplace_id, self.workplace.id)
        self.assertIsNone(latest.workplace_part_id)

    def test_finds_latest_edition_for_same_scope(self) -> None:
        self._seed_rule(group_id=self.group_a.id, workplace_id=self.workplace.id)
        first = pravidla_bezpecne_prace_edition_service.record_edition(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=pravidla_bezpecne_prace_service.generate(
                endangered_group_id=self.group_a.id,
                operation_id=self.operation.id,
                workplace_id=self.workplace.id,
            ),
            issued_at=datetime.now() - timedelta(hours=2),
        )
        second = pravidla_bezpecne_prace_edition_service.record_edition(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=pravidla_bezpecne_prace_service.generate(
                endangered_group_id=self.group_a.id,
                operation_id=self.operation.id,
                workplace_id=self.workplace.id,
            ),
            issued_at=datetime.now() - timedelta(minutes=5),
        )

        latest = pravidla_bezpecne_prace_edition_service.get_latest_edition(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest.id, second.id)
        self.assertNotEqual(latest.id, first.id)

    def test_separates_endangered_groups(self) -> None:
        self._seed_rule(
            group_id=self.group_a.id,
            workplace_id=self.workplace.id,
            event_name="A",
        )
        self._seed_rule(
            group_id=self.group_b.id,
            workplace_id=self.workplace.id,
            event_name="B",
            description="Používej brýle",
        )
        pravidla_bezpecne_prace_service.export_document(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        pravidla_bezpecne_prace_service.export_document(
            endangered_group_id=self.group_b.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

        latest_a = pravidla_bezpecne_prace_edition_service.get_latest_edition(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        latest_b = pravidla_bezpecne_prace_edition_service.get_latest_edition(
            endangered_group_id=self.group_b.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertIsNotNone(latest_a)
        self.assertIsNotNone(latest_b)
        assert latest_a is not None and latest_b is not None
        self.assertNotEqual(latest_a.id, latest_b.id)
        self.assertEqual(latest_a.endangered_group_id, self.group_a.id)
        self.assertEqual(latest_b.endangered_group_id, self.group_b.id)

    def test_separates_workplace_scope(self) -> None:
        self._seed_rule(
            group_id=self.group_a.id,
            workplace_id=self.workplace.id,
            workplace_part_id=self.part.id,
            event_name="Část",
        )
        self._seed_rule(
            group_id=self.group_a.id,
            workplace_id=self.workplace.id,
            event_name="Pracoviště",
            description="Jiná helma",
        )

        pravidla_bezpecne_prace_service.export_document(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
        )
        pravidla_bezpecne_prace_service.export_document(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        pravidla_bezpecne_prace_service.export_document(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=self.part.id,
        )

        only_operation = pravidla_bezpecne_prace_edition_service.get_latest_edition(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
        )
        workplace_scope = pravidla_bezpecne_prace_edition_service.get_latest_edition(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        part_scope = pravidla_bezpecne_prace_edition_service.get_latest_edition(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=self.part.id,
        )

        self.assertIsNotNone(only_operation)
        self.assertIsNotNone(workplace_scope)
        self.assertIsNotNone(part_scope)
        assert only_operation and workplace_scope and part_scope
        self.assertEqual(
            {only_operation.id, workplace_scope.id, part_scope.id},
            {only_operation.id, workplace_scope.id, part_scope.id},
        )
        self.assertEqual(len({only_operation.id, workplace_scope.id, part_scope.id}), 3)
        self.assertIsNone(only_operation.workplace_id)
        self.assertEqual(workplace_scope.workplace_id, self.workplace.id)
        self.assertIsNone(workplace_scope.workplace_part_id)
        self.assertEqual(part_scope.workplace_part_id, self.part.id)

    def test_stores_full_rule_snapshot(self) -> None:
        self._seed_rule(
            group_id=self.group_a.id,
            workplace_id=self.workplace.id,
            description="Používej helmu",
            severity=RISK_SEVERITY_CRITICAL,
            event_name="Snap",
        )
        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        edition = pravidla_bezpecne_prace_edition_service.record_edition(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=rules,
            export_path="/tmp/pbp5a.odt",
        )

        self.assertEqual(len(edition.rules), 1)
        snap = edition.rules[0]
        self.assertEqual(snap.sort_order, 1)
        self.assertEqual(snap.display_text, "Používej helmu.")
        self.assertEqual(snap.normalized_text, "používej helmu.")
        self.assertEqual(snap.severity, RISK_SEVERITY_CRITICAL)
        self.assertGreaterEqual(snap.severity_rank, 0)
        self.assertEqual(snap.measure_id, rules[0].measure_id)
        sources = json.loads(snap.sources_json)
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["measure_id"], rules[0].measure_id)
        self.assertIn("source_hazard_id", sources[0])
        self.assertIn("source_event_id", sources[0])
        self.assertEqual(sources[0]["severity"], RISK_SEVERITY_CRITICAL)

    def test_failed_export_does_not_create_edition(self) -> None:
        self._seed_rule(group_id=self.group_a.id, workplace_id=self.workplace.id)
        with patch.object(
            pravidla_bezpecne_prace_service.engine,
            "render",
            side_effect=RuntimeError("export failed"),
        ):
            with self.assertRaises(RuntimeError):
                pravidla_bezpecne_prace_service.export_document(
                    endangered_group_id=self.group_a.id,
                    operation_id=self.operation.id,
                    workplace_id=self.workplace.id,
                )

        latest = pravidla_bezpecne_prace_edition_service.get_latest_edition(
            endangered_group_id=self.group_a.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertIsNone(latest)

    def test_tables_created_by_migration(self) -> None:
        from core.database.database_initializer import _table_exists

        self.assertTrue(_table_exists("pravidla_bezpecne_prace_editions"))
        self.assertTrue(_table_exists("pravidla_bezpecne_prace_edition_rules"))


if __name__ == "__main__":
    unittest.main()
