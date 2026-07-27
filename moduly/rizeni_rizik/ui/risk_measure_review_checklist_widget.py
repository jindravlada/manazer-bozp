from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette, QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from moduly.rizeni_rizik.constants import (
    RISK_MEASURE_REVIEW_CHECKLIST_EMPTY,
    RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT,
    RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT,
    RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED,
)
from moduly.rizeni_rizik.ui.risk_measure_review_item_photos_dialog import (
    RiskMeasureReviewItemPhotosDialog,
)

_ROW_BG_EVEN = QColor("#ffffff")
_ROW_BG_ODD = QColor("#f0f0f0")


def _photo_button_label(count: int) -> str:
    if count <= 0:
        return "📷"
    return f"📷 ({count})"


class RiskMeasureReviewChecklistPointWidget(QFrame):
    """Jeden kontrolní bod checklistu (elektronická evidence)."""

    def __init__(
        self,
        row,
        *,
        row_index: int = 0,
        read_only: bool = False,
        on_changed=None,
        parent=None,
    ):
        super().__init__(parent)
        self.item_id = int(row.item_id)
        self._on_changed = on_changed
        self._read_only = bool(read_only)
        self._photo_count = int(row.photo_count or 0)
        self.setObjectName("riskMeasureReviewChecklistPoint")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAutoFillBackground(True)
        self._apply_row_background(row_index)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        title = (row.measure_title or "—").strip() or "—"
        self.measure_label = QLabel(title)
        self.measure_label.setWordWrap(True)
        self.measure_label.setToolTip(title)
        self.measure_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.measure_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        title_font = QFont(self.measure_label.font())
        title_font.setBold(True)
        self.measure_label.setFont(title_font)
        layout.addWidget(self.measure_label)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)

        self.compliant_radio = QRadioButton("Vyhovuje")
        self.non_compliant_radio = QRadioButton("Nevyhovuje")
        # Bez autoExclusive – výchozí stav může zůstat bez výběru.
        self.compliant_radio.setAutoExclusive(False)
        self.non_compliant_radio.setAutoExclusive(False)
        self._result_group = QButtonGroup(self)
        self._result_group.setExclusive(True)
        self._result_group.addButton(self.compliant_radio)
        self._result_group.addButton(self.non_compliant_radio)

        self._apply_result(str(getattr(row, "result", "") or ""))

        self.compliant_radio.setEnabled(not self._read_only)
        self.non_compliant_radio.setEnabled(not self._read_only)
        self.compliant_radio.toggled.connect(self._emit_changed)
        self.non_compliant_radio.toggled.connect(self._emit_changed)
        self._radio_was_checked_on_press = False
        for radio in (self.compliant_radio, self.non_compliant_radio):
            radio.pressed.connect(self._on_radio_pressed)
            radio.clicked.connect(self._on_radio_clicked)

        controls.addWidget(self.compliant_radio)
        controls.addSpacing(16)
        controls.addWidget(self.non_compliant_radio)
        controls.addSpacing(36)

        controls.addWidget(QLabel("Foto"))
        self.photo_btn = QPushButton(_photo_button_label(self._photo_count))
        self.photo_btn.setFlat(True)
        self.photo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.photo_btn.setEnabled(not self._read_only)
        self.photo_btn.clicked.connect(self._open_photos)
        controls.addWidget(self.photo_btn)
        controls.addSpacing(24)

        controls.addWidget(QLabel("Poznámka:"))
        self.note_edit = QLineEdit(row.note or "")
        self.note_edit.setReadOnly(self._read_only)
        self.note_edit.setClearButtonEnabled(False)
        self.note_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.note_edit.textChanged.connect(self._emit_changed)
        controls.addWidget(self.note_edit, 1)

        layout.addLayout(controls)

    def _apply_row_background(self, row_index: int) -> None:
        color = _ROW_BG_ODD if int(row_index) % 2 else _ROW_BG_EVEN
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, color)
        palette.setColor(QPalette.ColorRole.Base, color)
        self.setPalette(palette)

    def _apply_result(self, result: str) -> None:
        self._result_group.setExclusive(False)
        self.compliant_radio.setChecked(False)
        self.non_compliant_radio.setChecked(False)
        if result == RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT:
            self.compliant_radio.setChecked(True)
        elif result == RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT:
            self.non_compliant_radio.setChecked(True)
        # NOT_CHECKED / jiné → nic nezaškrtnuto
        self._result_group.setExclusive(True)

    def _on_radio_pressed(self) -> None:
        button = self.sender()
        self._radio_was_checked_on_press = bool(
            isinstance(button, QRadioButton) and button.isChecked()
        )

    def _on_radio_clicked(self) -> None:
        if self._read_only or not self._radio_was_checked_on_press:
            return
        button = self.sender()
        if not isinstance(button, QRadioButton):
            return
        # Opakovaný klik na už vybrané radio → nehodnoceno.
        self._result_group.setExclusive(False)
        button.setChecked(False)
        self._result_group.setExclusive(True)
        self._emit_changed()

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = bool(read_only)
        self.compliant_radio.setEnabled(not self._read_only)
        self.non_compliant_radio.setEnabled(not self._read_only)
        self.photo_btn.setEnabled(not self._read_only)
        self.note_edit.setReadOnly(self._read_only)

    def get_update(self) -> dict:
        if self.compliant_radio.isChecked():
            result = RISK_MEASURE_REVIEW_ITEM_RESULT_COMPLIANT
        elif self.non_compliant_radio.isChecked():
            result = RISK_MEASURE_REVIEW_ITEM_RESULT_NON_COMPLIANT
        else:
            result = RISK_MEASURE_REVIEW_ITEM_RESULT_NOT_CHECKED
        return {
            "item_id": self.item_id,
            "result": result,
            "compliant": self.compliant_radio.isChecked(),
            "non_compliant": self.non_compliant_radio.isChecked(),
            "note": self.note_edit.text().strip(),
            "photo_count": self._photo_count,
            "has_photo": self._photo_count > 0,
        }

    def _open_photos(self) -> None:
        dialog = RiskMeasureReviewItemPhotosDialog(self, item_id=self.item_id)
        dialog.exec()
        self._photo_count = dialog.photo_count()
        self.photo_btn.setText(_photo_button_label(self._photo_count))
        self._emit_changed()

    def _emit_changed(self, *_args) -> None:
        if callable(self._on_changed):
            self._on_changed()


class RiskMeasureReviewChecklistWidget(QWidget):
    """Checklist: seznam kontrolních bodů bez tabulkové hlavičky."""

    def __init__(self, parent=None, on_changed=None):
        super().__init__(parent)
        self._on_changed = on_changed
        self._read_only = False
        self._points: list[RiskMeasureReviewChecklistPointWidget] = []
        self.setObjectName("riskMeasureReviewChecklist")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.empty_label = QLabel(RISK_MEASURE_REVIEW_CHECKLIST_EMPTY)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.list_host = QWidget()
        self.list_host.setObjectName("riskMeasureReviewChecklistList")
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)
        self.list_layout.addStretch(1)
        self.scroll.setWidget(self.list_host)
        layout.addWidget(self.scroll)

    @property
    def points(self) -> list[RiskMeasureReviewChecklistPointWidget]:
        return list(self._points)

    def point_count(self) -> int:
        return len(self._points)

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = bool(read_only)
        for point in self._points:
            point.set_read_only(self._read_only)

    def load_rows(self, rows) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._points = []

        self.empty_label.setVisible(not rows)
        self.scroll.setVisible(bool(rows))
        if not rows:
            self.list_layout.addStretch(1)
            return

        for index, row in enumerate(rows):
            point = RiskMeasureReviewChecklistPointWidget(
                row,
                row_index=index,
                read_only=self._read_only,
                on_changed=self._emit_changed,
                parent=self.list_host,
            )
            self._points.append(point)
            self.list_layout.addWidget(point)
        self.list_layout.addStretch(1)

    def get_updates(self) -> list[dict]:
        return [point.get_update() for point in self._points]

    def _emit_changed(self, *_args) -> None:
        if callable(self._on_changed):
            self._on_changed()
