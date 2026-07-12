"""Read-only záložka Index procesu — rozpad oblastí, index a detail výpočtu."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QGroupBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moduly.pravni_pozadavky.sluzby.legal_requirement_process_status_service import (
    PROCESS_INDEX_PLACEHOLDER,
    ProcessIndexAreaBreakdown,
    ProcessIndexBreakdown,
    legal_requirement_process_status_service,
)

PROCESS_INDEX_DETAIL_PROMPT = "Vyberte oblast pro zobrazení detailu výpočtu."


def _format_index_number(value: float | None) -> str:
    if value is None:
        return PROCESS_INDEX_PLACEHOLDER
    return f"{value:.1f}".replace(".", ",")


class LegalRequirementProcessIndexWidget(QWidget):
    def __init__(self, requirement_id: int | None = None, parent=None):
        super().__init__(parent)
        self.requirement_id = requirement_id
        self._breakdown: ProcessIndexBreakdown | None = None
        self._updating_selection = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        heading = QLabel("Index procesu")
        heading_font = QFont(heading.font())
        heading_font.setBold(True)
        heading.setFont(heading_font)
        layout.addWidget(heading)

        intro = QLabel(
            "Rozpad oblastí Indexu procesu a výsledný index podle dostupných dat."
        )
        intro.setObjectName("InfoText")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Oblast", "Váha (%)", "Skóre", "Přínos"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self.table, 1)

        footer = QWidget()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(0, 8, 0, 0)
        self.total_weight_label = QLabel()
        self.index_label = QLabel()
        index_font = QFont(self.index_label.font())
        index_font.setBold(True)
        self.index_label.setFont(index_font)
        self.coverage_label = QLabel()
        footer_layout.addWidget(self.total_weight_label)
        footer_layout.addWidget(self.index_label)
        footer_layout.addWidget(self.coverage_label)
        layout.addWidget(footer)

        detail_heading = QLabel("Detail výpočtu")
        detail_heading_font = QFont(detail_heading.font())
        detail_heading_font.setBold(True)
        detail_heading.setFont(detail_heading_font)
        layout.addWidget(detail_heading)

        self.detail_panel = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_panel)
        self.detail_layout.setContentsMargins(0, 0, 0, 0)
        self.detail_layout.setSpacing(8)
        layout.addWidget(self.detail_panel, 1)

        self.refresh()

    def set_requirement_id(self, requirement_id: int | None) -> None:
        self.requirement_id = requirement_id
        self.refresh()

    def refresh(self) -> None:
        breakdown = legal_requirement_process_status_service.get_process_index_breakdown(
            self.requirement_id,
        )
        self._breakdown = breakdown
        self._fill_table(breakdown)
        self.total_weight_label.setText(f"Součet vah: {breakdown.total_weight_percent} %")
        if breakdown.index_value is None:
            self.index_label.setText(f"Index procesu:\n{PROCESS_INDEX_PLACEHOLDER}")
        else:
            self.index_label.setText(
                f"Index procesu:\n{_format_index_number(breakdown.index_value)} %"
            )
        self.coverage_label.setText(
            f"Pokrytí dat: {breakdown.data_coverage_percent} %"
        )
        self._select_initial_area()

    def _fill_table(self, breakdown: ProcessIndexBreakdown) -> None:
        self._updating_selection = True
        try:
            self.table.clearSelection()
            self.table.setRowCount(len(breakdown.areas))
            for row, area in enumerate(breakdown.areas):
                values = (
                    area.area_label,
                    str(area.weight_percent),
                    _format_index_number(area.score),
                    _format_index_number(area.contribution),
                )
                for column, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    if column > 0:
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                        )
                    self.table.setItem(row, column, item)
        finally:
            self._updating_selection = False

    def _select_initial_area(self) -> None:
        if self._breakdown is None:
            self._show_detail_prompt()
            return

        for row, area in enumerate(self._breakdown.areas):
            if area.score is not None:
                self.table.selectRow(row)
                return

        self.table.clearSelection()
        self._show_detail_prompt()

    def _on_selection_changed(self) -> None:
        if self._updating_selection:
            return
        if self._breakdown is None:
            self._show_detail_prompt()
            return

        selected_rows = {index.row() for index in self.table.selectedIndexes()}
        if len(selected_rows) != 1:
            self._show_detail_prompt()
            return

        row = next(iter(selected_rows))
        if row < 0 or row >= len(self._breakdown.areas):
            self._show_detail_prompt()
            return

        self._render_area_detail(self._breakdown.areas[row])

    def _clear_detail_panel(self) -> None:
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_detail_prompt(self) -> None:
        self._clear_detail_panel()
        prompt = QLabel(PROCESS_INDEX_DETAIL_PROMPT)
        prompt.setObjectName("InfoText")
        prompt.setWordWrap(True)
        self.detail_layout.addWidget(prompt)
        self.detail_layout.addStretch()

    def _add_line(self, layout: QVBoxLayout, text: str) -> None:
        label = QLabel(text)
        label.setWordWrap(True)
        layout.addWidget(label)

    def _make_group(self, title: str, lines: list[str]) -> QGroupBox | None:
        if not lines:
            return None
        group = QGroupBox(title)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(8, 8, 8, 8)
        group_layout.setSpacing(2)
        for line in lines:
            self._add_line(group_layout, line)
        return group

    def _render_area_detail(self, area: ProcessIndexAreaBreakdown) -> None:
        self._clear_detail_panel()

        area_heading = QLabel(area.area_label)
        area_font = QFont(area_heading.font())
        area_font.setBold(True)
        area_heading.setFont(area_font)
        self.detail_layout.addWidget(area_heading)

        result_group = self._make_group(
            "Výsledek",
            [
                f"Skóre: {_format_index_number(area.score)} %",
                f"Přínos: {_format_index_number(area.contribution)}",
                f"Metodická váha: {area.weight_percent} %",
            ],
        )
        if result_group is not None:
            self.detail_layout.addWidget(result_group)

        detail = area.score_detail
        if detail is None:
            self._add_line(
                self.detail_layout,
                "Pro tuto oblast zatím nejsou k dispozici podklady výpočtu.",
            )
            self.detail_layout.addStretch()
            return

        source_lines: list[str] = []
        if detail.source_entity_label:
            source_lines.append(f"Zdroj: {detail.source_entity_label}")
        if detail.source_entity_date is not None:
            source_lines.append(
                f"Datum: {detail.source_entity_date.strftime('%d.%m.%Y')}"
            )
        if detail.total_count is not None:
            source_lines.append(f"Počet položek: {detail.total_count}")
        source_lines.append(f"Započitatelných hodnocení: {detail.countable_count}")
        source_group = self._make_group("Zdroj dat", source_lines)
        if source_group is not None:
            self.detail_layout.addWidget(source_group)

        status_lines = [
            f"• {item.result_label}: {item.count}"
            for item in detail.result_counts
        ]
        status_group = self._make_group("Počty podle stavů", status_lines)
        if status_group is not None:
            self.detail_layout.addWidget(status_group)

        points_lines = [
            f"• {mapping.result_label}: {mapping.points} b."
            for mapping in detail.point_mappings
        ]
        points_group = self._make_group("Bodové hodnocení", points_lines)
        if points_group is not None:
            self.detail_layout.addWidget(points_group)

        calculation_lines = (
            [detail.calculation_summary] if detail.calculation_summary else []
        )
        calculation_group = self._make_group("Výpočet", calculation_lines)
        if calculation_group is not None:
            self.detail_layout.addWidget(calculation_group)

        self.detail_layout.addStretch()
