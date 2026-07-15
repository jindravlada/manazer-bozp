from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
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
    DEFAULT_HAZARD_LIBRARY_VERSION,
    HAZARD_LIBRARY_DIALOG_TITLE,
    HAZARD_LIBRARY_PLACEHOLDER_TEXT,
    HAZARD_LIBRARY_SCOPE_ALL,
    HAZARD_LIBRARY_SCOPE_LABELS,
    HAZARD_LIBRARY_SCOPE_MANUAL,
    HAZARD_LIBRARY_SCOPE_SELECTED,
    HAZARD_LIBRARY_SCOPES,
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


class HazardLibraryTemplateDialog(QDialog):
    def __init__(self, parent=None, template=None):
        super().__init__(parent)
        self.template = template
        self.saved_template = template
        self._content_changed = False

        self.setWindowTitle(HAZARD_LIBRARY_DIALOG_TITLE)
        self.resize(960, 680)

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
        self.application_scope = QComboBox()
        for scope in HAZARD_LIBRARY_SCOPES:
            self.application_scope.addItem(HAZARD_LIBRARY_SCOPE_LABELS[scope], scope)
        self.version_number = QSpinBox()
        self.version_number.setRange(1, 9999)
        self.version_number.setValue(DEFAULT_HAZARD_LIBRARY_VERSION)
        self.note = QTextEdit()
        self.note.setMinimumHeight(60)
        self.active_checkbox = QCheckBox("Aktivní")
        self.active_checkbox.setChecked(True)

        form.addRow("Název *:", self.name)
        form.addRow("Kategorie *:", self.category)
        form.addRow("Popis:", self.description)
        form.addRow("Rozsah použití *:", self.application_scope)
        form.addRow("Verze:", self.version_number)
        form.addRow("Poznámka:", self.note)
        form.addRow("", self.active_checkbox)

        basics_layout.addLayout(form)

        self.operations_label = QLabel("Vybrané provozy:")
        self.operations_list = QListWidget()
        self.operations_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.operations_list.setMinimumHeight(160)
        basics_layout.addWidget(self.operations_label)
        basics_layout.addWidget(self.operations_list)

        self.tabs.addTab(basics, HAZARD_LIBRARY_TAB_BASICS)

        self.content_widget = HazardLibraryTemplateContentWidget()
        self.content_tab_index = self.tabs.addTab(self.content_widget, HAZARD_LIBRARY_TAB_CONTENT)

        self.ai_peer_review_widget = AiPeerReviewWidget(
            provider=hazard_catalog_source_peer_review_provider,
            export_dialog_config=catalog_peer_review_export_dialog_config(),
            resolve_exposed_groups=False,
            evidence_only_import=True,
        )
        self.ai_peer_review_tab_index = self.tabs.addTab(
            self.ai_peer_review_widget,
            HAZARD_LIBRARY_TAB_AI_PEER_REVIEW,
        )

        for tab_label in (
            HAZARD_LIBRARY_TAB_USAGE,
            HAZARD_LIBRARY_TAB_HISTORY,
        ):
            placeholder = QWidget()
            placeholder_layout = QVBoxLayout(placeholder)
            placeholder_layout.addWidget(QLabel(HAZARD_LIBRARY_PLACEHOLDER_TEXT))
            placeholder_layout.addStretch()
            index = self.tabs.addTab(placeholder, tab_label)
            self.tabs.setTabEnabled(index, False)

        layout.addWidget(self.tabs)

        buttons = create_save_cancel_box(self)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_button is not None:
            save_button.clicked.connect(self._save_basics)
        if cancel_button is not None:
            cancel_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self.application_scope.currentIndexChanged.connect(self._update_operations_enabled)
        self.content_widget.content_changed.connect(self._on_content_changed)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._load_operations()
        if template is not None:
            self._load_template(template)
        else:
            self._update_operations_enabled()
        self._sync_content_context()
        self._update_content_tab_enabled()
        self._sync_ai_peer_review_context()
        self._update_ai_peer_review_tab_enabled()

    def _load_operations(self) -> None:
        self.operations_list.clear()
        for operation in hazard_library_template_service.get_active_operations():
            item = QListWidgetItem(operation.name)
            item.setData(256, operation.id)
            self.operations_list.addItem(item)

    def _load_template(self, template) -> None:
        self.name.setText(template.name)
        category_index = self.category.findData(template.category)
        if category_index >= 0:
            self.category.setCurrentIndex(category_index)
        self.description.setPlainText(template.description or "")
        scope_index = self.application_scope.findData(template.application_scope)
        if scope_index >= 0:
            self.application_scope.setCurrentIndex(scope_index)
        self.version_number.setValue(template.version_number)
        self.note.setPlainText(template.note or "")
        self.active_checkbox.setChecked(bool(template.active))

        selected_ids = set(hazard_library_template_service.get_operation_ids(template.id))
        for index in range(self.operations_list.count()):
            item = self.operations_list.item(index)
            if item.data(256) in selected_ids:
                item.setSelected(True)
        self._update_operations_enabled()

    def _update_operations_enabled(self) -> None:
        selected_scope = self.application_scope.currentData()
        enabled = selected_scope == HAZARD_LIBRARY_SCOPE_SELECTED
        self.operations_label.setEnabled(enabled)
        self.operations_list.setEnabled(enabled)
        if not enabled:
            self.operations_list.clearSelection()

    def _selected_operation_ids(self) -> list[int]:
        return [
            item.data(256)
            for item in self.operations_list.selectedItems()
            if item.data(256) is not None
        ]

    def get_data(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "category": self.category.currentData(),
            "description": self.description.toPlainText().strip(),
            "application_scope": self.application_scope.currentData(),
            "version_number": self.version_number.value(),
            "note": self.note.toPlainText().strip(),
            "active": self.active_checkbox.isChecked(),
            "operation_ids": self._selected_operation_ids(),
        }

    def _save_basics(self) -> None:
        data = self.get_data()
        template_id = self.template.id if self.template is not None else None
        preview = hazard_library_template_service.preview_scope_change(
            template_id,
            new_scope=data["application_scope"],
            operation_ids=data["operation_ids"],
        )
        if preview is not None and preview.removed_operation_names:
            names = ", ".join(preview.removed_operation_names)
            reply = QMessageBox.question(
                self,
                HAZARD_LIBRARY_DIALOG_TITLE,
                (
                    "Změna rozsahu odstraní vazby na tyto provozy:\n"
                    f"{names}\n\nPokračovat?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

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
        QMessageBox.information(self, HAZARD_LIBRARY_DIALOG_TITLE, "Základní údaje byly uloženy.")

    def _update_content_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(self.content_tab_index, self.template is not None)

    def _update_ai_peer_review_tab_enabled(self) -> None:
        self.tabs.setTabEnabled(self.ai_peer_review_tab_index, self.template is not None)

    def _sync_ai_peer_review_context(self) -> None:
        template_id = self.template.id if self.template is not None else None
        self.ai_peer_review_widget.set_source(template_id)

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

    def _finalize_content_version(self) -> None:
        if self.template is None or not self._content_changed:
            return
        updated = hazard_library_template_service.bump_content_version(self.template.id)
        if updated is not None:
            self.template = updated
            self.saved_template = updated
            self.version_number.setValue(updated.version_number)
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
