import importlib
import inspect
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

    from core.search.constants import (
        SOURCE_TYPE_ACCIDENT,
        SOURCE_TYPE_AUDIT,
        SOURCE_TYPE_INSPECTION,
        SOURCE_TYPE_TASK,
    )
    from core.search.global_search_service import GlobalSearchService
    from core.search.providers.accident_search_provider import AccidentSearchProvider
    from core.search.providers.audit_search_provider import AuditSearchProvider
    from core.search.providers.proverky_search_provider import ProverkySearchProvider
    from core.search.providers.task_search_provider import TaskSearchProvider
    from core.search.search_provider import SearchProvider
    from core.search.global_search_result import GlobalSearchResult
    from core.search.search_result import SearchResult
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.ukoly.sluzby.task_service import task_service


class _BrokenProvider(SearchProvider):
    provider_key = "broken"
    module_key = "broken"
    module_label = "Broken"

    def search(self, query: str, *, limit: int) -> list[GlobalSearchResult]:
        raise RuntimeError("provider failure")


class _StaticProvider(SearchProvider):
    provider_key = "static"
    module_key = "static"
    module_label = "Static"

    def __init__(self, results: list[GlobalSearchResult]) -> None:
        self._results = results

    def search(self, query: str, *, limit: int) -> list[GlobalSearchResult]:
        return self._results[:limit]


class SearchResultTestCase(unittest.TestCase):
    def test_search_result_can_be_created(self) -> None:
        result = GlobalSearchResult(
            entity_type=SOURCE_TYPE_TASK,
            entity_id=1,
            title="Kontrola OOPP",
            subtitle="Aktivní | Novák",
            description="Doplnit OOPP",
            module_key="ukoly",
            group_label="Úkoly",
            priority=100,
            metadata={"status": "Aktivní"},
        )

        self.assertEqual(result.entity_type, "task")
        self.assertEqual(result.entity_id, 1)
        self.assertIn("Kontrola OOPP", result.display)
        self.assertEqual(result.record_type, "task")
        self.assertEqual(result.record_id, 1)


class GlobalSearchServiceTestCase(unittest.TestCase):
    def test_registers_providers(self) -> None:
        service = GlobalSearchService()
        provider = TaskSearchProvider()

        service.register_provider(provider)

        self.assertEqual(len(service.providers), 1)
        self.assertIs(service.providers[0], provider)

    def test_short_query_returns_empty_list(self) -> None:
        service = GlobalSearchService()
        service.register_provider(TaskSearchProvider())

        self.assertEqual(service.search("a"), [])
        self.assertEqual(service.search("  "), [])

    def test_service_has_no_hardcoded_task_module_imports(self) -> None:
        source = inspect.getsource(GlobalSearchService)
        self.assertNotIn("ukoly", source)
        self.assertNotIn("task_service", source)
        self.assertNotIn("TaskSearchProvider", source)
        self.assertNotIn("TaskDialog", source)

    def test_open_result_delegates_to_opener(self) -> None:
        from unittest.mock import MagicMock

        from core.search.search_result_opener import SearchResultOpener

        opener = SearchResultOpener()
        handler = MagicMock(return_value=True)
        opener.register(SOURCE_TYPE_TASK, handler)
        service = GlobalSearchService(result_opener=opener)
        result = GlobalSearchResult(
            entity_type=SOURCE_TYPE_TASK,
            entity_id=1,
            title="Test",
            module_key="ukoly",
            group_label="Úkoly",
        )
        host = MagicMock()

        self.assertTrue(service.open_result(result, host))
        handler.assert_called_once_with(host, result)

    def test_open_result_returns_false_for_unknown_source_type(self) -> None:
        service = GlobalSearchService()
        result = GlobalSearchResult(
            entity_type="audit",
            entity_id=1,
            title="Audit",
            module_key="audity",
            group_label="Audity",
        )

        self.assertFalse(service.open_result(result, host=None))

    def test_task_opener_opens_agenda_page(self) -> None:
        from unittest.mock import MagicMock

        from core.search.bootstrap import build_default_search_result_opener

        task = task_service.create_task(title="Globální test úkolu")
        opener = build_default_search_result_opener()
        service = GlobalSearchService(result_opener=opener)
        result = GlobalSearchResult(
            entity_type=SOURCE_TYPE_TASK,
            entity_id=task.id,
            title=task.title,
            module_key="ukoly",
            group_label="Úkoly",
        )

        host = MagicMock()
        agenda_page = MagicMock()
        host._page_widgets = {"agenda": agenda_page, "ukoly": MagicMock()}

        with patch("moduly.ukoly.ui.task_dialog.TaskDialog") as mock_dialog:
            mock_dialog.return_value.exec.return_value = 0
            self.assertTrue(service.open_result(result, host))

        host._show.assert_called_once_with("agenda")
        agenda_page.open_task.assert_called_once_with(task.id)
        host._page_widgets["ukoly"].open_task.assert_not_called()

    def test_deduplicates_by_source_type_and_id(self) -> None:
        service = GlobalSearchService()
        duplicate = GlobalSearchResult(
            entity_type=SOURCE_TYPE_TASK,
            entity_id=7,
            title="A",
            module_key="ukoly",
            group_label="Úkoly",
            priority=10,
        )
        better = GlobalSearchResult(
            entity_type=SOURCE_TYPE_TASK,
            entity_id=7,
            title="A",
            module_key="ukoly",
            group_label="Úkoly",
            priority=90,
        )
        service.register_provider(_StaticProvider([duplicate, better]))

        results = service.search("aa", limit=10)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].priority, 90)

    def test_sorts_by_priority_desc_then_title(self) -> None:
        service = GlobalSearchService()
        service.register_provider(
            _StaticProvider(
                [
                    GlobalSearchResult(
                        entity_type=SOURCE_TYPE_TASK,
                        entity_id=1,
                        title="Beta",
                        module_key="ukoly",
                        group_label="Úkoly",
                        priority=50,
                    ),
                    GlobalSearchResult(
                        entity_type=SOURCE_TYPE_TASK,
                        entity_id=2,
                        title="Alfa",
                        module_key="ukoly",
                        group_label="Úkoly",
                        priority=100,
                    ),
                    GlobalSearchResult(
                        entity_type=SOURCE_TYPE_TASK,
                        entity_id=3,
                        title="Gama",
                        module_key="ukoly",
                        group_label="Úkoly",
                        priority=50,
                    ),
                ]
            )
        )

        results = service.search("aa", limit=10)

        self.assertEqual([item.entity_id for item in results], [2, 1, 3])

    def test_limit_is_applied(self) -> None:
        service = GlobalSearchService()
        service.register_provider(
            _StaticProvider(
                [
                    GlobalSearchResult(
                        entity_type=SOURCE_TYPE_TASK,
                        entity_id=index,
                        title=f"Úkol {index}",
                        module_key="ukoly",
                        group_label="Úkoly",
                        priority=index,
                    )
                    for index in range(5)
                ]
            )
        )

        results = service.search("aa", limit=2)

        self.assertEqual(len(results), 2)

    def test_provider_failure_does_not_break_search(self) -> None:
        service = GlobalSearchService()
        service.register_provider(_BrokenProvider())
        service.register_provider(
            _StaticProvider(
                [
                    GlobalSearchResult(
                        entity_type=SOURCE_TYPE_TASK,
                        entity_id=1,
                        title="Zachovaný úkol",
                        module_key="ukoly",
                        group_label="Úkoly",
                        priority=10,
                    )
                ]
            )
        )

        results = service.search("aa", limit=10)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Zachovaný úkol")


class TaskSearchProviderTestCase(unittest.TestCase):
    def test_finds_task_by_title(self) -> None:
        task = task_service.create_task(
            title="Revize hydrantů na halě A",
            description="Roční kontrola",
        )

        provider = TaskSearchProvider()
        results = provider.search("hydrant", limit=10)

        self.assertTrue(any(item.source_id == task.id for item in results))
        match = next(item for item in results if item.source_id == task.id)
        self.assertEqual(match.source_type, SOURCE_TYPE_TASK)
        self.assertEqual(match.module_key, "ukoly")
        self.assertEqual(match.module_label, "Úkoly")
        self.assertEqual(match.priority, 100)

    def test_finds_task_by_description_with_lower_priority(self) -> None:
        task = task_service.create_task(
            title="Obecné opatření",
            description="Specifický popis zábradlí",
        )

        provider = TaskSearchProvider()
        results = provider.search("zábradlí", limit=10)

        match = next(item for item in results if item.source_id == task.id)
        self.assertEqual(match.priority, 50)

    def test_finds_task_by_workplace(self) -> None:
        task = task_service.create_task(
            title="Kontrola",
            description="",
            workplace_id=None,
        )
        task.workplace_name = "Provoz Gamma"
        task_service.repository.update(task)

        provider = TaskSearchProvider()
        results = provider.search("gamma", limit=10)

        self.assertTrue(any(item.source_id == task.id for item in results))

    def test_title_match_sorted_before_description_match(self) -> None:
        title_task = task_service.create_task(
            title="Zábradlí servis",
            description="Jiný text",
        )
        description_task = task_service.create_task(
            title="Servis",
            description="Oprava zábradlí",
        )

        service = GlobalSearchService()
        service.register_provider(TaskSearchProvider())
        results = service.search("zábradlí", limit=10)

        ids = [item.source_id for item in results if item.source_id in {title_task.id, description_task.id}]
        self.assertEqual(ids[0], title_task.id)


class AuditSearchProviderTestCase(unittest.TestCase):
    def test_finds_audit_by_number(self) -> None:
        from moduly.nastaveni.sluzby.settings_service import settings_service

        workplace = settings_service.save_workplace(name="Provoz Vyhledávání")
        audit = audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            title="Poznámka k auditu",
        )

        provider = AuditSearchProvider()
        results = provider.search(str(audit.id), limit=10)

        match = next(item for item in results if item.source_id == audit.id)
        self.assertEqual(match.source_type, SOURCE_TYPE_AUDIT)
        self.assertEqual(match.module_key, "audity")
        self.assertEqual(match.module_label, "Audity")

    def test_finds_audit_by_workplace(self) -> None:
        from moduly.nastaveni.sluzby.settings_service import settings_service

        workplace = settings_service.save_workplace(name="Provoz Hradec Globální")
        audit = audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
        )

        provider = AuditSearchProvider()
        results = provider.search("hradec glob", limit=10)

        self.assertTrue(any(item.source_id == audit.id for item in results))


class ProverkySearchProviderTestCase(unittest.TestCase):
    def test_finds_inspection_by_title(self) -> None:
        from moduly.nastaveni.sluzby.settings_service import settings_service

        workplace = settings_service.save_workplace(name="Provoz Epsilon")
        inspection = bozp_inspection_service.create_inspection(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            title="Roční kontrola BOZP skladu",
        )

        provider = ProverkySearchProvider()
        results = provider.search("skladu", limit=10)

        match = next(item for item in results if item.source_id == inspection.id)
        self.assertEqual(match.source_type, SOURCE_TYPE_INSPECTION)
        self.assertEqual(match.module_key, "proverky")
        self.assertEqual(match.module_label, "Prověrky BOZP")

    def test_finds_inspection_by_workplace(self) -> None:
        from moduly.nastaveni.sluzby.settings_service import settings_service

        workplace = settings_service.save_workplace(name="Provoz Olomouc Globální")
        inspection = bozp_inspection_service.create_inspection(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
        )

        provider = ProverkySearchProvider()
        results = provider.search("olomouc glob", limit=10)

        self.assertTrue(any(item.source_id == inspection.id for item in results))


class AccidentSearchProviderTestCase(unittest.TestCase):
    def test_finds_accident_by_employee_name(self) -> None:
        from datetime import date

        accident = accident_service.create_accident(
            jmeno_prijmeni="Petr Svoboda",
            popis_urazoveho_deje="Uklouznutí na mokrém povrchu",
            accident_date=date(2026, 3, 15),
        )

        provider = AccidentSearchProvider()
        results = provider.search("svoboda", limit=10)

        match = next(item for item in results if item.source_id == accident.id)
        self.assertEqual(match.source_type, SOURCE_TYPE_ACCIDENT)
        self.assertEqual(match.module_key, "kniha_urazu")
        self.assertEqual(match.module_label, "Kniha úrazů")

    def test_finds_accident_by_description(self) -> None:
        from datetime import date

        accident = accident_service.create_accident(
            jmeno_prijmeni="Jan Novák",
            popis_urazoveho_deje="Pád ze žebříku ve skladu",
            accident_date=date(2026, 1, 10),
        )

        provider = AccidentSearchProvider()
        results = provider.search("žebříku", limit=10)

        match = next(item for item in results if item.source_id == accident.id)
        self.assertEqual(match.priority, 50)


class SearchResultOpenerIntegrationTestCase(unittest.TestCase):
    def test_audit_opener_opens_audity_page(self) -> None:
        from unittest.mock import MagicMock

        from core.search.bootstrap import build_default_search_result_opener
        from moduly.nastaveni.sluzby.settings_service import settings_service

        workplace = settings_service.save_workplace(name="Provoz Opener Audit")
        audit = audit_service.create_audit(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
        )
        opener = build_default_search_result_opener()
        service = GlobalSearchService(result_opener=opener)
        result = GlobalSearchResult(
            entity_type=SOURCE_TYPE_AUDIT,
            entity_id=audit.id,
            title=audit.number,
            module_key="audity",
            group_label="Audity",
        )

        host = MagicMock()
        audity_page = MagicMock()
        host._page_widgets = {"audity": audity_page}

        with patch("moduly.audity.ui.audit_dialog.AuditDialog") as mock_dialog:
            mock_dialog.return_value.exec.return_value = 0
            self.assertTrue(service.open_result(result, host))

        host._show.assert_called_once_with("audity")
        audity_page.open_audit.assert_called_once_with(audit.id)

    def test_inspection_opener_opens_proverky_page(self) -> None:
        from unittest.mock import MagicMock

        from core.search.bootstrap import build_default_search_result_opener
        from moduly.nastaveni.sluzby.settings_service import settings_service

        workplace = settings_service.save_workplace(name="Provoz Opener Prověrka")
        inspection = bozp_inspection_service.create_inspection(
            workplace_id=workplace.id,
            workplace_name=workplace.name,
        )
        opener = build_default_search_result_opener()
        service = GlobalSearchService(result_opener=opener)
        result = GlobalSearchResult(
            entity_type=SOURCE_TYPE_INSPECTION,
            entity_id=inspection.id,
            title=inspection.number,
            module_key="proverky",
            group_label="Prověrky BOZP",
        )

        host = MagicMock()
        proverky_page = MagicMock()
        host._page_widgets = {"proverky": proverky_page}

        with patch("moduly.proverky.ui.bozp_inspection_dialog.BozpInspectionDialog") as mock_dialog:
            mock_dialog.return_value.exec.return_value = 0
            self.assertTrue(service.open_result(result, host))

        host._show.assert_called_once_with("proverky")
        proverky_page.open_inspection.assert_called_once_with(inspection.id)

    def test_accident_opener_opens_kniha_urazu_page(self) -> None:
        from datetime import date
        from unittest.mock import MagicMock

        from core.search.bootstrap import build_default_search_result_opener

        accident = accident_service.create_accident(
            jmeno_prijmeni="Marie Dvořáková",
            accident_date=date(2026, 2, 1),
        )
        opener = build_default_search_result_opener()
        service = GlobalSearchService(result_opener=opener)
        result = GlobalSearchResult(
            entity_type=SOURCE_TYPE_ACCIDENT,
            entity_id=accident.id,
            title=accident.number,
            module_key="kniha_urazu",
            group_label="Kniha úrazů",
        )

        host = MagicMock()
        kniha_page = MagicMock()
        host._page_widgets = {"kniha_urazu": kniha_page}

        with patch("moduly.kniha_urazu.ui.accident_dialog.AccidentDialog") as mock_dialog:
            mock_dialog.return_value.exec.return_value = 0
            self.assertTrue(service.open_result(result, host))

        host._show.assert_called_once_with("kniha_urazu")
        kniha_page.open_accident.assert_called_once_with(accident.id)

    def test_service_has_no_dialog_imports(self) -> None:
        source = inspect.getsource(GlobalSearchService)
        self.assertNotIn("TaskDialog", source)
        self.assertNotIn("AuditDialog", source)
        self.assertNotIn("BozpInspectionDialog", source)
        self.assertNotIn("AccidentDialog", source)


if __name__ == "__main__":
    unittest.main()
