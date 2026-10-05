"""Skladba okruhů v editoru Testu: okruh a počet otázek."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.widgets.no_wheel_guards import NoWheelComboBox, NoWheelSpinBox

_ROLE_TOPIC_ID = Qt.ItemDataRole.UserRole


class TestDefinitionCompositionEditor(QWidget):
    """Seznam zařazených okruhů. Nově lze přidat jen okruhy předané jako dostupné."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._available: list[tuple[int, str]] = []
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        add_row = QHBoxLayout()
        self.topic_combo = NoWheelComboBox()
        self.topic_combo.setMinimumWidth(220)
        self.count_spin = NoWheelSpinBox()
        self.count_spin.setRange(1, 999)
        self.count_spin.setValue(1)
        self.add_btn = QPushButton("Přidat")
        add_row.addWidget(self.topic_combo, 1)
        add_row.addWidget(self.count_spin)
        add_row.addWidget(self.add_btn)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Okruh", "Počet", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setMinimumHeight(120)
        self.table.setMaximumHeight(180)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        layout.addLayout(add_row)
        layout.addWidget(self.table)

        self.add_btn.clicked.connect(self.add_current)

    def set_available_topics(self, topics: list[tuple[int, str]]) -> None:
        self._available = list(topics)
        self._reload_combo()

    def set_rows(self, rows: list[tuple[int, str, int]]) -> None:
        self._loading = True
        self.table.setRowCount(0)
        try:
            for topic_id, label, count in rows:
                self._append_row(int(topic_id), label, int(count))
        finally:
            self._loading = False
        self._reload_combo()
        self._emit_changed()

    def rows(self) -> list[tuple[int, int]]:
        result: list[tuple[int, int]] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            spin = self.table.cellWidget(row, 1)
            if item is None or not isinstance(spin, NoWheelSpinBox):
                continue
            result.append((int(item.data(_ROLE_TOPIC_ID)), int(spin.value())))
        return result

    def topic_labels(self) -> list[str]:
        labels: list[str] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                labels.append(item.text())
        return labels

    def add_current(self) -> None:
        topic_id = self.topic_combo.currentData()
        if topic_id is None:
            return
        self._append_row(int(topic_id), self.topic_combo.currentText(), self.count_spin.value())
        self._reload_combo()
        self._emit_changed()

    def _append_row(self, topic_id: int, label: str, count: int) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        item = QTableWidgetItem(label)
        item.setData(_ROLE_TOPIC_ID, int(topic_id))
        self.table.setItem(row, 0, item)
        spin = NoWheelSpinBox()
        spin.setRange(1, 999)
        spin.setValue(max(1, int(count)))
        spin.valueChanged.connect(self._emit_changed)
        self.table.setCellWidget(row, 1, spin)
        remove = QPushButton("Odebrat")
        remove.clicked.connect(lambda _checked=False, current=topic_id: self._remove(current))
        self.table.setCellWidget(row, 2, remove)

    def _remove(self, topic_id: int) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and int(item.data(_ROLE_TOPIC_ID) or 0) == int(topic_id):
                self.table.removeRow(row)
                break
        self._reload_combo()
        self._emit_changed()

    def _reload_combo(self) -> None:
        used = {topic_id for topic_id, _count in self.rows()}
        self.topic_combo.blockSignals(True)
        self.topic_combo.clear()
        for topic_id, name in self._available:
            if topic_id in used:
                continue
            self.topic_combo.addItem(name, int(topic_id))
        self.topic_combo.blockSignals(False)
        self.add_btn.setEnabled(self.topic_combo.count() > 0)

    def _emit_changed(self, *_args) -> None:
        if self._loading:
            return
        self.changed.emit()
