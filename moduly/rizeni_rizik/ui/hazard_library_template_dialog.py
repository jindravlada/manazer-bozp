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
from core.widgets.editor_dialog_controller import (
    configure_editor_close_button,
    confirm_unsaved_editor_close,
)
from moduly.rizeni_rizik.constants_library import (
    DEFAULT_HAZARD_LIBRARY_SCOPE,
    DEFAULT_HAZARD_LIBRARY_VERSION,
    HAZARD_LIBRARY_CANCEL_CONFIRM,
    HAZARD_LIBRARY_DIALOG_TITLE,
    HAZARD_LIBRARY_DUPLICATE_CANCEL,
    HAZARD_LIBRARY_DUPLICATE_CREATE_NEW,
    HAZARD_LIBRARY_DUPLICATE_NAME_TEXT,
    HAZARD_LIBRARY_DUPLICATE_NAME_TITLE,
    HAZARD_LIBRARY_DUPLICATE_OPEN_EXISTING,
    HAZARD_LIBRARY_PLACEHOLDER_TEXT,
    HAZARD_LIBRARY_REVISION_FORM_LABEL,
    HAZARD_LIBRARY_REVISION_READ_ONLY_TOOLTIP,
    HAZARD_LIBRARY_SAVE_SUCCESS,
    HAZARD_LIBRARY_TAB_AI_PEER_REVIEW,
    HAZARD_LIBRARY_TAB_BASICS,
    HAZARD_LIBRARY_TAB_CONTENT,
    HAZARD_LIBRARY_TAB_HISTORY,
    HAZARD_LIBRARY_TAB_USAGE,
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
from moduly.rizeni_rizik.ui.hazard_source_category_combo import (
    populate_hazard_source_category_combo,
)


class HazardLibraryTemplateDialog(QDialog):
    def __init__(
        self,
        parent=None,
        template=None,
        *,
        default_category: str | None = None,
        on_template_persisted=None,
    ):
        super().__init__(parent)
        self.template = template
        self.saved_template = template
        self._editor_session: CatalogEditorSession | None = None
        self._basics_dirty = False
        self._closing = False
        self._on_template_persisted = on_template_persisted
        self._allow_duplicate_name = False
        self._default_category = default_category

        self.setWindowTitle(HAZARD_LIBRARY_DIALOG_TITLE)
        self.setMinimumSize(720, 520)

        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        basics = QWidget()
        basics_layout = QVBoxLayout(basics)
        form = QFormLayout()

        self.name = QLineEdit()
        self.category = QComboBox()
        populate_hazard_source_category_combo(
            self.category,
            current_code=(
                template.category if template is not None else default_category
            ),
            include_inactive_current=template is not None,
        )
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

        self.buttons = create_save_cancel_box(self, is_new=template is None)
        self.save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        self.cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if self.save_button is not None:
            self.save_button.clicked.connect(self._save_all)
        if self.cancel_button is not None:
            self.cancel_button.clicked.connect(self._on_cancel_clicked)
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
        elif default_category is not None:
            index = self.category.findData(default_category)
            if index >= 0:
                with QSignalBlocker(self.category):
                    self.category.setCurrentIndex(index)
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
                existing = hazard_library_template_service.find_active_by_name(data["name"])
                if existing is not None and not self._allow_duplicate_name:
                    choice = self._prompt_duplicate_name(existing)
                    if choice == "cancel":
                        return False
                    if choice == "open":
                        self.template = existing
                        self.saved_template = existing
                        self._editor_session = CatalogEditorSession.load(existing.id)
                        self.ai_peer_review_widget.set_package_session(self._editor_session)
                        self._load_template(existing)
                        self._basics_dirty = False
                        self._update_content_tab_enabled()
                        self._sync_content_context()
                        self._sync_ai_peer_review_context()
                        self._update_ai_peer_review_tab_enabled()
                        self._sync_history_context()
                        self._update_history_tab_enabled()
                        self.content_widget.refresh()
                        self.history_widget.refresh()
                        self.ai_peer_review_widget.refresh()
                        configure_editor_close_button(self.cancel_button, is_new=False)
                        self._update_save_enabled()
                        if self._on_template_persisted is not None:
                            self._on_template_persisted(existing)
                        return True
                    self._allow_duplicate_name = True

                self.template = hazard_library_template_service.create_template(
                    **data,
                    allow_duplicate_name=self._allow_duplicate_name,
                )
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
        configure_editor_close_button(self.cancel_button, is_new=False)
        self._update_save_enabled()
        QMessageBox.information(self, HAZARD_LIBRARY_DIALOG_TITLE, HAZARD_LIBRARY_SAVE_SUCCESS)
        if self._on_template_persisted is not None and self.template is not None:
            self._on_template_persisted(self.template)
        return True

    def _prompt_duplicate_name(self, existing) -> str:
        message = QMessageBox(self)
        message.setWindowTitle(HAZARD_LIBRARY_DUPLICATE_NAME_TITLE)
        message.setIcon(QMessageBox.Icon.Question)
        message.setText(HAZARD_LIBRARY_DUPLICATE_NAME_TEXT)
        message.setInformativeText(f"Existující zdroj: {existing.name}")
        open_btn = message.addButton(
            HAZARD_LIBRARY_DUPLICATE_OPEN_EXISTING,
            QMessageBox.ButtonRole.AcceptRole,
        )
        create_btn = message.addButton(
            HAZARD_LIBRARY_DUPLICATE_CREATE_NEW,
            QMessageBox.ButtonRole.ActionRole,
        )
        cancel_btn = message.addButton(
            HAZARD_LIBRARY_DUPLICATE_CANCEL,
            QMessageBox.ButtonRole.RejectRole,
        )
        message.setDefaultButton(open_btn)
        message.exec()
        clicked = message.clickedButton()
        if clicked is open_btn:
            return "open"
        if clicked is create_btn:
            return "create"
        if clicked is cancel_btn:
            return "cancel"
        return "cancel"

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
        return confirm_unsaved_editor_close(self, title=HAZARD_LIBRARY_DIALOG_TITLE)

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
        selected_event_id = self.content_widget._selected_event_id
        self._sync_content_context()
        self.content_widget.refresh()
        self.content_widget.select_event_by_id(selected_event_id)
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
        if decision == "cancel":
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
            if decision == "cancel":
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
