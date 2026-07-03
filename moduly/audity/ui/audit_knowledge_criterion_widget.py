"""Pracovní karta oblasti ověření řídicího procesu."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.shared.constants import ENTITY_AUDITY
from core.shared.control_result_display import (
    allows_create_finding,
    allows_finding,
    allows_pkz_action,
)
from core.shared.finding_display import finding_status_label
from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
from core.shared.sluzby.finding_service import finding_service
from core.widgets.control_result_selector import ControlResultSelectorWidget
from core.widgets.control_result_photo_widget import ControlResultPhotoWidget
from core.widgets.finding_dialog import FindingDialog
from core.widgets.dialog_utils import exec_maximized
from core.widgets.image_viewer_dialog import ImageViewerDialog
from moduly.audity.constants import (
    CONTROL_POINT_SEVERITY_OPTIONS,
    FINDING_CREATE_FROM_CONTROL_POINT_LABEL,
    FINDING_CREATED_LABEL,
    FINDING_DIALOG_TITLE,
    FINDING_DUPLICATE_MESSAGE,
    FINDING_OPEN_EXISTING_LABEL,
    FINDING_REQUIRES_RESULT_MESSAGE,
    FINDING_SOURCE_LABEL,
    AUDIT_MUST_BE_SAVED_MESSAGE,
    AUDIT_FINDING_TYPE_NESHODA,
    AUDIT_FINDING_TYPE_PKZ,
    AUDIT_FINDING_TYPES,
    AUDIT_RESULT_HEADER_LABEL,
    AUDIT_RESULT_NOTE_LABEL,
    KNOWLEDGE_REFERENCE_PHOTOS_TITLE,
    REFERENCE_PHOTO_THUMBNAIL_SIZE,
    PROCESS_TERM_CRITERION,
    PROCESS_TERM_QUESTION,
    AuditFindingKnowledgeContext,
)
from moduly.audity.sluzby.audit_service import audit_service
from moduly.audity.sluzby.audit_knowledge_service import audit_knowledge_service
from moduly.audity.sluzby.audit_reference_photo_service import audit_reference_photo_service
from moduly.audity.ui.audit_methodology_panel_widget import AuditMethodologyPanelWidget


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



_SEVERITY_LABELS = dict(CONTROL_POINT_SEVERITY_OPTIONS)


class _ControlPointSeverityBadge(QLabel):
    def __init__(self, severity: str, parent=None):
        super().__init__(_SEVERITY_LABELS.get(severity, "Střední"), parent)
        self.setObjectName("ControlPointSeverityBadge")
        self.setProperty("severity", severity)
        self.style().unpolish(self)
        self.style().polish(self)


class AuditKnowledgeCriterionWidget(QWidget):
    """Střední pracovní plocha oblasti ověření — návodné otázky a hodnocení."""

    def __init__(self, methodology_panel: AuditMethodologyPanelWidget | None = None, parent=None):
        super().__init__(parent)

        self._methodology_panel = methodology_panel

        self._area_id = ""
        self._area_label = ""
        self._section_id = ""
        self._section_label = ""
        self._current_section: dict | None = None
        self._process_purpose = ""
        self._audit_id: int | None = None
        self._on_finding_saved = None
        self._selected_control_point_id = ""
        self._control_point_frames: dict[str, _ControlPointFrame] = {}

        self._content_host = QWidget()
        self._content_layout = QVBoxLayout(self._content_host)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(self._content_host)
        self._scroll_area = scroll

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll, 1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def scroll_to_top(self) -> None:
        self._scroll_area.verticalScrollBar().setValue(0)

    def set_process_purpose(self, purpose: str) -> None:
        self._process_purpose = str(purpose or "").strip()

    def set_criterion(
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
        self.scroll_to_top()

    def set_audit_id(self, audit_id: int | None) -> None:
        self._audit_id = audit_id
        self.refresh()

    def set_on_finding_saved(self, callback) -> None:
        self._on_finding_saved = callback

    def refresh(self) -> None:
        self._rebuild_content()

    def _rebuild_content(self) -> None:
        section = self._current_section
        self._clear_content()

        if not section:
            self._content_layout.addWidget(
                self._build_info_label(f"Vyberte {PROCESS_TERM_CRITERION.lower()} v seznamu vlevo.")
            )
            self._content_layout.addStretch()
            return

        if not self._section_label:
            self._section_label = str(section.get("nazev") or "").strip()

        questions = self._build_control_points_section(section)
        if questions is not None:
            self._content_layout.addWidget(questions)

        photos = audit_knowledge_service.get_general_reference_photos(section)
        if photos:
            self._content_layout.addWidget(
                self._build_block(
                    KNOWLEDGE_REFERENCE_PHOTOS_TITLE,
                    self._build_reference_photo_gallery(photos),
                )
            )

        self._content_layout.addStretch()

    def _clear_content(self) -> None:
        self._selected_control_point_id = ""
        self._control_point_frames.clear()
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

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
            absolute_path = audit_reference_photo_service.absolute_photo_path(relative_path)
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

        exec_maximized(ImageViewerDialog(image_path, title=KNOWLEDGE_REFERENCE_PHOTOS_TITLE, parent=self))

    def _select_control_point(self, context: AuditFindingKnowledgeContext) -> None:
        self._selected_control_point_id = context.control_point_id
        for control_point_id, frame in self._control_point_frames.items():
            selected = control_point_id == context.control_point_id
            frame.setProperty("selected", selected)
            frame.style().unpolish(frame)
            frame.style().polish(frame)
        if self._methodology_panel is not None:
            self._methodology_panel.refresh_history(context)

    def _build_control_points_section(self, section: dict) -> QWidget | None:
        items = audit_knowledge_service.get_audit_questions(section)
        if not items:
            return None

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        first_context: AuditFindingKnowledgeContext | None = None
        for item in items:
            context = self._context_for_control_point(item)
            if first_context is None:
                first_context = context
            layout.addWidget(self._build_control_point_row(item))
        if first_context is not None:
            self._select_control_point(first_context)

        return self._build_block(PROCESS_TERM_QUESTION, content)

    def _build_control_point_row(self, item: dict) -> QWidget:
        context = self._context_for_control_point(item)
        finding = self._finding_for_context(context)
        severity = audit_knowledge_service.get_control_point_severity(item)

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
            entity_type=ENTITY_AUDITY,
            entity_id=self._audit_id,
            context=self._control_point_context(context),
            must_be_saved_message=AUDIT_MUST_BE_SAVED_MESSAGE,
            result_header=AUDIT_RESULT_HEADER_LABEL,
            note_label=AUDIT_RESULT_NOTE_LABEL,
        )
        row_layout.addWidget(result_selector)

        photo_widget = ControlResultPhotoWidget()
        photo_widget.configure(
            entity_type=ENTITY_AUDITY,
            entity_id=self._audit_id,
            context=self._control_point_context(context),
            must_be_saved_message=AUDIT_MUST_BE_SAVED_MESSAGE,
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
            lambda ctx=context: self._methodology_panel.refresh_history(ctx)
            if self._methodology_panel is not None
            else None
        )

        return row_frame

    def _populate_finding_section(
        self,
        host: QWidget,
        layout: QVBoxLayout,
        control_point: dict,
        context: AuditFindingKnowledgeContext,
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

        if allows_create_finding(result):
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
        context: AuditFindingKnowledgeContext,
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

    def _default_finding_type_for_result(self, result: str) -> str | None:
        if allows_finding(result):
            return AUDIT_FINDING_TYPE_NESHODA
        if allows_pkz_action(result):
            return AUDIT_FINDING_TYPE_PKZ
        return None

    def _build_linked_finding_block(self, finding, context: AuditFindingKnowledgeContext) -> QWidget:
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

    def _context_for_control_point(self, control_point: dict) -> AuditFindingKnowledgeContext:
        control_point_label = str(
            control_point.get("text") or control_point.get("nazev") or "—"
        ).strip() or "—"
        question_id = str(control_point.get("id") or "").strip()
        return AuditFindingKnowledgeContext(
            area_id=self._area_id,
            area_label=self._area_label,
            section_id=self._section_id,
            section_label=self._section_label,
            control_point_id=question_id,
            control_point_label=control_point_label,
            question_stable_key=audit_knowledge_service.question_stable_key(
                self._area_id,
                self._section_id,
                question_id,
            ),
        )

    @staticmethod
    def _control_point_context(context: AuditFindingKnowledgeContext) -> ControlPointContext:
        return ControlPointContext(
            area_id=context.area_id,
            area_label=context.area_label,
            section_id=context.section_id,
            section_label=context.section_label,
            control_point_id=context.control_point_id,
            control_point_label=context.control_point_label,
        )

    def _finding_for_context(self, context: AuditFindingKnowledgeContext):
        if self._audit_id is None or not context.control_point_id:
            return None

        return audit_service.finding_for_control_point(
            self._audit_id,
            process_label=context.area_label,
            criterion_label=context.section_label,
            question_id=context.control_point_id,
        )

    def _create_finding(self, control_point: dict) -> None:
        if self._audit_id is None:
            QMessageBox.information(self, "Zjištění", AUDIT_MUST_BE_SAVED_MESSAGE)
            return

        context = self._context_for_control_point(control_point)
        point_context = self._control_point_context(context)
        current_result = control_result_service.current_result(
            ENTITY_AUDITY,
            self._audit_id,
            point_context,
        )
        default_finding_type = self._default_finding_type_for_result(current_result)
        if default_finding_type is None:
            QMessageBox.information(self, "Zjištění", FINDING_REQUIRES_RESULT_MESSAGE)
            return

        existing_open = audit_service.open_finding_for_control_point(
            self._audit_id,
            process_label=context.area_label,
            criterion_label=context.section_label,
            question_id=context.control_point_id,
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
            allowed_finding_types=AUDIT_FINDING_TYPES,
            default_finding_type=default_finding_type,
            knowledge_source={
                "source_label": FINDING_SOURCE_LABEL,
                "area_label": context.area_label,
                "section_label": context.section_label,
                "control_point_label": context.control_point_label,
            },
        )
        stored = control_result_service.get_for_control_point(
            ENTITY_AUDITY,
            self._audit_id,
            point_context,
        )
        note = str(stored.note or "").strip() if stored is not None else ""
        if note and allows_pkz_action(current_result):
            dialog.recommended_action_edit.setPlainText(note)
            if not dialog.description_edit.toPlainText().strip():
                dialog.description_edit.setPlainText(note)
        if not dialog.exec():
            return

        data = dialog.get_data()
        finding_service.create(
            ENTITY_AUDITY,
            self._audit_id,
            finding_type=data["finding_type"],
            reference_label=data["reference_label"] or context.question_stable_key or context.control_point_label,
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

    def _open_existing_finding(self, finding, context: AuditFindingKnowledgeContext) -> None:
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
