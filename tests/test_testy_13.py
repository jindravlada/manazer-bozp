"""TESTY-13: souhrn přezkoušení zaměstnanců na dashboardu."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QShowEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from sqlalchemy import delete

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="testy-13-"))
TODAY = date(2026, 6, 15)

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.database.session import get_session
    from core.dashboard.widget_exam_retraining import (
        LABEL_EXPIRED,
        LABEL_EXPIRING,
        LABEL_UNFINISHED,
        LABEL_VALID,
        UNFINISHED_TEXT,
        ExamRetrainingWidget,
        is_testy_module_enabled,
    )
    from core.modules.module_definition import ModuleDefinition
    from core.modules.module_manager import ModuleManager
    from core.theme.status_colors import (
        STATUS_DONE_TEXT,
        STATUS_MISSING_TEXT,
        STATUS_ORANGE_TEXT,
    )
    from core.windows.main_window import MainWindow
    from moduly.dashboard.ui.dashboard_page import DashboardPage
    from moduly.nastaveni.sluzby.responsibility_role_service import (
        responsibility_role_service,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.testy.constants import (
        AGENDA_EXAM_VALIDITY,
        EXAM_STATUS_CANCELLED,
        EXAM_STATUS_COMPLETED,
        EXAM_STATUS_PREPARED,
        EXAM_STATUS_STARTED,
        EXAMINER_MODE_NONE,
        MODULE_KEY,
        VALIDITY_UNIT_YEARS,
        WRITTEN_RESULT_FAILED,
        WRITTEN_RESULT_PASSED,
    )
    from moduly.testy.modely.test_definition import TestDefinition
    from moduly.testy.modely.test_definition_oral_topic import TestDefinitionOralTopic
    from moduly.testy.modely.test_definition_written_topic import (
        TestDefinitionWrittenTopic,
    )
    from moduly.testy.modely.test_employee import TestEmployee
    from moduly.testy.modely.test_employee_role import TestEmployeeRole
    from moduly.testy.modely.test_exam import TestExam
    from moduly.testy.modely.test_exam_examiner import TestExamExaminer
    from moduly.testy.modely.test_exam_oral_question import TestExamOralQuestion
    from moduly.testy.modely.test_exam_validity_tracking import TestExamValidityTracking
    from moduly.testy.modely.test_exam_written_answer import TestExamWrittenAnswer
    from moduly.testy.modely.test_exam_written_choice import TestExamWrittenChoice
    from moduly.testy.modely.test_exam_written_question import TestExamWrittenQuestion
    from moduly.testy.sluzby.exam_validity_service import exam_validity_service
    from moduly.testy.sluzby.test_definition_service import test_definition_service
    from moduly.testy.sluzby.test_employee_service import test_employee_service


def _wipe() -> None:
    with get_session() as session:
        session.execute(delete(TestExamWrittenChoice))
        session.execute(delete(TestExamWrittenAnswer))
        session.execute(delete(TestExamWrittenQuestion))
        session.execute(delete(TestExamOralQuestion))
        session.execute(delete(TestExamExaminer))
        session.execute(delete(TestExam))
        session.execute(delete(TestExamValidityTracking))
        session.execute(delete(TestDefinitionWrittenTopic))
        session.execute(delete(TestDefinitionOralTopic))
        session.execute(delete(TestDefinition))
        session.execute(delete(TestEmployeeRole))
        session.execute(delete(TestEmployee))
        session.commit()


class _ExamData:
    def setUp(self) -> None:
        _wipe()
        self.workplace = settings_service.save_workplace(name="Hala Sever")
        self.role = responsibility_role_service.create_role(name="Mistr souhrnu")
        self.tracked_valid = self._employee("00100", "Jan", "Novák")
        self.boundary_valid = self._employee("00200", "Eva", "Malá")
        self.inactive_test_employee = self._employee("00300", "Petr", "Svoboda")
        self.expiring_employee = self._employee("00400", "Iva", "Dvořáková")
        self.expired_employee = self._employee("00500", "Adam", "Černý")
        self.untracked = self._employee("00600", "Lucie", "Veselá")
        self.prepared_only = self._employee("00700", "Karel", "Horák")
        self.failed_only = self._employee("00800", "Nina", "Králová")
        self.inactive_employee = self._employee("00900", "Oldřich", "Němec")
        self.cancelled_only = self._employee("01000", "Tereza", "Pokorná")
        self.active_test = self._definition("BOZP")
        self.inactive_test = self._definition("První pomoc")

        self._success(self.tracked_valid, self.active_test, date(2027, 1, 1))
        self._exam(self.tracked_valid, self.active_test, status=EXAM_STATUS_PREPARED)
        self._success(self.boundary_valid, self.active_test, TODAY + timedelta(days=31))
        self._success(self.inactive_test_employee, self.inactive_test, date(2027, 3, 1))
        test_definition_service.deactivate(self.inactive_test.id)
        self._success(self.expiring_employee, self.active_test, TODAY + timedelta(days=30))
        self._success(self.expired_employee, self.active_test, TODAY - timedelta(days=1))
        self._success(self.untracked, self.active_test, date(2027, 1, 1))
        self._exam(self.untracked, self.active_test, status=EXAM_STATUS_PREPARED)
        self._exam(self.untracked, self.active_test, status=EXAM_STATUS_PREPARED)
        self._exam(
            self.untracked,
            self.active_test,
            status=EXAM_STATUS_STARTED,
            started_at=datetime(2026, 6, 15, 8, 0),
        )
        exam_validity_service.stop_tracking(self.untracked.id, self.active_test.id)
        self._exam(self.prepared_only, self.active_test, status=EXAM_STATUS_PREPARED)
        self._exam(
            self.failed_only,
            self.active_test,
            status=EXAM_STATUS_COMPLETED,
            valid_until=date(2027, 1, 1),
            finished_at=datetime(2026, 6, 1, 9, 0),
            result=WRITTEN_RESULT_FAILED,
        )
        self._success(self.inactive_employee, self.active_test, date(2027, 1, 1))
        self._exam(self.inactive_employee, self.active_test, status=EXAM_STATUS_PREPARED)
        test_employee_service.deactivate(self.inactive_employee.id)
        self._exam(self.cancelled_only, self.active_test, status=EXAM_STATUS_CANCELLED)

    def _employee(self, number, first, last):
        return test_employee_service.create_employee(
            personal_number=number,
            first_name=first,
            last_name=last,
            workplace_id=self.workplace.id,
            responsibility_role_ids=[self.role.id],
        )

    def _definition(self, name: str) -> TestDefinition:
        test = TestDefinition(
            name=name,
            description="",
            active=True,
            uses_written=False,
            uses_oral=True,
            allowed_wrong_answers=0,
            seconds_per_question=30,
            examiner_mode=EXAMINER_MODE_NONE,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
        )
        with get_session() as session:
            session.add(test)
            session.commit()
            session.refresh(test)
            session.expunge(test)
        return test

    def _success(self, employee, test, valid_until: date) -> TestExam:
        return self._exam(
            employee,
            test,
            status=EXAM_STATUS_COMPLETED,
            valid_until=valid_until,
            finished_at=datetime(2026, 1, 10, 9, 0),
            result=WRITTEN_RESULT_PASSED,
        )

    def _exam(
        self,
        employee,
        test,
        *,
        status: str,
        valid_until: date | None = None,
        finished_at: datetime | None = None,
        started_at: datetime | None = None,
        result: str | None = None,
    ) -> TestExam:
        exam_day = finished_at.date() if finished_at is not None else TODAY
        exam = TestExam(
            employee_id=employee.id,
            test_definition_id=test.id,
            exam_date=exam_day,
            valid_until=valid_until if valid_until is not None else exam_day,
            status=status,
            examiner_mode=EXAMINER_MODE_NONE,
            employee_personal_number=employee.personal_number,
            employee_first_name=employee.first_name,
            employee_last_name=employee.last_name,
            employee_display_name=employee.display_name,
            employee_workplace_name=self.workplace.name,
            test_name=test.name,
            validity_value=1,
            validity_unit=VALIDITY_UNIT_YEARS,
            written_started_at=started_at,
            written_finished_at=finished_at,
            exam_result=result,
        )
        with get_session() as session:
            session.add(exam)
            session.commit()
            session.refresh(exam)
            session.expunge(exam)
        return exam


class ExamRetrainingSummaryTests(_ExamData, unittest.TestCase):
    def test_counts_follow_validity_tracking_and_active_employees(self) -> None:
        summary = exam_validity_service.retraining_summary(today=TODAY)
        self.assertEqual(summary.valid_count, 3)
        self.assertEqual(summary.expiring_count, 1)
        self.assertEqual(summary.expired_count, 1)
        self.assertEqual(summary.unfinished_count, 5)

    def test_day_change_reclassifies_without_new_rules(self) -> None:
        later = TODAY + timedelta(days=40)
        summary = exam_validity_service.retraining_summary(today=later)
        self.assertEqual(summary.valid_count, 2)
        self.assertEqual(summary.expiring_count, 0)
        self.assertEqual(summary.expired_count, 3)
        self.assertEqual(summary.unfinished_count, 5)


class ExamRetrainingDashboardTests(_ExamData, unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_eight_tiles_share_one_row(self) -> None:
        page = self._shown_page(1100, 720)
        panel = page.exam_retraining
        panel.today_override = TODAY
        panel.refresh()
        QApplication.processEvents()
        cards = self._cards(page)
        self.assertEqual(
            [card.title_label.text() for card in cards],
            [
                "🔴 Po termínu",
                "🔵 Dnes",
                "🟡 Čeká kontrolu",
                "📋 Otevřeno",
                LABEL_VALID,
                LABEL_EXPIRING,
                LABEL_EXPIRED,
                LABEL_UNFINISHED,
            ],
        )
        self.assertTrue(page.exam_separator.isVisible())
        self.assertEqual(page.exam_separator.width(), 1)
        tops = [card.mapTo(page, card.rect().topLeft()).y() for card in cards]
        self.assertLessEqual(max(tops) - min(tops), 2)
        agenda_right = self._page_rect(page, cards[3]).right()
        tests_left = self._page_rect(page, cards[4]).left()
        separator = self._page_rect(page, page.exam_separator)
        self.assertLess(agenda_right, separator.left())
        self.assertGreater(tests_left, separator.right())
        self.assertAlmostEqual(page.summary.width(), page.exam_retraining.width(), delta=8)
        for group in (cards[:4], cards[4:]):
            widths = [card.width() for card in group]
            self.assertLessEqual(max(widths) - min(widths), 2)
            self.assertGreater(min(widths), 40)
        self.assertEqual(panel.valid_card.value_label.text(), "3")
        self.assertEqual(panel.expiring_card.value_label.text(), "1")
        self.assertEqual(panel.expired_card.value_label.text(), "1")
        self.assertEqual(panel.unfinished_card.value_label.text(), "5")
        self.assertIn(STATUS_DONE_TEXT, panel.valid_card.value_label.styleSheet())
        self.assertIn(STATUS_ORANGE_TEXT, panel.expiring_card.value_label.styleSheet())
        self.assertIn(STATUS_MISSING_TEXT, panel.expired_card.value_label.styleSheet())
        self.assertIn(UNFINISHED_TEXT, panel.unfinished_card.value_label.styleSheet())
        self.assertEqual(page.summary.overdue.subtitle_label.text(), "položky po termínu")
        self.assertEqual(page.summary.waiting.subtitle_label.text(), "čeká na kontrolu účinnosti")
        self.assertLessEqual(abs(page.summary.height() - 104), 20)
        self.assertEqual(page.summary.height(), page.exam_retraining.height())
        self.assertEqual(page.scroll_area.horizontalScrollBar().maximum(), 0)
        self.assertLess(page.summary.minimumSizeHint().width(), 80)
        self.assertLess(page.exam_retraining.minimumSizeHint().width(), 80)
        page.deleteLater()

    def test_titles_stay_readable_when_window_shrinks(self) -> None:
        page = self._shown_page(900, 640)
        QApplication.processEvents()
        self.assertLess(page.summary.minimumSizeHint().width(), 80)
        self.assertLess(page.exam_retraining.minimumSizeHint().width(), 80)
        for card in self._cards(page):
            self._assert_label_fits(card.title_label)
            if card.subtitle_label.isVisible():
                self._assert_label_fits(card.subtitle_label)
            self._assert_label_fits(card.value_label)
        rects = [self._page_rect(page, card) for card in self._cards(page)]
        rights = [rect.right() for rect in rects]
        lefts = [rect.left() for rect in rects]
        for previous, current in zip(rights, lefts[1:]):
            self.assertLessEqual(previous, current)
        page.deleteLater()

    def test_show_event_recomputes_only_when_day_changes(self) -> None:
        widget = ExamRetrainingWidget()
        widget.today_override = TODAY
        widget.refresh()
        calls: list[date | None] = []
        original = exam_validity_service.retraining_summary

        def wrapped(*, today=None):
            calls.append(today)
            return original(today=today)

        with patch.object(exam_validity_service, "retraining_summary", side_effect=wrapped):
            widget.showEvent(QShowEvent())
            self.assertEqual(calls, [])
            widget.today_override = TODAY + timedelta(days=40)
            widget.showEvent(QShowEvent())
        self.assertEqual(calls, [TODAY + timedelta(days=40)])
        self.assertEqual(widget.valid_card.value_label.text(), "2")
        self.assertEqual(widget.expired_card.value_label.text(), "3")
        self.assertEqual(widget.unfinished_card.value_label.text(), "5")
        self.assertTrue(widget._day_timer.isSingleShot())
        widget.deleteLater()

    def test_midnight_timer_runs_only_while_panel_is_shown(self) -> None:
        widget = ExamRetrainingWidget()
        widget.today_override = TODAY
        self.assertFalse(widget._day_timer.isActive())
        widget.show()
        QApplication.processEvents()
        self.assertTrue(widget._day_timer.isSingleShot())
        self.assertGreaterEqual(widget._day_timer.interval(), 1000)
        widget.hide()
        QApplication.processEvents()
        self.assertFalse(widget._day_timer.isActive())
        widget.deleteLater()

    def test_disabled_module_hides_panel_without_loading_summary(self) -> None:
        disabled = ModuleDefinition(
            key=MODULE_KEY,
            name="Testy",
            description="",
            page_factory=lambda: None,
            enabled=False,
        )
        with (
            patch.object(ModuleManager, "get_modules", return_value=[disabled]),
            patch.object(
                exam_validity_service,
                "retraining_summary",
                side_effect=AssertionError("souhrn se nemá počítat"),
            ),
        ):
            self.assertFalse(is_testy_module_enabled())
            page = DashboardPage()
            page.show()
            page.refresh()
            QApplication.processEvents()
        self.assertTrue(page.exam_retraining.isHidden())
        self.assertFalse(page.exam_retraining.isVisible())
        self.assertFalse(page.exam_separator.isVisible())
        self.assertGreater(page.summary.width(), page.width() * 0.7)
        page.deleteLater()

    def test_click_opens_validity_tab_and_return_refreshes_counts(self) -> None:
        window = MainWindow()
        try:
            window.show()
            QApplication.processEvents()
            panel = window._page_widgets["dashboard"].exam_retraining
            panel.today_override = TODAY
            window._show("dashboard")
            self.assertEqual(panel.valid_card.value_label.text(), "3")
            self.assertEqual(panel.unfinished_card.value_label.text(), "5")

            window._show("testy")
            exam_validity_service.stop_tracking(self.tracked_valid.id, self.active_test.id)
            window._show("dashboard")
            self.assertEqual(panel.valid_card.value_label.text(), "2")
            self.assertEqual(panel.expiring_card.value_label.text(), "1")
            self.assertEqual(panel.expired_card.value_label.text(), "1")
            self.assertEqual(panel.unfinished_card.value_label.text(), "5")

            QTest.mouseClick(panel.valid_card, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            testy = window._page_widgets["testy"]
            self.assertIs(window.current_page_widget(), testy)
            self.assertIs(testy.tabs.currentWidget(), testy.validity_tab)
            self.assertEqual(testy.tabs.tabText(testy.tabs.currentIndex()), AGENDA_EXAM_VALIDITY)

            window._show("dashboard")
            QTest.mouseClick(panel.unfinished_card, Qt.MouseButton.LeftButton)
            QApplication.processEvents()
            self.assertIs(testy.tabs.currentWidget(), testy.validity_tab)
        finally:
            window.deleteLater()
            QApplication.processEvents()

    def _shown_page(self, width: int, height: int) -> DashboardPage:
        page = DashboardPage()
        page.resize(width, height)
        page.show()
        QApplication.processEvents()
        return page

    def _cards(self, page: DashboardPage) -> list:
        panel = page.exam_retraining
        return [
            page.summary.overdue,
            page.summary.today,
            page.summary.waiting,
            page.summary.open_total,
            panel.valid_card,
            panel.expiring_card,
            panel.expired_card,
            panel.unfinished_card,
        ]

    def _page_rect(self, page, widget):
        top_left = widget.mapTo(page, widget.rect().topLeft())
        return widget.rect().translated(top_left)

    def _assert_label_fits(self, label) -> None:
        self.assertGreater(label.width(), 0)
        self.assertGreater(label.height(), 0)
        metrics = QFontMetrics(label.font())
        flags = Qt.TextFlag.TextWordWrap if label.wordWrap() else Qt.TextFlag.TextSingleLine
        bounds = metrics.boundingRect(0, 0, label.width(), 1000, int(flags), label.text())
        self.assertLessEqual(bounds.height(), label.height() + 2)
        self.assertLessEqual(bounds.width(), label.width() + 2)


if __name__ == "__main__":
    unittest.main()
