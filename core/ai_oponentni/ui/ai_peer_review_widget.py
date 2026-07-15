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
    AI_PEER_REVIEW_OBJECTIVE_LABELS,
    AI_PEER_REVIEW_ROLE_LABELS,
    AI_PEER_REVIEW_ROLES,
    AI_PEER_REVIEW_TABLE_HEADERS,
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
        self.setWindowTitle("Načíst odpověď AI")
        self.resize(640, 480)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.ai_model = QLineEdit()
        self.ai_model.setPlaceholderText("např. ChatGPT, Claude, …")
        form.addRow("Model AI:", self.ai_model)
        layout.addLayout(form)

        layout.addWidget(QLabel("Odpověď AI:"))
        self.response = QPlainTextEdit()
        self.response.setPlaceholderText(
            "Vložte odpověď AI ve formátu JSON 1.1 (dle schema_odpovedi.json), "
            "textovém formátu Oblast / Návrh / Zdůvodnění, nebo načtěte soubor "
            ".json, .txt či .zip."
        )
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
            "Načíst odpověď AI",
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
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, str(error))

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
                            str(error),
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
                QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, str(error))
                return

        self.response.setPlainText(result.text)

    def get_ai_model(self) -> str:
        return self.ai_model.text().strip()

    def get_response_text(self) -> str:
        return self.response.toPlainText().strip()


class AiPeerReviewWidget(QWidget):
    """Obecný widget oponentního posouzení – hostí libovolný doménový provider."""

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
        configure_table_columns(self.table, "ai_peer_reviews")
        self.table.itemSelectionChanged.connect(self._load_proposals_table)
        layout.addWidget(self.table)

        self.proposals_label = QLabel("Návrhy vybrané konzultace:")
        layout.addWidget(self.proposals_label)
        self.proposals_table = QTableWidget()
        self.proposals_table.setColumnCount(5)
        self.proposals_table.setHorizontalHeaderLabels(
            ["Oblast", "Návrh", "Zdůvodnění", "Stav", "ID návrhu"],
        )
        if self._evidence_only_import:
            self.proposals_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        else:
            self.proposals_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.proposals_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.proposals_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.proposals_table.setAlternatingRowColors(True)
        configure_table_columns(self.proposals_table, "ai_peer_review_proposals")
        self.proposals_table.doubleClicked.connect(self._edit_selected_proposals)
        layout.addWidget(self.proposals_table)

        if self._evidence_only_import:
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
        else:
            self.incorporate_btn = None
            self.reject_proposal_btn = None
            self.edit_proposal_btn = None
            self.incorporate_selected_btn = None
            self.reject_selected_btn = None

        self.export_btn.clicked.connect(self.export_package)
        self.import_btn.clicked.connect(self.import_response)
        self.set_source(None)

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
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, str(error))
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
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, str(error))
            return False
        except Exception as error:  # pragma: no cover - defensive
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, str(error))
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
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, str(error))
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
            )
        except AiPeerReviewError as error:
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, str(error))
            return False

        if parse_result.skipped_count:
            reasons = "\n".join(
                f"- {reason}" for reason in parse_result.skip_reasons[:12]
            )
            extra = ""
            if len(parse_result.skip_reasons) > 12:
                extra = f"\n… a dalších {len(parse_result.skip_reasons) - 12}."
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                (
                    f"Načteno platných návrhů: {len(parse_result.proposals)}\n"
                    f"Přeskočeno neplatných návrhů: {parse_result.skipped_count}\n\n"
                    f"{reasons}{extra}"
                ),
            )

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
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, str(error))
            return False

        self.refresh()
        self._select_review_row(updated.id)
        if self._on_proposals_applied is not None:
            self._on_proposals_applied()

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
                QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, str(error))
                return None
        if clicked is replace_button:
            ai_peer_review_service.delete_proposals_for_review(review.id)
            return review
        return None

    def _import_summary_message(self, review, format_label: str) -> str:
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

        proposals = ai_peer_review_service.get_unassigned_for_review(review_id)
        if self._evidence_only_import:
            proposals = [
                proposal
                for proposal in proposals
                if proposal.status == PROPOSAL_STATUS_PENDING
            ]
        self.proposals_table.setRowCount(len(proposals))
        for row_index, proposal in enumerate(proposals):
            area_item = QTableWidgetItem(proposal.area or "—")
            area_item.setData(Qt.ItemDataRole.UserRole, proposal.id)
            self.proposals_table.setItem(row_index, 0, area_item)
            self.proposals_table.setItem(
                row_index,
                1,
                QTableWidgetItem(proposal.name),
            )
            self.proposals_table.setItem(
                row_index,
                2,
                QTableWidgetItem(proposal.reasoning or "—"),
            )
            self.proposals_table.setItem(
                row_index,
                3,
                QTableWidgetItem(
                    PROPOSAL_STATUS_LABELS.get(proposal.status, proposal.status),
                ),
            )
            self.proposals_table.setItem(
                row_index,
                4,
                QTableWidgetItem(proposal.proposal_id or "—"),
            )
        configure_table_columns(self.proposals_table, "ai_peer_review_proposals")

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
        self.table.setRowCount(len(rows))
        for row_index, review in enumerate(rows):
            self.table.setItem(
                row_index,
                AI_PEER_REVIEW_COL_ID,
                QTableWidgetItem(str(review.id)),
            )
            self.table.setItem(
                row_index,
                AI_PEER_REVIEW_COL_EXPORT_DATE,
                QTableWidgetItem(review.exported_at.strftime("%d.%m.%Y %H:%M")),
            )
            response_loaded = (
                review.response_loaded_at.strftime("%d.%m.%Y %H:%M")
                if review.response_loaded_at is not None
                else "—"
            )
            self.table.setItem(
                row_index,
                AI_PEER_REVIEW_COL_RESPONSE_DATE,
                QTableWidgetItem(response_loaded),
            )
            self.table.setItem(
                row_index,
                AI_PEER_REVIEW_COL_MODEL,
                QTableWidgetItem(review.ai_model or "—"),
            )
            self.table.setItem(
                row_index,
                AI_PEER_REVIEW_COL_LOADED,
                QTableWidgetItem(str(review.loaded_proposals_count)),
            )
            self.table.setItem(
                row_index,
                AI_PEER_REVIEW_COL_PENDING,
                QTableWidgetItem(str(review.pending_proposals_count)),
            )
            self.table.setItem(
                row_index,
                AI_PEER_REVIEW_COL_ACCEPTED,
                QTableWidgetItem(str(review.accepted_count)),
            )
            self.table.setItem(
                row_index,
                AI_PEER_REVIEW_COL_REJECTED,
                QTableWidgetItem(str(review.rejected_count)),
            )
            self.table.setItem(
                row_index,
                AI_PEER_REVIEW_COL_UNASSIGNED,
                QTableWidgetItem(str(review.unassigned_count)),
            )
            self.table.setItem(
                row_index,
                AI_PEER_REVIEW_COL_FILENAME,
                QTableWidgetItem(Path(review.export_file_path).name or "—"),
            )
        configure_table_columns(self.table, "ai_peer_reviews")
        if rows:
            self.table.selectRow(0)

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

        from moduly.rizeni_rizik.constants_library import CATALOG_AI_PROPOSAL_INCORPORATE_SUCCESS
        from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_incorporate_service import (
            HazardCatalogProposalIncorporateError,
            hazard_catalog_proposal_incorporate_service,
        )
        from moduly.rizeni_rizik.sluzby.hazard_catalog_proposal_support import (
            CATALOG_DUPLICATE_ACTION_CANCEL,
            CATALOG_DUPLICATE_ACTION_EDIT,
            CATALOG_DUPLICATE_ACTION_MERGE,
            CATALOG_DUPLICATE_ACTION_SKIP,
        )
        from moduly.rizeni_rizik.ui.hazard_catalog_ai_proposal_edit_dialog import (
            HazardCatalogAiProposalEditDialog,
        )
        from moduly.rizeni_rizik.ui.hazard_catalog_proposal_duplicate_dialog import (
            HazardCatalogProposalDuplicateDialog,
        )

        export_id_map = hazard_catalog_proposal_incorporate_service.get_export_id_map(review_id)
        resolutions: dict[int, str] = {}
        proposals = hazard_catalog_proposal_incorporate_service.proposal_repository.get_by_ids(
            proposal_ids,
        )

        for proposal in proposals:
            if proposal.status != PROPOSAL_STATUS_PENDING:
                continue
            while True:
                duplicate = hazard_catalog_proposal_incorporate_service.detect_duplicate(
                    template_id=self._source_id,
                    proposal=proposal,
                    export_id_map=export_id_map,
                )
                if duplicate is None:
                    break
                dialog = HazardCatalogProposalDuplicateDialog(
                    self,
                    proposal_name=proposal.name,
                    duplicate=duplicate,
                )
                if not dialog.exec():
                    return
                action = dialog.selected_action
                if action == CATALOG_DUPLICATE_ACTION_CANCEL:
                    return
                if action == CATALOG_DUPLICATE_ACTION_EDIT:
                    edit_dialog = HazardCatalogAiProposalEditDialog(self, proposal=proposal)
                    if not edit_dialog.exec():
                        return
                    proposal = ai_peer_review_service.get_proposal_by_id(proposal.id)
                    if proposal is None:
                        return
                    continue
                resolutions[proposal.id] = action
                break

        try:
            result = hazard_catalog_proposal_incorporate_service.incorporate_proposals(
                template_id=self._source_id,
                review_id=review_id,
                proposal_ids=proposal_ids,
                resolutions=resolutions,
            )
        except HazardCatalogProposalIncorporateError as error:
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, str(error))
            return

        self.refresh()
        if self._on_catalog_incorporated is not None:
            self._on_catalog_incorporated(result.new_revision_number)
        if result.incorporated_count > 0:
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                CATALOG_AI_PROPOSAL_INCORPORATE_SUCCESS.format(
                    count=result.incorporated_count,
                    revision=result.new_revision_number or "—",
                ),
            )
