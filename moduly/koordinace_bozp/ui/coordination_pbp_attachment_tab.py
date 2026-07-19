from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.table_header_settings import configure_and_persist_table_columns
from core.widgets.table_utils import apply_cell_tooltip
from core.widgets.typed_table_sort import (
    create_typed_item,
    enable_typed_sorting,
    sorting_paused,
    typed_date,
    typed_int,
    typed_text,
)
from moduly.koordinace_bozp.constants import (
    COORD_HEADER_PBP,
    MAIN_EMPLOYER_RISK_HANDOVER_ATTACHMENT_TITLE,
    PBP_FRESHNESS_NEEDS_UPDATE,
    TAB_PBP_ATTACHMENT,
)
from moduly.koordinace_bozp.sluzby.bozp_coordination_service import (
    bozp_coordination_service,
)
from moduly.koordinace_bozp.sluzby.coordination_pbp_attachment_service import (
    CoordinationPbpAttachmentError,
    coordination_pbp_attachment_service,
)
from moduly.koordinace_bozp.sluzby.coordination_pbp_freshness import (
    evaluate_pbp_freshness,
    pbp_freshness_color,
)
from moduly.koordinace_bozp.ui.coordination_tab_edit_policy import (
    CoordinationTabEditPolicyMixin,
)


class CoordinationPbpHistoryDialog(QDialog):
    def __init__(self, parent=None, coordination_id: int | None = None):
        super().__init__(parent)
        self.setWindowTitle("Historie přílohy PBP")
        self.resize(720, 360)
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Revize", "Datum", "Uživatel", "Počet pravidel", "Hash"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        enable_typed_sorting(self.table)
        layout.addWidget(self.table)
        close_btn = QPushButton("Zavřít")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        if coordination_id is not None:
            self.load_history(coordination_id)

    def load_history(self, coordination_id: int) -> None:
        revisions = coordination_pbp_attachment_service.list_revisions(coordination_id)
        with sorting_paused(self.table):
            self.table.setRowCount(len(revisions))
            for row, item in enumerate(revisions):
                created = item.created_at
                created_text = created.strftime("%d.%m.%Y %H:%M") if created else ""
                self.table.setItem(
                    row,
                    0,
                    create_typed_item(str(item.revision_number), typed_int(item.revision_number)),
                )
                self.table.setItem(
                    row,
                    1,
                    create_typed_item(created_text, typed_date(created.date() if created else None)),
                )
                user_text = item.created_by or ""
                user_item = create_typed_item(user_text, typed_text(item.created_by))
                apply_cell_tooltip(user_item, user_text)
                self.table.setItem(row, 2, user_item)
                self.table.setItem(
                    row,
                    3,
                    create_typed_item(str(item.rules_count), typed_int(item.rules_count)),
                )
                hash_full = item.content_hash or ""
                hash_item = create_typed_item(hash_full[:12], typed_text(item.content_hash))
                apply_cell_tooltip(hash_item, hash_full)
                self.table.setItem(row, 4, hash_item)
        configure_and_persist_table_columns(
            self.table,
            "coordination_pbp_history",
            COORD_HEADER_PBP,
        )


class CoordinationPbpAttachmentTab(CoordinationTabEditPolicyMixin, QWidget):
    """Záložka automatické přílohy PBP (COORD-007)."""

    def __init__(self, parent=None, coordination_id: int | None = None):
        super().__init__(parent)
        self.coordination_id = coordination_id
        self._content_editable = True
        self._before_mutate = None

        layout = QVBoxLayout(self)
        self.unavailable_label = QLabel(
            "Přílohu PBP lze generovat po uložení koordinace."
        )
        self.unavailable_label.setWordWrap(True)
        layout.addWidget(self.unavailable_label)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        info = QLabel(
            f"Automatická příloha: „{MAIN_EMPLOYER_RISK_HANDOVER_ATTACHMENT_TITLE}“\n"
            "Obsah se sestaví z platných PBP pro aktivní místa výkonu práce."
        )
        info.setWordWrap(True)
        content_layout.addWidget(info)

        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        content_layout.addWidget(self.status_label)

        self.freshness_label = QLabel()
        self.freshness_label.setWordWrap(True)
        content_layout.addWidget(self.freshness_label)

        toolbar = QHBoxLayout()
        self.generate_btn = QPushButton("Generovat")
        self.update_btn = QPushButton("Aktualizovat")
        self.show_btn = QPushButton("Zobrazit")
        self.export_btn = QPushButton("Export ODT")
        self.history_btn = QPushButton("Historie")
        toolbar.addWidget(self.generate_btn)
        toolbar.addWidget(self.update_btn)
        toolbar.addWidget(self.show_btn)
        toolbar.addWidget(self.export_btn)
        toolbar.addWidget(self.history_btn)
        toolbar.addStretch()
        content_layout.addLayout(toolbar)
        content_layout.addStretch()
        layout.addWidget(self.content)

        self._update_btn_default_font = QFont(self.update_btn.font())
        self._update_btn_highlight_font = QFont(self.update_btn.font())
        self._update_btn_highlight_font.setBold(True)

        self.generate_btn.clicked.connect(self.generate_attachment)
        self.update_btn.clicked.connect(self.update_attachment)
        self.show_btn.clicked.connect(self.show_attachment)
        self.export_btn.clicked.connect(self.export_attachment)
        self.history_btn.clicked.connect(self.show_history)

        self.set_coordination_id(coordination_id)

    def set_coordination_id(self, coordination_id: int | None) -> None:
        self.coordination_id = coordination_id
        available = coordination_id is not None
        self.unavailable_label.setVisible(not available)
        self.content.setVisible(available)
        if available:
            self.refresh_status()
        else:
            self.status_label.clear()
            self.freshness_label.clear()
            self._set_update_highlighted(False)

    def refresh_status(self) -> None:
        if self.coordination_id is None:
            return
        current = coordination_pbp_attachment_service.get_current(self.coordination_id)
        if current is None:
            self.status_label.setText("Příloha zatím nebyla vygenerována.")
            self.show_btn.setEnabled(False)
            self.export_btn.setEnabled(False)
        else:
            created = (
                current.created_at.strftime("%d.%m.%Y %H:%M")
                if current.created_at
                else ""
            )
            self.status_label.setText(
                f"Aktuální revize {current.revision_number} "
                f"({current.rules_count} pravidel, {created}, "
                f"hash {current.content_hash[:12]}…)."
            )
            self.show_btn.setEnabled(True)
            self.export_btn.setEnabled(True)

        coordination = bozp_coordination_service.get_by_id(self.coordination_id)
        if coordination is None:
            self.freshness_label.clear()
            self._set_update_highlighted(False)
            self._update_action_buttons()
            return
        freshness = evaluate_pbp_freshness(coordination)
        self.freshness_label.setText(freshness.detail_message)
        self.freshness_label.setToolTip(freshness.tooltip)
        self.freshness_label.setStyleSheet(
            f"color: {pbp_freshness_color(freshness.state)};"
        )
        self._set_update_highlighted(freshness.state == PBP_FRESHNESS_NEEDS_UPDATE)
        self._update_action_buttons()

    def _set_update_highlighted(self, highlighted: bool) -> None:
        if highlighted:
            self.update_btn.setFont(self._update_btn_highlight_font)
            self.update_btn.setStyleSheet(
                "QPushButton { font-weight: bold; "
                "border: 2px solid #ef6c00; padding: 4px 10px; }"
            )
            self.update_btn.setDefault(True)
        else:
            self.update_btn.setFont(self._update_btn_default_font)
            self.update_btn.setStyleSheet("")
            self.update_btn.setDefault(False)

    def generate_attachment(self) -> None:
        self._run_generate(prefer_create_message=True)

    def update_attachment(self) -> None:
        self._run_generate(prefer_create_message=False)

    def _run_generate(self, *, prefer_create_message: bool) -> None:
        if self.coordination_id is None or not self.allow_mutate():
            return
        try:
            result = coordination_pbp_attachment_service.generate_or_update(
                self.coordination_id
            )
        except CoordinationPbpAttachmentError as error:
            QMessageBox.warning(self, TAB_PBP_ATTACHMENT, str(error))
            return
        if result.created:
            QMessageBox.information(self, TAB_PBP_ATTACHMENT, result.message)
        else:
            QMessageBox.information(
                self,
                TAB_PBP_ATTACHMENT,
                result.message
                if not prefer_create_message
                else "Příloha již existuje a obsah se nezměnil.",
            )
        self.refresh_status()

    def show_attachment(self) -> None:
        if self.coordination_id is None:
            return
        current = coordination_pbp_attachment_service.get_current(self.coordination_id)
        if current is None:
            QMessageBox.information(self, TAB_PBP_ATTACHMENT, "Nejdříve vygenerujte přílohu.")
            return
        try:
            coordination_pbp_attachment_service.open_revision(current.id, parent=self)
        except CoordinationPbpAttachmentError as error:
            QMessageBox.warning(self, TAB_PBP_ATTACHMENT, str(error))

    def export_attachment(self) -> None:
        if self.coordination_id is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export ODT",
            f"{MAIN_EMPLOYER_RISK_HANDOVER_ATTACHMENT_TITLE}.odt",
            "ODT (*.odt)",
        )
        if not path:
            return
        try:
            exported = coordination_pbp_attachment_service.export_current_odt(
                self.coordination_id,
                path,
            )
        except CoordinationPbpAttachmentError as error:
            QMessageBox.warning(self, TAB_PBP_ATTACHMENT, str(error))
            return
        QMessageBox.information(
            self,
            TAB_PBP_ATTACHMENT,
            f"Soubor byl uložen:\n{exported}",
        )

    def show_history(self) -> None:
        if self.coordination_id is None:
            return
        dialog = CoordinationPbpHistoryDialog(self, coordination_id=self.coordination_id)
        dialog.exec()

    def _update_action_buttons(self) -> None:
        editable = getattr(self, "_content_editable", True)
        available = self.coordination_id is not None
        self.generate_btn.setEnabled(available and editable)
        self.update_btn.setEnabled(available and editable)
