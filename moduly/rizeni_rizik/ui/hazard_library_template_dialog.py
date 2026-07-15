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
    HAZARD_LIBRARY_DIALOG_TITLE,
    HAZARD_LIBRARY_PLACEHOLDER_TEXT,
    HAZARD_LIBRARY_REVISION_FORM_LABEL,
    HAZARD_LIBRARY_REVISION_READ_ONLY_TOOLTIP,
    HAZARD_LIBRARY_REVISION_REASON_MANUAL,
    HAZARD_LIBRARY_TAB_AI_PEER_REVIEW,
    HAZARD_LIBRARY_TAB_BASICS,
    HAZARD_LIBRARY_TAB_CONTENT,
    HAZARD_LIBRARY_TAB_HISTORY,
    HAZARD_LIBRARY_TAB_USAGE,
)
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
        self._content_changed = False

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

        buttons = create_save_cancel_box(self)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.clicked.connect(self._save_basics)
        if cancel_button is not None:
            cancel_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self.content_widget.content_changed.connect(self._on_content_changed)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        if template is not None:
            self._load_template(template)
        self._sync_content_context()
        self._update_content_tab_enabled()
        self._sync_ai_peer_review_context()
        self._update_ai_peer_review_tab_enabled()
        self._sync_history_context()
        self._update_history_tab_enabled()

    def _load_template(self, template) -> None:
        self.name.setText(template.name)
        category_index = self.category.findData(template.category)
        if category_index >= 0:
            self.category.setCurrentIndex(category_index)
        self.description.setPlainText(template.description or "")
        self.version_number.setValue(template.version_number)
        self.note.setPlainText(template.note or "")
        self.active_checkbox.setChecked(bool(template.active))

    def get_data(self) -> dict:
        # R20e: rozsah použití se v UI nepoužívá; nové zápisy vždy MANUAL bez provozů.
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

    def _save_basics(self) -> None:
        data = self.get_data()
        try:
            if self.template is None:
                self.template = hazard_library_template_service.create_template(**data)
            else:
                updated = hazard_library_template_service.update_template(
                    self.template.id,
                    **data,
                )
                if updated is not None:
                    self.template = updated
        except HazardLibraryTemplateError as error:
            QMessageBox.warning(self, HAZARD_LIBRARY_DIALOG_TITLE, str(error))
            self.tabs.setCurrentIndex(0)
            return

        self.saved_template = self.template
        self._load_template(self.template)
        self._update_content_tab_enabled()
        self._sync_content_context()
        self._sync_ai_peer_review_context()
        self._update_ai_peer_review_tab_enabled()
        self._sync_history_context()
        self._update_history_tab_enabled()
        QMessageBox.information(self, HAZARD_LIBRARY_DIALOG_TITLE, "Základní údaje byly uloženy.")

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
        self.ai_peer_review_widget.set_source(template_id)

    def _on_catalog_proposals_incorporated(self, new_revision_number: int | None) -> None:
        if self.template is None:
            return
        if new_revision_number is not None:
            reloaded = hazard_library_template_service.get_by_id(self.template.id)
            if reloaded is not None:
                self.template = reloaded
                self.saved_template = reloaded
                self.version_number.setValue(reloaded.version_number)
            self._content_changed = False
        self.content_widget.refresh()
        self.history_widget.refresh()
        self.ai_peer_review_widget.refresh()

    def _sync_content_context(self) -> None:
        template_id = self.template.id if self.template is not None else None
        read_only = (
            self.template is None
            or not hazard_library_template_service.is_template_content_editable(template_id)
        )
        self.content_widget.set_template(template_id, read_only=read_only)

    def _on_content_changed(self) -> None:
        if self.template is None:
            return
        self._content_changed = True

    def _on_tab_changed(self, index: int) -> None:
        if index == self.content_tab_index and self.template is not None:
            self._sync_content_context()
            self.content_widget.refresh()
        if index == self.history_tab_index and self.template is not None:
            self.history_widget.refresh()

    def _finalize_content_version(self) -> None:
        if self.template is None or not self._content_changed:
            return
        updated = hazard_library_template_service.bump_content_version(
            self.template.id,
            change_reason=HAZARD_LIBRARY_REVISION_REASON_MANUAL,
        )
        if updated is not None:
            self.template = updated
            self.saved_template = updated
            self.version_number.setValue(updated.version_number)
            self.history_widget.refresh()
        self._content_changed = False

    def closeEvent(self, event: QCloseEvent) -> None:
        self._finalize_content_version()
        super().closeEvent(event)

    def reject(self) -> None:
        self._finalize_content_version()
        super().reject()

    def accept(self) -> None:
        self._finalize_content_version()
        super().reject()
