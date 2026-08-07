"""Testovací balíček – společná izolace schématu SQLite pro celou sadu."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Zapne ensure_current_schema_if_needed() v db_isolation (pouze testy).
os.environ["MANAGER_BOZP_TEST_AUTO_SCHEMA"] = "1"

_original_testcase_run = unittest.TestCase.run


def _run_with_schema_guard(self: unittest.TestCase, result=None):
    """Před a po každém testu zajistí aktuální schéma na aktivní testovací DB."""
    from tests.db_isolation import ensure_current_schema_if_needed

    if not getattr(self, "bozp_skip_schema_guard", False):
        try:
            ensure_current_schema_if_needed()
        except Exception:
            pass

    outcome = _original_testcase_run(self, result)

    if not getattr(self, "bozp_skip_schema_guard", False):
        try:
            ensure_current_schema_if_needed()
        except Exception:
            pass

    return outcome


unittest.TestCase.run = _run_with_schema_guard  # type: ignore[method-assign]
