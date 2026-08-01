"""Dialog správy již zkontrolovaných dvojic podobných záznamů (SIMILARITY-UX-8/9)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.shared.sluzby.similarity_checked_pair_service import (
    SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
    similarity_checked_pair_service,
)
from moduly.proverky.sluzby.control_point_similarity_service import (
    collect_control_point_candidates,
)

_ROLE_PAIR_IDS = Qt.ItemDataRole.UserRole


class SimilarityCheckedPairsDialog(QDialog):
    """Přehled dvojic označených jako zkontrolované (správa oddělená od analýzy)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Správa zkontrolovaných dvojic")
        self.setModal(True)
        self.resize(900, 520)

        root = QVBoxLayout(self)
        hint = QLabel(
            "Dvojice, které jste označili jako zkontrolované (nejde o skutečné "
            "duplicity). Vrácením do analýzy se znovu nabídnou při příští kontrole."
        )
        hint.setWordWrap(True)
        hint.setObjectName("InfoText")
        root.addWidget(hint)

        self._count_label = QLabel()
        self._count_label.setObjectName("InfoText")
        root.addWidget(self._count_label)

        self._empty_label = QLabel("Žádné zkontrolované dvojice.")
        self._empty_label.setObjectName("InfoText")
        self._empty_label.setVisible(False)
        root.addWidget(self._empty_label)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            [
                "První otázka",
                "Umístění první",
                "Druhá otázka",
                "Umístění druhé",
                "Označeno",
            ]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._update_return_button)
        root.addWidget(self.table, 1)

        buttons = QDialogButtonBox()
        self.return_to_analysis_btn = QPushButton("Vrátit do analýzy")
        self.return_to_analysis_btn.setEnabled(False)
        self.return_to_analysis_btn.clicked.connect(self._return_selected_to_analysis)
        buttons.addButton(
            self.return_to_analysis_btn, QDialogButtonBox.ButtonRole.ActionRole
        )
        close_btn = buttons.addButton(
            "Zavřít", QDialogButtonBox.ButtonRole.RejectRole
        )
        close_btn.clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self.refresh()

    def refresh(self) -> None:
        records = similarity_checked_pair_service.repository.list_for_type(
            SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT
        )
        by_id = {
            item.composite_id: item
            for item in collect_control_point_candidates(include_inactive=True)
        }

        self.table.setRowCount(0)
        if not records:
            self._empty_label.setVisible(True)
            self.table.setVisible(False)
            self._update_count(0)
            self._update_return_button()
            return

        self._empty_label.setVisible(False)
        self.table.setVisible(True)
        self.table.setRowCount(len(records))
        for row, record in enumerate(records):
            left = by_id.get(record.left_entity_id)
            right = by_id.get(record.right_entity_id)
            left_text = left.text if left is not None else record.left_entity_id
            right_text = right.text if right is not None else record.right_entity_id
            left_loc = left.location_label if left is not None else ""
            right_loc = right.location_label if right is not None else ""
            checked_at = ""
            if record.checked_at is not None:
                checked_at = record.checked_at.strftime("%d.%m.%Y %H:%M")

            first = QTableWidgetItem(left_text)
            first.setData(
                _ROLE_PAIR_IDS,
                (record.left_entity_id, record.right_entity_id),
            )
            self.table.setItem(row, 0, first)
            self.table.setItem(row, 1, QTableWidgetItem(left_loc))
            self.table.setItem(row, 2, QTableWidgetItem(right_text))
            self.table.setItem(row, 3, QTableWidgetItem(right_loc))
            self.table.setItem(row, 4, QTableWidgetItem(checked_at))

        self._update_count(len(records))
        self._update_return_button()

    def _update_count(self, total: int) -> None:
        self._count_label.setText(f"Celkem zkontrolovaných:\n{total}")

    def _selected_pair_ids(self) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        seen: set[int] = set()
        for index in self.table.selectionModel().selectedRows():
            row = index.row()
            if row in seen:
                continue
            seen.add(row)
            item = self.table.item(row, 0)
            if item is None:
                continue
            data = item.data(_ROLE_PAIR_IDS)
            if isinstance(data, tuple) and len(data) == 2:
                pairs.append((str(data[0]), str(data[1])))
        return pairs

    def _update_return_button(self) -> None:
        self.return_to_analysis_btn.setEnabled(bool(self._selected_pair_ids()))

    def _return_selected_to_analysis(self) -> None:
        pairs = self._selected_pair_ids()
        if not pairs:
            return
        for left_id, right_id in pairs:
            similarity_checked_pair_service.unmark_checked(
                SIMILARITY_ENTITY_PROVERKY_CONTROL_POINT,
                left_id,
                right_id,
            )
        self.refresh()
