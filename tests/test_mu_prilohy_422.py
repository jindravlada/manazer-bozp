"""Centrální přehled příloh vyšetřování MU (4.2.2)."""

from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QPushButton
from sqlalchemy import text

_TMP = Path(tempfile.mkdtemp(prefix="mu-prilohy-422-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database
    from core.database.session import get_session

    initialize_database()

    from core.services.attachment_service import attachment_service
    from core.shared.constants import ENTITY_MU_INVESTIGATION
    from moduly.vysetrovani_mu.sluzby.mu_investigation_service import mu_investigation_service
    from moduly.vysetrovani_mu.sluzby.mu_prilohy_prehled import (
        SECTION_CASOVA_OSA,
        SECTION_DODRZOVANI,
        SECTION_OHLEDANI,
        SECTION_SHARED,
        SECTION_SVEDCI,
        SECTION_ZAJISTENI,
        classify_mu_attachment,
        linked_attachment_names,
    )
    from moduly.vysetrovani_mu.ui.mu_investigation_dialog import MuInvestigationDialog
    from moduly.vysetrovani_mu.ui.mu_prilohy_widget import MuPrilohyWidget


class MuPrilohyClassification422TestCase(unittest.TestCase):
    def test_prefix_and_json_agree_or_stand_alone(self) -> None:
        zajisteni, casova, ohledani = linked_attachment_names(
            zajisteni_dukazu_json=json.dumps(
                {"fotky": {"CelkovyPohled": "Foto-CelkovyPohled-1.jpg", "DetailMista": "Foto-CelkovyPohled-1.jpg"}}
            ),
            casova_osa_json=json.dumps(
                {"cas_synchronizace": {"caszarizeni_rows": [{"foto": "Foto-CasZarizeni-Hodiny-1.jpg"}, {"foto": ""}]}}
            ),
            ohledani_mista_json=json.dumps({"ohledani_priloha": "protokol.pdf"}),
        )
        self.assertEqual(
            classify_mu_attachment(
                "Foto-CelkovyPohled-1.jpg",
                zajisteni_names=zajisteni,
                casova_osa_names=casova,
                ohledani_names=ohledani,
            ),
            SECTION_ZAJISTENI,
        )
        self.assertEqual(
            classify_mu_attachment(
                "Foto-CasZarizeni-Hodiny-1.jpg",
                zajisteni_names=zajisteni,
                casova_osa_names=casova,
                ohledani_names=ohledani,
            ),
            SECTION_CASOVA_OSA,
        )
        self.assertEqual(
            classify_mu_attachment(
                "protokol.pdf",
                zajisteni_names=zajisteni,
                casova_osa_names=casova,
                ohledani_names=ohledani,
            ),
            SECTION_OHLEDANI,
        )
        self.assertEqual(
            classify_mu_attachment(
                "DodrzovaniPredpisu-1-skoleni.pdf",
                zajisteni_names=set(),
                casova_osa_names=set(),
                ohledani_names=set(),
            ),
            SECTION_DODRZOVANI,
        )
        self.assertEqual(
            classify_mu_attachment(
                "Formular-Svedek-1.odt",
                zajisteni_names=set(),
                casova_osa_names=set(),
                ohledani_names=set(),
            ),
            SECTION_SVEDCI,
        )

    def test_unknown_or_conflicting_origin_stays_shared(self) -> None:
        self.assertEqual(
            classify_mu_attachment(
                "fotografie_mista.jpg",
                zajisteni_names=set(),
                casova_osa_names=set(),
                ohledani_names=set(),
            ),
            SECTION_SHARED,
        )
        self.assertEqual(
            classify_mu_attachment(
                "poznamka.pdf",
                zajisteni_names=set(),
                casova_osa_names=set(),
                ohledani_names=set(),
            ),
            SECTION_SHARED,
        )
        self.assertEqual(
            classify_mu_attachment(
                "Ohledani-protokol.pdf",
                zajisteni_names={"Ohledani-protokol.pdf"},
                casova_osa_names=set(),
                ohledani_names={"Ohledani-protokol.pdf"},
            ),
            SECTION_SHARED,
        )


class MuPrilohyOverview422TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _case(self, title: str):
        return mu_investigation_service.create_investigation(title=title, started_at=date(2026, 5, 1))

    def _source(self, name: str) -> Path:
        path = _TMP / "sources" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"obsah-" + name.encode("utf-8"))
        return path

    def _attach(self, investigation_id: int, target_name: str):
        return attachment_service.add_file_as(
            ENTITY_MU_INVESTIGATION,
            investigation_id,
            str(self._source(target_name)),
            target_name,
        )

    def _records(self) -> list[tuple]:
        with get_session() as session:
            rows = session.execute(
                text(
                    "SELECT id, entity_type, entity_id, filename, stored_path, original_path "
                    "FROM attachments ORDER BY id"
                )
            ).all()
        return [tuple(row) for row in rows]

    def _rows(self, widget: MuPrilohyWidget) -> list[tuple[str, str]]:
        rows = []
        for row in range(widget.table.rowCount()):
            rows.append((widget.table.item(row, 0).text(), widget.table.item(row, 1).text()))
        return rows

    def test_overview_lists_one_case_without_changing_files(self) -> None:
        first = self._case("První spis")
        second = self._case("Druhý spis")
        photo = self._attach(first.id, "Foto-CelkovyPohled-mu_1.pdf")
        device = self._attach(first.id, "Foto-CasZarizeni-Hodiny-mu_1.pdf")
        protocol = self._attach(first.id, "protokol.pdf")
        rules = self._attach(first.id, "DodrzovaniPredpisu-mu-skoleni.pdf")
        form = self._attach(first.id, "Formular-Vypoved-mu.odt")
        plain = self._attach(first.id, "poznamka.pdf")
        similar = self._attach(first.id, "fotografie_mista.pdf")
        other = self._attach(second.id, "Foto-CelkovyPohled-mu_2.pdf")
        self.assertIsNotNone(other)

        before = self._records()
        widget = MuPrilohyWidget()
        widget.show()
        self.app.processEvents()
        try:
            widget.refresh(
                first.id,
                zajisteni_dukazu_json=json.dumps(
                    {"fotky": {"CelkovyPohled": photo.filename, "DetailMista": photo.filename}}
                ),
                casova_osa_json=json.dumps(
                    {"cas_synchronizace": {"caszarizeni_rows": [{"foto": device.filename}]}}
                ),
                ohledani_mista_json=json.dumps({"ohledani_priloha": protocol.filename}),
            )
            self.assertEqual(
                self._rows(widget),
                [
                    (photo.filename, SECTION_ZAJISTENI),
                    (device.filename, SECTION_CASOVA_OSA),
                    (protocol.filename, SECTION_OHLEDANI),
                    (rules.filename, SECTION_DODRZOVANI),
                    (form.filename, SECTION_SVEDCI),
                    (plain.filename, SECTION_SHARED),
                    (similar.filename, SECTION_SHARED),
                ],
            )
            self.assertEqual(len(self._rows(widget)), len({name for name, _section in self._rows(widget)}))
            self.assertEqual(self._records(), before)

            stored = attachment_service.resolve_path(photo)
            payload = stored.read_bytes()
            with patch("moduly.vysetrovani_mu.ui.mu_prilohy_widget.open_local_file") as open_file:
                widget.table.cellWidget(0, 2).click()
                self.app.processEvents()
            open_file.assert_called_once_with(stored, parent=widget, title="Přílohy")
            self.assertEqual(stored.read_bytes(), payload)
            self.assertEqual(self._records(), before)
            self.assertNotIn("Přidat", " ".join(button.text() for button in widget.findChildren(QPushButton)))
            self.assertNotIn("Odebrat", " ".join(button.text() for button in widget.findChildren(QPushButton)))
        finally:
            widget.close()
            widget.deleteLater()
            self.app.processEvents()

    def test_dialog_tab_refreshes_without_writing(self) -> None:
        created = self._case("Přehled v editoru")
        photo = self._attach(created.id, "Ohledani-protokol-mu.pdf")
        plain = self._attach(created.id, "protokol-bez-vazby.pdf")
        with get_session() as session:
            before_updated = session.execute(
                text("SELECT updated_at FROM mu_investigations WHERE id = :id"),
                {"id": created.id},
            ).scalar()
            session.execute(
                text("UPDATE mu_investigations SET ohledani_mista_json = :raw WHERE id = :id"),
                {"raw": json.dumps({"ohledani_priloha": photo.filename}), "id": created.id},
            )
            session.commit()
        before = self._records()

        dialog = MuInvestigationDialog(investigation=mu_investigation_service.get_by_id(created.id))
        dialog.resize(860, 720)
        dialog.show()
        self.app.processEvents()
        try:
            self.assertEqual(dialog.tabs.tabText(dialog.tabs.count() - 1), "Přílohy")
            self.assertEqual(dialog.tabs.tabText(dialog.tabs.count() - 2), "Závěr")
            dialog.tabs.setCurrentWidget(dialog.prilohy_widget)
            self.app.processEvents()
            rows = {
                dialog.prilohy_widget.table.item(row, 0).text(): dialog.prilohy_widget.table.item(row, 1).text()
                for row in range(dialog.prilohy_widget.table.rowCount())
            }
            self.assertEqual(rows[photo.filename], SECTION_OHLEDANI)
            self.assertEqual(rows[plain.filename], SECTION_SHARED)
            self.assertEqual(len(rows), 2)
            self.assertFalse(dialog._is_dirty())
            self.assertEqual(self._records(), before)
            with get_session() as session:
                updated = session.execute(
                    text("SELECT updated_at, ohledani_mista_json FROM mu_investigations WHERE id = :id"),
                    {"id": created.id},
                ).one()
            self.assertEqual(updated.updated_at, before_updated)
            self.assertIn(photo.filename, updated.ohledani_mista_json)

            dialog.ohledani_mista_widget.ohledani_priloha.setText(plain.filename)
            dialog.tabs.setCurrentIndex(0)
            dialog.tabs.setCurrentWidget(dialog.prilohy_widget)
            self.app.processEvents()
            refreshed = {
                dialog.prilohy_widget.table.item(row, 0).text(): dialog.prilohy_widget.table.item(row, 1).text()
                for row in range(dialog.prilohy_widget.table.rowCount())
            }
            self.assertEqual(refreshed[plain.filename], SECTION_OHLEDANI)
            self.assertEqual(refreshed[photo.filename], SECTION_OHLEDANI)
            self.assertEqual(self._records(), before)
            with get_session() as session:
                stored_json = session.execute(
                    text("SELECT ohledani_mista_json FROM mu_investigations WHERE id = :id"),
                    {"id": created.id},
                ).scalar()
            self.assertIn(photo.filename, stored_json)
            self.assertNotIn(plain.filename, stored_json)
        finally:
            dialog._closing = True
            dialog.close()
            dialog.deleteLater()
            self.app.processEvents()
