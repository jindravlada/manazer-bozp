"""Panel souhrnu přezkoušení na pracovní ploše."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QHBoxLayout

from core.dashboard.widget_base import DashboardCard, DashboardPanel
from core.theme.status_colors import (
    STATUS_DONE_TEXT,
    STATUS_MISSING_TEXT,
    STATUS_ORANGE_TEXT,
)
from moduly.testy.constants import MODULE_KEY

PANEL_TITLE = "Přezkoušení zaměstnanců"
LABEL_VALID = "Platné"
LABEL_EXPIRING = "Končí do 30 dnů"
LABEL_EXPIRED = "Po platnosti"
LABEL_UNFINISHED = "Nedokončené"

# Stejná modrá jako nadpisy pracovní plochy.
UNFINISHED_TEXT = "#174a8b"


def is_testy_module_enabled() -> bool:
    """Modul Testy je v aplikaci zapnutý. Vypnutý modul panel nezobrazuje."""
    from core.modules.module_manager import ModuleManager

    for module in ModuleManager().get_modules():
        if module.key == MODULE_KEY:
            return bool(module.enabled)
    return False


class _IndicatorCard(DashboardCard):
    def __init__(self, title: str, color: str, on_click) -> None:
        super().__init__(title, "0", "")
        self._on_click = on_click
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.title_label.setStyleSheet(f"color: {color}; font-weight: 700;")
        self.value_label.setStyleSheet(
            f"color: {color}; font-size: 28px; font-weight: 800;"
        )
        for label in (self.title_label, self.value_label, self.subtitle_label):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and callable(self._on_click):
            self._on_click()
        super().mouseReleaseEvent(event)


class ExamRetrainingWidget(DashboardPanel):
    """Čtyři číselné ukazatele. Klik otevře Testy → Platnost zkoušek."""

    def __init__(self, open_callback=None) -> None:
        super().__init__(PANEL_TITLE)
        self.open_callback = open_callback
        self.today_override: date | None = None
        self._loaded_day: date | None = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.title_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        self.valid_card = _IndicatorCard(LABEL_VALID, STATUS_DONE_TEXT, self._open)
        self.expiring_card = _IndicatorCard(LABEL_EXPIRING, STATUS_ORANGE_TEXT, self._open)
        self.expired_card = _IndicatorCard(LABEL_EXPIRED, STATUS_MISSING_TEXT, self._open)
        self.unfinished_card = _IndicatorCard(LABEL_UNFINISHED, UNFINISHED_TEXT, self._open)
        for card in (
            self.valid_card,
            self.expiring_card,
            self.expired_card,
            self.unfinished_card,
        ):
            row.addWidget(card, 1)
        self.layout.addLayout(row)

        self._day_timer = QTimer(self)
        self._day_timer.setSingleShot(True)
        self._day_timer.timeout.connect(self.refresh)
        self.refresh()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._open()
        super().mouseReleaseEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if self._loaded_day != self._today():
            self.refresh()
        else:
            self._arm_midnight()

    def hideEvent(self, event) -> None:  # noqa: N802
        self._day_timer.stop()
        super().hideEvent(event)

    def refresh(self) -> None:
        if not is_testy_module_enabled():
            self._loaded_day = None
            self._day_timer.stop()
            self.hide()
            return
        from moduly.testy.sluzby.exam_validity_service import exam_validity_service

        day = self._today()
        summary = exam_validity_service.retraining_summary(today=day)
        self.valid_card.set_value(str(summary.valid_count))
        self.expiring_card.set_value(str(summary.expiring_count))
        self.expired_card.set_value(str(summary.expired_count))
        self.unfinished_card.set_value(str(summary.unfinished_count))
        self._loaded_day = day
        if self.parent() is not None and not self.isVisible():
            self.setVisible(True)
        self._arm_midnight()

    def _today(self) -> date:
        if self.today_override is not None:
            return self.today_override
        return date.today()

    def _open(self) -> None:
        if callable(self.open_callback):
            self.open_callback()

    def _arm_midnight(self) -> None:
        """Jednorázově po půlnoci, bez průběžného čtení databáze."""
        if not self.isVisible():
            self._day_timer.stop()
            return
        now = datetime.now()
        next_midnight = datetime.combine(now.date() + timedelta(days=1), time.min)
        delay_ms = max(int((next_midnight - now).total_seconds() * 1000) + 500, 1000)
        self._day_timer.start(delay_ms)
