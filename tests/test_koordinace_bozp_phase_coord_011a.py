"""Fáze COORD-011a – náhled a kontrola koordinačního protokolu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication
from sqlalchemy import delete, func, select

_TMP = Path(tempfile.mkdtemp(prefix="coord-011a-"))
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
        ATTACHMENT_TYPE_CONTRACTOR_RISKS,
        ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP,
        ATTACHMENT_TYPE_OTHER,
        BOZP_COORDINATION_STATUS_ARCHIVED,
        MEASURE_CATEGORY_COMMUNICATION,
        MEASURE_CATEGORY_PPE,
        PROTOCOL_WARNING_EMPLOYER_WITHOUT_ACTIVITY,
        PROTOCOL_WARNING_EXPIRED_VALIDITY,
        PROTOCOL_WARNING_INACTIVE_OR_ARCHIVED,
        PROTOCOL_WARNING_MISSING_COORDINATOR,
        PROTOCOL_WARNING_MISSING_MEASURES,
        PROTOCOL_WARNING_MISSING_PBP_SNAPSHOT,
        PROTOCOL_WARNING_MISSING_WORKPLACE,
        PROTOCOL_WARNING_RISKS_NOT_SUBMITTED,
        PROTOCOL_WARNING_RISKS_WITHOUT_ATTACHMENT,
        PROTOCOL_WARNING_STALE_PBP_SNAPSHOT,
        RISK_SUBMISSION_METHOD_EMAIL,
    )
    from moduly.koordinace_bozp.modely.bozp_coordination import BozpCoordination
    from moduly.koordinace_bozp.modely.coordination_attachment import (
        CoordinationAttachment,
    )
    from moduly.koordinace_bozp.modely.coordination_contact import CoordinationContact
    from moduly.koordinace_bozp.modely.coordination_coordinator import (
        CoordinationCoordinator,
    )
    from moduly.koordinace_bozp.modely.coordination_employer import CoordinationEmployer
    from moduly.koordinace_bozp.modely.coordination_employer_activity import (
        CoordinationEmployerActivity,
    )
    from moduly.koordinace_bozp.modely.coordination_employer_risk_submission import (
        CoordinationEmployerRiskSubmission,
    )
    from moduly.koordinace_bozp.modely.coordination_measure import CoordinationMeasure
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
    from moduly.koordinace_bozp.sluzby.coordination_attachment_service import (
        coordination_attachment_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_contact_service import (
        coordination_contact_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_coordinator_service import (
        coordination_coordinator_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_activity_service import (
        coordination_employer_activity_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_employer_service import (
        coordination_employer_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_measure_service import (
        coordination_measure_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_participant_service import (
        coordination_participant_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_pbp_attachment_service import (
        coordination_pbp_attachment_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_protocol_builder import (
        coordination_protocol_builder,
    )
    from moduly.koordinace_bozp.sluzby.coordination_risk_submission_service import (
        coordination_risk_submission_service,
    )
    from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
        coordination_workplace_service,
    )
    from moduly.koordinace_bozp.ui.bozp_coordination_dialog import BozpCoordinationDialog
    from moduly.koordinace_bozp.ui.coordination_protocol_preview_dialog import (
        CoordinationProtocolPreviewDialog,
    )
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


class KoordinaceBozpPhaseCoord011aTestCase(unittest.TestCase):
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
        self.group = ensure_exposed_group("COORD011a skupina")
        self.person = person_service.create_person(
            first_name="Coord",
            last_name="Protocol",
        )
        self.operation = settings_service.save_workplace(
            name="COORD011a provoz",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="COORD011a pracoviště",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.today = date.today()

    def _warning_codes(self, result) -> set[str]:
        return {item.code for item in result.warnings}

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

    def _create_pbp_measure(self, *, description: str, event_name: str = "Událost"):
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

    def _create_base_coordination(self, **kwargs):
        params = {
            "subject": "COORD-011a",
            "meeting_date": self.today,
            "place": "Jednací místnost",
            "valid_from": self.today,
            "valid_to": self.today + timedelta(days=365),
        }
        params.update(kwargs)
        return bozp_coordination_service.create_coordination(**params)

    def _add_workplace(self, coordination_id: int):
        return coordination_workplace_service.add(
            coordination_id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )

    def _set_coordinator(self, coordination_id: int, employer_id: int | None = None):
        if employer_id is None:
            employer = coordination_employer_service.ensure_main_employer(coordination_id)
            employer_id = employer.id
        participant = coordination_participant_service.add_manual(
            employer_id,
            full_name="Koordinátor Test",
            role="koordinátor BOZP",
            phone="+420111222333",
            email="koordinator@example.com",
        )
        return coordination_coordinator_service.set_coordinator(
            coordination_id,
            employer_id=employer_id,
            participant_id=participant.id,
        )

    def _add_activity(self, employer_id: int, *, name: str = "Montáž"):
        return coordination_employer_activity_service.add(
            employer_id,
            activity_name=name,
        )

    def _add_measure(self, coordination_id: int, *, title: str = "Opatření", category=None):
        return coordination_measure_service.add(
            coordination_id,
            title=title,
            category=category or MEASURE_CATEGORY_COMMUNICATION,
        )

    def _complete_coordination(self, *, with_contractor: bool = False):
        """Kompletní koordinace bez varování (volitelně s dodavatelem a přílohou)."""
        self._create_pbp_measure(description="Používej brýle")
        coordination = self._create_base_coordination()
        place = self._add_workplace(coordination.id)
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        self._set_coordinator(coordination.id, main.id)
        self._add_activity(main.id, name="Údržba")
        self._add_measure(coordination.id, title="Hlásit události")
        coordination_contact_service.add(
            coordination.id,
            custom_name="Ohlašovna",
            phone="+420999888777",
            email="",
        )
        coordination_pbp_attachment_service.generate_or_update(coordination.id)

        contractor = None
        if with_contractor:
            contractor = coordination_employer_service.add_participant(
                coordination.id,
                company_name="Dodavatel Alfa s.r.o.",
                abbreviation="ALF",
            )
            self._add_activity(contractor.id, name="Svařování")
            coordination_risk_submission_service.save_submission(
                contractor.id,
                submission_method=RISK_SUBMISSION_METHOD_EMAIL,
                submission_date=self.today,
                document_reference="e-mail",
            )
            source = _TMP / "rizika-alfa.pdf"
            source.write_bytes(b"%PDF-1.4 alfa")
            coordination_attachment_service.add_file(
                coordination_id=coordination.id,
                coordination_employer_id=contractor.id,
                source_path=source,
            )

        return (
            bozp_coordination_service.get_by_id(coordination.id),
            main,
            place,
            contractor,
        )

    def test_complete_coordination_without_warnings(self) -> None:
        coordination, *_ = self._complete_coordination(with_contractor=True)
        result = coordination_protocol_builder.build(coordination.id, today=self.today)
        self.assertEqual(result.warnings, [])
        self.assertEqual(result.summary.warnings_total, 0)
        data = result.protocol_data
        self.assertIsNotNone(data["coordinator"])
        self.assertEqual(len(data["workplaces"]), 1)
        self.assertIsNotNone(data["pbp_snapshot"])
        self.assertEqual(len(data["risk_handovers"]), 1)

    def test_missing_coordinator_warning(self) -> None:
        self._create_pbp_measure(description="Pravidlo")
        coordination = self._create_base_coordination()
        self._add_workplace(coordination.id)
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        self._add_activity(main.id)
        self._add_measure(coordination.id)
        coordination_pbp_attachment_service.generate_or_update(coordination.id)
        result = coordination_protocol_builder.build(coordination.id, today=self.today)
        self.assertIn(PROTOCOL_WARNING_MISSING_COORDINATOR, self._warning_codes(result))
        critical = [
            item
            for item in result.warnings
            if item.code == PROTOCOL_WARNING_MISSING_COORDINATOR
        ]
        self.assertEqual(critical[0].severity, "critical")

    def test_missing_workplace_warning(self) -> None:
        coordination = self._create_base_coordination()
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        self._set_coordinator(coordination.id, main.id)
        self._add_activity(main.id)
        self._add_measure(coordination.id)
        result = coordination_protocol_builder.build(coordination.id, today=self.today)
        self.assertIn(PROTOCOL_WARNING_MISSING_WORKPLACE, self._warning_codes(result))

    def test_employer_without_activity_warning(self) -> None:
        self._create_pbp_measure(description="Pravidlo")
        coordination = self._create_base_coordination()
        self._add_workplace(coordination.id)
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        self._set_coordinator(coordination.id, main.id)
        contractor = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Bez činnosti s.r.o.",
            abbreviation="BEZ",
        )
        self._add_activity(main.id)
        self._add_measure(coordination.id)
        coordination_pbp_attachment_service.generate_or_update(coordination.id)
        source = _TMP / "rizika-bez.pdf"
        source.write_bytes(b"%PDF-1.4 bez")
        coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_METHOD_EMAIL,
            submission_date=self.today,
        )
        coordination_attachment_service.add_file(
            coordination_id=coordination.id,
            coordination_employer_id=contractor.id,
            source_path=source,
        )
        result = coordination_protocol_builder.build(coordination.id, today=self.today)
        self.assertIn(
            PROTOCOL_WARNING_EMPLOYER_WITHOUT_ACTIVITY,
            self._warning_codes(result),
        )
        warning = next(
            item
            for item in result.warnings
            if item.code == PROTOCOL_WARNING_EMPLOYER_WITHOUT_ACTIVITY
        )
        self.assertEqual(warning.related_entity_id, contractor.id)

    def test_missing_pbp_snapshot_warning(self) -> None:
        coordination = self._create_base_coordination()
        self._add_workplace(coordination.id)
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        self._set_coordinator(coordination.id, main.id)
        self._add_activity(main.id)
        self._add_measure(coordination.id)
        result = coordination_protocol_builder.build(coordination.id, today=self.today)
        self.assertIn(
            PROTOCOL_WARNING_MISSING_PBP_SNAPSHOT,
            self._warning_codes(result),
        )

    def test_stale_pbp_snapshot_warning(self) -> None:
        self._create_pbp_measure(description="První pravidlo", event_name="A")
        coordination = self._create_base_coordination()
        self._add_workplace(coordination.id)
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        self._set_coordinator(coordination.id, main.id)
        self._add_activity(main.id)
        self._add_measure(coordination.id)
        coordination_pbp_attachment_service.generate_or_update(coordination.id)
        self._create_pbp_measure(description="Nové pravidlo", event_name="B")
        result = coordination_protocol_builder.build(coordination.id, today=self.today)
        self.assertIn(
            PROTOCOL_WARNING_STALE_PBP_SNAPSHOT,
            self._warning_codes(result),
        )

    def test_contractor_risks_not_submitted(self) -> None:
        coordination, main, _, _ = self._complete_coordination(with_contractor=False)
        contractor = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Nepředal s.r.o.",
            abbreviation="NEP",
        )
        self._add_activity(contractor.id, name="Práce")
        result = coordination_protocol_builder.build(coordination.id, today=self.today)
        self.assertIn(
            PROTOCOL_WARNING_RISKS_NOT_SUBMITTED,
            self._warning_codes(result),
        )

    def test_contractor_risks_without_attachment(self) -> None:
        coordination, _, _, _ = self._complete_coordination(with_contractor=False)
        contractor = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Bez přílohy s.r.o.",
            abbreviation="BPR",
        )
        self._add_activity(contractor.id, name="Práce")
        coordination_risk_submission_service.save_submission(
            contractor.id,
            submission_method=RISK_SUBMISSION_METHOD_EMAIL,
            submission_date=self.today,
            document_reference="e-mail bez souboru",
        )
        result = coordination_protocol_builder.build(coordination.id, today=self.today)
        self.assertIn(
            PROTOCOL_WARNING_RISKS_WITHOUT_ATTACHMENT,
            self._warning_codes(result),
        )

    def test_expired_validity_warning(self) -> None:
        coordination, *_ = self._complete_coordination(with_contractor=False)
        bozp_coordination_service.update_coordination(
            coordination.id,
            subject=coordination.subject,
            meeting_date=coordination.meeting_date,
            place=coordination.place or "",
            status=coordination.status,
            note=coordination.note or "",
            valid_from=self.today - timedelta(days=400),
            valid_to=self.today - timedelta(days=1),
        )
        result = coordination_protocol_builder.build(coordination.id, today=self.today)
        self.assertIn(PROTOCOL_WARNING_EXPIRED_VALIDITY, self._warning_codes(result))

    def test_archived_coordination_warning(self) -> None:
        coordination, *_ = self._complete_coordination(with_contractor=False)
        from moduly.koordinace_bozp.sluzby.coordination_lifecycle_service import (
            coordination_lifecycle_service,
        )

        coordination_lifecycle_service.transition(
            coordination.id,
            BOZP_COORDINATION_STATUS_ARCHIVED,
        )
        result = coordination_protocol_builder.build(coordination.id, today=self.today)
        self.assertIn(
            PROTOCOL_WARNING_INACTIVE_OR_ARCHIVED,
            self._warning_codes(result),
        )

    def test_summary_counts(self) -> None:
        coordination, main, place, contractor = self._complete_coordination(
            with_contractor=True
        )
        assert contractor is not None
        coordination_participant_service.add_manual(
            contractor.id,
            full_name="Účastník Dodavatel",
            role="vedoucí",
            phone="+420123",
            email="u@example.com",
        )
        result = coordination_protocol_builder.build(coordination.id, today=self.today)
        summary = result.summary
        self.assertEqual(summary.active_employers, 2)
        self.assertEqual(summary.active_participants, 2)  # koordinátor + účastník
        self.assertEqual(summary.active_workplaces, 1)
        self.assertEqual(summary.active_activities, 2)
        self.assertEqual(summary.active_measures, 1)
        self.assertEqual(summary.active_contacts, 1)
        self.assertGreaterEqual(summary.pbp_rules_count, 1)
        self.assertEqual(summary.active_attachments, 2)  # PBP revize + rizika
        self.assertEqual(summary.warnings_total, 0)
        self.assertIs(place.id, place.id)

    def test_grouping_and_sorting(self) -> None:
        self._create_pbp_measure(description="Pravidlo seskupení")
        coordination = self._create_base_coordination()
        place = self._add_workplace(coordination.id)
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        beta = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Beta s.r.o.",
            abbreviation="BET",
        )
        alfa = coordination_employer_service.add_participant(
            coordination.id,
            company_name="Alfa s.r.o.",
            abbreviation="ALF",
        )
        # Explicitní sort_order: Alfa před Betou (po hlavním).
        with get_session() as session:
            session_alfa = session.get(CoordinationEmployer, alfa.id)
            session_beta = session.get(CoordinationEmployer, beta.id)
            assert session_alfa is not None and session_beta is not None
            session_alfa.sort_order = 10
            session_beta.sort_order = 20
            session.commit()

        self._set_coordinator(coordination.id, main.id)
        coordination_participant_service.add_manual(
            alfa.id,
            full_name="Alfa osoba",
            role="technik",
            phone="+4201",
            email="a@example.com",
        )
        coordination_participant_service.add_manual(
            beta.id,
            full_name="Beta osoba",
            role="technik",
            phone="+4202",
            email="b@example.com",
        )
        self._add_activity(main.id, name="Hlavní činnost")
        self._add_activity(alfa.id, name="Alfa činnost")
        self._add_activity(beta.id, name="Beta činnost")
        self._add_measure(
            coordination.id,
            title="PPE opatření",
            category=MEASURE_CATEGORY_PPE,
        )
        self._add_measure(
            coordination.id,
            title="Komunikační opatření",
            category=MEASURE_CATEGORY_COMMUNICATION,
        )
        coordination_pbp_attachment_service.generate_or_update(coordination.id)

        for employer, name in ((alfa, "alfa"), (beta, "beta")):
            coordination_risk_submission_service.save_submission(
                employer.id,
                submission_method=RISK_SUBMISSION_METHOD_EMAIL,
                submission_date=self.today,
            )
            source = _TMP / f"rizika-{name}.pdf"
            source.write_bytes(b"%PDF-1.4 " + name.encode())
            coordination_attachment_service.add_file(
                coordination_id=coordination.id,
                coordination_employer_id=employer.id,
                source_path=source,
                attachment_type=ATTACHMENT_TYPE_CONTRACTOR_RISKS,
            )
        other = _TMP / "jina-priloha.pdf"
        other.write_bytes(b"%PDF-1.4 other")
        coordination_attachment_service.add_file(
            coordination_id=coordination.id,
            coordination_employer_id=alfa.id,
            source_path=other,
            attachment_type=ATTACHMENT_TYPE_OTHER,
            description="Jiná",
        )

        result = coordination_protocol_builder.build(coordination.id, today=self.today)
        employers = result.protocol_data["employers"]
        self.assertTrue(employers[0]["is_main"])
        self.assertEqual(
            [item["abbreviation"] for item in employers[1:]],
            ["ALF", "BET"],
        )

        participant_names = [
            group["participants"][0]["full_name"]
            for group in result.protocol_data["participants_by_employer"]
            if group["participants"]
            and not group["employer"]["is_main"]
        ]
        self.assertEqual(participant_names, ["Alfa osoba", "Beta osoba"])

        activity_names = [
            group["activities"][0]["activity_name"]
            for group in result.protocol_data["activities_by_employer"]
        ]
        self.assertEqual(
            activity_names,
            ["Hlavní činnost", "Alfa činnost", "Beta činnost"],
        )

        categories = [
            group["category"]
            for group in result.protocol_data["measures_by_category"]
        ]
        self.assertEqual(
            categories,
            [MEASURE_CATEGORY_COMMUNICATION, MEASURE_CATEGORY_PPE],
        )

        attachment_types = [
            group["attachment_type"]
            for group in result.protocol_data["attachments_by_group"]
        ]
        self.assertEqual(
            attachment_types,
            [
                ATTACHMENT_TYPE_MAIN_EMPLOYER_PBP,
                ATTACHMENT_TYPE_CONTRACTOR_RISKS,
                ATTACHMENT_TYPE_OTHER,
            ],
        )
        self.assertEqual(place.coordination_id, coordination.id)

    def test_preview_does_not_write_database(self) -> None:
        coordination, *_ = self._complete_coordination(with_contractor=True)
        before_revisions = self._revision_count(coordination.id)
        before = bozp_coordination_service.get_by_id(coordination.id)
        assert before is not None
        before_updated = before.updated_at

        result = coordination_protocol_builder.build(coordination.id, today=self.today)
        self.assertEqual(result.summary.warnings_total, 0)

        after = bozp_coordination_service.get_by_id(coordination.id)
        assert after is not None
        self.assertEqual(after.updated_at, before_updated)
        self.assertEqual(self._revision_count(coordination.id), before_revisions)

        dialog = CoordinationProtocolPreviewDialog(None, coordination_id=coordination.id)
        self.assertIn("Připraveno", dialog.status_label.text())
        dialog.close()
        self.assertEqual(self._revision_count(coordination.id), before_revisions)

    def test_dialog_has_preview_button(self) -> None:
        coordination, *_ = self._complete_coordination(with_contractor=False)
        dialog = BozpCoordinationDialog(None, coordination=coordination)
        self.assertTrue(hasattr(dialog, "preview_btn"))
        self.assertEqual(dialog.preview_btn.text(), "Náhled protokolu")
        self.assertTrue(dialog.preview_btn.isEnabled())
        dialog.close()

        new_dialog = BozpCoordinationDialog(None)
        self.assertFalse(new_dialog.preview_btn.isEnabled())
        new_dialog.close()

    def test_missing_measures_warning(self) -> None:
        self._create_pbp_measure(description="Pravidlo")
        coordination = self._create_base_coordination()
        self._add_workplace(coordination.id)
        main = coordination_employer_service.ensure_main_employer(coordination.id)
        self._set_coordinator(coordination.id, main.id)
        self._add_activity(main.id)
        coordination_pbp_attachment_service.generate_or_update(coordination.id)
        result = coordination_protocol_builder.build(coordination.id, today=self.today)
        self.assertIn(PROTOCOL_WARNING_MISSING_MEASURES, self._warning_codes(result))


if __name__ == "__main__":
    unittest.main()
