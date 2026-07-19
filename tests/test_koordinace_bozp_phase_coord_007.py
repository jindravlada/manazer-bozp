"""Fáze COORD-007 – automatické generování přílohy PBP."""

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

_TMP = Path(tempfile.mkdtemp(prefix="coord-007-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import _table_columns, initialize_database

    initialize_database()

    from core.database.session import get_session
    from moduly.koordinace_bozp.constants import (
        MAIN_EMPLOYER_RISK_HANDOVER_ATTACHMENT_TITLE,
        TAB_PBP_ATTACHMENT,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
    )
    from moduly.koordinace_bozp.modely.coordination_participant import (
        CoordinationParticipant,
    )
    from moduly.koordinace_bozp.modely.coordination_pbp_revision import (
        CoordinationPbpRevision,
    )
    from moduly.koordinace_bozp.modely.coordination_workplace import (
        CoordinationWorkplace,
    )
    from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
        bozp_coordination_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_pbp_attachment_service import (
        content_hash_for_rules,
        coordination_pbp_attachment_service,
        merge_pbp_rules,
    )
    from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
        coordination_workplace_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
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
        RISK_SEVERITY_MINOR,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_existing_measure import HazardExistingMeasure
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
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
        pravidla_bezpecne_prace_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class KoordinaceBozpPhaseCoord007TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationEmployerActivity))
            session.execute(delete(CoordinationMeasure))
            session.execute(delete(CoordinationWorkplace))
            session.execute(delete(CoordinationCoordinator))
            session.execute(delete(CoordinationParticipant))
            session.execute(delete(CoordinationEmployer))
            session.execute(delete(BozpCoordination))
            session.execute(delete(HazardExistingMeasure))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        settings_service.save_employer(
            ico="12345678",
            name="Hlavní firma s.r.o.",
            address="Praha",
            nace="",
        )
        self.group = ensure_exposed_group("COORD007 skupina")
        self.person = person_service.create_person(first_name="Coord", last_name="Pbp")
        self.operation = settings_service.save_workplace(
            name="COORD007 provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="COORD007 pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.part = settings_service.save_workplace(
            name="COORD007 část",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=self.workplace.id,
        )

    def _create_measure(
        self,
        *,
        workplace_id: int | None,
        workplace_part_id: int | None,
        description: str,
        severity: str = RISK_SEVERITY_MODERATE,
        event_name: str = "Událost",
    ):
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=workplace_id,
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
            exposed_group_id=self.group.id,
            severity=severity,
        )
        return hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description=description,
        )

    def test_model_table(self) -> None:
        columns = _table_columns("coordination_pbp_revisions")
        for name in (
            "id",
            "coordination_id",
            "revision_number",
            "title",
            "content_hash",
            "rules_count",
            "file_path",
            "created_by",
            "is_current",
        ):
            self.assertIn(name, columns)

    def test_single_place_matches_pbp_module(self) -> None:
        self._create_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            description="Používej ochranné brýle",
        )
        coordination = bozp_coordination_service.create_coordination(
            subject="Jedno místo",
            meeting_date=date.today(),
        )
        coordination_workplace_service.add(
            coordination.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        expected = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        actual = coordination_pbp_attachment_service.collect_rules_for_coordination(
            coordination.id
        )
        self.assertEqual([rule.text for rule in actual], [rule.text for rule in expected])
        self.assertEqual(actual[0].text, "Používej ochranné brýle.")

    def test_multiple_places_dedupe_and_overlap(self) -> None:
        self._create_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            description="Noste ochrannou přilbu",
            event_name="A",
        )
        self._create_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=self.part.id,
            description="Noste  ochrannou   přilbu",
            event_name="B",
        )
        self._create_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=self.part.id,
            description="Používej rukavice",
            event_name="C",
        )
        coordination = bozp_coordination_service.create_coordination(
            subject="Více míst",
            meeting_date=date.today(),
        )
        coordination_workplace_service.add(
            coordination.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        coordination_workplace_service.add(
            coordination.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=self.part.id,
        )

        workplace_rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        part_rules = pravidla_bezpecne_prace_service.generate(
            endangered_group_id=self.group.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=self.part.id,
        )
        expected = merge_pbp_rules(workplace_rules + part_rules)
        actual = coordination_pbp_attachment_service.collect_rules_for_coordination(
            coordination.id
        )
        self.assertEqual([r.text for r in actual], [r.text for r in expected])
        texts = [r.text for r in actual]
        self.assertEqual(len([t for t in texts if "přilbu" in t.casefold()]), 1)
        self.assertIn("Používej rukavice.", texts)

    def test_severity_sorting(self) -> None:
        self._create_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            description="Zanedbatelné pravidlo alfa",
            severity=RISK_SEVERITY_MINOR,
            event_name="m1",
        )
        self._create_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            description="Kritické pravidlo beta",
            severity=RISK_SEVERITY_CRITICAL,
            event_name="c1",
        )
        self._create_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            description="Kritické pravidlo alfa",
            severity=RISK_SEVERITY_CRITICAL,
            event_name="c2",
        )
        coordination = bozp_coordination_service.create_coordination(
            subject="Řazení",
            meeting_date=date.today(),
        )
        coordination_workplace_service.add(
            coordination.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        rules = coordination_pbp_attachment_service.collect_rules_for_coordination(
            coordination.id
        )
        self.assertEqual(
            [r.text for r in rules],
            [
                "Kritické pravidlo alfa.",
                "Kritické pravidlo beta.",
                "Zanedbatelné pravidlo alfa.",
            ],
        )

    def test_revision_created_only_when_content_changes(self) -> None:
        self._create_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            description="Dodržuj zákaz kouření",
        )
        coordination = bozp_coordination_service.create_coordination(
            subject="Revize",
            meeting_date=date.today(),
        )
        coordination_workplace_service.add(
            coordination.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        first = coordination_pbp_attachment_service.generate_or_update(coordination.id)
        self.assertTrue(first.created)
        assert first.revision is not None
        self.assertEqual(first.revision.revision_number, 1)
        self.assertEqual(first.revision.title, MAIN_EMPLOYER_RISK_HANDOVER_ATTACHMENT_TITLE)
        self.assertEqual(first.revision.rules_count, 1)
        path = coordination_pbp_attachment_service.resolve_path(first.revision)
        self.assertTrue(path.exists())
        self.assertTrue(zipfile.is_zipfile(path))

        second = coordination_pbp_attachment_service.generate_or_update(coordination.id)
        self.assertFalse(second.created)
        self.assertEqual(second.revision.id, first.revision.id)
        self.assertEqual(len(coordination_pbp_attachment_service.list_revisions(coordination.id)), 1)

        self._create_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            description="Používej respirátor",
            event_name="nová",
        )
        third = coordination_pbp_attachment_service.generate_or_update(coordination.id)
        self.assertTrue(third.created)
        assert third.revision is not None
        self.assertEqual(third.revision.revision_number, 2)
        self.assertEqual(third.revision.rules_count, 2)
        self.assertNotEqual(third.revision.content_hash, first.revision.content_hash)
        history = coordination_pbp_attachment_service.list_revisions(coordination.id)
        self.assertEqual(len(history), 2)
        self.assertTrue(history[0].is_current)
        self.assertFalse(history[1].is_current)

    def test_export_odt_copies_current_file(self) -> None:
        self._create_measure(
            workplace_id=self.workplace.id,
            workplace_part_id=None,
            description="Udržuj pořádek na pracovišti",
        )
        coordination = bozp_coordination_service.create_coordination(
            subject="Export",
            meeting_date=date.today(),
        )
        coordination_workplace_service.add(
            coordination.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        result = coordination_pbp_attachment_service.generate_or_update(coordination.id)
        assert result.revision is not None
        target = _TMP / "export-pbp.odt"
        exported = coordination_pbp_attachment_service.export_current_odt(
            coordination.id,
            target,
        )
        self.assertTrue(exported.exists())
        self.assertEqual(
            exported.read_bytes(),
            coordination_pbp_attachment_service.resolve_path(result.revision).read_bytes(),
        )
        with zipfile.ZipFile(exported) as zin:
            content = zin.read("content.xml").decode("utf-8")
        self.assertIn(MAIN_EMPLOYER_RISK_HANDOVER_ATTACHMENT_TITLE, content)
        self.assertIn("Udržuj pořádek na pracovišti.", content)

    def test_ui_tab_present(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="UI",
            meeting_date=date.today(),
        )
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        labels = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertIn(TAB_PBP_ATTACHMENT, labels)
        self.assertFalse(dialog.pbp_attachment_tab.content.isHidden())


if __name__ == "__main__":
    unittest.main()
