from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy

from core.dashboard.attention_item import ITEM_TYPE_YEARLY_PLAN_MONTH, AttentionItem
from core.dashboard.attention_service import get_attention_items
from core.dashboard.task_links import configure_task_label, task_id_from_link, task_link
from core.dashboard.widget_base import DashboardPanel
from moduly.ukoly.sluzby.task_service import task_service

STATUS_WAITING_CHECK = "Splněno - čeká na kontrolu"
STATUS_CLOSED = "Ukončeno"
STATUS_CANCELED = "Zrušeno"
_CLOSED_STATUSES = {STATUS_CLOSED, STATUS_CANCELED}

_ATTENTION_LINK_PREFIX = "attention:"


def task_urgency_due_date(task) -> date | None:
    """Rozhodný termín pro „Co hoří“ podle aktuální fáze úkolu."""
    status = task.computed_status
    if status in _CLOSED_STATUSES:
        return None
    if status == STATUS_WAITING_CHECK:
        return task.check_due_date
    return task.due_date


def classify_burning_tasks(tasks, today: date):
    """Rozdělí otevřené úkoly podle rozhodného termínu fáze."""
    burning = []
    due_today = []
    waiting = []

    for task in tasks:
        status = task.computed_status
        if status in _CLOSED_STATUSES:
            continue

        decisive = task_urgency_due_date(task)
        if decisive is not None and decisive < today:
            burning.append(task)
        elif decisive == today:
            due_today.append(task)
        elif status == STATUS_WAITING_CHECK:
            waiting.append(task)

    burning.sort(key=lambda task: (task_urgency_due_date(task) or date.max, task.id))
    due_today.sort(key=lambda task: (task_urgency_due_date(task) or date.max, task.id))
    waiting.sort(key=lambda task: (task.check_due_date or date.max, task.id))
    return burning, due_today, waiting


def overdue_yearly_plan_month_items(
    today: date,
    *,
    attention_items: list[AttentionItem] | None = None,
) -> list[AttentionItem]:
    """Výzvy „Zpracovat úkoly měsíce“ po termínu (měsíc ještě nezpracován)."""
    items = attention_items
    if items is None:
        items = get_attention_items(today=today)
    overdue = [
        item
        for item in items
        if item.item_type == ITEM_TYPE_YEARLY_PLAN_MONTH
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


class TodayWidget(DashboardPanel):
    def __init__(self, open_task_callback=None, open_attention_callback=None):
        super().__init__("Co hoří")
        self.open_task_callback = open_task_callback
        self.open_attention_callback = open_attention_callback
        self._linked_attention: list[AttentionItem] = []

        self.content = QLabel()
        configure_task_label(self.content)
        self.content.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.content.linkActivated.connect(self._on_link_clicked)

        self.layout.addWidget(self.content, 1)
        self.setFixedHeight(170)
        self.refresh()

    def _task_line(self, task, prefix):
        decisive = task_urgency_due_date(task)
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
        overdue_months = overdue_yearly_plan_month_items(today)
        self._linked_attention = list(overdue_months)

        ordered: list[str] = []
        for item in overdue_months:
            ordered.append(self._attention_line(item, "🔴"))
        ordered.extend(self._task_line(task, "🔴") for task in burning)
        ordered.extend(self._task_line(task, "🔵") for task in due_today)
        ordered.extend(self._task_line(task, "🟡") for task in waiting)

        lines = ordered[:5]

        if not lines:
            lines.append("Dnes není nic kritického.")

        self.content.setText("<br>".join(lines))
