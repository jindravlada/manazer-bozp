"""UX-TABLE-1d – typované řazení Úkolů, Knihy úrazů, MU a právních požadavků."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.widgets.typed_table_sort import sorting_paused
    from moduly.kniha_urazu.sluzby.accident_service import accident_service
    from moduly.kniha_urazu.ui.accident_table import AccidentTable
    from moduly.pravni_pozadavky.constants import (
        COMPLIANCE_CASTECNE_SPLNENO,
        COMPLIANCE_NENI_RELEVANTNI,
        COMPLIANCE_NESPLNENO,
        COMPLIANCE_SPLNENO,
        COMPLIANCE_STATUS_LABELS,
        DOCUMENT_TYPE_ZAKON,
    )
    from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
        legal_requirement_service,
    )
    from moduly.pravni_pozadavky.ui.legal_document_table import LegalDocumentTable
    from moduly.pravni_pozadavky.ui.legal_requirement_table import (
        COL_CODE,
        COL_ID,
        COL_PROCESS,
        COL_STATUS,
        LegalRequirementTable,
    )
    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.task_display import COL_DESCRIPTION, COL_DUE_DATE, COL_INDICATOR
    from moduly.ukoly.ui.task_table import TaskTable
    from moduly.vysetrovani_mu.constants import (
        MU_STATUS_DOKONCENO,
        MU_STATUS_ODLOZENO,
        MU_STATUS_PROBIHA,
    )
    from moduly.vysetrovani_mu.sluzby.mu_investigation_service import (
        mu_investigation_service,
    )
    from moduly.vysetrovani_mu.ui.mu_investigation_table import MuInvestigationTable


def _column_texts(table, column: int) -> list[str]:
    return [table.item(row, column).text() for row in range(table.rowCount())]


def _column_ids(table, column: int = 0) -> list[int]:
    return [int(table.item(row, column).text()) for row in range(table.rowCount())]


class UxTable1dTasksSortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.ukoly.modely.task import Task

        with get_session() as session:
            session.execute(delete(Task))
            session.commit()

    def test_task_due_date_sort(self) -> None:
        mid = task_service.create_task(title="A", due_date=date(2026, 3, 15))
        early = task_service.create_task(title="B", due_date=date(2026, 1, 5))
        late = task_service.create_task(title="C", due_date=date(2026, 7, 1))

        table = TaskTable()
        table.load_tasks(task_service.get_all_tasks())
        table.sortItems(COL_DUE_DATE, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_ids(table), [early.id, mid.id, late.id])

    def test_task_czech_title_sort(self) -> None:
        a = task_service.create_task(title="Chalupa")
        b = task_service.create_task(title="Cibule")
        c = task_service.create_task(title="Hrášek")

        table = TaskTable()
        table.load_tasks([a, b, c])
        table.sortItems(COL_DESCRIPTION, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, COL_DESCRIPTION), ["Cibule", "Hrášek", "Chalupa"])
        self.assertEqual(_column_ids(table), [b.id, c.id, a.id])

    def test_task_status_workflow_order(self) -> None:
        active = task_service.create_task(title="Aktivní")
        waiting = task_service.create_task(
            title="Čeká",
            completed=True,
            requires_verification=True,
        )
        done = task_service.create_task(
            title="Hotovo",
            completed=True,
            requires_verification=False,
        )
        canceled = task_service.create_task(title="Zrušen")
        task_service.cancel_task(canceled.id)
        canceled = task_service.get_task_by_id(canceled.id)

        self.assertEqual(active.computed_status, "Aktivní")
        self.assertEqual(waiting.computed_status, "Splněno - čeká na kontrolu")
        self.assertEqual(done.computed_status, "Ukončeno")
        self.assertEqual(canceled.computed_status, "Zrušeno")

        table = TaskTable()
        table.load_tasks([done, canceled, waiting, active])
        table.sortItems(COL_INDICATOR, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_ids(table), [active.id, waiting.id, done.id, canceled.id])

    def test_task_correct_record_after_sort(self) -> None:
        target = task_service.create_task(title="Cibule")
        task_service.create_task(title="Chalupa")
        task_service.create_task(title="Hrášek")

        table = TaskTable()
        table.load_tasks(task_service.get_all_tasks())
        table.sortItems(COL_DESCRIPTION, Qt.SortOrder.AscendingOrder)
        table.selectRow(0)
        self.assertEqual(int(table.item(0, 0).text()), target.id)

    def test_task_refresh_keeps_active_sort(self) -> None:
        first = task_service.create_task(title="Chalupa")
        second = task_service.create_task(title="Cibule")

        table = TaskTable()
        table.load_tasks([first, second])
        table.sortItems(COL_DESCRIPTION, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_ids(table), [second.id, first.id])

        third = task_service.create_task(title="Hrášek")
        table.load_tasks([first, second, third])
        self.assertEqual(_column_ids(table), [second.id, third.id, first.id])


class UxTable1dAccidentSortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.kniha_urazu.modely.accident import Accident
        from moduly.kniha_urazu.modely.investigation import AccidentInvestigation

        with get_session() as session:
            session.execute(delete(AccidentInvestigation))
            session.execute(delete(Accident))
            session.commit()

    def test_accident_datetime_sort(self) -> None:
        mid = accident_service.create_accident(
            jmeno_prijmeni="A",
            accident_date=date(2026, 3, 15),
            accident_time="10:00",
        )
        early = accident_service.create_accident(
            jmeno_prijmeni="B",
            accident_date=date(2026, 3, 15),
            accident_time="08:30",
        )
        late = accident_service.create_accident(
            jmeno_prijmeni="C",
            accident_date=date(2026, 3, 16),
            accident_time="07:00",
        )

        table = AccidentTable()
        table.load_accidents([mid, early, late])
        table.sortItems(3, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_ids(table, 1), [early.id, mid.id, late.id])

    def test_accident_number_sort(self) -> None:
        a = accident_service.create_accident(
            jmeno_prijmeni="A",
            accident_date=date(2026, 1, 1),
            year=2026,
        )
        b = accident_service.create_accident(
            jmeno_prijmeni="B",
            accident_date=date(2026, 1, 2),
            year=2026,
        )
        c = accident_service.create_accident(
            jmeno_prijmeni="C",
            accident_date=date(2025, 1, 1),
            year=2025,
        )
        # Doménové pořadí: rok, pak id (číslo id/rok).
        table = AccidentTable()
        table.load_accidents([a, b, c])
        table.sortItems(2, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_ids(table, 1), [c.id, a.id, b.id])

        numbers = _column_texts(table, 2)
        self.assertTrue(numbers[0].endswith("/2025"))
        self.assertTrue(numbers[1].endswith("/2026"))
        self.assertTrue(numbers[2].endswith("/2026"))
        self.assertLess(int(numbers[1].split("/")[0]), int(numbers[2].split("/")[0]))

    def test_accident_employee_czech_sort(self) -> None:
        a = accident_service.create_accident(jmeno_prijmeni="Chalupa", accident_date=date(2026, 1, 1))
        b = accident_service.create_accident(jmeno_prijmeni="Cibule", accident_date=date(2026, 1, 2))
        c = accident_service.create_accident(jmeno_prijmeni="Hrášek", accident_date=date(2026, 1, 3))

        table = AccidentTable()
        table.load_accidents([a, b, c])
        table.sortItems(4, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, 4), ["Cibule", "Hrášek", "Chalupa"])
        self.assertEqual(_column_ids(table, 1), [b.id, c.id, a.id])

    def test_accident_zou_status_sort(self) -> None:
        overdue = accident_service.create_accident(jmeno_prijmeni="A", accident_date=date(2026, 1, 1))
        waiting = accident_service.create_accident(jmeno_prijmeni="B", accident_date=date(2026, 1, 2))
        done = accident_service.create_accident(jmeno_prijmeni="C", accident_date=date(2026, 1, 3))

        table = AccidentTable()
        with patch.object(
            AccidentTable,
            "_zou_summary_state",
            side_effect=lambda accident, *_args: {
                overdue.id: "overdue",
                waiting.id: "waiting",
                done.id: "done",
            }[accident.id],
        ):
            table.load_accidents([done, overdue, waiting])
            table.sortItems(9, Qt.SortOrder.AscendingOrder)
            self.assertEqual(_column_ids(table, 1), [overdue.id, waiting.id, done.id])

    def test_accident_correct_record_after_sort(self) -> None:
        target = accident_service.create_accident(
            jmeno_prijmeni="Cibule",
            accident_date=date(2026, 1, 1),
        )
        accident_service.create_accident(jmeno_prijmeni="Chalupa", accident_date=date(2026, 1, 2))
        accident_service.create_accident(jmeno_prijmeni="Hrášek", accident_date=date(2026, 1, 3))

        table = AccidentTable()
        table.load_accidents(accident_service.get_all())
        table.sortItems(4, Qt.SortOrder.AscendingOrder)
        table.selectRow(0)
        self.assertEqual(int(table.item(0, 1).text()), target.id)


class UxTable1dMuSortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for investigation in mu_investigation_service.get_all():
            mu_investigation_service.delete_investigation(investigation.id)

    def test_mu_event_date_sort(self) -> None:
        mid = mu_investigation_service.create_investigation(
            title="A",
            started_at=date(2026, 3, 15),
        )
        early = mu_investigation_service.create_investigation(
            title="B",
            started_at=date(2026, 1, 5),
        )
        late = mu_investigation_service.create_investigation(
            title="C",
            started_at=date(2026, 7, 1),
        )

        table = MuInvestigationTable()
        table.load_investigations([mid, early, late])
        table.sortItems(5, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_ids(table), [early.id, mid.id, late.id])

    def test_mu_status_workflow_order(self) -> None:
        done = mu_investigation_service.create_investigation(
            title="Hotovo",
            status=MU_STATUS_DOKONCENO,
            started_at=date(2026, 1, 1),
        )
        running = mu_investigation_service.create_investigation(
            title="Běží",
            status=MU_STATUS_PROBIHA,
            started_at=date(2026, 1, 2),
        )
        deferred = mu_investigation_service.create_investigation(
            title="Odloženo",
            status=MU_STATUS_ODLOZENO,
            started_at=date(2026, 1, 3),
        )

        table = MuInvestigationTable()
        table.load_investigations([done, deferred, running])
        table.sortItems(2, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            _column_texts(table, 2),
            [MU_STATUS_PROBIHA, MU_STATUS_DOKONCENO, MU_STATUS_ODLOZENO],
        )
        self.assertEqual(_column_ids(table), [running.id, done.id, deferred.id])

    def test_mu_czech_title_sort(self) -> None:
        a = mu_investigation_service.create_investigation(title="Chalupa", started_at=date(2026, 1, 1))
        b = mu_investigation_service.create_investigation(title="Cibule", started_at=date(2026, 1, 2))
        c = mu_investigation_service.create_investigation(title="Hrášek", started_at=date(2026, 1, 3))

        table = MuInvestigationTable()
        table.load_investigations([a, b, c])
        table.sortItems(7, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, 7), ["Cibule", "Hrášek", "Chalupa"])
        self.assertEqual(_column_ids(table), [b.id, c.id, a.id])

    def test_mu_correct_record_after_sort(self) -> None:
        target = mu_investigation_service.create_investigation(
            title="Cibule",
            started_at=date(2026, 1, 1),
        )
        mu_investigation_service.create_investigation(title="Chalupa", started_at=date(2026, 1, 2))
        mu_investigation_service.create_investigation(title="Hrášek", started_at=date(2026, 1, 3))

        table = MuInvestigationTable()
        table.load_investigations(mu_investigation_service.get_all())
        table.sortItems(7, Qt.SortOrder.AscendingOrder)
        table.selectRow(0)
        self.assertEqual(int(table.item(0, 0).text()), target.id)


class UxTable1dLegalSortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_document import LegalDocument
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement

        with get_session() as session:
            session.execute(delete(LegalRequirement))
            session.execute(delete(LegalDocument))
            session.commit()

    def test_requirement_czech_name_and_process_code(self) -> None:
        a = legal_requirement_service.create_requirement(
            title="Chalupa",
            process_code="P-010",
            compliance_status=COMPLIANCE_SPLNENO,
        )
        b = legal_requirement_service.create_requirement(
            title="Cibule",
            process_code="P-002",
            compliance_status=COMPLIANCE_SPLNENO,
        )
        c = legal_requirement_service.create_requirement(
            title="Hrášek",
            process_code="P-001",
            compliance_status=COMPLIANCE_SPLNENO,
        )

        table = LegalRequirementTable()
        table.load_requirements([a, b, c])
        table.sortItems(COL_PROCESS, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, COL_PROCESS), ["Cibule", "Hrášek", "Chalupa"])
        self.assertEqual(_column_ids(table, COL_ID), [b.id, c.id, a.id])

        table.sortItems(COL_CODE, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, COL_CODE), ["P-001", "P-002", "P-010"])
        self.assertEqual(_column_ids(table, COL_ID), [c.id, b.id, a.id])

    def test_requirement_compliance_status_order(self) -> None:
        from sqlalchemy import update

        from core.database.session import get_session
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement

        empty = legal_requirement_service.create_requirement(title="Bez")
        with get_session() as session:
            session.execute(
                update(LegalRequirement)
                .where(LegalRequirement.id == empty.id)
                .values(compliance_status="")
            )
            session.commit()
        empty = legal_requirement_service.get_by_id(empty.id)

        done = legal_requirement_service.create_requirement(
            title="Splněno",
            compliance_status=COMPLIANCE_SPLNENO,
        )
        partial = legal_requirement_service.create_requirement(
            title="Částečně",
            compliance_status=COMPLIANCE_CASTECNE_SPLNENO,
        )
        missing = legal_requirement_service.create_requirement(
            title="Nesplněno",
            compliance_status=COMPLIANCE_NESPLNENO,
        )
        irrelevant = legal_requirement_service.create_requirement(
            title="Není",
            compliance_status=COMPLIANCE_NENI_RELEVANTNI,
        )

        table = LegalRequirementTable()
        table.load_requirements([irrelevant, empty, missing, done, partial])
        table.sortItems(COL_STATUS, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            _column_texts(table, COL_STATUS),
            [
                COMPLIANCE_STATUS_LABELS[COMPLIANCE_SPLNENO],
                COMPLIANCE_STATUS_LABELS[COMPLIANCE_CASTECNE_SPLNENO],
                COMPLIANCE_STATUS_LABELS[COMPLIANCE_NESPLNENO],
                COMPLIANCE_STATUS_LABELS[COMPLIANCE_NENI_RELEVANTNI],
                "",
            ],
        )
        self.assertEqual(
            _column_ids(table, COL_ID),
            [done.id, partial.id, missing.id, irrelevant.id, empty.id],
        )

    def test_document_number_effective_date_and_active(self) -> None:
        late = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Pozdě",
            number="10/2026",
            year=2026,
            effective_from=date(2026, 6, 1),
            active=True,
        )
        early = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Dříve",
            number="2/2026",
            year=2026,
            effective_from=date(2026, 1, 1),
            active=False,
        )
        mid = legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Střed",
            number="3/2025",
            year=2025,
            effective_from=date(2026, 3, 1),
            active=True,
        )

        table = LegalDocumentTable()
        table.load_documents([late, early, mid])
        table.sortItems(6, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_ids(table), [early.id, mid.id, late.id])

        table.sortItems(8, Qt.SortOrder.AscendingOrder)
        # False před True při vzestupném řazení bool.
        self.assertEqual(_column_ids(table)[0], early.id)
        self.assertEqual(_column_texts(table, 8)[0], "Ne")

        table.sortItems(4, Qt.SortOrder.AscendingOrder)
        table.selectRow(0)
        self.assertEqual(table.selected_document_id(), early.id)

        table.sortItems(2, Qt.SortOrder.AscendingOrder)
        numbers = _column_texts(table, 2)
        self.assertEqual(numbers, ["2/2026", "3/2025", "10/2026"])

    def test_requirement_correct_record_after_sort(self) -> None:
        target = legal_requirement_service.create_requirement(title="Cibule")
        legal_requirement_service.create_requirement(title="Chalupa")
        legal_requirement_service.create_requirement(title="Hrášek")

        table = LegalRequirementTable()
        table.load_requirements(legal_requirement_service.get_all())
        table.sortItems(COL_PROCESS, Qt.SortOrder.AscendingOrder)
        table.selectRow(0)
        self.assertEqual(int(table.item(0, COL_ID).text()), target.id)

    def test_sorting_paused_during_requirement_refresh(self) -> None:
        first = legal_requirement_service.create_requirement(title="Beta")
        second = legal_requirement_service.create_requirement(title="Alfa")
        table = LegalRequirementTable()
        table.load_requirements([first, second])
        table.sortItems(COL_PROCESS, Qt.SortOrder.AscendingOrder)

        with sorting_paused(table):
            table.setRowCount(0)
            self.assertFalse(table.isSortingEnabled())
        self.assertTrue(table.isSortingEnabled())


if __name__ == "__main__":
    unittest.main()
