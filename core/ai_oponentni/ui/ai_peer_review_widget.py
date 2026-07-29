from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.ai_oponentni.constants import (
    AI_PEER_REVIEW_COL_ACCEPTED,
    AI_PEER_REVIEW_COL_EXPORT_DATE,
    AI_PEER_REVIEW_COL_FILENAME,
    AI_PEER_REVIEW_COL_ID,
    AI_PEER_REVIEW_COL_LOADED,
    AI_PEER_REVIEW_COL_MODEL,
    AI_PEER_REVIEW_COL_PENDING,
    AI_PEER_REVIEW_COL_REJECTED,
    AI_PEER_REVIEW_COL_RESPONSE_DATE,
    AI_PEER_REVIEW_COL_UNASSIGNED,
    AI_PEER_REVIEW_COLUMN_COUNT,
    AI_PEER_REVIEW_DEFAULT_OBJECTIVES,
    AI_PEER_REVIEW_DEFAULT_ROLE,
    AI_PEER_REVIEW_DIALOG_TITLE,
    AI_PEER_REVIEW_EXPORT_BUTTON,
    AI_PEER_REVIEW_EXPORT_SCOPE_FULL,
    AI_PEER_REVIEW_EXPORT_SCOPE_SELECTED,
    AI_PEER_REVIEW_FOCUS_AREA_LABELS,
    AI_PEER_REVIEW_FOCUS_AREAS,
    AI_PEER_REVIEW_IMPORT_BUTTON,
    AI_PEER_REVIEW_IMPORT_INTRO_EVIDENCE,
    AI_PEER_REVIEW_INTRO_TEXT,
    AI_PEER_REVIEW_NO_CHANGE_CANNOT_DECIDE_MESSAGE,
    AI_PEER_REVIEW_NO_CHANGE_FOUND_MESSAGE,
    AI_PEER_REVIEW_OBJECTIVE_LABELS,
    AI_PEER_REVIEW_PACKAGE_TYPE_LABELS,
    AI_PEER_REVIEW_RESPONSE_DIALOG_TITLE,
    AI_PEER_REVIEW_RESPONSE_PLACEHOLDER,
    AI_PEER_REVIEW_ROLE_LABELS,
    AI_PEER_REVIEW_ROLES,
    AI_PEER_REVIEW_TABLE_HEADERS,
    format_ai_peer_review_user_error,
)
from core.ai_oponentni.modely.ai_proposal_package import (
    PACKAGE_STATUS_LABELS,
    PACKAGE_STATUS_PENDING,
)
from core.ai_oponentni.modely.ai_unassigned_proposal import (
    PROPOSAL_STATUS_LABELS,
    PROPOSAL_STATUS_PENDING,
)
from core.ai_oponentni.sluzby.ai_peer_review_service import (
    AiPeerReviewError,
    ai_peer_review_service,
)
from core.ai_oponentni.types import (
    AiExportSourceChoice,
    AiPeerReviewExportDialogConfig,
    AiPeerReviewExportOptions,
    AiPeerReviewProvider,
)
from core.ai_oponentni.ui.import_proposals_dialog import AiPeerReviewImportDialog
from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.table_utils import configure_table_columns
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_datetime,
    typed_empty,
    typed_int,
    typed_status,
    typed_text,
)

_PACKAGE_TYPE_ORDER = tuple(AI_PEER_REVIEW_PACKAGE_TYPE_LABELS.keys())
_PACKAGE_STATUS_ORDER = tuple(PACKAGE_STATUS_LABELS.keys())
_PROPOSAL_STATUS_ORDER = tuple(PROPOSAL_STATUS_LABELS.keys())


def _order_status(value: str, order: tuple[str, ...]):
    try:
        return typed_status(order.index(value), label=value or "")
    except ValueError:
        return typed_status(len(order), label=value or "")


def _text_or_empty(display: str | None):
    if not display or display == "—":
        return typed_empty()
    return typed_text(display)


class AiPeerReviewExportOptionsDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        source_choices: list[AiExportSourceChoice] | None = None,
        dialog_config: AiPeerReviewExportDialogConfig | None = None,
    ):
        super().__init__(parent)
        self._config = dialog_config or AiPeerReviewExportDialogConfig()
        self.setWindowTitle(AI_PEER_REVIEW_DIALOG_TITLE)
        self.resize(620, 680)

        root = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        layout.addWidget(QLabel("Role odborného oponenta:"))
        self.opponent_role = QComboBox()
        for role_id in AI_PEER_REVIEW_ROLES:
            self.opponent_role.addItem(AI_PEER_REVIEW_ROLE_LABELS[role_id], role_id)
        default_index = self.opponent_role.findData(AI_PEER_REVIEW_DEFAULT_ROLE)
        if default_index >= 0:
            self.opponent_role.setCurrentIndex(default_index)
        layout.addWidget(self.opponent_role)

        objectives_box = QGroupBox("Cíl oponentury")
        objectives_layout = QVBoxLayout(objectives_box)
        self._objective_checks: dict[str, QCheckBox] = {}
        for objective_id in self._config.objectives:
            checkbox = QCheckBox(
                self._config.objective_labels.get(
                    objective_id,
                    AI_PEER_REVIEW_OBJECTIVE_LABELS.get(objective_id, objective_id),
                )
            )
            checkbox.setChecked(objective_id in self._config.default_objectives)
            self._objective_checks[objective_id] = checkbox
            objectives_layout.addWidget(checkbox)
        layout.addWidget(objectives_box)

        focus_box = QGroupBox("Doplňující zaměření (volitelné)")
        focus_layout = QVBoxLayout(focus_box)
        self._focus_checks: dict[str, QCheckBox] = {}
        for focus_id in AI_PEER_REVIEW_FOCUS_AREAS:
            checkbox = QCheckBox(AI_PEER_REVIEW_FOCUS_AREA_LABELS[focus_id])
            checkbox.setChecked(False)
            self._focus_checks[focus_id] = checkbox
            focus_layout.addWidget(checkbox)
        layout.addWidget(focus_box)

        layout.addWidget(QLabel(self._config.context_field_label))
        self.workplace_characteristics = QPlainTextEdit()
        self.workplace_characteristics.setPlaceholderText(self._config.context_placeholder)
        self.workplace_characteristics.setMinimumHeight(90)
        layout.addWidget(self.workplace_characteristics)

        self.scope_full = QRadioButton(self._config.scope_full_label)
        self.scope_selected = QRadioButton(self._config.scope_selected_label)
        self.scope_full.setChecked(True)
        self._scope_group = QButtonGroup(self)
        self._scope_group.addButton(self.scope_full)
        self._scope_group.addButton(self.scope_selected)

        self.scope_section_label = QLabel("Rozsah exportu:")
        self.source_list_label = QLabel(self._config.source_list_label)
        self.source_list = QListWidget()
        self.source_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        for choice in source_choices or []:
            label = choice.label
            if choice.category_label:
                label = f"{choice.category_label}: {choice.label}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, choice.id)
            self.source_list.addItem(item)

        if self._config.show_export_scope:
            layout.addWidget(self.scope_section_label)
            layout.addWidget(self.scope_full)
            layout.addWidget(self.scope_selected)
        else:
            self.scope_full.setChecked(True)
            self.scope_full.hide()
            self.scope_selected.hide()
            self.scope_section_label.hide()

        if self._config.show_source_list:
            layout.addWidget(self.source_list_label)
            layout.addWidget(self.source_list)
        else:
            self.source_list_label.hide()
            self.source_list.hide()

        if self._config.show_export_scope:
            self.scope_full.toggled.connect(self._update_source_list_enabled)
            self._update_source_list_enabled()

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        buttons = create_save_cancel_box(self)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setText("Pokračovat")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _update_source_list_enabled(self) -> None:
        if not self._config.show_source_list:
            return
        enabled = self.scope_selected.isChecked()
        self.source_list.setEnabled(enabled)

    def _accept_if_valid(self) -> None:
        if (
            self._config.show_export_scope
            and self._config.show_source_list
            and self.scope_selected.isChecked()
            and not self.source_list.selectedItems()
        ):
            QMessageBox.warning(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                "Vyberte alespoň jeden zdroj analýzy.",
            )
            return
        if not any(box.isChecked() for box in self._objective_checks.values()):
            QMessageBox.warning(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                "Vyberte alespoň jeden cíl oponentury.",
            )
            return
        self.accept()

    def get_options(self) -> AiPeerReviewExportOptions:
        objectives = [
            objective_id
            for objective_id, checkbox in self._objective_checks.items()
            if checkbox.isChecked()
        ]
        focus_areas = [
            focus_id
            for focus_id, checkbox in self._focus_checks.items()
            if checkbox.isChecked()
        ]
        characteristics = self.workplace_characteristics.toPlainText().strip()
        role = self.opponent_role.currentData() or AI_PEER_REVIEW_DEFAULT_ROLE

        common = {
            "opponent_role": role,
            "objectives": objectives,
            "focus_areas": focus_areas,
            "workplace_characteristics": characteristics,
        }
        if self.scope_selected.isChecked():
            selected_ids = [
                int(item.data(Qt.ItemDataRole.UserRole))
                for item in self.source_list.selectedItems()
            ]
            return AiPeerReviewExportOptions(
                export_scope=AI_PEER_REVIEW_EXPORT_SCOPE_SELECTED,
                selected_source_ids=selected_ids,
                **common,
            )
        return AiPeerReviewExportOptions(
            export_scope=AI_PEER_REVIEW_EXPORT_SCOPE_FULL,
            selected_source_ids=None,
            **common,
        )


def catalog_peer_review_export_dialog_config() -> AiPeerReviewExportDialogConfig:
    from core.ai_oponentni.constants import (
        AI_CATALOG_PEER_REVIEW_CONTEXT_LABEL,
        AI_CATALOG_PEER_REVIEW_CONTEXT_PLACEHOLDER,
        AI_CATALOG_PEER_REVIEW_DEFAULT_OBJECTIVES,
        AI_CATALOG_PEER_REVIEW_OBJECTIVES,
        AI_CATALOG_PEER_REVIEW_SCOPE_FULL_LABEL,
    )

    return AiPeerReviewExportDialogConfig(
        objectives=AI_CATALOG_PEER_REVIEW_OBJECTIVES,
        default_objectives=AI_CATALOG_PEER_REVIEW_DEFAULT_OBJECTIVES,
        context_field_label=AI_CATALOG_PEER_REVIEW_CONTEXT_LABEL,
        context_placeholder=AI_CATALOG_PEER_REVIEW_CONTEXT_PLACEHOLDER,
        show_export_scope=False,
        show_source_list=False,
        scope_full_label=AI_CATALOG_PEER_REVIEW_SCOPE_FULL_LABEL,
    )


class AiPeerReviewResponseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(AI_PEER_REVIEW_RESPONSE_DIALOG_TITLE)
        self.resize(640, 480)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.ai_model = QLineEdit()
        self.ai_model.setPlaceholderText("např. ChatGPT, Claude, …")
        form.addRow("Model AI:", self.ai_model)
        layout.addLayout(form)

        layout.addWidget(QLabel("Odpověď AI:"))
        self.response = QPlainTextEdit()
        self.response.setPlaceholderText(AI_PEER_REVIEW_RESPONSE_PLACEHOLDER)
        layout.addWidget(self.response)

        load_btn = QPushButton("Načíst ze souboru…")
        load_btn.clicked.connect(self._load_from_file)
        layout.addWidget(load_btn)

        buttons = create_save_cancel_box(self)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setText("Pokračovat")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load_from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            AI_PEER_REVIEW_RESPONSE_DIALOG_TITLE,
            "",
            "Odpovědi AI (*.json *.txt *.zip);;"
            "JSON (*.json);;Text (*.txt);;ZIP (*.zip);;"
            "Všechny soubory (*)",
        )
        if not path:
            return
        file_path = Path(path)
        try:
            if file_path.suffix.casefold() == ".zip":
                self._load_from_zip(file_path)
            else:
                self.response.setPlainText(file_path.read_text(encoding="utf-8"))
        except OSError as error:
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))

    def _load_from_zip(self, zip_path: Path) -> None:
        from core.ai_oponentni.sluzby.response_zip_loader import (
            AiPeerReviewZipLoadError,
            load_response_from_zip,
        )

        entry_name: str | None = None
        while True:
            try:
                result = load_response_from_zip(zip_path, entry_name=entry_name)
                break
            except AiPeerReviewZipLoadError as error:
                if getattr(error, "selection_required", False):
                    entries = getattr(error, "entries", [])
                    if not entries:
                        QMessageBox.warning(
                            self,
                            AI_PEER_REVIEW_DIALOG_TITLE,
                            format_ai_peer_review_user_error(error),
                        )
                        return
                    label, ok = QInputDialog.getItem(
                        self,
                        AI_PEER_REVIEW_DIALOG_TITLE,
                        "Vyberte soubor odpovědi v ZIP:",
                        entries,
                        0,
                        False,
                    )
                    if not ok:
                        return
                    entry_name = label
                    continue
                QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))
                return

        self.response.setPlainText(result.text)

    def get_ai_model(self) -> str:
        return self.ai_model.text().strip()

    def get_response_text(self) -> str:
        return self.response.toPlainText().strip()


class AiPeerReviewWidget(QWidget):
    """Obecný widget oponentního posouzení – hostí libovolný doménový provider."""

    _HISTORY_ROW_HEIGHT = 29
    _HISTORY_HEADER_HEIGHT = 32

    def __init__(
        self,
        parent=None,
        *,
        provider: AiPeerReviewProvider,
        on_proposals_applied=None,
        on_catalog_incorporated=None,
        allow_new_exports: bool = True,
        export_dialog_config: AiPeerReviewExportDialogConfig | None = None,
        resolve_exposed_groups: bool = True,
        evidence_only_import: bool = False,
        package_incorporate_handler=None,
        package_session=None,
    ):
        super().__init__(parent)
        self._provider = provider
        self._source_id: int | None = None
        self._on_proposals_applied = on_proposals_applied
        self._on_catalog_incorporated = on_catalog_incorporated
        self._allow_new_exports = allow_new_exports
        self._export_dialog_config = export_dialog_config
        self._resolve_exposed_groups = resolve_exposed_groups
        self._evidence_only_import = evidence_only_import
        self._package_incorporate_handler = package_incorporate_handler
        self._package_session = package_session
        self._uses_proposal_packages = ai_peer_review_service.provider_uses_proposal_packages(
            provider,
        )

        layout = QVBoxLayout(self)

        intro = QLabel(AI_PEER_REVIEW_INTRO_TEXT)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        toolbar = QHBoxLayout()
        self.export_btn = QPushButton(AI_PEER_REVIEW_EXPORT_BUTTON)
        self.import_btn = QPushButton(AI_PEER_REVIEW_IMPORT_BUTTON)
        toolbar.addWidget(self.export_btn)
        toolbar.addWidget(self.import_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        layout.addWidget(QLabel("Historie konzultací:"))
        self.table = QTableWidget()
        self.table.setColumnCount(AI_PEER_REVIEW_COLUMN_COUNT)
        self.table.setHorizontalHeaderLabels(AI_PEER_REVIEW_TABLE_HEADERS)
        self.table.setColumnHidden(AI_PEER_REVIEW_COL_ID, True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(self._HISTORY_ROW_HEIGHT)
        self.table.verticalHeader().setMinimumSectionSize(self._HISTORY_ROW_HEIGHT)
        self.table.horizontalHeader().setFixedHeight(self._HISTORY_HEADER_HEIGHT)
        configure_table_columns(self.table, "ai_peer_reviews")
        enable_typed_sorting(self.table)
        self.table.itemSelectionChanged.connect(self._load_proposals_table)
        layout.addWidget(self.table)

        self.proposals_label = QLabel("Návrhy vybrané konzultace:")
        layout.addWidget(self.proposals_label)
        self.proposals_table = QTableWidget()
        if self._uses_proposal_packages:
            self.proposals_table.setColumnCount(8)
            self.proposals_table.setHorizontalHeaderLabels(
                [
                    "Typ",
                    "Událost / text",
                    "Posouzení",
                    "Zásady",
                    "Navazující",
                    "Právní vazby",
                    "Zdůvodnění",
                    "Stav",
                ],
            )
        else:
            self.proposals_table.setColumnCount(5)
            self.proposals_table.setHorizontalHeaderLabels(
                ["Oblast", "Návrh", "Zdůvodnění", "Stav", "ID návrhu"],
            )
        if self._evidence_only_import and not self._uses_proposal_packages:
            self.proposals_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        else:
            self.proposals_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.proposals_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.proposals_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.proposals_table.setAlternatingRowColors(True)
        configure_table_columns(self.proposals_table, "ai_peer_review_proposals")
        enable_typed_sorting(self.proposals_table)
        if self._uses_proposal_packages:
            self.proposals_table.doubleClicked.connect(self._edit_selected_package)
        else:
            self.proposals_table.doubleClicked.connect(self._edit_selected_proposals)
        layout.addWidget(self.proposals_table)

        self.package_detail = None
        self.package_detail_label = None

        if self._evidence_only_import and not self._uses_proposal_packages:
            from moduly.rizeni_rizik.constants_library import (
                CATALOG_AI_PROPOSAL_EDIT_BUTTON,
                CATALOG_AI_PROPOSAL_INCORPORATE_BUTTON,
                CATALOG_AI_PROPOSAL_INCORPORATE_SELECTED_BUTTON,
                CATALOG_AI_PROPOSAL_QUEUE_LABEL,
                CATALOG_AI_PROPOSAL_REJECT_BUTTON,
                CATALOG_AI_PROPOSAL_REJECT_SELECTED_BUTTON,
            )

            self.proposals_label.setText(CATALOG_AI_PROPOSAL_QUEUE_LABEL)
            proposal_actions = QHBoxLayout()
            self.incorporate_btn = QPushButton(CATALOG_AI_PROPOSAL_INCORPORATE_BUTTON)
            self.reject_proposal_btn = QPushButton(CATALOG_AI_PROPOSAL_REJECT_BUTTON)
            self.edit_proposal_btn = QPushButton(CATALOG_AI_PROPOSAL_EDIT_BUTTON)
            self.incorporate_selected_btn = QPushButton(
                CATALOG_AI_PROPOSAL_INCORPORATE_SELECTED_BUTTON,
            )
            self.reject_selected_btn = QPushButton(CATALOG_AI_PROPOSAL_REJECT_SELECTED_BUTTON)
            proposal_actions.addWidget(self.incorporate_btn)
            proposal_actions.addWidget(self.reject_proposal_btn)
            proposal_actions.addWidget(self.edit_proposal_btn)
            proposal_actions.addWidget(self.incorporate_selected_btn)
            proposal_actions.addWidget(self.reject_selected_btn)
            proposal_actions.addStretch()
            layout.addLayout(proposal_actions)

            self.incorporate_btn.clicked.connect(self._incorporate_current_proposal)
            self.reject_proposal_btn.clicked.connect(self._reject_current_proposals)
            self.edit_proposal_btn.clicked.connect(self._edit_selected_proposals)
            self.incorporate_selected_btn.clicked.connect(self._incorporate_selected_proposals)
            self.reject_selected_btn.clicked.connect(self._reject_selected_proposals)
        elif self._evidence_only_import and self._uses_proposal_packages:
            from moduly.rizeni_rizik.constants_library import (
                CATALOG_AI_PACKAGE_DETAIL_LABEL,
                CATALOG_AI_PACKAGE_EDIT_BUTTON,
                CATALOG_AI_PACKAGE_INCORPORATE_BUTTON,
                CATALOG_AI_PACKAGE_QUEUE_LABEL,
                CATALOG_AI_PACKAGE_REJECT_BUTTON,
            )

            self.proposals_label.setText(CATALOG_AI_PACKAGE_QUEUE_LABEL)
            self.package_detail_label = QLabel(CATALOG_AI_PACKAGE_DETAIL_LABEL)
            layout.addWidget(self.package_detail_label)
            self.package_detail = QPlainTextEdit()
            self.package_detail.setReadOnly(True)
            self.package_detail.setMinimumHeight(180)
            layout.addWidget(self.package_detail)

            package_actions = QHBoxLayout()
            self.edit_proposal_btn = QPushButton(CATALOG_AI_PACKAGE_EDIT_BUTTON)
            self.incorporate_btn = QPushButton(CATALOG_AI_PACKAGE_INCORPORATE_BUTTON)
            self.reject_proposal_btn = QPushButton(CATALOG_AI_PACKAGE_REJECT_BUTTON)
            self.incorporate_selected_btn = None
            self.reject_selected_btn = None
            package_actions.addWidget(self.edit_proposal_btn)
            package_actions.addWidget(self.incorporate_btn)
            package_actions.addWidget(self.reject_proposal_btn)
            package_actions.addStretch()
            layout.addLayout(package_actions)

            self.edit_proposal_btn.clicked.connect(self._edit_selected_package)
            self.incorporate_btn.clicked.connect(self._incorporate_selected_package)
            self.reject_proposal_btn.clicked.connect(self._reject_selected_package)
            self.proposals_table.itemSelectionChanged.connect(self._load_package_detail)
        else:
            self.incorporate_btn = None
            self.reject_proposal_btn = None
            self.edit_proposal_btn = None
            self.incorporate_selected_btn = None
            self.reject_selected_btn = None

        self.export_btn.clicked.connect(self.export_package)
        self.import_btn.clicked.connect(self.import_response)
        self.set_source(None)

    def set_package_session(self, package_session) -> None:
        """Nastaví CatalogEditorSession pro odložené AI balíky (katalog)."""
        self._package_session = package_session
        if self._source_id is not None:
            self._load_proposals_table()

    def set_source(self, source_id: int | None) -> None:
        self._source_id = source_id
        can_interact = self._provider.can_export(source_id)
        if self._allow_new_exports:
            self.export_btn.setEnabled(can_interact)
            self.import_btn.setEnabled(can_interact)
        else:
            self.export_btn.setEnabled(False)
            self.import_btn.setEnabled(False)
        self.refresh()

    def refresh(self) -> None:
        self._load_table()
        self._load_proposals_table()

    def export_package(self) -> bool:
        if self._source_id is None or not self._provider.can_export(self._source_id):
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                "Export je možné provést až po uložení zdrojového záznamu.",
            )
            return False

        try:
            source_choices = self._provider.get_export_source_choices(self._source_id)
        except Exception as error:  # pragma: no cover - defensive
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))
            return False

        options_dialog = AiPeerReviewExportOptionsDialog(
            self,
            source_choices=source_choices,
            dialog_config=self._export_dialog_config,
        )
        if not options_dialog.exec():
            return False
        options = options_dialog.get_options()

        try:
            content = self._provider.build_export_content(
                self._source_id,
                options=options,
            )
        except AiPeerReviewError as error:
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))
            return False
        except Exception as error:  # pragma: no cover - defensive
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))
            return False

        default_name = ai_peer_review_service.default_export_filename(
            content.source_label,
            datetime.now(),
        )
        target, _ = QFileDialog.getSaveFileName(
            self,
            AI_PEER_REVIEW_DIALOG_TITLE,
            default_name,
            "ZIP soubory (*.zip)",
        )
        if not target:
            return False

        target_path = Path(target)
        if target_path.suffix.lower() != ".zip":
            target_path = target_path.with_suffix(".zip")

        try:
            result = ai_peer_review_service.export_package(
                self._provider,
                self._source_id,
                target_path,
                options=options,
            )
        except AiPeerReviewError as error:
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))
            return False

        self.refresh()
        summary = "\n".join(result.summary_lines) if result.summary_lines else ""
        QMessageBox.information(
            self,
            AI_PEER_REVIEW_DIALOG_TITLE,
            f"Export byl vytvořen:\n{result.file_path}"
            + (f"\n\n{summary}" if summary else ""),
        )
        return True

    def import_response(self) -> bool:
        if self._source_id is None or not self._provider.can_export(self._source_id):
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                "Nejprve uložte zdrojový záznam.",
            )
            return False

        reviews = ai_peer_review_service.get_for_source(
            self._provider.source_type,
            self._source_id,
        )
        if not reviews:
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                "Nejdříve vytvořte export podkladů pro AI.",
            )
            return False

        review = reviews[0]
        if len(reviews) > 1:
            labels = [
                f"{item.exported_at.strftime('%d.%m.%Y %H:%M')} — "
                f"{Path(item.export_file_path).name}"
                for item in reviews
            ]
            label, ok = QInputDialog.getItem(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                "Vyberte konzultaci:",
                labels,
                0,
                False,
            )
            if not ok:
                return False
            review = reviews[labels.index(label)]

        review = self._resolve_import_review(review)
        if review is None:
            return False

        response_dialog = AiPeerReviewResponseDialog(self)
        if not response_dialog.exec():
            return False

        response_text = response_dialog.get_response_text()
        ai_model = response_dialog.get_ai_model()
        if not response_text:
            QMessageBox.warning(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                "Vložte text odpovědi AI.",
            )
            return False

        try:
            expected_number = self._provider.get_source_label(self._source_id)
            parse_result = ai_peer_review_service.parse_response(
                response_text,
                expected_source_identification_number=expected_number or None,
                require_proposal_packages=self._uses_proposal_packages,
            )
        except AiPeerReviewError as error:
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))
            return False

        if parse_result.skipped_count:
            reasons = "\n".join(
                f"- {reason}" for reason in parse_result.skip_reasons[:12]
            )
            extra = ""
            if len(parse_result.skip_reasons) > 12:
                extra = f"\n… a dalších {len(parse_result.skip_reasons) - 12}."
            loaded_label = (
                "balíků" if parse_result.uses_proposal_packages else "návrhů"
            )
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                (
                    f"Načteno platných {loaded_label}: "
                    f"{len(parse_result.packages) if parse_result.uses_proposal_packages else len(parse_result.proposals)}\n"
                    f"Přeskočeno neplatných {loaded_label}: {parse_result.skipped_count}\n\n"
                    f"{reasons}{extra}"
                ),
            )

        if parse_result.uses_proposal_packages:
            if not parse_result.packages and not parse_result.skip_reasons:
                QMessageBox.warning(
                    self,
                    AI_PEER_REVIEW_DIALOG_TITLE,
                    "Odpověď AI neobsahuje žádný platný návrhový balík.",
                )
                return False
            if not parse_result.packages and parse_result.skip_reasons:
                reasons = "\n".join(
                    f"- {reason}" for reason in parse_result.skip_reasons[:12]
                )
                extra = ""
                if len(parse_result.skip_reasons) > 12:
                    extra = f"\n… a dalších {len(parse_result.skip_reasons) - 12}."
                QMessageBox.warning(
                    self,
                    AI_PEER_REVIEW_DIALOG_TITLE,
                    (
                        "Odpověď AI neobsahuje žádný platný návrhový balík.\n\n"
                        f"Důvody přeskočení:\n{reasons}{extra}"
                    ),
                )
                return False
            try:
                if self._package_session is not None:
                    import_result = self._package_session.import_packages(
                        review_id=review.id,
                        source_type=self._provider.source_type,
                        packages=list(parse_result.packages),
                        response_text=response_text,
                        ai_model=ai_model,
                    )
                    if (
                        import_result.loaded_count == 0
                        and import_result.no_change_count > 0
                        and import_result.duplicate_count == 0
                    ):
                        # Ulož response_text / model i bez pending položek.
                        self._package_session.sync_review_stats(
                            review.id,
                            loaded_packages_count=0,
                        )
                        QMessageBox.information(
                            self,
                            AI_PEER_REVIEW_DIALOG_TITLE,
                            AI_PEER_REVIEW_NO_CHANGE_FOUND_MESSAGE,
                        )
                        self.refresh()
                        self._select_review_row(review.id)
                        return True
                    if (
                        import_result.loaded_count == 0
                        and import_result.duplicate_count > 0
                    ):
                        QMessageBox.information(
                            self,
                            AI_PEER_REVIEW_DIALOG_TITLE,
                            (
                                "Žádný nový balík nebyl načten.\n\n"
                                f"Všechny položky z odpovědi už jsou u této "
                                f"konzultace evidované (duplicit: "
                                f"{import_result.duplicate_count})."
                            ),
                        )
                        return False
                    if import_result.loaded_count == 0:
                        QMessageBox.warning(
                            self,
                            AI_PEER_REVIEW_DIALOG_TITLE,
                            "Odpověď AI neobsahuje žádný nový platný návrhový balík.",
                        )
                        return False
                    updated = self._package_session.sync_review_stats(
                        review.id,
                        loaded_packages_count=import_result.loaded_count,
                    )
                    if updated is None:
                        updated = review
                        updated.loaded_proposals_count = import_result.loaded_count
                        pending, rejected, accepted = (
                            self._package_session.count_packages_by_status(review.id)
                        )
                        updated.pending_proposals_count = pending
                        updated.rejected_count = rejected
                        updated.accepted_count = accepted
                    if import_result.duplicate_count:
                        QMessageBox.information(
                            self,
                            AI_PEER_REVIEW_DIALOG_TITLE,
                            (
                                f"Přeskočeno duplicitních balíků: "
                                f"{import_result.duplicate_count}."
                            ),
                        )
                else:
                    accepted_packages, duplicate_ids = (
                        ai_peer_review_service.filter_new_packages_for_review(
                            review_id=review.id,
                            packages=list(parse_result.packages),
                        )
                    )
                    no_change_only = (
                        not accepted_packages
                        and not duplicate_ids
                        and any(
                            not package.requires_user_decision
                            for package in parse_result.packages
                        )
                    )
                    if no_change_only:
                        updated = ai_peer_review_service.finalize_package_import(
                            provider=self._provider,
                            source_id=self._source_id,
                            review_id=review.id,
                            response_text=response_text,
                            ai_model=ai_model,
                            accepted=[],
                            rejected=[],
                            loaded_packages_count=0,
                        )
                        QMessageBox.information(
                            self,
                            AI_PEER_REVIEW_DIALOG_TITLE,
                            AI_PEER_REVIEW_NO_CHANGE_FOUND_MESSAGE,
                        )
                        self.refresh()
                        self._select_review_row(updated.id)
                        return True
                    if not accepted_packages and duplicate_ids:
                        QMessageBox.information(
                            self,
                            AI_PEER_REVIEW_DIALOG_TITLE,
                            (
                                "Žádný nový balík nebyl načten.\n\n"
                                f"Všechny položky z odpovědi už jsou u této "
                                f"konzultace evidované (duplicit: "
                                f"{len(duplicate_ids)})."
                            ),
                        )
                        return False
                    if not accepted_packages:
                        QMessageBox.warning(
                            self,
                            AI_PEER_REVIEW_DIALOG_TITLE,
                            "Odpověď AI neobsahuje žádný nový platný návrhový balík.",
                        )
                        return False
                    updated = ai_peer_review_service.finalize_package_import(
                        provider=self._provider,
                        source_id=self._source_id,
                        review_id=review.id,
                        response_text=response_text,
                        ai_model=ai_model,
                        accepted=accepted_packages,
                        rejected=[],
                        loaded_packages_count=len(accepted_packages),
                    )
                    if duplicate_ids:
                        QMessageBox.information(
                            self,
                            AI_PEER_REVIEW_DIALOG_TITLE,
                            f"Přeskočeno duplicitních balíků: {len(duplicate_ids)}.",
                        )
            except AiPeerReviewError as error:
                QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))
                return False
            except Exception as error:
                QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))
                return False
        else:
            import_dialog = AiPeerReviewImportDialog(
                self,
                proposals=parse_result.proposals,
                ai_model=ai_model,
                intro_text=(
                    AI_PEER_REVIEW_IMPORT_INTRO_EVIDENCE if self._evidence_only_import else None
                ),
                accept_column_label=(
                    "Přijmout" if self._evidence_only_import else "Převzít"
                ),
            )
            if not import_dialog.exec():
                return False

            accepted, rejected = import_dialog.get_accepted_and_rejected()
            if self._resolve_exposed_groups:
                from moduly.rizeni_rizik.ui.exposed_group_proposal_resolution_dialog import (
                    resolve_exposed_group_proposals,
                )

                accepted, resolution_rejected = resolve_exposed_group_proposals(self, accepted)
                rejected.extend(resolution_rejected)
            try:
                updated = ai_peer_review_service.finalize_import(
                    provider=self._provider,
                    source_id=self._source_id,
                    review_id=review.id,
                    response_text=response_text,
                    ai_model=ai_model,
                    accepted=accepted,
                    rejected=rejected,
                    loaded_proposals_count=len(parse_result.proposals),
                )
            except AiPeerReviewError as error:
                QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))
                return False

        self.refresh()
        self._select_review_row(updated.id)
        if parse_result.uses_proposal_packages:
            self._load_proposals_table()
            if self.proposals_table.rowCount() > 0:
                self.proposals_table.selectRow(0)
                self.proposals_table.setFocus()
                first_item = self.proposals_table.item(0, 0)
                if first_item is not None:
                    self.proposals_table.scrollToItem(first_item)
        if self._on_proposals_applied is not None:
            self._on_proposals_applied()
        if self._package_session is not None and self._on_catalog_incorporated is not None:
            self._on_catalog_incorporated(None)

        QMessageBox.information(
            self,
            AI_PEER_REVIEW_DIALOG_TITLE,
            self._import_summary_message(updated, parse_result.format_label),
        )
        return True

    def _resolve_import_review(self, review):
        if not (review.response_text or "").strip():
            return review

        message_box = QMessageBox(self)
        message_box.setWindowTitle(AI_PEER_REVIEW_DIALOG_TITLE)
        message_box.setIcon(QMessageBox.Icon.Question)
        message_box.setText("K této konzultaci již existuje načtená odpověď.")
        message_box.setInformativeText("Jak chcete pokračovat?")
        new_button = message_box.addButton(
            "Načíst jako novou odpověď",
            QMessageBox.ButtonRole.AcceptRole,
        )
        replace_button = message_box.addButton(
            "Nahradit předchozí odpověď",
            QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_button = message_box.addButton(
            "Zrušit",
            QMessageBox.ButtonRole.RejectRole,
        )
        message_box.setDefaultButton(new_button)
        message_box.exec()
        clicked = message_box.clickedButton()
        if clicked is cancel_button:
            return None
        if clicked is new_button:
            try:
                return ai_peer_review_service.clone_consultation_for_new_import(review.id)
            except AiPeerReviewError as error:
                QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))
                return None
        if clicked is replace_button:
            ai_peer_review_service.delete_import_data_for_review(review.id)
            return review
        return None

    def _import_summary_message(self, review, format_label: str) -> str:
        if self._uses_proposal_packages:
            return (
                f"Formát odpovědi: {format_label}\n"
                f"Načteno balíků: {review.loaded_proposals_count}\n"
                f"Čeká na odborné posouzení: {review.pending_proposals_count}\n"
                f"Zamítnuto: {review.rejected_count}\n\n"
                "Balíky jsou evidovány. Zapracujte je tlačítkem „Zapracovat balík“."
            )
        if self._evidence_only_import:
            return (
                f"Formát odpovědi: {format_label}\n"
                f"Načteno návrhů: {review.loaded_proposals_count}\n"
                f"Čeká na odborné posouzení: {review.pending_proposals_count}\n"
                f"Zamítnuto: {review.rejected_count}\n"
                f"Nezařazeno: {review.unassigned_count}"
            )
        return (
            f"Formát odpovědi: {format_label}\n"
            f"Načteno návrhů: {review.loaded_proposals_count}\n"
            f"Převzato: {review.accepted_count}\n"
            f"Zamítnuto: {review.rejected_count}\n"
            f"Nezařazeno: {review.unassigned_count}"
        )

    def _select_review_row(self, review_id: int) -> None:
        for row_index in range(self.table.rowCount()):
            item = self.table.item(row_index, AI_PEER_REVIEW_COL_ID)
            if item is not None and item.text() == str(review_id):
                self.table.selectRow(row_index)
                return

    def _selected_review_id(self) -> int | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        item = self.table.item(selected[0].row(), AI_PEER_REVIEW_COL_ID)
        if item is None:
            return None
        try:
            return int(item.text())
        except ValueError:
            return None

    def _load_proposals_table(self) -> None:
        self.proposals_table.setRowCount(0)
        review_id = self._selected_review_id()
        if review_id is None:
            return

        package_records = ai_peer_review_service.get_packages_for_review(review_id)
        if self._package_session is not None and self._uses_proposal_packages:
            self._configure_package_proposals_table()
            display_items = self._package_session.list_pending_packages(review_id)
            with sorting_paused(self.proposals_table):
                self.proposals_table.setRowCount(len(display_items))
                for row_index, item in enumerate(display_items):
                    package = item.package
                    stable_id = int(item.local_id)
                    type_label = AI_PEER_REVIEW_PACKAGE_TYPE_LABELS.get(
                        package.package_type,
                        package.package_type,
                    )
                    type_item = create_typed_item(
                        type_label,
                        _order_status(package.package_type, _PACKAGE_TYPE_ORDER),
                        stable_id=stable_id,
                    )
                    type_item.setData(Qt.ItemDataRole.UserRole, item.local_id)
                    resolved_name = None
                    if package.target_event_export_id:
                        from moduly.rizeni_rizik.ui.hazard_catalog_ai_package_edit_dialog import (
                            resolve_target_event_name,
                        )

                        resolved_name = resolve_target_event_name(
                            package_record_id=item.db_id,
                            target_event_export_id=package.target_event_export_id,
                            review_id=item.review_id,
                        )
                    self.proposals_table.setItem(row_index, 0, type_item)
                    event_label = package.display_event_label(resolved_target_name=resolved_name)
                    self.proposals_table.setItem(
                        row_index,
                        1,
                        create_typed_item(event_label, _text_or_empty(event_label), stable_id=stable_id),
                    )
                    self.proposals_table.setItem(
                        row_index,
                        2,
                        create_typed_item(
                            str(package.assessment_count),
                            typed_int(package.assessment_count),
                            stable_id=stable_id,
                        ),
                    )
                    self.proposals_table.setItem(
                        row_index,
                        3,
                        create_typed_item(
                            str(package.existing_measure_count),
                            typed_int(package.existing_measure_count),
                            stable_id=stable_id,
                        ),
                    )
                    self.proposals_table.setItem(
                        row_index,
                        4,
                        create_typed_item(
                            str(package.required_measure_count),
                            typed_int(package.required_measure_count),
                            stable_id=stable_id,
                        ),
                    )
                    self.proposals_table.setItem(
                        row_index,
                        5,
                        create_typed_item(
                            str(package.legal_link_count),
                            typed_int(package.legal_link_count),
                            stable_id=stable_id,
                        ),
                    )
                    self.proposals_table.setItem(
                        row_index,
                        6,
                        create_typed_item(
                            package.reasoning or "—",
                            _text_or_empty(package.reasoning),
                            stable_id=stable_id,
                        ),
                    )
                    self.proposals_table.setItem(
                        row_index,
                        7,
                        create_typed_item(
                            PACKAGE_STATUS_LABELS.get(
                                PACKAGE_STATUS_PENDING,
                                PACKAGE_STATUS_PENDING,
                            ),
                            _order_status(PACKAGE_STATUS_PENDING, _PACKAGE_STATUS_ORDER),
                            stable_id=stable_id,
                        ),
                    )
            configure_table_columns(self.proposals_table, "ai_peer_review_proposals")
            self._load_package_detail()
            return

        if package_records:
            self._configure_package_proposals_table()
            display_records = package_records
            if self._uses_proposal_packages:
                display_records = [
                    record
                    for record in package_records
                    if record.status == PACKAGE_STATUS_PENDING
                ]
            with sorting_paused(self.proposals_table):
                self.proposals_table.setRowCount(len(display_records))
                for row_index, record in enumerate(display_records):
                    package = ai_peer_review_service.package_repository.package_from_record(
                        record,
                    )
                    stable_id = int(record.id)
                    type_label = AI_PEER_REVIEW_PACKAGE_TYPE_LABELS.get(
                        package.package_type,
                        package.package_type,
                    )
                    type_item = create_typed_item(
                        type_label,
                        _order_status(package.package_type, _PACKAGE_TYPE_ORDER),
                        stable_id=stable_id,
                    )
                    type_item.setData(Qt.ItemDataRole.UserRole, record.id)
                    resolved_name = None
                    if package.target_event_export_id:
                        from moduly.rizeni_rizik.ui.hazard_catalog_ai_package_edit_dialog import (
                            resolve_target_event_name,
                        )

                        resolved_name = resolve_target_event_name(
                            package_record_id=record.id,
                            target_event_export_id=package.target_event_export_id,
                        )
                    self.proposals_table.setItem(row_index, 0, type_item)
                    event_label = package.display_event_label(resolved_target_name=resolved_name)
                    self.proposals_table.setItem(
                        row_index,
                        1,
                        create_typed_item(event_label, _text_or_empty(event_label), stable_id=stable_id),
                    )
                    self.proposals_table.setItem(
                        row_index,
                        2,
                        create_typed_item(
                            str(package.assessment_count),
                            typed_int(package.assessment_count),
                            stable_id=stable_id,
                        ),
                    )
                    self.proposals_table.setItem(
                        row_index,
                        3,
                        create_typed_item(
                            str(package.existing_measure_count),
                            typed_int(package.existing_measure_count),
                            stable_id=stable_id,
                        ),
                    )
                    self.proposals_table.setItem(
                        row_index,
                        4,
                        create_typed_item(
                            str(package.required_measure_count),
                            typed_int(package.required_measure_count),
                            stable_id=stable_id,
                        ),
                    )
                    self.proposals_table.setItem(
                        row_index,
                        5,
                        create_typed_item(
                            str(package.legal_link_count),
                            typed_int(package.legal_link_count),
                            stable_id=stable_id,
                        ),
                    )
                    self.proposals_table.setItem(
                        row_index,
                        6,
                        create_typed_item(
                            package.reasoning or "—",
                            _text_or_empty(package.reasoning),
                            stable_id=stable_id,
                        ),
                    )
                    self.proposals_table.setItem(
                        row_index,
                        7,
                        create_typed_item(
                            PACKAGE_STATUS_LABELS.get(record.status, record.status),
                            _order_status(record.status, _PACKAGE_STATUS_ORDER),
                            stable_id=stable_id,
                        ),
                    )
            configure_table_columns(self.proposals_table, "ai_peer_review_proposals")
            self._load_package_detail()
            return

        self._configure_flat_proposals_table()
        if self.package_detail is not None:
            self.package_detail.clear()
        proposals = ai_peer_review_service.get_unassigned_for_review(review_id)
        if self._evidence_only_import:
            proposals = [
                proposal
                for proposal in proposals
                if proposal.status == PROPOSAL_STATUS_PENDING
            ]
        with sorting_paused(self.proposals_table):
            self.proposals_table.setRowCount(len(proposals))
            for row_index, proposal in enumerate(proposals):
                stable_id = int(proposal.id)
                area = proposal.area or "—"
                area_item = create_typed_item(area, _text_or_empty(area), stable_id=stable_id)
                area_item.setData(Qt.ItemDataRole.UserRole, proposal.id)
                self.proposals_table.setItem(row_index, 0, area_item)
                self.proposals_table.setItem(
                    row_index,
                    1,
                    create_typed_item(proposal.name, _text_or_empty(proposal.name), stable_id=stable_id),
                )
                self.proposals_table.setItem(
                    row_index,
                    2,
                    create_typed_item(
                        proposal.reasoning or "—",
                        _text_or_empty(proposal.reasoning),
                        stable_id=stable_id,
                    ),
                )
                self.proposals_table.setItem(
                    row_index,
                    3,
                    create_typed_item(
                        PROPOSAL_STATUS_LABELS.get(proposal.status, proposal.status),
                        _order_status(proposal.status, _PROPOSAL_STATUS_ORDER),
                        stable_id=stable_id,
                    ),
                )
                self.proposals_table.setItem(
                    row_index,
                    4,
                    create_typed_item(
                        proposal.proposal_id or "—",
                        _text_or_empty(proposal.proposal_id),
                        stable_id=stable_id,
                    ),
                )
        configure_table_columns(self.proposals_table, "ai_peer_review_proposals")

    def _configure_package_proposals_table(self) -> None:
        if self.proposals_table.columnCount() == 8:
            return
        self.proposals_table.setColumnCount(8)
        self.proposals_table.setHorizontalHeaderLabels(
            [
                "Typ",
                "Událost / text",
                "Posouzení",
                "Zásady",
                "Navazující",
                "Právní vazby",
                "Zdůvodnění",
                "Stav",
            ],
        )

    def _configure_flat_proposals_table(self) -> None:
        if self.proposals_table.columnCount() == 5:
            return
        self.proposals_table.setColumnCount(5)
        self.proposals_table.setHorizontalHeaderLabels(
            ["Oblast", "Návrh", "Zdůvodnění", "Stav", "ID návrhu"],
        )

    def _load_table(self) -> None:
        self.table.setRowCount(0)
        if self._source_id is None:
            return

        rows = ai_peer_review_service.get_for_source(
            self._provider.source_type,
            self._source_id,
        )
        headers = list(AI_PEER_REVIEW_TABLE_HEADERS)
        if self._evidence_only_import:
            headers[AI_PEER_REVIEW_COL_ACCEPTED] = "Zapracováno"
        self.table.setHorizontalHeaderLabels(headers)
        with sorting_paused(self.table):
            self.table.setRowCount(len(rows))
            for row_index, review in enumerate(rows):
                record_id = int(review.id)
                response_loaded = (
                    review.response_loaded_at.strftime("%d.%m.%Y %H:%M")
                    if review.response_loaded_at is not None
                    else "—"
                )
                filename = Path(review.export_file_path).name or "—"
                self.table.setItem(
                    row_index,
                    AI_PEER_REVIEW_COL_ID,
                    create_typed_item(str(review.id), typed_int(review.id), stable_id=record_id),
                )
                self.table.setItem(
                    row_index,
                    AI_PEER_REVIEW_COL_EXPORT_DATE,
                    create_typed_item(
                        review.exported_at.strftime("%d.%m.%Y %H:%M"),
                        typed_datetime(review.exported_at),
                        stable_id=record_id,
                    ),
                )
                self.table.setItem(
                    row_index,
                    AI_PEER_REVIEW_COL_RESPONSE_DATE,
                    create_typed_item(
                        response_loaded,
                        typed_datetime(review.response_loaded_at)
                        if review.response_loaded_at is not None
                        else typed_empty(),
                        stable_id=record_id,
                    ),
                )
                self.table.setItem(
                    row_index,
                    AI_PEER_REVIEW_COL_MODEL,
                    create_typed_item(
                        review.ai_model or "—",
                        _text_or_empty(review.ai_model),
                        stable_id=record_id,
                    ),
                )
                self.table.setItem(
                    row_index,
                    AI_PEER_REVIEW_COL_LOADED,
                    self._centered_history_item(
                        str(review.loaded_proposals_count),
                        typed_int(review.loaded_proposals_count),
                        stable_id=record_id,
                    ),
                )
                self.table.setItem(
                    row_index,
                    AI_PEER_REVIEW_COL_PENDING,
                    self._centered_history_item(
                        str(review.pending_proposals_count),
                        typed_int(review.pending_proposals_count),
                        stable_id=record_id,
                    ),
                )
                self.table.setItem(
                    row_index,
                    AI_PEER_REVIEW_COL_ACCEPTED,
                    self._centered_history_item(
                        str(review.accepted_count),
                        typed_int(review.accepted_count),
                        stable_id=record_id,
                    ),
                )
                self.table.setItem(
                    row_index,
                    AI_PEER_REVIEW_COL_REJECTED,
                    self._centered_history_item(
                        str(review.rejected_count),
                        typed_int(review.rejected_count),
                        stable_id=record_id,
                    ),
                )
                self.table.setItem(
                    row_index,
                    AI_PEER_REVIEW_COL_UNASSIGNED,
                    self._centered_history_item(
                        str(review.unassigned_count),
                        typed_int(review.unassigned_count),
                        stable_id=record_id,
                    ),
                )
                self.table.setItem(
                    row_index,
                    AI_PEER_REVIEW_COL_FILENAME,
                    create_typed_item(filename, _text_or_empty(filename), stable_id=record_id),
                )
        configure_table_columns(self.table, "ai_peer_reviews")
        if rows:
            self.table.selectRow(0)

    @staticmethod
    def _centered_history_item(
        text: str,
        sort_value,
        *,
        stable_id: int,
    ) -> QTableWidgetItem:
        item = create_typed_item(text, sort_value, stable_id=stable_id)
        item.setData(
            Qt.ItemDataRole.TextAlignmentRole,
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
        )
        return item

    def _selected_proposal_ids(self) -> list[int]:
        selected_rows = self.proposals_table.selectionModel().selectedRows()
        proposal_ids: list[int] = []
        for model_index in selected_rows:
            item = self.proposals_table.item(model_index.row(), 0)
            if item is None:
                continue
            proposal_id = item.data(Qt.ItemDataRole.UserRole)
            if proposal_id is not None:
                proposal_ids.append(int(proposal_id))
        return proposal_ids

    def _incorporate_current_proposal(self) -> None:
        selected = self._selected_proposal_ids()
        if len(selected) != 1:
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                "Vyberte právě jeden návrh ke zapracování.",
            )
            return
        self._incorporate_proposal_ids(selected)

    def _incorporate_selected_proposals(self) -> None:
        selected = self._selected_proposal_ids()
        if not selected:
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                "Vyberte alespoň jeden návrh ke zapracování.",
            )
            return
        self._incorporate_proposal_ids(selected)

    def _reject_current_proposals(self) -> None:
        selected = self._selected_proposal_ids()
        if len(selected) != 1:
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                "Vyberte právě jeden návrh k zamítnutí.",
            )
            return
        self._reject_proposal_ids(selected)

    def _reject_selected_proposals(self) -> None:
        selected = self._selected_proposal_ids()
        if not selected:
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                "Vyberte alespoň jeden návrh k zamítnutí.",
            )
            return
        self._reject_proposal_ids(selected)

    def _reject_proposal_ids(self, proposal_ids: list[int]) -> None:
        from moduly.rizeni_rizik.constants_library import CATALOG_AI_PROPOSAL_REJECT_SUCCESS
        from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
            hazard_catalog_proposal_incorporate_service,
        )

        rejected = hazard_catalog_proposal_incorporate_service.reject_proposals(proposal_ids)
        if rejected <= 0:
            return
        self.refresh()
        if self._on_catalog_incorporated is not None:
            self._on_catalog_incorporated(None)
        QMessageBox.information(
            self,
            AI_PEER_REVIEW_DIALOG_TITLE,
            CATALOG_AI_PROPOSAL_REJECT_SUCCESS.format(count=rejected),
        )

    def _edit_selected_proposals(self) -> None:
        if self._uses_proposal_packages:
            self._edit_selected_package()
            return
        if not self._evidence_only_import:
            return
        selected = self._selected_proposal_ids()
        if len(selected) != 1:
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                "Vyberte právě jeden návrh k úpravě.",
            )
            return
        proposal = ai_peer_review_service.get_proposal_by_id(selected[0])
        if proposal is None:
            return
        from moduly.rizeni_rizik.ui.hazard_catalog_ai_proposal_edit_dialog import (
            HazardCatalogAiProposalEditDialog,
        )

        dialog = HazardCatalogAiProposalEditDialog(self, proposal=proposal)
        if dialog.exec():
            self._load_proposals_table()

    def _selected_package_record_id(self) -> int | None:
        selected = self._selected_proposal_ids()
        if len(selected) != 1:
            return None
        return selected[0]

    def _selected_package_requires_no_decision(self, record_id: int) -> bool:
        if self._package_session is not None:
            item = self._package_session.get_package(record_id)
            if item is not None:
                return not item.package.requires_user_decision
        for record in ai_peer_review_service.get_packages_for_review(
            self._selected_review_id() or 0
        ):
            if int(record.id) != int(record_id):
                continue
            from core.ai_oponentni.repository.ai_proposal_package_repository import (
                AiProposalPackageRepository,
            )

            package = AiProposalPackageRepository.package_from_record(record)
            return not package.requires_user_decision
        return False

    def _load_package_detail(self) -> None:
        if self.package_detail is None:
            return
        from moduly.rizeni_rizik.constants_library import CATALOG_AI_PACKAGE_EMPTY_DETAIL
        from core.ai_oponentni.sluzby.proposal_package_detail import (
            format_proposal_package_detail,
        )

        record_id = self._selected_package_record_id()
        if record_id is None:
            self.package_detail.setPlainText(CATALOG_AI_PACKAGE_EMPTY_DETAIL)
            return

        package = None
        review_id = None
        if self._package_session is not None:
            item = self._package_session.get_package(record_id)
            if item is None:
                self.package_detail.setPlainText(CATALOG_AI_PACKAGE_EMPTY_DETAIL)
                return
            package = item.package
            review_id = item.review_id
        else:
            record = ai_peer_review_service.package_repository.get_by_id(record_id)
            if record is None:
                self.package_detail.setPlainText(CATALOG_AI_PACKAGE_EMPTY_DETAIL)
                return
            package = ai_peer_review_service.package_repository.package_from_record(record)
            review_id = record.ai_peer_review_id

        resolved_name = None
        if package.target_event_export_id:
            from moduly.rizeni_rizik.ui.hazard_catalog_ai_package_edit_dialog import (
                resolve_target_event_name,
            )

            resolved_name = resolve_target_event_name(
                package_record_id=record_id if record_id > 0 else None,
                target_event_export_id=package.target_event_export_id,
                review_id=review_id,
            )
        self.package_detail.setPlainText(
            format_proposal_package_detail(
                package,
                resolved_target_event_name=resolved_name,
            ),
        )

    def _edit_selected_package(self) -> None:
        from moduly.rizeni_rizik.constants_library import CATALOG_AI_PACKAGE_SELECT_ONE
        from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
            HazardCatalogPackageIncorporateError,
            hazard_catalog_package_incorporate_service,
        )
        from moduly.rizeni_rizik.ui.hazard_catalog_ai_package_edit_dialog import (
            HazardCatalogAiPackageEditDialog,
        )

        record_id = self._selected_package_record_id()
        if record_id is None:
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                CATALOG_AI_PACKAGE_SELECT_ONE,
            )
            return

        if self._package_session is not None:
            item = self._package_session.get_package(record_id)
            if item is None:
                QMessageBox.warning(
                    self,
                    AI_PEER_REVIEW_DIALOG_TITLE,
                    CATALOG_AI_PACKAGE_SELECT_ONE,
                )
                self._load_proposals_table()
                return
            package = item.package
            if package.is_measure_recommendation:
                QMessageBox.information(
                    self,
                    AI_PEER_REVIEW_DIALOG_TITLE,
                    "Doporučení k opatřením nelze editovat jako balík události. "
                    "Převzít nebo zamítnout lze přímo ze seznamu.",
                )
                return
            dialog = HazardCatalogAiPackageEditDialog(
                self,
                package=package,
                package_record_id=item.db_id or 0,
                review_id=item.review_id,
            )
        else:
            record = ai_peer_review_service.package_repository.get_by_id(record_id)
            if record is None:
                QMessageBox.warning(
                    self,
                    AI_PEER_REVIEW_DIALOG_TITLE,
                    CATALOG_AI_PACKAGE_SELECT_ONE,
                )
                self._load_proposals_table()
                return
            package = ai_peer_review_service.package_repository.package_from_record(record)
            if package.is_measure_recommendation:
                QMessageBox.information(
                    self,
                    AI_PEER_REVIEW_DIALOG_TITLE,
                    "Doporučení k opatřením nelze editovat jako balík události. "
                    "Převzít nebo zamítnout lze přímo ze seznamu.",
                )
                return
            dialog = HazardCatalogAiPackageEditDialog(
                self,
                package=package,
                package_record_id=record_id,
            )

        from core.widgets.dialog_utils import exec_maximized

        if not exec_maximized(dialog):
            return
        updated = dialog.get_package()
        if updated is None:
            return
        try:
            if self._package_session is not None:
                self._package_session.update_package(record_id, updated)
            else:
                hazard_catalog_package_incorporate_service.update_package_payload(
                    record_id,
                    updated,
                )
        except (HazardCatalogPackageIncorporateError, ValueError) as error:
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))
            return

        self._load_proposals_table()
        self._select_proposal_row(record_id)
        if dialog.incorporate_requested():
            self._incorporate_selected_package()
            return

        self._load_package_detail()
        if self._package_session is not None and self._on_catalog_incorporated is not None:
            self._on_catalog_incorporated(None)

    def _incorporate_selected_package(self) -> None:
        from moduly.rizeni_rizik.constants_library import (
            CATALOG_AI_PACKAGE_INCORPORATE_SUCCESS,
            CATALOG_AI_PACKAGE_SELECT_ONE,
        )
        from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
            HazardCatalogPackageAmbiguousGroupError,
            HazardCatalogPackageIncorporateError,
            hazard_catalog_package_incorporate_service,
        )
        from moduly.rizeni_rizik.ui.hazard_catalog_package_ambiguous_group_dialog import (
            HazardCatalogPackageAmbiguousGroupDialog,
        )

        record_id = self._selected_package_record_id()
        if record_id is None or self._source_id is None:
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                CATALOG_AI_PACKAGE_SELECT_ONE,
            )
            return
        if self._selected_package_requires_no_decision(record_id):
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                AI_PEER_REVIEW_NO_CHANGE_CANNOT_DECIDE_MESSAGE,
            )
            return

        overrides: dict[int, int] = {}
        while True:
            try:
                incorporate = (
                    self._package_incorporate_handler
                    if self._package_incorporate_handler is not None
                    else hazard_catalog_package_incorporate_service.incorporate_package
                )
                result = incorporate(
                    template_id=self._source_id,
                    package_record_id=record_id,
                    group_assessment_overrides=overrides or None,
                )
                break
            except HazardCatalogPackageAmbiguousGroupError as error:
                dialog = HazardCatalogPackageAmbiguousGroupDialog(
                    self,
                    group_name=error.group_name,
                    candidates=error.candidates,
                )
                if not dialog.exec() or dialog.selected_assessment_id is None:
                    return
                overrides[error.group_id] = dialog.selected_assessment_id
            except HazardCatalogPackageIncorporateError as error:
                QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))
                return

        self.refresh()
        if self._on_catalog_incorporated is not None:
            self._on_catalog_incorporated(result.new_revision_number)
        if result.new_revision_number:
            success_text = CATALOG_AI_PACKAGE_INCORPORATE_SUCCESS.format(
                revision=result.new_revision_number,
            )
        else:
            from moduly.rizeni_rizik.constants_library import (
                CATALOG_AI_PACKAGE_INCORPORATE_PENDING_SAVE,
            )

            success_text = CATALOG_AI_PACKAGE_INCORPORATE_PENDING_SAVE
        QMessageBox.information(
            self,
            AI_PEER_REVIEW_DIALOG_TITLE,
            success_text,
        )

    def _reject_selected_package(self) -> None:
        from moduly.rizeni_rizik.constants_library import (
            CATALOG_AI_PACKAGE_REJECT_SUCCESS,
            CATALOG_AI_PACKAGE_SELECT_ONE,
        )
        from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
            hazard_catalog_package_incorporate_service,
        )

        record_id = self._selected_package_record_id()
        if record_id is None:
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                CATALOG_AI_PACKAGE_SELECT_ONE,
            )
            return
        if self._selected_package_requires_no_decision(record_id):
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                AI_PEER_REVIEW_NO_CHANGE_CANNOT_DECIDE_MESSAGE,
            )
            return
        if self._package_session is not None:
            if not self._package_session.reject_package(record_id):
                return
            review_id = self._selected_review_id()
            if review_id is not None:
                self._package_session.sync_review_stats(review_id)
        elif not hazard_catalog_package_incorporate_service.reject_package(record_id):
            return
        self.refresh()
        if self._on_catalog_incorporated is not None:
            self._on_catalog_incorporated(None)
        QMessageBox.information(
            self,
            AI_PEER_REVIEW_DIALOG_TITLE,
            CATALOG_AI_PACKAGE_REJECT_SUCCESS,
        )

    def _select_proposal_row(self, proposal_id: int) -> None:
        for row_index in range(self.proposals_table.rowCount()):
            item = self.proposals_table.item(row_index, 0)
            if item is None:
                continue
            if item.data(Qt.ItemDataRole.UserRole) == proposal_id:
                self.proposals_table.selectRow(row_index)
                self.proposals_table.scrollToItem(item)
                return

    def _show_incorporate_summary(self, result) -> None:
        from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
            format_incorporate_summary,
        )

        QMessageBox.information(
            self,
            AI_PEER_REVIEW_DIALOG_TITLE,
            format_incorporate_summary(
                newly_incorporated=result.newly_incorporated_count,
                used_existing=result.used_existing_count,
                requires_manual_decision=result.requires_manual_decision_count,
                skipped=result.skipped_count,
                rejected=0,
                revision=result.new_revision_number,
            ),
        )

    def _offer_manual_completion_guide(self, manual_count: int) -> bool:
        from moduly.rizeni_rizik.constants_library import (
            CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_LATER_BUTTON,
            CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_OFFER_TEXT,
            CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_OFFER_TITLE,
            CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_OPEN_BUTTON,
        )

        message = QMessageBox(self)
        message.setIcon(QMessageBox.Icon.Question)
        message.setWindowTitle(CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_OFFER_TITLE)
        message.setText(
            CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_OFFER_TEXT.format(count=manual_count),
        )
        open_button = message.addButton(
            CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_OPEN_BUTTON,
            QMessageBox.ButtonRole.AcceptRole,
        )
        later_button = message.addButton(
            CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_LATER_BUTTON,
            QMessageBox.ButtonRole.RejectRole,
        )
        message.setDefaultButton(open_button)
        message.exec()
        return message.clickedButton() == open_button

    def _incorporate_single_catalog_proposal(
        self,
        *,
        review_id: int,
        proposal_id: int,
        resolutions: dict[int, str],
    ):
        from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
            HazardCatalogProposalIncorporateError,
            hazard_catalog_proposal_incorporate_service,
        )

        if self._source_id is None:
            return None
        try:
            result = hazard_catalog_proposal_incorporate_service.incorporate_single_proposal(
                template_id=self._source_id,
                review_id=review_id,
                proposal_id=proposal_id,
                resolutions=resolutions,
            )
        except HazardCatalogProposalIncorporateError as error:
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))
            return None

        self.refresh()
        if self._on_catalog_incorporated is not None and result.new_revision_number:
            self._on_catalog_incorporated(result.new_revision_number)
        return result

    def _proposal_incorporation_succeeded(self, result) -> bool:
        if result is None:
            return False
        return (
            result.incorporated_count > 0
            or result.skipped_count > 0
            or result.used_existing_count > 0
        )

    def _assign_legal_requirement_and_incorporate(
        self,
        *,
        review_id: int,
        proposal_id: int,
        requirement_id: int,
        resolutions: dict[int, str],
    ) -> bool:
        from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
            hazard_catalog_proposal_incorporate_service,
        )

        hazard_catalog_proposal_incorporate_service.assign_proposal_legal_requirement(
            proposal_id,
            requirement_id,
        )
        result = self._incorporate_single_catalog_proposal(
            review_id=review_id,
            proposal_id=proposal_id,
            resolutions=resolutions,
        )
        return self._proposal_incorporation_succeeded(result)

    def _incorporate_proposal_if_pending(
        self,
        *,
        review_id: int,
        proposal_id: int,
        resolutions: dict[int, str],
    ) -> bool:
        proposal = ai_peer_review_service.get_proposal_by_id(proposal_id)
        if proposal is None or proposal.status != PROPOSAL_STATUS_PENDING:
            return True
        result = self._incorporate_single_catalog_proposal(
            review_id=review_id,
            proposal_id=proposal_id,
            resolutions=resolutions,
        )
        return self._proposal_incorporation_succeeded(result)

    def _assign_measure_assessment_and_incorporate(
        self,
        *,
        review_id: int,
        proposal_id: int,
        assessment_export_id: str | None = None,
        assessment_id: int | None = None,
        resolutions: dict[int, str],
    ) -> bool:
        from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
            hazard_catalog_proposal_incorporate_service,
        )

        if assessment_id is not None:
            hazard_catalog_proposal_incorporate_service.assign_proposal_assessment_by_id(
                proposal_id,
                review_id,
                assessment_id,
            )
        elif assessment_export_id:
            hazard_catalog_proposal_incorporate_service.assign_proposal_assessment(
                proposal_id,
                assessment_export_id,
            )
        else:
            return False

        result = self._incorporate_single_catalog_proposal(
            review_id=review_id,
            proposal_id=proposal_id,
            resolutions=resolutions,
        )
        return result is not None and result.incorporated_count > 0

    def _create_assessment_for_measure_proposal(
        self,
        *,
        review_id: int,
        proposal_id: int,
        proposal_name: str,
        event_choices: tuple[tuple[int, str], ...],
        resolutions: dict[int, str],
        progress_label: str = "",
    ) -> bool:
        from moduly.rizeni_rizik.constants_library import (
            CATALOG_AI_PROPOSAL_ASSESSMENT_CREATE_EVENT_DIALOG_TITLE,
        )
        from moduly.rizeni_rizik.ui.hazard_catalog_proposal_assessment_choice_dialog import (
            HazardCatalogProposalAssessmentCreateDialog,
        )
        from moduly.rizeni_rizik.ui.hazard_catalog_proposal_requirement_choice_dialog import (
            HazardCatalogProposalRequirementChoiceDialog,
        )
        from moduly.rizeni_rizik.ui.hazard_library_template_assessment_dialog import (
            HazardLibraryTemplateAssessmentDialog,
        )
        from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
            CATALOG_DUPLICATE_ACTION_CREATE,
            CATALOG_DUPLICATE_ACTION_SKIP,
        )

        if self._source_id is None:
            return False

        create_dialog = HazardCatalogProposalAssessmentCreateDialog(
            self,
            proposal_name=proposal_name,
        )
        if progress_label:
            create_dialog.setWindowTitle(f"{create_dialog.windowTitle()} – {progress_label}")
        if not create_dialog.exec():
            return False
        if create_dialog.selected_action == CATALOG_DUPLICATE_ACTION_SKIP:
            resolutions[proposal_id] = CATALOG_DUPLICATE_ACTION_SKIP
            return True
        if create_dialog.selected_action != CATALOG_DUPLICATE_ACTION_CREATE:
            return False

        if not event_choices:
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                "Ve zdroji rizika zatím není žádná nežádoucí událost. "
                "Nejdříve založte událost v odborném obsahu zdroje.",
            )
            return False

        template_event_id = event_choices[0][0]
        if len(event_choices) > 1:
            event_dialog = HazardCatalogProposalRequirementChoiceDialog(
                self,
                proposal_name=proposal_name,
                candidates=event_choices,
                intro_text=(
                    "Vyberte nežádoucí událost, ke které se má nové posouzení vztahovat."
                ),
            )
            event_dialog.setWindowTitle(CATALOG_AI_PROPOSAL_ASSESSMENT_CREATE_EVENT_DIALOG_TITLE)
            if progress_label:
                event_dialog.setWindowTitle(
                    f"{event_dialog.windowTitle()} – {progress_label}",
                )
            if not event_dialog.exec():
                return False
            if event_dialog.selected_action == CATALOG_DUPLICATE_ACTION_SKIP:
                resolutions[proposal_id] = CATALOG_DUPLICATE_ACTION_SKIP
                return True
            if event_dialog.selected_requirement_id is None:
                return False
            template_event_id = event_dialog.selected_requirement_id

        assessment_dialog = HazardLibraryTemplateAssessmentDialog(
            self,
            template_id=self._source_id,
            template_event_id=template_event_id,
        )
        if progress_label:
            assessment_dialog.setWindowTitle(
                f"{assessment_dialog.windowTitle()} – {progress_label}",
            )
        if not assessment_dialog.exec():
            return False

        saved = assessment_dialog.saved_assessment
        if saved is None:
            return False

        return self._assign_measure_assessment_and_incorporate(
            review_id=review_id,
            proposal_id=proposal_id,
            assessment_id=saved.id,
            resolutions=resolutions,
        )

    def _resolve_incorporation_plan_interactively(
        self,
        *,
        review_id: int,
        plan,
        allow_manual_legal_pick: bool = False,
        auto_incorporate: bool = False,
        progress_label: str = "",
    ) -> tuple[dict[int, str], bool] | None:
        from moduly.rizeni_rizik.constants_library import (
            CATALOG_AI_PROPOSAL_MANUAL_REQUIREMENT_INTRO,
        )
        from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
            hazard_catalog_proposal_incorporate_service,
        )
        from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
            CATALOG_CONFLICT_TYPE_ASSESSMENT_CHOICE,
            CATALOG_CONFLICT_TYPE_ASSESSMENT_CREATE,
            CATALOG_CONFLICT_TYPE_DUPLICATE,
            CATALOG_CONFLICT_TYPE_REQUIREMENT_CHOICE,
            CATALOG_DUPLICATE_ACTION_CANCEL,
            CATALOG_DUPLICATE_ACTION_EDIT,
            CATALOG_DUPLICATE_ACTION_SKIP,
            CATALOG_PROPOSAL_KIND_EXISTING_MEASURE,
            CATALOG_PROPOSAL_KIND_LEGAL,
            CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE,
            classify_catalog_proposal,
        )
        from moduly.rizeni_rizik.ui.hazard_catalog_ai_proposal_edit_dialog import (
            HazardCatalogAiProposalEditDialog,
        )
        from moduly.rizeni_rizik.ui.hazard_catalog_proposal_assessment_choice_dialog import (
            HazardCatalogProposalAssessmentChoiceDialog,
            HazardCatalogProposalAssessmentCreateDialog,
        )
        from moduly.rizeni_rizik.ui.hazard_catalog_proposal_duplicate_dialog import (
            HazardCatalogProposalDuplicateDialog,
        )
        from moduly.rizeni_rizik.ui.hazard_catalog_proposal_requirement_choice_dialog import (
            HazardCatalogProposalRequirementChoiceDialog,
        )

        resolutions = dict(plan.resolutions)
        pending_conflicts = list(plan.conflicts)
        pending_manual_ids = list(plan.pending_proposal_ids)
        conflict_index = 0

        while pending_manual_ids and allow_manual_legal_pick:
            proposal_id = pending_manual_ids[0]
            proposal = ai_peer_review_service.get_proposal_by_id(proposal_id)
            if proposal is None or proposal.status != PROPOSAL_STATUS_PENDING:
                pending_manual_ids.pop(0)
                continue

            self._select_proposal_row(proposal_id)
            proposal_kind = classify_catalog_proposal(proposal)
            if proposal_kind in {
                CATALOG_PROPOSAL_KIND_EXISTING_MEASURE,
                CATALOG_PROPOSAL_KIND_REQUIRED_MEASURE,
            }:
                measure_plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
                    template_id=self._source_id,
                    review_id=review_id,
                    proposal_ids=[proposal_id],
                )
                measure_resolved = self._resolve_incorporation_plan_interactively(
                    review_id=review_id,
                    plan=measure_plan,
                    allow_manual_legal_pick=False,
                    auto_incorporate=auto_incorporate,
                    progress_label=progress_label,
                )
                if measure_resolved is None:
                    return None
                child_resolutions, _ = measure_resolved
                resolutions.update(child_resolutions)
                if auto_incorporate and not self._incorporate_proposal_if_pending(
                    review_id=review_id,
                    proposal_id=proposal_id,
                    resolutions=resolutions,
                ):
                    return None
                pending_manual_ids.pop(0)
                continue

            if proposal_kind != CATALOG_PROPOSAL_KIND_LEGAL:
                pending_manual_ids.pop(0)
                continue

            candidates = hazard_catalog_proposal_incorporate_service.list_legal_requirement_candidates()
            if not candidates:
                edit_dialog = HazardCatalogAiProposalEditDialog(self, proposal=proposal)
                if not edit_dialog.exec():
                    return None
                pending_manual_ids.pop(0)
                refreshed = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
                    template_id=self._source_id,
                    review_id=review_id,
                    proposal_ids=[proposal_id],
                )
                resolutions.update(refreshed.resolutions)
                pending_conflicts.extend(refreshed.conflicts)
                pending_manual_ids = list(refreshed.pending_proposal_ids)
                continue

            dialog = HazardCatalogProposalRequirementChoiceDialog(
                self,
                proposal_name=proposal.name,
                candidates=candidates,
                intro_text=CATALOG_AI_PROPOSAL_MANUAL_REQUIREMENT_INTRO,
            )
            if progress_label:
                dialog.setWindowTitle(
                    f"{dialog.windowTitle()} – {progress_label}",
                )
            if not dialog.exec():
                return None
            if dialog.selected_action == CATALOG_DUPLICATE_ACTION_CANCEL:
                return None
            if dialog.selected_action == CATALOG_DUPLICATE_ACTION_SKIP:
                resolutions[proposal_id] = CATALOG_DUPLICATE_ACTION_SKIP
                if auto_incorporate:
                    if not self._incorporate_proposal_if_pending(
                        review_id=review_id,
                        proposal_id=proposal_id,
                        resolutions=resolutions,
                    ):
                        return None
                pending_manual_ids.pop(0)
                continue
            if dialog.selected_requirement_id is not None:
                if auto_incorporate:
                    if not self._assign_legal_requirement_and_incorporate(
                        review_id=review_id,
                        proposal_id=proposal_id,
                        requirement_id=dialog.selected_requirement_id,
                        resolutions=resolutions,
                    ):
                        refreshed = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
                            template_id=self._source_id,
                            review_id=review_id,
                            proposal_ids=[proposal_id],
                        )
                        resolutions.update(refreshed.resolutions)
                        pending_conflicts.extend(refreshed.conflicts)
                        pending_manual_ids = list(refreshed.pending_proposal_ids)
                        continue
                    pending_manual_ids.pop(0)
                    continue
                hazard_catalog_proposal_incorporate_service.assign_proposal_legal_requirement(
                    proposal_id,
                    dialog.selected_requirement_id,
                )
                refreshed = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
                    template_id=self._source_id,
                    review_id=review_id,
                    proposal_ids=[proposal_id],
                )
                resolutions.update(refreshed.resolutions)
                pending_conflicts.extend(refreshed.conflicts)
                pending_manual_ids = list(refreshed.pending_proposal_ids)
                continue
            return None

        while conflict_index < len(pending_conflicts):
            conflict = pending_conflicts[conflict_index]
            proposal = ai_peer_review_service.get_proposal_by_id(conflict.proposal_id)
            if proposal is None or proposal.status != PROPOSAL_STATUS_PENDING:
                conflict_index += 1
                continue

            self._select_proposal_row(conflict.proposal_id)

            if conflict.conflict_type == CATALOG_CONFLICT_TYPE_REQUIREMENT_CHOICE:
                dialog = HazardCatalogProposalRequirementChoiceDialog(
                    self,
                    proposal_name=conflict.proposal_label,
                    candidates=conflict.requirement_candidates,
                )
                if progress_label:
                    dialog.setWindowTitle(
                        f"{dialog.windowTitle()} – {progress_label}",
                    )
                if not dialog.exec():
                    return None
                if dialog.selected_action == CATALOG_DUPLICATE_ACTION_CANCEL:
                    return None
                if dialog.selected_action == CATALOG_DUPLICATE_ACTION_SKIP:
                    resolutions[proposal.id] = CATALOG_DUPLICATE_ACTION_SKIP
                    if auto_incorporate and not self._incorporate_proposal_if_pending(
                        review_id=review_id,
                        proposal_id=proposal.id,
                        resolutions=resolutions,
                    ):
                        return None
                    conflict_index += 1
                    continue
                if dialog.selected_requirement_id is not None:
                    if auto_incorporate:
                        if not self._assign_legal_requirement_and_incorporate(
                            review_id=review_id,
                            proposal_id=proposal.id,
                            requirement_id=dialog.selected_requirement_id,
                            resolutions=resolutions,
                        ):
                            refreshed = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
                                template_id=self._source_id,
                                review_id=review_id,
                                proposal_ids=[proposal.id],
                            )
                            resolutions.update(refreshed.resolutions)
                            pending_conflicts.extend(refreshed.conflicts)
                            conflict_index += 1
                            continue
                    else:
                        hazard_catalog_proposal_incorporate_service.assign_proposal_legal_requirement(
                            proposal.id,
                            dialog.selected_requirement_id,
                        )
                        refreshed = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
                            template_id=self._source_id,
                            review_id=review_id,
                            proposal_ids=[proposal.id],
                        )
                        resolutions.update(refreshed.resolutions)
                        pending_conflicts.extend(refreshed.conflicts)
                    conflict_index += 1
                    continue

            if conflict.conflict_type == CATALOG_CONFLICT_TYPE_ASSESSMENT_CREATE:
                if not self._create_assessment_for_measure_proposal(
                    review_id=review_id,
                    proposal_id=proposal.id,
                    proposal_name=conflict.proposal_label,
                    event_choices=conflict.template_event_choices,
                    resolutions=resolutions,
                    progress_label=progress_label,
                ):
                    return None
                conflict_index += 1
                continue

            if conflict.conflict_type == CATALOG_CONFLICT_TYPE_ASSESSMENT_CHOICE:
                dialog = HazardCatalogProposalAssessmentChoiceDialog(
                    self,
                    proposal_name=conflict.proposal_label,
                    candidates=conflict.assessment_candidates,
                )
                if progress_label:
                    dialog.setWindowTitle(
                        f"{dialog.windowTitle()} – {progress_label}",
                    )
                if not dialog.exec():
                    return None
                if dialog.selected_action == CATALOG_DUPLICATE_ACTION_CANCEL:
                    return None
                if dialog.selected_action == CATALOG_DUPLICATE_ACTION_SKIP:
                    resolutions[proposal.id] = CATALOG_DUPLICATE_ACTION_SKIP
                    if auto_incorporate and not self._incorporate_proposal_if_pending(
                        review_id=review_id,
                        proposal_id=proposal.id,
                        resolutions=resolutions,
                    ):
                        return None
                    conflict_index += 1
                    continue
                if dialog.selected_assessment_export_id:
                    incorporated = self._assign_measure_assessment_and_incorporate(
                        review_id=review_id,
                        proposal_id=proposal.id,
                        assessment_export_id=dialog.selected_assessment_export_id,
                        resolutions=resolutions,
                    )
                    if not incorporated:
                        if auto_incorporate and not self._incorporate_proposal_if_pending(
                            review_id=review_id,
                            proposal_id=proposal.id,
                            resolutions=resolutions,
                        ):
                            refreshed = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
                                template_id=self._source_id,
                                review_id=review_id,
                                proposal_ids=[proposal.id],
                            )
                            resolutions.update(refreshed.resolutions)
                            pending_conflicts.extend(refreshed.conflicts)
                conflict_index += 1
                continue

            while True:
                if conflict.conflict_type != CATALOG_CONFLICT_TYPE_DUPLICATE or conflict.duplicate is None:
                    break
                dialog = HazardCatalogProposalDuplicateDialog(
                    self,
                    proposal_name=conflict.proposal_label,
                    duplicate=conflict.duplicate,
                )
                if progress_label:
                    dialog.setWindowTitle(
                        f"{dialog.windowTitle()} – {progress_label}",
                    )
                if not dialog.exec():
                    return None
                action = dialog.selected_action
                if action == CATALOG_DUPLICATE_ACTION_CANCEL:
                    return None
                if action == CATALOG_DUPLICATE_ACTION_EDIT:
                    edit_dialog = HazardCatalogAiProposalEditDialog(self, proposal=proposal)
                    if not edit_dialog.exec():
                        return None
                    proposal = ai_peer_review_service.get_proposal_by_id(proposal.id)
                    if proposal is None:
                        return None
                    refreshed = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
                        template_id=self._source_id,
                        review_id=review_id,
                        proposal_ids=[proposal.id],
                    )
                    if refreshed.conflicts:
                        conflict = refreshed.conflicts[0]
                        continue
                    resolutions.update(refreshed.resolutions)
                    if proposal.id not in refreshed.resolutions:
                        resolutions.pop(proposal.id, None)
                    break
                resolutions[proposal.id] = action
                break
            if auto_incorporate and not self._incorporate_proposal_if_pending(
                review_id=review_id,
                proposal_id=proposal.id,
                resolutions=resolutions,
            ):
                return None
            conflict_index += 1

        return resolutions, True

    def _run_manual_completion_guide(
        self,
        proposal_ids: list[int],
        review_id: int,
        accumulated,
    ):
        from moduly.rizeni_rizik.constants_library import (
            CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_PROGRESS,
        )
        from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
            CatalogIncorporateResult,
            HazardCatalogProposalIncorporateError,
            hazard_catalog_proposal_incorporate_service,
        )

        remaining = list(proposal_ids)
        total = len(remaining)
        current_result = accumulated

        while remaining:
            proposal_id = remaining[0]
            proposal = ai_peer_review_service.get_proposal_by_id(proposal_id)
            if proposal is None or proposal.status != PROPOSAL_STATUS_PENDING:
                remaining.pop(0)
                continue

            self._select_proposal_row(proposal_id)
            progress_label = CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_PROGRESS.format(
                current=total - len(remaining) + 1,
                total=total,
                proposal_name=proposal.name,
            )

            plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
                template_id=self._source_id,
                review_id=review_id,
                proposal_ids=[proposal_id],
            )
            resolved = self._resolve_incorporation_plan_interactively(
                review_id=review_id,
                plan=plan,
                allow_manual_legal_pick=True,
                auto_incorporate=True,
                progress_label=progress_label,
            )
            if resolved is None:
                return None
            resolutions, _ = resolved

            proposal = ai_peer_review_service.get_proposal_by_id(proposal_id)
            if proposal is not None and proposal.status == PROPOSAL_STATUS_PENDING:
                try:
                    step_result = hazard_catalog_proposal_incorporate_service.incorporate_single_proposal(
                        template_id=self._source_id,
                        review_id=review_id,
                        proposal_id=proposal_id,
                        resolutions=resolutions,
                    )
                except HazardCatalogProposalIncorporateError as error:
                    QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))
                    return None
            else:
                step_result = CatalogIncorporateResult(
                    incorporated_count=0,
                    newly_incorporated_count=0,
                    used_existing_count=0,
                    skipped_count=0,
                    requires_manual_decision_count=0,
                    manual_decision_proposal_ids=[],
                    merged_count=0,
                    new_revision_number=None,
                )

            current_result = hazard_catalog_proposal_incorporate_service.merge_incorporate_results(
                current_result,
                step_result,
            )
            if self._on_catalog_incorporated is not None and step_result.new_revision_number:
                self._on_catalog_incororporated(step_result.new_revision_number)

            remaining.pop(0)
            self.refresh()

        return CatalogIncorporateResult(
            incorporated_count=current_result.incorporated_count,
            newly_incorporated_count=current_result.newly_incorporated_count,
            used_existing_count=current_result.used_existing_count,
            skipped_count=current_result.skipped_count,
            requires_manual_decision_count=0,
            manual_decision_proposal_ids=[],
            merged_count=current_result.merged_count,
            new_revision_number=current_result.new_revision_number,
        )

    def _incorporate_proposal_ids(self, proposal_ids: list[int]) -> None:
        if self._source_id is None:
            return
        review_id = self._selected_review_id()
        if review_id is None:
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                "Vyberte konzultaci s návrhy.",
            )
            return

        from moduly.rizeni_rizik.constants_library import (
            CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_DEFERRED,
        )
        from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
            HazardCatalogProposalIncorporateError,
            hazard_catalog_proposal_incorporate_service,
        )

        plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self._source_id,
            review_id=review_id,
            proposal_ids=proposal_ids,
        )
        resolved = self._resolve_incorporation_plan_interactively(
            review_id=review_id,
            plan=plan,
            allow_manual_legal_pick=False,
            auto_incorporate=True,
        )
        if resolved is None:
            return
        resolutions, _ = resolved

        final_plan = hazard_catalog_proposal_incorporate_service.prepare_incorporation(
            template_id=self._source_id,
            review_id=review_id,
            proposal_ids=proposal_ids,
        )
        merged_resolutions = dict(final_plan.resolutions)
        merged_resolutions.update(resolutions)

        try:
            result = hazard_catalog_proposal_incorporate_service.incorporate_proposals(
                template_id=self._source_id,
                review_id=review_id,
                proposal_ids=proposal_ids,
                resolutions=merged_resolutions,
                pending_proposal_ids=final_plan.pending_proposal_ids,
            )
        except HazardCatalogProposalIncorporateError as error:
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, format_ai_peer_review_user_error(error))
            return

        self.refresh()
        if self._on_catalog_incorporated is not None:
            self._on_catalog_incorporated(result.new_revision_number)

        if result.requires_manual_decision_count > 0:
            if self._offer_manual_completion_guide(result.requires_manual_decision_count):
                final_result = self._run_manual_completion_guide(
                    result.manual_decision_proposal_ids,
                    review_id,
                    result,
                )
                if final_result is None:
                    return
                self._show_incorporate_summary(final_result)
            else:
                QMessageBox.information(
                    self,
                    AI_PEER_REVIEW_DIALOG_TITLE,
                    CATALOG_AI_PROPOSAL_MANUAL_COMPLETION_DEFERRED,
                )
            return

        if (
            result.incorporated_count > 0
            or result.skipped_count > 0
            or result.used_existing_count > 0
        ):
            self._show_incorporate_summary(result)
