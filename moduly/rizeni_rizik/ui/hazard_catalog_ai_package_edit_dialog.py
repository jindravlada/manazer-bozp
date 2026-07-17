"""Editor celého návrhového balíku AI (R20b, ergonomie R20d)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.ai_oponentni.constants import (
    AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT,
    AI_PEER_REVIEW_PACKAGE_TYPE_LABELS,
    AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT,
)
from core.ai_oponentni.proposal_package_types import (
    AiProposalPackage,
    AiProposalPackageAssessment,
    AiProposalPackageEvent,
    AiProposalPackageLegalLink,
    AiProposalPackageMeasure,
)
from core.ai_oponentni.repository.ai_proposal_package_repository import (
    AiProposalPackageRepository,
)
from core.widgets.dialog_utils import create_save_cancel_box
from core.widgets.multi_exposed_group_selector import MultiExposedGroupSelector
from core.widgets.multi_legal_document_selector import MultiLegalDocumentSelector
from moduly.nastaveni.sluzby.exposed_group_service import ExposedGroupMatchKind, exposed_group_service
from moduly.nastaveni.ui.exposed_groups_management_dialog import ExposedGroupsManagementDialog
from moduly.rizeni_rizik.constants import (
    DEFAULT_RISK_SEVERITY,
    RISK_SEVERITIES,
    RISK_SEVERITY_LABELS,
)
from moduly.rizeni_rizik.constants_library import (
    CATALOG_AI_PACKAGE_EDIT_DIALOG_TITLE,
    CATALOG_AI_PACKAGE_EDIT_SAVE_BUTTON,
    CATALOG_AI_PACKAGE_SUMMARY_TITLE,
)
from moduly.rizeni_rizik.sluzby.hazard_catalog_package_incorporate_service import (
    hazard_catalog_package_incorporate_service,
)
from moduly.rizeni_rizik.sluzby.hazard_library_template_event_service import (
    hazard_library_template_event_service,
)
from moduly.pravni_pozadavky.sluzby.legal_document_service import legal_document_service
from moduly.rizeni_rizik.sluzby.hazard_catalog_legal_requirement_resolver import (
    LegalDocumentMatchKind,
    hazard_catalog_legal_document_resolver,
)


def resolve_exact_legal_document_id(reference: str) -> int | None:
    """Vrátí ID předpisu při jednoznačné shodě resolveru, jinak None."""
    match = hazard_catalog_legal_document_resolver.resolve(reference or "")
    if match.kind == LegalDocumentMatchKind.EXACT and match.document_id is not None:
        return int(match.document_id)
    return None


def collect_legal_document_ids_from_links(
    links: tuple[AiProposalPackageLegalLink, ...] | list[AiProposalPackageLegalLink],
) -> tuple[list[int], list[str], dict[int, str]]:
    """Rozdělí AI vazby na vybraná ID, nenalezené citace a mapu ID→původní citace."""
    selected_ids: list[int] = []
    unresolved: list[str] = []
    reference_by_id: dict[int, str] = {}
    seen_ids: set[int] = set()
    seen_unresolved: set[str] = set()

    for link in links or ():
        reference = (link.reference or "").strip()
        document_id = link.legal_document_id
        if document_id is None and reference:
            document_id = resolve_exact_legal_document_id(reference)

        if document_id is not None:
            document_id = int(document_id)
            if document_id not in seen_ids:
                selected_ids.append(document_id)
                seen_ids.add(document_id)
            if reference and document_id not in reference_by_id:
                reference_by_id[document_id] = reference
            continue

        if reference and reference.casefold() not in seen_unresolved:
            unresolved.append(reference)
            seen_unresolved.add(reference.casefold())

    return selected_ids, unresolved, reference_by_id


def resolve_target_event_name(
    *,
    package_record_id: int | None,
    target_event_export_id: str | None,
) -> str | None:
    """Vrátí lidský název cílové události pro EVENT-… z export_id_map oponentury."""
    export_id = (target_event_export_id or "").strip()
    if not export_id or package_record_id is None:
        return None
    record = AiProposalPackageRepository().get_by_id(package_record_id)
    if record is None:
        return None
    export_map = hazard_catalog_package_incorporate_service.get_export_id_map(
        record.ai_peer_review_id,
    )
    payload = export_map.get(export_id)
    if not isinstance(payload, dict) or payload.get("kind") != "event":
        return None
    event_id = payload.get("id")
    if event_id is None:
        return None
    event = hazard_library_template_event_service.get_by_id(int(event_id))
    if event is None:
        return None
    name = (event.name or "").strip()
    return name or None


def assessment_section_title(index: int, assessment: AiProposalPackageAssessment | None) -> str:
    groups: list[str] = []
    if assessment is not None:
        groups = [
            name.strip()
            for name in (assessment.exposed_groups or ())
            if str(name or "").strip()
        ]
        if not groups and assessment.exposed_group.strip():
            groups = [assessment.exposed_group.strip()]
        if not groups:
            for group_id in assessment.exposed_group_ids or ():
                name = exposed_group_service.display_name(int(group_id))
                if name:
                    groups.append(name)
    group_label = ", ".join(groups) if groups else "bez skupiny"
    return f"Posouzení {index} – {group_label}"


def format_package_summary(
    package: AiProposalPackage,
    *,
    target_event_name: str | None = None,
) -> str:
    type_label = AI_PEER_REVIEW_PACKAGE_TYPE_LABELS.get(
        package.package_type,
        package.package_type,
    )
    if package.package_type == AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT:
        if target_event_name:
            event_label = target_event_name
        else:
            event_label = "Doplnění události"
        event_line = f"Cílová událost: {event_label}"
    else:
        event_name = ""
        if package.event is not None:
            event_name = (package.event.name or "").strip()
        event_line = f"Nová událost: {event_name or '—'}"

    return "\n".join(
        [
            f"Typ: {type_label}",
            event_line,
            f"Posouzení: {package.assessment_count}",
            f"Existující opatření: {package.existing_measure_count}",
            f"Potřebná opatření: {package.required_measure_count}",
            f"Právní vazby: {package.legal_link_count}",
        ],
    )


def _configure_plain_text(widget: QPlainTextEdit, *, min_height: int) -> None:
    widget.setMinimumHeight(min_height)
    widget.setMaximumHeight(max(min_height * 2, 120))
    widget.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
    widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)


class _AssessmentEditor(QWidget):
    def __init__(self, parent=None, *, assessment: AiProposalPackageAssessment | None = None):
        super().__init__(parent)
        layout = QFormLayout(self)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        group_row = QHBoxLayout()
        self.exposed_groups = MultiExposedGroupSelector(self)
        self.manage_groups_btn = QPushButton("Spravovat číselník…")
        self.manage_groups_btn.clicked.connect(self._open_groups_management)
        group_row.addWidget(self.exposed_groups, 1)
        group_row.addWidget(self.manage_groups_btn)

        self.severity = QComboBox()
        for severity in RISK_SEVERITIES:
            self.severity.addItem(RISK_SEVERITY_LABELS[severity], severity)
        self.conclusion = QPlainTextEdit()
        _configure_plain_text(self.conclusion, min_height=50)
        self.existing_measures = QPlainTextEdit()
        self.existing_measures.setPlaceholderText("Jedno opatření na řádek")
        _configure_plain_text(self.existing_measures, min_height=60)
        self.required_measures = QPlainTextEdit()
        self.required_measures.setPlaceholderText("Jedno opatření na řádek")
        _configure_plain_text(self.required_measures, min_height=60)

        layout.addRow("Ohrožené skupiny *:", group_row)
        layout.addRow("Závažnost *:", self.severity)
        layout.addRow("Závěr:", self.conclusion)
        layout.addRow("Existující opatření:", self.existing_measures)
        layout.addRow("Potřebná opatření:", self.required_measures)

        if assessment is not None:
            group_ids = list(assessment.exposed_group_ids)
            if not group_ids and assessment.exposed_group_id is not None:
                group_ids = [assessment.exposed_group_id]
            if not group_ids:
                for name in assessment.exposed_groups or (
                    (assessment.exposed_group,) if assessment.exposed_group else ()
                ):
                    match = exposed_group_service.classify_name(name)
                    if match.kind == ExposedGroupMatchKind.ACTIVE and match.groups:
                        group_ids.append(int(match.groups[0].id))
            self.exposed_groups.reload(preserve_ids=group_ids)
            severity_index = self.severity.findData(
                assessment.severity if assessment.severity in RISK_SEVERITIES else DEFAULT_RISK_SEVERITY,
            )
            if severity_index >= 0:
                self.severity.setCurrentIndex(severity_index)
            self.conclusion.setPlainText(assessment.conclusion)
            self.existing_measures.setPlainText(
                "\n".join(m.description for m in assessment.existing_measures),
            )
            self.required_measures.setPlainText(
                "\n".join(m.description for m in assessment.required_measures),
            )
        else:
            self.exposed_groups.reload()
            severity_index = self.severity.findData(DEFAULT_RISK_SEVERITY)
            if severity_index >= 0:
                self.severity.setCurrentIndex(severity_index)

    def _open_groups_management(self) -> None:
        dialog = ExposedGroupsManagementDialog(self)
        dialog.exec()
        self.exposed_groups.reload(preserve_ids=self.exposed_groups.selected_group_ids())

    def to_assessment(self) -> AiProposalPackageAssessment:
        group_ids = self.exposed_groups.selected_group_ids()
        group_names: list[str] = []
        for group_id in group_ids:
            name = exposed_group_service.display_name(group_id)
            if name:
                group_names.append(name)
        return AiProposalPackageAssessment(
            exposed_group=group_names[0] if group_names else "",
            exposed_groups=tuple(group_names),
            severity=self.severity.currentData() or DEFAULT_RISK_SEVERITY,
            conclusion=self.conclusion.toPlainText().strip(),
            exposed_group_id=group_ids[0] if group_ids else None,
            exposed_group_ids=tuple(group_ids),
            existing_measures=tuple(
                AiProposalPackageMeasure(description=line.strip())
                for line in self.existing_measures.toPlainText().splitlines()
                if line.strip()
            ),
            required_measures=tuple(
                AiProposalPackageMeasure(description=line.strip())
                for line in self.required_measures.toPlainText().splitlines()
                if line.strip()
            ),
        )


class _CollapsibleAssessmentSection(QWidget):
    def __init__(
        self,
        parent=None,
        *,
        title: str,
        assessment: AiProposalPackageAssessment | None = None,
        expanded: bool = False,
    ):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(2)

        self.toggle = QToolButton(self)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(expanded)
        self.toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.toggle.setAutoRaise(True)
        self.toggle.clicked.connect(self._sync_expanded)
        root.addWidget(self.toggle)

        self.content = _AssessmentEditor(assessment=assessment)
        self.content.setVisible(expanded)
        root.addWidget(self.content)

        self.set_title(title)
        self._sync_expanded()

    @property
    def editor(self) -> _AssessmentEditor:
        return self.content

    def set_title(self, title: str) -> None:
        self.toggle.setText(title)

    def set_expanded(self, expanded: bool) -> None:
        self.toggle.setChecked(expanded)
        self._sync_expanded()

    def is_expanded(self) -> bool:
        return self.toggle.isChecked()

    def _sync_expanded(self) -> None:
        expanded = self.toggle.isChecked()
        self.content.setVisible(expanded)
        self.toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow,
        )


class HazardCatalogAiPackageEditDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        package: AiProposalPackage,
        package_record_id: int,
        target_event_name: str | None = None,
    ):
        super().__init__(parent)
        self._package = package
        self._package_record_id = package_record_id
        self._result_package: AiProposalPackage | None = None
        self._target_event_export_id = (package.target_event_export_id or "").strip()
        self._target_event_name = target_event_name
        if self._target_event_name is None and self._target_event_export_id:
            self._target_event_name = resolve_target_event_name(
                package_record_id=package_record_id,
                target_event_export_id=self._target_event_export_id,
            )

        self.setWindowTitle(CATALOG_AI_PACKAGE_EDIT_DIALOG_TITLE)
        self.setMinimumWidth(560)
        self.setMinimumHeight(520)
        self.resize(640, 720)
        self.setSizeGripEnabled(True)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        summary_box = QGroupBox(CATALOG_AI_PACKAGE_SUMMARY_TITLE)
        summary_layout = QVBoxLayout(summary_box)
        self.summary_label = QLabel(
            format_package_summary(package, target_event_name=self._target_event_name),
        )
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse,
        )
        summary_layout.addWidget(self.summary_label)
        root.addWidget(summary_box)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(10)

        meta = QLabel(f"ID balíku: {package.package_id}")
        meta.setWordWrap(True)
        layout.addWidget(meta)

        event_box = QGroupBox("Událost")
        event_form = QFormLayout(event_box)
        event_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.event_name = QLineEdit()
        self.event_description = QPlainTextEdit()
        _configure_plain_text(self.event_description, min_height=60)
        self.event_note = QPlainTextEdit()
        _configure_plain_text(self.event_note, min_height=50)
        self.target_event = QLineEdit(self._target_event_export_id)
        self.target_event_name_label = QPlainTextEdit()
        self.target_event_name_label.setReadOnly(True)
        self.target_event_name_label.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.target_event_name_label.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.target_event_name_label.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded,
        )
        self.target_event_name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.MinimumExpanding,
        )
        self.target_event_name_label.setMinimumHeight(48)
        self.target_event_name_label.setMaximumHeight(120)
        self.target_event_name_label.setFrameStyle(QFrame.Shape.StyledPanel)
        self.target_event_id_label = QLabel()
        self.target_event_id_label.setVisible(False)

        if package.package_type == AI_PEER_REVIEW_PACKAGE_TYPE_EXTEND_EVENT:
            display_name = self._target_event_name or "Doplnění události"
            self.target_event_name_label.setPlainText(display_name)
            if self._target_event_export_id:
                self.target_event_name_label.setToolTip(self._target_event_export_id)
            event_form.addRow("Cílová událost:", self.target_event_name_label)
            self.target_event.setVisible(False)
            if package.event is not None:
                self.event_name.setText(package.event.name)
                self.event_description.setPlainText(package.event.description)
                self.event_note.setPlainText(package.event.note)
        else:
            if package.event is not None:
                self.event_name.setText(package.event.name)
                self.event_description.setPlainText(package.event.description)
                self.event_note.setPlainText(package.event.note)
            event_form.addRow("Název události *:", self.event_name)
            event_form.addRow("Popis:", self.event_description)
            event_form.addRow("Poznámka:", self.event_note)
        layout.addWidget(event_box)

        assessments_box = QGroupBox("Posouzení")
        self._assessments_layout = QVBoxLayout(assessments_box)
        self._assessment_sections: list[_CollapsibleAssessmentSection] = []
        initial_assessments = package.assessments or (
            AiProposalPackageAssessment(
                exposed_group="",
                severity=DEFAULT_RISK_SEVERITY,
            ),
        )
        for index, assessment in enumerate(initial_assessments, start=1):
            section = _CollapsibleAssessmentSection(
                title=assessment_section_title(index, assessment),
                assessment=assessment,
                expanded=(index == 1),
            )
            self._assessment_sections.append(section)
            self._assessments_layout.addWidget(section)
        add_assessment_btn = QPushButton("Přidat posouzení")
        add_assessment_btn.clicked.connect(self._add_assessment)
        self._assessments_layout.addWidget(add_assessment_btn)
        layout.addWidget(assessments_box)

        legal_box = QGroupBox("Právní vazby")
        legal_layout = QVBoxLayout(legal_box)
        legal_info = QLabel(
            "Přidejte předpisy z registru přes našeptávač. "
            "Jednoznačné AI citace se předvyplní automaticky."
        )
        legal_info.setWordWrap(True)
        legal_layout.addWidget(legal_info)

        legal_form = QFormLayout()
        legal_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow,
        )
        self.legal_documents = MultiLegalDocumentSelector(self)
        legal_form.addRow("Právní předpis:", self.legal_documents)
        legal_layout.addLayout(legal_form)

        self.unresolved_legal_label = QLabel()
        self.unresolved_legal_label.setWordWrap(True)
        self.unresolved_legal_label.setObjectName("InfoText")
        legal_layout.addWidget(self.unresolved_legal_label)

        selected_ids, unresolved, reference_by_id = collect_legal_document_ids_from_links(
            package.legal_links,
        )
        self._legal_reference_by_document_id = reference_by_id
        self._unresolved_legal_references = list(unresolved)
        self.legal_documents.set_document_ids(selected_ids)
        self._refresh_unresolved_legal_label()
        layout.addWidget(legal_box)

        reasoning_label = QLabel("Zdůvodnění AI:")
        reasoning_label.setWordWrap(True)
        layout.addWidget(reasoning_label)
        self.reasoning = QPlainTextEdit(package.reasoning or "")
        _configure_plain_text(self.reasoning, min_height=80)
        layout.addWidget(self.reasoning)
        layout.addStretch(1)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        buttons = create_save_cancel_box(self)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button is not None:
            save_button.setText(CATALOG_AI_PACKAGE_EDIT_SAVE_BUTTON)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._scroll = scroll
        self._buttons = buttons

    @property
    def _assessment_editors(self) -> list[_AssessmentEditor]:
        return [section.editor for section in self._assessment_sections]

    def _add_assessment(self) -> None:
        index = len(self._assessment_sections) + 1
        section = _CollapsibleAssessmentSection(
            title=assessment_section_title(index, None),
            expanded=True,
        )
        self._assessment_sections.append(section)
        # Insert before the "Přidat posouzení" button.
        self._assessments_layout.insertWidget(self._assessments_layout.count() - 1, section)

    def _refresh_unresolved_legal_label(self) -> None:
        references = [
            reference.strip()
            for reference in self._unresolved_legal_references
            if str(reference or "").strip()
        ]
        if not references:
            self.unresolved_legal_label.setText("")
            self.unresolved_legal_label.hide()
            return
        lines = ["Návrhy AI k dořešení:"]
        lines.extend(f"• {reference}" for reference in references)
        self.unresolved_legal_label.setText("\n".join(lines))
        self.unresolved_legal_label.show()

    def _build_legal_links(self) -> tuple[AiProposalPackageLegalLink, ...]:
        legal_links: list[AiProposalPackageLegalLink] = []
        selected_ids = self.legal_documents.selected_document_ids()
        for document_id in selected_ids:
            reference = self._legal_reference_by_document_id.get(document_id, "")
            if not reference:
                document = legal_document_service.get_by_id(document_id)
                if document is not None:
                    reference = (document.title or "").strip() or f"Předpis #{document_id}"
                else:
                    reference = f"Předpis #{document_id}"
            legal_links.append(
                AiProposalPackageLegalLink(
                    reference=reference,
                    legal_document_id=document_id,
                ),
            )
        for reference in self._unresolved_legal_references:
            cleaned = str(reference or "").strip()
            if not cleaned:
                continue
            legal_links.append(AiProposalPackageLegalLink(reference=cleaned))
        return tuple(legal_links)

    def get_package(self) -> AiProposalPackage | None:
        return self._result_package

    def accept(self) -> None:
        assessments: list[AiProposalPackageAssessment] = []
        for index, editor in enumerate(self._assessment_editors, start=1):
            assessment = editor.to_assessment()
            if not assessment.exposed_group.strip() and not assessment.exposed_group_ids:
                QMessageBox.warning(
                    self,
                    self.windowTitle(),
                    "Vyberte alespoň jednu ohroženou skupinu.",
                )
                return
            if index - 1 < len(self._assessment_sections):
                self._assessment_sections[index - 1].set_title(
                    assessment_section_title(index, assessment),
                )
            assessments.append(assessment)
        if not assessments:
            QMessageBox.warning(self, self.windowTitle(), "Balík musí mít alespoň jedno posouzení.")
            return

        event = None
        target_event = None
        if self._package.package_type == AI_PEER_REVIEW_PACKAGE_TYPE_NEW_EVENT:
            name = self.event_name.text().strip()
            if not name:
                QMessageBox.warning(self, self.windowTitle(), "Vyplňte název události.")
                return
            event = AiProposalPackageEvent(
                name=name,
                description=self.event_description.toPlainText().strip(),
                note=self.event_note.toPlainText().strip(),
            )
        else:
            target_event = self._target_event_export_id or self.target_event.text().strip() or None
            if not target_event:
                QMessageBox.warning(self, self.windowTitle(), "Vyplňte cílovou událost EVENT-…")
                return
            if self.event_name.text().strip():
                event = AiProposalPackageEvent(
                    name=self.event_name.text().strip(),
                    description=self.event_description.toPlainText().strip(),
                    note=self.event_note.toPlainText().strip(),
                )

        self._result_package = AiProposalPackage(
            package_id=self._package.package_id,
            package_type=self._package.package_type,
            target_event_export_id=target_event,
            event=event,
            assessments=tuple(assessments),
            legal_links=self._build_legal_links(),
            reasoning=self.reasoning.toPlainText().strip(),
        )
        super().accept()
