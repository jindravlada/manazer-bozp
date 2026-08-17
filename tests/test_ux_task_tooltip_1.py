"""UX-TASK-TOOLTIP-1: titul editoru úkolu a globální výdrž tooltipů."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QHelpEvent, QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QToolTip,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="ux-task-tooltip-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from core.dashboard.widget_calendar_placeholder import TaskCalendarWidget
    from core.widgets.persistent_tooltips import (
        QT_DEFAULT_FALL_ASLEEP_MS,
        TOOLTIP_DISPLAY_MS,
        install_persistent_tooltips,
        persistent_tooltips_installed,
        show_persistent_tooltip,
        uninstall_persistent_tooltips,
    )
    from moduly.ukoly.constants import TASK_TYPE_INVESTIGATION_ACTION
    from moduly.ukoly.sluzby.task_service import task_service
    from moduly.ukoly.ui.task_dialog import (
        TASK_EDITOR_TITLE,
        TASK_EDITOR_TITLE_FINDING,
        TASK_EDITOR_TITLE_INVESTIGATION,
        TaskDialog,
        resolve_task_editor_window_title,
    )


def _send_tooltip(widget, pos: QPoint | None = None) -> QHelpEvent:
    local = pos or widget.rect().center()
    event = QHelpEvent(QEvent.Type.ToolTip, local, widget.mapToGlobal(local))
    QApplication.sendEvent(widget, event)
    return event


class TaskEditorTitleTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def test_new_task_window_title_is_ukol(self) -> None:
        dialog = TaskDialog()
        self.assertEqual(dialog.windowTitle(), TASK_EDITOR_TITLE)
        self.assertEqual(dialog.windowTitle(), "Úkol")
        self.assertEqual(dialog.type_label.text(), "Nápravné opatření")

    def test_existing_task_window_title_is_ukol(self) -> None:
        task = task_service.create_task(title="Existující úkol")
        dialog = TaskDialog(task=task)
        self.assertEqual(dialog.windowTitle(), "Úkol")

    def test_contextual_finding_title_is_kept(self) -> None:
        self.assertEqual(
            resolve_task_editor_window_title(has_finding=True),
            TASK_EDITOR_TITLE_FINDING,
        )
        dialog = TaskDialog(window_title="Nápravné opatření")
        self.assertEqual(dialog.windowTitle(), "Nápravné opatření")

        task = task_service.create_task(title="Opatření ze zjištění")
        fake_finding = SimpleNamespace(
            description="Neshoda v dokumentaci",
            entity_type="audity",
            entity_id=1,
        )
        with patch(
            "moduly.ukoly.ui.task_dialog.finding_task_service.get_finding_for_task",
            return_value=fake_finding,
        ), patch(
            "moduly.ukoly.ui.task_dialog.source_navigator.can_open",
            return_value=False,
        ):
            finding_dialog = TaskDialog(task=task)
        self.assertEqual(finding_dialog.windowTitle(), "Nápravné opatření")

    def test_investigation_title_is_kept(self) -> None:
        task = task_service.create_task(
            title="Úkon",
            task_type=TASK_TYPE_INVESTIGATION_ACTION,
        )
        dialog = TaskDialog(task=task)
        self.assertEqual(dialog.windowTitle(), TASK_EDITOR_TITLE_INVESTIGATION)

    def test_agenda_new_task_uses_ukol_title(self) -> None:
        from moduly.agenda.ui.agenda_page import AgendaPage

        page = AgendaPage()
        with patch(
            "moduly.agenda.ui.agenda_page.exec_maximized",
            return_value=0,
        ) as mocked:
            page.new_task()
        dialog = mocked.call_args.args[0]
        self.assertIsInstance(dialog, TaskDialog)
        self.assertEqual(dialog.windowTitle(), "Úkol")


class PersistentTooltipTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        install_persistent_tooltips(cls._app)

    @classmethod
    def tearDownClass(cls) -> None:
        QToolTip.hideText()
        uninstall_persistent_tooltips()

    def setUp(self) -> None:
        QToolTip.hideText()
        install_persistent_tooltips(self._app)

    def tearDown(self) -> None:
        QToolTip.hideText()

    def test_duration_is_not_the_original_short_delay(self) -> None:
        self.assertTrue(persistent_tooltips_installed())
        self.assertGreater(TOOLTIP_DISPLAY_MS, QT_DEFAULT_FALL_ASLEEP_MS)
        self.assertGreater(TOOLTIP_DISPLAY_MS, 10_000)
        delay = self._app.style().styleHint(QStyle.StyleHint.SH_ToolTip_FallAsleepDelay)
        self.assertEqual(delay, TOOLTIP_DISPLAY_MS)
        self.assertNotEqual(delay, QT_DEFAULT_FALL_ASLEEP_MS)

        label = QLabel("Pole")
        label.setToolTip("Nápověda pole")
        label.show()
        QApplication.processEvents()
        self.assertEqual(label.toolTipDuration(), TOOLTIP_DISPLAY_MS)

    def test_empty_tooltip_is_not_shown(self) -> None:
        label = QLabel("Prázdné")
        label.setToolTip("   ")
        label.show()
        QApplication.processEvents()
        event = _send_tooltip(label)
        self.assertFalse(event.isAccepted())
        self.assertFalse(QToolTip.isVisible())

        show_persistent_tooltip(QPoint(8, 8), "   ", label)
        self.assertFalse(QToolTip.isVisible())

    def test_widget_tooltip_hides_on_leave_click_wheel_deactivate(self) -> None:
        label = QLabel("Widget")
        label.setToolTip("Nápověda widgetu")
        label.resize(180, 60)
        label.show()
        QApplication.processEvents()
        _send_tooltip(label)
        self.assertTrue(QToolTip.isVisible())
        self.assertEqual(QToolTip.text(), "Nápověda widgetu")

        QApplication.sendEvent(label, QEvent(QEvent.Type.Leave))
        QTest.qWait(350)
        self.assertFalse(QToolTip.isVisible())

        _send_tooltip(label)
        self.assertTrue(QToolTip.isVisible())
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(label.rect().center()),
            label.mapToGlobal(QPointF(label.rect().center())),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QApplication.sendEvent(label, press)
        QApplication.processEvents()
        self.assertFalse(QToolTip.isVisible())

        _send_tooltip(label)
        self.assertTrue(QToolTip.isVisible())
        center = label.rect().center()
        wheel = QWheelEvent(
            QPointF(center),
            label.mapToGlobal(QPointF(center)),
            QPoint(0, 0),
            QPoint(0, -120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        QApplication.sendEvent(label, wheel)
        QApplication.processEvents()
        self.assertFalse(QToolTip.isVisible())

        _send_tooltip(label)
        self.assertTrue(QToolTip.isVisible())
        QApplication.sendEvent(label.window(), QEvent(QEvent.Type.WindowDeactivate))
        QApplication.processEvents()
        self.assertFalse(QToolTip.isVisible())

        _send_tooltip(label)
        self.assertTrue(QToolTip.isVisible())
        QApplication.sendEvent(self._app, QEvent(QEvent.Type.ApplicationDeactivate))
        QTest.qWait(350)
        self.assertFalse(QToolTip.isVisible())

    def test_table_tooltip_updates_between_items_and_hides_empty(self) -> None:
        table = QTableWidget(1, 2)
        first = QTableWidgetItem("A")
        first.setToolTip("Tooltip A")
        second = QTableWidgetItem("B")
        second.setToolTip("Tooltip B")
        table.setItem(0, 0, first)
        table.setItem(0, 1, second)
        table.resize(420, 160)
        table.show()
        QApplication.processEvents()

        viewport = table.viewport()
        pos_a = table.visualRect(table.model().index(0, 0)).center()
        pos_b = table.visualRect(table.model().index(0, 1)).center()

        with patch(
            "core.widgets.persistent_tooltips.QToolTip.showText"
        ) as show_text:
            _send_tooltip(viewport, pos_a)
            self.assertEqual(show_text.call_count, 1)
            self.assertEqual(show_text.call_args.args[1], "Tooltip A")
            self.assertEqual(show_text.call_args.args[4], TOOLTIP_DISPLAY_MS)

        with patch(
            "core.widgets.persistent_tooltips.QToolTip.showText"
        ) as show_text:
            _send_tooltip(viewport, pos_b)
            self.assertEqual(show_text.call_count, 1)
            self.assertEqual(show_text.call_args.args[1], "Tooltip B")
            self.assertEqual(show_text.call_args.args[4], TOOLTIP_DISPLAY_MS)

        second.setToolTip("")
        with patch(
            "core.widgets.persistent_tooltips.QToolTip.hideText"
        ) as hide_text, patch(
            "core.widgets.persistent_tooltips.QToolTip.showText"
        ) as show_text:
            event = _send_tooltip(viewport, pos_b)
            hide_text.assert_called()
            show_text.assert_not_called()
            self.assertFalse(event.isAccepted())

    def test_calendar_uses_shared_duration_and_swallows_qt_tooltip(self) -> None:
        self.assertEqual(TOOLTIP_DISPLAY_MS, 24 * 60 * 60 * 1000)
        cal = TaskCalendarWidget()
        cal.show()
        QApplication.processEvents()
        cal._ensure_tooltip_hook()
        view = cal._view
        self.assertIsNotNone(view)

        with patch.object(QToolTip, "showText") as show_text, patch.object(
            QToolTip, "hideText"
        ) as hide_text:
            pos = view.viewport().rect().center()
            event = _send_tooltip(view.viewport(), pos)
            self.assertTrue(event.isAccepted())
            show_text.assert_not_called()
            hide_text.assert_not_called()

        with patch.object(QToolTip, "showText") as show_text:
            show_persistent_tooltip(QPoint(4, 4), "Den v kalendáři", view.viewport())
            self.assertEqual(show_text.call_count, 1)
            self.assertEqual(show_text.call_args.args[4], TOOLTIP_DISPLAY_MS)


if __name__ == "__main__":
    unittest.main()
