"""PBP-4b: řazení pravidel podle závažnosti rizika."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="pbp-4b-"))
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
        RISK_SEVERITIES,
        RISK_SEVERITY_CRITICAL,
        RISK_SEVERITY_MINOR,
        RISK_SEVERITY_MODERATE,
        RISK_SEVERITY_NEGLIGIBLE,
        RISK_SEVERITY_SERIOUS,
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
        severity_rank,
        pravidla_bezpecne_prace_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class PravidlaBezpecnePracePhasePbp4bTestCase(unittest.TestCase):
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

        self.group = ensure_exposed_group("PBP4b skupina")
        self.person = person_service.create_person(first_name="PBP4b", last_name="Tester")
        self.operation = settings_service.save_workplace(
            name="PBP4b provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="PBP4b pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )

    def _create_measure(self, description: str, *, severity: str, event_name: str) -> None:
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
            severity=severity,
        )
        hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description=description,
        )

    def test_severity_rank_matches_register_order(self) -> None:
        ranks = [severity_rank(code) for code in RISK_SEVERITIES]
        self.assertEqual(ranks, list(range(len(RISK_SEVERITIES))))
        self.assertGreater(severity_rank(RISK_SEVERITY_CRITICAL), severity_rank(RISK_SEVERITY_SERIOUS))
        self.assertGreater(severity_rank(RISK_SEVERITY_SERIOUS), severity_rank(RISK_SEVERITY_MODERATE))
        self.assertGreater(severity_rank(RISK_SEVERITY_MODERATE), severity_rank(RISK_SEVERITY_MINOR))
        self.assertGreater(severity_rank(RISK_SEVERITY_MINOR), severity_rank(RISK_SEVERITY_NEGLIGIBLE))

    def test_sort_by_severity_then_alphabet(self) -> None:
        self._create_measure("Zebra pravidlo", severity=RISK_SEVERITY_MINOR, event_name="Lehký Z")
        self._create_measure("Alfa pravidlo", severity=RISK_SEVERITY_MINOR, event_name="Lehký A")
        self._create_measure("Střední pravidlo", severity=RISK_SEVERITY_MODERATE, event_name="Střední")
        self._create_measure("Vysoké pravidlo", severity=RISK_SEVERITY_SERIOUS, event_name="Vysoké")
        self._create_measure("Kritické pravidlo", severity=RISK_SEVERITY_CRITICAL, event_name="Kritické")
        self._create_measure(
            "Zanedbatelné pravidlo",
            severity=RISK_SEVERITY_NEGLIGIBLE,
            event_name="Zanedbatelné",
        )

        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

        texts = [rule.text for rule in rules]
        self.assertEqual(
            texts,
            [
                "Kritické pravidlo.",
                "Vysoké pravidlo.",
                "Střední pravidlo.",
                "Alfa pravidlo.",
                "Zebra pravidlo.",
                "Zanedbatelné pravidlo.",
            ],
        )
        self.assertEqual(
            [rule.severity for rule in rules],
            [
                RISK_SEVERITY_CRITICAL,
                RISK_SEVERITY_SERIOUS,
                RISK_SEVERITY_MODERATE,
                RISK_SEVERITY_MINOR,
                RISK_SEVERITY_MINOR,
                RISK_SEVERITY_NEGLIGIBLE,
            ],
        )

    def test_duplicate_keeps_highest_severity_once(self) -> None:
        self._create_measure("Používej helmu", severity=RISK_SEVERITY_MINOR, event_name="Dup low")
        self._create_measure("používej helmu", severity=RISK_SEVERITY_CRITICAL, event_name="Dup high")
        self._create_measure("Používej helmu.", severity=RISK_SEVERITY_MODERATE, event_name="Dup mid")

        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

        helm = [rule for rule in rules if "helmu" in rule.text.casefold()]
        self.assertEqual(len(helm), 1)
        self.assertEqual(helm[0].severity, RISK_SEVERITY_CRITICAL)
        self.assertEqual(helm[0].severity_rank, severity_rank(RISK_SEVERITY_CRITICAL))
        self.assertEqual(len(helm[0].sources), 3)


if __name__ == "__main__":
    unittest.main()
