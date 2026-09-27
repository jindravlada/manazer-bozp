"""Test spouštěče Zaloha_zdrojaku.sh. Nespouští skutečnou zálohu projektu."""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "Zaloha_zdrojaku.sh"

_STUB = """#!/bin/sh
printf '%s\\n' "$PWD" > "$LAUNCHER_LOG"
printf '%s\\n' "$@" >> "$LAUNCHER_LOG"
exit "${LAUNCHER_EXIT:-0}"
"""


class SourceBackupLauncherTestCase(unittest.TestCase):
    bozp_skip_schema_guard = True

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        bindir = self.tmp / "bin"
        bindir.mkdir()
        stub = bindir / "python3"
        stub.write_text(_STUB, encoding="utf-8")
        stub.chmod(0o755)
        self._bindir = bindir

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _env(self, log: Path, code: int) -> dict[str, str]:
        env = os.environ.copy()
        env["PATH"] = f"{self._bindir}{os.pathsep}{env.get('PATH', '')}"
        env["LAUNCHER_LOG"] = str(log)
        env["LAUNCHER_EXIT"] = str(code)
        return env

    def _run(self, cwd: Path, code: int = 0) -> subprocess.CompletedProcess[str]:
        log = self.tmp / "log.txt"
        return subprocess.run(
            [str(LAUNCHER)],
            cwd=cwd,
            env=self._env(log, code),
            text=True,
            capture_output=True,
            check=False,
        )

    def _recorded(self) -> list[str]:
        return (self.tmp / "log.txt").read_text(encoding="utf-8").splitlines()

    def test_spoustec_je_spustitelny_a_nema_vlastni_logiku_zalohy(self) -> None:
        mode = LAUNCHER.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR)
        text = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn("python3 tools/backup_source.py", text)
        self.assertNotIn("zipfile", text)
        self.assertNotIn("source_backups", text)

    def test_spusteni_z_korene_preda_kod_a_adresar(self) -> None:
        result = self._run(ROOT, code=0)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertEqual(self._recorded(), [str(ROOT.resolve()), "tools/backup_source.py"])

    def test_spusteni_z_jineho_adresare(self) -> None:
        elsewhere = self.tmp / "jinde"
        elsewhere.mkdir()
        result = self._run(elsewhere, code=0)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self._recorded(), [str(ROOT.resolve()), "tools/backup_source.py"])

    def test_chyba_pythonu_zachova_navratovy_kod_a_ceskou_hlasku(self) -> None:
        result = self._run(self.tmp, code=4)
        self.assertEqual(result.returncode, 4)
        self.assertIn(
            "Zálohu zdrojového projektu se nepodařilo dokončit.",
            result.stderr,
        )

    def test_chybi_python3(self) -> None:
        bindir = self.tmp / "bez-pythonu"
        bindir.mkdir()
        for name in ("bash", "env", "readlink", "dirname"):
            os.symlink(shutil.which(name), bindir / name)
        env = os.environ.copy()
        env["PATH"] = str(bindir)
        result = subprocess.run(
            [str(LAUNCHER)],
            cwd=self.tmp,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 127)
        self.assertIn("není dostupný python3", result.stderr)


if __name__ == "__main__":
    unittest.main()
