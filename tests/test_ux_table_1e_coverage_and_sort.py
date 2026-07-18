"""UX-TABLE-1e – pokrytí zbývajících pracovních tabulek + kontrola setSortingEnabled."""

from __future__ import annotations

import ast
import importlib
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt

_TMP = Path(tempfile.mkdtemp())
_PROJECT_ROOT = Path(__file__).resolve().parents[1]

_ALLOWED_SET_SORTING_ENABLED_TRUE = frozenset(
    {
        "core/widgets/typed_table_sort.py",
    }
)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.attention_item import AttentionItem, ITEM_TYPE_TASK
    from core.dashboard.widget_upcoming_tasks import (
        COL_DUE,
        COL_TITLE,
        UpcomingTasksWidget,
    )
    from core.shared.constants import ENTITY_LEGAL_REQUIREMENT, ENTITY_TASK
    from core.shared.sluzby.entity_link_service import entity_link_service
    from core.shared.widgets.entity_links_widget import EntityLinksWidget
    from moduly.nastaveni.sluzby.exposed_group_service import exposed_group_service
    from moduly.nastaveni.sluzby.person_service import person_service
    from moduly.nastaveni.ui.exposed_groups_management_dialog import (
        ExposedGroupsManagementDialog,
    )
    from moduly.nastaveni.ui.nastaveni_page import NastaveniPage
    from moduly.pravni_pozadavky.sluzby.legal_requirement_service import (
        legal_requirement_service,
    )
    from moduly.pravni_pozadavky.ui.legal_requirement_hazard_catalog_sources_widget import (
        LegalRequirementHazardCatalogSourcesWidget,
    )
    from moduly.proverky.constants import (
        INSPECTION_STATUS_DOKONCENO,
        INSPECTION_STATUS_PLANOVANO,
        INSPECTION_STATUS_PROBIHA,
    )
    from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
    from moduly.proverky.ui.rocni_plan_dialog import RocniPlanDialog
    from moduly.rizeni_rizik.sluzby.hazard_catalog_legal_requirement_usage_service import (
        HazardCatalogSourceUsage,
    )
    from moduly.ukoly.sluzby.task_service import task_service


def _column_texts(table, column: int) -> list[str]:
    return [table.item(row, column).text() for row in range(table.rowCount())]


def _iter_python_sources():
    for base in ("core", "moduly"):
        root = _PROJECT_ROOT / base
        for path in root.rglob("*.py"):
            yield path.relative_to(_PROJECT_ROOT).as_posix(), path


def _calls_set_sorting_enabled_true(source: str) -> list[int]:
    tree = ast.parse(source)
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "setSortingEnabled":
            continue
        if len(node.args) != 1:
            continue
        arg = node.args[0]
        if isinstance(arg, ast.Constant) and arg.value is True:
            lines.append(getattr(node, "lineno", 0))
    return lines


class UxTable1eStaticSortingGuardTests(unittest.TestCase):
    def test_no_raw_set_sorting_enabled_true_outside_infrastructure(self) -> None:
        offenders: list[str] = []
        for rel, path in _iter_python_sources():
            if rel in _ALLOWED_SET_SORTING_ENABLED_TRUE:
                continue
            text = path.read_text(encoding="utf-8")
            if "setSortingEnabled" not in text:
                continue
            for line in _calls_set_sorting_enabled_true(text):
                offenders.append(f"{rel}:{line}")
        self.assertEqual(
            offenders,
            [],
            "Nalezeno setSortingEnabled(True) mimo enable_typed_sorting(): "
            + ", ".join(offenders),
        )


class UxTable1eNastaveniSortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_person_table_czech_sort_and_selection(self) -> None:
        a = person_service.create_person(
            first_name="Jan",
            last_name="Novák",
            organization="Chalupa",
        )
        b = person_service.create_person(
            first_name="Eva",
            last_name="Svobodová",
            organization="Cibule",
        )
        c = person_service.create_person(
            first_name="Petr",
            last_name="Dvořák",
            organization="Hrášek",
        )

        page = NastaveniPage()
        page.person_filter.setCurrentText("Vše")
        page.refresh_persons()
        table = page.person_table
        table.sortItems(2, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, 2)[:3], ["Cibule", "Hrášek", "Chalupa"])
        table.selectRow(0)
        self.assertEqual(int(table.item(0, 0).text()), b.id)
        self.assertIn(a.id, [int(table.item(row, 0).text()) for row in range(3)])
        self.assertIn(c.id, [int(table.item(row, 0).text()) for row in range(3)])

    def test_exposed_groups_dialog_active_bool_and_id(self) -> None:
        inactive = exposed_group_service.create_group(name="Beta", active=False)
        active = exposed_group_service.create_group(name="Alfa", active=True)

        dialog = ExposedGroupsManagementDialog()
        dialog.filter.setCurrentIndex(1)  # Všechny
        dialog.refresh()
        table = dialog.table
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(table.item(0, 0).text(), "Alfa")
        table.selectRow(0)
        self.assertEqual(int(table.item(0, 0).data(Qt.ItemDataRole.UserRole)), active.id)

        table.sortItems(2, Qt.SortOrder.AscendingOrder)
        self.assertEqual(table.item(0, 2).text(), "Ne")
        self.assertEqual(
            int(table.item(0, 0).data(Qt.ItemDataRole.UserRole)),
            inactive.id,
        )


class UxTable1eRocniPlanSortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        for inspection in bozp_inspection_service.get_all():
            bozp_inspection_service.delete_inspection(inspection.id)

    def test_month_date_status_and_correct_record(self) -> None:
        late = bozp_inspection_service.create_inspection(
            workplace_name="Chalupa",
            year=2026,
            planned_month=7,
            inspection_date=date(2026, 7, 15),
            started_at=date(2026, 7, 1),
            finished_at=date(2026, 7, 2),
        )
        early = bozp_inspection_service.create_inspection(
            workplace_name="Cibule",
            year=2026,
            planned_month=2,
            inspection_date=date(2026, 2, 10),
        )
        mid = bozp_inspection_service.create_inspection(
            workplace_name="Hrášek",
            year=2026,
            planned_month=4,
            inspection_date=date(2026, 4, 1),
            started_at=date(2026, 4, 1),
        )
        self.assertEqual(early.status, INSPECTION_STATUS_PLANOVANO)
        self.assertEqual(mid.status, INSPECTION_STATUS_PROBIHA)
        self.assertEqual(late.status, INSPECTION_STATUS_DOKONCENO)

        dialog = RocniPlanDialog(year=2026)
        table = dialog.table
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        ids = [
            int(table.item(row, 0).data(Qt.ItemDataRole.UserRole))
            for row in range(table.rowCount())
        ]
        self.assertEqual(ids, [early.id, mid.id, late.id])

        table.sortItems(3, Qt.SortOrder.AscendingOrder)
        status_ids = [
            int(table.item(row, 0).data(Qt.ItemDataRole.UserRole))
            for row in range(table.rowCount())
        ]
        self.assertEqual(status_ids, [early.id, mid.id, late.id])

        table.sortItems(1, Qt.SortOrder.AscendingOrder)
        table.selectRow(0)
        self.assertEqual(
            int(table.item(0, 0).data(Qt.ItemDataRole.UserRole)),
            early.id,
        )


class UxTable1eDashboardSortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_due_date_sort_and_open_identity(self) -> None:
        items = [
            AttentionItem(
                item_type=ITEM_TYPE_TASK,
                entity_id=10,
                title="Pozdě",
                due_date=date(2026, 7, 1),
                source_label="Úkoly",
                status="Aktivní",
                priority="Normální",
            ),
            AttentionItem(
                item_type=ITEM_TYPE_TASK,
                entity_id=20,
                title="Dříve",
                due_date=date(2026, 1, 5),
                source_label="Úkoly",
                status="Aktivní",
                priority="Vysoká",
            ),
            AttentionItem(
                item_type=ITEM_TYPE_TASK,
                entity_id=30,
                title="Střed",
                due_date=date(2026, 3, 15),
                source_label="Úkoly",
                status="Aktivní",
                priority="Nízká",
            ),
        ]
        widget = UpcomingTasksWidget()
        with patch(
            "core.dashboard.widget_upcoming_tasks.get_attention_items",
            return_value=items,
        ):
            widget.refresh()

        table = widget.table
        table.sortItems(COL_DUE, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, COL_TITLE), ["Dříve", "Střed", "Pozdě"])
        table.selectRow(0)
        selected = widget._selected_item()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.entity_id, 20)


class UxTable1eEntityLinksAndHazardSourcesSortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from core.shared.modely.entity_link import EntityLink
        from moduly.pravni_pozadavky.modely.legal_requirement import LegalRequirement
        from moduly.ukoly.modely.task import Task

        with get_session() as session:
            session.execute(delete(EntityLink))
            session.execute(delete(LegalRequirement))
            session.execute(delete(Task))
            session.commit()

    def test_entity_links_czech_sort_and_id(self) -> None:
        requirement = legal_requirement_service.create_requirement(title="Proces")
        task_a = task_service.create_task(title="Úkol A")
        task_b = task_service.create_task(title="Úkol B")
        link_b = entity_link_service.create(
            source_type=ENTITY_LEGAL_REQUIREMENT,
            source_id=requirement.id,
            target_type=ENTITY_TASK,
            target_id=task_b.id,
            note="Cibule",
        )
        link_a = entity_link_service.create(
            source_type=ENTITY_LEGAL_REQUIREMENT,
            source_id=requirement.id,
            target_type=ENTITY_TASK,
            target_id=task_a.id,
            note="Chalupa",
        )

        widget = EntityLinksWidget(ENTITY_LEGAL_REQUIREMENT, requirement.id)
        table = widget.table
        self.assertIsNotNone(table)
        table.sortItems(4, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, 4), ["Cibule", "Chalupa"])
        table.selectRow(0)
        self.assertEqual(int(table.item(0, 0).text()), link_b.id)
        self.assertIn(link_a.id, [int(table.item(row, 0).text()) for row in range(table.rowCount())])

    def test_hazard_catalog_sources_name_and_active(self) -> None:
        sources = (
            HazardCatalogSourceUsage(
                template_id=2,
                name="Chalupa",
                category_label="A",
                version_number=1,
                active=False,
            ),
            HazardCatalogSourceUsage(
                template_id=1,
                name="Cibule",
                category_label="B",
                version_number=3,
                active=True,
            ),
        )
        widget = LegalRequirementHazardCatalogSourcesWidget(requirement_id=1)
        with patch.object(widget, "_load_sources", return_value=sources):
            widget.refresh()

        table = widget._table
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, 0), ["Cibule", "Chalupa"])
        table.selectRow(0)
        self.assertEqual(int(table.item(0, 0).data(Qt.ItemDataRole.UserRole)), 1)

        table.sortItems(3, Qt.SortOrder.AscendingOrder)
        self.assertEqual(table.item(0, 3).text(), "Ne")
        self.assertEqual(int(table.item(0, 0).data(Qt.ItemDataRole.UserRole)), 2)


if __name__ == "__main__":
    unittest.main()
