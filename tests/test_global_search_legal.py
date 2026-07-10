import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.search.bootstrap import build_default_global_search_service
    from core.search.constants import (
        ENTITY_TYPE_LEGAL_DOCUMENT,
        ENTITY_TYPE_LEGAL_REQUIREMENT,
        GROUP_LEGAL_DOCUMENTS,
        GROUP_LEGAL_REQUIREMENTS,
        RESULT_TYPE_LEGAL_DOCUMENT,
        RESULT_TYPE_LEGAL_REQUIREMENT,
    )
    from core.search.global_search_service import GlobalSearchService
    from core.search.providers.legal_document_search_provider import LegalDocumentSearchProvider
    from core.search.providers.legal_requirement_search_provider import LegalRequirementSearchProvider
    from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_ZAKON
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service


class GlobalSearchLegalTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement

        with get_session() as session:
            session.execute(delete(LegalRequirement))
            session.commit()

    def _legal_service(self) -> GlobalSearchService:
        service = GlobalSearchService()
        service.register_provider(LegalRequirementSearchProvider())
        service.register_provider(LegalDocumentSearchProvider())
        return service

    def test_empty_query_returns_no_results(self) -> None:
        service = self._legal_service()
        self.assertEqual(service.search(""), [])
        self.assertEqual(service.search(" "), [])
        self.assertEqual(service.search("a"), [])

    def test_search_finds_process_by_code(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-005",
            requirement_summary="Hodnocení rizik",
        )

        service = self._legal_service()
        results = service.search("P-005")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].entity_type, ENTITY_TYPE_LEGAL_REQUIREMENT)
        self.assertEqual(results[0].entity_id, requirement.id)
        self.assertEqual(results[0].title, "P-005 – Řízení rizik")
        self.assertEqual(results[0].subtitle, RESULT_TYPE_LEGAL_REQUIREMENT)
        self.assertEqual(results[0].group_label, GROUP_LEGAL_REQUIREMENTS)

    def test_search_finds_process_by_title(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-005",
            requirement_summary="Hodnocení rizik",
        )

        service = self._legal_service()
        results = service.search("rizika")

        self.assertTrue(any(item.entity_id == requirement.id for item in results))

    def test_search_finds_document_by_number_and_year(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262/2006",
            year=2006,
            short_title="ZP",
        )

        service = self._legal_service()
        results = service.search("262/2006")

        match = next(item for item in results if item.entity_id == document.id)
        self.assertEqual(match.entity_type, ENTITY_TYPE_LEGAL_DOCUMENT)
        self.assertEqual(match.subtitle, RESULT_TYPE_LEGAL_DOCUMENT)
        self.assertEqual(match.group_label, GROUP_LEGAL_DOCUMENTS)

    def test_search_finds_document_by_title(self) -> None:
        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262/2006",
            year=2006,
            short_title="ZP",
        )

        service = self._legal_service()
        results = service.search("zákonník práce")

        self.assertTrue(any(item.entity_id == document.id for item in results))

    def test_search_without_results_returns_empty_list(self) -> None:
        service = self._legal_service()
        results = service.search("neexistující dotaz xyz")
        self.assertEqual(results, [])

    def test_open_selected_process_opens_requirement_editor(self) -> None:
        from core.search.openers.legal_requirement_opener import open_legal_requirement_search_result
        from core.search.global_search_result import GlobalSearchResult

        from moduly.pravni_pozadavky.ui.pravni_pozadavky_page import PravniPozadavkyPage

        requirement = legal_requirement_service.create_requirement(
            title="Řízení rizik",
            process_code="P-005",
        )
        host = MagicMock()
        page = PravniPozadavkyPage()
        host._page_widgets = {"pravni_pozadavky": page}
        result = GlobalSearchResult(
            entity_type=ENTITY_TYPE_LEGAL_REQUIREMENT,
            entity_id=requirement.id,
            title="P-005 – Řízení rizik",
            subtitle=RESULT_TYPE_LEGAL_REQUIREMENT,
            group_label=GROUP_LEGAL_REQUIREMENTS,
        )

        with patch(
            "moduly.pravni_pozadavky.ui.pravni_pozadavky_requirements_tab.exec_maximized",
            return_value=False,
        ) as mock_exec:
            self.assertTrue(open_legal_requirement_search_result(host, result))

        mock_exec.assert_called_once()

        host._show.assert_called_once_with("pravni_pozadavky")

    def test_open_selected_document_opens_document_editor(self) -> None:
        from core.search.openers.legal_document_opener import open_legal_document_search_result
        from core.search.global_search_result import GlobalSearchResult
        from moduly.pravni_pozadavky.ui.pravni_pozadavky_page import PravniPozadavkyPage

        document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce",
            number="262/2006",
            year=2006,
        )
        host = MagicMock()
        page = PravniPozadavkyPage()
        host._page_widgets = {"pravni_pozadavky": page}
        result = GlobalSearchResult(
            entity_type=ENTITY_TYPE_LEGAL_DOCUMENT,
            entity_id=document.id,
            title="262/2006 Sb. – Zákoník práce",
            subtitle=RESULT_TYPE_LEGAL_DOCUMENT,
            group_label=GROUP_LEGAL_DOCUMENTS,
        )

        with patch(
            "moduly.pravni_pozadavky.ui.pravni_predpisy_tab.exec_maximized",
            return_value=False,
        ) as mock_exec:
            self.assertTrue(open_legal_document_search_result(host, result))

        mock_exec.assert_called_once()

        host._show.assert_called_once_with("pravni_pozadavky")

    def test_default_service_registers_legal_providers(self) -> None:
        service = build_default_global_search_service()
        provider_keys = {provider.provider_key for provider in service.providers}
        self.assertIn("legal_requirements", provider_keys)
        self.assertIn("legal_documents", provider_keys)


if __name__ == "__main__":
    unittest.main()
