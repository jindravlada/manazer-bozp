"""Editor ústního okruhu."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.widgets.dialog_utils import (
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.editor_dialog_controller import EditorDialogController
from moduly.testy.constants import (
    MODULE_NAME,
    TOPIC_DIALOG_TITLE_EDIT,
    TOPIC_DIALOG_TITLE_NEW,
)
from moduly.testy.modely.oral_question_topic import OralQuestionTopic
from moduly.testy.sluzby.oral_question_topic_service import (
    OralQuestionTopicError,
    oral_question_topic_service,
)


class OralQuestionTopicDialog(QDialog):
    def __init__(self, parent=None, topic: OralQuestionTopic | None = None):
        super().__init__(parent)
        self.topic_id = topic.id if topic is not None else None
        self.saved_topic_id: int | None = self.topic_id
        is_new = topic is None

        self.setWindowTitle(TOPIC_DIALOG_TITLE_NEW if is_new else TOPIC_DIALOG_TITLE_EDIT)
        configure_resizable_form_dialog(
            self,
            width=560,
            height=420,
            min_width=420,
            min_height=320,
        )

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.name = QLineEdit()
        self.description = QPlainTextEdit()
        self.description.setMinimumHeight(96)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Název:", self.name)
        form.addRow("Popis:", self.description)
        form.addRow("", self.active_checkbox)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)
        buttons = create_save_cancel_box(self, is_new=is_new)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=is_new,
            title=self.windowTitle(),
        )
        self._editor.set_snapshot_provider(self._snapshot)
        self._editor.install_auto_dirty_tracking()

        if topic is not None:
            self.name.setText(topic.name)
            self.description.setPlainText(topic.description or "")
            self.active_checkbox.setChecked(topic.active)

        self._editor.capture_baseline()

    def accept(self) -> None:
        data = self.get_data()
        try:
            if self.topic_id is None:
                created = oral_question_topic_service.create_topic(**data)
                self.saved_topic_id = created.id
            else:
                updated = oral_question_topic_service.update_topic(
                    self.topic_id,
                    **data,
                )
                self.saved_topic_id = updated.id
        except OralQuestionTopicError as error:
            QMessageBox.warning(self, MODULE_NAME, str(error))
            return
        super().accept()

    def get_data(self) -> dict:
        return {
            "name": self.name.text(),
            "description": self.description.toPlainText(),
            "active": self.active_checkbox.isChecked(),
        }

    def _snapshot(self) -> tuple:
        return (
            self.name.text(),
            self.description.toPlainText(),
            self.active_checkbox.isChecked(),
        )
