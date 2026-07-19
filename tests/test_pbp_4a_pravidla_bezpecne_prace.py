"""PBP-4a: doladění šablony a kontroly kvality pravidel."""

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

_TMP = Path(tempfile.mkdtemp(prefix="pbp-4a-"))
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
        is_unsuitable_employee_rule,
        pravidla_bezpecne_prace_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


def _odt_part(path: Path, name: str) -> str:
    with zipfile.ZipFile(path) as zin:
        return zin.read(name).decode("utf-8")


class UnsuitableRulePbp4aTestCase(unittest.TestCase):
    def test_noun_phrases_without_verb(self) -> None:
        for text in (
            "Poučení obsluhy.",
            "Používání ochranného krytu vrtáku.",
            "Stabilní umístění nábytku na rovném podkladu.",
        ):
            with self.subTest(text=text):
                self.assertTrue(is_unsuitable_employee_rule(text))

    def test_no_measure_needed_formulations(self) -> None:
        for text in (
            "Není potřeba dalších opatření.",
            "Není nutné přijímat opatření.",
            "Bez opatření – riziko je zřejmé.",
            "Riziko je zřejmé, opatření není potřeba.",
        ):
            with self.subTest(text=text):
                self.assertTrue(is_unsuitable_employee_rule(text))

    def test_employee_imperatives_remain_ok(self) -> None:
        for text in (
            "Používej ochrannou přilbu.",
            "Zákaz vstupu pod břemeno.",
        ):
            with self.subTest(text=text):
                self.assertFalse(is_unsuitable_employee_rule(text))


class PravidlaBezpecnePracePhasePbp4aTestCase(unittest.TestCase):
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

        self.group = ensure_exposed_group("PBP4a skupina")
        self.person = person_service.create_person(first_name="PBP4a", last_name="Tester")
        self.operation = settings_service.save_workplace(
            name="PBP4a provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="PBP4a pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.part = settings_service.save_workplace(
            name="PBP4a část",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=self.workplace.id,
        )

    def _seed(self, *, workplace_id=None, workplace_part_id=None) -> None:
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=workplace_id,
            workplace_part_id=workplace_part_id,
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
            name="Událost",
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
            description="Používej ochranné brýle",
        )

    def test_template_footer_uses_pravidla_title(self) -> None:
        template = pravidla_bezpecne_prace_service.template_path()
        styles = _odt_part(template, "styles.xml")
        self.assertIn("Pravidla bezpečné práce", styles)
        self.assertNotIn("Roční zpráva o stavu BOZP", styles)
        self.assertIn("Strana", styles)
        self.assertIn("text:page-number", styles)
        self.assertIn("text:page-count", styles)

    def test_export_omits_empty_workplace_rows(self) -> None:
        # Identifikace vyžaduje pracoviště, ale export může být jen za provoz.
        self._seed(workplace_id=self.workplace.id)
        path = pravidla_bezpecne_prace_service.export_document(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            issued_at=date(2026, 7, 19),
        )
        self.assertIsNotNone(path)
        assert path is not None
        content = _odt_part(path, "content.xml")
        self.assertIn("PBP4a provoz", content)
        self.assertIn("Datum vydání", content)
        self.assertNotIn(">Pracoviště<", content)
        self.assertNotIn(">Část pracoviště<", content)

    def test_export_keeps_selected_workplace_rows(self) -> None:
        self._seed(workplace_id=self.workplace.id, workplace_part_id=self.part.id)
        path = pravidla_bezpecne_prace_service.export_document(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=self.part.id,
            issued_at=date(2026, 7, 19),
        )
        self.assertIsNotNone(path)
        assert path is not None
        content = _odt_part(path, "content.xml")
        self.assertIn(">Pracoviště<", content)
        self.assertIn("PBP4a pracoviště", content)
        self.assertIn(">Část pracoviště<", content)
        self.assertIn("PBP4a část", content)


if __name__ == "__main__":
    unittest.main()
