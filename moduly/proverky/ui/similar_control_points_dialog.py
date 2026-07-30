"""Dialog výsledků podobných kontrolních otázek (SIMILARITY-1)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moduly.proverky.sluzby.control_point_similarity_service import (
    ControlPointSimilarityMatch,
)


class SimilarControlPointsDialog(QDialog):
    """Modální přehled podobných kontrolních otázek."""

    def __init__(
        self,
        parent: QWidget | None,
        *,
        matches: list[ControlPointSimilarityMatch],
        on_open=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Podobné kontrolní otázky")
        self.setModal(True)
        self.resize(820, 420)

        self._matches = list(matches)
        self._on_open = on_open
        self.opened_match: ControlPointSimilarityMatch | None = None

        layout = QVBoxLayout(self)

        if not self._matches:
            empty = QLabel("Nebyly nalezeny žádné podobné kontrolní otázky.")
            empty.setWordWrap(True)
            empty.setObjectName("InfoText")
            layout.addWidget(empty)
        else:
            hint = QLabel(
                "Nalezené podobnosti jsou pouze upozorněním. "
                "Rozhodnutí o úpravě ponechte na sobě — nic se neslučuje automaticky."
            )
            hint.setWordWrap(True)
            hint.setObjectName("InfoText")
            layout.addWidget(hint)

            self.table = QTableWidget(len(self._matches), 4)
            self.table.setHorizontalHeaderLabels(
                ["Podobnost", "Kontrolní otázka", "Umístění", "Akce"]
            )
            self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
            self.table.verticalHeader().setVisible(False)
            header = self.table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

            for row, item in enumerate(self._matches):
                similarity = (
                    f"{item.match.score_percent} % — {item.match.match_label}"
                )
                self.table.setItem(row, 0, QTableWidgetItem(similarity))
                self.table.setItem(row, 1, QTableWidgetItem(item.match.text))
                self.table.setItem(row, 2, QTableWidgetItem(item.location_label))

                action_host = QWidget()
                action_layout = QHBoxLayout(action_host)
                action_layout.setContentsMargins(4, 2, 4, 2)
                open_btn = QPushButton("Otevřít")
                open_btn.clicked.connect(
                    lambda _checked=False, match=item: self._open_match(match)
                )
                action_layout.addWidget(open_btn)
                action_layout.addStretch()
                self.table.setCellWidget(row, 3, action_host)

            layout.addWidget(self.table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.setText("Zavřít")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _open_match(self, match: ControlPointSimilarityMatch) -> None:
        self.opened_match = match
        if self._on_open is not None:
            self._on_open(match)
        self.accept()
