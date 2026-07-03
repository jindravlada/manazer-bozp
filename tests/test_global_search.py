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

    from core.search.constants import SOURCE_TYPE_TASK
    from core.search.global_search_service import GlobalSearchService
    from core.search.search_provider import SearchProvider
    from core.search.search_result import SearchResult
    from core.search.providers.task_search_provider import TaskSearchProvider
    from moduly.ukoly.sluzby.task_service import task_service


class _BrokenProvider(SearchProvider):
    provider_key = "broken"
    module_key = "broken"
    module_label = "Broken"

    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        raise RuntimeError("provider failure")


class _StaticProvider(SearchProvider):
    provider_key = "static"
    module_key = "static"
    module_label = "Static"

    def __init__(self, results: list[SearchResult]) -> None:
        self._results = results

    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        return self._results[:limit]


class SearchResultTestCase(unittest.TestCase):
    def test_search_result_can_be_created(self) -> None:
        result = SearchResult(
            source_type=SOURCE_TYPE_TASK,
            source_id=1,
            title="Kontrola OOPP",
            subtitle="Aktivní | Novák",
            description="Doplnit OOPP",
            module_key="ukoly",
            module_label="Úkoly",
            priority=100,
            metadata={"status": "Aktivní"},
        )

        self.assertEqual(result.source_type, "task")
        self.assertEqual(result.source_id, 1)
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
        result = SearchResult(
            source_type=SOURCE_TYPE_TASK,
            source_id=1,
            title="Test",
            module_key="ukoly",
            module_label="Úkoly",
        )
        host = MagicMock()

        self.assertTrue(service.open_result(result, host))
        handler.assert_called_once_with(host, result)

    def test_open_result_returns_false_for_unknown_source_type(self) -> None:
        service = GlobalSearchService()
        result = SearchResult(
            source_type="audit",
            source_id=1,
            title="Audit",
            module_key="audity",
            module_label="Audity",
        )

        self.assertFalse(service.open_result(result, host=None))

    def test_task_opener_opens_ukoly_page(self) -> None:
        from unittest.mock import MagicMock

        from core.search.bootstrap import build_default_search_result_opener

        task = task_service.create_task(title="Globální test úkolu")
        opener = build_default_search_result_opener()
        service = GlobalSearchService(result_opener=opener)
        result = SearchResult(
            source_type=SOURCE_TYPE_TASK,
            source_id=task.id,
            title=task.title,
            module_key="ukoly",
            module_label="Úkoly",
        )

        host = MagicMock()
        ukoly_page = MagicMock()
        host._page_widgets = {"ukoly": ukoly_page}

        with patch("moduly.ukoly.ui.task_dialog.TaskDialog") as mock_dialog:
            mock_dialog.return_value.exec.return_value = 0
            self.assertTrue(service.open_result(result, host))

        host._show.assert_called_once_with("ukoly")
        ukoly_page.open_task.assert_called_once_with(task.id)

    def test_deduplicates_by_source_type_and_id(self) -> None:
        service = GlobalSearchService()
        duplicate = SearchResult(
            source_type=SOURCE_TYPE_TASK,
            source_id=7,
            title="A",
            module_key="ukoly",
            module_label="Úkoly",
            priority=10,
        )
        better = SearchResult(
            source_type=SOURCE_TYPE_TASK,
            source_id=7,
            title="A",
            module_key="ukoly",
            module_label="Úkoly",
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
                    SearchResult(
                        source_type=SOURCE_TYPE_TASK,
                        source_id=1,
                        title="Beta",
                        module_key="ukoly",
                        module_label="Úkoly",
                        priority=50,
                    ),
                    SearchResult(
                        source_type=SOURCE_TYPE_TASK,
                        source_id=2,
                        title="Alfa",
                        module_key="ukoly",
                        module_label="Úkoly",
                        priority=100,
                    ),
                    SearchResult(
                        source_type=SOURCE_TYPE_TASK,
                        source_id=3,
                        title="Gama",
                        module_key="ukoly",
                        module_label="Úkoly",
                        priority=50,
                    ),
                ]
            )
        )

        results = service.search("aa", limit=10)

        self.assertEqual([item.source_id for item in results], [2, 1, 3])

    def test_limit_is_applied(self) -> None:
        service = GlobalSearchService()
        service.register_provider(
            _StaticProvider(
                [
                    SearchResult(
                        source_type=SOURCE_TYPE_TASK,
                        source_id=index,
                        title=f"Úkol {index}",
                        module_key="ukoly",
                        module_label="Úkoly",
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
                    SearchResult(
                        source_type=SOURCE_TYPE_TASK,
                        source_id=1,
                        title="Zachovaný úkol",
                        module_key="ukoly",
                        module_label="Úkoly",
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


if __name__ == "__main__":
    unittest.main()
