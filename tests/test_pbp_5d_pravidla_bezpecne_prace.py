"""PBP-5d: zobrazení změn v dokumentu Pravidel bezpečné práce."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

_TMP = Path(tempfile.mkdtemp(prefix="pbp-5d-"))
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
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_document_format import (
        format_change_sections,
        format_numbered_valid_rules,
    )
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_edition_service import (
        pravidla_bezpecne_prace_edition_service,
    )
    from moduly.rizeni_rizik.sluzby.pravidla_bezpecne_prace_service import (
        pravidla_bezpecne_prace_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


class PravidlaBezpecnePracePhasePbp5dTestCase(unittest.TestCase):
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

        self.group = ensure_exposed_group("PBP5d skupina")
        self.person = person_service.create_person(first_name="PBP5d", last_name="Tester")
        self.operation = settings_service.save_workplace(
            name="PBP5d provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="PBP5d pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )

    def _seed(
        self,
        *,
        description: str,
        event_name: str,
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
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
        )
        measure = hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description=description,
        )
        return measure, identification.id

    def _export(self, *, issued_at: date | datetime) -> Path:
        path = pravidla_bezpecne_prace_service.export_document(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            issued_at=issued_at,
        )
        self.assertIsNotNone(path)
        assert path is not None
        return path

    def _record_baseline(self, *, issued_at: datetime) -> None:
        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        pravidla_bezpecne_prace_edition_service.record_edition(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=rules,
            issued_at=issued_at,
        )

    def test_first_edition_has_no_change_sections(self) -> None:
        self._seed(description="Používej helmu", event_name="First")
        content = _odt_content(self._export(issued_at=date(2026, 7, 1)))
        self.assertIn("DODRŽUJTE TATO PRAVIDLA", content)
        self.assertIn("• Používej helmu.", content)
        self.assertNotIn("Shrnutí změn", content)
        self.assertNotIn("🟢", content)
        self.assertNotIn("🟡", content)
        self.assertNotIn("🔴", content)
        self.assertNotIn("Nová pravidla", content)

    def test_identical_edition_has_no_change_sections(self) -> None:
        self._seed(description="Používej helmu", event_name="Same")
        self._record_baseline(issued_at=datetime(2026, 7, 1, 10, 0, 0))
        content = _odt_content(self._export(issued_at=date(2026, 7, 10)))
        self.assertIn("DODRŽUJTE TATO PRAVIDLA", content)
        self.assertIn("• Používej helmu.", content)
        self.assertNotIn("Shrnutí změn", content)
        self.assertNotIn("🟢", content)

    def test_only_new_rules(self) -> None:
        self._seed(description="Používej helmu", event_name="Keep")
        self._record_baseline(issued_at=datetime(2026, 6, 1, 8, 0, 0))
        self._seed(description="Používej brýle", event_name="New")
        content = _odt_content(self._export(issued_at=date(2026, 7, 15)))

        self.assertIn("Shrnutí změn", content)
        self.assertIn("Nová pravidla: 1", content)
        self.assertIn("Změněná pravidla: 0", content)
        self.assertIn("Zrušená pravidla: 0", content)
        self.assertIn("🟢 Nová pravidla", content)
        self.assertIn("🟢 Používej brýle.", content)
        self.assertNotIn("🟡 Změněná pravidla", content)
        self.assertNotIn("🔴 Zrušená pravidla", content)
        self.assertIn("• 🟢 Používej brýle.", content)
        self.assertIn("• Používej helmu.", content)
        self.assertNotRegex(
            content.split("DODRŽUJTE TATO PRAVIDLA", 1)[1],
            r"• 🟢 Používej helmu\.",
        )

    def test_only_changed_rules(self) -> None:
        measure, identification_id = self._seed(
            description="Používej helmu",
            event_name="Chg",
        )
        self._record_baseline(issued_at=datetime(2026, 6, 2, 8, 0, 0))
        hazard_existing_measure_service.update_measure(
            measure.id,
            hazard_identification_id=identification_id,
            hazard_risk_assessment_id=measure.hazard_risk_assessment_id,
            description="Používej ochrannou přilbu",
        )
        content = _odt_content(self._export(issued_at=date(2026, 7, 16)))

        self.assertIn("Změněná pravidla: 1", content)
        self.assertIn("Nová pravidla: 0", content)
        self.assertIn("🟡 Změněná pravidla", content)
        self.assertIn("Staré:", content)
        self.assertIn("• Používej helmu.", content)
        self.assertIn("Nové:", content)
        self.assertIn("🟡 Používej ochrannou přilbu.", content)
        self.assertNotIn("🟢 Nová pravidla", content)
        self.assertNotIn("🔴 Zrušená pravidla", content)
        self.assertIn("• 🟡 Používej ochrannou přilbu.", content)
        # Změnová sekce bez číslování.
        self.assertNotIn("• 🟡 Používej ochrannou přilbu.", content.split("DODRŽUJTE")[0])

    def test_only_removed_rules(self) -> None:
        keep, _ = self._seed(description="Používej helmu", event_name="KeepR")
        gone, _ = self._seed(description="Používej brýle", event_name="GoneR")
        self._record_baseline(issued_at=datetime(2026, 6, 3, 8, 0, 0))
        hazard_existing_measure_service.deactivate_measure(gone.id)
        content = _odt_content(self._export(issued_at=date(2026, 7, 17)))

        self.assertIn("Zrušená pravidla: 1", content)
        self.assertIn("🔴 Zrušená pravidla", content)
        self.assertIn("🔴 Používej brýle.", content)
        self.assertNotIn("🟢 Nová pravidla", content)
        self.assertNotIn("🟡 Změněná pravidla", content)
        self.assertIn("• Používej helmu.", content)
        self.assertNotIn("Používej brýle.", content.split("DODRŽUJTE")[-1])
        self.assertEqual(keep.id, keep.id)  # keep used

    def test_combination_of_all_change_types_and_section_order(self) -> None:
        keep, _ = self._seed(description="Používej helmu", event_name="AllKeep")
        change, change_ident = self._seed(
            description="Používej rukavice",
            event_name="AllChg",
        )
        gone, _ = self._seed(description="Používej brýle", event_name="AllGone")
        self._record_baseline(issued_at=datetime(2026, 5, 1, 9, 0, 0))

        hazard_existing_measure_service.update_measure(
            change.id,
            hazard_identification_id=change_ident,
            hazard_risk_assessment_id=change.hazard_risk_assessment_id,
            description="Používej ochranné rukavice",
        )
        hazard_existing_measure_service.deactivate_measure(gone.id)
        self._seed(description="Noste vestu", event_name="AllNew")

        content = _odt_content(self._export(issued_at=date(2026, 7, 18)))
        summary = content.find("Shrnutí změn")
        new_sec = content.find("🟢 Nová pravidla")
        chg_sec = content.find("🟡 Změněná pravidla")
        rem_sec = content.find("🔴 Zrušená pravidla")
        valid = content.find("DODRŽUJTE TATO PRAVIDLA")
        self.assertTrue(0 <= summary < new_sec < chg_sec < rem_sec < valid)

        self.assertIn("Nová pravidla: 1", content)
        self.assertIn("Změněná pravidla: 1", content)
        self.assertIn("Zrušená pravidla: 1", content)
        self.assertIn("🟢 Noste vestu.", content)
        self.assertIn("• Používej rukavice.", content)
        self.assertIn("🟡 Používej ochranné rukavice.", content)
        self.assertIn("🔴 Používej brýle.", content)

        platna = content.split("DODRŽUJTE TATO PRAVIDLA", 1)[1]
        self.assertIn("🟢 Noste vestu.", platna)
        self.assertIn("🟡 Používej ochranné rukavice.", platna)
        self.assertIn(f"Používej helmu.", platna)
        self.assertNotIn("🔴", platna)
        self.assertIn("• 🟢 Noste vestu.", platna)
        self.assertIn("• 🟡 Používej ochranné rukavice.", platna)
        self.assertIn("• Používej helmu.", platna)
        _ = keep

    def test_change_sections_unnumbered_valid_rules_bulleted(self) -> None:
        self._seed(description="Používej helmu", event_name="NumKeep")
        self._record_baseline(issued_at=datetime(2026, 6, 4, 8, 0, 0))
        self._seed(description="Používej brýle", event_name="NumNew")
        content = _odt_content(self._export(issued_at=date(2026, 7, 19)))
        before, after = content.split("DODRŽUJTE TATO PRAVIDLA", 1)
        self.assertIn("🟢 Používej brýle.", before)
        self.assertNotRegex(before, r"•\s*🟢")
        self.assertIn("• 🟢 Používej brýle.", after)
        self.assertIn("• Používej helmu.", after)

    def test_previous_and_current_edition_dates(self) -> None:
        self._seed(description="Používej helmu", event_name="Dates")
        self._record_baseline(issued_at=datetime(2026, 4, 12, 14, 30, 0))
        self._seed(description="Používej brýle", event_name="DatesNew")
        content = _odt_content(self._export(issued_at=date(2026, 7, 20)))
        self.assertIn("Poslední vydání:", content)
        self.assertIn("12.04.2026", content)
        self.assertIn("Aktuální vydání:", content)
        self.assertIn("20.07.2026", content)

    def test_formatter_skips_empty_detail_sections(self) -> None:
        comparison = pravidla_bezpecne_prace_edition_service.compare_to_latest(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=[],
        )
        # první vydání
        text = format_change_sections(
            comparison,
            current_issued_at=date(2026, 7, 1),
            date_formatter=pravidla_bezpecne_prace_service._fmt_date,
        )
        self.assertEqual(text, "")

        self._seed(description="Používej helmu", event_name="Fmt")
        self._record_baseline(issued_at=datetime.now() - timedelta(days=1))
        self._seed(description="Používej brýle", event_name="FmtNew")
        rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        comparison = pravidla_bezpecne_prace_edition_service.compare_to_latest(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            rules=rules,
        )
        text = format_change_sections(
            comparison,
            current_issued_at=date(2026, 8, 1),
            date_formatter=pravidla_bezpecne_prace_service._fmt_date,
        )
        self.assertIn("🟢 Nová pravidla", text)
        self.assertNotIn("🟡 Změněná pravidla", text)
        self.assertNotIn("🔴 Zrušená pravidla", text)
        numbered = format_numbered_valid_rules(rules, comparison)
        self.assertIn("🟢 Používej brýle.", numbered)
        self.assertIn("Používej helmu.", numbered)


if __name__ == "__main__":
    unittest.main()
