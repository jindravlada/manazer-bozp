"""Sestavení přehledu aktuálních auditních otázek z živé metodiky / editoru."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import TYPE_CHECKING

from core.export.methodology_questions_pdf import (
    METHODOLOGY_PDF_AUDIT_TITLE,
    PARAM_SEVERITY,
    PARAM_VERIFICATION_TYPE,
    MethodologyGroup,
    MethodologyQuestion,
    MethodologyQuestionsDocument,
    MethodologySection,
)
from core.shared.verification_type import VERIFICATION_TYPE_LABELS, methodology_verification_type
from moduly.audity.constants import (
    AUDIT_QUESTION_KIND_EXTRAORDINARY,
    CONTROL_POINT_SEVERITY_OPTIONS,
)
from moduly.audity.sluzby.audit_knowledge_service import (
    KNOWLEDGE_NODE_PROCESS,
    KNOWLEDGE_NODE_SECTION,
    KnowledgeTreeNode,
    audit_knowledge_service,
)
from moduly.audity.sluzby.audit_question_kind import interpret_question_kind

if TYPE_CHECKING:
    from moduly.audity.ui.audity_knowledge_editor_dialog import AudityKnowledgeEditorDialog

_SEVERITY_LABELS = dict(CONTROL_POINT_SEVERITY_OPTIONS)
_SECTION_METADATA_KEYS = frozenset(
    {
        "nazev",
        "popis",
        "cil_overeni",
        "poradi",
        "aktivni",
        "legal_requirement_id",
    }
)


def build_audit_methodology_questions_document(
    *,
    knowledge_tree: list[KnowledgeTreeNode] | None = None,
    process_drafts: dict[str, dict] | None = None,
    section_drafts: dict[tuple[str, str], dict] | None = None,
    process_active: dict[str, bool] | None = None,
    created_on: date | None = None,
) -> MethodologyQuestionsDocument:
    """Sestaví přehled z jednoho stromu metodiky. Strom se nenačítá opakovaně."""
    if knowledge_tree is None:
        knowledge_tree = audit_knowledge_service.get_knowledge_tree(
            include_inactive=True,
            ensure=False,
        )
    if process_active is None:
        process_active = {
            process.id: process.aktivni
            for process in audit_knowledge_service.get_processes(
                include_inactive=True,
                ensure=False,
            )
        }

    groups: list[MethodologyGroup] = []
    question_count = 0
    drafts = process_drafts or {}
    section_overlays = section_drafts or {}

    for root in knowledge_tree:
        if root.node_type != KNOWLEDGE_NODE_PROCESS:
            continue
        process_overlay = drafts.get(root.process_id) or {}
        active = process_overlay.get("aktivni", process_active.get(root.process_id, True))
        if not _is_active(active):
            continue
        title = str(process_overlay.get("nazev") or root.label or "").strip() or root.label
        sections = _collect_sections(root.children, root.process_id, section_overlays)
        if not sections:
            continue
        question_count += sum(len(section.questions) for section in sections)
        groups.append(MethodologyGroup(title=title, sections=tuple(sections)))

    return MethodologyQuestionsDocument(
        title=METHODOLOGY_PDF_AUDIT_TITLE,
        created_on=created_on or date.today(),
        question_count=question_count,
        groups=tuple(groups),
    )


def build_audit_methodology_questions_document_from_editor(
    editor: AudityKnowledgeEditorDialog,
    *,
    created_on: date | None = None,
) -> MethodologyQuestionsDocument:
    """Pracovní podoba editoru bez stash/uložení a bez změny dirty stavu."""
    process_drafts = dict(editor._process_drafts)
    section_drafts = dict(editor._section_drafts)
    if (
        editor.content_stack.currentIndex() == editor._PAGE_PROCESS
        and editor.process_editor.has_process()
    ):
        process_drafts[editor.process_editor.process_id] = (
            editor.process_editor.process_metadata()
        )
    elif (
        editor.content_stack.currentIndex() == editor._PAGE_SECTION
        and editor.section_editor.has_section()
    ):
        key = (editor.section_editor.process_id, editor.section_editor.section_id)
        section_drafts[key] = editor.section_editor.section_metadata()

    return build_audit_methodology_questions_document(
        knowledge_tree=list(editor.knowledge_tree.tree_roots),
        process_drafts=process_drafts,
        section_drafts=section_drafts,
        created_on=created_on,
    )


def _collect_sections(
    nodes: tuple[KnowledgeTreeNode, ...] | list[KnowledgeTreeNode],
    process_id: str,
    section_drafts: dict[tuple[str, str], dict],
) -> list[MethodologySection]:
    collected: list[MethodologySection] = []
    for node in nodes:
        if node.node_type != KNOWLEDGE_NODE_SECTION:
            collected.extend(_collect_sections(node.children, process_id, section_drafts))
            continue
        section = _overlay_section(node, process_id, section_drafts)
        if not _is_active(section.get("aktivni", True)):
            continue
        questions = _questions_from_section(section)
        if questions:
            title = str(section.get("nazev") or node.label or "").strip() or node.label
            collected.append(
                MethodologySection(title=title, questions=tuple(questions))
            )
        collected.extend(_collect_sections(node.children, process_id, section_drafts))
    return collected


def _overlay_section(
    node: KnowledgeTreeNode,
    process_id: str,
    section_drafts: dict[tuple[str, str], dict],
) -> dict:
    section = deepcopy(node.section) if isinstance(node.section, dict) else {}
    overlay = section_drafts.get((process_id, node.node_id))
    if not overlay:
        return section
    for key in _SECTION_METADATA_KEYS:
        if key in overlay:
            section[key] = overlay[key]
    return section


def _questions_from_section(section: dict) -> list[MethodologyQuestion]:
    questions: list[MethodologyQuestion] = []
    for item in audit_knowledge_service.get_audit_questions(section):
        if not _is_active(item.get("aktivni", True)):
            continue
        if _is_extraordinary(item):
            continue
        text = str(item.get("text") or item.get("nazev") or "").strip()
        if not text:
            continue
        verification = VERIFICATION_TYPE_LABELS.get(
            methodology_verification_type(item),
            "",
        )
        severity = _SEVERITY_LABELS.get(
            audit_knowledge_service.get_control_point_severity(item),
            "",
        )
        questions.append(
            MethodologyQuestion(
                text=text,
                params=(
                    (PARAM_VERIFICATION_TYPE, verification),
                    (PARAM_SEVERITY, severity),
                ),
            )
        )
    return questions


def _is_extraordinary(item: dict) -> bool:
    try:
        kind = interpret_question_kind(item.get("question_kind"))
    except Exception:
        return False
    return kind == AUDIT_QUESTION_KIND_EXTRAORDINARY


def _is_active(value) -> bool:
    return bool(value) if value is not None else True
