"""Pracovní karta znalostního uzlu sekce prověrky."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.shared.constants import ENTITY_PROVERKY
from core.shared.control_result_display import allows_finding, control_result_label
from core.shared.finding_display import finding_status_label
from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
from core.shared.sluzby.finding_service import finding_service
from core.widgets.control_result_selector import ControlResultSelectorWidget
from core.widgets.control_result_photo_widget import ControlResultPhotoWidget
from core.widgets.dialog_utils import wrap_in_scroll_area
from core.widgets.finding_dialog import FindingDialog
from core.widgets.image_viewer_dialog import ImageViewerDialog
from moduly.proverky.constants import (
    CONTROL_POINT_HISTORY_EMPTY,
    CONTROL_POINT_HISTORY_LIMIT,
    CONTROL_POINT_HISTORY_SELECT,
    CONTROL_POINT_SEVERITY_OPTIONS,
    CONTROL_POINT_SHARED_EXPERIENCES_EMPTY,
    CONTROL_POINT_SHARED_EXPERIENCES_TITLE,
    CONTROL_POINT_HISTORY_WORKPLACE_NO_WORKPLACE,
    CONTROL_POINT_HISTORY_WORKPLACE_TITLE,
    FINDING_CREATE_FROM_CONTROL_POINT_LABEL,
    FINDING_CREATED_LABEL,
    FINDING_DIALOG_TITLE,
    FINDING_DUPLICATE_MESSAGE,
    FINDING_OPEN_EXISTING_LABEL,
    FINDING_REQUIRES_NONCOMPLIANCE_MESSAGE,
    FINDING_SOURCE_LABEL,
    INSPECTION_MUST_BE_SAVED_MESSAGE,
    KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT,
    KNOWLEDGE_REFERENCE_PHOTOS_TITLE,
    REFERENCE_PHOTO_PLACEHOLDER_ICON_SIZE_PX,
    REFERENCE_PHOTO_PLACEHOLDER_WIDTH,
    REFERENCE_PHOTO_THUMBNAIL_SIZE,
    ProverkyFindingKnowledgeContext,
)
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
from moduly.proverky.sluzby.control_point_history_service import control_point_history_service
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service
from moduly.proverky.sluzby.proverky_reference_photo_service import proverky_reference_photo_service


class _ControlPointFrame(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class _ReferencePhotoThumbnail(QLabel):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ControlResultPhotoThumbnail")
        self.setFixedSize(REFERENCE_PHOTO_THUMBNAIL_SIZE, REFERENCE_PHOTO_THUMBNAIL_SIZE)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setScaledContents(False)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)



_RIGHT_COLUMN_BLOCKS: tuple[tuple[str, str], ...] = (
    ("Typické závady", "typicke_zavady"),
    ("Historie", "historie"),
    ("Doporučené postupy", "doporucene_postupy"),
    ("Legislativa", "legislativa"),
)

_COLUMN_SPLIT_LEFT_STRETCH = 65
_COLUMN_SPLIT_RIGHT_STRETCH = 35

_SEVERITY_LABELS = dict(CONTROL_POINT_SEVERITY_OPTIONS)


class _ControlPointSeverityBadge(QLabel):
    def __init__(self, severity: str, parent=None):
        super().__init__(_SEVERITY_LABELS.get(severity, "Střední"), parent)
        self.setObjectName("ControlPointSeverityBadge")
        self.setProperty("severity", severity)
        self.style().unpolish(self)
        self.style().polish(self)


class BozpKnowledgeSectionWidget(QWidget):
    """Vykreslí znalostní uzel sekce — popis a tematické bloky z JSON."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self._area_id = ""
        self._area_label = ""
        self._section_id = ""
        self._section_label = ""
        self._current_section: dict | None = None
        self._inspection_id: int | None = None
        self._on_finding_saved = None
        self._selected_control_point_id = ""
        self._control_point_frames: dict[str, _ControlPointFrame] = {}
        self._history_point_label: QLabel | None = None
        self._workplace_history_host: QWidget | None = None
        self._shared_experiences_host: QWidget | None = None

        self._content_host = QWidget()
        self._content_layout = QVBoxLayout(self._content_host)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._content_host, 1)

    def set_section(
        self,
        section: dict | None,
        *,
        area_id: str = "",
        area_label: str = "",
        section_label: str = "",
    ) -> None:
        self._current_section = section
        self._area_id = area_id.strip()
        self._area_label = area_label.strip()
        self._section_label = section_label.strip()
        self._section_id = str(section.get("id") or "").strip() if section else ""
        self._rebuild_content()

    def set_inspection_id(self, inspection_id: int | None) -> None:
        self._inspection_id = inspection_id
        self.refresh()

    def set_on_finding_saved(self, callback) -> None:
        self._on_finding_saved = callback

    def refresh(self) -> None:
        self._rebuild_content()

    def _rebuild_content(self) -> None:
        section = self._current_section
        self._clear_content()

        if not section:
            self._content_layout.addWidget(self._build_info_label("Vyberte sekci v seznamu vlevo."))
            self._content_layout.addStretch()
            return

        if not self._section_label:
            self._section_label = str(section.get("nazev") or "").strip()

        self._content_layout.addWidget(self._build_popis_block(section))
        self._content_layout.addWidget(self._build_referencni_fotografie_block(section))
        self._content_layout.addWidget(self._build_columns(section), 1)

    def _build_columns(self, section: dict) -> QWidget:
        right_host = self._build_right_column(section)
        left_scroll = self._build_control_points_scroll_area(section)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("KnowledgeSectionSplitter")
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(left_scroll)
        splitter.addWidget(wrap_in_scroll_area(right_host))
        splitter.setStretchFactor(0, _COLUMN_SPLIT_LEFT_STRETCH)
        splitter.setStretchFactor(1, _COLUMN_SPLIT_RIGHT_STRETCH)
        return splitter

    def _build_right_column(self, section: dict) -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        for title, field in _RIGHT_COLUMN_BLOCKS:
            if field == "historie":
                layout.addWidget(self._build_historie_block(title))
            else:
                layout.addWidget(self._build_list_block(title, section, field))

        layout.addStretch()
        return host

    def _clear_content(self) -> None:
        self._selected_control_point_id = ""
        self._control_point_frames.clear()
        self._history_point_label = None
        self._workplace_history_host = None
        self._shared_experiences_host = None
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

    def _build_referencni_fotografie_block(self, section: dict) -> QWidget:
        photos = proverky_knowledge_service.get_general_reference_photos(section)
        if photos:
            content = self._build_reference_photo_gallery(photos)
        else:
            content = self._build_reference_photo_placeholder()
        return self._build_block(KNOWLEDGE_REFERENCE_PHOTOS_TITLE, content)

    def _build_reference_photo_placeholder(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ReferencePhotoPlaceholder")
        panel.setFixedSize(REFERENCE_PHOTO_PLACEHOLDER_WIDTH, REFERENCE_PHOTO_THUMBNAIL_SIZE)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        icon = QLabel("📷")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"font-size: {REFERENCE_PHOTO_PLACEHOLDER_ICON_SIZE_PX}px;"
            " border: none; background: transparent; padding: 0;"
        )

        text = QLabel("Referenční fotografie<br>budou doplněny.")
        text.setObjectName("InfoText")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setWordWrap(False)

        layout.addStretch(1)
        layout.addWidget(icon)
        layout.addWidget(text)
        layout.addStretch(1)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(panel)
        row.addStretch()

        host = QWidget()
        host.setLayout(row)
        return host

    def _build_reference_photo_gallery(self, photos: list[dict]) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        for photo in photos:
            relative_path = str(photo.get("soubor") or "")
            absolute_path = proverky_reference_photo_service.absolute_photo_path(relative_path)
            thumbnail = _ReferencePhotoThumbnail()
            thumbnail.setCursor(Qt.CursorShape.PointingHandCursor)

            if absolute_path.is_file():
                pixmap = QPixmap(str(absolute_path))
                if not pixmap.isNull():
                    thumbnail.setPixmap(
                        pixmap.scaled(
                            thumbnail.size(),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
                else:
                    thumbnail.setText("Náhled\nnedostupný")
            else:
                thumbnail.setText("Soubor\nchybí")

            thumbnail.clicked.connect(
                lambda checked=False, path=absolute_path: self._view_reference_photo(path)
            )
            row.addWidget(thumbnail)

        row.addStretch()
        scroll.setWidget(host)
        scroll.setFixedHeight(REFERENCE_PHOTO_THUMBNAIL_SIZE + 12)
        return scroll

    def _view_reference_photo(self, image_path) -> None:
        if not image_path.is_file():
            QMessageBox.information(
                self,
                KNOWLEDGE_REFERENCE_PHOTOS_TITLE,
                "Fotografii se nepodařilo načíst.",
            )
            return

        dialog = ImageViewerDialog(image_path, title=KNOWLEDGE_REFERENCE_PHOTOS_TITLE, parent=self)
        dialog.exec()

    def _build_list_block(self, title: str, section: dict, field: str) -> QWidget:
        items = proverky_knowledge_service.get_active_items(section.get(field))
        if not items:
            return self._build_block(title, self._build_info_label(KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT))

        if field == "legislativa":
            content = self._build_reference_list(items)
        else:
            content = self._build_knowledge_items_list(items)

        return self._build_block(title, content)

    def _build_historie_block(self, title: str) -> QWidget:
        container = QWidget()
        block_layout = QVBoxLayout(container)
        block_layout.setContentsMargins(0, 0, 0, 0)
        block_layout.setSpacing(8)

        header = QLabel(title)
        header.setObjectName("SectionTitle")
        block_layout.addWidget(header)

        self._history_point_label = QLabel(CONTROL_POINT_HISTORY_SELECT)
        self._history_point_label.setObjectName("InfoText")
        self._history_point_label.setWordWrap(True)
        block_layout.addWidget(self._history_point_label)

        block_layout.addWidget(self._build_history_section_block(
            CONTROL_POINT_HISTORY_WORKPLACE_TITLE,
            host_attr="_workplace_history_host",
            initial_text=CONTROL_POINT_HISTORY_SELECT,
        ))
        block_layout.addWidget(self._build_history_section_block(
            CONTROL_POINT_SHARED_EXPERIENCES_TITLE,
            host_attr="_shared_experiences_host",
            initial_text=CONTROL_POINT_SHARED_EXPERIENCES_EMPTY,
        ))
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
        content_layout.addWidget(self._build_info_label(initial_text))

        panel = QFrame()
        panel.setObjectName("ModulePanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 12, 12, 12)
        panel_layout.setSpacing(6)
        panel_layout.addWidget(content_host)

        section_layout.addWidget(panel)
        setattr(self, host_attr, content_host)
        return section

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

    def _refresh_control_point_history(self, context: ProverkyFindingKnowledgeContext | None = None) -> None:
        if self._workplace_history_host is None or self._shared_experiences_host is None:
            return

        if context is None and self._selected_control_point_id:
            context = ProverkyFindingKnowledgeContext(
                area_id=self._area_id,
                area_label=self._area_label,
                section_id=self._section_id,
                section_label=self._section_label,
                control_point_id=self._selected_control_point_id,
                control_point_label="",
            )

        if context is None or not context.control_point_id:
            if self._history_point_label is not None:
                self._history_point_label.setText(CONTROL_POINT_HISTORY_SELECT)
            self._set_panel_content(
                self._workplace_history_host,
                self._build_info_label(CONTROL_POINT_HISTORY_SELECT),
            )
            self._set_panel_content(
                self._shared_experiences_host,
                self._build_info_label(CONTROL_POINT_SHARED_EXPERIENCES_EMPTY),
            )
            return

        if self._history_point_label is not None:
            label = context.control_point_label.strip() or context.control_point_id
            self._history_point_label.setText(label)

        workplace_id = None
        if self._inspection_id is not None:
            inspection = bozp_inspection_service.get_by_id(self._inspection_id)
            if inspection is not None:
                workplace_id = inspection.workplace_id

        if workplace_id is None:
            self._set_panel_content(
                self._workplace_history_host,
                self._build_info_label(CONTROL_POINT_HISTORY_WORKPLACE_NO_WORKPLACE),
            )
        else:
            workplace_entries = control_point_history_service.get_workplace_history(
                area_label=context.area_label,
                section_label=context.section_label,
                control_point_id=context.control_point_id,
                workplace_id=workplace_id,
                exclude_inspection_id=self._inspection_id,
                limit=CONTROL_POINT_HISTORY_LIMIT,
            )
            if not workplace_entries:
                self._set_panel_content(
                    self._workplace_history_host,
                    self._build_info_label(CONTROL_POINT_HISTORY_EMPTY),
                )
            else:
                self._set_panel_content(
                    self._workplace_history_host,
                    self._build_history_entries_list(
                        workplace_entries,
                        include_workplace=False,
                    ),
                )

        shared_entries = control_point_history_service.get_shared_experiences(
            area_label=context.area_label,
            section_label=context.section_label,
            control_point_id=context.control_point_id,
            exclude_inspection_id=self._inspection_id,
            limit=CONTROL_POINT_HISTORY_LIMIT,
        )
        if not shared_entries:
            self._set_panel_content(
                self._shared_experiences_host,
                self._build_info_label(CONTROL_POINT_SHARED_EXPERIENCES_EMPTY),
            )
        else:
            self._set_panel_content(
                self._shared_experiences_host,
                self._build_history_entries_list(
                    shared_entries,
                    include_workplace=True,
                ),
            )

    def _build_history_entries_list(
        self,
        entries,
        *,
        include_workplace: bool,
    ) -> QWidget:
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

        inspection_label = entry.inspection_number or str(entry.inspection_id)
        layout.addWidget(self._build_info_label(f"Prověrka: {inspection_label}"))

        if entry.note.strip():
            layout.addWidget(self._build_info_label(f"Poznámka: {entry.note.strip()}"))

        if entry.finding is not None:
            finding_text = self._text_preview(entry.finding.description, max_len=80)
            layout.addWidget(
                self._build_info_label(
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
            layout.addWidget(self._build_info_label(f"Poznámka: {entry.note.strip()}"))

        if entry.finding is not None:
            finding_text = self._text_preview(entry.finding.description, max_len=80)
            layout.addWidget(
                self._build_info_label(
                    f"Zjištění: {finding_text} ({finding_status_label(entry.finding.status)})"
                )
            )

        return row

    @staticmethod
    def _format_history_datetime(value) -> str:
        if value is None:
            return "—"
        return value.strftime("%d.%m.%Y %H:%M")

    def _select_control_point(self, context: ProverkyFindingKnowledgeContext) -> None:
        self._selected_control_point_id = context.control_point_id
        for control_point_id, frame in self._control_point_frames.items():
            selected = control_point_id == context.control_point_id
            frame.setProperty("selected", selected)
            frame.style().unpolish(frame)
            frame.style().polish(frame)
        self._refresh_control_point_history(context)

    def _build_control_points_scroll_area(self, section: dict) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)

        header = QLabel("Kontrolní body")
        header.setObjectName("SectionTitle")
        layout.addWidget(header)

        items = proverky_knowledge_service.get_active_items(section.get("kontrolni_body"))
        if not items:
            layout.addWidget(self._build_info_label(KNOWLEDGE_BLOCK_NOT_IMPLEMENTED_TEXT))
        else:
            first_context: ProverkyFindingKnowledgeContext | None = None
            for item in items:
                context = self._context_for_control_point(item)
                if first_context is None:
                    first_context = context
                layout.addWidget(self._build_control_point_row(item))
            if first_context is not None:
                self._select_control_point(first_context)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _build_control_point_row(self, item: dict) -> QWidget:
        context = self._context_for_control_point(item)
        finding = self._finding_for_context(context)
        severity = proverky_knowledge_service.get_control_point_severity(item)

        row_frame = _ControlPointFrame()
        row_frame.setObjectName("ControlPointPanel")
        row_frame.setProperty("severity", severity)
        row_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row_frame.clicked.connect(lambda ctx=context: self._select_control_point(ctx))
        self._control_point_frames[context.control_point_id] = row_frame
        row_frame.style().unpolish(row_frame)
        row_frame.style().polish(row_frame)

        row_layout = QVBoxLayout(row_frame)
        row_layout.setContentsMargins(14, 12, 14, 14)
        row_layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)
        header_row.addWidget(_ControlPointSeverityBadge(severity), 0, Qt.AlignmentFlag.AlignTop)
        nazev = context.control_point_label
        title_label = QLabel(nazev)
        title_label.setObjectName("ControlPointTitle")
        title_label.setWordWrap(True)
        header_row.addWidget(title_label, 1)
        row_layout.addLayout(header_row)

        popis = str(item.get("popis") or "").strip()
        if popis:
            description = QLabel(popis)
            description.setObjectName("InfoText")
            description.setWordWrap(True)
            row_layout.addWidget(description)

        result_selector = ControlResultSelectorWidget()
        result_selector.configure(
            entity_type=ENTITY_PROVERKY,
            entity_id=self._inspection_id,
            context=self._control_point_context(context),
            must_be_saved_message=INSPECTION_MUST_BE_SAVED_MESSAGE,
        )
        row_layout.addWidget(result_selector)

        photo_widget = ControlResultPhotoWidget()
        photo_widget.configure(
            entity_type=ENTITY_PROVERKY,
            entity_id=self._inspection_id,
            context=self._control_point_context(context),
            must_be_saved_message=INSPECTION_MUST_BE_SAVED_MESSAGE,
        )
        row_layout.addWidget(photo_widget)

        finding_host = QWidget()
        finding_layout = QVBoxLayout(finding_host)
        finding_layout.setContentsMargins(0, 0, 0, 0)
        finding_layout.setSpacing(0)
        row_layout.addWidget(finding_host)

        self._populate_finding_section(
            finding_host,
            finding_layout,
            item,
            context,
            finding,
            result_selector.current_result(),
        )
        result_selector.result_changed.connect(
            lambda result, host=finding_host, layout=finding_layout, cp=item, ctx=context: self._on_control_result_changed(
                host,
                layout,
                cp,
                ctx,
                result,
            )
        )
        result_selector.data_saved.connect(
            lambda ctx=context: self._refresh_control_point_history(ctx)
        )

        return row_frame

    def _populate_finding_section(
        self,
        host: QWidget,
        layout: QVBoxLayout,
        control_point: dict,
        context: ProverkyFindingKnowledgeContext,
        finding,
        result: str,
    ) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        finding = finding or self._finding_for_context(context)

        if finding is not None:
            layout.addWidget(self._build_linked_finding_block(finding, context))
            return

        if allows_finding(result):
            actions = QHBoxLayout()
            actions.setContentsMargins(0, 4, 0, 0)
            actions.addWidget(self._build_create_finding_button(control_point))
            actions.addStretch()
            wrapper = QWidget()
            wrapper.setLayout(actions)
            layout.addWidget(wrapper)

    def _on_control_result_changed(
        self,
        host: QWidget,
        layout: QVBoxLayout,
        control_point: dict,
        context: ProverkyFindingKnowledgeContext,
        result: str,
    ) -> None:
        self._select_control_point(context)
        self._populate_finding_section(
            host,
            layout,
            control_point,
            context,
            self._finding_for_context(context),
            result,
        )

    def _build_create_finding_button(self, control_point: dict) -> QPushButton:
        button = QPushButton(FINDING_CREATE_FROM_CONTROL_POINT_LABEL)
        button.clicked.connect(lambda _checked=False, item=control_point: self._create_finding(item))
        return button

    def _build_linked_finding_block(self, finding, context: ProverkyFindingKnowledgeContext) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ModulePanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 10, 12, 10)
        panel_layout.setSpacing(6)

        header = QLabel(FINDING_CREATED_LABEL)
        header.setObjectName("SectionTitle")
        panel_layout.addWidget(header)

        description = self._text_preview(finding.description)
        panel_layout.addWidget(self._build_info_label(description))

        status_label = QLabel(f"Stav: {finding_status_label(finding.status)}")
        status_label.setObjectName("InfoText")
        panel_layout.addWidget(status_label)

        open_btn = QPushButton(FINDING_OPEN_EXISTING_LABEL)
        open_btn.clicked.connect(lambda _checked=False, f=finding: self._open_existing_finding(f, context))
        panel_layout.addWidget(open_btn, 0, Qt.AlignmentFlag.AlignLeft)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 4, 0, 0)
        container_layout.addWidget(panel)
        return container

    def _context_for_control_point(self, control_point: dict) -> ProverkyFindingKnowledgeContext:
        control_point_label = str(control_point.get("nazev") or "—").strip() or "—"
        return ProverkyFindingKnowledgeContext(
            area_id=self._area_id,
            area_label=self._area_label,
            section_id=self._section_id,
            section_label=self._section_label,
            control_point_id=str(control_point.get("id") or "").strip(),
            control_point_label=control_point_label,
        )

    @staticmethod
    def _control_point_context(context: ProverkyFindingKnowledgeContext) -> ControlPointContext:
        return ControlPointContext(
            area_id=context.area_id,
            area_label=context.area_label,
            section_id=context.section_id,
            section_label=context.section_label,
            control_point_id=context.control_point_id,
            control_point_label=context.control_point_label,
        )

    def _finding_for_context(self, context: ProverkyFindingKnowledgeContext):
        if self._inspection_id is None or not context.control_point_id:
            return None

        return bozp_inspection_service.finding_for_control_point(
            self._inspection_id,
            area_label=context.area_label,
            section_label=context.section_label,
            control_point_id=context.control_point_id,
        )

    def _create_finding(self, control_point: dict) -> None:
        if self._inspection_id is None:
            QMessageBox.information(self, "Zjištění", INSPECTION_MUST_BE_SAVED_MESSAGE)
            return

        context = self._context_for_control_point(control_point)
        point_context = self._control_point_context(context)
        current_result = control_result_service.current_result(
            ENTITY_PROVERKY,
            self._inspection_id,
            point_context,
        )
        if not allows_finding(current_result):
            QMessageBox.information(self, "Zjištění", FINDING_REQUIRES_NONCOMPLIANCE_MESSAGE)
            return

        existing_open = bozp_inspection_service.open_finding_for_control_point(
            self._inspection_id,
            area_label=context.area_label,
            section_label=context.section_label,
            control_point_id=context.control_point_id,
        )
        if existing_open is not None:
            QMessageBox.information(self, "Zjištění", FINDING_DUPLICATE_MESSAGE)
            self._open_existing_finding(existing_open, context)
            return

        existing_any = self._finding_for_context(context)
        if existing_any is not None:
            QMessageBox.information(self, "Zjištění", FINDING_DUPLICATE_MESSAGE)
            self._open_existing_finding(existing_any, context)
            return

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
        self._notify_finding_saved()

    def _open_existing_finding(self, finding, context: ProverkyFindingKnowledgeContext) -> None:
        dialog = FindingDialog(
            self,
            finding=finding,
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

        finding_service.update(finding.id, **dialog.get_data())
        self._notify_finding_saved()

    def _notify_finding_saved(self) -> None:
        self.refresh()
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
    def _text_preview(text: str, max_len: int = 120) -> str:
        value = (text or "").strip()
        if not value:
            return "—"
        if len(value) <= max_len:
            return value
        return value[: max_len - 1].rstrip() + "…"

    @staticmethod
    def _build_info_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("InfoText")
        label.setWordWrap(True)
        return label
