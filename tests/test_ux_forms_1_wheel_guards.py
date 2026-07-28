"""UX-FORMS-1: ochrana editačních polí před změnou kolečkem myši."""

from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_TMP = Path(tempfile.mkdtemp(prefix="ux-forms-1-"))

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.widgets.multi_legal_document_selector import MultiLegalDocumentSelector
from core.widgets.multi_responsibility_role_selector import (
    MultiResponsibilityRoleSelector,
)
from core.widgets.no_wheel_guards import (
    NoWheelComboBox,
    NoWheelSpinBox,
    form_wheel_guards_installed,
    install_form_wheel_guards,
    uninstall_form_wheel_guards,
)
from core.widgets.person_selector import PersonSelector
from core.widgets.search_combo_box import SearchComboBox
from core.widgets.search_responsibility_role_selector import (
    SearchResponsibilityRoleSelector,
)
from moduly.nastaveni.sluzby.person_service import person_service
from moduly.nastaveni.sluzby.responsibility_role_service import (
    responsibility_role_service,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.pravni_pozadavky.ui.legal_document_selector import (
    LegalDocumentNameSelector,
)


def _send_wheel(widget: QWidget, *, delta_y: int = -120) -> None:
    center = widget.rect().center()
    event = QWheelEvent(
        QPointF(center),
        widget.mapToGlobal(QPointF(center)),
        QPoint(0, 0),
        QPoint(0, delta_y),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(widget, event)


class UxForms1WheelGuardTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])
        cls.person = person_service.create_person(
            first_name="Jan",
            last_name="Novák",
            active=True,
        )
        person_service.create_person(first_name="Eva", last_name="Svobodová", active=True)
        cls.role = responsibility_role_service.create_role(name="Technik BOZP UX-FORMS-1")
        responsibility_role_service.create_role(name="Mistr UX-FORMS-1")
        from moduly.pravni_pozadavky.constants import DOCUMENT_TYPE_NARIZENI_VLADY, DOCUMENT_TYPE_ZAKON

        cls.document = legal_document_service.create(
            document_type=DOCUMENT_TYPE_NARIZENI_VLADY,
            title="Nařízení vlády UX-FORMS-1",
            number="999",
            year=2000,
            short_title="NV-UXF1",
        )
        legal_document_service.create(
            document_type=DOCUMENT_TYPE_ZAKON,
            title="Zákoník práce UX-FORMS-1",
            number="262",
            year=2006,
            short_title="ZP-UXF1",
        )

    def setUp(self) -> None:
        uninstall_form_wheel_guards()
        install_form_wheel_guards(self._app)
        self.assertTrue(form_wheel_guards_installed())

    def tearDown(self) -> None:
        uninstall_form_wheel_guards()

    def test_closed_combobox_wheel_keeps_current_index(self) -> None:
        combo = QComboBox()
        combo.addItems(["A", "B", "C", "D"])
        combo.setCurrentIndex(1)
        combo.resize(200, 30)
        combo.show()

        _send_wheel(combo)
        self.assertEqual(combo.currentIndex(), 1)
        _send_wheel(combo, delta_y=120)
        self.assertEqual(combo.currentIndex(), 1)

    def test_spinbox_wheel_keeps_value(self) -> None:
        spin = QSpinBox()
        spin.setRange(0, 100)
        spin.setValue(42)
        spin.resize(120, 30)
        spin.show()

        _send_wheel(spin)
        self.assertEqual(spin.value(), 42)
        _send_wheel(spin, delta_y=120)
        self.assertEqual(spin.value(), 42)

    def test_person_selector_wheel_does_not_change_or_add_person(self) -> None:
        self.assertTrue(issubclass(PersonSelector, NoWheelComboBox))
        selector = PersonSelector(include_empty=True, allow_add_new=False)
        selector.set_person_id(None)
        selector.show()
        QApplication.processEvents()

        before_id = selector.current_person_id()
        before_text = selector.currentText()
        _send_wheel(selector)
        self.assertEqual(selector.current_person_id(), before_id)
        self.assertEqual(selector.currentText(), before_text)
        self.assertIsNone(selector.current_person_id())

    def test_role_selector_wheel_does_not_add_role(self) -> None:
        self.assertTrue(issubclass(SearchResponsibilityRoleSelector, NoWheelComboBox))
        multi = MultiResponsibilityRoleSelector()
        multi.selector.set_role_id(None)
        multi.show()
        QApplication.processEvents()

        _send_wheel(multi.selector)
        self.assertEqual(multi.list_widget.count(), 0)
        self.assertIsNone(multi.selector.current_role_id())

    def test_legal_document_selector_wheel_does_not_change_document(self) -> None:
        self.assertTrue(issubclass(LegalDocumentNameSelector, NoWheelComboBox))
        multi = MultiLegalDocumentSelector()
        multi.selector.set_document_id(None)
        multi.show()
        QApplication.processEvents()

        before = multi.selector.current_document_id()
        _send_wheel(multi.selector)
        self.assertEqual(multi.list_widget.count(), 0)
        self.assertEqual(multi.selector.current_document_id(), before)
        self.assertIsNone(multi.selector.current_document_id())

    def test_scroll_area_still_scrolls_when_wheel_over_combo(self) -> None:
        host = QWidget()
        layout = QVBoxLayout(host)
        for index in range(40):
            layout.addWidget(QLabel(f"Řádek {index}"))
        combo = QComboBox()
        combo.addItems(["X", "Y", "Z"])
        combo.setCurrentIndex(0)
        layout.addWidget(combo)
        for index in range(40):
            layout.addWidget(QLabel(f"Spodek {index}"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(host)
        scroll.resize(320, 200)
        scroll.show()
        QApplication.processEvents()

        bar = scroll.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        before = bar.value()
        _send_wheel(combo, delta_y=-240)
        QApplication.processEvents()
        self.assertGreater(bar.value(), before)
        self.assertEqual(combo.currentIndex(), 0)

    def test_open_combo_popup_can_scroll_with_wheel(self) -> None:
        from core.widgets.no_wheel_guards import (
            FormWheelGuardFilter,
            should_block_wheel_on_widget,
        )

        combo = QComboBox()
        combo.addItems([f"Položka {i}" for i in range(40)])
        combo.setCurrentIndex(0)
        combo.resize(220, 30)
        combo.show()
        QApplication.processEvents()

        combo.showPopup()
        QApplication.processEvents()
        view = combo.view()
        self.assertTrue(view.isVisible())

        # Otevřený seznam: filtr wheel neblokuje (scroll nabídky zůstává Qt default).
        self.assertIsNone(should_block_wheel_on_widget(combo))
        self.assertIsNone(should_block_wheel_on_widget(view))

        center = view.rect().center()
        event = QWheelEvent(
            QPointF(center),
            view.mapToGlobal(QPointF(center)),
            QPoint(0, 0),
            QPoint(0, -240),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        guard = FormWheelGuardFilter()
        self.assertFalse(guard.eventFilter(view, event))
        self.assertFalse(guard.eventFilter(combo, event))
        self.assertEqual(combo.currentIndex(), 0)

    def test_no_wheel_subclasses_block_without_app_filter(self) -> None:
        uninstall_form_wheel_guards()
        combo = NoWheelComboBox()
        combo.addItems(["1", "2", "3"])
        combo.setCurrentIndex(0)
        combo.show()
        _send_wheel(combo)
        self.assertEqual(combo.currentIndex(), 0)

        spin = NoWheelSpinBox()
        spin.setValue(7)
        spin.show()
        _send_wheel(spin)
        self.assertEqual(spin.value(), 7)

        search = SearchComboBox(values=["A", "B"])
        search.setCurrentIndex(0)
        search.show()
        _send_wheel(search)
        self.assertEqual(search.currentIndex(), 0)


if __name__ == "__main__":
    unittest.main()
