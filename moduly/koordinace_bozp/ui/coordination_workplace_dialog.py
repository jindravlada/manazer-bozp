from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from moduly.koordinace_bozp.sluzby.coordination_workplace_service import (
    coordination_workplace_service,
)


class CoordinationWorkplaceDialog(QDialog):
    """Přidání / úprava místa výkonu práce (COORD-006)."""

    def __init__(self, parent=None, workplace_link=None):
        super().__init__(parent)
        self.workplace_link = workplace_link
        self._loading = False
        self.setWindowTitle(
            "Upravit místo" if workplace_link is not None else "Přidat místo"
        )
        configure_resizable_form_dialog(self, width=520, height=360, min_width=420, min_height=280)

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.operation = QComboBox()
        self.workplace = QComboBox()
        self.workplace_part = QComboBox()
        self.note = QTextEdit()
        self.note.setMinimumHeight(70)

        form.addRow("Provoz *:", self.operation)
        form.addRow("Pracoviště:", self.workplace)
        form.addRow("Část pracoviště:", self.workplace_part)
        form.addRow("Poznámka:", self.note)
        layout.addWidget(wrap_in_scroll_area(form_host), 1)

        buttons = create_save_cancel_box(self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.operation.currentIndexChanged.connect(self._on_operation_changed)
        self.workplace.currentIndexChanged.connect(self._on_workplace_changed)

        preserve_operation = workplace_link.operation_id if workplace_link else None
        preserve_workplace = workplace_link.workplace_id if workplace_link else None
        preserve_part = workplace_link.workplace_part_id if workplace_link else None
        self._reload_operations(preserve_id=preserve_operation)
        self._reload_workplaces(self.operation.currentData(), preserve_id=preserve_workplace)
        self._reload_parts(self.workplace.currentData(), preserve_id=preserve_part)
        if workplace_link is not None:
            self.note.setPlainText(workplace_link.note or "")

    def _on_operation_changed(self) -> None:
        if self._loading:
            return
        self._reload_workplaces(self.operation.currentData())
        self._reload_parts(None)

    def _on_workplace_changed(self) -> None:
        if self._loading:
            return
        self._reload_parts(self.workplace.currentData())

    def _reload_operations(self, *, preserve_id: int | None = None) -> None:
        self._loading = True
        try:
            self.operation.clear()
            self.operation.addItem("", None)
            for item in coordination_workplace_service.get_operations(include_inactive=False):
                self.operation.addItem(item.name, item.id)
            if preserve_id is not None:
                index = self.operation.findData(preserve_id)
                if index >= 0:
                    self.operation.setCurrentIndex(index)
        finally:
            self._loading = False

    def _reload_workplaces(
        self,
        operation_id: int | None,
        *,
        preserve_id: int | None = None,
    ) -> None:
        self._loading = True
        try:
            self.workplace.clear()
            self.workplace.addItem("", None)
            for item in coordination_workplace_service.get_workplaces_for_operation(
                operation_id,
                include_inactive=False,
            ):
                self.workplace.addItem(item.name, item.id)
            if preserve_id is not None:
                index = self.workplace.findData(preserve_id)
                if index >= 0:
                    self.workplace.setCurrentIndex(index)
            self.workplace.setEnabled(operation_id is not None)
        finally:
            self._loading = False

    def _reload_parts(
        self,
        workplace_id: int | None,
        *,
        preserve_id: int | None = None,
    ) -> None:
        self._loading = True
        try:
            self.workplace_part.clear()
            self.workplace_part.addItem("", None)
            for item in coordination_workplace_service.get_parts_for_workplace(
                workplace_id,
                include_inactive=False,
            ):
                self.workplace_part.addItem(item.name, item.id)
            if preserve_id is not None:
                index = self.workplace_part.findData(preserve_id)
                if index >= 0:
                    self.workplace_part.setCurrentIndex(index)
            self.workplace_part.setEnabled(workplace_id is not None)
        finally:
            self._loading = False

    def get_data(self) -> dict:
        return {
            "operation_id": self.operation.currentData(),
            "workplace_id": self.workplace.currentData(),
            "workplace_part_id": self.workplace_part.currentData(),
            "note": self.note.toPlainText().strip(),
        }
