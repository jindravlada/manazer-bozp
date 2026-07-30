"""RISK-AI-18: atomické a opakovatelné zapracování AI balíků."""

from __future__ import annotations

import copy
import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="risk-ai-18-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QMessageBox

    from core.ai_oponentni.constants import AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT
    from core.ai_oponentni.modely.ai_peer_review import AiPeerReview, AiPeerReviewBatch
    from core.ai_oponentni.modely.ai_proposal_package import (
        PACKAGE_STATUS_INCORPORATED,
        PACKAGE_STATUS_PENDING,
        AiProposalPackageRecord,
    )
    from core.ai_oponentni.proposal_package_types import (
        AiProposalPackage,
        AiProposalPackageAssessment,
        AiProposalPackageEvent,
        AiProposalPackageMeasure,
    )
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from core.ai_oponentni.ui.ai_peer_review_widget import AiPeerReviewWidget
    from core.database.session import get_session
    from moduly.rizeni_rizik.constants import (
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import (
        CATALOG_INCORPORATE_ERROR_ASSESSMENT_GROUP,
        HAZARD_LIBRARY_SCOPE_ALL,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_library_template_event import (
        HazardLibraryTemplateEvent,
    )
    from moduly.rizeni_rizik.modely.hazard_library_template_revision import (
        HazardLibraryTemplateRevision,
    )
    from moduly.rizeni_rizik.sluzby.catalog_editor_session import (
        SESSION_PACKAGE_PENDING,
        SESSION_PACKAGE_STAGED,
        CatalogEditorSession,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
        CATALOG_INCORPORATE_ERROR_DUPLICATE_EVENT,
        HazardCatalogPackageIncorporateError,
        hazard_catalog_package_incorporate_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        hazard_catalog_source_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
        HazardLibraryTemplateEventError,
        hazard_library_template_event_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.ui.hazard_library_template_dialog import (
        HazardLibraryTemplateDialog,
    )
    from sqlalchemy import delete
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


class RiskAi18AtomicIncorporateTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        with get_session() as session:
            session.execute(delete(AiProposalPackageRecord))
            session.execute(delete(AiPeerReviewBatch))
            session.execute(delete(AiPeerReview))
            session.execute(delete(HazardLibraryTemplateRevision))
            session.execute(delete(HazardLibraryTemplateEvent))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

        self.group = ensure_exposed_group("Zaměstnanci RISK-AI-18")
        self.template = hazard_library_template_service.create_template(
            name="Šablona RISK-AI-18",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        export_dir = Path(tempfile.mkdtemp())
        export_result = ai_peer_review_service.export_package(
            hazard_catalog_source_peer_review_provider,
            self.template.id,
            export_dir / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        self.review = export_result.review

    def _package(
        self,
        *,
        package_id: str,
        name: str,
        with_group: bool,
        exposed_group: str = "Neurčená skupina",
    ) -> AiProposalPackage:
        if with_group:
            assessment = AiProposalPackageAssessment(
                exposed_group=self.group.name,
                exposed_group_ids=(self.group.id,),
                severity=RISK_SEVERITY_MODERATE,
                conclusion="závěr AI-18",
                existing_measures=(
                    AiProposalPackageMeasure(description="Zásada AI-18", note=""),
                ),
                required_measures=(),
            )
        else:
            assessment = AiProposalPackageAssessment(
                exposed_group=exposed_group,
                exposed_group_ids=(),
                severity=RISK_SEVERITY_MODERATE,
                conclusion="závěr bez skupiny",
                existing_measures=(),
                required_measures=(),
            )
        return AiProposalPackage(
            package_id=package_id,
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            reasoning="důvod AI-18",
            event=AiProposalPackageEvent(name=name, description="popis", note=""),
            assessments=(assessment,),
            legal_links=(),
        )

    def _import_package(self, package: AiProposalPackage) -> AiProposalPackageRecord:
        stored = ai_peer_review_service.finalize_package_import(
            provider=hazard_catalog_source_peer_review_provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text="{}",
            ai_model="Test",
            accepted=[package],
            rejected=[],
        )
        return ai_peer_review_service.get_packages_for_review(stored.id)[0]

    @staticmethod
    def _wc_fingerprint(working_copy) -> tuple:
        events = []
        for event in sorted(working_copy.events, key=lambda row: row.id):
            assessments = []
            for assessment in event.assessments:
                assessments.append(
                    (
                        assessment.id,
                        assessment.active,
                        tuple(sorted(assessment.exposed_group_ids)),
                        tuple(m.description for m in assessment.existing_measures),
                        tuple(m.description for m in assessment.required_measures),
                    ),
                )
            events.append(
                (
                    event.id,
                    event.name,
                    event.active,
                    tuple(assessments),
                ),
            )
        return (
            tuple(events),
            tuple(
                (link.id, link.legal_document_id, link.active)
                for link in working_copy.legal_links
            ),
            tuple(working_copy.pending_package_ids),
            working_copy.is_dirty,
        )

    def test_missing_group_stops_before_wc_mutation(self) -> None:
        record = self._import_package(
            self._package(package_id="miss-1", name="Nová událost", with_group=False),
        )
        session = CatalogEditorSession.load(self.template.id)
        before = self._wc_fingerprint(session.content)

        with self.assertRaises(HazardCatalogPackageIncorporateError) as raised:
            hazard_catalog_package_incorporate_service.incorporate_package_into_working_copy(
                session.content,
                template_id=self.template.id,
                package_record_id=record.id,
                editor_session=session,
            )

        self.assertIn(
            CATALOG_INCORPORATE_ERROR_ASSESSMENT_GROUP.format(name="Neurčená skupina"),
            str(raised.exception),
        )
        self.assertEqual(self._wc_fingerprint(session.content), before)
        item = session.get_package(record.id)
        assert item is not None
        self.assertEqual(item.session_status, SESSION_PACKAGE_PENDING)
        self.assertEqual(len(session.list_pending_packages()), 1)

    def test_retry_after_group_fix_succeeds_and_reuses_existing_event(self) -> None:
        """Regrese: WC už má aktivní událost → fail bez skupiny → doplnění → reuse."""
        record = self._import_package(
            self._package(
                package_id="retry-1",
                name="Kolizní událost",
                with_group=False,
            ),
        )
        session = CatalogEditorSession.load(self.template.id)
        existing = session.content.create_event(
            template_id=self.template.id,
            name="Kolizní událost",
            description="původní",
        )
        existing_id = existing.id
        before = self._wc_fingerprint(session.content)

        with self.assertRaises(HazardCatalogPackageIncorporateError):
            hazard_catalog_package_incorporate_service.incorporate_package_into_working_copy(
                session.content,
                template_id=self.template.id,
                package_record_id=record.id,
                editor_session=session,
            )
        self.assertEqual(self._wc_fingerprint(session.content), before)
        self.assertEqual(len(session.content.events), 1)

        fixed = self._package(
            package_id="retry-1",
            name="Kolizní událost",
            with_group=True,
        )
        session.update_package(record.id, fixed)
        result = hazard_catalog_package_incorporate_service.incorporate_package_into_working_copy(
            session.content,
            template_id=self.template.id,
            package_record_id=record.id,
            editor_session=session,
        )

        self.assertEqual(result.event_count, 0)
        self.assertEqual(result.assessment_count, 1)
        self.assertEqual(len(session.content.events), 1)
        self.assertEqual(session.content.events[0].id, existing_id)
        self.assertEqual(len(session.content.events[0].assessments), 1)
        item = session.get_package(record.id)
        assert item is not None
        self.assertEqual(item.session_status, SESSION_PACKAGE_STAGED)
        self.assertEqual(len(session.list_pending_packages()), 0)

    def test_no_second_active_event_same_name(self) -> None:
        record = self._import_package(
            self._package(package_id="dup-1", name="Stejný název", with_group=True),
        )
        session = CatalogEditorSession.load(self.template.id)
        session.content.create_event(
            template_id=self.template.id,
            name="Stejný název",
        )
        hazard_catalog_package_incorporate_service.incorporate_package_into_working_copy(
            session.content,
            template_id=self.template.id,
            package_record_id=record.id,
            editor_session=session,
        )
        active_same = [
            event
            for event in session.content.events
            if event.active and event.name.strip().casefold() == "stejný název"
        ]
        self.assertEqual(len(active_same), 1)

    def test_mid_incorporate_exception_rolls_back_wc(self) -> None:
        record = self._import_package(
            self._package(package_id="mid-1", name="Událost mid", with_group=True),
        )
        session = CatalogEditorSession.load(self.template.id)
        before = self._wc_fingerprint(session.content)

        with patch.object(
            hazard_catalog_package_incorporate_service,
            "_wc_incorporate_assessment",
            side_effect=RuntimeError("simulovaná chyba uprostřed"),
        ):
            with self.assertRaises(RuntimeError):
                hazard_catalog_package_incorporate_service.incorporate_package_into_working_copy(
                    session.content,
                    template_id=self.template.id,
                    package_record_id=record.id,
                    editor_session=session,
                )

        self.assertEqual(self._wc_fingerprint(session.content), before)
        item = session.get_package(record.id)
        assert item is not None
        self.assertEqual(item.session_status, SESSION_PACKAGE_PENDING)
        self.assertEqual(len(session.list_pending_packages()), 1)

    def test_duplicate_name_error_from_create_event_is_user_friendly(self) -> None:
        from moduly.rizeni_rizik.sluzby.hazard_library_template_working_copy import (
            HazardLibraryTemplateWorkingCopy,
        )

        record = self._import_package(
            self._package(package_id="dup-msg", name="X", with_group=True),
        )
        session = CatalogEditorSession.load(self.template.id)
        before = self._wc_fingerprint(session.content)

        def _patched_candidate():
            cloned = HazardLibraryTemplateWorkingCopy.clone(session.content)

            def boom(*_a, **_k):
                raise HazardLibraryTemplateEventError(
                    "Aktivní událost se stejným názvem již v tomto zdroji existuje.",
                )

            cloned.create_event = boom  # type: ignore[method-assign]
            return cloned

        with patch.object(
            hazard_catalog_package_incorporate_service,
            "_wc_resolve_event_id",
            return_value=None,
        ):
            with patch.object(session.content, "clone", side_effect=_patched_candidate):
                with self.assertRaises(HazardCatalogPackageIncorporateError) as raised:
                    hazard_catalog_package_incorporate_service.incorporate_package_into_working_copy(
                        session.content,
                        template_id=self.template.id,
                        package_record_id=record.id,
                        editor_session=session,
                    )

        self.assertEqual(str(raised.exception), CATALOG_INCORPORATE_ERROR_DUPLICATE_EVENT)
        self.assertEqual(self._wc_fingerprint(session.content), before)
    def test_repeated_failed_attempts_do_not_create_duplicates(self) -> None:
        record = self._import_package(
            self._package(package_id="rep-1", name="Opakovaná", with_group=False),
        )
        session = CatalogEditorSession.load(self.template.id)
        before = self._wc_fingerprint(session.content)
        for _ in range(3):
            with self.assertRaises(HazardCatalogPackageIncorporateError):
                hazard_catalog_package_incorporate_service.incorporate_package_into_working_copy(
                    session.content,
                    template_id=self.template.id,
                    package_record_id=record.id,
                    editor_session=session,
                )
            self.assertEqual(self._wc_fingerprint(session.content), before)
            self.assertEqual(len(session.content.events), 0)
            item = session.get_package(record.id)
            assert item is not None
            self.assertEqual(item.session_status, SESSION_PACKAGE_PENDING)

    def test_user_edits_survive_failed_incorporate(self) -> None:
        record = self._import_package(
            self._package(package_id="edit-1", name="Upravovaná", with_group=False),
        )
        session = CatalogEditorSession.load(self.template.id)
        edited = self._package(
            package_id="edit-1",
            name="Upravovaná – po editaci",
            with_group=False,
            exposed_group="Stále chybí",
        )
        session.update_package(record.id, edited)

        with self.assertRaises(HazardCatalogPackageIncorporateError):
            hazard_catalog_package_incorporate_service.incorporate_package_into_working_copy(
                session.content,
                template_id=self.template.id,
                package_record_id=record.id,
                editor_session=session,
            )

        item = session.get_package(record.id)
        assert item is not None
        self.assertEqual(item.session_status, SESSION_PACKAGE_PENDING)
        self.assertEqual(item.package.event_name, "Upravovaná – po editaci")
        self.assertEqual(item.package.assessments[0].exposed_group, "Stále chybí")

    def test_successful_incorporate_stages_only_after_all_items(self) -> None:
        record = self._import_package(
            self._package(package_id="ok-1", name="Úspěšná", with_group=True),
        )
        session = CatalogEditorSession.load(self.template.id)
        result = hazard_catalog_package_incorporate_service.incorporate_package_into_working_copy(
            session.content,
            template_id=self.template.id,
            package_record_id=record.id,
            editor_session=session,
        )
        self.assertEqual(result.event_count, 1)
        self.assertGreaterEqual(result.assessment_count, 1)
        item = session.get_package(record.id)
        assert item is not None
        self.assertEqual(item.session_status, SESSION_PACKAGE_STAGED)
        self.assertEqual(session.list_pending_packages(), [])
        self.assertTrue(any(event.name == "Úspěšná" for event in session.content.events))
        self.assertTrue(any(event.assessments for event in session.content.events))

    def test_success_save_marks_incorporated_not_empty(self) -> None:
        record = self._import_package(
            self._package(package_id="save-1", name="Uložená", with_group=True),
        )
        dialog = HazardLibraryTemplateDialog(template=self.template)
        dialog._incorporate_package_into_working_copy(
            template_id=self.template.id,
            package_record_id=record.id,
        )
        assert dialog._editor_session is not None
        self.assertEqual(len(dialog._editor_session.list_pending_packages()), 0)
        with patch.object(
            QMessageBox,
            "information",
            return_value=QMessageBox.StandardButton.Ok,
        ):
            self.assertTrue(dialog._save_all())

        reloaded = ai_peer_review_service.package_repository.get_by_id(record.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, PACKAGE_STATUS_INCORPORATED)
        events = hazard_library_template_event_service.get_for_template(self.template.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].name, "Uložená")

    def test_ui_catches_domain_error_without_traceback(self) -> None:
        record = self._import_package(
            self._package(package_id="ui-1", name="UI chyba", with_group=False),
        )
        widget = AiPeerReviewWidget(
            provider=hazard_catalog_source_peer_review_provider,
            package_incorporate_handler=(
                lambda **_kwargs: (_ for _ in ()).throw(
                    HazardCatalogPackageIncorporateError(
                        CATALOG_INCORPORATE_ERROR_DUPLICATE_EVENT,
                    ),
                )
            ),
        )
        widget.set_source(self.template.id)
        widget.refresh()
        # Vybrat řádek balíku v tabulce návrhů
        if widget.proposals_table.rowCount() > 0:
            widget.proposals_table.selectRow(0)

        with patch.object(widget, "_selected_package_record_id", return_value=record.id):
            with patch.object(widget, "refresh") as refresh_mock:
                with patch.object(QMessageBox, "warning") as warning_mock:
                    with patch.object(QMessageBox, "information") as info_mock:
                        widget._incorporate_selected_package()

        warning_mock.assert_called_once()
        args = warning_mock.call_args[0]
        self.assertIn("Nebyly provedeny žádné změny", args[2])
        info_mock.assert_not_called()
        refresh_mock.assert_called()
        # Balík zůstává pending – zapracování lze zkusit znovu.
        reloaded = ai_peer_review_service.package_repository.get_by_id(record.id)
        assert reloaded is not None
        self.assertEqual(reloaded.status, PACKAGE_STATUS_PENDING)

    def test_unresolvable_collision_full_rollback(self) -> None:
        """Dvě aktivní události se stejným normalizovaným názvem → chyba + žádná změna."""
        record = self._import_package(
            self._package(package_id="col-1", name="Duplicitní", with_group=True),
        )
        session = CatalogEditorSession.load(self.template.id)
        session.content.create_event(
            template_id=self.template.id,
            name="Duplicitní",
        )
        # Obcházíme validaci WC a vložíme druhou se stejným klíčem přímo.
        twin = copy.deepcopy(session.content.events[0])
        twin.id = session.content._alloc_id()
        twin.name = "duplicitní"
        session.content.events.append(twin)
        before = self._wc_fingerprint(session.content)

        with self.assertRaises(HazardCatalogPackageIncorporateError) as raised:
            hazard_catalog_package_incorporate_service.incorporate_package_into_working_copy(
                session.content,
                template_id=self.template.id,
                package_record_id=record.id,
                editor_session=session,
            )
        self.assertEqual(str(raised.exception), CATALOG_INCORPORATE_ERROR_DUPLICATE_EVENT)
        self.assertEqual(self._wc_fingerprint(session.content), before)
        item = session.get_package(record.id)
        assert item is not None
        self.assertEqual(item.session_status, SESSION_PACKAGE_PENDING)


if __name__ == "__main__":
    unittest.main()
