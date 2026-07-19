from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
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
)


class CoordinationMeasureDialog(QDialog):
    """Přidání / úprava organizačního opatření (COORD-009)."""

    def __init__(self, parent=None, measure=None):
        super().__init__(parent)
        self.measure = measure
        self.setWindowTitle(
            "Upravit opatření" if measure is not None else "Přidat opatření"
        )
        configure_resizable_form_dialog(
            self,
            width=520,
            height=380,
            min_width=420,
            min_height=300,
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.category = QComboBox()
        for category_id in MEASURE_CATEGORIES:
            self.category.addItem(MEASURE_CATEGORY_LABELS[category_id], category_id)
        self.title = QLineEdit()
        self.description = QTextEdit()
        self.description.setMinimumHeight(90)

        form.addRow("Kategorie *:", self.category)
        form.addRow("Název *:", self.title)
        form.addRow("Popis:", self.description)
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
