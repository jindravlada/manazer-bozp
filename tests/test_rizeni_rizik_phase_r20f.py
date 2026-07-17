"""Fáze R20f – ergonomie AI oponentury."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.ai_oponentni.constants import AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT
    from core.ai_oponentni.proposal_package_types import (
        AiProposalPackage,
        AiProposalPackageEvent,
    )
    from core.ai_oponentni.sluzby.ai_peer_review_service import ai_peer_review_service
    from core.ai_oponentni.types import AiPeerReviewExportOptions
    from moduly.rizeni_rizik.constants import HAZARD_INVENTORY_CATEGORY_EQUIPMENT
    from moduly.rizeni_rizik.constants_library import HAZARD_LIBRARY_SCOPE_ALL
    from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
        hazard_catalog_source_peer_review_provider,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )


class RizeniRizikPhaseR20fTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.provider = hazard_catalog_source_peer_review_provider
        self.template = hazard_library_template_service.create_template(
            name=f"R20f šablona {id(self)}",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            application_scope=HAZARD_LIBRARY_SCOPE_ALL,
        )
        self.export_dir = Path(tempfile.mkdtemp())
        export_result = ai_peer_review_service.export_package(
            self.provider,
            self.template.id,
            self.export_dir / "export.zip",
            options=AiPeerReviewExportOptions(),
        )
        self.review = export_result.review

    def test_r20f1_package_import_skips_selection_dialog_and_imports_all(self) -> None:
        from core.ai_oponentni.ui.ai_peer_review_widget import AiPeerReviewWidget

        packages = [
            AiProposalPackage(
                package_id="PACKAGE-001",
                package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
                target_event_export_id=None,
                event=AiProposalPackageEvent(name="Pád z výšky"),
                assessments=(),
                legal_links=(),
                reasoning="test",
            ),
            AiProposalPackage(
                package_id="PACKAGE-002",
                package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
                target_event_export_id=None,
                event=AiProposalPackageEvent(name="Pořezání"),
                assessments=(),
                legal_links=(),
                reasoning="test",
            ),
        ]
        parse_result = MagicMock()
        parse_result.skipped_count = 0
        parse_result.skip_reasons = []
        parse_result.uses_proposal_packages = True
        parse_result.packages = packages
        parse_result.proposals = []
        parse_result.format_label = "návrhové balíky"

        updated_review = MagicMock()
        updated_review.id = self.review.id

        widget = AiPeerReviewWidget(
            provider=self.provider,
            evidence_only_import=True,
        )
        widget.set_source(self.template.id)

        response_dialog = MagicMock()
        response_dialog.exec.return_value = True
        response_dialog.get_response_text.return_value = '{"packages":[]}'
        response_dialog.get_ai_model.return_value = "TestModel"

        with (
            patch.object(widget, "_resolve_import_review", return_value=self.review),
            patch(
                "core.ai_oponentni.ui.ai_peer_review_widget.AiPeerReviewResponseDialog",
                return_value=response_dialog,
            ),
            patch.object(
                ai_peer_review_service,
                "parse_response",
                return_value=parse_result,
            ),
            patch.object(
                ai_peer_review_service,
                "finalize_package_import",
                return_value=updated_review,
            ) as finalize_mock,
            patch(
                "core.ai_oponentni.ui.ai_peer_review_widget.AiPeerReviewPackageImportDialog",
                create=True,
            ) as import_dialog_cls,
            patch(
                "core.ai_oponentni.ui.ai_peer_review_widget.QMessageBox.information",
            ),
            patch(
                "core.ai_oponentni.ui.ai_peer_review_widget.QMessageBox.warning",
            ),
        ):
            result = widget.import_response()

        self.assertTrue(result)
        import_dialog_cls.assert_not_called()
        finalize_mock.assert_called_once()
        kwargs = finalize_mock.call_args.kwargs
        self.assertEqual(kwargs["accepted"], packages)
        self.assertEqual(kwargs["rejected"], [])
        self.assertEqual(kwargs["loaded_packages_count"], 2)

    def test_r20f2_ui_hides_event_export_ids(self) -> None:
        from core.ai_oponentni.constants import (
            AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
            AI_PEER_REVIEW_PACKAGE_TYPE_LABELS,
        )
        from core.ai_oponentni.proposal_package_types import AiProposalPackage
        from core.ai_oponentni.sluzby.proposal_package_detail import (
            format_proposal_package_detail,
        )
        from moduly.rizeni_rizik.ui.hazard_catalog_ai_package_edit_dialog import (
            format_package_summary,
        )

        package = AiProposalPackage(
            package_id="PACKAGE-EXT",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
            target_event_export_id="EVENT-003",
            event=None,
            assessments=(),
            legal_links=(),
            reasoning="",
        )
        self.assertEqual(
            AI_PEER_REVIEW_PACKAGE_TYPE_LABELS[AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT],
            "Doplnění události",
        )
        self.assertEqual(package.event_name, "—")
        self.assertEqual(
            package.display_event_label(resolved_target_name="Pád z výšky"),
            "Pád z výšky",
        )
        self.assertEqual(package.display_event_label(), "Doplnění události")
        self.assertNotIn("EVENT-003", package.display_event_label())

        detail = format_proposal_package_detail(
            package,
            resolved_target_event_name="Pád z výšky",
        )
        self.assertIn("Doplnění události: Pád z výšky", detail)
        self.assertNotIn("EVENT-003", detail)

        summary = format_package_summary(package, target_event_name="Pád z výšky")
        self.assertIn("Cílová událost: Pád z výšky", summary)
        self.assertNotIn("EVENT-003", summary)

    def test_r20f3_target_event_uses_wrapping_readonly_widget(self) -> None:
        from core.ai_oponentni.constants import AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT
        from core.ai_oponentni.proposal_package_types import AiProposalPackage
        from moduly.rizeni_rizik.ui.hazard_catalog_ai_package_edit_dialog import (
            HazardCatalogAiPackageEditDialog,
        )

        long_name = (
            "Velmi dlouhý název cílové události, který se dříve překrýval "
            "v jednořádkovém poli a musí být čitelný i při zalamování textu."
        )
        package = AiProposalPackage(
            package_id="PACKAGE-LONG",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
            target_event_export_id="EVENT-009",
            event=None,
            assessments=(),
            legal_links=(),
            reasoning="",
        )
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=0,
            target_event_name=long_name,
        )
        self.assertEqual(dialog.target_event_name_label.toPlainText(), long_name)
        self.assertTrue(dialog.target_event_name_label.isReadOnly())
        self.assertGreaterEqual(dialog.target_event_name_label.minimumHeight(), 48)

    def test_r20f4_package_editor_opens_maximized(self) -> None:
        from core.ai_oponentni.ui.ai_peer_review_widget import AiPeerReviewWidget
        from core.ai_oponentni.constants import AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT
        from core.ai_oponentni.proposal_package_types import (
            AiProposalPackage,
            AiProposalPackageEvent,
        )

        package = AiProposalPackage(
            package_id="PACKAGE-MAX",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            event=AiProposalPackageEvent(name="Pád"),
            assessments=(),
            legal_links=(),
            reasoning="",
        )
        updated = ai_peer_review_service.finalize_package_import(
            provider=self.provider,
            source_id=self.template.id,
            review_id=self.review.id,
            response_text="{}",
            ai_model="Test",
            accepted=[package],
            rejected=[],
            loaded_packages_count=1,
        )
        records = ai_peer_review_service.get_packages_for_review(updated.id)
        self.assertEqual(len(records), 1)

        widget = AiPeerReviewWidget(
            provider=self.provider,
            evidence_only_import=True,
        )
        widget.set_source(self.template.id)
        widget._select_review_row(updated.id)
        widget._load_proposals_table()
        widget.proposals_table.selectRow(0)

        with patch(
            "core.widgets.dialog_utils.exec_maximized",
            return_value=False,
        ) as maximized_mock:
            widget._edit_selected_package()
        maximized_mock.assert_called_once()

    def test_r20f5_legal_mapping_uses_multi_selector_not_dialog(self) -> None:
        from core.ai_oponentni.constants import AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT
        from core.ai_oponentni.proposal_package_types import (
            AiProposalPackage,
            AiProposalPackageEvent,
            AiProposalPackageLegalLink,
        )
        from core.widgets.multi_legal_document_selector import MultiLegalDocumentSelector
        from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_NARIZENI_VLADY
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.sluzby.legal_document_service import (
            legal_document_service,
        )
        from moduly.rizeni_rizik.ui.hazard_catalog_ai_package_edit_dialog import (
            HazardCatalogAiPackageEditDialog,
        )
        from sqlalchemy import delete

        from core.database.session import SessionLocal

        with SessionLocal() as session:
            session.execute(delete(LegalDocument))
            session.commit()

        legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            number="378",
            year=2001,
            title="Nařízení vlády č. 378/2001 Sb.",
            short_title="NV 378/2001",
        )
        package = AiProposalPackage(
            package_id="PACKAGE-LEGAL",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            event=AiProposalPackageEvent(name="Pád"),
            assessments=(),
            legal_links=(
                AiProposalPackageLegalLink(reference="NV č. 378/2001 Sb."),
            ),
            reasoning="",
        )
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=0,
        )
        self.assertIsInstance(dialog.legal_documents, MultiLegalDocumentSelector)
        self.assertFalse(hasattr(dialog, "pick_legal_document_btn"))
        self.assertFalse(hasattr(dialog, "legal_mapping_label"))
        self.assertNotIn("Mapovat první řádek", dialog.windowTitle())

    def test_r20f6_exact_legal_match_is_prefilled(self) -> None:
        from core.ai_oponentni.constants import AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT
        from core.ai_oponentni.proposal_package_types import (
            AiProposalPackage,
            AiProposalPackageEvent,
            AiProposalPackageLegalLink,
        )
        from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_NARIZENI_VLADY
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.sluzby.legal_document_service import (
            legal_document_service,
        )
        from moduly.rizeni_rizik.ui.hazard_catalog_ai_package_edit_dialog import (
            HazardCatalogAiPackageEditDialog,
            resolve_exact_legal_document_id,
        )
        from sqlalchemy import delete

        from core.database.session import SessionLocal

        with SessionLocal() as session:
            session.execute(delete(LegalDocument))
            session.commit()

        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            number="378",
            year=2001,
            title="Nařízení vlády č. 378/2001 Sb.",
            short_title="NV 378/2001",
        )
        self.assertEqual(
            resolve_exact_legal_document_id("NV 378/2001 Sb."),
            document.id,
        )
        package = AiProposalPackage(
            package_id="PACKAGE-PREFILL",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            event=AiProposalPackageEvent(name="Pád"),
            assessments=(),
            legal_links=(
                AiProposalPackageLegalLink(reference="NV 378/2001 Sb."),
            ),
            reasoning="",
        )
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=0,
        )
        self.assertEqual(dialog.legal_documents.selected_document_ids(), [document.id])
        self.assertFalse(dialog.unresolved_legal_label.isVisible())
        self.assertIsNone(resolve_exact_legal_document_id("neexistující předpis XYZ"))

    def test_r20f7_multi_legal_document_selection_roundtrip(self) -> None:
        from core.ai_oponentni.constants import AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT
        from core.ai_oponentni.proposal_package_types import (
            AiProposalPackage,
            AiProposalPackageEvent,
            AiProposalPackageLegalLink,
        )
        from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
        from moduly.pravni_pozadavky.constants import (
            DOCUMENT_TYPE_NARIZENI_VLADY,
            DOCUMENT_TYPE_ZAKON,
        )
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.sluzby.legal_document_service import (
            legal_document_service,
        )
        from moduly.rizeni_rizik.ui.hazard_catalog_ai_package_edit_dialog import (
            HazardCatalogAiPackageEditDialog,
        )
        from sqlalchemy import delete

        from core.database.session import SessionLocal

        with SessionLocal() as session:
            session.execute(delete(LegalDocument))
            session.commit()

        zakon = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            number="262",
            year=2006,
            title="Zákon č. 262/2006 Sb., zákoník práce",
            short_title="ZP",
        )
        nv_101 = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            number="101",
            year=2005,
            title="Nařízení vlády č. 101/2005 Sb.",
            short_title="NV 101/2005",
        )
        nv_378 = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            number="378",
            year=2001,
            title="Nařízení vlády č. 378/2001 Sb.",
            short_title="NV 378/2001",
        )
        group = exposed_group_service.create_group(name=f"R20f7 skupina {id(self)}")

        package = AiProposalPackage(
            package_id="PACKAGE-MULTI-LEGAL",
            package_type=AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
            target_event_export_id=None,
            event=AiProposalPackageEvent(name="Pád"),
            assessments=(),
            legal_links=(
                AiProposalPackageLegalLink(reference="zák. č. 262/2006 Sb."),
                AiProposalPackageLegalLink(reference="NV 101/2005 Sb."),
                AiProposalPackageLegalLink(reference="neznámý předpis XYZ-999"),
            ),
            reasoning="",
        )
        dialog = HazardCatalogAiPackageEditDialog(
            package=package,
            package_record_id=0,
        )
        self.assertEqual(
            set(dialog.legal_documents.selected_document_ids()),
            {zakon.id, nv_101.id},
        )
        self.assertIn("neznámý předpis XYZ-999", dialog.unresolved_legal_label.text())
        self.assertFalse(dialog.unresolved_legal_label.isHidden())
        self.assertNotIn("Vybrat předpis", dialog.windowTitle())

        dialog.legal_documents._append_document_id(nv_378.id)
        self.assertEqual(
            set(dialog.legal_documents.selected_document_ids()),
            {zakon.id, nv_101.id, nv_378.id},
        )
        dialog.legal_documents.list_widget.setCurrentRow(0)
        dialog.legal_documents.remove_selected()
        remaining = set(dialog.legal_documents.selected_document_ids())
        self.assertEqual(len(remaining), 2)
        self.assertTrue(remaining.issubset({zakon.id, nv_101.id, nv_378.id}))

        dialog._assessment_editors[0].exposed_groups.set_group_ids([group.id])
        dialog.event_name.setText("Pád z výšky")
        dialog.accept()
        saved = dialog.get_package()
        self.assertIsNotNone(saved)
        saved_ids = {
            link.legal_document_id
            for link in saved.legal_links
            if link.legal_document_id is not None
        }
        self.assertEqual(saved_ids, remaining)
        unresolved = [
            link.reference
            for link in saved.legal_links
            if link.legal_document_id is None
        ]
        self.assertEqual(unresolved, ["neznámý předpis XYZ-999"])

        reopened = HazardCatalogAiPackageEditDialog(
            package=saved,
            package_record_id=0,
        )
        self.assertEqual(
            set(reopened.legal_documents.selected_document_ids()),
            remaining,
        )
        self.assertIn("neznámý předpis XYZ-999", reopened.unresolved_legal_label.text())


if __name__ == "__main__":
    unittest.main()
