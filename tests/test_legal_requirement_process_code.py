import importlib
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

    from moduly.pravni_pozadavky.constants import (
        format_process_code,
        is_valid_process_code,
        parse_process_code,
        parse_process_code_number,
        process_code_sort_key,
    )
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import legal_requirement_service
    from moduly.pravni_pozadavky.ui.legal_requirement_table import COL_CODE, LegalRequirementTable


class LegalRequirementProcessCodeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.pravni_pozadavky.modely.legal_requirement_source import LegalRequirementSource

        with get_session() as session:
            session.execute(delete(LegalRequirementSource))
            session.execute(delete(LegalRequirement))
            session.commit()

    def test_create_assigns_sequential_process_codes(self) -> None:
        first = legal_requirement_service.create_requirement(
            title="První proces",
            requirement_summary="A",
        )
        second = legal_requirement_service.create_requirement(
            title="Druhý proces",
            requirement_summary="B",
        )

        self.assertEqual(first.process_code, "P-001")
        self.assertEqual(second.process_code, "P-002")

    def test_archived_code_is_not_reused(self) -> None:
        first = legal_requirement_service.create_requirement(
            title="P-001",
            requirement_summary="A",
        )
        legal_requirement_service.create_requirement(
            title="P-002",
            requirement_summary="B",
        )
        legal_requirement_service.archive_requirement(first.id)

        third = legal_requirement_service.create_requirement(
            title="P-003",
            requirement_summary="C",
        )

        self.assertEqual(third.process_code, "P-003")
        archived = legal_requirement_service.get_by_id(first.id)
        assert archived is not None
        self.assertEqual(archived.process_code, "P-001")

    def test_merge_sets_merged_into_and_keeps_source_code(self) -> None:
        target = legal_requirement_service.create_requirement(
            title="Prevence rizik",
            requirement_summary="Cíl",
        )
        source = legal_requirement_service.create_requirement(
            title="Kontrola dokumentace",
            requirement_summary="Zdroj",
        )
        source_code = source.process_code
        target_code = target.process_code

        legal_requirement_service.merge_process_requirements(source.id, target.id)

        archived_source = legal_requirement_service.get_by_id(source.id)
        assert archived_source is not None
        self.assertEqual(archived_source.process_code, source_code)
        self.assertEqual(archived_source.merged_into_requirement_id, target.id)
        self.assertFalse(archived_source.active)

        merged_target = legal_requirement_service.get_by_id(target.id)
        assert merged_target is not None
        self.assertEqual(merged_target.process_code, target_code)

    def test_process_code_sort_key_sorts_numerically(self) -> None:
        class _Item:
            def __init__(self, process_code: str):
                self.process_code = process_code

        items = [_Item("P-010"), _Item("P-002"), _Item("P-001")]
        sorted_codes = [item.process_code for item in sorted(items, key=process_code_sort_key)]
        self.assertEqual(sorted_codes, ["P-001", "P-002", "P-010"])

    def test_process_code_sort_key_for_root_and_child_codes(self) -> None:
        class _Item:
            def __init__(self, process_code: str):
                self.process_code = process_code

        root = _Item("P-015")
        child = _Item("P-015.1")

        self.assertEqual(process_code_sort_key(root), (0, 15, 0))
        self.assertEqual(process_code_sort_key(child), (0, 15, 1))

    def test_process_code_sort_key_sorts_child_codes_after_parent(self) -> None:
        class _Item:
            def __init__(self, process_code: str):
                self.process_code = process_code

        items = [
            _Item("P-016"),
            _Item("P-015.2"),
            _Item("P-014"),
            _Item("P-015"),
            _Item("P-015.1"),
        ]
        sorted_codes = [item.process_code for item in sorted(items, key=process_code_sort_key)]
        self.assertEqual(
            sorted_codes,
            ["P-014", "P-015", "P-015.1", "P-015.2", "P-016"],
        )

    def test_invalid_process_codes_use_sort_fallback_and_are_rejected_on_create(self) -> None:
        class _Item:
            def __init__(self, process_code: str):
                self.process_code = process_code

        invalid = _Item("P-015-CHILD")
        self.assertIsNone(parse_process_code("P-015-CHILD"))
        self.assertFalse(is_valid_process_code("P-015-CHILD"))
        self.assertEqual(process_code_sort_key(invalid), (1, "p-015-child"))

        with self.assertRaisesRegex(ValueError, "neplatný formát"):
            legal_requirement_service.create_requirement(
                title="Neplatný kód",
                process_code="P-015-CHILD",
            )

    def test_create_accepts_child_process_code(self) -> None:
        legal_requirement_service.create_requirement(
            title="Řízení VTZ",
            process_code="P-015",
        )
        child = legal_requirement_service.create_requirement(
            title="Řízení vyhrazených elektrických zařízení",
            process_code="P-015.1",
        )

        self.assertEqual(child.process_code, "P-015.1")

    def test_table_shows_process_code_column(self) -> None:
        requirement = legal_requirement_service.create_requirement(
            title="Systém řízení BOZP",
            requirement_summary="Test",
        )

        table = LegalRequirementTable()
        table.load_requirements([requirement])

        self.assertEqual(table.item(0, COL_CODE).text(), requirement.process_code)

    def test_format_and_parse_process_code(self) -> None:
        self.assertEqual(format_process_code(4), "P-004")
        self.assertEqual(parse_process_code_number("P-004"), 4)
        self.assertEqual(parse_process_code_number("P-015.1"), 15)
        self.assertEqual(parse_process_code("P-015.1"), parse_process_code("p-015.1"))
        self.assertIsNone(parse_process_code_number("X-004"))
        self.assertTrue(is_valid_process_code("P-015"))
        self.assertTrue(is_valid_process_code("P-015.2"))
        self.assertFalse(is_valid_process_code("P-015.1.2"))


if __name__ == "__main__":
    unittest.main()
