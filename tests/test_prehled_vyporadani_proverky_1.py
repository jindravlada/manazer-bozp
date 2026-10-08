"""PROVĚRKY-VYPOŘÁDÁNÍ-1: přehled vypořádání zjištění z prověrek BOZP."""

from __future__ import annotations

import html
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
    from core.database.session import get_session
    from core.shared.constants import (
        ENTITY_PROVERKY,
        FINDING_STATUS_OTEVRENE,
        FINDING_STATUS_V_PROCESU,
        FINDING_STATUS_VYPORADANO,
        FINDING_TYPE_NESHODA,
        FINDING_TYPE_POZOROVANI,
        FINDING_TYPE_PRILEZITOST,
        SETTLEMENT_SOURCE_AUDITY,
        SETTLEMENT_SOURCE_PROVERKY,
    )
    from core.shared.sluzby.finding_service import finding_service
    from core.shared.sluzby.finding_settlement_overview_service import (
        FindingSettlementOverviewError,
        finding_settlement_overview_service,
    )
    from core.shared.sluzby.finding_task_service import finding_task_service
    from moduly.audity.constants import AUDIT_STATUS_DOKONCENO
    from moduly.audity.modely.audit import Audit
    from moduly.audity.repository.audit_repository import AuditRepository
    from moduly.audity.sluzby.prehled_vyporadani_export_service import (
        EMPTY_SECTION,
        SECTION_NEW,
        SECTION_REOPENED,
        SECTION_SETTLED_BASELINE,
        SECTION_SETTLED_SINCE,
        SECTION_UNSETTLED,
        count_with_percent,
    )
    from moduly.audity.ui.prehled_vyporadani_dialog import (
        PrehledVyporadaniCreateDialog,
        PrehledVyporadaniDetailDialog,
        PrehledVyporadaniDialog,
    )
    from moduly.proverky.constants import (
        INSPECTION_STATUS_DOKONCENO,
        INSPECTION_STATUS_PLANOVANO,
        INSPECTION_STATUS_PROBIHA,
        SETTLEMENT_OVERVIEW_BUTTON_LABEL,
    )
    from moduly.proverky.modely.bozp_inspection import BozpInspection
    from moduly.proverky.sluzby.prehled_vyporadani_export_service import (
        RECORD_HEADING,
        prehled_vyporadani_proverky_export_service,
    )
    from moduly.proverky.ui.prehled_vyporadani_dialog import (
        PROVERKY_SETTLEMENT_PROFILE,
        PrehledVyporadaniProverkyDialog,
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
        connection.execute(text("DELETE FROM bozp_inspections"))


def _overview_count(source_type: str | None = None) -> int:
    session_module.reconfigure_database_engine()
    statement = "SELECT COUNT(*) FROM finding_settlement_overviews"
    params: dict[str, str] = {}
    if source_type is not None:
        statement += " WHERE source_type = :source_type"
        params["source_type"] = source_type
    with session_module.engine.connect() as connection:
        return int(connection.execute(text(statement), params).scalar() or 0)


def _odt_xml(path: Path, name: str) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read(name).decode("utf-8")


def _odt_text(path: Path) -> str:
    xml = _odt_xml(path, "content.xml")
    text_value = re.sub(r"<text:line-break\s*/>", "\n", xml)
    text_value = re.sub(r"<[^>]+>", "", text_value)
    return html.unescape(text_value)


class PrehledVyporadaniProverkyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        _wipe()
        self.audits = AuditRepository()
        self.service = finding_settlement_overview_service
        self.export = prehled_vyporadani_proverky_export_service

    def _inspection(
        self,
        *,
        status: str,
        year: int,
        number: str,
        workplace: str,
    ) -> BozpInspection:
        session = get_session()
        row = BozpInspection(
            number=number,
            year=year,
            status=status,
            workplace_name=workplace,
            title=f"Prověrka {number}",
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        session.expunge(row)
        session.close()
        return row

    def _finding(self, inspection_id: int, **fields):
        payload = {
            "finding_type": FINDING_TYPE_NESHODA,
            "description": "Zjištění z prověrky",
            "status": FINDING_STATUS_OTEVRENE,
            "source_area_label": "PROCES-XYZ",
            "source_section_label": "OBLAST-XYZ",
            "recommended_action": "OPATRENI-XYZ",
        }
        payload.update(fields)
        return finding_service.create(ENTITY_PROVERKY, inspection_id, **payload)

    def _confirm_yes(self):
        from PySide6.QtWidgets import QMessageBox

        return patch(
            "moduly.audity.ui.prehled_vyporadani_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        )

    def test_button_stays_available_and_toolbar_wraps_inside_window(self) -> None:
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QApplication

        from moduly.proverky.ui.proverky_page import ProverkyPage

        page = ProverkyPage()
        controls = [
            page.new_btn,
            page.edit_btn,
            page.delete_btn,
            page.plan_btn,
            page.generate_btn,
            page.protocol_btn,
            page.detailed_report_btn,
            page.report_btn,
            page.settlement_btn,
            page.knowledge_editor_btn,
            page.status_filter,
            page.year_filter,
        ]
        self.assertEqual(page.settlement_btn.text(), SETTLEMENT_OVERVIEW_BUTTON_LABEL)
        self.assertTrue(page.settlement_btn.isEnabled())
        self.assertFalse(page.edit_btn.isEnabled())
        page.show()
        for window_width in (1920, 1600, 1100):
            page.resize(window_width - 250, 800)
            QApplication.processEvents()
            positions = []
            for widget in controls:
                origin = widget.mapTo(page, QPoint(0, 0))
                self.assertGreater(widget.width(), 0, widget)
                self.assertGreater(widget.height(), 0, widget)
                self.assertGreaterEqual(origin.x(), 0, widget)
                self.assertLess(origin.x() + widget.width(), page.width() + 1, widget)
                self.assertLess(origin.y() + widget.height(), page.height() + 1, widget)
                self.assertEqual(widget.height(), widget.sizeHint().height(), widget)
                positions.append(origin)
            for earlier, later in zip(positions, positions[1:]):
                self.assertLessEqual(earlier.y(), later.y())
                if earlier.y() == later.y():
                    self.assertLess(earlier.x(), later.x())
        self.assertTrue(page.settlement_btn.isEnabled())
        page.close()

    def test_opening_dialog_does_not_write(self) -> None:
        self._inspection(
            status=INSPECTION_STATUS_DOKONCENO,
            year=2024,
            number="1/2024",
            workplace="Dílna",
        )
        before = _overview_count()
        listing = PrehledVyporadaniProverkyDialog()
        create = PrehledVyporadaniCreateDialog(profile=PROVERKY_SETTLEMENT_PROFILE)
        self.assertEqual(_overview_count(), before)
        self.assertEqual(listing.table.rowCount(), 0)
        self.assertFalse(listing.detail_btn.isEnabled())
        self.assertFalse(listing.export_btn.isEnabled())
        self.assertTrue(listing.new_btn.isEnabled())
        self.assertIn("neobsahují žádná zjištění", create.warning_label.text())
        self.assertIn("prověr", create.confirmation_message())
        listing.close()
        create.close()

        _wipe()
        empty = PrehledVyporadaniCreateDialog(profile=PROVERKY_SETTLEMENT_PROFILE)
        self.assertIn("žádná dokončená prověrka", empty.warning_label.text())
        self.assertEqual(_overview_count(), 0)
        empty.close()

    def test_baseline_includes_completed_inspections_of_all_years(self) -> None:
        from PySide6.QtCore import QDate

        old = self._inspection(
            status=INSPECTION_STATUS_DOKONCENO,
            year=2019,
            number="4/2019",
            workplace="Stará hala",
        )
        current = self._inspection(
            status=INSPECTION_STATUS_DOKONCENO,
            year=2026,
            number="3/2026",
            workplace="Hala 3",
        )
        running = self._inspection(
            status=INSPECTION_STATUS_PROBIHA,
            year=2026,
            number="2/2026",
            workplace="Dvůr",
        )
        planned = self._inspection(
            status=INSPECTION_STATUS_PLANOVANO,
            year=2024,
            number="1/2024",
            workplace="Kancelář",
        )
        long_text = "Dlouhý popis zjištění " + ("bez zkrácení " * 12)
        self._finding(old.id, description="Stará neshoda z roku 2019")
        settled = self._finding(
            current.id,
            description=long_text,
            finding_type=FINDING_TYPE_POZOROVANI,
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2026, 3, 1),
        )
        self._finding(
            current.id,
            description="Rozpracovaná příležitost",
            finding_type=FINDING_TYPE_PRILEZITOST,
            status=FINDING_STATUS_V_PROCESU,
        )
        self._finding(running.id, description="Z probíhající prověrky")
        self._finding(planned.id, description="Z plánované prověrky")
        open_task = self._finding(old.id, description="Otevřené s úkolem")
        task = finding_task_service.create_task_from_finding(open_task.id)

        audit = self.audits.add(
            Audit(
                number="9/2026",
                year=2026,
                status=AUDIT_STATUS_DOKONCENO,
                workplace_name="Auditovna",
                title="Audit",
            )
        )
        finding_service.create(
            "audity",
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Jen z auditu",
            status=FINDING_STATUS_OTEVRENE,
        )
        audit_overview = self.service.create_overview(
            SETTLEMENT_SOURCE_AUDITY,
            presented_at=date(2026, 9, 1),
        )

        create = PrehledVyporadaniCreateDialog(profile=PROVERKY_SETTLEMENT_PROFILE)
        self.assertEqual(create.sequence_number, 0)
        self.assertEqual(create.heading_label.text(), "Přehled č. 0 – výchozí stav")
        create.date_edit.setDate(QDate(2026, 10, 1))
        create.note_edit.setPlainText("Bod 0 prověrek")
        from PySide6.QtWidgets import QMessageBox

        with patch(
            "moduly.audity.ui.prehled_vyporadani_dialog.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ):
            create._save()
        self.assertEqual(_overview_count(SETTLEMENT_SOURCE_PROVERKY), 0)

        with self._confirm_yes():
            create._save()
        rows = self.service.list_overviews(SETTLEMENT_SOURCE_PROVERKY)
        self.assertEqual(len(rows), 1)
        first = rows[0]
        self.assertEqual(first.sequence_number, 0)
        self.assertEqual(first.presented_at, date(2026, 10, 1))
        self.assertEqual(first.total_count, 4)
        self.assertEqual(first.settled_count, 1)
        self.assertEqual(first.in_process_count, 2)
        self.assertEqual(first.open_count, 1)
        self.assertEqual(
            first.settled_count,
            int(count_with_percent(1, 4).split()[0]),
        )
        descriptions = {item.description for item in self.service.items_for(first.id)}
        self.assertIn(long_text, descriptions)
        self.assertIn("Stará neshoda z roku 2019", descriptions)
        self.assertNotIn("Z probíhající prověrky", descriptions)
        self.assertNotIn("Z plánované prověrky", descriptions)
        self.assertNotIn("Jen z auditu", descriptions)
        settled_item = next(
            item for item in self.service.items_for(first.id) if item.finding_id == settled.id
        )
        self.assertEqual(settled_item.audit_number, "3/2026")
        self.assertEqual(settled_item.audit_year, 2026)
        self.assertEqual(settled_item.workplace_name, "Hala 3")
        self.assertEqual(audit_overview.sequence_number, 0)
        self.assertEqual(
            [row.sequence_number for row in self.service.list_overviews(SETTLEMENT_SOURCE_AUDITY)],
            [0],
        )

        listing = PrehledVyporadaniProverkyDialog()
        self.assertEqual(listing.table.rowCount(), 1)
        self.assertEqual(listing.table.item(0, 0).text(), "0")
        listing.close()

        task_service.update_task(
            task.id,
            title="Přejmenovaný úkol",
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
        path = self.export.generate(first.id, output_path=_TMP / "bod0-proverky.odt")
        document = _odt_text(path)
        styles = _odt_xml(path, "styles.xml")
        self.assertIn("PŘEHLED VYPOŘÁDÁNÍ ZJIŠTĚNÍ", document)
        self.assertIn("Z PROVĚREK BOZP", document)
        self.assertIn("Přehled č. 0 – výchozí stav", document)
        self.assertIn("VÝCHOZÍ STAV", document)
        self.assertNotIn("AKTUÁLNÍ STAV", document)
        self.assertNotIn("ZMĚNY OD PŘEDCHOZÍHO PŘEHLEDU", document)
        self.assertIn("Datum předložení: 01.10.2026", document)
        self.assertIn("Období: výchozí stav k 01.10.2026", document)
        self.assertIn("Dosud nevypořádaná zjištění: 3", document)
        self.assertIn("- V procesu: 2", document)
        self.assertIn("- Otevřená: 1", document)
        self.assertNotIn("Celkem zjištění", document)
        self.assertNotIn("Typy zjištění", document)
        self.assertNotIn("%", document)
        self.assertIn(RECORD_HEADING, document)
        self.assertIn("3/2026", document)
        self.assertIn("Hala 3", document)
        self.assertNotIn("3/2026/2026", document)
        self.assertNotIn(long_text, document)
        self.assertNotIn(SECTION_SETTLED_BASELINE, document)
        self.assertIn(SECTION_UNSETTLED, document)
        self.assertNotIn("01.03.2026", document)
        self.assertIn("Otevřené s úkolem", document)
        self.assertIn("OPATRENI-XYZ (Aktivní)", document)
        self.assertNotIn("Přejmenovaný úkol", document)
        self.assertNotIn(SECTION_NEW, document)
        self.assertNotIn(SECTION_REOPENED, document)
        self.assertNotIn("PROCES-XYZ", document)
        self.assertNotIn("OBLAST-XYZ", document)
        self.assertNotIn("Z probíhající prověrky", document)
        self.assertNotIn("Jen z auditu", document)
        self.assertIn("z prověrek BOZP", styles)
        self.assertNotIn("interních auditů", styles)
        self.assertIn('fo:page-width="21.001cm"', styles)
        self.assertIn('fo:page-height="29.7cm"', styles)
        self.assertIn('style:print-orientation="portrait"', styles)
        create.close()

    def test_next_overview_categories_and_historical_export(self) -> None:
        old = self._inspection(
            status=INSPECTION_STATUS_DOKONCENO,
            year=2020,
            number="10/2020",
            workplace="Halda",
        )
        fresh = self._inspection(
            status=INSPECTION_STATUS_PROBIHA,
            year=2026,
            number="11/2026",
            workplace="Rampa",
        )
        will_settle = self._finding(old.id, description="K vypořádání")
        will_reopen = self._finding(
            old.id,
            description="K znovuotevření",
            status=FINDING_STATUS_VYPORADANO,
            resolved_at=date(2026, 1, 15),
        )
        stays = self._finding(
            old.id,
            description="Zůstává v procesu",
            status=FINDING_STATUS_V_PROCESU,
            finding_type=FINDING_TYPE_PRILEZITOST,
        )
        hidden = self._finding(fresh.id, description="Ještě ne")
        first = self.service.create_overview(
            SETTLEMENT_SOURCE_PROVERKY,
            presented_at=date(2026, 6, 1),
            note="Výchozí",
        )
        finding_service.update(will_settle.id, status=FINDING_STATUS_VYPORADANO)
        finding_service.update(will_reopen.id, status=FINDING_STATUS_OTEVRENE)
        session = get_session()
        stored = session.get(BozpInspection, fresh.id)
        stored.status = INSPECTION_STATUS_DOKONCENO
        renamed = session.get(BozpInspection, old.id)
        renamed.workplace_name = "Přejmenováno"
        renamed.number = "10/2020-zmena"
        session.commit()
        session.close()
        self._finding(old.id, description="Nové po bodu 0")
        finding_service.update(stays.id, description="Upravený živý text")
        second = self.service.create_overview(
            SETTLEMENT_SOURCE_PROVERKY,
            presented_at=date(2026, 9, 1),
        )
        self.assertEqual(second.sequence_number, 1)
        self.assertEqual(
            [row.sequence_number for row in self.service.list_overviews(SETTLEMENT_SOURCE_AUDITY)],
            [],
        )

        baseline = PrehledVyporadaniDetailDialog(
            overview_id=first.id,
            profile=PROVERKY_SETTLEMENT_PROFILE,
        )
        baseline.show()
        self.assertEqual(baseline.load_error, "")
        self.assertFalse(baseline.changes_box.isVisible())
        self.assertEqual(baseline.table.horizontalHeaderItem(0).text(), "Prověrka")
        references = {
            baseline.table.item(row, 0).text()
            for row in range(baseline.table.rowCount())
        }
        self.assertIn("10/2020", references)
        self.assertNotIn("10/2020/2020", references)
        self.assertNotIn("10/2020-zmena", references)
        workplaces = {
            baseline.table.item(row, 1).text()
            for row in range(baseline.table.rowCount())
        }
        self.assertIn("Halda", workplaces)
        self.assertNotIn("Přejmenováno", workplaces)
        descriptions = {
            baseline.table.item(row, 5).text()
            for row in range(baseline.table.rowCount())
        }
        self.assertIn("Zůstává v procesu", descriptions)
        self.assertNotIn("Upravený živý text", descriptions)
        self.assertNotIn("Ještě ne", descriptions)

        later = PrehledVyporadaniDetailDialog(
            overview_id=second.id,
            profile=PROVERKY_SETTLEMENT_PROFILE,
        )
        later.show()
        self.assertTrue(later.changes_box.isVisible())
        self.assertEqual(later.settled_since_label.text(), "1")
        self.assertEqual(later.unsettled_label.text(), "4")
        self.assertEqual(later.new_label.text(), "2")
        self.assertEqual(later.reopened_label.text(), "1")

        second_text = _odt_text(
            self.export.generate(second.id, output_path=_TMP / "bod1-proverky.odt")
        )
        self.assertIn("Přehled č. 1", second_text)
        self.assertIn("Datum předložení: 01.09.2026", second_text)
        self.assertIn("Období: 01.06.2026 – 01.09.2026", second_text)
        self.assertLess(
            second_text.index("ZMĚNY OD PŘEDCHOZÍHO PŘEHLEDU"),
            second_text.index("AKTUÁLNÍ STAV"),
        )
        self.assertIn("Nová zjištění: 2", second_text)
        self.assertIn("Vypořádaná od posledního přehledu: 1", second_text)
        self.assertIn("Znovuotevřená zjištění: 1", second_text)
        self.assertEqual(second_text.count("Znovuotevřená zjištění"), 1)
        self.assertIn("Dosud nevypořádaná zjištění: 4", second_text)
        self.assertIn("- V procesu: 1", second_text)
        self.assertIn("- Otevřená: 3", second_text)
        self.assertNotIn("Celkem evidovaných", second_text)
        self.assertNotIn("%", second_text)
        self.assertIn(SECTION_SETTLED_SINCE, second_text)
        self.assertIn(SECTION_NEW, second_text)
        self.assertIn("K vypořádání", second_text)
        self.assertIn("Nové po bodu 0", second_text)
        self.assertIn("Ještě ne", second_text)
        self.assertIn("K znovuotevření", second_text)
        self.assertEqual(second_text.count("K znovuotevření"), 1)
        unsettled_table = second_text.index(
            SECTION_UNSETTLED,
            second_text.index(SECTION_UNSETTLED) + len(SECTION_UNSETTLED),
        )
        new_table = second_text.index(
            SECTION_NEW,
            second_text.index(SECTION_NEW) + len(SECTION_NEW),
        )
        self.assertLess(unsettled_table, second_text.index("K znovuotevření"))
        self.assertLess(second_text.index("K znovuotevření"), new_table)
        self.assertIn("Upravený živý text", second_text)
        listing = PrehledVyporadaniProverkyDialog()
        self.assertEqual(
            [listing.table.item(row, 0).text() for row in range(listing.table.rowCount())],
            ["1", "0"],
        )
        listing.close()

        finding_service.update(stays.id, description="Ještě novější text")
        repeated = _odt_text(
            self.export.generate(first.id, output_path=_TMP / "bod0-znovu.odt")
        )
        self.assertIn("Zůstává v procesu", repeated)
        self.assertNotIn("Ještě novější text", repeated)
        self.assertNotIn("Upravený živý text", repeated)
        self.assertNotIn(SECTION_NEW, repeated)
        self.assertEqual(hidden.description, "Ještě ne")
        baseline.close()
        later.close()

    def test_dialog_sorts_each_series_newest_first(self) -> None:
        for presented in (date(2024, 1, 10), date(2025, 6, 1), date(2026, 3, 1)):
            self.service.create_overview(
                SETTLEMENT_SOURCE_PROVERKY,
                presented_at=presented,
            )
        for presented in (date(2026, 1, 1), date(2026, 8, 1)):
            self.service.create_overview(
                SETTLEMENT_SOURCE_AUDITY,
                presented_at=presented,
            )

        inspections = PrehledVyporadaniProverkyDialog()
        audits = PrehledVyporadaniDialog()
        self.assertEqual(
            [inspections.table.item(row, 0).text() for row in range(3)],
            ["2", "1", "0"],
        )
        self.assertEqual(inspections._overviews[-1].sequence_number, 2)
        self.assertEqual(
            [audits.table.item(row, 0).text() for row in range(2)],
            ["1", "0"],
        )
        self.assertEqual(audits._overviews[-1].sequence_number, 1)
        self.assertEqual(
            [row.sequence_number for row in self.service.list_overviews(SETTLEMENT_SOURCE_PROVERKY)],
            [0, 1, 2],
        )
        inspections.close()
        audits.close()

    def test_empty_overview_and_error_states(self) -> None:
        from PySide6.QtCore import QDate

        create = PrehledVyporadaniCreateDialog(profile=PROVERKY_SETTLEMENT_PROFILE)
        create.date_edit.setDate(QDate(2026, 10, 8))
        with self._confirm_yes():
            create._save()
        overview = self.service.list_overviews(SETTLEMENT_SOURCE_PROVERKY)[0]
        self.assertEqual(overview.sequence_number, 0)
        self.assertEqual(overview.total_count, 0)
        empty_text = _odt_text(
            self.export.generate(overview.id, output_path=_TMP / "prazdny.odt")
        )
        self.assertIn("VÝCHOZÍ STAV", empty_text)
        self.assertIn("Dosud nevypořádaná zjištění: 0", empty_text)
        self.assertIn("- V procesu: 0", empty_text)
        self.assertIn("- Otevřená: 0", empty_text)
        self.assertIn(EMPTY_SECTION, empty_text)
        self.assertEqual(empty_text.count(EMPTY_SECTION), 1)
        self.assertNotIn(SECTION_NEW, empty_text)
        self.assertNotIn(SECTION_REOPENED, empty_text)
        self.assertNotIn(SECTION_SETTLED_BASELINE, empty_text)
        self.assertNotIn("Celkem zjištění", empty_text)
        self.assertNotIn("%", empty_text)

        later = PrehledVyporadaniCreateDialog(
            previous=overview,
            profile=PROVERKY_SETTLEMENT_PROFILE,
        )
        with (
            patch.object(later, "presented_date", return_value=date(2026, 10, 1)),
            patch(
                "moduly.audity.ui.prehled_vyporadani_dialog.QMessageBox.warning"
            ) as warned,
        ):
            later._save()
        self.assertTrue(warned.called)
        self.assertEqual(_overview_count(SETTLEMENT_SOURCE_PROVERKY), 1)
        with self.assertRaises(FindingSettlementOverviewError):
            self.service.create_overview(
                SETTLEMENT_SOURCE_PROVERKY,
                presented_at=date(2026, 1, 1),
            )

        inspection = self._inspection(
            status=INSPECTION_STATUS_DOKONCENO,
            year=2026,
            number="1/2026",
            workplace="Sklad",
        )
        self._finding(inspection.id, description="Původní text")
        with patch.object(
            type(self.service),
            "_build_item",
            side_effect=RuntimeError("selhání"),
        ):
            with self.assertRaises(RuntimeError):
                self.service.create_overview(SETTLEMENT_SOURCE_PROVERKY)
        self.assertEqual(_overview_count(SETTLEMENT_SOURCE_PROVERKY), 1)

        session_module.reconfigure_database_engine()
        with session_module.engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE finding_settlement_overviews "
                    "SET type_counts_json = 'rozbité' WHERE id = :overview_id"
                ),
                {"overview_id": overview.id},
            )
        detail = PrehledVyporadaniDetailDialog(
            overview_id=overview.id,
            profile=PROVERKY_SETTLEMENT_PROFILE,
        )
        self.assertIn("poškozený", detail.load_error)
        with self.assertRaises(Exception):
            self.export.generate(overview.id, output_path=_TMP / "poskozeny.odt")
        self.assertFalse((_TMP / "poskozeny.odt").exists())

        audit = self.audits.add(
            Audit(
                number="1/2026",
                year=2026,
                status=AUDIT_STATUS_DOKONCENO,
                workplace_name="Auditovna",
                title="Audit",
            )
        )
        finding_service.create(
            "audity",
            audit.id,
            finding_type=FINDING_TYPE_NESHODA,
            description="Auditní text",
            status=FINDING_STATUS_OTEVRENE,
        )
        audit_overview = self.service.create_overview(SETTLEMENT_SOURCE_AUDITY)
        with self.assertRaises(Exception):
            self.export.load_view(audit_overview.id)
        with self.assertRaises(Exception):
            self.export.load_view(999999)
        audit_detail = PrehledVyporadaniDetailDialog(overview_id=overview.id)
        self.assertIn("nalezen", audit_detail.load_error)
        self.assertEqual(audit_overview.sequence_number, 0)
        create.close()
        later.close()
        detail.close()
        audit_detail.close()
