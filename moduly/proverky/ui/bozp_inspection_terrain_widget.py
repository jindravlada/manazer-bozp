"""Záložka Terén – plochý seznam kontrolních bodů pro ověření v provozu."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.shared.constants import ENTITY_PROVERKY
from core.shared.control_result_display import allows_finding
from core.shared.finding_display import finding_status_label
from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
from core.shared.sluzby.finding_service import finding_service
from core.widgets.control_result_photo_widget import ControlResultPhotoWidget
from core.widgets.control_result_selector import ControlResultSelectorWidget
from core.widgets.finding_dialog import FindingDialog
from moduly.proverky.constants import (
    CONTROL_POINT_SEVERITY_OPTIONS,
    FINDING_CREATE_FROM_CONTROL_POINT_LABEL,
    FINDING_CREATED_LABEL,
    FINDING_DIALOG_TITLE,
    FINDING_DUPLICATE_MESSAGE,
    FINDING_OPEN_EXISTING_LABEL,
    FINDING_REQUIRES_NONCOMPLIANCE_MESSAGE,
    FINDING_SOURCE_LABEL,
    INSPECTION_MUST_BE_SAVED_MESSAGE,
    MOVE_TO_DOCUMENTATION_LABEL,
    MOVE_VERIFICATION_TYPE_TOOLTIP,
    TERRAIN_CHECKLIST_BUTTON_LABEL,
    TERRAIN_CHECKLIST_DIALOG_TITLE,
    TERRAIN_CHECKLIST_REQUIRES_SAVED,
    TERRAIN_CHECKLIST_TOOLTIP,
    TERRAIN_TAB_EMPTY,
    TERRAIN_TAB_HINT,
    VERIFICATION_TYPE_DOCUMENTATION,
    VERIFICATION_TYPE_TERRAIN,
    ProverkyFindingKnowledgeContext,
)
from moduly.proverky.sluzby.bozp_inspection_service import bozp_inspection_service
from moduly.proverky.sluzby.inspection_verification_service import (
    InspectionControlPointRef,
    inspection_verification_service,
)
from moduly.proverky.sluzby.proverky_knowledge_service import proverky_knowledge_service
from moduly.proverky.sluzby.terrain_checklist_service import terrain_checklist_service

_SEVERITY_LABELS = dict(CONTROL_POINT_SEVERITY_OPTIONS)


class _ControlPointFrame(QFrame):
    pass


class _SeverityBadge(QLabel):
    def __init__(self, severity: str, parent=None):
        super().__init__(_SEVERITY_LABELS.get(severity, "Střední"), parent)
        self.setObjectName("ControlPointSeverityBadge")
        self.setProperty("severity", severity)
        self.style().unpolish(self)
        self.style().polish(self)


class BozpInspectionTerrainWidget(QWidget):
    """Pracovní seznam terénních kontrolních bodů (bez stromu oblastí)."""

    verification_type_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._inspection_id: int | None = None
        self._on_finding_saved = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        hint = QLabel(TERRAIN_TAB_HINT)
        hint.setObjectName("InfoText")
        hint.setWordWrap(True)
        header.addWidget(hint, 1)
        self.checklist_btn = QPushButton(TERRAIN_CHECKLIST_BUTTON_LABEL)
        self.checklist_btn.setToolTip(TERRAIN_CHECKLIST_TOOLTIP)
        self.checklist_btn.clicked.connect(self._export_terrain_checklist)
        header.addWidget(self.checklist_btn, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(self._scroll, 1)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 8, 0)
        self._content_layout.setSpacing(12)
        self._scroll.setWidget(self._content)

        self.refresh()

    def set_inspection_id(self, inspection_id: int | None) -> None:
        self._inspection_id = inspection_id
        self.checklist_btn.setEnabled(inspection_id is not None)
        self.refresh()

    def set_on_finding_saved(self, callback) -> None:
        self._on_finding_saved = callback

    def _export_terrain_checklist(self) -> None:
        if self._inspection_id is None:
            QMessageBox.information(
                self,
                TERRAIN_CHECKLIST_DIALOG_TITLE,
                TERRAIN_CHECKLIST_REQUIRES_SAVED,
            )
            return
        inspection = bozp_inspection_service.get_by_id(self._inspection_id)
        if inspection is None:
            QMessageBox.warning(
                self,
                TERRAIN_CHECKLIST_DIALOG_TITLE,
                "Prověrka nebyla nalezena.",
            )
            return
        try:
            terrain_checklist_service.open_for_inspection(inspection)
        except Exception as exc:
            QMessageBox.warning(
                self,
                TERRAIN_CHECKLIST_DIALOG_TITLE,
                f"Terénní checklist se nepodařilo vygenerovat.\n\n{exc}",
            )

    def refresh(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        points = inspection_verification_service.list_control_points(
            self._inspection_id,
            verification_type=VERIFICATION_TYPE_TERRAIN,
        )
        if not points:
            empty = QLabel(TERRAIN_TAB_EMPTY)
            empty.setObjectName("InfoText")
            empty.setWordWrap(True)
            self._content_layout.addWidget(empty)
            self._content_layout.addStretch()
            return

        for ref in points:
            self._content_layout.addWidget(self._build_row(ref))
        self._content_layout.addStretch()

    def _build_row(self, ref: InspectionControlPointRef) -> QWidget:
        context = ref.knowledge_context
        severity = proverky_knowledge_service.get_control_point_severity(ref.control_point)
        finding = self._finding_for_context(context)

        frame = _ControlPointFrame()
        frame.setObjectName("ControlPointPanel")
        frame.setProperty("severity", severity)
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        row_layout = QVBoxLayout(frame)
        row_layout.setContentsMargins(14, 12, 14, 14)
        row_layout.setSpacing(8)

        meta = QLabel(f"{ref.area_label} · {ref.section_label}")
        meta.setObjectName("InfoText")
        meta.setWordWrap(True)
        row_layout.addWidget(meta)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(10)
        header.addWidget(_SeverityBadge(severity), 0, Qt.AlignmentFlag.AlignTop)
        title = QLabel(ref.control_point_label)
        title.setObjectName("ControlPointTitle")
        title.setWordWrap(True)
        header.addWidget(title, 1)
        row_layout.addLayout(header)

        popis = str(ref.control_point.get("popis") or "").strip()
        if popis:
            description = QLabel(popis)
            description.setObjectName("InfoText")
            description.setWordWrap(True)
            row_layout.addWidget(description)

        cp_context = ControlPointContext(
            area_id=ref.area_id,
            area_label=ref.area_label,
            section_id=ref.section_id,
            section_label=ref.section_label,
            control_point_id=ref.control_point_id,
            control_point_label=ref.control_point_label,
        )

        result_selector = ControlResultSelectorWidget()
        result_selector.configure(
            entity_type=ENTITY_PROVERKY,
            entity_id=self._inspection_id,
            context=cp_context,
            must_be_saved_message=INSPECTION_MUST_BE_SAVED_MESSAGE,
        )
        row_layout.addWidget(result_selector)

        photo_widget = ControlResultPhotoWidget()
        photo_widget.configure(
            entity_type=ENTITY_PROVERKY,
            entity_id=self._inspection_id,
            context=cp_context,
            must_be_saved_message=INSPECTION_MUST_BE_SAVED_MESSAGE,
        )
        row_layout.addWidget(photo_widget)

        move_row = QHBoxLayout()
        move_row.setContentsMargins(0, 0, 0, 0)
        move_btn = QPushButton(MOVE_TO_DOCUMENTATION_LABEL)
        move_btn.setToolTip(MOVE_VERIFICATION_TYPE_TOOLTIP)
        move_btn.clicked.connect(lambda _checked=False, item=ref: self._move_to_documentation(item))
        move_row.addWidget(move_btn)
        move_row.addStretch()
        row_layout.addLayout(move_row)

        finding_host = QWidget()
        finding_layout = QVBoxLayout(finding_host)
        finding_layout.setContentsMargins(0, 0, 0, 0)
        finding_layout.setSpacing(0)
        row_layout.addWidget(finding_host)
        self._populate_finding_section(
            finding_host,
            finding_layout,
            ref,
            finding,
            result_selector.current_result(),
        )
        result_selector.result_changed.connect(
            lambda result, host=finding_host, layout=finding_layout, item=ref: (
                self._populate_finding_section(
                    host,
                    layout,
                    item,
                    self._finding_for_context(item.knowledge_context),
                    result,
                )
            )
        )
        return frame

    def _populate_finding_section(
        self,
        host: QWidget,
        layout: QVBoxLayout,
        ref: InspectionControlPointRef,
        finding,
        result: str,
    ) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        finding = finding or self._finding_for_context(ref.knowledge_context)
        if finding is not None:
            layout.addWidget(self._build_linked_finding_block(finding, ref))
            return
        if allows_finding(result):
            actions = QHBoxLayout()
            actions.setContentsMargins(0, 4, 0, 0)
            btn = QPushButton(FINDING_CREATE_FROM_CONTROL_POINT_LABEL)
            btn.clicked.connect(lambda _checked=False, item=ref: self._create_finding(item))
            actions.addWidget(btn)
            actions.addStretch()
            wrapper = QWidget()
            wrapper.setLayout(actions)
            layout.addWidget(wrapper)

    def _build_linked_finding_block(
        self, finding, ref: InspectionControlPointRef
    ) -> QWidget:
        panel = QFrame()
        panel.setObjectName("ModulePanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(12, 10, 12, 10)
        panel_layout.setSpacing(6)

        header = QLabel(FINDING_CREATED_LABEL)
        header.setObjectName("SectionTitle")
        panel_layout.addWidget(header)

        description = str(finding.description or "").strip() or "—"
        if len(description) > 180:
            description = description[:177] + "…"
        info = QLabel(description)
        info.setObjectName("InfoText")
        info.setWordWrap(True)
        panel_layout.addWidget(info)

        status_label = QLabel(f"Stav: {finding_status_label(finding.status)}")
        status_label.setObjectName("InfoText")
        panel_layout.addWidget(status_label)

        open_btn = QPushButton(FINDING_OPEN_EXISTING_LABEL)
        open_btn.clicked.connect(
            lambda _checked=False, f=finding, item=ref: self._open_existing_finding(f, item)
        )
        panel_layout.addWidget(open_btn, 0, Qt.AlignmentFlag.AlignLeft)
        return panel

    def _finding_for_context(self, context: ProverkyFindingKnowledgeContext):
        if self._inspection_id is None or not context.control_point_id:
            return None
        return bozp_inspection_service.finding_for_control_point(
            self._inspection_id,
            area_label=context.area_label,
            section_label=context.section_label,
            control_point_id=context.control_point_id,
        )

    def _create_finding(self, ref: InspectionControlPointRef) -> None:
        if self._inspection_id is None:
            QMessageBox.information(self, FINDING_DIALOG_TITLE, INSPECTION_MUST_BE_SAVED_MESSAGE)
            return
        context = ref.knowledge_context
        point_context = ControlPointContext(
            area_id=ref.area_id,
            area_label=ref.area_label,
            section_id=ref.section_id,
            section_label=ref.section_label,
            control_point_id=ref.control_point_id,
            control_point_label=ref.control_point_label,
        )
        current_result = control_result_service.current_result(
            ENTITY_PROVERKY,
            self._inspection_id,
            point_context,
        )
        if not allows_finding(current_result):
            QMessageBox.information(
                self,
                FINDING_DIALOG_TITLE,
                FINDING_REQUIRES_NONCOMPLIANCE_MESSAGE,
            )
            return

        existing_open = bozp_inspection_service.open_finding_for_control_point(
            self._inspection_id,
            area_label=context.area_label,
            section_label=context.section_label,
            control_point_id=context.control_point_id,
        )
        if existing_open is not None:
            QMessageBox.information(self, FINDING_DIALOG_TITLE, FINDING_DUPLICATE_MESSAGE)
            self._open_existing_finding(existing_open, ref)
            return

        existing_any = self._finding_for_context(context)
        if existing_any is not None:
            QMessageBox.information(self, FINDING_DIALOG_TITLE, FINDING_DUPLICATE_MESSAGE)
            self._open_existing_finding(existing_any, ref)
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
        if self._on_finding_saved:
            self._on_finding_saved()
        self.refresh()

    def _open_existing_finding(self, finding, ref: InspectionControlPointRef) -> None:
        context = ref.knowledge_context
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
        data = dialog.get_data()
        finding_service.update(finding.id, **data)
        if self._on_finding_saved:
            self._on_finding_saved()
        self.refresh()

    def _move_to_documentation(self, ref: InspectionControlPointRef) -> None:
        if self._inspection_id is None:
            QMessageBox.information(
                self,
                MOVE_TO_DOCUMENTATION_LABEL,
                INSPECTION_MUST_BE_SAVED_MESSAGE,
            )
            return
        inspection_verification_service.set_override(
            self._inspection_id,
            area_id=ref.area_id,
            section_id=ref.section_id,
            control_point_id=ref.control_point_id,
            verification_type=VERIFICATION_TYPE_DOCUMENTATION,
            methodology_type=ref.methodology_verification_type,
        )
        self.verification_type_changed.emit()
        self.refresh()
