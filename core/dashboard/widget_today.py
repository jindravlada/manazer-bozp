from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
)

from core.dashboard.attention_item import (
    ITEM_TYPE_MEETING,
    ITEM_TYPE_OZO_CONTRACT,
    ITEM_TYPE_OZO_PERSON_CERTIFICATE,
    ITEM_TYPE_QUALIFICATION_CERTIFICATE,
    ITEM_TYPE_YEARLY_PLAN_MONTH,
    AttentionItem,
)
from core.dashboard.attention_service import (
    build_sort_key,
    get_attention_items,
    get_external_audit_reminder_items,
    get_external_finding_reminder_items,
    get_periodic_reminder_items,
    get_yearly_plan_month_reminder_items,
)
from core.dashboard.task_links import configure_task_label, task_id_from_link, task_link
from core.dashboard.widget_base import DashboardPanel
from moduly.schuzky.constants import STATUS_PLANNED as MEETING_STATUS_PLANNED
from moduly.schuzky.sluzby.meeting_service import meeting_service
from moduly.ukoly.sluzby.task_service import task_service

STATUS_WAITING_CHECK = "Splněno - čeká na kontrolu"
STATUS_CLOSED = "Ukončeno"
STATUS_CANCELED = "Zrušeno"
_CLOSED_STATUSES = {STATUS_CLOSED, STATUS_CANCELED}

_ATTENTION_LINK_PREFIX = "attention:"
PANEL_TITLE_REMINDERS = "Připomínky"

_CERTIFICATE_ITEM_TYPES = {
    ITEM_TYPE_OZO_PERSON_CERTIFICATE,
    ITEM_TYPE_QUALIFICATION_CERTIFICATE,
}


def task_urgency_due_date(task) -> date | None:
    """Rozhodný termín pro Připomínky podle aktuální fáze úkolu."""
    status = task.computed_status
    if status in _CLOSED_STATUSES:
        return None
    if status == STATUS_WAITING_CHECK:
        return task.check_due_date
    return task.due_date


def task_should_appear_in_reminders(task, today: date) -> bool:
    """Má se aktivní / čekající úkol zobrazit v panelu Připomínky?"""
    status = task.computed_status
    if status in _CLOSED_STATUSES:
        return False

    if status == STATUS_WAITING_CHECK:
        check_due = task.check_due_date
        return check_due is not None and today >= check_due

    remind_from = getattr(task, "remind_from", None)
    if remind_from is not None and today >= remind_from:
        return True
    due_date = task.due_date
    if due_date is not None and today >= due_date:
        return True
    return False


def classify_burning_tasks(tasks, today: date):
    """Rozdělí úkoly pro panel Připomínky podle rozhodného termínu fáze."""
    burning = []
    due_today = []
    waiting = []

    for task in tasks:
        if not task_should_appear_in_reminders(task, today):
            continue

        status = task.computed_status
        decisive = task_urgency_due_date(task)

        if decisive is not None and decisive < today:
            burning.append(task)
        elif decisive == today:
            due_today.append(task)
        elif status == STATUS_WAITING_CHECK:
            # Pojistka: před check_due_date už vyřazeno výše.
            waiting.append(task)
        else:
            # Aktivní: připomenuto přes remind_from před due_date / bez due_date.
            due_today.append(task)

    burning.sort(key=lambda task: (task_urgency_due_date(task) or date.max, task.id))
    due_today.sort(key=lambda task: (task_urgency_due_date(task) or date.max, task.id))
    waiting.sort(key=lambda task: (task.check_due_date or date.max, task.id))
    return burning, due_today, waiting


def meeting_event_date(meeting) -> date | None:
    """Kalendářní datum události (zahájení)."""
    starts_at = meeting.starts_at
    if starts_at is None:
        return None
    return starts_at.date()


def meeting_should_appear_in_reminders(meeting, today: date) -> bool:
    """Má se naplánovaná událost zobrazit v panelu Připomínky?"""
    status = meeting_service.normalize_status(getattr(meeting, "status", None))
    if status != MEETING_STATUS_PLANNED:
        return False

    remind_from = getattr(meeting, "remind_from", None)
    if remind_from is not None and today >= remind_from:
        return True
    event_date = meeting_event_date(meeting)
    if event_date is not None and today >= event_date:
        return True
    return False


def classify_reminder_meetings(meetings, today: date):
    """Rozdělí události pro panel Připomínky (po termínu / dnes včetně předstihu)."""
    burning = []
    due_today = []

    for meeting in meetings:
        if not meeting_should_appear_in_reminders(meeting, today):
            continue
        event_date = meeting_event_date(meeting)
        if event_date is not None and event_date < today:
            burning.append(meeting)
        else:
            due_today.append(meeting)

    burning.sort(key=lambda item: (meeting_event_date(item) or date.max, item.id))
    due_today.sort(
        key=lambda item: (
            meeting_event_date(item) or getattr(item, "remind_from", None) or date.max,
            item.id,
        )
    )
    return burning, due_today


def meeting_reminder_attention_item(meeting) -> AttentionItem:
    """AttentionItem pro kliknutí na událost v Připomínkách."""
    starts_at = meeting.starts_at
    event_date = meeting_event_date(meeting)
    if event_date is None:
        event_date = getattr(meeting, "remind_from", None)
    title = (meeting.title or "").strip() or "Bez názvu"
    event_type = (getattr(meeting, "event_type", None) or "").strip()
    if event_type:
        title = f"{event_type} – {title}"
    location = (meeting.location or "").strip() or "—"
    return AttentionItem(
        item_type=ITEM_TYPE_MEETING,
        source_type=ITEM_TYPE_MEETING,
        source_id=meeting.id,
        title=title,
        date=event_date,
        subtitle=location,
        status=meeting.status or "",
        priority="",
        event_at=starts_at,
        ends_at=meeting.ends_at,
        open_metadata={
            "source_type": ITEM_TYPE_MEETING,
            "source_id": meeting.id,
        },
        sort_key=build_sort_key(
            event_date,
            item_type=ITEM_TYPE_MEETING,
            title=title,
            source_id=meeting.id,
            due_datetime=starts_at,
        ),
    )

def classify_reminder_periodics(items: list[AttentionItem], today: date):
    """Rozdělí periodiky pro Připomínky: po termínu / dnes včetně předstihu."""
    burning = []
    due_today = []
    for item in items:
        due = item.due_date
        if due is not None and due < today:
            burning.append(item)
        else:
            due_today.append(item)
    burning.sort(key=lambda item: (item.due_date or date.max, item.source_id))
    due_today.sort(key=lambda item: (item.due_date or date.max, item.source_id))
    return burning, due_today


def classify_reminder_yearly_plan_months(items: list[AttentionItem], today: date):
    """Rozdělí měsíční připomínky: po termínu / v den prvního pracovního dne."""
    burning = []
    due_today = []
    for item in items:
        due = item.due_date
        if due is not None and due < today:
            burning.append(item)
        else:
            due_today.append(item)
    burning.sort(key=lambda item: (item.due_date or date.max, item.source_id))
    due_today.sort(key=lambda item: (item.due_date or date.max, item.source_id))
    return burning, due_today


def classify_reminder_attention_items(items: list[AttentionItem], today: date):
    """Rozdělí obecné AttentionItem pro Připomínky: po termínu / dnes včetně."""
    burning = []
    due_today = []
    for item in items:
        due = item.due_date
        if due is not None and due < today:
            burning.append(item)
        else:
            due_today.append(item)
    burning.sort(key=lambda item: (item.due_date or date.max, item.source_id))
    due_today.sort(key=lambda item: (item.due_date or date.max, item.source_id))
    return burning, due_today


def overdue_yearly_plan_month_items(
    today: date,
    *,
    attention_items: list[AttentionItem] | None = None,
) -> list[AttentionItem]:
    """Připomínka zpracování měsíce od prvního pracovního dne (Připomínky)."""
    _ = attention_items
    return get_yearly_plan_month_reminder_items(today=today)

def overdue_ozo_contract_items(
    today: date,
    *,
    attention_items: list[AttentionItem] | None = None,
) -> list[AttentionItem]:
    """Aktivní smlouvy OZO po datu platnosti do."""
    items = attention_items
    if items is None:
        items = get_attention_items(today=today)
    overdue = [
        item
        for item in items
        if item.item_type == ITEM_TYPE_OZO_CONTRACT
        and item.due_date is not None
        and item.due_date < today
    ]
    overdue.sort(key=lambda item: (item.due_date or date.max, item.source_id))
    return overdue


def overdue_certificate_items(
    today: date,
    *,
    attention_items: list[AttentionItem] | None = None,
) -> list[AttentionItem]:
    """Osvědčení OZO / ostatní po datu platnosti."""
    items = attention_items
    if items is None:
        items = get_attention_items(today=today)
    overdue = [
        item
        for item in items
        if item.item_type in _CERTIFICATE_ITEM_TYPES
        and item.due_date is not None
        and item.due_date < today
    ]
    overdue.sort(key=lambda item: (item.due_date or date.max, item.source_id))
    return overdue


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def attention_link(item: AttentionItem) -> str:
    safe_text = _escape_html(item.title or "")
    href = f"{_ATTENTION_LINK_PREFIX}{item.item_type}:{item.source_id}"
    return (
        f'<a href="{href}" '
        f'style="color:inherit; text-decoration:none; cursor:pointer;">{safe_text}</a>'
    )


def attention_from_link(
    link: str,
    items: list[AttentionItem],
) -> AttentionItem | None:
    if not link.startswith(_ATTENTION_LINK_PREFIX):
        return None
    payload = link[len(_ATTENTION_LINK_PREFIX) :]
    if ":" not in payload:
        return None
    item_type, raw_id = payload.split(":", 1)
    try:
        source_id = int(raw_id)
    except ValueError:
        return None
    for item in items:
        if item.item_type == item_type and item.source_id == source_id:
            return item
    return None


class _ReminderContentLabel(QLabel):
    """QLabel, který hlásí výšku obsahu, aby QScrollArea mohla rolovat svisle."""

    def __init__(self) -> None:
        super().__init__()
        configure_task_label(self)
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        self.setMinimumWidth(1)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt API
        super().setText(text)
        self._update_min_height()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._update_min_height()

    def _update_min_height(self) -> None:
        width = self.width()
        if width <= 1:
            parent = self.parentWidget()
            if parent is not None:
                width = parent.width()
        if width <= 1:
            return
        height = self.heightForWidth(width)
        if height < 0:
            height = self.sizeHint().height()
        if self.minimumHeight() != height:
            self.setMinimumHeight(height)


class TodayWidget(DashboardPanel):
    def __init__(self, open_task_callback=None, open_attention_callback=None):
        super().__init__(PANEL_TITLE_REMINDERS)
        self.open_task_callback = open_task_callback
        self.open_attention_callback = open_attention_callback
        self._linked_attention: list[AttentionItem] = []

        self.content = _ReminderContentLabel()
        self.content.linkActivated.connect(self._on_link_clicked)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("RemindersScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setFocusPolicy(Qt.FocusPolicy.WheelFocus)
        self._scroll.setWidget(self.content)

        self.layout.addWidget(self._scroll, 1)
        self.setFixedHeight(170)
        self.refresh()

    def _task_line(self, task, prefix):
        decisive = task_urgency_due_date(task)
        if decisive is None and getattr(task, "remind_from", None) is not None:
            decisive = task.remind_from
        term = decisive.strftime("%d.%m.%Y") if decisive else "bez termínu"
        place = task.workplace_name or "—"
        title = task_link(task.id, task.title)
        return (
            f"{prefix} <b>{term}</b> – {title}"
            f"<br><span style='color:#666;'>📍 {place}</span>"
        )

    def _attention_line(self, item: AttentionItem, prefix: str) -> str:
        term = item.due_date.strftime("%d.%m.%Y") if item.due_date else "bez termínu"
        place = item.subtitle or "—"
        title = attention_link(item)
        return (
            f"{prefix} <b>{term}</b> – {title}"
            f"<br><span style='color:#666;'>📍 {place}</span>"
        )

    def _on_link_clicked(self, link: str) -> None:
        task_id = task_id_from_link(link)
        if task_id is not None and self.open_task_callback:
            self.open_task_callback(task_id)
            return
        attention = attention_from_link(link, self._linked_attention)
        if attention is not None and self.open_attention_callback:
            self.open_attention_callback(attention)

    def refresh(self, today: date | None = None):
        today = today or date.today()
        burning, due_today, waiting = classify_burning_tasks(
            task_service.get_all_tasks(),
            today,
        )
        meeting_burning, meeting_due = classify_reminder_meetings(
            meeting_service.get_all(),
            today,
        )
        meeting_burning_items = [
            meeting_reminder_attention_item(meeting) for meeting in meeting_burning
        ]
        meeting_due_items = [
            meeting_reminder_attention_item(meeting) for meeting in meeting_due
        ]
        attention_items = get_attention_items(today=today)
        month_burning, month_due = classify_reminder_yearly_plan_months(
            get_yearly_plan_month_reminder_items(today=today),
            today,
        )
        overdue_contracts = overdue_ozo_contract_items(
            today, attention_items=attention_items
        )
        overdue_certs = overdue_certificate_items(
            today, attention_items=attention_items
        )
        periodic_burning, periodic_due = classify_reminder_periodics(
            get_periodic_reminder_items(today=today),
            today,
        )
        ea_audit_burning, ea_audit_due = classify_reminder_attention_items(
            get_external_audit_reminder_items(today=today),
            today,
        )
        ea_finding_burning, ea_finding_due = classify_reminder_attention_items(
            get_external_finding_reminder_items(today=today),
            today,
        )
        self._linked_attention = (
            list(month_burning)
            + list(month_due)
            + list(overdue_contracts)
            + list(overdue_certs)
            + list(periodic_burning)
            + list(periodic_due)
            + meeting_burning_items
            + meeting_due_items
            + list(ea_audit_burning)
            + list(ea_audit_due)
            + list(ea_finding_burning)
            + list(ea_finding_due)
        )

        ordered: list[str] = []
        ordered.extend(self._attention_line(item, "🔴") for item in month_burning)
        for item in overdue_contracts:
            ordered.append(self._attention_line(item, "🔴"))
        for item in overdue_certs:
            ordered.append(self._attention_line(item, "🔴"))
        ordered.extend(self._attention_line(item, "🔴") for item in periodic_burning)
        ordered.extend(self._attention_line(item, "🔴") for item in meeting_burning_items)
        ordered.extend(self._attention_line(item, "🔴") for item in ea_audit_burning)
        ordered.extend(self._attention_line(item, "🔴") for item in ea_finding_burning)
        ordered.extend(self._task_line(task, "🔴") for task in burning)
        ordered.extend(self._attention_line(item, "🔵") for item in month_due)
        ordered.extend(self._attention_line(item, "🔵") for item in periodic_due)
        ordered.extend(self._attention_line(item, "🔵") for item in meeting_due_items)
        ordered.extend(self._attention_line(item, "🔵") for item in ea_audit_due)
        ordered.extend(self._attention_line(item, "🔵") for item in ea_finding_due)
        ordered.extend(self._task_line(task, "🔵") for task in due_today)
        ordered.extend(self._task_line(task, "🟡") for task in waiting)

        if not ordered:
            ordered.append("Nic k připomenutí.")

        self.content.setText("<br>".join(ordered))
        self._clamp_scroll_position()

    def _clamp_scroll_position(self) -> None:
        bar = self._scroll.verticalScrollBar()
        bar.setValue(min(max(bar.value(), 0), bar.maximum()))

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API
        bar = self._scroll.verticalScrollBar()
        if bar.maximum() > 0:
            bar.setValue(bar.value() - event.angleDelta().y())
            event.accept()
            return
        super().wheelEvent(event)
