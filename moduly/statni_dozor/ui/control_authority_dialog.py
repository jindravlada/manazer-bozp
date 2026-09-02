"""Editor kontrolního orgánu — ruční vytvoření a úprava."""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.utils.https_url import open_https_url
from core.widgets.dialog_utils import (
    configure_form_tab_navigation,
    configure_resizable_form_dialog,
    create_save_cancel_box,
    wrap_in_scroll_area,
)
from core.widgets.editor_dialog_controller import EditorDialogController
from moduly.statni_dozor.constants import (
    AUTHORITY_NAME_REQUIRED_MESSAGE,
    AUTHORITY_ORIGIN_LABELS,
    CATALOG_CODE_PLACEHOLDER,
    CATALOG_MANUAL_EDIT_HINT,
    CATALOG_REFRESH_AFTER_SAVE_MESSAGE,
    CATALOG_ROW_KIND_AUTHORITY,
    EMPTY_VALUE,
)
from moduly.statni_dozor.modely.control_authority import ControlAuthority
from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
    ControlAuthorityCatalogError,
    control_authority_catalog_service,
)

logger = logging.getLogger(__name__)


def _format_checked_at(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%d. %m. %Y %H:%M")


class ControlAuthorityDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        authority: ControlAuthority | None = None,
        on_catalog_changed=None,
    ):
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setWindowTitle(CATALOG_ROW_KIND_AUTHORITY)
        configure_resizable_form_dialog(self, width=560, height=480, min_width=460, min_height=360)

        self._authority = authority
        self._on_catalog_changed = on_catalog_changed
        self._catalog = control_authority_catalog_service

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.name_edit = QLineEdit()
        self.abbreviation_edit = QLineEdit()
        self.website_edit = QLineEdit()
        self.source_url_edit = QLineEdit()
        self.display_order_spin = QSpinBox()
        self.display_order_spin.setMinimum(0)
        self.display_order_spin.setMaximum(999999)
        self.code_edit = QLineEdit()
        self.code_edit.setReadOnly(True)
        self.origin_label = QLabel(EMPTY_VALUE)
        self.last_checked_label = QLabel("")
        self.last_checked_label.setVisible(False)

        form.addRow("Název:", self.name_edit)
        form.addRow("Zkratka:", self.abbreviation_edit)
        form.addRow("Web:", self._url_row(self.website_edit))
        form.addRow("Oficiální zdroj:", self._url_row(self.source_url_edit))
        form.addRow("Pořadí:", self.display_order_spin)
        form.addRow("Technický kód:", self.code_edit)
        form.addRow("Původ:", self.origin_label)
        form.addRow("Poslední webová kontrola:", self.last_checked_label)

        hint = QLabel(CATALOG_MANUAL_EDIT_HINT)
        hint.setWordWrap(True)
        form.addRow(hint)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)
        configure_form_tab_navigation(form_host)

        buttons = create_save_cancel_box(self, is_new=authority is None)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=authority is None,
            title=self.windowTitle(),
            on_save=self._persist,
        )
        self._editor.set_snapshot_provider(self.get_data)
        self._editor.install_auto_dirty_tracking()

        if authority is not None:
            self.name_edit.setText(authority.name or "")
            self.abbreviation_edit.setText(authority.abbreviation or "")
            self.website_edit.setText(authority.website or "")
            self.source_url_edit.setText(authority.source_url or "")
            self.display_order_spin.setValue(int(authority.display_order or 0))
            self.code_edit.setText(authority.code or "")
            self.origin_label.setText(
                AUTHORITY_ORIGIN_LABELS.get(authority.origin or "", EMPTY_VALUE)
            )
            checked = _format_checked_at(authority.last_checked_at)
            self.last_checked_label.setText(checked)
            self.last_checked_label.setVisible(bool(checked))
        else:
            self.code_edit.setPlaceholderText(CATALOG_CODE_PLACEHOLDER)
            self.origin_label.setText(AUTHORITY_ORIGIN_LABELS.get("manual", "Ručně"))

        self._editor.capture_baseline()

    def _url_row(self, edit: QLineEdit) -> QWidget:
        row = QWidget(self)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(edit, 1)
        button = QPushButton("Otevřít")
        button.clicked.connect(lambda: open_https_url(edit.text(), parent=self))
        layout.addWidget(button)
        return row

    def get_data(self) -> dict:
        return {
            "name": self.name_edit.text().strip(),
            "abbreviation": self.abbreviation_edit.text().strip(),
            "website": self.website_edit.text().strip(),
            "source_url": self.source_url_edit.text().strip(),
            "display_order": int(self.display_order_spin.value()),
        }

    def _persist(self) -> bool:
        data = self.get_data()
        if not data["name"]:
            QMessageBox.warning(self, self.windowTitle(), AUTHORITY_NAME_REQUIRED_MESSAGE)
            return False
        try:
            if self._authority is None:
                code = self._catalog.allocate_unique_authority_code(data["name"])
                saved = self._catalog.create_authority(
                    code=code,
                    name=data["name"],
                    abbreviation=data["abbreviation"],
                    website=data["website"],
                    display_order=data["display_order"],
                    source_url=data["source_url"],
                )
                self._authority = saved
                self.code_edit.setText(saved.code)
                self.origin_label.setText(
                    AUTHORITY_ORIGIN_LABELS.get(saved.origin, EMPTY_VALUE)
                )
            else:
                saved = self._catalog.update_authority(
                    int(self._authority.id),
                    name=data["name"],
                    abbreviation=data["abbreviation"],
                    website=data["website"],
                    display_order=data["display_order"],
                    source_url=data["source_url"],
                )
                self._authority = saved
                self.origin_label.setText(
                    AUTHORITY_ORIGIN_LABELS.get(saved.origin, EMPTY_VALUE)
                )
        except ControlAuthorityCatalogError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return False
        except Exception:
            logger.exception("Uložení kontrolního orgánu selhalo.")
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "Kontrolní orgán se nepodařilo uložit.",
            )
            return False
        try:
            if self._on_catalog_changed is not None:
                self._on_catalog_changed(
                    kind="authority", record_id=int(self._authority.id)
                )
        except Exception:
            logger.exception("Obnovení přehledu katalogu po uložení orgánu selhalo.")
            QMessageBox.warning(
                self, self.windowTitle(), CATALOG_REFRESH_AFTER_SAVE_MESSAGE
            )
        return True
