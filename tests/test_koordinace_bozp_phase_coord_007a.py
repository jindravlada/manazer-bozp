"""Fáze COORD-007a – kontrola aktuálnosti přílohy PBP."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from sqlalchemy import delete, func, select

_TMP = Path(tempfile.mkdtemp(prefix="coord-007a-"))
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
    from moduly.koordinace_bozp.constants import (
        BOZP_COORDINATION_STATUS_ARCHIVED,
        BOZP_COORDINATION_STATUS_COMPLETED,
        COL_PBP,
        PBP_FILTER_MISSING,
        PBP_FILTER_NEEDS_UPDATE,
        PBP_FRESHNESS_COLORS,
        PBP_FRESHNESS_CURRENT,
        PBP_FRESHNESS_DETAIL_MESSAGES,
        PBP_FRESHNESS_MISSING,
        PBP_FRESHNESS_NEEDS_UPDATE,
        PBP_FRESHNESS_SKIPPED,
        PBP_FRESHNESS_UNVERIFIABLE,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact
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
        coordination_pbp_attachment_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_pbp_freshness import (
        evaluate_pbp_freshness,
        is_pbp_freshness_eligible,
    )
    from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
        coordination_workplace_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.koordinace_bozp.ui.bozp_coordination_table import BozpCoordinationTable
    from moduly.koordinace_bozp.ui.koordinace_bozp_page import KoordinaceBozpPage
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
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class KoordinaceBozpPhaseCoord007aTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(CoordinationPbpRevision))
            session.execute(delete(CoordinationAttachment))
            session.execute(delete(CoordinationEmployerRiskSubmission))
            session.execute(delete(CoordinationContact))
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
        self.group = ensure_exposed_group("COORD007a skupina")
        self.person = person_service.create_person(first_name="Coord", last_name="Fresh")
        self.operation = settings_service.save_workplace(
            name="COORD007a provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="COORD007a pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.part = settings_service.save_workplace(
            name="COORD007a část",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
            parent_id=self.workplace.id,
        )
        self.today = date.today()

    def _create_measure(self, *, description: str, event_name: str = "Událost"):
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            workplace_part_id=None,
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
        return hazard_existing_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            description=description,
        )

    def _create_coordination_with_place(self, *, subject: str = "Kontrola"):
        coordination = bozp_coordination_service.create_coordination(
            subject=subject,
            meeting_date=self.today,
            valid_from=self.today,
            valid_to=self.today + timedelta(days=365),
        )
        coordination_workplace_service.add(
            coordination.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        return bozp_coordination_service.get_by_id(coordination.id)

    def _revision_count(self, coordination_id: int) -> int:
        with get_session() as session:
            return int(
                session.scalar(
                    select(func.count())
                    .select_from(CoordinationPbpRevision)
                    .where(CoordinationPbpRevision.coordination_id == coordination_id)
                )
                or 0
            )

    def test_missing_snapshot(self) -> None:
        self._create_measure(description="Používej brýle")
        coordination = self._create_coordination_with_place(subject="Bez přílohy")
        result = evaluate_pbp_freshness(coordination, today=self.today)
        self.assertEqual(result.state, PBP_FRESHNESS_MISSING)
        self.assertEqual(result.label, "Nevytvořena")
        self.assertEqual(
            result.detail_message,
            PBP_FRESHNESS_DETAIL_MESSAGES[PBP_FRESHNESS_MISSING],
        )

    def test_matching_hash_is_current(self) -> None:
        self._create_measure(description="Dodržuj zákaz kouření")
        coordination = self._create_coordination_with_place(subject="Shoda")
        generated = coordination_pbp_attachment_service.generate_or_update(coordination.id)
        self.assertTrue(generated.created)
        result = evaluate_pbp_freshness(coordination, today=self.today)
        self.assertEqual(result.state, PBP_FRESHNESS_CURRENT)
        self.assertEqual(result.snapshot_hash, generated.revision.content_hash)
        self.assertEqual(result.current_hash, generated.revision.content_hash)

    def test_changed_pbp_content_needs_update(self) -> None:
        self._create_measure(description="Noste přilbu", event_name="A")
        coordination = self._create_coordination_with_place(subject="Změna PBP")
        coordination_pbp_attachment_service.generate_or_update(coordination.id)
        self._create_measure(description="Používej rukavice", event_name="B")
        result = evaluate_pbp_freshness(coordination, today=self.today)
        self.assertEqual(result.state, PBP_FRESHNESS_NEEDS_UPDATE)
        self.assertNotEqual(result.current_hash, result.snapshot_hash)

    def test_changed_active_places_needs_update(self) -> None:
        self._create_measure(description="Pravidlo pracoviště A", event_name="WP-A")
        workplace_b = settings_service.save_workplace(
            name="COORD007a pracoviště B",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=workplace_b.id,
            workplace_part_id=None,
            responsible_person_id=self.person.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Položka B",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="Událost B",
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
            description="Pravidlo pracoviště B",
        )

        coordination = self._create_coordination_with_place(subject="Místa")
        places = coordination_workplace_service.list_for_coordination(
            coordination.id,
            include_inactive=True,
        )
        self.assertEqual(len(places), 1)
        coordination_pbp_attachment_service.generate_or_update(coordination.id)
        before = evaluate_pbp_freshness(coordination, today=self.today)
        self.assertEqual(before.state, PBP_FRESHNESS_CURRENT)

        coordination_workplace_service.deactivate(places[0].id)
        coordination_workplace_service.add(
            coordination.id,
            operation_id=self.operation.id,
            workplace_id=workplace_b.id,
        )
        after = evaluate_pbp_freshness(coordination, today=self.today)
        self.assertEqual(after.state, PBP_FRESHNESS_NEEDS_UPDATE)

    def test_inactive_coordination_skipped(self) -> None:
        self._create_measure(description="Pravidlo")
        coordination = self._create_coordination_with_place(subject="Neaktivní")
        bozp_coordination_service.deactivate(coordination.id)
        coordination = bozp_coordination_service.get_by_id(coordination.id)
        self.assertFalse(is_pbp_freshness_eligible(coordination, today=self.today))
        result = evaluate_pbp_freshness(coordination, today=self.today)
        self.assertEqual(result.state, PBP_FRESHNESS_SKIPPED)
        self.assertEqual(result.label, "—")

    def test_archived_coordination_skipped(self) -> None:
        self._create_measure(description="Pravidlo")
        coordination = self._create_coordination_with_place(subject="Archiv")
        from moduly.koordinace_bozp.sluzby.coordination_lifecycle_service import (
            coordination_lifecycle_service,
        )

        coordination_lifecycle_service.transition(
            coordination.id,
            BOZP_COORDINATION_STATUS_ARCHIVED,
        )
        coordination = bozp_coordination_service.get_by_id(coordination.id)
        result = evaluate_pbp_freshness(coordination, today=self.today)
        self.assertEqual(result.state, PBP_FRESHNESS_SKIPPED)

    def test_expired_coordination_skipped(self) -> None:
        self._create_measure(description="Pravidlo")
        coordination = bozp_coordination_service.create_coordination(
            subject="Po platnosti",
            meeting_date=self.today - timedelta(days=400),
            valid_from=self.today - timedelta(days=400),
            valid_to=self.today - timedelta(days=1),
        )
        coordination_workplace_service.add(
            coordination.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        coordination = bozp_coordination_service.get_by_id(coordination.id)
        result = evaluate_pbp_freshness(coordination, today=self.today)
        self.assertEqual(result.state, PBP_FRESHNESS_SKIPPED)

    def test_ended_without_snapshot_not_shown_as_missing(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="Ukončená bez přílohy",
            meeting_date=self.today - timedelta(days=400),
            valid_from=self.today - timedelta(days=400),
            valid_to=self.today - timedelta(days=10),
        )
        coordination.status = BOZP_COORDINATION_STATUS_COMPLETED
        coordination = bozp_coordination_service.repository.update(coordination)
        result = evaluate_pbp_freshness(coordination, today=self.today)
        self.assertEqual(result.state, PBP_FRESHNESS_SKIPPED)
        self.assertNotEqual(result.state, PBP_FRESHNESS_MISSING)

    def test_unverifiable_without_active_places(self) -> None:
        coordination = bozp_coordination_service.create_coordination(
            subject="Bez míst",
            meeting_date=self.today,
            valid_from=self.today,
            valid_to=self.today + timedelta(days=30),
        )
        result = evaluate_pbp_freshness(coordination, today=self.today)
        self.assertEqual(result.state, PBP_FRESHNESS_UNVERIFIABLE)

    def test_filters_exclude_ended_problem_coordinations(self) -> None:
        self._create_measure(description="Aktivní pravidlo", event_name="live")
        active_missing = self._create_coordination_with_place(subject="Aktivní bez PBP")

        expired_missing = bozp_coordination_service.create_coordination(
            subject="Ukončená bez PBP",
            meeting_date=self.today - timedelta(days=400),
            valid_from=self.today - timedelta(days=400),
            valid_to=self.today - timedelta(days=5),
        )
        coordination_workplace_service.add(
            expired_missing.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

        inactive_missing = self._create_coordination_with_place(subject="Neaktivní bez PBP")
        bozp_coordination_service.deactivate(inactive_missing.id)

        stale = self._create_coordination_with_place(subject="Zastaralá")
        coordination_pbp_attachment_service.generate_or_update(stale.id)
        self._create_measure(description="Nové pravidlo", event_name="new")

        archived = self._create_coordination_with_place(subject="Archiv bez PBP")
        from moduly.koordinace_bozp.sluzby.coordination_lifecycle_service import (
            coordination_lifecycle_service,
        )

        coordination_lifecycle_service.transition(
            archived.id,
            BOZP_COORDINATION_STATUS_ARCHIVED,
        )

        missing_ids = {
            item.id
            for item in bozp_coordination_service.get_all(
                include_inactive=True,
                pbp_filter=PBP_FILTER_MISSING,
                today=self.today,
            )
        }
        needs_ids = {
            item.id
            for item in bozp_coordination_service.get_all(
                include_inactive=True,
                pbp_filter=PBP_FILTER_NEEDS_UPDATE,
                today=self.today,
            )
        }

        self.assertIn(active_missing.id, missing_ids)
        self.assertNotIn(expired_missing.id, missing_ids)
        self.assertNotIn(inactive_missing.id, missing_ids)
        self.assertNotIn(archived.id, missing_ids)

        self.assertIn(stale.id, needs_ids)
        self.assertNotIn(expired_missing.id, needs_ids)
        self.assertNotIn(inactive_missing.id, needs_ids)

    def test_check_does_not_create_revision_or_write(self) -> None:
        self._create_measure(description="Kontrola bez zápisu")
        coordination = self._create_coordination_with_place(subject="Bez zápisu")
        before = self._revision_count(coordination.id)
        self.assertEqual(before, 0)

        with patch.object(
            coordination_pbp_attachment_service,
            "generate_or_update",
            side_effect=AssertionError("generate_or_update nesmí být voláno"),
        ), patch.object(
            coordination_pbp_attachment_service.repository,
            "add",
            side_effect=AssertionError("repository.add nesmí být voláno"),
        ), patch.object(
            coordination_pbp_attachment_service,
            "_write_odt",
            side_effect=AssertionError("_write_odt nesmí být voláno"),
        ):
            result = evaluate_pbp_freshness(coordination, today=self.today)

        self.assertEqual(result.state, PBP_FRESHNESS_MISSING)
        self.assertEqual(self._revision_count(coordination.id), 0)
        self.assertIsNone(coordination_pbp_attachment_service.get_current(coordination.id))

    def test_table_column_and_page_filter(self) -> None:
        self._create_measure(description="UI pravidlo")
        missing = self._create_coordination_with_place(subject="UI bez přílohy")
        current = self._create_coordination_with_place(subject="UI aktuální")
        coordination_pbp_attachment_service.generate_or_update(current.id)

        table = BozpCoordinationTable()
        items = bozp_coordination_service.get_all(include_inactive=True, today=self.today)
        table.load_coordinations(items, today=self.today)
        labels_by_id = {}
        colors_by_id = {}
        for row in range(table.rowCount()):
            cid = int(table.item(row, 0).text())
            pbp_item = table.item(row, COL_PBP)
            labels_by_id[cid] = pbp_item.text()
            colors_by_id[cid] = pbp_item.foreground().color()
            self.assertTrue(pbp_item.toolTip())

        self.assertEqual(labels_by_id[missing.id], "Nevytvořena")
        self.assertEqual(labels_by_id[current.id], "Aktuální")
        self.assertEqual(
            colors_by_id[missing.id],
            QColor(PBP_FRESHNESS_COLORS[PBP_FRESHNESS_MISSING]),
        )
        self.assertEqual(
            colors_by_id[current.id],
            QColor(PBP_FRESHNESS_COLORS[PBP_FRESHNESS_CURRENT]),
        )

        page = KoordinaceBozpPage()
        index = page.pbp_filter.findData(PBP_FILTER_MISSING)
        self.assertGreaterEqual(index, 0)
        page.pbp_filter.setCurrentIndex(index)
        page.refresh()
        visible_ids = {
            int(page.table.item(row, 0).text())
            for row in range(page.table.rowCount())
        }
        self.assertIn(missing.id, visible_ids)
        self.assertNotIn(current.id, visible_ids)

    def test_detail_tab_highlights_update_when_stale(self) -> None:
        self._create_measure(description="Detail A", event_name="d1")
        coordination = self._create_coordination_with_place(subject="Detail")
        coordination_pbp_attachment_service.generate_or_update(coordination.id)
        self._create_measure(description="Detail B", event_name="d2")

        dialog = BozpCoordinationDialog(None, coordination=coordination)
        tab = dialog.pbp_attachment_tab
        tab.refresh_status()
        self.assertEqual(
            tab.freshness_label.text(),
            PBP_FRESHNESS_DETAIL_MESSAGES[PBP_FRESHNESS_NEEDS_UPDATE],
        )
        self.assertTrue(tab.update_btn.font().bold())


if __name__ == "__main__":
    unittest.main()
