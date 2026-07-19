from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from moduly.koordinace_bozp.constants import (
    DEFAULT_MEASURE_CATEGORY,
    MEASURE_CATEGORIES,
    MEASURE_CATEGORY_LABELS,
    MEASURE_EDITOR_HELP_TEXT,
)


class CoordinationMeasureDialog(QDialog):
    """Přidání / úprava organizačního opatření (COORD-009 / UX-COORD-4b)."""

    def __init__(self, parent=None, measure=None):
        super().__init__(parent)
        self.measure = measure
        self.setWindowTitle(
            "Upravit opatření" if measure is not None else "Přidat opatření"
        )
        configure_resizable_form_dialog(
            self,
            width=560,
            height=440,
            min_width=440,
            min_height=340,
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.category = QComboBox()
        for category_id in MEASURE_CATEGORIES:
            self.category.addItem(MEASURE_CATEGORY_LABELS[category_id], category_id)
        self.title = QLineEdit()
        self.description = QTextEdit()
        self.description.setMinimumHeight(110)
        self.help_label = QLabel(MEASURE_EDITOR_HELP_TEXT)
        self.help_label.setWordWrap(True)
        self.help_label.setStyleSheet("color: #555555;")

        form.addRow("Kategorie *:", self.category)
        form.addRow("Krátký název *:", self.title)
        form.addRow("Text opatření:", self.description)
        form.addRow("", self.help_label)
        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if measure is not None:
            index = self.category.findData(measure.category)
            self.category.setCurrentIndex(index if index >= 0 else 0)
            self.title.setText(measure.title or "")
            self.description.setPlainText(measure.description or "")
        else:
            self.category.setCurrentIndex(
                self.category.findData(DEFAULT_MEASURE_CATEGORY)
            )

    def get_data(self) -> dict:
        return {
            "category": self.category.currentData() or DEFAULT_MEASURE_CATEGORY,
            "title": self.title.text(),
            "description": self.description.toPlainText(),
        }
