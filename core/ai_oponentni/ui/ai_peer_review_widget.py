from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.ai_oponentni.constants import (
    AI_PEER_REVIEW_COL_ACCEPTED,
    AI_PEER_REVIEW_COL_DATE,
    AI_PEER_REVIEW_COL_FILENAME,
    AI_PEER_REVIEW_COL_ID,
    AI_PEER_REVIEW_COL_MODEL,
    AI_PEER_REVIEW_COL_REJECTED,
    AI_PEER_REVIEW_COLUMN_COUNT,
    AI_PEER_REVIEW_DIALOG_TITLE,
    AI_PEER_REVIEW_EXPORT_BUTTON,
    AI_PEER_REVIEW_IMPORT_BUTTON,
    AI_PEER_REVIEW_INCLUDE_RESPONSIBLE_PERSON,
    AI_PEER_REVIEW_INTRO_TEXT,
    AI_PEER_REVIEW_TABLE_HEADERS,
)
from core.ai_oponentni.sluzby.ai_peer_review_service import (
    AiPeerReviewError,
    ai_peer_review_service,
)
from core.ai_oponentni.types import AiPeerReviewExportOptions, AiPeerReviewProvider
from core.ai_oponentni.ui.import_proposals_dialog import AiPeerReviewImportDialog
from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.table_utils import configure_table_columns


class AiPeerReviewExportOptionsDialog(QDialog):
    def __init__(self, parent=None, *, show_responsible_person: bool = False):
        super().__init__(parent)
        self.setWindowTitle(AI_PEER_REVIEW_DIALOG_TITLE)
        self.resize(440, 140)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.include_responsible_person = QCheckBox(AI_PEER_REVIEW_INCLUDE_RESPONSIBLE_PERSON)
        self.include_responsible_person.setChecked(False)
        if show_responsible_person:
            form.addRow("", self.include_responsible_person)
        else:
            self.include_responsible_person.hide()
        layout.addLayout(form)

        buttons = create_save_cancel_box(self)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setText("Pokračovat")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_options(self) -> AiPeerReviewExportOptions:
        return AiPeerReviewExportOptions(
            include_responsible_person=self.include_responsible_person.isChecked(),
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
            "Vložte text odpovědi AI ve formátu Oblast / Návrh / Zdůvodnění."
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
            "Textové soubory (*.txt *.md);;Všechny soubory (*)",
        )
        if not path:
            return
        try:
            self.response.setPlainText(Path(path).read_text(encoding="utf-8"))
        except OSError as error:
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, str(error))

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
        show_responsible_person_option: bool = False,
        on_proposals_applied=None,
    ):
        super().__init__(parent)
        self._provider = provider
        self._source_id: int | None = None
        self._show_responsible_person_option = show_responsible_person_option
        self._on_proposals_applied = on_proposals_applied

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
        layout.addWidget(self.table)

        self.export_btn.clicked.connect(self.export_package)
        self.import_btn.clicked.connect(self.import_response)
        self.set_source(None)

    def set_source(self, source_id: int | None) -> None:
        self._source_id = source_id
        enabled = self._provider.can_export(source_id)
        self.export_btn.setEnabled(enabled)
        self.import_btn.setEnabled(enabled)
        self.refresh()

    def refresh(self) -> None:
        self._load_table()

    def export_package(self) -> bool:
        if self._source_id is None or not self._provider.can_export(self._source_id):
            QMessageBox.information(
                self,
                AI_PEER_REVIEW_DIALOG_TITLE,
                "Export je možné provést až po uložení zdrojového záznamu.",
            )
            return False

        options_dialog = AiPeerReviewExportOptionsDialog(
            self,
            show_responsible_person=self._show_responsible_person_option,
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
            proposals = ai_peer_review_service.parse_response(response_text)
        except AiPeerReviewError as error:
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, str(error))
            return False

        import_dialog = AiPeerReviewImportDialog(
            self,
            proposals=proposals,
            ai_model=ai_model,
        )
        if not import_dialog.exec():
            return False

        accepted, rejected = import_dialog.get_accepted_and_rejected()
        try:
            ai_peer_review_service.finalize_import(
                provider=self._provider,
                source_id=self._source_id,
                review_id=review.id,
                response_text=response_text,
                ai_model=ai_model,
                accepted=accepted,
                rejected=rejected,
            )
        except AiPeerReviewError as error:
            QMessageBox.warning(self, AI_PEER_REVIEW_DIALOG_TITLE, str(error))
            return False

        self.refresh()
        if self._on_proposals_applied is not None:
            self._on_proposals_applied()

        QMessageBox.information(
            self,
            AI_PEER_REVIEW_DIALOG_TITLE,
            (
                f"Převzato: {len(accepted)}\n"
                f"Zamítnuto: {len(rejected)}"
            ),
        )
        return True

    def _load_table(self) -> None:
        self.table.setRowCount(0)
        if self._source_id is None:
            return

        rows = ai_peer_review_service.get_for_source(
            self._provider.source_type,
            self._source_id,
        )
        self.table.setRowCount(len(rows))
        for row_index, review in enumerate(rows):
            self.table.setItem(row_index, AI_PEER_REVIEW_COL_ID, QTableWidgetItem(str(review.id)))
            self.table.setItem(
                row_index,
                AI_PEER_REVIEW_COL_DATE,
                QTableWidgetItem(review.exported_at.strftime("%d.%m.%Y %H:%M")),
            )
            self.table.setItem(
                row_index,
                AI_PEER_REVIEW_COL_MODEL,
                QTableWidgetItem(review.ai_model or "—"),
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
                AI_PEER_REVIEW_COL_FILENAME,
                QTableWidgetItem(Path(review.export_file_path).name or "—"),
            )
        configure_table_columns(self.table, "ai_peer_reviews")
