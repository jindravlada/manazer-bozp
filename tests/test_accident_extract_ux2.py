"""ACCIDENT-EXTRACT-UX2 – aktuální šablona Výpisu a skrytí prázdných kontrol."""

from __future__ import annotations

import html
import importlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="accident-extract-ux2-"))
_REPO = Path(__file__).resolve().parents[1]
_TEMPLATE_REL = "moduly/kniha_urazu/templates/exporty/VypisPracovniUraz.odt"

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.kniha_urazu.modely.accident import Accident
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    import moduly.kniha_urazu.sluzby.vypis_urazu_service as vypis_module

    importlib.reload(vypis_module)
    vypis_urazu_service = vypis_module.vypis_urazu_service
    vypis_storage = vypis_module.storage_service
    from moduly.kniha_urazu.sluzby.zaverecna_zprava_service import zaverecna_zprava_service

KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
MEASURES = "Zajistit zábradlí na galerii."
NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
}


def _git_bytes(rev_path: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(_REPO), "show", rev_path])


_OLD_DEFAULT = _git_bytes(f"6005ad4:{_TEMPLATE_REL}")
_UX1_DEFAULT = _git_bytes(f"265f190:{_TEMPLATE_REL}")


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as zin:
        return zin.read("content.xml").decode("utf-8")


def _odt_plain_text(content: str) -> str:
    text = re.sub(r"<text:line-break\s*/>", "\n", content)
    text = re.sub(
        r'<text:s\s+text:c="(\d+)"/>',
        lambda match: " " * int(match.group(1)),
        text,
    )
    text = re.sub(r"<text:s\s*/>", " ", text)
    text = re.sub(r"<text:tab\s*/>", "\t", text)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


def _paragraphs(content: str) -> list[ET.Element]:
    root = ET.fromstring(content)
    return list(root.findall(".//text:p", NS))


def _inner_text(node: ET.Element) -> str:
    chunks: list[str] = []
    if node.text:
        chunks.append(node.text)
    for child in list(node):
        if child.tag == "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}line-break":
            chunks.append("\n")
        else:
            chunks.append("".join(child.itertext()))
        if child.tail:
            chunks.append(child.tail)
    return "".join(chunks).strip()


def _user_template() -> Path:
    return vypis_storage.template_file("exporty", "VypisPracovniUraz.odt")


def _marker(path: Path) -> Path:
    return vypis_storage._template_bundle_hash_path(path)


def _bundled() -> Path:
    bundled = vypis_storage.bundled_template_file("exporty", "VypisPracovniUraz.odt")
    assert bundled is not None
    return bundled


class AccidentExtractUx2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.kniha_urazu.modely.investigation import AccidentInvestigation
        from moduly.ukoly.modely.task import Task

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(AccidentInvestigation))
            session.execute(delete(Accident))
            session.commit()

        user = _user_template()
        if user.exists():
            user.unlink()
        marker = _marker(user)
        if marker.exists():
            marker.unlink()
        backup_dir = vypis_storage.backups_dir / "sablony"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        vypis_urazu_service.last_template_resolution = None

    def _create(self, **kwargs):
        data = {
            "jmeno_prijmeni": "Jan Novák",
            "accident_date": date(2026, 3, 10),
            "druh_urazu": KIND_OVER_3,
            "opatreni": MEASURES,
            "zamestnavatel_nazev": "Elektrárna Tušimice",
            "zamestnavatel_ico": "12345678",
            "vrchni_dozor": "OIP",
            "zamestnavatel_adresa": "Tušimice 1",
            "uraz_pracoviste_zamestnavatele": "ANO",
        }
        data.update(kwargs)
        return accident_service.create_accident(**data)

    def _generate(self, accident, **kwargs) -> tuple[Path, str, str]:
        path = vypis_urazu_service.generate_for_accident(accident, **kwargs)
        content = _odt_content(path)
        return path, content, _odt_plain_text(content)

    def _control_block(self, text: str) -> str:
        after = text.split("Další údaje", 1)[1]
        return after.split("Předpisy, které byly", 1)[0]

    def test_exporter_reports_exact_used_template_path(self) -> None:
        accident = self._create()
        self._generate(accident)
        resolution = vypis_urazu_service.last_template_resolution
        self.assertIsNotNone(resolution)
        assert resolution is not None
        self.assertEqual(resolution.path.resolve(), _user_template().resolve())
        self.assertTrue(str(resolution.path).startswith(str(_TMP)))
        self.assertEqual(resolution.sha256, vypis_storage._file_sha256(_bundled()))
        self.assertEqual(resolution.path.read_bytes(), _bundled().read_bytes())

    def test_missing_workspace_template_copies_current_default(self) -> None:
        self.assertFalse(_user_template().exists())
        resolution = vypis_urazu_service.prepare_template()
        self.assertTrue(resolution.path.exists())
        self.assertEqual(resolution.path.read_bytes(), _bundled().read_bytes())
        self.assertIn(resolution.action, {"copied_default", "already_current"})

    def test_known_old_unmodified_default_is_backed_up_and_updated(self) -> None:
        user = _user_template()
        user.write_bytes(_OLD_DEFAULT)
        resolution = vypis_urazu_service.prepare_template()
        self.assertEqual(resolution.action, "updated_known_default")
        self.assertIsNotNone(resolution.backup_path)
        assert resolution.backup_path is not None
        self.assertTrue(resolution.backup_path.exists())
        self.assertEqual(resolution.backup_path.read_bytes(), _OLD_DEFAULT)
        self.assertEqual(user.read_bytes(), _bundled().read_bytes())
        self.assertEqual(
            _marker(user).read_text(encoding="utf-8").strip(),
            vypis_storage._file_sha256(_bundled()),
        )

    def test_ux1_default_is_treated_as_known_old_and_updated(self) -> None:
        user = _user_template()
        user.write_bytes(_UX1_DEFAULT)
        vypis_storage._write_template_bundle_hash(
            user,
            vypis_storage._file_sha256(user),
        )
        resolution = vypis_urazu_service.prepare_template()
        self.assertEqual(resolution.action, "updated_known_default")
        self.assertEqual(user.read_bytes(), _bundled().read_bytes())
        self.assertIsNotNone(resolution.backup_path)

    def test_current_copy_is_noop_and_repeated_export_is_idempotent(self) -> None:
        first = vypis_urazu_service.prepare_template()
        self.assertEqual(first.path.read_bytes(), _bundled().read_bytes())
        backups_before = list((vypis_storage.backups_dir / "sablony").glob("*.odt"))
        user_mtime = first.path.stat().st_mtime_ns
        second = vypis_urazu_service.prepare_template()
        third = vypis_urazu_service.prepare_template()
        self.assertEqual(second.action, "already_current")
        self.assertEqual(third.action, "already_current")
        self.assertEqual(second.path.read_bytes(), first.path.read_bytes())
        backups_after = list((vypis_storage.backups_dir / "sablony").glob("*.odt"))
        self.assertEqual(len(backups_after), len(backups_before))
        self.assertEqual(third.path.stat().st_mtime_ns, user_mtime)

    def test_custom_template_is_kept_without_confirmation(self) -> None:
        user = _user_template()
        custom = b"custom-logo-vypis-template"
        user.write_bytes(custom)
        resolution = vypis_urazu_service.prepare_template()
        self.assertEqual(resolution.action, "kept_custom")
        self.assertTrue(resolution.custom)
        self.assertEqual(user.read_bytes(), custom)
        self.assertIsNone(resolution.backup_path)

    def test_confirmed_custom_replace_creates_backup_and_uses_default(self) -> None:
        user = _user_template()
        custom = b"custom-logo-vypis-template"
        user.write_bytes(custom)
        resolution = vypis_urazu_service.prepare_template(confirm_replace_custom=True)
        self.assertEqual(resolution.action, "replaced_custom")
        self.assertEqual(user.read_bytes(), _bundled().read_bytes())
        self.assertIsNotNone(resolution.backup_path)
        assert resolution.backup_path is not None
        self.assertEqual(resolution.backup_path.read_bytes(), custom)

    def test_source_and_appimage_paths_use_same_old_default_rule(self) -> None:
        user = _user_template()
        user.write_bytes(_OLD_DEFAULT)
        source_resolution = vypis_urazu_service.prepare_template()
        self.assertEqual(source_resolution.action, "updated_known_default")
        self.assertEqual(user.read_bytes(), _bundled().read_bytes())

        user.write_bytes(_OLD_DEFAULT)
        fake_root = _TMP / "meipass"
        dest = fake_root / "moduly" / "kniha_urazu" / "templates" / "exporty"
        dest.mkdir(parents=True)
        shutil.copy2(_bundled(), dest / "VypisPracovniUraz.odt")
        with patch.object(sys, "frozen", True, create=True):
            with patch.object(sys, "_MEIPASS", str(fake_root), create=True):
                appimage_resolution = vypis_urazu_service.prepare_template()
        self.assertEqual(appimage_resolution.action, "updated_known_default")
        self.assertEqual(appimage_resolution.bundled_path, dest / "VypisPracovniUraz.odt")
        self.assertEqual(user.read_bytes(), (dest / "VypisPracovniUraz.odt").read_bytes())

    def test_other_templates_remain_unchanged(self) -> None:
        other = vypis_storage.template_file("setreni", "ZaverecnaZprava.odt")
        self.assertTrue(other.exists())
        original = other.read_bytes()
        user = _user_template()
        user.write_bytes(_OLD_DEFAULT)
        vypis_urazu_service.prepare_template()
        self.assertEqual(other.read_bytes(), original)

    def test_alcohol_no_with_reason_shows_only_filled_rows(self) -> None:
        accident = self._create(
            kontrola_alkohol="NE",
            kontrola_alkohol_duvod_neprovedeni="Pozdní nahlášení.",
            vysledek_kontroly_alkohol="",
            mnozstvi_alkohol="",
            kontrola_navykove_latky="NE",
            vysledek_kontroly_navykove_latky="",
            navykove_latky_popis="",
            kontrola_navykove_latky_duvod_neprovedeni="",
        )
        _path, content, text = self._generate(accident)
        block = self._control_block(text)
        self.assertIn("Kontrola přítomnosti alkoholu: NE", block)
        self.assertIn("Důvod neprovedení kontroly alkoholu: Pozdní nahlášení.", block)
        self.assertIn("Kontrola návykových látek: NE", block)
        self.assertNotIn("Výsledek kontroly:", block)
        self.assertNotIn("Množství alkoholu:", block)
        self.assertNotIn("Zjištěné látky:", block)
        self.assertNotIn("Důvod neprovedení kontroly návykových látek:", block)
        self.assertNotIn("&#x20;", content)
        self.assertNotIn("&#x20;", text)
        self.assertNotIn("<table:table", content)

    def test_alcohol_yes_with_result_and_amount(self) -> None:
        accident = self._create(
            kontrola_alkohol="ANO",
            vysledek_kontroly_alkohol="Pozitivní",
            mnozstvi_alkohol="0,24",
            kontrola_alkohol_duvod_neprovedeni="",
            kontrola_navykove_latky="",
        )
        _path, _content, text = self._generate(accident)
        block = self._control_block(text)
        self.assertIn("Kontrola přítomnosti alkoholu: ANO", block)
        self.assertIn("Výsledek kontroly: Pozitivní", block)
        self.assertIn("Množství alkoholu: 0,24 ‰", block)
        self.assertNotIn("Důvod neprovedení kontroly alkoholu:", block)
        self.assertNotIn("Kontrola návykových látek:", block)

    def test_drugs_no_without_reason_shows_only_flag(self) -> None:
        accident = self._create(
            kontrola_alkohol="",
            kontrola_navykove_latky="NE",
            kontrola_navykove_latky_duvod_neprovedeni="",
        )
        _path, _content, text = self._generate(accident)
        block = self._control_block(text)
        self.assertEqual(
            [line for line in block.splitlines() if line.strip() and line.strip() != "Kontrola"],
            ["Kontrola návykových látek: NE"],
        )

    def test_drugs_yes_with_result_and_substances(self) -> None:
        accident = self._create(
            kontrola_navykove_latky="ANO",
            vysledek_kontroly_navykove_latky="Pozitivní",
            navykove_latky_popis="THC",
            kontrola_alkohol="",
        )
        _path, _content, text = self._generate(accident)
        block = self._control_block(text)
        self.assertIn("Kontrola návykových látek: ANO", block)
        self.assertIn("Výsledek kontroly: Pozitivní", block)
        self.assertIn("Zjištěné látky: THC", block)
        self.assertNotIn("Důvod neprovedení kontroly návykových látek:", block)

    def test_whitespace_is_treated_as_empty(self) -> None:
        accident = self._create(
            kontrola_alkohol="NE",
            vysledek_kontroly_alkohol="   ",
            mnozstvi_alkohol="\n",
            kontrola_alkohol_duvod_neprovedeni="  \t  ",
            kontrola_navykove_latky="  ",
        )
        _path, _content, text = self._generate(accident)
        block = self._control_block(text)
        self.assertIn("Kontrola přítomnosti alkoholu: NE", block)
        self.assertNotIn("Výsledek kontroly:", block)
        self.assertNotIn("Množství alkoholu:", block)
        self.assertNotIn("Důvod neprovedení kontroly alkoholu:", block)
        self.assertNotIn("Kontrola návykových látek:", block)

    def test_xml_space_entity_is_never_shown(self) -> None:
        accident = self._create(
            kontrola_alkohol="NE",
            vysledek_kontroly_alkohol="&#x20;",
            mnozstvi_alkohol="&amp;#x20;",
            kontrola_navykove_latky="NE",
            navykove_latky_popis="&#32;",
        )
        _path, content, text = self._generate(accident)
        self.assertNotIn("&#x20;", content)
        self.assertNotIn("&#x20;", text)
        self.assertNotIn("&#32;", text)
        block = self._control_block(text)
        self.assertNotIn("Výsledek kontroly:", block)
        self.assertNotIn("Množství alkoholu:", block)
        self.assertNotIn("Zjištěné látky:", block)
        self.assertNotIn("20 ‰", block)

    def test_zero_alcohol_amount_is_kept(self) -> None:
        accident = self._create(
            kontrola_alkohol="ANO",
            vysledek_kontroly_alkohol="Negativní",
            mnozstvi_alkohol="0",
        )
        _path, _content, text = self._generate(accident)
        self.assertIn("Množství alkoholu: 0 ‰", self._control_block(text))

        accident.mnozstvi_alkohol = 0  # type: ignore[assignment]
        _path, _content, text = self._generate(accident)
        self.assertIn("Množství alkoholu: 0 ‰", self._control_block(text))

    def test_empty_controls_hide_whole_subsection(self) -> None:
        accident = self._create(
            kontrola_alkohol="",
            vysledek_kontroly_alkohol="&#x20;",
            mnozstvi_alkohol=" ",
            kontrola_navykove_latky="",
        )
        accident.kontrola_navykove_latky = None  # type: ignore[assignment]
        _path, content, text = self._generate(accident)
        block = self._control_block(text)
        self.assertNotIn("Kontrola přítomnosti alkoholu", block)
        self.assertNotIn("Kontrola návykových látek", block)
        paragraphs = [_inner_text(node) for node in _paragraphs(content)]
        self.assertNotIn("Kontrola", paragraphs)
        self.assertNotIn("${kontrola_sekce}", content)
        self.assertNotIn("<table:table", content)
        dalsi = paragraphs.index("Další údaje")
        self.assertNotEqual(paragraphs[dalsi + 1], "")

    def test_ux1_layout_and_other_accident_export_remain(self) -> None:
        accident = self._create(
            kontrola_alkohol="NE",
            kontrola_alkohol_duvod_neprovedeni="Pozdní nahlášení.",
            kontrola_navykove_latky="NE",
            hlavni_cinnost_zamestnavatele="Výroba elektřiny",
        )
        _path, content, text = self._generate(accident)
        self.assertIn(f"o pracovním úrazu č. {accident.number}", text)
        self.assertNotIn("Vytvořeno aplikací Manažer BOZP", text)
        self.assertNotIn("Hlavní činnost zaměstnavatele", text)
        self.assertNotIn("Šetření úrazu", text)
        self.assertIn("Úraz na pracovišti zaměstnavatele", text)
        self.assertIn(MEASURES, text)
        self.assertNotIn("Termín ohlášení pracovního úrazu", text)
        styles = {
            node.get("{urn:oasis:names:tc:opendocument:xmlns:style:1.0}name"): node
            for node in ET.fromstring(content).findall(".//style:style", NS)
        }
        align = styles["TitleCentered"].find("style:paragraph-properties", NS)
        self.assertEqual(
            align.get("{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}text-align"),
            "center",
        )
        zaverecna = zaverecna_zprava_service.generate_for_accident(accident)
        zaverecna_text = _odt_plain_text(_odt_content(zaverecna))
        self.assertIn("Termín ohlášení pracovního úrazu", zaverecna_text)
