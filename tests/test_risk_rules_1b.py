"""RISK-RULES-1b: samostatné odrážky podle řádků pravidel."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="risk-rules-1b-"))
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
    from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
        HazardRiskAssessmentExposedGroup,
    )
    from moduly.rizeni_rizik.sluzby.exposed_target_ref import (
        SOURCE_TYPE_HAZARD_GROUP,
        ExposedTargetRef,
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
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_document_format import (
        format_bullet_valid_rules,
        rule_line_dedupe_key,
        split_rule_lines,
    )
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
        PravidloBezpecnePrace,
        normalize_rule_text,
        pravidla_bezpecne_prace_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


class SplitRuleLinesUnitTestCase(unittest.TestCase):
    def test_single_line(self) -> None:
        self.assertEqual(split_rule_lines("Používej helmu."), ["Používej helmu."])

    def test_three_lines(self) -> None:
        text = (
            "Řádně sledovat provoz a návěstidla.\n"
            "Bezodkladně zastavit při zaslechnutí nouzového volání.\n"
            "Dodržovat pravidla radiové komunikace."
        )
        self.assertEqual(
            split_rule_lines(text),
            [
                "Řádně sledovat provoz a návěstidla.",
                "Bezodkladně zastavit při zaslechnutí nouzového volání.",
                "Dodržovat pravidla radiové komunikace.",
            ],
        )

    def test_skips_empty_lines(self) -> None:
        self.assertEqual(
            split_rule_lines("První.\n\n\nDruhé."),
            ["První.", "Druhé."],
        )

    def test_strips_whitespace(self) -> None:
        self.assertEqual(
            split_rule_lines("  První.  \n\tDruhé.\t"),
            ["První.", "Druhé."],
        )

    def test_windows_newlines(self) -> None:
        self.assertEqual(
            split_rule_lines("První.\r\nDruhé.\r\nTřetí."),
            ["První.", "Druhé.", "Třetí."],
        )

    def test_old_mac_newlines(self) -> None:
        self.assertEqual(
            split_rule_lines("První.\rDruhé."),
            ["První.", "Druhé."],
        )

    def test_dedupe_key_collapses_spaces_without_changing_display(self) -> None:
        display = "Používej   helmu."
        self.assertEqual(rule_line_dedupe_key(display), "Používej helmu.")
        self.assertEqual(display, "Používej   helmu.")


class RiskRules1bBulletFormatTestCase(unittest.TestCase):
    def _rule(self, text: str, measure_id: int = 1) -> PravidloBezpecnePrace:
        return PravidloBezpecnePrace(
            measure_id=measure_id,
            text=text,
            source_hazard_id=1,
            source_event_id=1,
        )

    def test_single_line_one_bullet(self) -> None:
        bullets = format_bullet_valid_rules(
            [self._rule("Používej helmu.")],
            None,
        )
        self.assertEqual(bullets, ["• Používej helmu."])

    def test_three_lines_three_bullets(self) -> None:
        text = normalize_rule_text(
            "Řádně sledovat provoz a návěstidla.\n"
            "Bezodkladně zastavit při zaslechnutí nouzového volání.\n"
            "Dodržovat pravidla radiové komunikace."
        )
        bullets = format_bullet_valid_rules([self._rule(text)], None)
        self.assertEqual(
            bullets,
            [
                "• Řádně sledovat provoz a návěstidla.",
                "• Bezodkladně zastavit při zaslechnutí nouzového volání.",
                "• Dodržovat pravidla radiové komunikace.",
            ],
        )

    def test_empty_lines_skipped(self) -> None:
        text = normalize_rule_text("První.\n\n\nDruhé.")
        bullets = format_bullet_valid_rules([self._rule(text)], None)
        self.assertEqual(bullets, ["• První.", "• Druhé."])

    def test_duplicate_line_across_measures_once(self) -> None:
        bullets = format_bullet_valid_rules(
            [
                self._rule("Používej helmu.\nZákaz vstupu.", measure_id=1),
                self._rule("Používej   helmu.\nDalší pravidlo.", measure_id=2),
            ],
            None,
        )
        self.assertEqual(
            bullets,
            [
                "• Používej helmu.",
                "• Zákaz vstupu.",
                "• Další pravidlo.",
            ],
        )

    def test_preserves_order_inside_measure(self) -> None:
        bullets = format_bullet_valid_rules(
            [self._rule("C.\nA.\nB.")],
            None,
        )
        self.assertEqual(bullets, ["• C.", "• A.", "• B."])


class RiskRules1bExportTestCase(unittest.TestCase):
    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(HazardRiskAssessmentExposedGroup))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.group = ensure_exposed_group("RULES1b skupina")
        self.person = person_service.create_person(first_name="Rules", last_name="OneB")
        self.operation = settings_service.save_workplace(
            name="RULES1b provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="RULES1b pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )

    def _seed(self, description: str, *, event_name: str) -> HazardExistingMeasure:
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
            target_refs=[ExposedTargetRef(SOURCE_TYPE_HAZARD_GROUP, self.group.id)],
            severity=RISK_SEVERITY_MODERATE,
        )
        return hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description=description,
        )

    def test_odt_multiline_measure_separate_bullet_paragraphs(self) -> None:
        self._seed(
            "Řádně sledovat provoz a návěstidla.\r\n"
            "\r\n"
            "  Bezodkladně zastavit při zaslechnutí nouzového volání.  \r\n"
            "Dodržovat pravidla radiové komunikace.",
            event_name="Multi",
        )
        path = pravidla_bezpecne_prace_service.export_document(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        self.assertIsNotNone(path)
        assert path is not None
        content = _odt_content(path)

        self.assertIn("DODRŽUJTE TATO PRAVIDLA", content)
        self.assertNotIn("PLATNÁ PRAVIDLA BEZPEČNÉ PRÁCE", content)
        self.assertEqual(content.count('text:style-name="PbpRuleBullet"'), 3)
        self.assertIn("• Řádně sledovat provoz a návěstidla.", content)
        self.assertIn(
            "• Bezodkladně zastavit při zaslechnutí nouzového volání.",
            content,
        )
        self.assertIn("• Dodržovat pravidla radiové komunikace.", content)
        # Každý řádek je samostatný odstavec, ne jeden odstavec s line-break.
        self.assertNotIn(
            "Řádně sledovat provoz a návěstidla.<text:line-break/>",
            content,
        )


if __name__ == "__main__":
    unittest.main()
