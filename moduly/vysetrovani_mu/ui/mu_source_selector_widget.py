from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QLineEdit,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.widgets.search_combo_box import SearchComboBox
from moduly.vysetrovani_mu.constants import (
    SOURCE_TYPE_ACCIDENT,
    SOURCE_TYPE_AUDIT,
    SOURCE_TYPE_CONTROL,
    SOURCE_TYPE_MANUAL,
    SOURCE_TYPE_OTHER,
)


class MuSourceSelectorWidget(QWidget):
    _PAGE_ACCIDENT = 0
    _PAGE_AUDIT = 1
    _PAGE_CONTROL = 2
    _PAGE_OTHER = 3
    _PAGE_MANUAL = 4

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.accident_combo = self._make_record_combo()
        self.audit_combo = self._make_record_combo()
        self.control_combo = self._make_record_combo()
        self.text_edit = QLineEdit()
        self.text_edit.setPlaceholderText("Popište zdroj podnětu")
        self.manual_page = QWidget()
        manual_layout = QVBoxLayout(self.manual_page)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(0)
        self.manual_info = QLabel("Zdrojový záznam není navázán")
        self.manual_info.setObjectName("InfoText")
        self.manual_info.setWordWrap(True)
        manual_layout.addWidget(self.manual_info, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.stack.addWidget(self.accident_combo)
        self.stack.addWidget(self.audit_combo)
        self.stack.addWidget(self.control_combo)
        self.stack.addWidget(self.text_edit)
        self.stack.addWidget(self.manual_page)

        layout.addWidget(self.stack)

        row_height = self.accident_combo.sizeHint().height()
        self.stack.setFixedHeight(row_height)
        self.setFixedHeight(row_height)

        self._current_source_type = SOURCE_TYPE_ACCIDENT
        self._populate_accidents()
        self._populate_audits()
        self._populate_controls()
        self.set_source_type(SOURCE_TYPE_ACCIDENT)

    def set_source_type(self, source_type: str) -> None:
        self._current_source_type = source_type
        if source_type == SOURCE_TYPE_ACCIDENT:
            self.stack.setCurrentIndex(self._PAGE_ACCIDENT)
        elif source_type == SOURCE_TYPE_AUDIT:
            self.stack.setCurrentIndex(self._PAGE_AUDIT)
        elif source_type == SOURCE_TYPE_CONTROL:
            self.stack.setCurrentIndex(self._PAGE_CONTROL)
        elif source_type == SOURCE_TYPE_OTHER:
            self.stack.setCurrentIndex(self._PAGE_OTHER)
        else:
            self.stack.setCurrentIndex(self._PAGE_MANUAL)

    def set_source(self, source_type: str, source_id: int | None, source_label: str) -> None:
        self.set_source_type(source_type)

        if source_type == SOURCE_TYPE_ACCIDENT:
            self._populate_accidents()
            self._set_combo_value(self.accident_combo, source_id)
        elif source_type == SOURCE_TYPE_AUDIT:
            self._populate_audits()
            self._set_combo_value(self.audit_combo, source_id)
        elif source_type == SOURCE_TYPE_CONTROL:
            self._populate_controls()
            self._set_combo_value(self.control_combo, source_id)
        elif source_type == SOURCE_TYPE_OTHER:
            self.text_edit.setText(source_label or "")

    def current_source_id(self) -> int | None:
        current = self.stack.currentWidget()
        if current is self.accident_combo:
            return self._current_combo_id(self.accident_combo)
        if current is self.audit_combo:
            return self._current_combo_id(self.audit_combo)
        if current is self.control_combo:
            return self._current_combo_id(self.control_combo)
        return None

    def current_source_label(self) -> str:
        current = self.stack.currentWidget()
        if current is self.text_edit:
            return self.text_edit.text().strip()
        if current is self.manual_page:
            return ""

        source_id = self.current_source_id()
        if source_id is None:
            return ""

        if current is self.accident_combo:
            return self._accident_label(source_id)
        if current is self.audit_combo:
            return self._audit_label(source_id)
        if current is self.control_combo:
            return self._control_label(source_id)
        return ""

    def has_binding(self) -> bool:
        current = self.stack.currentWidget()
        if current is self.manual_page:
            return False
        if current is self.text_edit:
            return bool(self.text_edit.text().strip())
        return self.current_source_id() is not None

    def _make_record_combo(self) -> SearchComboBox:
        combo = SearchComboBox(allow_custom_value=False)
        combo.addItem("— vyberte záznam —", None)
        return combo

    def _set_combo_value(self, combo: QComboBox, value: int | None) -> None:
        combo.blockSignals(True)
        index = combo.findData(value, role=Qt.ItemDataRole.UserRole)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _current_combo_id(self, combo: QComboBox) -> int | None:
        value = combo.currentData(Qt.ItemDataRole.UserRole)
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _populate_accidents(self) -> None:
        from moduly.kniha_urazu.sluzby.accident_service import accident_service

        self.accident_combo.blockSignals(True)
        self.accident_combo.clear()
        self.accident_combo.addItem("— vyberte záznam —", None)
        for accident in accident_service.get_all():
            label = accident.number or f"ID {accident.id}"
            name = (accident.employee_name or accident.jmeno_prijmeni or "").strip()
            if name:
                label = f"{label} — {name}"
            self.accident_combo.addItem(label, accident.id)
        self.accident_combo.blockSignals(False)

    def _populate_audits(self) -> None:
        from moduly.audity.sluzby.internal_audit_service import internal_audit_service

        self.audit_combo.blockSignals(True)
        self.audit_combo.clear()
        self.audit_combo.addItem("— vyberte záznam —", None)
        for audit in internal_audit_service.get_all():
            number = audit.number or f"ID {audit.id}"
            title = (audit.title or "").strip()
            label = f"Audit IMS {number}"
            if title:
                label = f"{label} — {title}"
            self.audit_combo.addItem(label, audit.id)
        self.audit_combo.blockSignals(False)

    def _populate_controls(self) -> None:
        from moduly.kontroly.sluzby.control_service import control_service

        self.control_combo.blockSignals(True)
        self.control_combo.clear()
        self.control_combo.addItem("— vyberte záznam —", None)
        for control in control_service.get_all():
            date_label = control.inspection_date.strftime("%d.%m.%Y") if control.inspection_date else "—"
            title = (control.title or "").strip() or f"Kontrola {control.id}"
            workplace = (control.workplace_name or "").strip()
            label = f"{date_label} — {title}"
            if workplace:
                label = f"{label} ({workplace})"
            self.control_combo.addItem(label, control.id)
        self.control_combo.blockSignals(False)

    def _accident_label(self, accident_id: int) -> str:
        from moduly.kniha_urazu.sluzby.accident_service import accident_service

        accident = accident_service.get_by_id(accident_id)
        if accident is None or not accident.number:
            return ""
        return f"Událost č. {accident.number}"

    def _audit_label(self, audit_id: int) -> str:
        from moduly.audity.sluzby.internal_audit_service import internal_audit_service

        audit = internal_audit_service.get_by_id(audit_id)
        if audit is None or not audit.number:
            return ""
        return f"Audit IMS {audit.number}"

    def _control_label(self, control_id: int) -> str:
        from moduly.kontroly.sluzby.control_service import control_service

        control = control_service.get_by_id(control_id)
        if control is None:
            return ""
        title = (control.title or "").strip()
        if control.inspection_date is not None:
            return f"Kontrola {control.inspection_date.strftime('%d.%m.%Y')} — {title or control.id}"
        return title or f"Kontrola {control.id}"
