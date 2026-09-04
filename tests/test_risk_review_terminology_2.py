"""RISK-REVIEW-TERMINOLOGY-2: uživatelské názvy Revize posouzení rizik."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import inspect as sa_inspect, select

_TMP = Path(tempfile.mkdtemp(prefix="risk-review-terminology-2-"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from PySide6.QtWidgets import QApplication, QFormLayout, QMessageBox

    from core.database.session import get_session
    from core.models.attachment import Attachment
    from core.services.attachment_service import attachment_service
    from core.shared.task_source_display import task_source_label, task_source_short_label
    from moduly.nastaveni.constants.workplace_hierarchy_constants import (
        WORKPLACE_ITEM_TYPE_OPERATION,
        WORKPLACE_ITEM_TYPE_WORKPLACE,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.rizeni_rizik.constants import (
        ENTITY_RISK_MEASURE_REVIEW_ITEM,
        HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        RISK_MEASURE_REVIEW_CHECKLIST_TITLE,
        RISK_MEASURE_REVIEW_DIALOG_TITLE,
        RISK_MEASURE_REVIEW_EXECUTE_DIALOG_TITLE,
        RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
        RISK_MEASURE_REVIEW_ITEM_RESOLUTION_MEASURE_REVISION,
        RISK_MEASURE_REVIEW_NEW_BUTTON,
        RISK_MEASURE_REVIEW_PRINT_BUTTON,
        RISK_MEASURE_REVIEW_PRINT_DIALOG_TITLE,
        RISK_MEASURE_REVIEW_PRINT_EMPTY,
        RISK_MEASURE_REVIEW_PRINT_FAILED,
        RISK_MEASURE_REVIEW_TAB_TITLE,
        RISK_MEASURE_REVIEW_TASKS_TITLE,
        RISK_SEVERITY_MODERATE,
    )
    from moduly.rizeni_rizik.modely.hazard_event import HazardEvent
    from moduly.rizeni_rizik.modely.hazard_identification import HazardIdentification
    from moduly.rizeni_rizik.modely.hazard_inventory_item import HazardInventoryItem
    from moduly.rizeni_rizik.modely.hazard_required_measure import HazardRequiredMeasure
    from moduly.rizeni_rizik.modely.hazard_risk_assessment import HazardRiskAssessment
    from moduly.rizeni_rizik.modely.hazard_risk_assessment_exposed_group import (
        HazardRiskAssessmentExposedGroup,
    )
    from moduly.rizeni_rizik.modely.risk_measure_review import RiskMeasureReview
    from moduly.rizeni_rizik.modely.risk_measure_review_item import RiskMeasureReviewItem
    from moduly.rizeni_rizik.sluzby.hazard_event_service import hazard_event_service
    from moduly.rizeni_rizik.sluzby.hazard_identification_service import (
        hazard_identification_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_inventory_item_service import (
        hazard_inventory_item_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_required_measure_service import (
        hazard_required_measure_service,
    )
    from moduly.rizeni_rizik.sluzby.hazard_risk_assessment_service import (
        hazard_risk_assessment_service,
    )
    from moduly.rizeni_rizik.sluzby.risk_measure_review_checklist_export_service import (
        risk_measure_review_checklist_export_service,
    )
    from moduly.rizeni_rizik.sluzby.risk_measure_review_service import (
        risk_measure_review_service,
    )
    from moduly.rizeni_rizik.ui.risk_measure_review_dialog import RiskMeasureReviewDialog
    from moduly.rizeni_rizik.ui.risk_measure_review_execution_dialog import (
        RiskMeasureReviewExecutionDialog,
    )
    from moduly.rizeni_rizik.ui.risk_measure_reviews_tab import RiskMeasureReviewsTab
    from moduly.rizeni_rizik.ui.rizeni_rizik_page import RizeniRizikPage
    from moduly.ukoly.modely.task import Task
    from tests.rizeni_rizik_test_helpers import ensure_exposed_group


def _model_rows(model) -> list[tuple]:
    mapper = sa_inspect(model)
    columns = [column.key for column in mapper.columns]
    with get_session() as session:
        records = session.execute(select(model)).scalars().all()
        return sorted(
            tuple(getattr(record, column) for column in columns)
            for record in records
        )


class RiskReviewTerminology2TestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        from sqlalchemy import delete

        with get_session() as session:
            session.execute(delete(Task))
            session.execute(delete(Attachment))
            session.execute(delete(RiskMeasureReviewItem))
            session.execute(delete(RiskMeasureReview))
            session.execute(delete(HazardRequiredMeasure))
            session.execute(delete(HazardRiskAssessmentExposedGroup))
            session.execute(delete(HazardRiskAssessment))
            session.execute(delete(HazardEvent))
            session.execute(delete(HazardInventoryItem))
            session.execute(delete(HazardIdentification))
            session.commit()

        self.operation = settings_service.save_workplace(
            name="Provoz Term2",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.workplace = settings_service.save_workplace(
            name="Dílna Term2",
            item_type=WORKPLACE_ITEM_TYPE_WORKPLACE,
            parent_id=self.operation.id,
        )
        self.empty_operation = settings_service.save_workplace(
            name="Prázdný provoz Term2",
            item_type=WORKPLACE_ITEM_TYPE_OPERATION,
        )
        self.reviewer = settings_service.save_worker(
            first_name="Eva",
            last_name="Revizní",
        )
        self.group = ensure_exposed_group("Skupina Term2")
        self.measure = self._create_measure("Jsou kryty na místě?")
        self.review = risk_measure_review_service.create_review(
            review_date=date(2026, 9, 4),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
            note="Historická poznámka revize",
        )

    def _create_measure(self, title: str) -> HazardRequiredMeasure:
        identification = hazard_identification_service.create_identification(
            operation_id=self.operation.id,
            workplace_id=self.workplace.id,
        )
        item = hazard_inventory_item_service.create_item(
            hazard_identification_id=identification.id,
            name="Lis Term2",
            category=HAZARD_INVENTORY_CATEGORY_EQUIPMENT,
        )
        event = hazard_event_service.create_event(
            hazard_identification_id=identification.id,
            inventory_item_id=item.id,
            name="Přivření Term2",
        )
        assessment = hazard_risk_assessment_service.create_assessment(
            hazard_identification_id=identification.id,
            hazard_event_id=event.id,
            exposed_group_ids=[self.group.id],
            severity=RISK_SEVERITY_MODERATE,
        )
        return hazard_required_measure_service.create_measure(
            hazard_identification_id=identification.id,
            hazard_risk_assessment_id=assessment.id,
            title=title,
        )

    def test_main_tab_title(self) -> None:
        self.assertEqual(RISK_MEASURE_REVIEW_TAB_TITLE, "Revize posouzení rizik")
        page = RizeniRizikPage()
        titles = [page.tabs.tabText(index) for index in range(page.tabs.count())]
        self.assertEqual(titles[2], "Revize posouzení rizik")

    def test_list_buttons(self) -> None:
        self.assertEqual(RISK_MEASURE_REVIEW_NEW_BUTTON, "Nová revize")
        self.assertEqual(RISK_MEASURE_REVIEW_EXECUTE_DIALOG_TITLE, "Provést revizi")
        tab = RiskMeasureReviewsTab()
        self.assertEqual(tab.new_btn.text(), "Nová revize")
        self.assertEqual(tab.execute_btn.text(), "Provést revizi")
        self.assertEqual(
            tab.text_filter.search_edit.placeholderText(),
            "🔍 Hledat revizi...",
        )

    def test_execute_dialog_title(self) -> None:
        dialog = RiskMeasureReviewExecutionDialog(review=self.review)
        self.assertTrue(dialog.windowTitle().startswith("Provést revizi"))
        self.assertIn(self.review.review_number, dialog.windowTitle())
        header = RiskMeasureReviewDialog(review=self.review)
        self.assertEqual(header.windowTitle(), "Revize posouzení rizik")
        self.assertEqual(RISK_MEASURE_REVIEW_DIALOG_TITLE, "Revize posouzení rizik")
        form = header.findChild(QFormLayout)
        labels = []
        for row in range(form.rowCount()):
            item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if item is not None and item.widget() is not None:
                labels.append(item.widget().text())
        self.assertIn("Číslo revize:", labels)
        dialog._editor.mark_clean()
        dialog.close()
        header._editor.mark_clean()
        header.close()

    def test_control_questions_tab(self) -> None:
        self.assertEqual(RISK_MEASURE_REVIEW_CHECKLIST_TITLE, "Kontrolní otázky")
        dialog = RiskMeasureReviewExecutionDialog(review=self.review)
        titles = [dialog.tabs.tabText(index) for index in range(dialog.tabs.count())]
        self.assertEqual(titles[0], "Kontrolní otázky")
        self.assertEqual(titles[1], RISK_MEASURE_REVIEW_TASKS_TITLE)
        point = dialog.checklist.points[0]
        self.assertEqual(point.compliant_radio.text(), "Vyhovuje")
        self.assertEqual(point.non_compliant_radio.text(), "Nevyhovuje")
        self.assertNotEqual(
            RISK_MEASURE_REVIEW_ITEM_RESOLUTION_MEASURE_REVISION,
            "not_applicable",
        )
        self.assertNotIn("Netýká se", [point.compliant_radio.text(), point.non_compliant_radio.text()])
        dialog._editor.mark_clean()
        dialog.close()

    def test_print_button_and_messages(self) -> None:
        self.assertEqual(RISK_MEASURE_REVIEW_PRINT_BUTTON, "Vytisknout kontrolní otázky")
        self.assertEqual(
            RISK_MEASURE_REVIEW_PRINT_DIALOG_TITLE,
            "Kontrolní otázky pro revizi posouzení rizik",
        )
        self.assertEqual(
            RISK_MEASURE_REVIEW_PRINT_FAILED,
            "Seznam kontrolních otázek se nepodařilo vytvořit.",
        )
        self.assertEqual(
            RISK_MEASURE_REVIEW_PRINT_EMPTY,
            "Revize neobsahuje žádné kontrolní otázky.",
        )
        dialog = RiskMeasureReviewExecutionDialog(review=self.review)
        self.assertEqual(dialog.print_btn.text(), "Vytisknout kontrolní otázky")
        with patch.object(
            risk_measure_review_checklist_export_service,
            "open_for_review",
            side_effect=RuntimeError("chyba šablony"),
        ):
            with patch.object(QMessageBox, "warning") as warning:
                dialog._print_checklist()
        warning.assert_called_once()
        self.assertEqual(warning.call_args[0][1], "Vytisknout kontrolní otázky")
        self.assertIn(
            "Seznam kontrolních otázek se nepodařilo vytvořit.",
            warning.call_args[0][2],
        )

        empty = risk_measure_review_service.create_review(
            review_date=date.today(),
            reviewer_person_id=self.reviewer.id,
            operation_id=self.empty_operation.id,
        )
        path = risk_measure_review_checklist_export_service.generate_for_review(empty)
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("content.xml").decode("utf-8")
        self.assertIn("Revize neobsahuje žádné kontrolní otázky.", xml)
        dialog._editor.mark_clean()
        dialog.close()

    def test_odt_title(self) -> None:
        template = Path(
            "moduly/rizeni_rizik/templates/exporty/PrezkoumaniOpatreniChecklist.odt"
        )
        self.assertEqual(
            risk_measure_review_checklist_export_service.TEMPLATE_NAME,
            "PrezkoumaniOpatreniChecklist.odt",
        )
        with zipfile.ZipFile(template) as archive:
            xml = archive.read("content.xml").decode("utf-8")
        self.assertIn("Kontrolní otázky pro revizi posouzení rizik", xml)
        self.assertNotIn("Checklist přezkoumání opatření", xml)

        with patch(
            "moduly.rizeni_rizik.sluzby.risk_measure_review_checklist_export_service.open_export_file"
        ) as open_export:
            path = risk_measure_review_checklist_export_service.open_for_review(self.review)
        open_export.assert_called_once()
        self.assertEqual(
            open_export.call_args.kwargs["title"],
            "Kontrolní otázky pro revizi posouzení rizik",
        )
        with zipfile.ZipFile(path) as archive:
            rendered = archive.read("content.xml").decode("utf-8")
        self.assertIn("Kontrolní otázky pro revizi posouzení rizik", rendered)
        self.assertIn("Vyhovuje", rendered)
        self.assertIn("Nevyhovuje", rendered)
        self.assertNotIn("Netýká se", rendered)

    def test_open_and_print_existing_review_does_not_change_db(self) -> None:
        rows = risk_measure_review_service.list_checklist_rows(self.review.id)
        item_id = rows[0].item_id
        risk_measure_review_service.update_review(
            self.review.id,
            review_date=self.review.review_date,
            reviewer_person_id=self.review.reviewer_person_id,
            operation_id=self.review.operation_id,
            workplace_id=self.review.workplace_id,
            note=self.review.note or "",
            checklist_updates=[
                {
                    "item_id": item_id,
                    "result": RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
                    "note": "Historický výsledek",
                    "has_photo": True,
                }
            ],
        )
        photo = _TMP / "historie.jpg"
        photo.write_bytes(
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xd9"
        )
        attachment_service.add_file(
            ENTITY_RISK_MEASURE_REVIEW_ITEM,
            item_id,
            str(photo),
        )
        task = risk_measure_review_service.create_task_for_review(
            self.review.id,
            title="Doplnit kryt po revizi",
            description="Navázaný historický úkol",
        )
        self.assertEqual(
            task_source_label(task),
            f"Revize posouzení rizik {self.review.review_number}",
        )
        self.assertEqual(task_source_short_label(task), "Revize")

        before = {
            "reviews": _model_rows(RiskMeasureReview),
            "items": _model_rows(RiskMeasureReviewItem),
            "attachments": _model_rows(Attachment),
            "tasks": _model_rows(Task),
        }

        loaded = risk_measure_review_service.get_by_id(self.review.id)
        dialog = RiskMeasureReviewExecutionDialog(review=loaded)
        self.assertEqual(dialog.checklist.point_count(), 1)
        self.assertEqual(dialog.checklist.points[0].note_edit.text(), "Historický výsledek")
        self.assertTrue(dialog.checklist.points[0].compliant_radio.isChecked())
        self.assertIn("(1)", dialog.checklist.points[0].photo_btn.text())
        self.assertEqual(dialog.tasks.table.rowCount(), 1)
        self.assertIn("Doplnit kryt po revizi", dialog.tasks.table.item(0, 1).text())

        with patch(
            "moduly.rizeni_rizik.sluzby.risk_measure_review_checklist_export_service.open_export_file"
        ):
            dialog._print_checklist()
        dialog._editor.mark_clean()
        dialog.close()

        after = {
            "reviews": _model_rows(RiskMeasureReview),
            "items": _model_rows(RiskMeasureReviewItem),
            "attachments": _model_rows(Attachment),
            "tasks": _model_rows(Task),
        }
        self.assertEqual(before, after)

        rows_after = risk_measure_review_service.list_checklist_rows(self.review.id)
        self.assertEqual(rows_after[0].result, RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT)
        self.assertEqual(rows_after[0].note, "Historický výsledek")
        self.assertGreaterEqual(rows_after[0].photo_count, 1)
        self.assertEqual(
            len(attachment_service.get_for_entity(ENTITY_RISK_MEASURE_REVIEW_ITEM, item_id)),
            1,
        )
        tasks_after = risk_measure_review_service.get_tasks_for_review(self.review.id)
        self.assertEqual([item.title for item in tasks_after], ["Doplnit kryt po revizi"])


if __name__ == "__main__":
    unittest.main()
