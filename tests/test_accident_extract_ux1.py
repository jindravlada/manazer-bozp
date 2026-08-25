"""ACCIDENT-EXTRACT-UX1 – zjednodušení Výpisu o pracovním úrazu."""

from __future__ import annotations

import html
import importlib
import os
import re
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="accident-extract-ux1-"))

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
    from moduly.kniha_urazu.sluzby.vypis_urazu_service import (
        _ADDITIONAL_EMPLOYER_HEADING,
        vypis_urazu_service,
    )
    from moduly.kniha_urazu.sluzby.zaverecna_zprava_service import zaverecna_zprava_service
    from moduly.ukoly.sluzby.task_service import task_service


KIND_OVER_3 = "pracovní úraz s pracovní neschopností delší než 3 kalendářní dny"
MEASURES = "Zajistit zábradlí na galerii.\nProškolit obsluhu jeřábu."
LONG_MEASURES = (
    "1. Obnovit zábradlí na celé délce galerie a ověřit únosnost kotev.\n"
    "2. Doplnit pracovní postup o zákaz vstupu bez zachycovače pádu.\n"
    "3. " + ("Dlouhé souvětí o organizaci práce a kontrole OOPP. " * 12).strip()
)
NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "fo": "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
}


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


def _style_map(content: str) -> dict[str, ET.Element]:
    root = ET.fromstring(content)
    return {
        node.get("{urn:oasis:names:tc:opendocument:xmlns:style:1.0}name"): node
        for node in root.findall(".//style:style", NS)
    }


class AccidentExtractUx1TestCase(unittest.TestCase):
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
            "hlavni_cinnost_zamestnavatele": "Výroba elektřiny",
            "uraz_pracoviste_zamestnavatele": "ANO",
            "subjekt_registrovan": "ANO",
            "adresa_sidla_subjektu": "Praha 1",
            "ico_subjektu": "11111111",
        }
        data.update(kwargs)
        return accident_service.create_accident(**data)

    def _generate(self, accident) -> tuple[Path, str, str]:
        path = vypis_urazu_service.generate_for_accident(accident)
        content = _odt_content(path)
        return path, content, _odt_plain_text(content)

    def test_title_is_centered_with_number_and_blank_line(self) -> None:
        accident = self._create()
        _path, content, text = self._generate(accident)
        styles = _style_map(content)
        title = styles["TitleCentered"]
        para_props = title.find("style:paragraph-properties", NS)
        self.assertIsNotNone(para_props)
        self.assertEqual(
            para_props.get("{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}text-align"),
            "center",
        )

        paragraphs = _paragraphs(content)
        self.assertEqual(_inner_text(paragraphs[0]), "Výpis")
        self.assertEqual(paragraphs[0].get("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name"), "TitleCentered")
        self.assertEqual(
            _inner_text(paragraphs[1]),
            f"o pracovním úrazu č. {accident.number}",
        )
        self.assertEqual(paragraphs[1].get("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name"), "TitleCentered")
        self.assertRegex(accident.number or "", r"^\d+/\d{4}$")
        self.assertEqual(_inner_text(paragraphs[2]), "")
        self.assertEqual(paragraphs[2].get("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name"), "Standard")
        self.assertNotIn("Vytvořeno aplikací Manažer BOZP", text)
        self.assertIn(f"o pracovním úrazu č. {accident.number}", text)

    def test_employer_main_activity_is_removed(self) -> None:
        accident = self._create()
        _path, _content, text = self._generate(accident)
        self.assertNotIn("Hlavní činnost zaměstnavatele", text)
        self.assertNotIn("Výroba elektřiny", text)
        self.assertIn("Elektrárna Tušimice", text)
        self.assertIn("12345678", text)

    def test_missing_additional_employer_leaves_no_heading_or_blank_block(self) -> None:
        accident = self._create(
            dalsi_zamestnavatel_nazev="  ",
            dalsi_zamestnavatel_ico="",
            dalsi_zamestnavatel_adresa="\n",
            dalsi_zamestnavatel_cinnost="   ",
        )
        self.assertFalse(vypis_urazu_service.additional_employer_is_present(accident))
        _path, content, text = self._generate(accident)
        self.assertNotIn(_ADDITIONAL_EMPLOYER_HEADING, text)
        self.assertNotIn("${dalsi_zamestnavatel_sekce}", content)
        paragraphs = [_inner_text(node) for node in _paragraphs(content)]
        employer_idx = paragraphs.index("Zaměstnavatel")
        employee_idx = paragraphs.index("Zaměstnanec")
        between = paragraphs[employer_idx + 1 : employee_idx]
        self.assertTrue(between)
        self.assertFalse(any(item == "" for item in between))

    def test_partial_additional_employer_shows_only_filled_fields(self) -> None:
        accident = self._create(
            dalsi_zamestnavatel_nazev="Dodavatel Alfa",
            dalsi_zamestnavatel_ico="",
            dalsi_zamestnavatel_adresa="Mostecká 12",
            dalsi_zamestnavatel_cinnost="  ",
        )
        self.assertTrue(vypis_urazu_service.additional_employer_is_present(accident))
        _path, _content, text = self._generate(accident)
        self.assertIn(_ADDITIONAL_EMPLOYER_HEADING, text)
        self.assertIn("Název: Dodavatel Alfa", text)
        self.assertIn("Adresa: Mostecká 12", text)
        self.assertNotIn("IČO:", text.split(_ADDITIONAL_EMPLOYER_HEADING, 1)[1].split("Zaměstnanec", 1)[0])
        self.assertNotIn(
            "Hlavní/ekonomická činnost:",
            text.split(_ADDITIONAL_EMPLOYER_HEADING, 1)[1].split("Zaměstnanec", 1)[0],
        )

    def test_workplace_section_ends_at_employer_workplace_flag(self) -> None:
        accident = self._create()
        _path, content, text = self._generate(accident)
        workplace = text.split("Pracoviště / zdroj / příčina", 1)[1].split("Další údaje", 1)[0]
        self.assertIn("Úraz na pracovišti zaměstnavatele", workplace)
        self.assertTrue(workplace.strip().endswith("ANO"))
        self.assertNotIn("Subjekt je registrován", text)
        self.assertNotIn("Adresa sídla: Praha 1", text)
        self.assertNotIn("Ekonomická činnost subjektu", text)
        self.assertNotIn("Okres pracoviště", text)
        self.assertNotIn("${adresa_sidla_subjektu}", content)

    def test_investigation_section_is_removed(self) -> None:
        accident = self._create()
        _path, _content, text = self._generate(accident)
        self.assertNotIn("Šetření úrazu", text)
        self.assertNotIn("Stav šetření", text)
        self.assertNotIn("Stanovisko specialisty BOZP", text)

    def test_measures_use_accident_field_not_reporting_deadlines(self) -> None:
        accident = self._create(opatreni=MEASURES)
        tasks = task_service.get_all_tasks()
        self.assertTrue(any("Termín ohlášení" in (task.title or "") for task in tasks))
        self.assertTrue(any("Termín odeslání Záznamu" in (task.title or "") for task in tasks))

        _path, _content, text = self._generate(accident)
        self.assertIn("Zajistit zábradlí na galerii.", text)
        self.assertIn("Proškolit obsluhu jeřábu.", text)
        self.assertNotIn("Termín ohlášení pracovního úrazu", text)
        self.assertNotIn("Termín odeslání Záznamu o pracovním úrazu", text)
        self.assertNotIn("{", text.split("Popis přijatých opatření", 1)[1].split("Svědci", 1)[0])

        zaverecna = zaverecna_zprava_service.generate_for_accident(accident)
        zaverecna_text = _odt_plain_text(_odt_content(zaverecna))
        self.assertIn("Termín ohlášení pracovního úrazu", zaverecna_text)

    def test_multiline_measures_keep_line_breaks(self) -> None:
        accident = self._create(opatreni=LONG_MEASURES)
        _path, content, text = self._generate(accident)
        self.assertIn("Obnovit zábradlí", text)
        self.assertIn("Doplnit pracovní postup", text)
        self.assertIn("Dlouhé souvětí o organizaci práce", text)
        self.assertIn("<text:line-break/>", content)
        block = text.split("Popis přijatých opatření k zabránění opakování úrazu:", 1)[1]
        self.assertIn("1. Obnovit zábradlí", block)
        self.assertIn("2. Doplnit pracovní postup", block)

    def test_missing_measures_on_legacy_record_do_not_crash(self) -> None:
        accident = self._create(opatreni="")
        accident.opatreni = None  # type: ignore[assignment]
        accident.measures_summary = None  # type: ignore[assignment]
        path, content, text = self._generate(accident)
        self.assertTrue(path.exists())
        self.assertIn("Popis přijatých opatření k zabránění opakování úrazu:", text)
        self.assertNotIn("Nejsou evidována.", text)
        self.assertNotIn("${opatreni}", content)

    def test_document_has_no_empty_tables_or_empty_page_markers(self) -> None:
        ordinary = self._create()
        partial = self._create(
            jmeno_prijmeni="Petr Částečný",
            dalsi_zamestnavatel_nazev="Beta s.r.o.",
            dalsi_zamestnavatel_ico="",
            dalsi_zamestnavatel_adresa="Chomutov",
        )
        long_one = self._create(jmeno_prijmeni="Eva Dlouhá", opatreni=LONG_MEASURES)

        for accident in (ordinary, partial, long_one):
            _path, content, text = self._generate(accident)
            self.assertNotIn("<table:table", content)
            self.assertNotIn("Šetření úrazu", text)
            paragraphs = _paragraphs(content)
            empty_run = 0
            max_empty = 0
            for node in paragraphs:
                if _inner_text(node) == "":
                    empty_run += 1
                    max_empty = max(max_empty, empty_run)
                else:
                    empty_run = 0
            self.assertLessEqual(max_empty, 1)
            headings = [
                node
                for node in paragraphs
                if (node.get("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name") or "").startswith("Heading")
            ]
            self.assertTrue(headings)
            heading_style = _style_map(content)["Heading_20_2"]
            keep = heading_style.find("style:paragraph-properties", NS)
            self.assertEqual(
                keep.get("{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}keep-with-next"),
                "always",
            )


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
