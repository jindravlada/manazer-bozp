"""Testy lokální zálohy zdrojového projektu. Nezálohují skutečný pracovní strom."""

from __future__ import annotations

import hashlib
import io
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from core.version import APP_VERSION
from tools.backup_source import (
    SourceBackupError,
    create_source_backup,
    main,
    sha256_file,
    source_backup_filename,
    verify_zip,
)

WHEN = datetime(2026, 9, 27, 8, 15)


class SourceBackupTestCase(unittest.TestCase):
    bozp_skip_schema_guard = True

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name) / "projekt"
        self.root.mkdir()
        self._write("main.py", "print('bozp')\n")
        self._write("core/backup/engine.py", "# modul záloh aplikace\n")
        self._write("README.md", "readme\n")
        self._write(".gitignore", "source_backups/\n")
        self._write(".git/HEAD", "ref: refs/heads/master\n")
        self._write(".git/refs/heads/master", "abc\n")
        self._write(".venv/lib.py", "venv\n")
        self._write("moduly/__pycache__/widget.pyc", "pyc")
        self._write("build/out.bin", "build")
        self._write("dist/app.bin", "dist")
        self._write("source_backups/stara.zip", "old")
        self._write("data/databaze/.gitkeep", "")
        self._write("data/databaze/manager_bozp.db", "sqlite-user")
        self._write("data/prilohy/doklad.pdf", "priloha")
        self._write("data/nastaveni/settings.json", '{"theme": "light"}')
        self._write("data/.gitkeep", "")
        self._write("Zalohy/instance.mbbackup", "backup")
        self._write(".env", "TOKEN=tajne\n")
        self._write(".env.local", "API=tajne\n")
        self._write("credentials.json", "{}")
        self._write("api_token.json", "{}")
        self._write("oauth.json", "{}")
        self._write("secret.pem", "pem")
        self._write("id_rsa", "key")
        self._write("ManagerBOZP.AppImage", "image")
        self._write("zdroje/preklady/qtbase_cs.qm", "qm")
        self._write("jinde/dialog.qm", "qm")
        self._write("ManazerBOZP.spec", "# spec\n")
        self._write("M-BOZP-4.0.7.zip", "archiv")
        self._write("manager-bozp-backup-stary.zip", "archiv")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, relative: str, content: str) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _create(self) -> zipfile.ZipFile:
        result = create_source_backup(self.root, when=WHEN)
        self.assertTrue(result.path.is_file())
        self.assertEqual(result.path.parent.name, "source_backups")
        return result

    def _names(self) -> set[str]:
        result = self._create()
        with zipfile.ZipFile(result.path) as archive:
            return set(archive.namelist())

    def test_vytvori_zip_s_aktualni_verzi(self) -> None:
        result = self._create()
        expected = source_backup_filename(APP_VERSION, WHEN)
        self.assertEqual(result.path.name, expected)
        self.assertIn(APP_VERSION, result.path.name)
        self.assertTrue(result.path.name.endswith(".zip"))

    def test_zahrne_bezny_zdrojovy_soubor(self) -> None:
        names = self._names()
        self.assertIn("main.py", names)
        self.assertIn("core/backup/engine.py", names)
        self.assertIn("README.md", names)
        self.assertIn(".gitignore", names)
        self.assertIn("ManazerBOZP.spec", names)
        self.assertIn("zdroje/preklady/qtbase_cs.qm", names)
        self.assertIn("data/.gitkeep", names)
        self.assertIn("data/databaze/.gitkeep", names)

    def test_zahrne_git(self) -> None:
        names = self._names()
        self.assertIn(".git/HEAD", names)
        self.assertIn(".git/refs/heads/master", names)

    def test_vynecha_venv(self) -> None:
        self.assertNotIn(".venv/lib.py", self._names())

    def test_vynecha_pycache(self) -> None:
        self.assertNotIn("moduly/__pycache__/widget.pyc", self._names())

    def test_vynecha_build_a_dist(self) -> None:
        names = self._names()
        self.assertNotIn("build/out.bin", names)
        self.assertNotIn("dist/app.bin", names)

    def test_vynecha_source_backups(self) -> None:
        names = self._names()
        self.assertFalse(any(name.startswith("source_backups/") for name in names))

    def test_vynecha_databaze_a_uzivatelska_data(self) -> None:
        names = self._names()
        self.assertNotIn("data/databaze/manager_bozp.db", names)
        self.assertNotIn("data/prilohy/doklad.pdf", names)
        self.assertNotIn("data/nastaveni/settings.json", names)
        self.assertNotIn("Zalohy/instance.mbbackup", names)

    def test_vynecha_secrets_a_tokeny(self) -> None:
        names = self._names()
        for excluded in (
            ".env",
            ".env.local",
            "credentials.json",
            "api_token.json",
            "oauth.json",
            "secret.pem",
            "id_rsa",
        ):
            self.assertNotIn(excluded, names)

    def test_kontrola_integrity_zipu(self) -> None:
        result = self._create()
        verify_zip(result.path)
        with zipfile.ZipFile(result.path) as archive:
            self.assertIsNone(archive.testzip())

    def test_sha256_odpovida_souboru(self) -> None:
        result = self._create()
        self.assertEqual(result.sha256, sha256_file(result.path))
        self.assertEqual(result.sha256, hashlib.sha256(result.path.read_bytes()).hexdigest())
        self.assertEqual(len(result.sha256), 64)
        self.assertEqual(result.size_bytes, result.path.stat().st_size)
        self.assertGreater(result.file_count, 0)

    def test_neuplny_zip_se_nepublikuje(self) -> None:
        existing = self.root / "source_backups" / "Manazer_BOZP_source_0_stary.zip"
        existing.write_bytes(b"ponechat")
        with patch(
            "tools.backup_source.zipfile.ZipFile.testzip",
            return_value="poskozeny",
        ):
            with self.assertRaises(SourceBackupError):
                create_source_backup(self.root, when=WHEN)
        backups = self.root / "source_backups"
        finished = backups / source_backup_filename(APP_VERSION, WHEN)
        self.assertFalse(finished.exists())
        self.assertFalse(list(backups.glob("*.partial")))
        self.assertEqual(existing.read_bytes(), b"ponechat")

    def test_selhani_zapisu_smaze_rozpracovany_soubor(self) -> None:
        with patch(
            "tools.backup_source.zipfile.ZipFile.write",
            side_effect=OSError("disk"),
        ):
            with self.assertRaises(SourceBackupError):
                create_source_backup(self.root, when=WHEN)
        backups = self.root / "source_backups"
        published = [
            path.name
            for path in backups.iterdir()
            if path.name.startswith("Manazer_BOZP_source_") and path.name.endswith(".zip")
        ]
        self.assertEqual(published, [])
        self.assertFalse(list(backups.glob("*.partial")))

    def test_main_vypise_uspech_a_pri_chybe_nevytvori_zip(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = main(project_root=self.root)
        self.assertEqual(code, 0)
        text = stdout.getvalue()
        self.assertIn(APP_VERSION, text)
        self.assertIn("SHA-256:", text)
        self.assertIn("Záloha zdrojového kódu byla úspěšně vytvořena.", text)

        for finished in (self.root / "source_backups").glob("Manazer_BOZP_source_*.zip"):
            finished.unlink()
        stderr = io.StringIO()
        with patch(
            "tools.backup_source.zipfile.ZipFile.testzip",
            return_value="poskozeny",
        ):
            with redirect_stderr(stderr):
                failed = main(project_root=self.root)
        self.assertEqual(failed, 1)
        self.assertIn("nezdařila", stderr.getvalue())
        self.assertFalse(
            list((self.root / "source_backups").glob("Manazer_BOZP_source_*.zip"))
        )

    def test_vynecha_archiv_a_cizi_qm_a_ponecha_zdroj(self) -> None:
        before = (self.root / "main.py").read_text(encoding="utf-8")
        names = self._names()
        self.assertNotIn("M-BOZP-4.0.7.zip", names)
        self.assertNotIn("manager-bozp-backup-stary.zip", names)
        self.assertNotIn("jinde/dialog.qm", names)
        self.assertNotIn("ManagerBOZP.AppImage", names)
        self.assertEqual((self.root / "main.py").read_text(encoding="utf-8"), before)
        self.assertTrue((self.root / ".env").is_file())
        self.assertTrue((self.root / "data/databaze/manager_bozp.db").is_file())


if __name__ == "__main__":
    unittest.main()
