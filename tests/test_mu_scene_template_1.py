"""MU-SCENE-TEMPLATE-1: tisk prázdné šablony Ohledání místa."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

from sqlalchemy import select

_TMP = Path(tempfile.mkdtemp(prefix="mu-scene-template-1-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QMessageBox

    from core.database.session import get_session
    from core.models.attachment import Attachment
    from core.services.attachment_service import attachment_service
    from core.shared.constants import ENTITY_MU_INVESTIGATION
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.vysetrovani_mu.constants import (
        EVENT_CHARACTER_URAZ,
        OHLEDANI_MISTA_PRINT_BUTTON,
        OHLEDANI_MISTA_PRINT_DIALOG_TITLE,
        OHLEDANI_MISTA_PRINT_REQUIRES_SAVED,
        SOURCE_TYPE_ACCIDENT,
    )
    from moduly.vysetrovani_mu.sluzby.mu_investigation_service import (
        mu_investigation_service,
    )
    from moduly.vysetrovani_mu.sluzby.mu_ohledani_mista_template_service import (
        mu_ohledani_mista_template_service,
    )
    from moduly.vysetrovani_mu.ui.mu_investigation_dialog import MuInvestigationDialog
    from moduly.vysetrovani_mu.ui.mu_ohledani_mista_widget import MuOhledaniMistaWidget


_FILLED_MARKER = "TAJNY_POPIS_XYZ_998877"

_FORM_LABELS = (
    "Záznam provedl",
    "Provoz",
    "Ohledání místa provedli",
    "Čas ohledání - zahájení",
    "Čas ohledání - ukončení",
    "Podrobný popis místa",
    "Poznámka k pořízené fotodokumentaci",
)


def _odt_content(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("content.xml").decode("utf-8")


def _odt_styles(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("styles.xml").decode("utf-8")


def _assert_valid_odt_package(path: Path) -> None:
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        assert infos, "prázdný ODT archiv"
        first = infos[0]
        assert first.filename == "mimetype"
        assert first.compress_type == zipfile.ZIP_STORED
        assert archive.read("mimetype") == b"application/vnd.oasis.opendocument.text"

        required = {
            "mimetype",
            "content.xml",
            "styles.xml",
            "META-INF/manifest.xml",
        }
        names = set(archive.namelist())
        missing = required - names
        assert not missing, f"chybí soubory: {sorted(missing)}"

        for name in ("content.xml", "styles.xml", "meta.xml", "settings.xml", "META-INF/manifest.xml"):
            if name in names:
                ET.fromstring(archive.read(name))


def _plain_xml_text(xml: str) -> str:
    return ET.fromstring(xml).itertext()


class MuSceneTemplate1TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def _create_accident(self):
        event_date = date(2026, 9, 8)
        return accident_service.create_accident(
            jmeno_prijmeni="Jan Zkušební",
            accident_date=event_date,
            accident_time="07:15",
            year=event_date.year,
            misto_urazu="Kolejiště u haly B",
            workplace_name="Provoz Východ",
        )

    def _create_investigation(self, **kwargs):
        accident = kwargs.pop("accident", None)
        data = {
            "title": "Pád materiálu",
            "event_character": EVENT_CHARACTER_URAZ,
            "started_at": date(2026, 9, 9),
        }
        if accident is not None:
            data.update(
                {
                    "source_type": SOURCE_TYPE_ACCIDENT,
                    "source_id": accident.id,
                    "source_label": accident.number,
                    "started_at": accident.accident_date,
                }
            )
        data.update(kwargs)
        return mu_investigation_service.create_investigation(**data)

    def test_print_button_on_ohledani_tab(self) -> None:
        dialog = MuInvestigationDialog()
        labels = [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())]
        self.assertIn("Ohledání místa", labels)
        widget = dialog.ohledani_mista_widget
        self.assertEqual(widget.print_template_btn.text(), OHLEDANI_MISTA_PRINT_BUTTON)
        self.assertEqual(widget.print_template_btn.text(), "Vytisknout šablonu")
        self.assertFalse(widget.print_template_btn.isEnabled())
        dialog.close()

        investigation = self._create_investigation()
        saved = MuInvestigationDialog(investigation=investigation)
        self.assertTrue(saved.ohledani_mista_widget.print_template_btn.isEnabled())
        saved.close()

    def test_widget_button_requires_saved_investigation(self) -> None:
        widget = MuOhledaniMistaWidget()
        self.assertEqual(widget.print_template_btn.text(), "Vytisknout šablonu")
        self.assertFalse(widget.print_template_btn.isEnabled())
        with patch.object(QMessageBox, "information") as info:
            widget._print_template()
        info.assert_called_once()
        self.assertEqual(info.call_args[0][1], OHLEDANI_MISTA_PRINT_DIALOG_TITLE)
        self.assertEqual(info.call_args[0][2], OHLEDANI_MISTA_PRINT_REQUIRES_SAVED)

        widget.set_context(7, event_number="MU-1/2026")
        self.assertTrue(widget.print_template_btn.isEnabled())

    def test_template_is_valid_a4_odt(self) -> None:
        template = mu_ohledani_mista_template_service.template_path()
        self.assertTrue(template.exists())
        _assert_valid_odt_package(template)
        content = _odt_content(template)
        styles = _odt_styles(template)
        self.assertIn("Šablona ohledání místa", content)
        self.assertIn("${cislo_mu}", content)
        self.assertIn("${datum_udalosti}", content)
        self.assertIn("${misto}", content)
        self.assertIn("${formular_text}", content)
        self.assertIn('fo:page-width="21.001cm"', styles)
        self.assertIn('fo:page-height="29.7cm"', styles)
        self.assertIn('style:print-orientation="portrait"', styles)

    def test_generate_prefills_identification_and_keeps_form_blank(self) -> None:
        accident = self._create_accident()
        investigation = self._create_investigation(
            accident=accident,
            ohledani_mista_json=json.dumps(
                {
                    "ohledani_zapsal": "Vyplněný zapisovatel",
                    "ohledani_provoz": "Vyplněný provoz",
                    "ohledani_provedli": "Vyplněný tým",
                    "ohledani_zahajeni": "10:00",
                    "ohledani_ukonceni": "11:30",
                    "ohledani_popis_mista": _FILLED_MARKER,
                    "ohledani_priloha": "protokol.pdf",
                },
                ensure_ascii=False,
            ),
        )

        path = mu_ohledani_mista_template_service.generate_for_investigation(investigation)
        self.assertTrue(path.exists())
        _assert_valid_odt_package(path)
        xml = _odt_content(path)
        text = "".join(_plain_xml_text(xml))
        styles = _odt_styles(path)

        self.assertIn(investigation.number, text)
        self.assertIn("Pád materiálu", text)
        self.assertIn(EVENT_CHARACTER_URAZ, text)
        self.assertIn("08.09.2026", text)
        self.assertIn("07:15", text)
        self.assertIn("Kolejiště u haly B", text)

        for label in _FORM_LABELS:
            self.assertIn(label, text)

        self.assertNotIn(_FILLED_MARKER, text)
        self.assertNotIn("Vyplněný zapisovatel", text)
        self.assertNotIn("Vyplněný provoz", text)
        self.assertNotIn("protokol.pdf", text)
        self.assertIn("____________________", text)
        self.assertNotIn("Přiložit podepsaný protokol", text)

        self.assertIn('fo:page-width="21.001cm"', styles)
        self.assertIn('style:print-orientation="portrait"', styles)

    def test_generate_does_not_write_investigation_or_attachments(self) -> None:
        investigation = self._create_investigation(
            ohledani_mista_json='{"ohledani_popis_mista": "původní popis"}',
        )
        before = mu_investigation_service.get_by_id(investigation.id)
        self.assertIsNotNone(before)
        assert before is not None
        before_json = before.ohledani_mista_json
        before_updated = before.updated_at
        before_attachments = attachment_service.get_for_entity(
            ENTITY_MU_INVESTIGATION,
            investigation.id,
        )

        path = mu_ohledani_mista_template_service.generate_for_investigation(before)
        self.assertTrue(path.exists())

        after = mu_investigation_service.get_by_id(investigation.id)
        self.assertIsNotNone(after)
        assert after is not None
        self.assertEqual(after.ohledani_mista_json, before_json)
        self.assertEqual(after.updated_at, before_updated)
        after_attachments = attachment_service.get_for_entity(
            ENTITY_MU_INVESTIGATION,
            investigation.id,
        )
        self.assertEqual(len(after_attachments), len(before_attachments))
        with get_session() as session:
            stored = session.execute(
                select(Attachment).where(
                    Attachment.entity_type == ENTITY_MU_INVESTIGATION,
                    Attachment.entity_id == investigation.id,
                )
            ).scalars().all()
        self.assertEqual(stored, [])

    def test_open_uses_export_workflow(self) -> None:
        investigation = self._create_investigation()
        with patch(
            "moduly.vysetrovani_mu.sluzby.mu_ohledani_mista_template_service.open_export_file"
        ) as open_export:
            path = mu_ohledani_mista_template_service.open_for_investigation(investigation)
        open_export.assert_called_once()
        self.assertEqual(
            open_export.call_args.kwargs["title"],
            OHLEDANI_MISTA_PRINT_DIALOG_TITLE,
        )
        self.assertTrue(path.exists())

        widget = MuOhledaniMistaWidget()
        widget.set_context(investigation.id, event_number=investigation.number)
        with patch.object(
            mu_ohledani_mista_template_service,
            "open_for_investigation_id",
            return_value=path,
        ) as opened:
            widget._print_template()
        opened.assert_called_once_with(investigation.id)


if __name__ == "__main__":
    unittest.main()
