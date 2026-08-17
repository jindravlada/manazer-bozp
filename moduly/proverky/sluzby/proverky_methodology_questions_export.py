"""Sestavení přehledu aktuálních otázek prověrek BOZP z živé metodiky / editoru."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import TYPE_CHECKING

from core.export.methodology_questions_pdf import (
    METHODOLOGY_PDF_PROVERKY_TITLE,
    PARAM_DESCRIPTION,
    PARAM_SEVERITY,
    PARAM_VERIFICATION_TYPE,
    MethodologyGroup,
    MethodologyQuestion,
    MethodologyQuestionsDocument,
    MethodologySection,
)
from core.shared.verification_type import VERIFICATION_TYPE_LABELS, methodology_verification_type
from moduly.proverky.constants import CONTROL_POINT_SEVERITY_OPTIONS
from moduly.proverky.sluzby.proverky_knowledge_service import (
    KNOWLEDGE_NODE_AREA,
    KNOWLEDGE_NODE_SECTION,
    KnowledgeTreeNode,
    proverky_knowledge_service,
)

if TYPE_CHECKING:
    from moduly.proverky.ui.proverky_knowledge_editor_dialog import ProverkyKnowledgeEditorDialog

_SEVERITY_LABELS = dict(CONTROL_POINT_SEVERITY_OPTIONS)


def build_proverky_methodology_questions_document(
    *,
    knowledge_tree: list[KnowledgeTreeNode] | None = None,
    section_drafts: dict[tuple[str, str], dict] | None = None,
    area_active: dict[str, bool] | None = None,
    created_on: date | None = None,
) -> MethodologyQuestionsDocument:
    """Sestaví přehled z jednoho stromu metodiky. Strom se nenačítá opakovaně."""
    if knowledge_tree is None:
        knowledge_tree = proverky_knowledge_service.get_knowledge_tree(
            include_inactive=True,
            ensure=False,
        )
    if area_active is None:
        area_active = {
            area.id: area.aktivni
            for area in proverky_knowledge_service.get_areas(
                include_inactive=True,
                ensure=False,
            )
        }

    groups: list[MethodologyGroup] = []
    question_count = 0
    overlays = section_drafts or {}

    for root in knowledge_tree:
        if root.node_type != KNOWLEDGE_NODE_AREA:
            continue
        if not _is_active(area_active.get(root.area_id, True)):
            continue
        sections = _collect_sections(root.children, root.area_id, overlays)
        if not sections:
            continue
        question_count += sum(len(section.questions) for section in sections)
        groups.append(MethodologyGroup(title=root.label, sections=tuple(sections)))

    return MethodologyQuestionsDocument(
        title=METHODOLOGY_PDF_PROVERKY_TITLE,
        created_on=created_on or date.today(),
        question_count=question_count,
        groups=tuple(groups),
    )


def build_proverky_methodology_questions_document_from_editor(
    editor: ProverkyKnowledgeEditorDialog,
    *,
    created_on: date | None = None,
) -> MethodologyQuestionsDocument:
    """Pracovní podoba editoru bez stash/uložení a bez změny dirty stavu."""
    drafts = dict(editor._drafts)
    section_editor = editor._section_editor
    if section_editor is not None:
        drafts[(section_editor.area_id, section_editor.section_id)] = (
            section_editor.capture_draft()
        )
    return build_proverky_methodology_questions_document(
        knowledge_tree=list(editor.knowledge_tree.tree_roots),
        section_drafts=drafts,
        created_on=created_on,
    )


def _collect_sections(
    nodes: tuple[KnowledgeTreeNode, ...] | list[KnowledgeTreeNode],
    area_id: str,
    section_drafts: dict[tuple[str, str], dict],
) -> list[MethodologySection]:
    collected: list[MethodologySection] = []
    for node in nodes:
        if node.node_type != KNOWLEDGE_NODE_SECTION:
            collected.extend(_collect_sections(node.children, area_id, section_drafts))
            continue
        section = _overlay_section(node, area_id, section_drafts)
        if not _is_active(section.get("aktivni", True)):
            continue
        questions = _questions_from_section(section)
        if questions:
            title = str(section.get("nazev") or node.label or "").strip() or node.label
            collected.append(
                MethodologySection(title=title, questions=tuple(questions))
            )
        collected.extend(_collect_sections(node.children, area_id, section_drafts))
    return collected


def _overlay_section(
    node: KnowledgeTreeNode,
    area_id: str,
    section_drafts: dict[tuple[str, str], dict],
) -> dict:
    overlay = section_drafts.get((area_id, node.node_id))
    if overlay:
        return deepcopy(overlay)
    if isinstance(node.section, dict):
        return deepcopy(node.section)
    return {}


def _questions_from_section(section: dict) -> list[MethodologyQuestion]:
    items = proverky_knowledge_service.get_active_items(section.get("kontrolni_body") or [])
    questions: list[MethodologyQuestion] = []
    for item in items:
        text = str(item.get("nazev") or "").strip()
        if not text:
            continue
        params: list[tuple[str, str]] = [
            (
                PARAM_VERIFICATION_TYPE,
                VERIFICATION_TYPE_LABELS.get(methodology_verification_type(item), ""),
            ),
            (
                PARAM_SEVERITY,
                _SEVERITY_LABELS.get(
                    proverky_knowledge_service.get_control_point_severity(item),
                    "",
                ),
            ),
        ]
        popis = str(item.get("popis") or "").strip()
        if popis:
            params.append((PARAM_DESCRIPTION, popis))
        questions.append(MethodologyQuestion(text=text, params=tuple(params)))
    return questions


def _is_active(value) -> bool:
    return bool(value) if value is not None else True
