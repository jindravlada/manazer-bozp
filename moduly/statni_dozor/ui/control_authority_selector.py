"""Editovatelné výběry kontrolního orgánu a příslušného pracoviště."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCompleter

from core.widgets.search_combo_box import SearchComboBox
from moduly.statni_dozor.modely.control_authority import ControlAuthority
from moduly.statni_dozor.modely.control_authority_office import ControlAuthorityOffice
from moduly.statni_dozor.sluzby.control_authority_catalog_service import (
    control_authority_catalog_service,
)

logger = logging.getLogger(__name__)


def authority_display_label(authority: ControlAuthority) -> str:
    name = str(authority.name or "").strip()
    abbreviation = str(authority.abbreviation or "").strip()
    if abbreviation:
        return f"{name} ({abbreviation})"
    return name


def office_item_tooltip(office: ControlAuthorityOffice) -> str:
    parts = [
        part
        for part in (
            str(office.address or "").strip(),
            str(office.territorial_scope or "").strip(),
        )
        if part
    ]
    return "\n".join(parts)


class ControlAuthoritySelector(SearchComboBox):
    """Aktivní kontrolní orgány z katalogu, s možností ručního textu."""

    def __init__(self, parent=None):
        super().__init__(values=[], parent=parent, allow_custom_value=True)
        self._records: dict[int, ControlAuthority] = {}
        self.addItem("", None)

    def reload(self) -> bool:
        current = self.currentText()
        blocked = self.signalsBlocked()
        self.blockSignals(True)
        self.clear()
        self._records = {}
        self.addItem("", None)
        try:
            records = control_authority_catalog_service.list_authorities(
                include_inactive=False
            )
        except Exception:
            logger.exception("Načtení katalogu kontrolních orgánů v editoru selhalo.")
            self._set_completer([])
            self.setCurrentText(current)
            self.blockSignals(blocked)
            return False
        names: list[str] = []
        for authority in records:
            label = authority_display_label(authority)
            self.addItem(label, int(authority.id))
            self._records[int(authority.id)] = authority
            names.append(label)
        self._set_completer(names)
        self.setCurrentText(current)
        self.blockSignals(blocked)
        return True

    def _set_completer(self, names: list[str]) -> None:
        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(completer)

    def catalog_id_for_current_text(self) -> int | None:
        text = self.currentText().strip()
        if not text:
            return None
        for index in range(self.count()):
            if self.itemText(index).strip() != text:
                continue
            data = self.itemData(index)
            if isinstance(data, int):
                return int(data)
        return None

    def record_by_id(self, authority_id: int | None) -> ControlAuthority | None:
        if authority_id is None:
            return None
        return self._records.get(int(authority_id))

    def display_text(self) -> str:
        return self.currentText().strip()


class ControlAuthorityOfficeSelector(SearchComboBox):
    """Aktivní příslušná pracoviště vybraného orgánu, s možností ručního textu."""

    def __init__(self, parent=None):
        super().__init__(values=[], parent=parent, allow_custom_value=True)
        self._records: dict[int, ControlAuthorityOffice] = {}
        self._authority_id: int | None = None
        self.reload(None)

    def reload(self, authority_id: int | None) -> bool:
        blocked = self.signalsBlocked()
        self.blockSignals(True)
        self.clear()
        self._records = {}
        self._authority_id = int(authority_id) if authority_id else None
        self.addItem("", None)
        names: list[str] = []
        ok = True
        if self._authority_id is not None:
            try:
                offices = control_authority_catalog_service.list_offices(
                    authority_id=self._authority_id,
                    include_inactive=False,
                )
            except Exception:
                logger.exception(
                    "Načtení pracovišť kontrolního orgánu v editoru selhalo."
                )
                ok = False
                offices = []
            for office in offices:
                self.addItem(office.name, int(office.id))
                index = self.count() - 1
                tooltip = office_item_tooltip(office)
                if tooltip:
                    self.setItemData(index, tooltip, Qt.ItemDataRole.ToolTipRole)
                self._records[int(office.id)] = office
                names.append(office.name)
        completer = QCompleter(names, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        self.setCompleter(completer)
        self.setCurrentIndex(0)
        self.blockSignals(blocked)
        return ok

    def catalog_id_for_current_text(self) -> int | None:
        text = self.currentText().strip()
        if not text:
            return None
        for index in range(self.count()):
            if self.itemText(index).strip() != text:
                continue
            data = self.itemData(index)
            if isinstance(data, int):
                return int(data)
        return None

    def record_by_id(self, office_id: int | None) -> ControlAuthorityOffice | None:
        if office_id is None:
            return None
        return self._records.get(int(office_id))

    def display_text(self) -> str:
        return self.currentText().strip()
