from PySide6.QtCore import QSignalBlocker
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

from core.ai_oponentni.ui.ai_peer_review_widget import (
    AiPeerReviewWidget,
    catalog_peer_review_export_dialog_config,
)
from core.widgets.dialog_utils import create_save_cancel_box
from moduly.rizeni_rizik.constants import (
    HAZARD_INVENTORY_CATEGORIES,
    HAZARD_INVENTORY_CATEGORY_LABELS,
)
from moduly.rizeni_rizik.constants_library import (
    DEFAULT_HAZARD_LIBRARY_SCOPE,
    DEFAULT_HAZARD_LIBRARY_VERSION,
    HAZARD_LIBRARY_CANCEL_CONFIRM,
    HAZARD_LIBRARY_DIALOG_TITLE,
    HAZARD_LIBRARY_PLACEHOLDER_TEXT,
    HAZARD_LIBRARY_REVISION_FORM_LABEL,
    HAZARD_LIBRARY_REVISION_READ_ONLY_TOOLTIP,
    HAZARD_LIBRARY_SAVE_SUCCESS,
    HAZARD_LIBRARY_TAB_AI_PEER_REVIEW,
    HAZARD_LIBRARY_TAB_BASICS,
    HAZARD_LIBRARY_TAB_CONTENT,
    HAZARD_LIBRARY_TAB_HISTORY,
    HAZARD_LIBRARY_TAB_USAGE,
    HAZARD_LIBRARY_UNSAVED_DISCARD,
    HAZARD_LIBRARY_UNSAVED_PROMPT,
    HAZARD_LIBRARY_UNSAVED_SAVE,
    HAZARD_LIBRARY_UNSAVED_STAY,
)
from moduly.rizeni_rizik.sluzby.catalog_editor_session import CatalogEditorSession
from moduly.rizeni_rizik.sluzby.hazard_catalog_source_peer_review_provider import (
    hazard_catalog_source_peer_review_provider,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_service import (
    HazardLibraryTemplateError,
    hazard_library_template_service,
)
from moduly.rizeni_rizik.ui.hazard_library_template_content_widget import (
    HazardLibraryTemplateContentWidget,
)
from moduly.rizeni_rizik.ui.hazard_library_template_revision_history_widget import (
    HazardLibraryTemplateRevisionHistoryWidget,
)


class HazardLibraryTemplateDialog(QDialog):
    def __init__(self, parent=None, template=None):
        super().__init__(parent)
        self.template = template
        self.saved_template = template
        self._editor_session: CatalogEditorSession | None = None
        self._basics_dirty = False
        self._closing = False

        self.setWindowTitle(HAZARD_LIBRARY_DIALOG_TITLE)
        self.setMinimumSize(720, 520)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        basics = QWidget()
        basics_layout = QVBoxLayout(basics)
        form = QFormLayout()

        self.name = QLineEdit()
        self.category = QComboBox()
        for category in HAZARD_INVENTORY_CATEGORIES:
            self.category.addItem(HAZARD_INVENTORY_CATEGORY_LABELS[category], category)
        self.description = QTextEdit()
        self.description.setMinimumHeight(80)
        self.version_number = QSpinBox()
        self.version_number.setRange(1, 9999)
        self.version_number.setValue(DEFAULT_HAZARD_LIBRARY_VERSION)
        self.version_number.setReadOnly(True)
        self.version_number.setToolTip(HAZARD_LIBRARY_REVISION_READ_ONLY_TOOLTIP)
        self.note = QTextEdit()
        self.note.setMinimumHeight(60)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Název *:", self.name)
        form.addRow("Kategorie *:", self.category)
        form.addRow("Popis:", self.description)
        form.addRow(HAZARD_LIBRARY_REVISION_FORM_LABEL, self.version_number)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.active_checkbox)

        basics_layout.addLayout(form)
        basics_layout.addStretch()
        self.tabs.addTab(basics, HAZARD_LIBRARY_TAB_BASICS)

        self.content_widget = HazardLibraryTemplateContentWidget()
        self.content_tab_index = self.tabs.addTab(self.content_widget, HAZARD_LIBRARY_TAB_CONTENT)

        self.ai_peer_review_widget = AiPeerReviewWidget(
            provider=hazard_catalog_source_peer_review_provider,
            export_dialog_config=catalog_peer_review_export_dialog_config(),
            resolve_exposed_groups=False,
            evidence_only_import=True,
            on_catalog_incorporated=self._on_catalog_proposals_incorporated,
            package_incorporate_handler=self._incorporate_package_into_working_copy,
        )
        self.ai_peer_review_tab_index = self.tabs.addTab(
            self.ai_peer_review_widget,
            HAZARD_LIBRARY_TAB_AI_PEER_REVIEW,
        )

        self.history_widget = HazardLibraryTemplateRevisionHistoryWidget()
        self.history_tab_index = self.tabs.addTab(self.history_widget, HAZARD_LIBRARY_TAB_HISTORY)

        usage_placeholder = QWidget()
        usage_placeholder_layout = QVBoxLayout(usage_placeholder)
        usage_placeholder_layout.addWidget(QLabel(HAZARD_LIBRARY_PLACEHOLDER_TEXT))
        usage_placeholder_layout.addStretch()
        usage_tab_index = self.tabs.addTab(usage_placeholder, HAZARD_LIBRARY_TAB_USAGE)
        self.tabs.setTabEnabled(usage_tab_index, False)

        layout.addWidget(self.tabs)

        self.buttons = create_save_cancel_box(self)
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if self.save_button is not None:
            self.save_button.clicked.connect(self._save_all)
        if cancel_button is not None:
            cancel_button.clicked.connect(self._on_cancel_clicked)
        layout.addWidget(self.buttons)

        self.content_widget.content_changed.connect(self._on_content_changed)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.name.textChanged.connect(self._on_basics_edited)
        self.category.currentIndexChanged.connect(self._on_basics_edited)
        self.description.textChanged.connect(self._on_basics_edited)
        self.note.textChanged.connect(self._on_basics_edited)
        self.active_checkbox.toggled.connect(self._on_basics_edited)

        if template is not None:
            self._load_template(template)
            self._editor_session = CatalogEditorSession.load(template.id)
            self.ai_peer_review_widget.set_package_session(self._editor_session)
        self._sync_content_context()
        self._update_content_tab_enabled()
        self._sync_ai_peer_review_context()
        self._update_ai_peer_review_tab_enabled()
        self._sync_history_context()
        self._update_history_tab_enabled()
        self._update_save_enabled()

    @property
    def _content_store(self):
        """Kompatibilita pro content widget / find_catalog_working_copy."""
        if self._editor_session is None:
            return None
        return self._editor_session.content

    @_content_store.setter
    def _content_store(self, value) -> None:
        # Zachováno kvůli starším testům, které nastavují _content_store přímo.
        if value is None:
            self._editor_session = None
            self.ai_peer_review_widget.set_package_session(None)
            return
        if self._editor_session is None:
            self._editor_session = CatalogEditorSession(value.template_id, value)
            self._editor_session._load_pending_packages_from_db()
            self.ai_peer_review_widget.set_package_session(self._editor_session)
        else:
            self._editor_session.content = value

    def _load_template(self, template) -> None:
        with QSignalBlocker(self.name), QSignalBlocker(self.category), QSignalBlocker(
            self.description,
        ), QSignalBlocker(self.note), QSignalBlocker(self.active_checkbox):
            self.name.setText(template.name)
            category_index = self.category.findData(template.category)
            if category_index >= 0:
                self.category.setCurrentIndex(category_index)
            self.description.setPlainText(template.description or "")
            self.version_number.setValue(template.version_number)
            self.note.setPlainText(template.note or "")
            self.active_checkbox.setChecked(bool(template.active))
        self._basics_dirty = False

    def get_data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "category": self.category.currentData(),
            "description": self.description.toPlainText().strip(),
            "application_scope": DEFAULT_HAZARD_LIBRARY_SCOPE,
            "version_number": self.version_number.value(),
            "note": self.note.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
            "operation_ids": [],
        }

    def is_dirty(self) -> bool:
        session_dirty = self._editor_session is not None and self._editor_session.is_dirty
        return self._basics_dirty or session_dirty

    def _update_save_enabled(self) -> None:
        if self.save_button is not None:
            self.save_button.setEnabled(self.is_dirty() or self.template is None)

    def _on_basics_edited(self, *_args) -> None:
        self._basics_dirty = True
        self._update_save_enabled()

    def _on_content_changed(self) -> None:
        self._update_save_enabled()

    def _save_all(self) -> bool:
        data = self.get_data()
        try:
            if self.template is None:
                self.template = hazard_library_template_service.create_template(**data)
                self._editor_session = CatalogEditorSession.load(self.template.id)
                self.ai_peer_review_widget.set_package_session(self._editor_session)
                self._basics_dirty = False
            else:
                if self._editor_session is None:
                    self._editor_session = CatalogEditorSession.load(self.template.id)
                    self.ai_peer_review_widget.set_package_session(self._editor_session)
                session_dirty = self._editor_session.is_dirty
                if session_dirty:
                    updated = self._editor_session.commit(
                        basics=data if self._basics_dirty else None,
                        bump_revision=True,
                    )
                    self.template = updated
                elif self._basics_dirty:
                    updated = hazard_library_template_service.update_template(
                        self.template.id,
                        **data,
                    )
                    if updated is not None:
                        self.template = updated
                self._basics_dirty = False
        except HazardLibraryTemplateError as error:
            QMessageBox.warning(self, HAZARD_LIBRARY_DIALOG_TITLE, str(error))
            self.tabs.setCurrentIndex(0)
            return False
        except Exception as error:
            QMessageBox.warning(self, HAZARD_LIBRARY_DIALOG_TITLE, str(error))
            return False

        self.saved_template = self.template
        self._load_template(self.template)
        self._update_content_tab_enabled()
        self._sync_content_context()
        self._sync_ai_peer_review_context()
        self._update_ai_peer_review_tab_enabled()
        self._sync_history_context()
        self._update_history_tab_enabled()
        self.content_widget.refresh()
        self.history_widget.refresh()
        self.ai_peer_review_widget.refresh()
        self._update_save_enabled()
        QMessageBox.information(self, HAZARD_LIBRARY_DIALOG_TITLE, HAZARD_LIBRARY_SAVE_SUCCESS)
        return True

    def _discard_working_copy(self) -> None:
        self._editor_session = None
        self.ai_peer_review_widget.set_package_session(None)
        self._basics_dirty = False

    def _on_cancel_clicked(self) -> None:
        if self.is_dirty():
            answer = QMessageBox.question(
                self,
                HAZARD_LIBRARY_DIALOG_TITLE,
                HAZARD_LIBRARY_CANCEL_CONFIRM,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self._discard_working_copy()
        self._closing = True
        self.reject()

    def _prompt_unsaved_close(self) -> str:
        message = QMessageBox(self)
        message.setWindowTitle(HAZARD_LIBRARY_DIALOG_TITLE)
        message.setText(HAZARD_LIBRARY_UNSAVED_PROMPT)
        message.setIcon(QMessageBox.Icon.Question)
        save_btn = message.addButton(
            HAZARD_LIBRARY_UNSAVED_SAVE,
            QMessageBox.ButtonRole.AcceptRole,
        )
        discard_btn = message.addButton(
            HAZARD_LIBRARY_UNSAVED_DISCARD,
            QMessageBox.ButtonRole.DestructiveRole,
        )
        stay_btn = message.addButton(
            HAZARD_LIBRARY_UNSAVED_STAY,
            QMessageBox.ButtonRole.RejectRole,
        )
        message.setDefaultButton(stay_btn)
        message.exec()
        clicked = message.clickedButton()
        if clicked is save_btn:
            return "save"
        if clicked is discard_btn:
            return "discard"
        return "stay"

    def _update_content_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(self.content_tab_index, self.template is not None)

    def _update_ai_peer_review_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(self.ai_peer_review_tab_index, self.template is not None)

    def _update_history_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(self.history_tab_index, self.template is not None)

    def _sync_history_context(self) -> None:
        template_id = self.template.id if self.template is not None else None
        self.history_widget.set_template_id(template_id)

    def _sync_ai_peer_review_context(self) -> None:
        template_id = self.template.id if self.template is not None else None
        self.ai_peer_review_widget.set_package_session(self._editor_session)
        self.ai_peer_review_widget.set_source(template_id)

    def _incorporate_package_into_working_copy(
        self,
        *,
        template_id: int,
        package_record_id: int,
        group_assessment_overrides: dict[int, int] | None = None,
    ):
        from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
            hazard_catalog_package_incorporate_service,
        )

        if self._editor_session is None:
            self._editor_session = CatalogEditorSession.load(template_id)
            self.ai_peer_review_widget.set_package_session(self._editor_session)
        return hazard_catalog_package_incorporate_service.incorporate_package_into_working_copy(
            self._editor_session.content,
            template_id=template_id,
            package_record_id=package_record_id,
            group_assessment_overrides=group_assessment_overrides,
            editor_session=self._editor_session,
        )

    def _on_catalog_proposals_incorporated(self, new_revision_number: int | None) -> None:
        if self.template is None:
            return
        if new_revision_number is not None and new_revision_number > 0:
            reloaded = hazard_library_template_service.get_by_id(self.template.id)
            if reloaded is not None:
                self.template = reloaded
                self.saved_template = reloaded
                self.version_number.setValue(reloaded.version_number)
        self.content_widget.refresh()
        self.history_widget.refresh()
        self.ai_peer_review_widget.refresh()
        self._update_save_enabled()

    def _sync_content_context(self) -> None:
        template_id = self.template.id if self.template is not None else None
        read_only = (
            self.template is None
            or not hazard_library_template_service.is_template_content_editable(template_id)
        )
        self.content_widget.set_template(
            template_id,
            read_only=read_only,
            content_store=self._content_store,
        )

    def _on_tab_changed(self, index: int) -> None:
        if index == self.content_tab_index and self.template is not None:
            self._sync_content_context()
            self.content_widget.refresh()
        if index == self.history_tab_index and self.template is not None:
            self.history_widget.refresh()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._closing or not self.is_dirty():
            self._discard_working_copy()
            super().closeEvent(event)
            return
        decision = self._prompt_unsaved_close()
        if decision == "stay":
            event.ignore()
            return
        if decision == "save":
            if not self._save_all():
                event.ignore()
                return
        self._discard_working_copy()
        self._closing = True
        super().closeEvent(event)

    def reject(self) -> None:
        if self._closing:
            super().reject()
            return
        if self.is_dirty():
            decision = self._prompt_unsaved_close()
            if decision == "stay":
                return
            if decision == "save":
                if not self._save_all():
                    return
            self._discard_working_copy()
        self._closing = True
        super().reject()

    def accept(self) -> None:
        if not self._save_all():
            return
        self._closing = True
        super().accept()
