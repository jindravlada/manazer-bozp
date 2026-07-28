"""UX-FORMS-1: ochrana editačních polí před změnou kolečkem myši.

Diagnostika (zdrojové UI, bez AppDir/dist/venv):
- ~90 souborů vytváří ``QComboBox`` / ``QSpinBox`` / ``QDoubleSpinBox``
- sdílené selektory: ``SearchComboBox``, ``PersonSelector``, ``ThpWorkerSelector``,
  ``WorkplaceSelector``, ``ExposedGroupSelector``, ``ExposedTargetSelector``,
  ``SearchResponsibilityRoleSelector``, ``LegalDocumentNameSelector``,
  ``CodeSelector``, ``ResponsibilityRoleSelector``
- multi-selectory: ``Multi*`` (obsahují combo + seznam; wheel dřív měnil
  currentIndex / mohl „vložit“ první položku)
- žádné vlastní ``wheelEvent`` override v aplikačním kódu

Řešení: centrální ``QApplication`` event filter + společné podtřídy
(``NoWheelComboBox`` / ``NoWheelSpinBox`` / ``NoWheelDoubleSpinBox``).
Filtr pokrývá i přímé ``QComboBox()`` ve formulářích bez migrace souborů.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QWidget,
)

_filter: FormWheelGuardFilter | None = None


def _combo_dropdown_open(combo: QComboBox) -> bool:
    """True, pokud je otevřený rozbalovací seznam (ne completer popup)."""
    view = combo.view()
    return view is not None and view.isVisible()


def redirect_wheel_to_scroll_parent(widget: QWidget, event: QWheelEvent) -> bool:
    """Předá wheel nejbližšímu ``QAbstractScrollArea`` (viewport), jinak ignore.

    Returns:
        True, pokud byla událost předána scroll oblasti.
    """
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QAbstractScrollArea):
            QApplication.sendEvent(parent.viewport(), event)
            return True
        parent = parent.parentWidget()
    event.ignore()
    return False


def should_block_wheel_on_widget(widget: QObject) -> QWidget | None:
    """Vrátí widget, jehož hodnotu má wheel blokovat, jinak None."""
    if not isinstance(widget, QWidget):
        return None

    if isinstance(widget, QComboBox):
        if _combo_dropdown_open(widget):
            return None
        return widget

    if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
        return widget

    if isinstance(widget, QAbstractSpinBox):
        # QDateEdit / QDateTimeEdit / QTimeEdit – stejný problém při rolování.
        return widget

    # Interní line-edit / šipky spinboxu a editovatelného comboboxu.
    parent = widget.parentWidget()
    if isinstance(parent, QComboBox):
        if _combo_dropdown_open(parent):
            return None
        return parent
    if isinstance(parent, (QSpinBox, QDoubleSpinBox, QAbstractSpinBox)):
        return parent

    return None


class FormWheelGuardFilter(QObject):
    """Aplikační filtr: wheel nemění hodnoty zavřených combo/spin polí."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if event.type() != QEvent.Type.Wheel:
            return False
        if not isinstance(event, QWheelEvent):
            return False

        target = should_block_wheel_on_widget(watched)
        if target is None:
            return False

        redirect_wheel_to_scroll_parent(target, event)
        return True


def install_form_wheel_guards(app: QApplication | None = None) -> FormWheelGuardFilter:
    """Nainstaluje globální ochranu (idempotentní)."""
    global _filter
    application = app or QApplication.instance()
    if application is None:
        raise RuntimeError("QApplication není k dispozici.")
    if _filter is None:
        _filter = FormWheelGuardFilter(application)
        application.installEventFilter(_filter)
    return _filter


def uninstall_form_wheel_guards() -> None:
    """Odstraní globální ochranu (pro testy)."""
    global _filter
    application = QApplication.instance()
    if application is not None and _filter is not None:
        application.removeEventFilter(_filter)
    _filter = None


def form_wheel_guards_installed() -> bool:
    return _filter is not None


class NoWheelComboBox(QComboBox):
    """QComboBox: wheel mění hodnotu jen při otevřeném popup seznamu."""

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if _combo_dropdown_open(self):
            super().wheelEvent(event)
            return
        redirect_wheel_to_scroll_parent(self, event)


class NoWheelSpinBox(QSpinBox):
    """QSpinBox: wheel hodnotu nemění (šipky / klávesnice / zápis ano)."""

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        redirect_wheel_to_scroll_parent(self, event)


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox: wheel hodnotu nemění."""

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        redirect_wheel_to_scroll_parent(self, event)
