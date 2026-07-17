"""Fáze R20g – slučování posouzení podle ohrožených skupin."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.ai_oponentni.constants import AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_proposal_package import AiProposalPackageRecord
    from core.ai_oponentni.proposal_package_types import (
        AiProposalPackage,
        AiProposalPackageAssessment,
        AiProposalPackageMeasure,
    )
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_CRITICAL,
        RISK_SEVERITY_MINOR,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_ALL
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
        HazardLibraryTemplateAssessment,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment_exposed_group import (
        HazardLibraryTemplateAssessmentExposedGroup,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_legal_link import (
        HazardLibraryTemplateLegalLink,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_measure import (
        HazardLibraryTemplateExistingMeasure,
        HazardLibraryTemplateRequiredMeasure,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
        HazardCatalogPackageAmbiguousGroupError,
        hazard_catalog_package_incorporate_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        hazard_catalog_source_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_assessment_service import (
        hazard_library_template_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_existing_measure_service import (
        hazard_library_template_existing_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_required_measure_service import (
        hazard_library_template_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class RizeniRizikPhaseR20gTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session

        with get_session() as session:
            session.execute(delete(AiProposalPackageRecord))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(HazardLibraryTemplateRevision))
            session.execute(delete(HazardLibraryTemplateLegalLink))
            session.execute(delete(HazardLibraryTemplateRequiredMeasure))
            session.execute(delete(HazardLibraryTemplateExistingMeasure))
            session.execute(delete(HazardLibraryTemplateAssessmentExposedGroup))
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.employees = ensure_exposed_group("Zaměstnanci daného pracoviště")
        self.contractors = ensure_exposed_group("Dodavatelé")
        self.visitors = ensure_exposed_group("Návštěvy")

        self.template = hazard_library_template_service.create_template(
            name=f"R20g šablona {id(self)}",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        self.event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Pád předmětu",
        )
        self.provider = hazard_catalog_source_peer_review_provider
        self.export_dir = Path(tempfile.mkdtemp())
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            self.export_dir / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        self.review = export_result.review
        self.initial_version = hazard_library_template_service.get_by_id(
            self.template.id,
        ).version_number
        self.event_export_id = next(
            key
            for key, value in hazard_catalog_package_incorporate_service.get_export_id_map(
                self.review.id,
            ).items()
            if isinstance(value, dict)
            and value.get("kind") == "event"
            and int(value.get("id")) == self.event.id
        )

    def _store_package(self, package: AiProposalPackage) -> AiProposalPackageRecord:
        updated = ai_peer_review_service.finalize_package_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text="{}",
            ai_model="Test",
            accepted=[package],
            rejected=[],
        )
        stored = ai_peer_review_service.get_packages_for_review(updated.id)
        self.assertEqual(len(stored), 1)
        return stored[0]

    def _extend_package(
        self,
        *,
        groups: tuple[str, ...],
        severity: str = RISK_SEVERITY_MODERATE,
        conclusion: str = "Nový závěr AI.",
        existing_measures: tuple[str, ...] = ("Nové existující opatření",),
        required_measures: tuple[str, ...] = ("Nové potřebné opatření",),
    ) -> AiProposalPackage:
        return AiProposalPackage(
            package_id=f"PACKAGE-R20G-{id(groups)}",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
            target_event_export_id=self.event_export_id,
            event=None,
            assessments=(
                AiProposalPackageAssessment(
                    exposed_group=groups[0],
                    exposed_groups=groups,
                    severity=severity,
                    conclusion=conclusion,
                    existing_measures=tuple(
                        AiProposalPackageMeasure(description=text)
                        for text in existing_measures
                    ),
                    required_measures=tuple(
                        AiProposalPackageMeasure(description=text)
                        for text in required_measures
                    ),
                ),
            ),
            legal_links=(),
            reasoning="R20g test",
        )

    def _active_assessments(self):
        return hazard_library_template_assessment_service.get_for_event(
            self.event.id,
            include_inactive=False,
        )

    def test_one_existing_and_one_new_group(self) -> None:
        existing = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.event.id,
            exposed_group_ids=[self.employees.id],
            severity=RISK_SEVERITY_MINOR,
            conclusion="Ověřit stabilní uložení předmětů.",
        )
        hazard_library_template_existing_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=existing.id,
            description="Původní existující opatření",
        )

        record = self._store_package(
            self._extend_package(
                groups=("Zaměstnanci daného pracoviště", "Dodavatelé"),
                severity=RISK_SEVERITY_CRITICAL,
                conclusion="Prověřit stav a nosnost polic.",
                existing_measures=("Původní existující opatření", "Další opatření"),
                required_measures=("Nové potřebné opatření",),
            ),
        )
        result = hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=record.id,
        )

        self.assertEqual(result.assessment_count, 1)
        self.assertEqual(result.merged_assessment_count, 1)
        self.assertEqual(result.new_revision_number, self.initial_version + 1)

        rows = self._active_assessments()
        self.assertEqual(len(rows), 2)

        reloaded = hazard_library_template_assessment_service.get_by_id(existing.id)
        self.assertEqual(reloaded.severity, RISK_SEVERITY_CRITICAL)
        self.assertIn("Ověřit stabilní uložení předmětů.", reloaded.conclusion)
        self.assertIn("Prověřit stav a nosnost polic.", reloaded.conclusion)
        self.assertEqual(
            hazard_library_template_assessment_service.get_group_ids(existing.id),
            [self.employees.id],
        )

        existing_measures = {
            measure.description
            for measure in hazard_library_template_existing_measure_service.get_for_assessment(
                existing.id,
                include_inactive=False,
            )
        }
        self.assertEqual(
            existing_measures,
            {"Původní existující opatření", "Další opatření"},
        )

        new_rows = [
            row
            for row in rows
            if row.assessment.id != existing.id
        ]
        self.assertEqual(len(new_rows), 1)
        self.assertEqual(
            set(new_rows[0].exposed_group_ids),
            {self.contractors.id},
        )
        self.assertNotIn(self.employees.id, new_rows[0].exposed_group_ids)

    def test_one_existing_and_two_new_groups(self) -> None:
        existing = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.event.id,
            exposed_group_ids=[self.employees.id],
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Původní.",
        )
        record = self._store_package(
            self._extend_package(
                groups=(
                    "Zaměstnanci daného pracoviště",
                    "Dodavatelé",
                    "Návštěvy",
                ),
            ),
        )
        result = hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        self.assertEqual(result.assessment_count, 1)
        self.assertEqual(result.merged_assessment_count, 1)

        rows = self._active_assessments()
        self.assertEqual(len(rows), 2)
        new_row = next(row for row in rows if row.assessment.id != existing.id)
        self.assertEqual(
            set(new_row.exposed_group_ids),
            {self.contractors.id, self.visitors.id},
        )
        self.assertNotIn(self.employees.id, new_row.exposed_group_ids)

    def test_all_groups_already_exist(self) -> None:
        existing = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.event.id,
            exposed_group_ids=[self.employees.id, self.contractors.id],
            severity=RISK_SEVERITY_MINOR,
            conclusion="Stejný závěr.",
        )
        record = self._store_package(
            self._extend_package(
                groups=("Zaměstnanci daného pracoviště", "Dodavatelé"),
                severity=RISK_SEVERITY_MINOR,
                conclusion="Stejný závěr.",
                existing_measures=("Jen nové",),
                required_measures=(),
            ),
        )
        result = hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        self.assertEqual(result.assessment_count, 0)
        self.assertEqual(result.merged_assessment_count, 1)
        self.assertEqual(len(self._active_assessments()), 1)

        reloaded = hazard_library_template_assessment_service.get_by_id(existing.id)
        self.assertEqual(reloaded.conclusion, "Stejný závěr.")
        measures = {
            measure.description
            for measure in hazard_library_template_existing_measure_service.get_for_assessment(
                existing.id,
                include_inactive=False,
            )
        }
        self.assertIn("Jen nové", measures)

    def test_no_groups_exist_yet(self) -> None:
        record = self._store_package(
            self._extend_package(groups=("Dodavatelé", "Návštěvy")),
        )
        result = hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        self.assertEqual(result.assessment_count, 1)
        self.assertEqual(result.merged_assessment_count, 0)
        rows = self._active_assessments()
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            set(rows[0].exposed_group_ids),
            {self.contractors.id, self.visitors.id},
        )

    def test_stricter_severity_and_conclusion_merge(self) -> None:
        existing = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.event.id,
            exposed_group_ids=[self.employees.id],
            severity=RISK_SEVERITY_CRITICAL,
            conclusion="Ověřit stabilní uložení předmětů.",
        )
        record = self._store_package(
            self._extend_package(
                groups=("Zaměstnanci daného pracoviště",),
                severity=RISK_SEVERITY_MINOR,
                conclusion="Prověřit stav a nosnost polic.",
                existing_measures=(),
                required_measures=(),
            ),
        )
        hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        reloaded = hazard_library_template_assessment_service.get_by_id(existing.id)
        self.assertEqual(reloaded.severity, RISK_SEVERITY_CRITICAL)
        self.assertEqual(
            reloaded.conclusion,
            "Ověřit stabilní uložení předmětů.\n\nPrověřit stav a nosnost polic.",
        )

    def test_duplicate_conclusion_not_appended(self) -> None:
        existing = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.event.id,
            exposed_group_ids=[self.employees.id],
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Ověřit stabilní uložení předmětů.",
        )
        record = self._store_package(
            self._extend_package(
                groups=("Zaměstnanci daného pracoviště",),
                conclusion="  ověřit   stabilní uložení předmětů. ",
                existing_measures=(),
                required_measures=(),
            ),
        )
        hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        reloaded = hazard_library_template_assessment_service.get_by_id(existing.id)
        self.assertEqual(reloaded.conclusion, "Ověřit stabilní uložení předmětů.")

    def test_duplicate_measures_not_recreated(self) -> None:
        existing = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.event.id,
            exposed_group_ids=[self.employees.id],
            severity=RISK_SEVERITY_MODERATE,
        )
        hazard_library_template_existing_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=existing.id,
            description="Zábradlí",
        )
        hazard_library_template_required_measure_service.create_measure(
            template_id=self.template.id,
            template_assessment_id=existing.id,
            description="Kontrola zábradlí",
        )
        record = self._store_package(
            self._extend_package(
                groups=("Zaměstnanci daného pracoviště",),
                existing_measures=("  zábradlí ", "Nové EO"),
                required_measures=("Kontrola zábradlí", "Nové PO"),
            ),
        )
        result = hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        self.assertEqual(result.existing_measure_count, 1)
        self.assertEqual(result.required_measure_count, 1)

        existing_texts = [
            measure.description
            for measure in hazard_library_template_existing_measure_service.get_for_assessment(
                existing.id,
                include_inactive=False,
            )
        ]
        required_texts = [
            measure.description
            for measure in hazard_library_template_required_measure_service.get_for_assessment(
                existing.id,
                include_inactive=False,
            )
        ]
        self.assertEqual(existing_texts.count("Zábradlí"), 1)
        self.assertIn("Nové EO", existing_texts)
        self.assertEqual(required_texts.count("Kontrola zábradlí"), 1)
        self.assertIn("Nové PO", required_texts)

    def test_ambiguous_group_requires_override(self) -> None:
        first = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.event.id,
            exposed_group_ids=[self.employees.id],
            severity=RISK_SEVERITY_MINOR,
            conclusion="První",
            active=False,
        )
        # Temporarily allow second active with same group by inserting via repository
        # after deactivating uniqueness path: create second with contractors, then
        # force-add employees to both active assessments through direct session.
        second = hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.event.id,
            exposed_group_ids=[self.contractors.id],
            severity=RISK_SEVERITY_MODERATE,
            conclusion="Druhé",
        )
        from core.database.session import get_session
        from moduly.rizeni_rizik.modely.hazard_library_template_assessment_exposed_group import (
            HazardLibraryTemplateAssessmentExposedGroup as Join,
        )

        with get_session() as session:
            first_db = session.get(HazardLibraryTemplateAssessment, first.id)
            first_db.active = True
            session.add(first_db)
            session.add(
                Join(
                    assessment_id=second.id,
                    exposed_group_id=self.employees.id,
                    sort_order=2,
                ),
            )
            session.commit()

        record = self._store_package(
            self._extend_package(groups=("Zaměstnanci daného pracoviště",)),
        )
        with self.assertRaises(HazardCatalogPackageAmbiguousGroupError) as caught:
            hazard_catalog_package_incorporate_service.incorporate_package(
                template_id=self.template.id,
                package_record_id=record.id,
            )
        self.assertEqual(caught.exception.group_id, self.employees.id)
        self.assertEqual(len(caught.exception.candidates), 2)

        result = hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=record.id,
            group_assessment_overrides={self.employees.id: second.id},
        )
        self.assertEqual(result.assessment_count, 0)
        self.assertEqual(result.merged_assessment_count, 1)
        reloaded = hazard_library_template_assessment_service.get_by_id(second.id)
        self.assertIn("Nový závěr AI.", reloaded.conclusion)
        template = hazard_library_template_service.get_by_id(self.template.id)
        self.assertEqual(template.version_number, self.initial_version + 1)

    def test_revision_bumped_once(self) -> None:
        hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.event.id,
            exposed_group_ids=[self.employees.id],
            severity=RISK_SEVERITY_MODERATE,
        )
        record = self._store_package(
            self._extend_package(
                groups=("Zaměstnanci daného pracoviště", "Dodavatelé"),
            ),
        )
        result = hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        self.assertEqual(result.new_revision_number, self.initial_version + 1)
        template = hazard_library_template_service.get_by_id(self.template.id)
        self.assertEqual(template.version_number, self.initial_version + 1)

        from sqlalchemy import func, select

        from core.database.session import get_session

        with get_session() as session:
            count = session.scalar(
                select(func.count()).select_from(HazardLibraryTemplateRevision).where(
                    HazardLibraryTemplateRevision.template_id == self.template.id,
                    HazardLibraryTemplateRevision.revision_number
                    == result.new_revision_number,
                ),
            )
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
