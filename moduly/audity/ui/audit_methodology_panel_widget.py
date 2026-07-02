"""Pravý panel metodické podpory auditora."""

from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from core.shared.control_result_display import control_result_label
from core.shared.finding_display import finding_status_label
from moduly.audity.constants import (
    CONTROL_POINT_HISTORY_EMPTY,
    CONTROL_POINT_HISTORY_LIMIT,
    CONTROL_POINT_HISTORY_SELECT,
    CONTROL_POINT_SHARED_EXPERIENCES_EMPTY,
    CONTROL_POINT_SHARED_EXPERIENCES_TITLE,
    CONTROL_POINT_HISTORY_WORKPLACE_NO_WORKPLACE,
    CONTROL_POINT_HISTORY_WORKPLACE_TITLE,
    GUIDE_LABEL_NORM_REQUIREMENTS,
    GUIDE_LABEL_OBJECTIVE_EVIDENCE,
    GUIDE_LABEL_OBSERVATIONS_IN_OPERATION,
    GUIDE_LABEL_PROCESS_LINKS,
    GUIDE_LABEL_RECOMMENDED_INTERVIEWS,
    GUIDE_LABEL_TYPICAL_NONCONFORMITIES,
    METHODOLOGY_PANEL_MIN_WIDTH,
    METHODOLOGY_PANEL_TITLE,
    AuditFindingKnowledgeContext,
)
from moduly.audity.sluzby.audit_control_point_history_service import audit_control_point_history_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_service import audit_service

_CRITERION_LIST_BLOCKS: tuple[tuple[str, str], ...] = (
    (GUIDE_LABEL_OBJECTIVE_EVIDENCE, "objektivni_dukazy"),
    (GUIDE_LABEL_RECOMMENDED_INTERVIEWS, "doporucene_rozhovory"),
    (GUIDE_LABEL_OBSERVATIONS_IN_OPERATION, "pozorovani_v_provozu"),
    (GUIDE_LABEL_TYPICAL_NONCONFORMITIES, "typicke_neshody"),
    ("PKZ", "pkz"),
    ("Pozorování", "pozorovani"),
    (GUIDE_LABEL_PROCESS_LINKS, "vazby_procesy"),
    (GUIDE_LABEL_NORM_REQUIREMENTS, "pozadavky_normy"),
)

_PROCESS_LIST_BLOCKS: tuple[tuple[str, str], ...] = (
    (GUIDE_LABEL_PROCESS_LINKS, "vazby_procesy"),
    (GUIDE_LABEL_NORM_REQUIREMENTS, "pozadavky_norem"),
)


class AuditMethodologyPanelWidget(QFrame):
    """Metodická podpora — seznamy z JSON a historie návodných otázek."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ModulePanel")

        self._audit_id: int | None = None
        self._mode = "hint"
        self._section: dict | None = None
        self._process_knowledge: dict | None = None
        self._workplace_history_host: QWidget | None = None
        self._shared_experiences_host: QWidget | None = None
        self._history_area_label = ""
        self._history_section_label = ""

        self._content_host = QWidget()
        self._content_layout = QVBoxLayout(self._content_host)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self._content_host)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(8)

        header = QLabel(METHODOLOGY_PANEL_TITLE)
        header.setObjectName("SectionTitle")
        outer.addWidget(header)
        outer.addWidget(scroll, 1)

        self.setMinimumWidth(METHODOLOGY_PANEL_MIN_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.show_hint()

    def set_audit_id(self, audit_id: int | None) -> None:
        self._audit_id = audit_id

    def show_hint(self, text: str = "Vyberte položku ve stromu vlevo.") -> None:
        self._mode = "hint"
        self._section = None
        self._process_knowledge = None
        self._history_area_label = ""
        self._history_section_label = ""
        self._clear_content()
        self._content_layout.addWidget(self._info_label(text))
        self._content_layout.addStretch()

    def show_process(self, knowledge: dict | None) -> None:
        self._mode = "process"
        self._section = None
        self._process_knowledge = knowledge
        self._history_area_label = ""
        self._history_section_label = ""
        self._rebuild_process()

    def show_criterion(self, section: dict | None, process_knowledge: dict | None = None) -> None:
        self._mode = "criterion"
        self._section = section
        self._process_knowledge = process_knowledge
        self._rebuild_criterion()

    def refresh_history(self, context: AuditFindingKnowledgeContext | None = None) -> None:
        if self._mode != "criterion":
            return
        self._refresh_control_point_history(context)

    def refresh(self) -> None:
        if self._mode == "process":
            self._rebuild_process()
        elif self._mode == "criterion":
            self._rebuild_criterion()

    def _rebuild_process(self) -> None:
        self._clear_content()
        knowledge = self._process_knowledge
        if not knowledge:
            self.show_hint()
            return

        has_content = False
        for title, field in _PROCESS_LIST_BLOCKS:
            block = self._build_list_block(title, knowledge, field)
            if block is not None:
                self._content_layout.addWidget(block)
                has_content = True

        if not has_content:
            self._content_layout.addWidget(
                self._info_label("Pro tento proces zatím není metodická podpora.")
            )
        self._content_layout.addStretch()

    def _rebuild_criterion(self) -> None:
        self._clear_content()
        section = self._section
        if not section:
            self.show_hint()
            return

        has_content = False
        for title, field in _CRITERION_LIST_BLOCKS:
            block = self._build_merged_list_block(title, section, field)
            if block is not None:
                self._content_layout.addWidget(block)
                has_content = True

        self._content_layout.addWidget(self._build_historie_block("Historie"))
        has_content = True

        if not has_content:
            self._content_layout.addWidget(
                self._info_label("Pro tuto oblast zatím není metodická podpora.")
            )
        self._content_layout.addStretch()

    def _build_merged_list_block(self, title: str, section: dict, field: str) -> QWidget | None:
        items = audit_knowledge_service.get_active_items(section.get(field))
        if field == "pozadavky_normy":
            if not items and self._process_knowledge:
                items = audit_knowledge_service.get_active_items(
                    self._process_knowledge.get("pozadavky_norem")
                )
        elif field == "vazby_procesy":
            if not items and self._process_knowledge:
                items = audit_knowledge_service.get_active_items(
                    self._process_knowledge.get("vazby_procesy")
                )

        if not items:
            return None
        return self._build_block(title, self._build_knowledge_items_list(items))

    def _build_list_block(
        self,
        title: str,
        data: dict,
        field: str,
        *,
        items_override: list[dict] | None = None,
    ) -> QWidget | None:
        items = items_override if items_override is not None else audit_knowledge_service.get_active_items(
            data.get(field)
        )
        if not items:
            return None
        return self._build_block(title, self._build_knowledge_items_list(items))

    def _build_historie_block(self, title: str) -> QWidget:
        container = QWidget()
        block_layout = QVBoxLayout(container)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(8)

        header = QLabel(title)
        header.setObjectName("SectionTitle")
        block_layout.addWidget(header)

        block_layout.addWidget(
            self._build_history_section_block(
                CONTROL_POINT_HISTORY_WORKPLACE_TITLE,
                host_attr="_workplace_history_host",
                initial_text=CONTROL_POINT_HISTORY_EMPTY,
            )
        )
        block_layout.addWidget(
            self._build_history_section_block(
                CONTROL_POINT_SHARED_EXPERIENCES_TITLE,
                host_attr="_shared_experiences_host",
                initial_text=CONTROL_POINT_SHARED_EXPERIENCES_EMPTY,
            )
        )
        return container

    def _build_history_section_block(
        self,
        title: str,
        *,
        host_attr: str,
        initial_text: str,
    ) -> QWidget:
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(6)

        header = QLabel(title)
        header.setObjectName("InfoText")
        section_layout.addWidget(header)

        content_host = QWidget()
        content_layout = QVBoxLayout(content_host)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        content_layout.addWidget(self._info_label(initial_text))

        panel = QFrame()
        panel.setObjectName("ModulePanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(6)
        panel_layout.addWidget(content_host)

        section_layout.addWidget(panel)
        setattr(self, host_attr, content_host)
        return section

    def _refresh_control_point_history(self, context: AuditFindingKnowledgeContext | None) -> None:
        if self._workplace_history_host is None or self._shared_experiences_host is None:
            return

        if context is None or not context.control_point_id:
            self._set_panel_content(
                self._workplace_history_host,
                self._info_label(CONTROL_POINT_HISTORY_SELECT),
            )
            self._set_panel_content(
                self._shared_experiences_host,
                self._info_label(CONTROL_POINT_SHARED_EXPERIENCES_EMPTY),
            )
            return

        workplace_id = None
        if self._audit_id is not None:
            audit = audit_service.get_by_id(self._audit_id)
            if audit is not None:
                workplace_id = audit.workplace_id

        if workplace_id is None:
            self._set_panel_content(
                self._workplace_history_host,
                self._info_label(CONTROL_POINT_HISTORY_WORKPLACE_NO_WORKPLACE),
            )
        else:
            workplace_entries = audit_control_point_history_service.get_workplace_history(
                process_label=context.area_label,
                criterion_label=context.section_label,
                question_id=context.control_point_id,
                workplace_id=workplace_id,
                exclude_audit_id=self._audit_id,
                limit=CONTROL_POINT_HISTORY_LIMIT,
            )
            if not workplace_entries:
                self._set_panel_content(
                    self._workplace_history_host,
                    self._info_label(CONTROL_POINT_HISTORY_EMPTY),
                )
            else:
                self._set_panel_content(
                    self._workplace_history_host,
                    self._build_history_entries_list(workplace_entries, include_workplace=False),
                )

        shared_entries = audit_control_point_history_service.get_shared_experiences(
            process_label=context.area_label,
            criterion_label=context.section_label,
            question_id=context.control_point_id,
            exclude_audit_id=self._audit_id,
            limit=CONTROL_POINT_HISTORY_LIMIT,
        )
        if not shared_entries:
            self._set_panel_content(
                self._shared_experiences_host,
                self._info_label(CONTROL_POINT_SHARED_EXPERIENCES_EMPTY),
            )
        else:
            self._set_panel_content(
                self._shared_experiences_host,
                self._build_history_entries_list(shared_entries, include_workplace=True),
            )

    def _set_panel_content(self, host: QWidget | None, widget: QWidget) -> None:
        if host is None:
            return

        layout = host.layout()
        while layout.count():
            item = layout.takeAt(0)
            child = item.widget()
            if child is not None:
                child.deleteLater()
        layout.addWidget(widget)

    def _build_history_entries_list(self, entries, *, include_workplace: bool) -> QWidget:
        list_host = QWidget()
        list_layout = QVBoxLayout(list_host)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(10)
        for entry in entries:
            if include_workplace:
                list_layout.addWidget(self._build_similar_history_entry_row(entry))
            else:
                list_layout.addWidget(self._build_history_entry_row(entry))
        return list_host

    def _build_history_entry_row(self, entry) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        date_text = self._format_history_datetime(entry.recorded_at)
        header = QLabel(f"• {date_text} — {control_result_label(entry.result)}")
        header.setWordWrap(True)
        layout.addWidget(header)

        audit_label = entry.audit_number or str(entry.audit_id)
        layout.addWidget(self._info_label(f"Audit: {audit_label}"))

        if entry.note.strip():
            layout.addWidget(self._info_label(f"Poznámka: {entry.note.strip()}"))

        if entry.finding is not None:
            finding_text = self._text_preview(entry.finding.description, max_len=80)
            layout.addWidget(
                self._info_label(
                    f"Zjištění: {finding_text} ({finding_status_label(entry.finding.status)})"
                )
            )

        return row

    def _build_similar_history_entry_row(self, entry) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        date_text = self._format_history_datetime(entry.recorded_at)
        workplace_label = entry.workplace_name or "—"
        header = QLabel(f"• {date_text} — {workplace_label} — {control_result_label(entry.result)}")
        header.setWordWrap(True)
        layout.addWidget(header)

        if entry.note.strip():
            layout.addWidget(self._info_label(f"Poznámka: {entry.note.strip()}"))

        if entry.finding is not None:
            finding_text = self._text_preview(entry.finding.description, max_len=80)
            layout.addWidget(
                self._info_label(
                    f"Zjištění: {finding_text} ({finding_status_label(entry.finding.status)})"
                )
            )

        return row

    def _build_knowledge_items_list(self, items: list[dict]) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        for item in items:
            layout.addWidget(self._build_knowledge_item_row(item))

        return container

    def _build_knowledge_item_row(self, item: dict) -> QWidget:
        row = QWidget()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(2)

        nazev = str(item.get("nazev") or "—").strip() or "—"
        title_label = QLabel(f"• {nazev}")
        title_label.setWordWrap(True)
        row_layout.addWidget(title_label)

        popis = str(item.get("popis") or "").strip()
        if popis:
            description = QLabel(popis)
            description.setObjectName("InfoText")
            description.setWordWrap(True)
            description.setContentsMargins(16, 0, 0, 0)
            row_layout.addWidget(description)

        return row

    def _build_block(self, title: str, content: QWidget) -> QWidget:
        container = QWidget()
        block_layout = QVBoxLayout(container)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(6)

        header = QLabel(title)
        header.setObjectName("SectionTitle")

        panel = QFrame()
        panel.setObjectName("ModulePanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(6)
        panel_layout.addWidget(content)

        block_layout.addWidget(header)
        block_layout.addWidget(panel)
        return container

    def _clear_content(self) -> None:
        self._workplace_history_host = None
        self._shared_experiences_host = None
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    @staticmethod
    def _format_history_datetime(value) -> str:
        if value is None:
            return "—"
        return value.strftime("%d.%m.%Y %H:%M")

    @staticmethod
    def _text_preview(text: str, max_len: int = 120) -> str:
        value = (text or "").strip()
        if not value:
            return "—"
        if len(value) <= max_len:
            return value
        return value[: max_len - 1].rstrip() + "…"

    @staticmethod
    def _info_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        return label
