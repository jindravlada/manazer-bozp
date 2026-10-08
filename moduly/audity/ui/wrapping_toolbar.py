"""Lišta, která drží pořadí ovládacích prvků a při úzkém okně je zalamuje."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import (
    QLayout,
    QLayoutItem,
    QSizePolicy,
    QSpacerItem,
    QStyle,
    QWidget,
)


class _FlowLayout(QLayout):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(_style_spacing(parent))
        self._items: list[QLayoutItem] = []

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientations:
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            if _is_stretch(item):
                continue
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(
            margins.left() + margins.right(),
            margins.top() + margins.bottom(),
        )

    def _do_layout(self, rect: QRect, *, test_only: bool) -> int:
        margins = self.contentsMargins()
        available = rect.width() - margins.left() - margins.right()
        if available <= 0:
            available = self._widest_item()
        lines = _break_lines(self._items, available, self.spacing())
        space_y = self.spacing()
        y = rect.y() + margins.top()
        for line in lines:
            line_height = _line_height(line)
            if not test_only:
                _place_line(
                    line,
                    x=rect.x() + margins.left(),
                    y=y,
                    width=available,
                    height=line_height,
                    spacing=self.spacing(),
                )
            y += line_height + space_y
        if lines:
            y -= space_y
        return y - rect.y() + margins.bottom()

    def _widest_item(self) -> int:
        widest = 1
        for item in self._items:
            if _is_stretch(item):
                continue
            widest = max(widest, item.sizeHint().width())
        return widest


class WrappingToolbar(QWidget):
    """Jeden řádek akcí. Při nedostatku šířky pokračuje dalším řádkem."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._flow = _FlowLayout(self)
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def add_widget(self, widget: QWidget) -> None:
        policy = widget.sizePolicy()
        policy.setHorizontalPolicy(QSizePolicy.Policy.Minimum)
        widget.setSizePolicy(policy)
        self._flow.addWidget(widget)

    def add_stretch(self) -> None:
        self._flow.addItem(
            QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        )

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._flow.heightForWidth(width)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.width() <= 0:
            return
        height = self._flow.heightForWidth(self.width())
        if height > 0 and self.minimumHeight() != height:
            self.setMinimumHeight(height)


def _is_stretch(item: QLayoutItem) -> bool:
    spacer = item.spacerItem()
    if spacer is None:
        return False
    return bool(spacer.expandingDirections() & Qt.Orientation.Horizontal)


def _break_lines(
    items: list[QLayoutItem],
    available: int,
    spacing: int,
) -> list[list[QLayoutItem]]:
    lines: list[list[QLayoutItem]] = []
    current: list[QLayoutItem] = []
    used = 0
    for item in items:
        if _is_stretch(item):
            current.append(item)
            continue
        width = item.sizeHint().width()
        extra = spacing if _visible_count(current) else 0
        if current and used + extra + width > available:
            lines.append(current)
            current = [item]
            used = width
        else:
            current.append(item)
            used += extra + width
    if current:
        lines.append(current)
    return lines


def _visible_count(items: list[QLayoutItem]) -> int:
    return sum(1 for item in items if not _is_stretch(item))


def _line_height(items: list[QLayoutItem]) -> int:
    height = 0
    for item in items:
        if _is_stretch(item):
            continue
        height = max(height, item.sizeHint().height())
    return height


def _place_line(
    items: list[QLayoutItem],
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    spacing: int,
) -> None:
    visible = _visible_count(items)
    content = 0
    if visible:
        content = sum(
            item.sizeHint().width() for item in items if not _is_stretch(item)
        )
        content += spacing * (visible - 1)
    leftover = max(0, width - content)
    stretches = [item for item in items if _is_stretch(item)]
    stretch_width = leftover // len(stretches) if stretches else 0
    cursor = x
    placed_visible = 0
    for item in items:
        if _is_stretch(item):
            item.setGeometry(QRect(cursor, y, stretch_width, height))
            cursor += stretch_width
            continue
        hint = item.sizeHint()
        if placed_visible:
            cursor += spacing
        item.setGeometry(QRect(cursor, y, hint.width(), hint.height()))
        cursor += hint.width()
        placed_visible += 1


def _style_spacing(parent: QWidget | None) -> int:
    if parent is None:
        return 6
    metric = parent.style().pixelMetric(
        QStyle.PixelMetric.PM_LayoutHorizontalSpacing,
        None,
        parent,
    )
    return 6 if metric < 0 else metric
