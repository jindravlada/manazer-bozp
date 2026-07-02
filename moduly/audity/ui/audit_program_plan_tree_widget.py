"""Strom plánu návštěv programu auditů."""

from __future__ import annotations

from collections import defaultdict

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from moduly.audity.constants import (
    AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED,
    AUDIT_PROGRAM_VISIT_STATUS_COMPLETED,
    AUDIT_PROGRAM_VISIT_STATUS_SKIPPED,
)
from moduly.audity.sluzby.audit_program_service import AuditProgramOverview
from moduly.audity.sluzby.audit_program_visit_formatting import (
    visit_sort_key,
    visit_tree_label,
)


NODE_WORKPLACE = "workplace"
NODE_VISIT = "visit"
NODE_PROCESS = "process"


class AuditProgramPlanTreeWidget(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setAlternatingRowColors(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

    def populate(self, overview: AuditProgramOverview) -> None:
        self.clear()

        visits_by_workplace: dict[int | None, list] = defaultdict(list)
        for visit in overview.visits:
            visits_by_workplace[visit.workplace_id].append(visit)

        processes_by_visit: dict[int, list] = defaultdict(list)
        for visit_process in overview.visit_processes:
            processes_by_visit[visit_process.visit_id].append(visit_process)

        for workplace in overview.workplaces:
            if not workplace.active:
                continue

            workplace_item = QTreeWidgetItem([workplace.workplace_name or "—"])
            self._set_node_data(
                workplace_item,
                node_type=NODE_WORKPLACE,
                entity_id=workplace.id,
                workplace_id=workplace.workplace_id,
            )
            self.addTopLevelItem(workplace_item)

            workplace_visits = visits_by_workplace.get(workplace.workplace_id, [])
            workplace_visits.sort(key=visit_sort_key)

            for visit in workplace_visits:
                visit_label = visit_tree_label(visit)
                visit_item = QTreeWidgetItem([visit_label])
                self._set_node_data(
                    visit_item,
                    node_type=NODE_VISIT,
                    entity_id=visit.id,
                    workplace_id=workplace.workplace_id,
                )
                if visit.status == AUDIT_PROGRAM_VISIT_STATUS_SKIPPED:
                    self._style_skipped_item(visit_item)
                elif visit.status == AUDIT_PROGRAM_VISIT_STATUS_COMPLETED:
                    self._style_completed_item(visit_item)
                workplace_item.addChild(visit_item)

                visit_processes = processes_by_visit.get(visit.id, [])
                visit_processes.sort(key=lambda item: (item.process_name, item.id))
                for visit_process in visit_processes:
                    prefix = (
                        "✓ "
                        if visit_process.status == AUDIT_PROGRAM_VISIT_PROCESS_STATUS_COMPLETED
                        else "• "
                    )
                    process_label = f"{prefix}{visit_process.process_name or visit_process.process_id}"
                    process_item = QTreeWidgetItem([process_label])
                    self._set_node_data(
                        process_item,
                        node_type=NODE_PROCESS,
                        entity_id=visit_process.id,
                        workplace_id=workplace.workplace_id,
                        visit_id=visit.id,
                    )
                    if visit.status == AUDIT_PROGRAM_VISIT_STATUS_SKIPPED:
                        self._style_skipped_item(process_item)
                    visit_item.addChild(process_item)

            workplace_item.setExpanded(True)

        self.expandAll()

    @staticmethod
    def node_type(item: QTreeWidgetItem | None) -> str | None:
        if item is None:
            return None
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            return None
        return payload.get("type")

    @staticmethod
    def node_id(item: QTreeWidgetItem | None) -> int | None:
        if item is None:
            return None
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            return None
        value = payload.get("id")
        return int(value) if value is not None else None

    @staticmethod
    def workplace_id(item: QTreeWidgetItem | None) -> int | None:
        if item is None:
            return None
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            return None
        return payload.get("workplace_id")

    @staticmethod
    def visit_id(item: QTreeWidgetItem | None) -> int | None:
        if item is None:
            return None
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(payload, dict):
            return None
        return payload.get("visit_id")

    @staticmethod
    def _set_node_data(
        item: QTreeWidgetItem,
        *,
        node_type: str,
        entity_id: int,
        workplace_id: int | None,
        visit_id: int | None = None,
    ) -> None:
        item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            {
                "type": node_type,
                "id": entity_id,
                "workplace_id": workplace_id,
                "visit_id": visit_id,
            },
        )

    @staticmethod
    def _style_skipped_item(item: QTreeWidgetItem) -> None:
        font = item.font(0)
        font.setStrikeOut(True)
        item.setFont(0, font)
        item.setForeground(0, QBrush(QColor("#777777")))

    @staticmethod
    def _style_completed_item(item: QTreeWidgetItem) -> None:
        item.setForeground(0, QBrush(QColor("#2e7d32")))
