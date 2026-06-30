"""Pracovní karta znalostního uzlu sekce prověrky."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from core.shared.constants import ENTITY_PROVERKY
from core.shared.sluzby.finding_service import finding_service
from core.widgets.dialog_utils import wrap_in_scroll_area
from core.widgets.finding_dialog import FindingDialog
from moduly.proverky.constants import (
    FINDING_CREATE_FROM_CONTROL_POINT_LABEL,
    FINDING_DIALOG_TITLE,
    FINDING_SOURCE_LABEL,
    INSPECTION_MUST_BE_SAVED_MESSAGE,
    KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT,
    ProverkyFindingKnowledgeContext,
)
from moduly.proverky.sluzby.proverky_knowledge_service import (
    SECTION_LIST_BLOCKS,
    proverky_knowledge_service,
)


class BozpKnowledgeSectionWidget(QWidget):
    """Vykreslí znalostní uzel sekce — popis a tematické bloky z JSON."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._area_id = ""
        self._area_label = ""
        self._section_id = ""
        self._section_label = ""
        self._inspection_id: int | None = None
        self._on_finding_saved = None

        self._content_host = QWidget()
        self._content_layout = QVBoxLayout(self._content_host)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(wrap_in_scroll_area(self._content_host))

    def set_section(
        self,
        section: dict | None,
        *,
        area_id: str = "",
        area_label: str = "",
        section_label: str = "",
    ) -> None:
        self._area_id = area_id.strip()
        self._area_label = area_label.strip()
        self._section_label = section_label.strip()
        self._section_id = str(section.get("id") or "").strip() if section else ""
        self._clear_content()

        if not section:
            self._content_layout.addWidget(self._build_info_label("Vyberte sekci v seznamu vlevo."))
            self._content_layout.addStretch()
            return

        if not self._section_label:
            self._section_label = str(section.get("nazev") or "").strip()

        self._content_layout.addWidget(self._build_popis_block(section))

        for title, field in SECTION_LIST_BLOCKS:
            self._content_layout.addWidget(self._build_list_block(title, section, field))

        self._content_layout.addStretch()

    def set_inspection_id(self, inspection_id: int | None) -> None:
        self._inspection_id = inspection_id

    def set_on_finding_saved(self, callback) -> None:
        self._on_finding_saved = callback

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _build_popis_block(self, section: dict) -> QWidget:
        popis = str(section.get("popis") or "").strip()
        if popis:
            return self._build_block("Popis", self._build_info_label(popis))
        return self._build_block("Popis", self._build_info_label(KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT))

    def _build_list_block(self, title: str, section: dict, field: str) -> QWidget:
        if field == "historie":
            return self._build_historie_block(title, section)

        items = proverky_knowledge_service.get_active_items(section.get(field))
        if not items:
            return self._build_block(title, self._build_info_label(KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT))

        if field == "kontrolni_body":
            content = self._build_control_points_list(items)
        elif field == "legislativa":
            content = self._build_reference_list(items)
        else:
            content = self._build_knowledge_items_list(items)

        return self._build_block(title, content)

    def _build_historie_block(self, title: str, section: dict) -> QWidget:
        items = proverky_knowledge_service.get_active_items(section.get("historie"))
        if not items:
            return self._build_block(title, self._build_info_label(KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT))
        return self._build_block(title, self._build_knowledge_items_list(items))

    def _build_control_points_list(self, items: list[dict]) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        for item in items:
            layout.addWidget(self._build_control_point_row(item))

        return container

    def _build_control_point_row(self, item: dict) -> QWidget:
        row = QWidget()
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)

        nazev = str(item.get("nazev") or "—").strip() or "—"
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        title_label = QLabel(f"• {nazev}")
        title_label.setWordWrap(True)
        header_row.addWidget(title_label, 1)

        create_btn = QPushButton(FINDING_CREATE_FROM_CONTROL_POINT_LABEL)
        create_btn.clicked.connect(
            lambda _checked=False, item=item: self._open_finding_dialog(item)
        )
        header_row.addWidget(create_btn, 0)
        row_layout.addLayout(header_row)

        popis = str(item.get("popis") or "").strip()
        if popis:
            description = QLabel(popis)
            description.setObjectName("InfoText")
            description.setWordWrap(True)
            description.setContentsMargins(16, 0, 0, 0)
            row_layout.addWidget(description)

        return row

    def _open_finding_dialog(self, control_point: dict) -> None:
        if self._inspection_id is None:
            QMessageBox.information(self, "Zjištění", INSPECTION_MUST_BE_SAVED_MESSAGE)
            return

        control_point_label = str(control_point.get("nazev") or "—").strip() or "—"
        context = ProverkyFindingKnowledgeContext(
            area_id=self._area_id,
            area_label=self._area_label,
            section_id=self._section_id,
            section_label=self._section_label,
            control_point_id=str(control_point.get("id") or "").strip(),
            control_point_label=control_point_label,
        )
        dialog = FindingDialog(
            self,
            title=FINDING_DIALOG_TITLE,
            knowledge_source={
                "source_label": FINDING_SOURCE_LABEL,
                "area_label": context.area_label,
                "section_label": context.section_label,
                "control_point_label": context.control_point_label,
            },
        )
        if not dialog.exec():
            return

        data = dialog.get_data()
        finding_service.create(
            ENTITY_PROVERKY,
            self._inspection_id,
            finding_type=data["finding_type"],
            reference_label=data["reference_label"] or context.control_point_label,
            description=data["description"],
            recommended_action=data["recommended_action"],
            responsible_person_id=data["responsible_person_id"],
            responsible_person_name=data["responsible_person_name"],
            due_date=data["due_date"],
            status=data["status"],
            resolution_note=data["resolution_note"],
            source_area_label=context.area_label,
            source_section_label=context.section_label,
            source_control_point_id=context.control_point_id,
            source_control_point_label=context.control_point_label,
        )
        if self._on_finding_saved is not None:
            self._on_finding_saved()

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

    def _build_reference_list(self, items: list[dict]) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for item in items:
            nazev = str(item.get("nazev") or "—").strip() or "—"
            label = QLabel(f"• {nazev}")
            label.setWordWrap(True)
            layout.addWidget(label)

            popis = str(item.get("popis") or "").strip()
            if popis:
                description = QLabel(popis)
                description.setObjectName("InfoText")
                description.setWordWrap(True)
                description.setContentsMargins(16, 0, 0, 0)
                layout.addWidget(description)

        return container

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

    @staticmethod
    def _build_info_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        return label
