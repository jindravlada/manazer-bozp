"""AUDIT-HANG-FIX-1: get_knowledge_tree nevolá ensure_catalogs per proces."""

from __future__ import annotations

import importlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp(prefix="audit-hang-fix-1-"))
_HOME_PATCHER = patch.object(Path, "home", return_value=_TMP)
_HOME_PATCHER.start()

import core.services.editable_catalog_service as editable_catalog_module
import core.services.storage_service as storage_module

importlib.reload(storage_module)
storage_module.storage_service.ensure_structure()
importlib.reload(editable_catalog_module)

import moduly.audity.sluzby.audit_knowledge_service as knowledge_module

importlib.reload(knowledge_module)

from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service


class AuditHangFix1TestCase(unittest.TestCase):
    def setUp(self) -> None:
        audit_knowledge_service.ensure_catalogs()

    def test_get_knowledge_tree_ensure_true_calls_ensure_catalogs_once(self) -> None:
        ensure_calls = {"count": 0}
        original_ensure = audit_knowledge_service.ensure_catalogs
        original_load = audit_knowledge_service.load_process_knowledge
        load_ensure_flags: list[bool] = []

        def counting_ensure() -> None:
            ensure_calls["count"] += 1
            return original_ensure()

        def tracking_load(process, *, ensure: bool = True):
            load_ensure_flags.append(ensure)
            return original_load(process, ensure=ensure)

        with (
            patch.object(
                audit_knowledge_service,
                "ensure_catalogs",
                side_effect=counting_ensure,
            ),
            patch.object(
                audit_knowledge_service,
                "load_process_knowledge",
                side_effect=tracking_load,
            ),
        ):
            roots = audit_knowledge_service.get_knowledge_tree(ensure=True)

        self.assertGreaterEqual(len(roots), 1)
        self.assertEqual(ensure_calls["count"], 1)
        self.assertGreaterEqual(len(load_ensure_flags), 1)
        self.assertTrue(all(flag is False for flag in load_ensure_flags))

    def test_get_knowledge_tree_ensure_false_skips_ensure_catalogs(self) -> None:
        with patch.object(
            audit_knowledge_service,
            "ensure_catalogs",
            side_effect=AssertionError("ensure_catalogs must not be called"),
        ):
            roots = audit_knowledge_service.get_knowledge_tree(ensure=False)
        self.assertGreaterEqual(len(roots), 1)

    def test_load_process_knowledge_ensure_true_still_calls_ensure(self) -> None:
        processes = audit_knowledge_service.get_processes(ensure=False)
        with_file = next(p for p in processes if p.has_knowledge_file)

        ensure_calls = {"count": 0}
        original_ensure = audit_knowledge_service.ensure_catalogs

        def counting_ensure() -> None:
            ensure_calls["count"] += 1
            return original_ensure()

        with patch.object(
            audit_knowledge_service,
            "ensure_catalogs",
            side_effect=counting_ensure,
        ):
            knowledge = audit_knowledge_service.load_process_knowledge(
                with_file,
                ensure=True,
            )

        self.assertIsNotNone(knowledge)
        self.assertEqual(ensure_calls["count"], 1)


if __name__ == "__main__":
    unittest.main()
