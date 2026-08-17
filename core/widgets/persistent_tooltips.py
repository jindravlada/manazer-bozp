"""UX-TASK-TOOLTIP-1: tooltip zůstane, dokud kurzor zůstává nad stejným prvkem.

Qt samo skrývá tooltip při Leave, kliknutí, kolečku, deaktivaci okna a FocusOut.
Výchozí výdrž je ale krátká (~2 s FallAsleep + ~10 s expire). Tento modul:

- nastaví ``SH_ToolTip_FallAsleepDelay`` a ``toolTipDuration`` přes ``QProxyStyle``,
- u item views (tabulky/seznamy) předá stejnou dobu do ``QToolTip.showText``,
- kalendář a další přímé ``showText`` napojí na ``show_persistent_tooltip``.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, Qt
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QProxyStyle,
    QStyle,
    QToolTip,
    QWidget,
)

# 24 h — prakticky „dokud kurzor zůstane“; Qt skryje tooltip dřív při Leave/klik/wheel.
TOOLTIP_DISPLAY_MS = 24 * 60 * 60 * 1000
QT_DEFAULT_FALL_ASLEEP_MS = 2_000
_CALENDAR_OBJECT_NAME = "TaskCalendarWidget"

_style: PersistentToolTipStyle | None = None
_filter: PersistentToolTipFilter | None = None


def show_persistent_tooltip(
    pos: QPoint,
    text: str | None,
    widget: QWidget | None = None,
    rect: QRect | None = None,
) -> None:
    """Zobrazí tooltip se sdílenou výdrží. Prázdný text tooltip skryje."""
    if not str(text or "").strip():
        QToolTip.hideText()
        return
    QToolTip.showText(pos, text, widget, rect or QRect(), TOOLTIP_DISPLAY_MS)


def hide_persistent_tooltip() -> None:
    QToolTip.hideText()


class PersistentToolTipStyle(QProxyStyle):
    """Společný styl: dlouhá výdrž tooltipu u běžných QWidgetů i Wake/FallAsleep."""

    def styleHint(self, hint, option=None, widget=None, returnData=None):  # noqa: N802
        if hint == QStyle.StyleHint.SH_ToolTip_FallAsleepDelay:
            return TOOLTIP_DISPLAY_MS
        return super().styleHint(hint, option, widget, returnData)

    def polish(self, arg):
        super().polish(arg)
        if isinstance(arg, QWidget) and arg.toolTipDuration() != TOOLTIP_DISPLAY_MS:
            arg.setToolTipDuration(TOOLTIP_DISPLAY_MS)


class PersistentToolTipFilter(QObject):
    """Doplňuje C++ item-view tooltipy (delegate nepoužívá toolTipDuration)."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        etype = event.type()
        if etype == QEvent.Type.ApplicationDeactivate:
            QToolTip.hideText()
            return False
        if etype != QEvent.Type.ToolTip:
            return False
        if not isinstance(event, QHelpEvent):
            return False

        view = _item_view_for_viewport(watched)
        if view is not None:
            if _is_task_calendar_view(view):
                # Kalendář má vlastní MouseMove tooltip; prázdný Qt ToolTip by ho schoval.
                event.accept()
                return True
            return _show_item_view_tooltip(view, event)

        if isinstance(watched, QWidget) and not str(watched.toolTip() or "").strip():
            QToolTip.hideText()
            event.ignore()
            return True
        return False


def _item_view_for_viewport(obj: QObject) -> QAbstractItemView | None:
    if not isinstance(obj, QWidget):
        return None
    parent = obj.parentWidget()
    if isinstance(parent, QAbstractItemView) and obj is parent.viewport():
        return parent
    return None


def _is_task_calendar_view(view: QAbstractItemView) -> bool:
    parent = view.parentWidget()
    while parent is not None:
        if parent.objectName() == _CALENDAR_OBJECT_NAME:
            return True
        parent = parent.parentWidget()
    return False


def _show_item_view_tooltip(view: QAbstractItemView, event: QHelpEvent) -> bool:
    index = view.indexAt(event.pos())
    text = ""
    if index.isValid():
        value = index.data(Qt.ItemDataRole.ToolTipRole)
        text = "" if value is None else str(value)
    if not text.strip():
        QToolTip.hideText()
        event.ignore()
        return True
    QToolTip.showText(
        event.globalPos(),
        text,
        view.viewport(),
        view.visualRect(index),
        TOOLTIP_DISPLAY_MS,
    )
    event.accept()
    return True


def install_persistent_tooltips(app: QApplication | None = None) -> PersistentToolTipFilter:
    """Nainstaluje globální výdrž tooltipů (idempotentní)."""
    global _style, _filter
    application = app or QApplication.instance()
    if application is None:
        raise RuntimeError("QApplication není k dispozici.")
    if _style is None:
        _style = PersistentToolTipStyle(application.style())
        application.setStyle(_style)
    if _filter is None:
        _filter = PersistentToolTipFilter(application)
        application.installEventFilter(_filter)
    return _filter


def uninstall_persistent_tooltips() -> None:
    """Odstraní event filter (styl zůstává). Určeno pro testy."""
    global _filter
    application = QApplication.instance()
    if application is not None and _filter is not None:
        application.removeEventFilter(_filter)
    _filter = None


def persistent_tooltips_installed() -> bool:
    return _filter is not None
