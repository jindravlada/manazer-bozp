from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)

from moduly.rizeni_rizik.constants import format_inventory_item_source_label
from moduly.rizeni_rizik.constants_library import (
    CATALOG_COMPARE_WITH_MASTER_DIALOG_TITLE,
    CATALOG_COMPARE_WITH_MASTER_INTRO,
    CATALOG_COMPARE_WITH_MASTER_NO_DIFFERENCES,
    CATALOG_COMPARE_WITH_MASTER_VERSION_NOTE,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_instance_compare_service import (
    CatalogInstanceCompareResult,
    hazard_catalog_instance_compare_service,
)


class HazardCatalogInstanceCompareDialog(QDialog):
    def __init__(self, parent=None, *, result: CatalogInstanceCompareResult):
        super().__init__(parent)
        self.result = result

        self.setWindowTitle(CATALOG_COMPARE_WITH_MASTER_DIALOG_TITLE)
        self.resize(760, 520)

        layout = QVBoxLayout(self)

        header_parts = [
            f"Zdroj rizika: {result.inventory_item_name}",
            f"Master: {result.template_name}",
            format_inventory_item_source_label(
                source_template_id=result.template_id,
                source_template_version=result.source_template_version,
            ),
        ]
        header = QLabel("\n".join(part for part in header_parts if part))
        header.setWordWrap(True)
        layout.addWidget(header)

        intro = QLabel(CATALOG_COMPARE_WITH_MASTER_INTRO)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        if result.master_version_differs:
            version_note = QLabel(
                CATALOG_COMPARE_WITH_MASTER_VERSION_NOTE.format(
                    master_version=result.master_version,
                    source_version=result.source_template_version,
                )
            )
            version_note.setWordWrap(True)
            layout.addWidget(version_note)

        self.lines_view = QPlainTextEdit()
        self.lines_view.setReadOnly(True)
        self.lines_view.setMinimumHeight(280)
        if result.has_differences:
            formatted_lines = hazard_catalog_instance_compare_service.format_lines(result)
            self.lines_view.setPlainText("\n".join(formatted_lines))
        else:
            self.lines_view.setPlainText(CATALOG_COMPARE_WITH_MASTER_NO_DIFFERENCES)
        layout.addWidget(self.lines_view, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
