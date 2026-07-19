"""PBP-3: první použitelný ODT dokument Pravidla bezpečné práce."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="pbp-3-"))
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
        pravidla_bezpecne_prace_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path) as zin:
        return zin.read("content.xml").decode("utf-8")


class PravidlaBezpecnePracePhasePbp3TestCase(unittest.TestCase):
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

        self.group = ensure_exposed_group("PBP3 skupina")
        self.person = person_service.create_person(first_name="PBP3", last_name="Tester")
        self.operation = settings_service.save_workplace(
            name="PBP3 provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="PBP3 pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.part = settings_service.save_workplace(
            name="PBP3 část",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=self.workplace.id,
        )

    def _seed_rules(self) -> tuple[HazardIdentification, HazardEvent]:
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=self.part.id,
            responsible_person_id=self.person.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Zařízení",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="Pád břemene",
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
            description="Zákaz vstupu pod břemeno",
        )
        hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description="Používej ochrannou přilbu",
        )
        return identification, event

    def test_template_is_available(self) -> None:
        template = pravidla_bezpecne_prace_service.template_path()
        self.assertTrue(template.exists(), template)
        content = _odt_content(template)
        self.assertIn("PLATNÁ PRAVIDLA BEZPEČNÉ PRÁCE", content)
        self.assertIn("${platna_pravidla_text}", content)
        self.assertNotIn("🟢", content)
        self.assertNotIn("🟡", content)
        self.assertNotIn("🔴", content)

    def test_generate_includes_source_ids(self) -> None:
        identification, event = self._seed_rules()
        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=self.part.id,
        )
        self.assertGreaterEqual(len(rules), 2)
        for rule in rules:
            self.assertIsInstance(rule, PravidloBezpecnePrace)
            self.assertEqual(rule.source_hazard_id, identification.id)
            self.assertEqual(rule.source_event_id, event.id)

    def test_export_creates_odt_with_header_and_numbered_rules(self) -> None:
        self._seed_rules()
        path = pravidla_bezpecne_prace_service.export_document(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=self.part.id,
            issued_at=date(2026, 7, 19),
        )
        self.assertIsNotNone(path)
        assert path is not None
        self.assertTrue(path.exists())
        self.assertTrue(path.name.endswith(".odt"))

        content = _odt_content(path)
        self.assertIn("PBP3 skupina", content)
        self.assertIn("PBP3 provoz", content)
        self.assertIn("PBP3 pracoviště", content)
        self.assertIn("PBP3 část", content)
        self.assertIn("19.07.2026", content)
        self.assertIn("PLATNÁ PRAVIDLA BEZPEČNÉ PRÁCE", content)
        self.assertIn("1. Používej ochrannou přilbu.", content)
        self.assertIn("2. Zákaz vstupu pod břemeno.", content)
        self.assertNotIn("🟢", content)
        self.assertNotIn("${", content)

    def test_export_returns_none_when_empty(self) -> None:
        path = pravidla_bezpecne_prace_service.export_document(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
        )
        self.assertIsNone(path)

    def test_open_document_opens_export(self) -> None:
        self._seed_rules()
        with patch(
            "moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service.open_export_file"
        ) as open_file:
            path = pravidla_bezpecne_prace_service.open_document(
                endangered_group_id=self.group.id,
                operation_id=self.operation.id,
                workplace_id=self.workplace.id,
            )
        self.assertIsNotNone(path)
        open_file.assert_called_once()
        self.assertEqual(open_file.call_args.args[0], path)


if __name__ == "__main__":
    unittest.main()
