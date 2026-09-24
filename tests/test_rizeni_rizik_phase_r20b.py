"""Fáze R20b – UI a zapracování návrhových balíků."""

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

    from core.ai_oponentni.constants import (
        AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
        AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
    )
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_proposal_package import (
        PACKAGE_STATUS_INCORPORATED,
        PACKAGE_STATUS_PENDING,
        PACKAGE_STATUS_REJECTED,
        AiProposalPackageRecord,
    )
    from core.ai_oponentni.proposal_package_types import (
        AiProposalPackage,
        AiProposalPackageAssessment,
        AiProposalPackageEvent,
        AiProposalPackageLegalLink,
        AiProposalPackageMeasure,
    )
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.sluzby.proposal_package_detail import (
        format_proposal_package_detail,
    )
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from core.ai_oponentni.ui.ai_peer_review_widget import AiPeerReviewWidget
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import (
        CATALOG_AI_PACKAGE_EDIT_BUTTON,
        CATALOG_AI_PACKAGE_INCORPORATE_BUTTON,
        CATALOG_AI_PACKAGE_REJECT_BUTTON,
        HAZARD_LIBRARY_SCOPE_ALL,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_assessment import (
        HazardLibraryTemplateAssessment,
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
        HazardCatalogPackageIncorporateError,
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
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


def _package(
    *,
    package_type: str = AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
    target_event_export_id: str | None = None,
    with_measures: bool = True,
) -> AiProposalPackage:
    assessments = (
        AiProposalPackageAssessment(
            exposed_group="Zaměstnanci",
            severity=RISK_SEVERITY_MODERATE,
            existing_measures=(
                (AiProposalPackageMeasure(description="Zábradlí"),) if with_measures else ()
            ),
            required_measures=(
                (AiProposalPackageMeasure(description="Kontrola zábradlí"),)
                if with_measures
                else ()
            ),
        ),
    )
    event = None
    if package_type == AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT:
        event = AiProposalPackageEvent(name="Pád z výšky", description="Práce na střeše")
    return AiProposalPackage(
        package_id="PACKAGE-001",
        package_type=package_type,
        target_event_export_id=target_event_export_id,
        event=event,
        assessments=assessments,
        legal_links=(),
        reasoning="Kompletní scénář opomenutí.",
    )


class AiProposalPackagesR20bTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

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
            session.execute(delete(HazardLibraryTemplateAssessment))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.group = ensure_exposed_group("Zaměstnanci")
        self.template = hazard_library_template_service.create_template(
            name="Testovací zdroj R20b",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        self.existing_event = hazard_library_template_event_service.create_event(
            template_id=self.template.id,
            name="Existující událost",
        )
        hazard_library_template_assessment_service.create_assessment(
            template_id=self.template.id,
            template_event_id=self.existing_event.id,
            exposed_group_id=self.group.id,
            severity=RISK_SEVERITY_MODERATE,
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

    def test_format_package_detail_contains_sections(self) -> None:
        text = format_proposal_package_detail(_package())
        self.assertIn("UDÁLOST", text)
        self.assertIn("POSOUZENÍ", text)
        self.assertIn("Zásady bezpečné práce", text)
        self.assertIn("Kontrolní otázky pro revizi rizik", text)
        self.assertIn("PRÁVNÍ VAZBY", text)
        self.assertIn("ZDŮVODNĚNÍ AI", text)
        self.assertIn("Pád z výšky", text)

    def test_widget_shows_package_actions_and_detail(self) -> None:
        widget = AiPeerReviewWidget(
            provider=self.provider,
            evidence_only_import=True,
        )
        widget.set_source(self.template.id)
        self.assertEqual(widget.edit_proposal_btn.text(), CATALOG_AI_PACKAGE_EDIT_BUTTON)
        self.assertEqual(
            widget.incorporate_btn.text(),
            CATALOG_AI_PACKAGE_INCORPORATE_BUTTON,
        )
        self.assertEqual(widget.reject_proposal_btn.text(), CATALOG_AI_PACKAGE_REJECT_BUTTON)
        self.assertIsNotNone(widget.package_detail)

    def test_incorporate_new_event_package(self) -> None:
        record = self._store_package(_package())
        result = hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        self.assertEqual(result.event_count, 1)
        self.assertEqual(result.assessment_count, 1)
        self.assertEqual(result.existing_measure_count, 1)
        self.assertEqual(result.required_measure_count, 1)
        self.assertGreater(result.new_revision_number, self.initial_version)

        events = hazard_library_template_event_service.get_for_template(
            self.template.id,
            include_inactive=False,
        )
        self.assertIn("Pád z výšky", {event.name for event in events})

        reloaded = ai_peer_review_service.package_repository.get_by_id(record.id)
        self.assertEqual(reloaded.status, PACKAGE_STATUS_INCORPORATED)
        template = hazard_library_template_service.get_by_id(self.template.id)
        self.assertEqual(template.version_number, result.new_revision_number)

    def test_incorporate_extend_event_package(self) -> None:
        export_map = hazard_catalog_package_incorporate_service.get_export_id_map(
            self.review.id,
        )
        event_export_id = next(
            key
            for key, value in export_map.items()
            if isinstance(value, dict) and value.get("kind") == "event"
        )
        package = _package(
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
            target_event_export_id=event_export_id,
        )
        record = self._store_package(package)
        result = hazard_catalog_package_incorporate_service.incorporate_package(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        self.assertEqual(result.event_count, 0)
        self.assertEqual(result.assessment_count, 0)
        self.assertEqual(result.merged_assessment_count, 1)
        assessments = hazard_library_template_assessment_service.get_for_event(
            self.existing_event.id,
            include_inactive=False,
        )
        self.assertEqual(len(assessments), 1)
        self.assertEqual(
            hazard_library_template_assessment_service.get_group_ids(
                assessments[0].assessment.id,
            ),
            [self.group.id],
        )

    def test_rollback_on_unresolved_exposed_group(self) -> None:
        package = AiProposalPackage(
            package_id="PACKAGE-BAD",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            event=AiProposalPackageEvent(name="Výbuch"),
            assessments=(
                AiProposalPackageAssessment(
                    exposed_group="Neexistující skupina XYZ",
                    severity=RISK_SEVERITY_MODERATE,
                ),
            ),
            reasoning="Test rollback",
        )
        record = self._store_package(package)
        with self.assertRaises(HazardCatalogPackageIncorporateError):
            hazard_catalog_package_incorporate_service.incorporate_package(
                template_id=self.template.id,
                package_record_id=record.id,
            )
        reloaded = ai_peer_review_service.package_repository.get_by_id(record.id)
        self.assertEqual(reloaded.status, PACKAGE_STATUS_PENDING)
        template = hazard_library_template_service.get_by_id(self.template.id)
        self.assertEqual(template.version_number, self.initial_version)
        events = hazard_library_template_event_service.get_for_template(
            self.template.id,
            include_inactive=False,
        )
        self.assertNotIn("Výbuch", {event.name for event in events})

    def test_reject_package(self) -> None:
        record = self._store_package(_package())
        self.assertTrue(
            hazard_catalog_package_incorporate_service.reject_package(record.id),
        )
        reloaded = ai_peer_review_service.package_repository.get_by_id(record.id)
        self.assertEqual(reloaded.status, PACKAGE_STATUS_REJECTED)

    def test_update_package_payload(self) -> None:
        record = self._store_package(_package())
        updated = AiProposalPackage(
            package_id="PACKAGE-001",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            event=AiProposalPackageEvent(name="Upravená událost"),
            assessments=_package().assessments,
            legal_links=(),
            reasoning="Upravené zdůvodnění",
        )
        hazard_catalog_package_incorporate_service.update_package_payload(
            record.id,
            updated,
        )
        package = ai_peer_review_service.package_repository.package_from_record(
            ai_peer_review_service.package_repository.get_by_id(record.id),
        )
        self.assertEqual(package.event_name, "Upravená událost")
        self.assertEqual(package.reasoning, "Upravené zdůvodnění")

    def test_widget_loads_package_detail_on_selection(self) -> None:
        record = self._store_package(_package())
        widget = AiPeerReviewWidget(
            provider=self.provider,
            evidence_only_import=True,
        )
        widget.set_source(self.template.id)
        widget._select_review_row(self.review.id)
        widget._load_proposals_table()
        widget.proposals_table.selectRow(0)
        widget._load_package_detail()
        detail = widget.package_detail.toPlainText()
        self.assertIn("Pád z výšky", detail)
        self.assertIn(record.package_id, detail)

    def test_reach_link_is_skipped_and_exact_citation_is_incorporated(self) -> None:
        from moduly.pravni_pozadavky.constants import (
            DOCUMENT_TYPE_NARIZENI_VLADY,
            DOCUMENT_TYPE_VYHLASKA,
            DOCUMENT_TYPE_ZAKON,
        )
        from moduly.pravni_pozadavky.sluzby.legal_document_service import (
            legal_document_service,
        )
        from moduly.rizeni_rizik.modely.hazard_library_template_legal_link import (
            HazardLibraryTemplateLegalLink,
        )
        from moduly.rizeni_rizik.ui import hazard_catalog_ai_package_edit_dialog as package_edit_ui

        reach = (
            "Nařízení Evropského parlamentu a Rady (ES) č. 1907/2006 (REACH), "
            "zejména čl. 35"
        )
        labour = "zák. č. 262/2006 Sb."
        decoys = [
            legal_document_service.create(
                document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
                title="Nařízení vlády o vyhrazených technických elektrických zařízeních",
                number="190/2022 Sb.",
                year=2022,
            ),
            legal_document_service.create(
                document_type=DOCUMENT_TYPE_ZAKON,
                title="Zákon o posuzování shody stanovených výrobků při jejich dodávání na trh",
                number="90/2016 Sb.",
                year=2016,
            ),
            legal_document_service.create(
                document_type=DOCUMENT_TYPE_VYHLASKA,
                title="Vyhláška o používání výbušnin",
                number="35/1998 Sb.",
                year=1998,
            ),
        ]
        labour_document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákon zákoník práce",
            number="262/2006 Sb.",
            year=2006,
        )
        decoy_ids = {document.id for document in decoys}
        package = _package()
        package = AiProposalPackage(
            package_id=package.package_id,
            package_type=package.package_type,
            target_event_export_id=package.target_event_export_id,
            event=package.event,
            assessments=package.assessments,
            legal_links=(
                AiProposalPackageLegalLink(reference=reach),
                AiProposalPackageLegalLink(reference=labour),
            ),
            reasoning=package.reasoning,
        )
        record = self._store_package(package)
        original_payload = record.payload_json
        review_before = ai_peer_review_service.get_by_id(self.review.id)
        response_before = review_before.response_text

        unresolved = hazard_catalog_package_incorporate_service.unresolved_legal_references(
            package,
        )
        self.assertEqual(unresolved, [reach])
        self.assertFalse(
            hazard_catalog_package_incorporate_service._assignment_is_unambiguous(
                reach,
                decoys[0],
            ),
        )
        self.assertTrue(
            hazard_catalog_package_incorporate_service._assignment_is_unambiguous(
                labour,
                labour_document,
            ),
        )

        dialog = package_edit_ui.UnresolvedLegalLinksConfirmDialog(None, unresolved)
        from PySide6.QtWidgets import QPlainTextEdit

        listing = dialog.findChild(QPlainTextEdit)
        self.assertIsNotNone(listing)
        self.assertIn(reach, listing.toPlainText())
        self.assertIn("čl. 35", listing.toPlainText())
        self.assertTrue(listing.isReadOnly())

        widget = AiPeerReviewWidget(
            provider=self.provider,
            evidence_only_import=True,
        )
        widget.set_source(self.template.id)
        widget._select_review_row(self.review.id)
        widget._load_proposals_table()
        widget.proposals_table.selectRow(0)

        with (
            patch.object(
                package_edit_ui,
                "confirm_unresolved_legal_links",
                return_value=False,
            ) as cancelled_confirm,
            patch("core.ai_oponentni.ui.ai_peer_review_widget.QMessageBox.information"),
            patch("core.ai_oponentni.ui.ai_peer_review_widget.QMessageBox.warning"),
        ):
            widget._incorporate_selected_package()
        cancelled_confirm.assert_called_once()
        cancelled = ai_peer_review_service.package_repository.get_by_id(record.id)
        self.assertEqual(cancelled.status, PACKAGE_STATUS_PENDING)
        self.assertEqual(cancelled.payload_json, original_payload)

        with (
            patch.object(
                package_edit_ui,
                "confirm_unresolved_legal_links",
                return_value=True,
            ),
            patch("core.ai_oponentni.ui.ai_peer_review_widget.QMessageBox.information"),
            patch("core.ai_oponentni.ui.ai_peer_review_widget.QMessageBox.warning"),
        ):
            widget._incorporate_selected_package()

        incorporated = ai_peer_review_service.package_repository.get_by_id(record.id)
        self.assertEqual(incorporated.status, PACKAGE_STATUS_INCORPORATED)
        self.assertEqual(incorporated.payload_json, original_payload)
        self.assertIn("1907/2006", incorporated.payload_json)
        review_after = ai_peer_review_service.get_by_id(self.review.id)
        self.assertEqual(review_after.response_text, response_before)

        from sqlalchemy import select

        from core.database.session import get_session

        with get_session() as session:
            links = session.scalars(
                select(HazardLibraryTemplateLegalLink).where(
                    HazardLibraryTemplateLegalLink.template_id == self.template.id,
                ),
            ).all()
        linked_ids = {link.legal_document_id for link in links}
        self.assertIn(labour_document.id, linked_ids)
        self.assertTrue(decoy_ids.isdisjoint(linked_ids))

    def test_only_unresolved_legal_links_do_not_finish_package(self) -> None:
        from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
            CATALOG_INCORPORATE_ERROR_EMPTY_RESULT,
            HazardCatalogPackageIncorporateError,
        )

        export_map = hazard_catalog_package_incorporate_service.get_export_id_map(
            self.review.id,
        )
        event_export_id = next(
            key
            for key, value in export_map.items()
            if isinstance(value, dict) and value.get("kind") == "event"
        )
        package = AiProposalPackage(
            package_id="PACKAGE-REACH",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
            target_event_export_id=event_export_id,
            event=None,
            assessments=(),
            legal_links=(
                AiProposalPackageLegalLink(
                    reference=(
                        "Nařízení Evropského parlamentu a Rady (ES) č. 1907/2006 "
                        "(REACH), zejména čl. 35"
                    ),
                ),
            ),
            reasoning="",
        )
        record = self._store_package(package)
        with self.assertRaises(HazardCatalogPackageIncorporateError) as caught:
            hazard_catalog_package_incorporate_service.incorporate_package(
                template_id=self.template.id,
                package_record_id=record.id,
            )
        self.assertEqual(str(caught.exception), CATALOG_INCORPORATE_ERROR_EMPTY_RESULT)
        reloaded = ai_peer_review_service.package_repository.get_by_id(record.id)
        self.assertEqual(reloaded.status, PACKAGE_STATUS_PENDING)
