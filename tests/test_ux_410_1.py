"""UX-4.1.0-1: sloupce auditů, tlačítka manažera, auditovaný systém a dialog úkolu."""

from __future__ import annotations

import importlib
import os
import re
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication, QFormLayout, QHeaderView

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="ux-410-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.theme.app_style import apply_app_style
    from core.widgets.table_utils import configure_table_columns
    from moduly.audity.constants import (
        AUDITED_SYSTEM_LABEL,
        AUDIT_DETAILED_REPORT_BUTTON_LABEL,
        AUDIT_DETAILED_REPORT_BUTTON_SHORT,
        AUDIT_PROGRAM_ADD_VISIT_BUTTON,
        AUDIT_PROGRAM_ADD_VISIT_BUTTON_SHORT,
        AUDIT_PROGRAM_EDIT_VISIT_BUTTON,
        AUDIT_PROGRAM_EDIT_VISIT_BUTTON_SHORT,
        AUDIT_PROGRAM_EXPORT_PLAN_BUTTON_SHORT,
        AUDIT_PROGRAM_EXPORT_PLAN_TOOLTIP,
        AUDIT_PROGRAM_FINAL_REPORT_BUTTON,
        AUDIT_PROGRAM_GENERATE_VISITS_BUTTON,
        AUDIT_PROGRAM_MOVE_PROCESS_BUTTON,
        AUDIT_PROGRAM_OPEN_AUDIT_BUTTON,
        AUDIT_PROGRAM_PRINT_STATEMENTS_BUTTON,
        AUDIT_PROGRAM_REFRESH_OVERVIEW_BUTTON,
        AUDIT_PROGRAM_SKIP_VISIT_BUTTON,
        AUDIT_PROGRAM_SKIP_VISIT_BUTTON_SHORT,
        AUDIT_PROGRAM_START_AUDIT_BUTTON,
        AUDIT_PROGRAM_START_AUDIT_BUTTON_SHORT,
        AUDIT_PROGRAM_SUPPLEMENT_WORKPLACES_BUTTON,
        AUDIT_PROTOCOL_BUTTON_LABEL,
        AUDIT_PROTOCOL_BUTTON_SHORT,
        DEFAULT_AUDIT_PROGRAM_STANDARDS,
    )
    from moduly.audity.sluzby.audit_export_context_service import (
        audit_export_context_service,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.audity.sluzby.audit_service import audit_service
    from moduly.audity.sluzby.protokol_audit_service import protokol_audit_service
    from moduly.audity.ui.audit_program_manager_dialog import AuditProgramManagerDialog
    from moduly.audity.ui.audit_table import (
        COL_AUDIT_DATE,
        COL_FINDINGS_TOTAL,
        COL_NUMBER,
        COL_PLANNED_MONTH,
        COL_WORKPLACE,
        COL_YEAR,
        AuditTable,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.ui.task_dialog import TaskDialog


def _odt_plain(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        content = archive.read("content.xml").decode("utf-8")
    text = re.sub(r"<text:line-break\s*/>", "\n", content)
    text = re.sub(r"<[^>]+>", "", text)
    return text


class _AuditRow:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Ux4101AuditTableTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_column_names_order_and_bold_header_widths(self) -> None:
        table = AuditTable()
        configure_table_columns(table, "audity")
        table.resize(1800, 400)
        table.show()
        QApplication.processEvents()

        labels = [
            table.horizontalHeaderItem(column).text()
            for column in range(table.columnCount())
        ]
        self.assertEqual(
            labels[:7],
            [
                "ID",
                "Číslo auditu",
                "Rok",
                "Plán měsíc",
                "Plán datum",
                "Auditovaný provoz",
                "Celkem",
            ],
        )
        self.assertEqual(
            labels[7:],
            [
                "Závady",
                "Nedostatky",
                "Porušení",
                "Neshody",
                "Pozorování",
                "Zjištění",
                "PKZ",
                "Ostatní",
                "Stav",
                "Typ auditu",
            ],
        )
        header = table.horizontalHeader()
        self.assertEqual(
            header.sectionResizeMode(COL_WORKPLACE),
            QHeaderView.ResizeMode.Stretch,
        )
        self.assertEqual(
            header.sectionResizeMode(COL_AUDIT_DATE),
            QHeaderView.ResizeMode.Interactive,
        )
        self.assertEqual(
            header.sectionResizeMode(COL_PLANNED_MONTH),
            QHeaderView.ResizeMode.Interactive,
        )

        font = QFont(header.font())
        font.setBold(True)
        metrics = QFontMetrics(font)
        for column in (
            COL_NUMBER,
            COL_PLANNED_MONTH,
            COL_AUDIT_DATE,
            COL_WORKPLACE,
        ):
            text = table.horizontalHeaderItem(column).text()
            needed = metrics.horizontalAdvance(text) + 24
            self.assertGreaterEqual(table.columnWidth(column), needed, text)
        table.close()

    def test_cell_values_and_sort_keys_follow_columns(self) -> None:
        table = AuditTable()
        early = _AuditRow(
            id=1,
            number="A-1",
            year=2026,
            planned_month=1,
            audit_date=date(2026, 1, 10),
            workplace_name="Zeta",
            status="Plánováno",
            audit_type="Interní",
        )
        later = _AuditRow(
            id=2,
            number="A-2",
            year=2026,
            planned_month=6,
            audit_date=date(2026, 6, 2),
            workplace_name="Alfa",
            status="Plánováno",
            audit_type="Interní",
        )
        table.load_audits([early, later])

        self.assertEqual(table.item(0, COL_PLANNED_MONTH).text(), "leden")
        self.assertEqual(table.item(0, COL_AUDIT_DATE).text(), "10.01.2026")
        self.assertEqual(table.item(0, COL_WORKPLACE).text(), "Zeta")
        self.assertEqual(table.item(0, COL_FINDINGS_TOTAL).text(), "0")
        self.assertEqual(table.item(1, COL_YEAR).text(), "2026")

        table.sortItems(COL_AUDIT_DATE)
        self.assertEqual(table.item(0, COL_NUMBER).text(), "A-1")
        table.sortItems(COL_WORKPLACE)
        self.assertEqual(table.item(0, COL_NUMBER).text(), "A-2")
        self.assertEqual(table.item(0, COL_WORKPLACE).text(), "Alfa")
        self.assertEqual(table.item(0, COL_AUDIT_DATE).text(), "02.06.2026")
        table.close()


class Ux4101ManagerButtonsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        apply_app_style(cls._app)

    def test_short_labels_tooltips_and_full_width_at_1920(self) -> None:
        dialog = AuditProgramManagerDialog()
        dialog.resize(1920, 1080)
        dialog.show()
        QApplication.processEvents()

        overview = [
            (
                dialog._add_visit_btn,
                AUDIT_PROGRAM_ADD_VISIT_BUTTON_SHORT,
                AUDIT_PROGRAM_ADD_VISIT_BUTTON,
            ),
            (
                dialog._edit_visit_btn,
                AUDIT_PROGRAM_EDIT_VISIT_BUTTON_SHORT,
                AUDIT_PROGRAM_EDIT_VISIT_BUTTON,
            ),
            (
                dialog._skip_visit_btn,
                AUDIT_PROGRAM_SKIP_VISIT_BUTTON_SHORT,
                AUDIT_PROGRAM_SKIP_VISIT_BUTTON,
            ),
            (dialog._move_process_btn, AUDIT_PROGRAM_MOVE_PROCESS_BUTTON, ""),
            (
                dialog._start_audit_btn,
                AUDIT_PROGRAM_START_AUDIT_BUTTON_SHORT,
                AUDIT_PROGRAM_START_AUDIT_BUTTON,
            ),
            (dialog._open_audit_btn, AUDIT_PROGRAM_OPEN_AUDIT_BUTTON, ""),
            (
                dialog._print_statements_btn,
                AUDIT_PROGRAM_PRINT_STATEMENTS_BUTTON,
                "",
            ),
            (
                dialog._protocol_btn,
                AUDIT_PROTOCOL_BUTTON_SHORT,
                AUDIT_PROTOCOL_BUTTON_LABEL,
            ),
            (
                dialog._detailed_report_btn,
                AUDIT_DETAILED_REPORT_BUTTON_SHORT,
                AUDIT_DETAILED_REPORT_BUTTON_LABEL,
            ),
        ]
        previous_right = -1
        for button, text, tooltip in overview:
            self.assertEqual(button.text(), text)
            if tooltip:
                self.assertIn(tooltip, button.toolTip())
            else:
                self.assertEqual(button.toolTip(), "")
            self.assertFalse(button.isEnabled())
            self.assertGreaterEqual(button.width(), button.sizeHint().width())
            self.assertLessEqual(button.geometry().right(), button.parentWidget().width())
            self.assertGreater(button.geometry().left(), previous_right)
            previous_right = button.geometry().right()

        self.assertEqual(dialog._export_plan_btn.text(), AUDIT_PROGRAM_EXPORT_PLAN_BUTTON_SHORT)
        self.assertEqual(dialog._export_plan_btn.toolTip(), AUDIT_PROGRAM_EXPORT_PLAN_TOOLTIP)
        self.assertFalse(dialog._export_plan_btn.isEnabled())
        self.assertGreaterEqual(
            dialog._export_plan_btn.width(),
            dialog._export_plan_btn.sizeHint().width(),
        )
        self.assertEqual(
            dialog._generate_visits_btn.text(), AUDIT_PROGRAM_GENERATE_VISITS_BUTTON
        )
        self.assertEqual(
            dialog._supplement_workplaces_btn.text(),
            AUDIT_PROGRAM_SUPPLEMENT_WORKPLACES_BUTTON,
        )
        self.assertEqual(
            dialog._refresh_overview_btn.text(), AUDIT_PROGRAM_REFRESH_OVERVIEW_BUTTON
        )
        self.assertEqual(
            dialog._final_report_btn.text(), AUDIT_PROGRAM_FINAL_REPORT_BUTTON
        )
        dialog.close()


class Ux4101AuditedSystemTestCase(unittest.TestCase):
    def test_both_documents_use_fixed_system_and_keep_program_name(self) -> None:
        program_name = "Program UX410 Jedinečný název"
        program = audit_program_service.create_program(
            name=program_name,
            date_from=date(2026, 1, 1),
            date_to=date(2029, 12, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        audit = audit_service.create_audit(
            program_id=program.id,
            number="IA-410",
            year=2026,
            planned_month=5,
            audit_date=date(2026, 5, 4),
            workplace_name="Provoz UX410",
            audit_type="Řádný",
        )
        values = audit_export_context_service.build(audit).placeholder_values()
        self.assertEqual(values["auditovany_system"], AUDITED_SYSTEM_LABEL)
        self.assertEqual(values["program_nazev"], program_name)
        self.assertNotEqual(values["auditovany_system"], values["program_nazev"])

        for path in (
            protokol_audit_service.generate_for_audit(audit),
            protokol_audit_service.generate_detailed_report_for_audit(audit),
        ):
            plain = _odt_plain(path)
            self.assertIn(program_name, plain)
            start = 0
            found = 0
            while True:
                index = plain.find("Auditovaný systém", start)
                if index < 0:
                    break
                window = plain[index : index + 80]
                self.assertIn(AUDITED_SYSTEM_LABEL, window)
                self.assertNotIn(program_name, window)
                found += 1
                start = index + 1
            self.assertGreaterEqual(found, 1)


class Ux4101TaskDialogTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_workplace_follows_responsible_and_save_keeps_values(self) -> None:
        workplace = settings_service.save_workplace(name="Provoz úkolu UX410")
        task = task_service.create_task(
            title="Úkol UX410",
            priority="Vysoká",
            due_date=date(2026, 12, 1),
            workplace_id=workplace.id,
            note="Původní poznámka",
        )
        dialog = TaskDialog(task=task)
        form = dialog.title_edit.parentWidget().layout()
        self.assertIsInstance(form, QFormLayout)
        labels = []
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            labels.append("" if item is None or item.widget() is None else item.widget().text())
        self.assertEqual(
            labels[:11],
            [
                "Typ:",
                "Opatření:",
                "Odpovídá:",
                "Pracoviště:",
                "Priorita:",
                "Termín splnění:",
                "Připomenout od:",
                "",
                "Splnění:",
                "Splněno dne:",
                "Kontrolovat:",
            ],
        )
        self.assertIn("Poznámka / zjištěné závady:", labels)
        self.assertEqual(dialog.workplace_selector.current_workplace_id(), workplace.id)
        self.assertEqual(dialog.priority_combo.currentText(), "Vysoká")

        dialog.title_edit.setPlainText("Úkol UX410 uložený")
        self.assertTrue(dialog._persist())
        reloaded = task_service.get_task_by_id(task.id)
        self.assertEqual(reloaded.title, "Úkol UX410 uložený")
        self.assertEqual(reloaded.workplace_id, workplace.id)
        self.assertEqual(reloaded.priority, "Vysoká")
        self.assertEqual(reloaded.due_date, date(2026, 12, 1))
        self.assertEqual(reloaded.note, "Původní poznámka")

        again = TaskDialog(task=task_service.get_task_by_id(task.id))
        self.assertEqual(again.title_edit.toPlainText(), "Úkol UX410 uložený")
        self.assertEqual(again.workplace_selector.current_workplace_id(), workplace.id)
        self.assertEqual(again.priority_combo.currentText(), "Vysoká")
        dialog.close()
        again.close()


if __name__ == "__main__":
    unittest.main()
