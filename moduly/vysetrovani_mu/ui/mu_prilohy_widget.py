"""Centrální přehled příloh vyšetřování. Soubory jen zobrazuje a otevírá."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.export.open_export import open_local_file
from core.services.attachment_service import attachment_service
from core.shared.constants import ENTITY_MU_INVESTIGATION
from moduly.vysetrovani_mu.sluzby.mu_prilohy_prehled import (
    classify_mu_attachment,
    linked_attachment_names,
)


class MuPrilohyWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._investigation_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.empty_label = QLabel("Přílohy se zobrazí po uložení vyšetřování.")
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Název souboru", "Zařazení", "Otevřít"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.doubleClicked.connect(self._open_current_row)
        layout.addWidget(self.table, 1)

    def refresh(
        self,
        investigation_id: int | None,
        *,
        zajisteni_dukazu_json: str = "",
        casova_osa_json: str = "",
        ohledani_mista_json: str = "",
    ) -> None:
        self._investigation_id = investigation_id if isinstance(investigation_id, int) and investigation_id > 0 else None
        self.table.setRowCount(0)
        if self._investigation_id is None:
            self.empty_label.setText("Přílohy se zobrazí po uložení vyšetřování.")
            self.empty_label.setVisible(True)
            return

        zajisteni_names, casova_names, ohledani_names = linked_attachment_names(
            zajisteni_dukazu_json=zajisteni_dukazu_json,
            casova_osa_json=casova_osa_json,
            ohledani_mista_json=ohledani_mista_json,
        )
        attachments = attachment_service.get_for_entity(
            ENTITY_MU_INVESTIGATION,
            self._investigation_id,
        )
        seen: set[int] = set()
        for attachment in attachments:
            if attachment.id in seen:
                continue
            seen.add(attachment.id)
            section = classify_mu_attachment(
                attachment.filename or "",
                zajisteni_names=zajisteni_names,
                casova_osa_names=casova_names,
                ohledani_names=ohledani_names,
            )
            self._add_row(attachment.id, attachment.filename or "", section)

        self.empty_label.setText("Toto vyšetřování nemá žádné přílohy.")
        self.empty_label.setVisible(self.table.rowCount() == 0)

    def _add_row(self, attachment_id: int, filename: str, section: str) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        name_item = QTableWidgetItem(filename)
        name_item.setData(Qt.ItemDataRole.UserRole, attachment_id)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        section_item = QTableWidgetItem(section)
        section_item.setFlags(section_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, 0, name_item)
        self.table.setItem(row, 1, section_item)

        button = QPushButton("Otevřít")
        button.setAutoDefault(False)
        button.setDefault(False)
        button.clicked.connect(lambda _checked=False, ident=attachment_id: self._open_attachment(ident))
        self.table.setCellWidget(row, 2, button)

    def _open_current_row(self) -> None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        if item is None:
            return
        attachment_id = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(attachment_id, int):
            self._open_attachment(attachment_id)

    def _open_attachment(self, attachment_id: int) -> None:
        if self._investigation_id is None:
            return
        attachment = next(
            (
                item
                for item in attachment_service.get_for_entity(
                    ENTITY_MU_INVESTIGATION,
                    self._investigation_id,
                )
                if item.id == attachment_id
            ),
            None,
        )
        if attachment is None:
            self._warn_missing()
            return
        try:
            path = attachment_service.resolve_path(attachment)
        except ValueError:
            self._warn_missing()
            return
        if not path.exists():
            self._warn_missing()
            return
        open_local_file(path, parent=self, title="Přílohy")

    def _warn_missing(self) -> None:
        QMessageBox.warning(self, "Přílohy", "Soubor nebyl nalezen.")
