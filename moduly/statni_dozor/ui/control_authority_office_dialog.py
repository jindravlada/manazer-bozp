"""Editor příslušného pracoviště kontrolního orgánu."""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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
    AUTHORITY_ORIGIN_LABELS,
    CATALOG_MANUAL_EDIT_HINT,
    CATALOG_REFRESH_AFTER_SAVE_MESSAGE,
    CATALOG_ROW_KIND_AUTHORITY,
    CATALOG_ROW_KIND_OFFICE,
    EMPTY_VALUE,
    OFFICE_AUTHORITY_REQUIRED_MESSAGE,
    OFFICE_KIND_USER_LABELS,
    OFFICE_NAME_REQUIRED_MESSAGE,
)
from moduly.statni_dozor.modely.control_authority_office import ControlAuthorityOffice
from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
    ControlAuthorityCatalogError,
    control_authority_catalog_service,
)

logger = logging.getLogger(__name__)


def _format_checked_at(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%d. %m. %Y %H:%M")


class ControlAuthorityOfficeDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        office: ControlAuthorityOffice | None = None,
        preselected_authority_id: int | None = None,
        on_catalog_changed=None,
    ):
        super().__init__(parent)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setWindowTitle(CATALOG_ROW_KIND_OFFICE)
        configure_resizable_form_dialog(self, width=620, height=560, min_width=480, min_height=400)

        self._office = office
        self._on_catalog_changed = on_catalog_changed
        self._catalog = control_authority_catalog_service

        layout = QVBoxLayout(self)
        form_host = QWidget()
        form = QFormLayout(form_host)

        self.authority_combo = QComboBox()
        self.name_edit = QLineEdit()
        self.abbreviation_edit = QLineEdit()
        self.address_edit = QLineEdit()
        self.scope_edit = QLineEdit()
        self.phone_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.website_edit = QLineEdit()
        self.source_url_edit = QLineEdit()
        self.kind_combo = QComboBox()
        self.display_order_spin = QSpinBox()
        self.display_order_spin.setMinimum(0)
        self.display_order_spin.setMaximum(999999)
        self.origin_label = QLabel(EMPTY_VALUE)
        self.last_checked_label = QLabel("")
        self.last_checked_label.setVisible(False)

        self._fill_authority_combo(
            current_id=(
                int(office.authority_id)
                if office is not None
                else preselected_authority_id
            ),
            allow_inactive_id=(
                int(office.authority_id) if office is not None else None
            ),
        )
        self.kind_combo.addItem("", "")
        for code, label in OFFICE_KIND_USER_LABELS.items():
            self.kind_combo.addItem(label, code)

        form.addRow(f"{CATALOG_ROW_KIND_AUTHORITY}:", self.authority_combo)
        form.addRow("Název příslušného pracoviště:", self.name_edit)
        form.addRow("Zkratka:", self.abbreviation_edit)
        form.addRow("Adresa:", self.address_edit)
        form.addRow("Územní působnost:", self.scope_edit)
        form.addRow("Telefon:", self.phone_edit)
        form.addRow("E-mail:", self.email_edit)
        form.addRow("Web:", self._url_row(self.website_edit))
        form.addRow("Oficiální zdroj:", self._url_row(self.source_url_edit))
        form.addRow("Typ pracoviště:", self.kind_combo)
        form.addRow("Pořadí:", self.display_order_spin)
        form.addRow("Původ:", self.origin_label)
        form.addRow("Poslední webová kontrola:", self.last_checked_label)

        hint = QLabel(CATALOG_MANUAL_EDIT_HINT)
        hint.setWordWrap(True)
        form.addRow(hint)

        layout.addWidget(wrap_in_scroll_area(form_host), 1)
        configure_form_tab_navigation(form_host)

        buttons = create_save_cancel_box(self, is_new=office is None)
        layout.addWidget(buttons)
        self._editor = EditorDialogController(
            self,
            buttons,
            is_new=office is None,
            title=self.windowTitle(),
            on_save=self._persist,
        )
        self._editor.set_snapshot_provider(self.get_data)
        self._editor.install_auto_dirty_tracking()

        if office is not None:
            self.name_edit.setText(office.name or "")
            self.abbreviation_edit.setText(office.abbreviation or "")
            self.address_edit.setText(office.address or "")
            self.scope_edit.setText(office.territorial_scope or "")
            self.phone_edit.setText(office.phone or "")
            self.email_edit.setText(office.email or "")
            self.website_edit.setText(office.website or "")
            self.source_url_edit.setText(office.source_url or "")
            self.display_order_spin.setValue(int(office.display_order or 0))
            kind_index = self.kind_combo.findData(office.office_kind or "")
            if kind_index < 0:
                kind_index = 0
            self.kind_combo.setCurrentIndex(kind_index)
            self.origin_label.setText(
                AUTHORITY_ORIGIN_LABELS.get(office.origin or "", EMPTY_VALUE)
            )
            checked = _format_checked_at(office.last_checked_at)
            self.last_checked_label.setText(checked)
            self.last_checked_label.setVisible(bool(checked))
        else:
            self.origin_label.setText(AUTHORITY_ORIGIN_LABELS.get("manual", "Ručně"))
            if preselected_authority_id is not None:
                index = self.authority_combo.findData(int(preselected_authority_id))
                if index >= 0:
                    self.authority_combo.setCurrentIndex(index)

        self._editor.capture_baseline()

    def _fill_authority_combo(
        self,
        *,
        current_id: int | None,
        allow_inactive_id: int | None,
    ) -> None:
        self.authority_combo.addItem(EMPTY_VALUE, None)
        authorities = self._catalog.list_authorities(include_inactive=True)
        for authority in authorities:
            if not authority.active and authority.id != allow_inactive_id:
                continue
            self.authority_combo.addItem(authority.name, int(authority.id))
        if current_id is not None:
            index = self.authority_combo.findData(int(current_id))
            if index >= 0:
                self.authority_combo.setCurrentIndex(index)

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
        authority_id = self.authority_combo.currentData()
        kind = self.kind_combo.currentData()
        return {
            "authority_id": int(authority_id) if authority_id else None,
            "name": self.name_edit.text().strip(),
            "abbreviation": self.abbreviation_edit.text().strip(),
            "address": self.address_edit.text().strip(),
            "territorial_scope": self.scope_edit.text().strip(),
            "phone": self.phone_edit.text().strip(),
            "email": self.email_edit.text().strip(),
            "website": self.website_edit.text().strip(),
            "source_url": self.source_url_edit.text().strip(),
            "office_kind": str(kind or ""),
            "display_order": int(self.display_order_spin.value()),
        }

    def _persist(self) -> bool:
        data = self.get_data()
        if data["authority_id"] is None:
            QMessageBox.warning(
                self, self.windowTitle(), OFFICE_AUTHORITY_REQUIRED_MESSAGE
            )
            return False
        if not data["name"]:
            QMessageBox.warning(self, self.windowTitle(), OFFICE_NAME_REQUIRED_MESSAGE)
            return False
        try:
            if self._office is None:
                saved = self._catalog.create_office(
                    authority_id=data["authority_id"],
                    name=data["name"],
                    abbreviation=data["abbreviation"],
                    address=data["address"],
                    phone=data["phone"],
                    email=data["email"],
                    website=data["website"],
                    territorial_scope=data["territorial_scope"],
                    office_kind=data["office_kind"] or None,
                    display_order=data["display_order"],
                    source_url=data["source_url"],
                )
            else:
                saved = self._catalog.update_office(
                    int(self._office.id),
                    authority_id=data["authority_id"],
                    name=data["name"],
                    abbreviation=data["abbreviation"],
                    address=data["address"],
                    phone=data["phone"],
                    email=data["email"],
                    website=data["website"],
                    territorial_scope=data["territorial_scope"],
                    office_kind=data["office_kind"],
                    display_order=data["display_order"],
                    source_url=data["source_url"],
                )
            self._office = saved
            self.origin_label.setText(
                AUTHORITY_ORIGIN_LABELS.get(saved.origin, EMPTY_VALUE)
            )
        except ControlAuthorityCatalogError as exc:
            QMessageBox.warning(self, self.windowTitle(), str(exc))
            return False
        except Exception:
            logger.exception("Uložení příslušného pracoviště selhalo.")
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "Příslušné pracoviště se nepodařilo uložit.",
            )
            return False
        try:
            if self._on_catalog_changed is not None:
                self._on_catalog_changed(
                    kind="office", record_id=int(self._office.id)
                )
        except Exception:
            logger.exception("Obnovení přehledu katalogu po uložení pracoviště selhalo.")
            QMessageBox.warning(
                self, self.windowTitle(), CATALOG_REFRESH_AFTER_SAVE_MESSAGE
            )
        return True
