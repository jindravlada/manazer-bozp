"""AUDIT-VYPOŘÁDÁNÍ-4: dialog a export přehledu vypořádání."""

from __future__ import annotations

import importlib
import os
import re
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text

from tests.temp_dir_helpers import create_tracked_temp_dir

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = create_tracked_temp_dir()

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database import session as session_module
    from core.shared.constants import (
        ENTITY_AUDITY,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_PRILEZITOST,
        SETTLEMENT_SOURCE_AUDITY,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_settlement_overview_service import (
        finding_settlement_overview_service,
    )
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.constants import (
        AUDIT_STATUS_DOKONCENO,
        AUDIT_STATUS_PROBIHA,
        SETTLEMENT_OVERVIEW_BUTTON_LABEL,
    )
    from moduly.audity.modely.audit import Audit
    from moduly.audity.repository.audit_repository import AuditRepository
    from moduly.audity.sluzby.prehled_vyporadani_export_service import (
        SECTION_NEW,
        SECTION_REOPENED,
        SECTION_SETTLED_BASELINE,
        SECTION_SETTLED_SINCE,
        SECTION_UNSETTLED,
        PrehledVyporadaniExportError,
        prehled_vyporadani_export_service,
        presented_date_problem,
    )
    from moduly.audity.ui.audity_page import AudityPage
    from moduly.audity.ui.prehled_vyporadani_dialog import (
        PrehledVyporadaniCreateDialog,
        PrehledVyporadaniDetailDialog,
        PrehledVyporadaniDialog,
    )
    from moduly.ukoly.sluzby.task_service import task_service


def _wipe() -> None:
    session_module.reconfigure_database_engine()
    with session_module.engine.begin() as connection:
        connection.execute(text("DELETE FROM finding_settlement_overview_items"))
        connection.execute(text("DELETE FROM finding_settlement_overviews"))
        connection.execute(text("DELETE FROM finding_status_events"))
        connection.execute(text("DELETE FROM findings"))
        connection.execute(text("DELETE FROM tasks"))
        connection.execute(text("DELETE FROM audits"))


def _overview_count() -> int:
    session_module.reconfigure_database_engine()
    with session_module.engine.connect() as connection:
        return int(
            connection.execute(
                text("SELECT COUNT(*) FROM finding_settlement_overviews")
            ).scalar()
            or 0
        )


def _odt_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("content.xml").decode("utf-8")
    text_value = re.sub(r"<text:line-break\s*/>", "\n", xml)
    text_value = re.sub(r"<[^>]+>", "", text_value)
    return text_value


class PrehledVyporadaniUiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _wipe()
        self.audits = AuditRepository()
        self.service = finding_settlement_overview_service
        self.export = prehled_vyporadani_export_service

    def _audit(self, *, status: str, year: int, number: str, workplace: str) -> Audit:
        return self.audits.add(
            Audit(
                number=number,
                year=year,
                status=status,
                workplace_name=workplace,
                title=f"Audit {number}/{year}",
            )
        )

    def _finding(self, audit_id: int, **fields):
        payload = {
            "finding_type": FINDING_TYPE_NESHODA,
            "description": "Zjištění",
            "status": FINDING_STATUS_OTEVRENE,
            "source_area_label": "Údržba",
            "source_section_label": "Zábradlí",
            "recommended_action": "Doplnit zábradlí",
        }
        payload.update(fields)
        return finding_service.create(ENTITY_AUDITY, audit_id, **payload)

    def _confirm_yes(self):
        from PySide6.QtWidgets import QMessageBox

        return patch(
            "moduly.audity.ui.prehled_vyporadani_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        )

    def _silence_warning(self):
        return patch(
            "moduly.audity.ui.prehled_vyporadani_dialog.QMessageBox.warning"
        )

    def test_opening_dialogs_does_not_write(self) -> None:
        self._audit(
            status=AUDIT_STATUS_DOKONCENO,
            year=2024,
            number="1",
            workplace="Dílna",
        )
        before = _overview_count()
        overview_dialog = PrehledVyporadaniDialog()
        create_dialog = PrehledVyporadaniCreateDialog()
        self.assertEqual(_overview_count(), before)
        self.assertEqual(overview_dialog.table.rowCount(), 0)
        self.assertFalse(overview_dialog.detail_btn.isEnabled())
        self.assertFalse(overview_dialog.export_btn.isEnabled())
        self.assertTrue(overview_dialog.new_btn.isEnabled())
        self.assertIn("neobsahují žádná zjištění", create_dialog.warning_label.text())
        _wipe()
        empty = PrehledVyporadaniCreateDialog()
        self.assertIn("žádný dokončený", empty.warning_label.text())
        self.assertEqual(_overview_count(), 0)
        overview_dialog.close()
        create_dialog.close()
        empty.close()

    def test_completed_audits_without_findings_are_reported(self) -> None:
        self._audit(
            status=AUDIT_STATUS_DOKONCENO,
            year=2024,
            number="1",
            workplace="Dílna",
        )
        dialog = PrehledVyporadaniCreateDialog()
        self.assertIn("neobsahují žádná zjištění", dialog.warning_label.text())
        self.assertEqual(_overview_count(), 0)
        dialog.close()

    def test_create_baseline_and_next_overview_from_dialog(self) -> None:
        from PySide6.QtCore import QDate
        from PySide6.QtWidgets import QMessageBox

        audit = self._audit(
            status=AUDIT_STATUS_DOKONCENO,
            year=2019,
            number="4",
            workplace="Dílna",
        )
        self._finding(audit.id, description="Stará neshoda")
        running = self._audit(
            status=AUDIT_STATUS_PROBIHA,
            year=2026,
            number="2",
            workplace="Dvůr",
        )
        self._finding(running.id, description="Z probíhajícího")

        create = PrehledVyporadaniCreateDialog()
        self.assertEqual(create.sequence_number, 0)
        self.assertEqual(create.heading_label.text(), "Přehled č. 0 – výchozí stav")
        create.date_edit.setDate(QDate(2026, 10, 1))
        create.note_edit.setPlainText("Bod 0")
        self.assertIn("výchozí stav k 01.10.2026", create.period_label.text())
        self.assertIn("neměnný historický snímek", create.confirmation_message())
        with patch(
            "moduly.audity.ui.prehled_vyporadani_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            create._save()
        self.assertEqual(_overview_count(), 0)

        with self._confirm_yes(), self._silence_warning():
            create._save()
        self.assertEqual(_overview_count(), 1)
        first = self.service.list_overviews(SETTLEMENT_SOURCE_AUDITY)[0]
        self.assertEqual(first.sequence_number, 0)
        self.assertIsNone(first.period_from)
        self.assertEqual(first.period_to, date(2026, 10, 1))
        self.assertEqual(first.note, "Bod 0")
        self.assertEqual(first.total_count, 1)

        listing = PrehledVyporadaniDialog()
        self.assertEqual(listing.table.rowCount(), 1)
        self.assertEqual(listing.table.item(0, 0).text(), "0")
        self.assertEqual(listing.table.item(0, 1).text(), "01.10.2026")
        self.assertIn("01.10.2026", listing.table.item(0, 2).text())
        self.assertEqual(listing.table.item(0, 3).text(), "1")
        listing.table.selectRow(0)
        self.assertTrue(listing.detail_btn.isEnabled())
        self.assertTrue(listing.export_btn.isEnabled())

        second = PrehledVyporadaniCreateDialog(previous=first)
        self.assertEqual(second.sequence_number, 1)
        self.assertEqual(second.heading_label.text(), "Přehled č. 1")
        self.assertEqual(second.previous_date_label.text(), "01.10.2026")
        second.date_edit.setDate(QDate(2026, 11, 2))
        self.assertEqual(
            second.period_label.text(),
            "01.10.2026 – 02.11.2026",
        )
        self.assertEqual(
            presented_date_problem(date(2026, 9, 1), first.presented_at),
            "Datum předložení nesmí být starší než datum předchozího přehledu.",
        )
        second.presented_date = lambda: date(2026, 9, 1)
        with self._silence_warning() as warning:
            second._save()
        self.assertTrue(warning.called)
        self.assertEqual(_overview_count(), 1)

        second.presented_date = lambda: date(2026, 11, 2)
        with self._confirm_yes(), self._silence_warning():
            second._save()
        rows = self.service.list_overviews(SETTLEMENT_SOURCE_AUDITY)
        self.assertEqual([row.sequence_number for row in rows], [0, 1])
        self.assertEqual(rows[1].period_from, date(2026, 10, 1))
        self.assertEqual(rows[1].period_to, date(2026, 11, 2))
        listing.refresh()
        self.assertEqual(
            [listing.table.item(row, 0).text() for row in range(listing.table.rowCount())],
            ["1", "0"],
        )
        listing.close()
        create.close()
        second.close()

    def test_detail_and_export_use_snapshot_categories(self) -> None:
        old = self._audit(
            status=AUDIT_STATUS_DOKONCENO,
            year=2020,
            number="10",
            workplace="Halda",
        )
        fresh = self._audit(
            status=AUDIT_STATUS_PROBIHA,
            year=2026,
            number="11",
            workplace="Rampa",
        )
        will_settle = self._finding(old.id, description="K vypořádání")
        will_reopen = self._finding(
            old.id,
            description="K znovuotevření",
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2026, 1, 15),
            finding_type=FINDING_TYPE_NESHODA,
        )
        stays = self._finding(
            old.id,
            description="Zůstává v procesu",
            status=FINDING_STATUS_V_PROCESU,
            finding_type=FINDING_TYPE_PRILEZITOST,
        )
        hidden = self._finding(fresh.id, description="Ještě ne")
        first = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date(2026, 6, 1),
            note="Výchozí",
        )
        finding_service.update(will_settle.id, status=FINDING_STATUS_VYPORADANO)
        finding_service.update(will_reopen.id, status=FINDING_STATUS_OTEVRENE)
        self.audits.update_fields(fresh.id, status=AUDIT_STATUS_DOKONCENO)
        self._finding(old.id, description="Nové po bodu 0")
        self.audits.update_fields(old.id, workplace_name="Přejmenováno")
        finding_service.update(stays.id, description="Upravený živý text")
        second = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date(2026, 9, 1),
        )

        baseline = PrehledVyporadaniDetailDialog(overview_id=first.id)
        baseline.show()
        self.assertEqual(baseline.load_error, "")
        self.assertEqual(baseline.total_label.text(), "3")
        self.assertEqual(baseline.settled_label.text(), "1")
        self.assertEqual(baseline.open_label.text(), "1")
        self.assertEqual(baseline.in_process_label.text(), "1")
        self.assertFalse(baseline.changes_box.isVisible())
        self.assertIn("Neshoda: 2", baseline.types_label.text())
        descriptions = {
            baseline.table.item(row, 5).text()
            for row in range(baseline.table.rowCount())
        }
        self.assertIn("Zůstává v procesu", descriptions)
        self.assertNotIn("Upravený živý text", descriptions)
        self.assertNotIn("Ještě ne", descriptions)
        workplaces = {
            baseline.table.item(row, 1).text()
            for row in range(baseline.table.rowCount())
        }
        self.assertIn("Halda", workplaces)
        self.assertNotIn("Přejmenováno", workplaces)

        later = PrehledVyporadaniDetailDialog(overview_id=second.id)
        later.show()
        self.assertTrue(later.changes_box.isVisible())
        self.assertEqual(later.settled_since_label.text(), "1")
        self.assertEqual(later.unsettled_label.text(), "4")
        self.assertEqual(later.new_label.text(), "2")
        self.assertEqual(later.reopened_label.text(), "1")
        later_descriptions = {
            later.table.item(row, 5).text()
            for row in range(later.table.rowCount())
        }
        self.assertIn("Upravený živý text", later_descriptions)
        self.assertIn("Ještě ne", later_descriptions)
        self.assertIn("Nové po bodu 0", later_descriptions)

        first_path = self.export.generate(first.id, output_path=_TMP / "bod0.odt")
        second_path = self.export.generate(second.id, output_path=_TMP / "bod1.odt")
        first_text = _odt_text(first_path)
        second_text = _odt_text(second_path)
        self.assertIn("PŘEHLED VYPOŘÁDÁNÍ ZJIŠTĚNÍ", first_text)
        self.assertIn("Z INTERNÍCH AUDITŮ", first_text)
        self.assertIn("Přehled č. 0 – výchozí stav", first_text)
        self.assertIn("Stav k: 01.06.2026", first_text)
        self.assertIn("Souhrnné vyhodnocení", first_text)
        self.assertIn("Celkem zjištění: 3", first_text)
        self.assertNotIn("AKTUÁLNÍ STAV", first_text)
        self.assertNotIn("ZMĚNY OD PŘEDCHOZÍHO PŘEHLEDU", first_text)
        self.assertNotIn("Podrobné tabulky obsahují pouze změny", first_text)
        self.assertIn("Vypořádáno: 1 (33 %)", first_text)
        self.assertIn(SECTION_SETTLED_BASELINE, first_text)
        self.assertIn(SECTION_UNSETTLED, first_text)
        self.assertNotIn(SECTION_NEW, first_text)
        self.assertNotIn(SECTION_REOPENED, first_text)
        self.assertIn("10/2020", first_text)
        self.assertNotIn("10/2020/2020", first_text)
        self.assertIn("Halda", first_text)
        self.assertIn("K znovuotevření", first_text)
        self.assertIn("15.01.2026", first_text)
        self.assertIn("Zůstává v procesu", first_text)
        self.assertNotIn("Řídicí proces:", first_text)
        self.assertNotIn("Oblast ověřování:", first_text)
        self.assertNotIn("Doporučené opatření:", first_text)
        self.assertNotIn("Upravený živý text", first_text)
        self.assertNotIn("${", first_text)

        self.assertIn("Přehled č. 1", second_text)
        self.assertIn("Období: 01.06.2026 – 01.09.2026", second_text)
        self.assertIn("AKTUÁLNÍ STAV", second_text)
        self.assertIn("Celkem evidovaných zjištění: 5", second_text)
        self.assertIn("Vypořádáno: 1 (20 %)", second_text)
        self.assertIn("ZMĚNY OD PŘEDCHOZÍHO PŘEHLEDU", second_text)
        self.assertIn("Nově vypořádáno: 1", second_text)
        self.assertIn("Nová zjištění: 2", second_text)
        self.assertIn("Znovuotevřeno: 1", second_text)
        self.assertIn(
            "Podrobné tabulky obsahují pouze změny "
            "od předchozího přehledu a všechna dosud "
            "nevypořádaná zjištění.",
            second_text,
        )
        self.assertNotIn("Souhrnné vyhodnocení", second_text)
        self.assertIn(SECTION_SETTLED_SINCE, second_text)
        self.assertIn(SECTION_NEW, second_text)
        self.assertNotIn(SECTION_REOPENED, second_text)
        self.assertLess(
            second_text.index("K vypořádání"),
            second_text.index(SECTION_UNSETTLED),
        )
        self.assertLess(
            second_text.index(SECTION_UNSETTLED),
            second_text.index("Upravený živý text"),
        )
        self.assertLess(
            second_text.index(SECTION_UNSETTLED),
            second_text.index("K znovuotevření"),
        )
        self.assertEqual(second_text.count("K znovuotevření"), 1)
        self.assertIn("Nové po bodu 0", second_text)
        self.assertIn("Ještě ne", second_text)

        finding_service.update(stays.id, description="Ještě novější text")
        repeated = self.export.generate(first.id, output_path=_TMP / "bod0-znovu.odt")
        repeated_text = _odt_text(repeated)
        self.assertIn("Zůstává v procesu", repeated_text)
        self.assertNotIn("Ještě novější text", repeated_text)
        self.assertNotIn("Upravený živý text", repeated_text)
        self.assertEqual(_overview_count(), 2)
        baseline.close()
        later.close()

    def test_export_keeps_task_snapshot(self) -> None:
        audit = self._audit(
            status=AUDIT_STATUS_DOKONCENO,
            year=2026,
            number="8",
            workplace="Jeřáb",
        )
        finding = self._finding(audit.id, recommended_action="Doplnit zábradlí")
        task = finding_task_service.create_task_from_finding(finding.id)
        overview = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date(2026, 7, 1),
        )
        task_service.update_task(
            task.id,
            title="Nový název úkolu",
            description=task.description,
            priority=task.priority,
            due_date=task.due_date,
            remind_from=task.remind_from,
            responsible_person_id=task.responsible_person_id,
            workplace_id=task.workplace_id,
            completed=True,
            completed_date=date.today(),
            checked_date=None,
            requires_verification=True,
        )
        text_value = _odt_text(
            self.export.generate(overview.id, output_path=_TMP / "ukol.odt")
        )
        self.assertIn("Doplnit zábradlí (Aktivní)", text_value)
        self.assertNotIn("Nový název úkolu", text_value)

    def test_failed_create_and_damaged_overview(self) -> None:
        audit = self._audit(
            status=AUDIT_STATUS_DOKONCENO,
            year=2026,
            number="1",
            workplace="Sklad",
        )
        finding = self._finding(audit.id, description="Původní text")
        create = PrehledVyporadaniCreateDialog()
        with (
            patch.object(
                type(self.service),
                "_build_item",
                side_effect=RuntimeError("selhání"),
            ),
            self._confirm_yes(),
            self._silence_warning() as warning,
        ):
            create._save()
        self.assertTrue(warning.called)
        self.assertIsNone(create.created_id)
        self.assertEqual(_overview_count(), 0)

        with self._confirm_yes(), self._silence_warning():
            create._save()
        overview = self.service.list_overviews(SETTLEMENT_SOURCE_AUDITY)[0]
        session_module.reconfigure_database_engine()
        with session_module.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE finding_settlement_overviews "
                    "SET type_counts_json = 'rozbité' WHERE id = :overview_id"
                ),
                {"overview_id": overview.id},
            )
        detail = PrehledVyporadaniDetailDialog(overview_id=overview.id)
        self.assertIn("poškozený", detail.load_error)
        with self.assertRaises(PrehledVyporadaniExportError):
            self.export.generate(overview.id, output_path=_TMP / "poskozeny.odt")
        self.assertFalse((_TMP / "poskozeny.odt").exists())
        stored = self.service.items_for(overview.id)[0]
        self.assertEqual(stored.description, "Původní text")
        finding_service.update(finding.id, description="Živá úprava")
        self.assertEqual(self.service.items_for(overview.id)[0].description, "Původní text")

        with self.assertRaises(PrehledVyporadaniExportError):
            self.export.load_view(999999)
        listing = PrehledVyporadaniDialog()
        listing.export_selected()
        with patch(
            "moduly.audity.ui.prehled_vyporadani_dialog.prehled_vyporadani_export_service.generate",
            side_effect=PrehledVyporadaniExportError("Export selhal."),
        ), self._silence_warning() as export_warning:
            listing.table.selectRow(0)
            listing.export_selected()
        self.assertTrue(export_warning.called)
        self.assertEqual(export_warning.call_args.args[2], "Export selhal.")
        self.assertEqual(_overview_count(), 1)
        create.close()
        listing.close()

    def test_audity_page_button_stays_available(self) -> None:
        from PySide6.QtCore import QItemSelectionModel

        from moduly.audity.constants import AUDIT_STATUS_FILTER_VSE, YEAR_FILTER_VSE
        from moduly.audity.sluzby.audit_service import audit_service

        audit_service.create_audit(title="Audit A", started_at=date(2026, 3, 1))
        audit_service.create_audit(title="Audit B", started_at=date(2026, 3, 2))
        page = AudityPage()
        page.status_filter.setCurrentText(AUDIT_STATUS_FILTER_VSE)
        page.year_filter.setCurrentIndex(page.year_filter.findData(YEAR_FILTER_VSE))
        page.refresh()
        self.assertEqual(page.settlement_btn.text(), SETTLEMENT_OVERVIEW_BUTTON_LABEL)
        self.assertTrue(page.settlement_btn.isEnabled())
        self.assertIn(
            "self.settlement_btn.clicked.connect(self.open_settlement_overviews)",
            Path("moduly/audity/ui/audity_page.py").read_text(encoding="utf-8"),
        )
        model = page.table.selectionModel()
        flags = (
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows
        )
        model.select(page.table.model().index(0, 0), flags)
        model.select(page.table.model().index(1, 0), flags)
        page._refresh_action_buttons()
        self.assertGreaterEqual(page._selected_row_count(), 2)
        self.assertTrue(page.settlement_btn.isEnabled())
        self.assertFalse(page.edit_btn.isEnabled())
        page.close()
