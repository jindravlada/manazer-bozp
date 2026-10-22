"""Veřejná licence a dokumentace pro publikaci zdrojových kódů."""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

from core.version import APP_VERSION

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_GPL3_SHA256 = (
    "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986"
)
_MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_RELEASE_PREFIX = "https://github.com/jindravlada/manazer-bozp/releases"
# Linuxové stažení sleduje APP_VERSION. Tuto konstantu měň jen při novém Windows instalátoru.
LAST_PUBLISHED_WINDOWS_VERSION = "4.1.3"


def _release_asset_url(version: str, filename: str) -> str:
    return f"{_RELEASE_PREFIX}/download/v{version}/{filename}"


def _between(text: str, start: str, end: str) -> str:
    start_at = text.index(start)
    end_at = text.index(end, start_at + len(start))
    return text[start_at:end_at]


class PublicLicenseDocsTestCase(unittest.TestCase):
    def test_license_txt_is_the_full_official_gpl3(self) -> None:
        path = PROJECT_ROOT / "LICENSE.txt"
        data = path.read_bytes()
        text = data.decode("utf-8")
        digest = hashlib.sha256(data).hexdigest()

        self.assertEqual(digest, OFFICIAL_GPL3_SHA256)
        self.assertIn("GNU GENERAL PUBLIC LICENSE", text)
        self.assertIn("Version 3, 29 June 2007", text)
        self.assertIn("END OF TERMS AND CONDITIONS", text)
        self.assertIn("How to Apply These Terms to Your New Programs", text)
        self.assertNotIn("Vladimír Jindra", text)

    def test_installer_references_existing_license(self) -> None:
        installer = (PROJECT_ROOT / "installer.iss").read_text(encoding="utf-8")
        generator = (PROJECT_ROOT / "generate_installer_iss.py").read_text(encoding="utf-8")
        self.assertIn("LicenseFile=LICENSE.txt", installer)
        self.assertIn("LicenseFile=LICENSE.txt", generator)
        self.assertTrue((PROJECT_ROOT / "LICENSE.txt").is_file())
        repo_url = "https://github.com/jindravlada/manazer-bozp"
        for field in ("AppPublisherURL", "AppSupportURL", "AppUpdatesURL"):
            self.assertIn(f"{field}={repo_url}", installer)
            self.assertIn(f"{field}={repo_url}", generator)
        self.assertNotIn("https://github.com/\n", installer)
        self.assertNotIn("https://github.com/\n", generator)

    def test_readme_links_and_paths(self) -> None:
        readme_path = PROJECT_ROOT / "README.md"
        readme = readme_path.read_text(encoding="utf-8")
        self.assertTrue(readme.startswith(f"# Manažer BOZP {APP_VERSION}"))
        self.assertIn(f"Aktuální verze: {APP_VERSION}", readme)
        self.assertIn("GPL-3.0-or-later", readme)
        self.assertIn("Copyright © 2026 Ing. Vladimír Jindra", readme)
        self.assertNotIn("/home/", readme)
        self.assertNotIn("C:\\Users\\", readme)
        self.assertNotIn("DOKUMENTACE.md", readme)
        linux_url = _release_asset_url(
            APP_VERSION,
            f"Manazer-BOZP-{APP_VERSION}-x86_64.AppImage",
        )
        windows_filename = (
            "Manazer_BOZP_"
            f"{LAST_PUBLISHED_WINDOWS_VERSION.replace('.', '_')}_Setup.exe"
        )
        windows_url = _release_asset_url(
            LAST_PUBLISHED_WINDOWS_VERSION,
            windows_filename,
        )
        linux_section = _between(readme, "### Linux", "### Windows")
        windows_section = _between(readme, "### Windows", "## O aplikaci")
        self.assertIn(linux_url, linux_section)
        self.assertNotIn(windows_url, linux_section)
        self.assertIn(windows_url, windows_section)
        self.assertNotIn(linux_url, windows_section)
        self.assertNotIn("4.0.10", linux_section)
        self.assertNotIn("4.0.10", windows_section)
        if LAST_PUBLISHED_WINDOWS_VERSION != APP_VERSION:
            self.assertIn("Poslední dostupná verze", windows_section)
            self.assertIn(LAST_PUBLISHED_WINDOWS_VERSION, windows_section)
            self.assertIn(
                f"Instalátor verze {APP_VERSION} zatím není dostupný.",
                windows_section,
            )
        else:
            self.assertNotIn("zatím není dostupný", windows_section)

        for match in _MARKDOWN_LINK.finditer(readme):
            target = match.group(1).strip()
            if target.startswith(_RELEASE_PREFIX):
                continue
            self.assertFalse(target.startswith(("http://", "https://")), target)
            self.assertTrue((readme_path.parent / target).is_file(), target)

    def test_third_party_notices_stay_within_verified_metadata(self) -> None:
        notices = (PROJECT_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only", notices)
        self.assertIn("Apache-2.0", notices)
        self.assertIn("MIT-CMU", notices)
        self.assertIn("Python Software Foundation License Version 2", notices)
        self.assertIn("Bootloader Exception", notices)
        self.assertIn("https://www.qt.io/licensing", notices)
        self.assertNotIn("/home/", notices)
        self.assertNotIn("C:\\Users\\", notices)
