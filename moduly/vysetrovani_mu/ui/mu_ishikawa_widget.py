import json
import uuid

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.shared.constants import (
    ENTITY_MU_INVESTIGATION,
    FINDING_TYPE_BEZPROSTREDNI_PRICINA,
    FINDING_TYPE_SYSTEMOVA_PRICINA,
    FINDING_TYPE_ZAKLADNI_PRICINA,
)
from core.shared.sluzby.finding_service import finding_service
from moduly.vysetrovani_mu.constants import (
    ISHIKAWA_CATEGORIES,
    ISHIKAWA_LEVEL_BEZPROSTREDNI,
    ISHIKAWA_LEVEL_LABELS,
    ISHIKAWA_LEVEL_SYSTEMOVA,
    ISHIKAWA_LEVEL_ZAKLADNI,
    ISHIKAWA_LEVELS,
    ISHIKAWA_STATUS_HYPOTEZA,
    ISHIKAWA_STATUS_LABELS,
    ISHIKAWA_STATUSES,
)
from moduly.vysetrovani_mu.ui.mu_ishikawa_cause_dialog import MuIshikawaCauseDialog

_LEVEL_TO_FINDING_TYPE = {
    ISHIKAWA_LEVEL_BEZPROSTREDNI: FINDING_TYPE_BEZPROSTREDNI_PRICINA,
    ISHIKAWA_LEVEL_ZAKLADNI: FINDING_TYPE_ZAKLADNI_PRICINA,
    ISHIKAWA_LEVEL_SYSTEMOVA: FINDING_TYPE_SYSTEMOVA_PRICINA,
}


class MuIshikawaWidget(QWidget):
    def __init__(self, parent=None, *, on_findings_changed=None):
        super().__init__(parent)

        self._investigation_id: int | None = None
        self._causes: list[dict] = []
        self._on_findings_changed = on_findings_changed

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Ishikawa+")
        group_layout = QVBoxLayout(group)

        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("Přidat příčinu")
        self.edit_btn = QPushButton("Upravit")
        self.delete_btn = QPushButton("Odebrat")
        self.create_finding_btn = QPushButton("Vytvořit zjištění")
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.delete_btn)
        toolbar.addWidget(self.create_finding_btn)
        toolbar.addStretch()
        group_layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Kategorie",
            "Popis",
            "Faktory",
            "Stav",
            "Úroveň",
            "Důkazy",
        ])
        self.table.setColumnHidden(0, True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self.edit_cause)
        group_layout.addWidget(self.table)

        layout.addWidget(group)

        self.add_btn.clicked.connect(self.add_cause)
        self.edit_btn.clicked.connect(self.edit_cause)
        self.delete_btn.clicked.connect(self.delete_cause)
        self.create_finding_btn.clicked.connect(self.create_finding)
        self.table.itemSelectionChanged.connect(self._update_toolbar_state)

        self._update_toolbar_state()

    def set_investigation_id(self, investigation_id: int | None) -> None:
        self._investigation_id = investigation_id
        self._update_toolbar_state()

    def load_json(self, raw_json: str) -> None:
        try:
            data = json.loads(raw_json or "{}")
        except Exception:
            data = {}
        self._causes = self._normalize_causes(data.get("causes", []) or [])
        self._refresh_table()

    def get_json(self) -> str:
        return json.dumps({"causes": self._causes}, ensure_ascii=False)

    def add_cause(self) -> None:
        if not self._ensure_investigation():
            return

        dialog = MuIshikawaCauseDialog(self, title="Přidat příčinu")
        if not dialog.exec():
            return

        data = dialog.get_data()
        if not data["description"]:
            QMessageBox.information(self, "Ishikawa+", "Vyplňte popis možné příčiny.")
            return

        self._causes.append(self._new_cause(data))
        self._refresh_table()

    def edit_cause(self) -> None:
        cause = self._selected_cause()
        if cause is None:
            QMessageBox.information(self, "Ishikawa+", "Vyberte příčinu.")
            return

        dialog = MuIshikawaCauseDialog(self, cause=cause, title="Upravit příčinu")
        if not dialog.exec():
            return

        data = dialog.get_data()
        if not data["description"]:
            QMessageBox.information(self, "Ishikawa+", "Vyplňte popis možné příčiny.")
            return

        cause.update(data)
        self._refresh_table()

    def delete_cause(self) -> None:
        cause = self._selected_cause()
        if cause is None:
            QMessageBox.information(self, "Ishikawa+", "Vyberte příčinu.")
            return

        answer = QMessageBox.question(
            self,
            "Ishikawa+",
            "Odebrat vybranou příčinu?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        self._causes = [item for item in self._causes if item.get("id") != cause.get("id")]
        self._refresh_table()

    def create_finding(self) -> None:
        if not self._ensure_investigation():
            return

        cause = self._selected_cause()
        if cause is None:
            QMessageBox.information(self, "Ishikawa+", "Vyberte příčinu.")
            return

        description = self._finding_description(cause)
        if not description:
            QMessageBox.information(self, "Ishikawa+", "Vybraná příčina nemá popis.")
            return

        cause_level = cause.get("cause_level") or ISHIKAWA_LEVEL_BEZPROSTREDNI
        finding_type = _LEVEL_TO_FINDING_TYPE.get(cause_level, FINDING_TYPE_BEZPROSTREDNI_PRICINA)

        finding_service.create(
            ENTITY_MU_INVESTIGATION,
            self._investigation_id,
            finding_type=finding_type,
            description=description,
            reference_label="Ishikawa+",
            recommended_action="",
        )

        if self._on_findings_changed is not None:
            self._on_findings_changed()

    def _ensure_investigation(self) -> bool:
        if self._investigation_id is not None:
            return True
        QMessageBox.information(
            self,
            "Ishikawa+",
            "Příčiny lze upravovat až po uložení vyšetřování.",
        )
        return False

    def _new_cause(self, data: dict) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "category": data["category"],
            "factors": list(data.get("factors") or []),
            "custom_factor": data.get("custom_factor") or "",
            "description": data["description"],
            "evidence": data["evidence"],
            "status": data["status"],
            "cause_level": data["cause_level"],
            "note": data["note"],
        }

    def _normalize_causes(self, causes: list) -> list[dict]:
        normalized = []
        for raw in causes:
            if not isinstance(raw, dict):
                continue
            category = raw.get("category") or ISHIKAWA_CATEGORIES[0]
            if category not in ISHIKAWA_CATEGORIES:
                category = ISHIKAWA_CATEGORIES[-1]
            status = raw.get("status") or ISHIKAWA_STATUS_HYPOTEZA
            if status not in ISHIKAWA_STATUSES:
                status = ISHIKAWA_STATUS_HYPOTEZA
            cause_level = raw.get("cause_level") or ISHIKAWA_LEVEL_BEZPROSTREDNI
            if cause_level not in ISHIKAWA_LEVELS:
                cause_level = ISHIKAWA_LEVEL_BEZPROSTREDNI
            normalized.append(
                {
                    "id": str(raw.get("id") or uuid.uuid4()),
                    "category": category,
                    "factors": [
                        str(factor).strip()
                        for factor in (raw.get("factors") or [])
                        if str(factor).strip()
                    ],
                    "custom_factor": str(raw.get("custom_factor") or "").strip(),
                    "description": str(raw.get("description") or "").strip(),
                    "evidence": str(raw.get("evidence") or "").strip(),
                    "status": status,
                    "cause_level": cause_level,
                    "note": str(raw.get("note") or "").strip(),
                }
            )
        return normalized

    def _sorted_causes(self) -> list[dict]:
        category_index = {category: index for index, category in enumerate(ISHIKAWA_CATEGORIES)}

        def sort_key(item: tuple[int, dict]) -> tuple[int, int]:
            index, cause = item
            return (category_index.get(cause.get("category"), len(ISHIKAWA_CATEGORIES)), index)

        indexed = list(enumerate(self._causes))
        indexed.sort(key=sort_key)
        return [cause for _, cause in indexed]

    def _refresh_table(self) -> None:
        causes = self._sorted_causes()
        self.table.setRowCount(len(causes))
        for row, cause in enumerate(causes):
            values = [
                cause.get("id", ""),
                cause.get("category") or "—",
                self._text_preview(cause.get("description")),
                self._factors_summary(cause),
                ISHIKAWA_STATUS_LABELS.get(cause.get("status"), "—"),
                ISHIKAWA_LEVEL_LABELS.get(cause.get("cause_level"), "—"),
                self._text_preview(cause.get("evidence")),
            ]
            tooltip = self._cause_tooltip(cause)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(tooltip)
                self.table.setItem(row, column, item)

        self._update_toolbar_state()

    def _selected_cause(self) -> dict | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None

        item = self.table.item(selected[0].row(), 0)
        if item is None:
            return None

        cause_id = item.text()
        for cause in self._causes:
            if cause.get("id") == cause_id:
                return cause
        return None

    def _update_toolbar_state(self) -> None:
        enabled = self._investigation_id is not None
        has_selection = self._selected_cause() is not None
        self.add_btn.setEnabled(enabled)
        self.edit_btn.setEnabled(enabled and has_selection)
        self.delete_btn.setEnabled(enabled and has_selection)
        self.create_finding_btn.setEnabled(enabled and has_selection)

    def _text_preview(self, text: str | None, max_len: int = 80) -> str:
        value = (text or "").strip()
        if not value:
            return "—"
        if len(value) <= max_len:
            return value
        return value[: max_len - 1].rstrip() + "…"

    def _factors_summary(self, cause: dict, max_len: int = 80) -> str:
        items = list(cause.get("factors") or [])
        custom = (cause.get("custom_factor") or "").strip()
        if custom:
            items.append(custom)
        if not items:
            return "—"
        return self._text_preview(", ".join(items), max_len=max_len)

    def _finding_description(self, cause: dict) -> str:
        parts = []
        description = (cause.get("description") or "").strip()
        if description:
            parts.append(description)

        factors = [factor for factor in (cause.get("factors") or []) if factor]
        if factors:
            parts.append("Faktory: " + ", ".join(factors))

        custom_factor = (cause.get("custom_factor") or "").strip()
        if custom_factor:
            parts.append(f"Vlastní faktor: {custom_factor}")

        return "\n\n".join(parts)

    def _cause_tooltip(self, cause: dict) -> str:
        lines = [
            f"Kategorie: {cause.get('category') or '—'}",
            f"Popis: {cause.get('description') or '—'}",
        ]
        factors = cause.get("factors") or []
        if factors:
            lines.append("Faktory: " + ", ".join(factors))
        if cause.get("custom_factor"):
            lines.append(f"Vlastní faktor: {cause.get('custom_factor')}")
        lines.extend([
            f"Důkazy: {cause.get('evidence') or '—'}",
            f"Stav: {ISHIKAWA_STATUS_LABELS.get(cause.get('status'), '—')}",
            f"Úroveň: {ISHIKAWA_LEVEL_LABELS.get(cause.get('cause_level'), '—')}",
        ])
        if cause.get("note"):
            lines.append(f"Poznámka: {cause.get('note')}")
        return "\n".join(lines)
