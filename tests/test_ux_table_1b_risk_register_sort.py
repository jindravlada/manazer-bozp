"""UX-TABLE-1b – typované řazení tabulek Registru rizik."""

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

    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        COL_ID,
        COL_STARTED_AT,
        COL_STATUS,
        COL_WORKPLACE,
        HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
        HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        HAZARD_IDENTIFICATION_STATUS_DRAFT,
        HAZARD_IDENTIFICATION_STATUS_IN_PROGRESS,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        INVENTORY_COL_ID,
        INVENTORY_COL_NAME,
        RISK_ASSESSMENT_COL_COMPLETED_AT,
        RISK_ASSESSMENT_COL_ID,
        RISK_ASSESSMENT_STATUS_COMPLETED,
        RISK_ASSESSMENT_STATUS_DRAFT,
        RISK_LIST_FILTER_ALL,
        RISK_SEVERITY_MINOR,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.constants_library import (
        HAZARD_LIBRARY_COL_ACTIVE,
        HAZARD_LIBRARY_COL_ID,
        HAZARD_LIBRARY_COL_NAME,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_library_template import HazardLibraryTemplate
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
        hazard_library_template_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.ui.hazard_inventory_widget import HazardInventoryWidget
    from moduly.rizeni_rizik.ui.hazard_library_page import HazardLibraryPage
    from moduly.rizeni_rizik.ui.hazard_risk_assessments_widget import (
        HazardRiskAssessmentsWidget,
    )
    from moduly.rizeni_rizik.ui.rizeni_rizik_page import RizeniRizikPage
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


def _column_texts(table, column: int) -> list[str]:
    return [table.item(row, column).text() for row in range(table.rowCount())]


def _column_ids(table, column: int) -> list[int]:
    return [int(table.item(row, column).text()) for row in range(table.rowCount())]


class UxTable1bRiskRegisterSortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

        cls.operation = settings_service.save_workplace(
            name="Provoz UX-TABLE-1b",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        cls.workplace_cibule = settings_service.save_workplace(
            name="Cibule",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=cls.operation.id,
        )
        cls.workplace_hrasek = settings_service.save_workplace(
            name="Hrášek",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=cls.operation.id,
        )
        cls.workplace_chalupa = settings_service.save_workplace(
            name="Chalupa",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=cls.operation.id,
        )
        cls.group = ensure_exposed_group("Skupina UX-TABLE-1b")

    def setUp(self) -> None:
        from sqlalchemy import delete

        from core.database.session import get_session
        from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
            HazardRiskAssessmentExposedGroup,
        )

        with get_session() as session:
            session.execute(delete(HazardRiskAssessmentExposedGroup))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.execute(delete(HazardLibraryTemplate))
            session.commit()

    def _create_identification(
        self,
        *,
        workplace_id: int,
        started_at: date | None = None,
        status: str = HAZARD_IDENTIFICATION_STATUS_DRAFT,
    ):
        return hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=workplace_id,
            started_at=started_at,
            status=status,
        )

    def test_identifications_czech_text_sort(self) -> None:
        self._create_identification(workplace_id=self.workplace_chalupa.id)
        self._create_identification(workplace_id=self.workplace_cibule.id)
        self._create_identification(workplace_id=self.workplace_hrasek.id)

        page = RizeniRizikPage()
        table = page.identifications_tab.table
        table.sortItems(COL_WORKPLACE, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            _column_texts(table, COL_WORKPLACE),
            ["Cibule", "Hrášek", "Chalupa"],
        )
        table.sortItems(COL_WORKPLACE, Qt.SortOrder.DescendingOrder)
        self.assertEqual(
            _column_texts(table, COL_WORKPLACE),
            ["Chalupa", "Hrášek", "Cibule"],
        )

    def test_identifications_date_sort(self) -> None:
        mid = self._create_identification(
            workplace_id=self.workplace_cibule.id,
            started_at=date(2026, 3, 15),
        )
        early = self._create_identification(
            workplace_id=self.workplace_hrasek.id,
            started_at=date(2026, 1, 5),
        )
        late = self._create_identification(
            workplace_id=self.workplace_chalupa.id,
            started_at=date(2026, 7, 1),
        )

        page = RizeniRizikPage()
        table = page.identifications_tab.table
        table.sortItems(COL_STARTED_AT, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            _column_ids(table, COL_ID),
            [early.id, mid.id, late.id],
        )
        table.sortItems(COL_STARTED_AT, Qt.SortOrder.DescendingOrder)
        self.assertEqual(
            _column_ids(table, COL_ID),
            [late.id, mid.id, early.id],
        )

    def test_identifications_status_workflow_order(self) -> None:
        archived = self._create_identification(
            workplace_id=self.workplace_cibule.id,
            status=HAZARD_IDENTIFICATION_STATUS_ARCHIVED,
        )
        completed = self._create_identification(
            workplace_id=self.workplace_hrasek.id,
            status=HAZARD_IDENTIFICATION_STATUS_COMPLETED,
        )
        draft = self._create_identification(
            workplace_id=self.workplace_chalupa.id,
            status=HAZARD_IDENTIFICATION_STATUS_DRAFT,
        )
        in_progress = self._create_identification(
            workplace_id=self.workplace_cibule.id,
            status=HAZARD_IDENTIFICATION_STATUS_IN_PROGRESS,
        )

        page = RizeniRizikPage()
        table = page.identifications_tab.table
        table.sortItems(COL_STATUS, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            _column_texts(table, COL_STATUS),
            ["Rozpracováno", "Probíhá", "Uzavřeno", "Archivováno"],
        )
        self.assertEqual(
            _column_ids(table, COL_ID),
            [draft.id, in_progress.id, completed.id, archived.id],
        )

    def test_identifications_editor_opens_correct_record_after_sort(self) -> None:
        first = self._create_identification(workplace_id=self.workplace_chalupa.id)
        target = self._create_identification(workplace_id=self.workplace_cibule.id)
        self._create_identification(workplace_id=self.workplace_hrasek.id)

        page = RizeniRizikPage()
        table = page.identifications_tab.table
        table.sortItems(COL_WORKPLACE, Qt.SortOrder.AscendingOrder)
        # Po českém řazení je Cibule první.
        table.selectRow(0)
        self.assertEqual(table.selected_identification_id(), target.id)
        self.assertNotEqual(table.selected_identification_id(), first.id)

    def test_identifications_refresh_keeps_active_sort(self) -> None:
        self._create_identification(workplace_id=self.workplace_chalupa.id)
        self._create_identification(workplace_id=self.workplace_cibule.id)

        page = RizeniRizikPage()
        table = page.identifications_tab.table
        table.sortItems(COL_WORKPLACE, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, COL_WORKPLACE)[0], "Cibule")

        self._create_identification(workplace_id=self.workplace_hrasek.id)
        page.identifications_tab.refresh()
        self.assertEqual(
            _column_texts(table, COL_WORKPLACE),
            ["Cibule", "Hrášek", "Chalupa"],
        )

    def test_catalog_czech_names_including_ch(self) -> None:
        hazard_library_template_service.create_template(name="Chalupa")
        hazard_library_template_service.create_template(name="Cibule")
        hazard_library_template_service.create_template(name="Hrášek")

        page = HazardLibraryPage()
        table = page.table
        table.sortItems(HAZARD_LIBRARY_COL_NAME, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            _column_texts(table, HAZARD_LIBRARY_COL_NAME),
            ["Cibule", "Hrášek", "Chalupa"],
        )

    def test_catalog_active_boolean_sort(self) -> None:
        inactive = hazard_library_template_service.create_template(
            name="Neaktivní",
            active=False,
        )
        active = hazard_library_template_service.create_template(
            name="Aktivní",
            active=True,
        )

        page = HazardLibraryPage()
        page.active_filter.setCurrentIndex(page.active_filter.findData(RISK_LIST_FILTER_ALL))
        table = page.table
        table.sortItems(HAZARD_LIBRARY_COL_ACTIVE, Qt.SortOrder.AscendingOrder)
        self.assertEqual(
            _column_texts(table, HAZARD_LIBRARY_COL_ACTIVE),
            ["Ne", "Ano"],
        )
        self.assertEqual(
            _column_ids(table, HAZARD_LIBRARY_COL_ID),
            [inactive.id, active.id],
        )
        table.sortItems(HAZARD_LIBRARY_COL_ACTIVE, Qt.SortOrder.DescendingOrder)
        self.assertEqual(
            _column_texts(table, HAZARD_LIBRARY_COL_ACTIVE),
            ["Ano", "Ne"],
        )

    def test_inventory_row_data_stays_bound_after_sort(self) -> None:
        identification = self._create_identification(
            workplace_id=self.workplace_cibule.id,
        )
        zebra = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Zebra",
        )
        auto = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Auto",
        )

        widget = HazardInventoryWidget()
        self._select_equipment_category(widget)
        widget.set_identification(
            identification.id,
            read_only=False,
            identification_status=identification.status,
        )
        table = widget.table
        self.assertEqual(table.rowCount(), 2)

        table.sortItems(INVENTORY_COL_NAME, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, INVENTORY_COL_NAME)[0], "Auto")
        self.assertEqual(int(table.item(0, INVENTORY_COL_ID).text()), auto.id)
        self.assertEqual(int(table.item(1, INVENTORY_COL_ID).text()), zebra.id)

        table.selectRow(0)
        selected = widget._selected_item()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, auto.id)
        self.assertEqual(selected.name, "Auto")

        table.sortItems(INVENTORY_COL_NAME, Qt.SortOrder.DescendingOrder)
        table.selectRow(0)
        selected = widget._selected_item()
        self.assertEqual(selected.id, zebra.id)
        self.assertEqual(selected.name, "Zebra")

    def test_assessments_empty_values_always_last(self) -> None:
        identification = self._create_identification(
            workplace_id=self.workplace_cibule.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
            name="Jeřáb",
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="Pád břemene",
        )
        completed = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            exposed_group_ids=[self.group.id],
            severity=RISK_SEVERITY_MODERATE,
            assessment_status=RISK_ASSESSMENT_STATUS_COMPLETED,
        )
        group_b = ensure_exposed_group("Skupina B UX-TABLE-1b")
        draft = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            exposed_group_ids=[group_b.id],
            severity=RISK_SEVERITY_MINOR,
            assessment_status=RISK_ASSESSMENT_STATUS_DRAFT,
        )
        self.assertIsNotNone(completed.completed_at)
        self.assertIsNone(draft.completed_at)

        widget = HazardRiskAssessmentsWidget()
        widget.set_identification(identification.id, read_only=False)
        table = widget.table
        self.assertEqual(table.rowCount(), 2)

        table.sortItems(RISK_ASSESSMENT_COL_COMPLETED_AT, Qt.SortOrder.AscendingOrder)
        texts = _column_texts(table, RISK_ASSESSMENT_COL_COMPLETED_AT)
        self.assertTrue(texts[0])
        self.assertEqual(texts[1], "")
        self.assertEqual(int(table.item(0, RISK_ASSESSMENT_COL_ID).text()), completed.id)

        table.sortItems(RISK_ASSESSMENT_COL_COMPLETED_AT, Qt.SortOrder.DescendingOrder)
        texts = _column_texts(table, RISK_ASSESSMENT_COL_COMPLETED_AT)
        self.assertTrue(texts[0])
        self.assertEqual(texts[1], "")
        self.assertEqual(int(table.item(0, RISK_ASSESSMENT_COL_ID).text()), completed.id)

        table.selectRow(0)
        selected = widget._selected_assessment()
        self.assertEqual(selected.id, completed.id)

    def test_sorting_paused_helper_restores_indicator(self) -> None:
        from core.widgets.typed_table_sort import (
            create_typed_item,
            enable_typed_sorting,
            sorting_paused,
            typed_text,
        )
        from PySide6.QtWidgets import QTableWidget

        table = QTableWidget(0, 1)
        enable_typed_sorting(table)
        table.setSortingEnabled(False)
        table.setRowCount(2)
        table.setItem(0, 0, create_typed_item("B", typed_text("B"), stable_id=2))
        table.setItem(1, 0, create_typed_item("A", typed_text("A"), stable_id=1))
        table.setSortingEnabled(True)
        table.sortItems(0, Qt.SortOrder.AscendingOrder)
        self.assertEqual(_column_texts(table, 0), ["A", "B"])

        with sorting_paused(table):
            table.setRowCount(3)
            table.setItem(0, 0, create_typed_item("C", typed_text("C"), stable_id=3))
            table.setItem(1, 0, create_typed_item("A", typed_text("A"), stable_id=1))
            table.setItem(2, 0, create_typed_item("B", typed_text("B"), stable_id=2))

        self.assertEqual(_column_texts(table, 0), ["A", "B", "C"])
        self.assertTrue(table.isSortingEnabled())

    @staticmethod
    def _select_equipment_category(widget: HazardInventoryWidget) -> None:
        for row in range(widget.category_list.count()):
            item = widget.category_list.item(row)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == (
                HAZARD_INVENTORY_CATEGORY_EQUIPMENT
            ):
                widget.category_list.setCurrentRow(row)
                return
        raise AssertionError("Kategorie equipment nebyla nalezena")


if __name__ == "__main__":
    unittest.main()
