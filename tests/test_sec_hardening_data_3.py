"""SEC-HARDENING-DATA-3: výchozí vypnutí debug diagnostiky protokolu auditu."""

from __future__ import annotations

import os
import shutil
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from moduly.audity.sluzby import protokol_audit_service as protokol_module
from moduly.audity.sluzby.protokol_audit_service import (
    _DIAG_ENV,
    _DIAG_LOG_NAME,
    _diag,
    _diag_is_enabled,
    protokol_audit_service,
)

_TEST_ROOT = Path(__file__).resolve().parents[1] / ".test-tmp" / "sec-hardening-data-3"


class SecHardeningData3TestCase(unittest.TestCase):
    def setUp(self) -> None:
        if _TEST_ROOT.exists():
            shutil.rmtree(_TEST_ROOT)
        self.logs_dir = _TEST_ROOT / "logy"
        self.logs_dir.mkdir(parents=True)
        self._env = patch.dict(os.environ, {}, clear=False)
        self._env.start()
        os.environ.pop(_DIAG_ENV, None)
        self.addCleanup(self._env.stop)

    def tearDown(self) -> None:
        shutil.rmtree(_TEST_ROOT, ignore_errors=True)

    def _storage(self) -> SimpleNamespace:
        return SimpleNamespace(
            ensure_structure=lambda: None,
            logs_dir=self.logs_dir,
        )

    def test_default_diag_is_off(self) -> None:
        self.assertFalse(protokol_module._DIAG_ENABLED)
        self.assertFalse(_diag_is_enabled())
        with patch.object(protokol_module, "storage_service", self._storage()), patch(
            "builtins.print"
        ) as mock_print:
            _diag("nesmi-se-zapsat")
        mock_print.assert_not_called()
        self.assertEqual(list(self.logs_dir.iterdir()), [])

    def test_env_enables_diag_and_writes_log(self) -> None:
        os.environ[_DIAG_ENV] = "1"
        self.assertTrue(_diag_is_enabled())
        with patch.object(protokol_module, "storage_service", self._storage()), patch(
            "builtins.print"
        ) as mock_print:
            _diag("diag-zapnuta")
        log_path = self.logs_dir / _DIAG_LOG_NAME
        self.assertTrue(log_path.is_file())
        self.assertIn("diag-zapnuta", log_path.read_text(encoding="utf-8"))
        mock_print.assert_called()

    def test_env_zero_keeps_diag_off(self) -> None:
        os.environ[_DIAG_ENV] = "0"
        self.assertFalse(_diag_is_enabled())

    def test_generate_still_validates_without_diag(self) -> None:
        with patch.object(protokol_module, "storage_service", self._storage()), patch(
            "builtins.print"
        ) as mock_print:
            with self.assertRaises(ValueError):
                protokol_audit_service.generate_for_audit(None)
        mock_print.assert_not_called()
        self.assertEqual(list(self.logs_dir.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
