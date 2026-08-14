"""Sestavení a kanonizace payloadu metodické podpory."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

from moduly.audity.constants import (
    METHOD_SUPPORT_PAYLOAD_VERSION,
    METHOD_SUPPORT_PROCESS_KEYS,
    METHOD_SUPPORT_SECTION_KEYS,
    METHOD_SUPPORT_SECTION_TEXT_KEYS,
    METHOD_SUPPORT_STATUS_AVAILABLE,
    METHOD_SUPPORT_STATUS_EMPTY,
)
from moduly.audity.sluzby.audit_knowledge_service import (
    KnowledgeTreeNode,
    audit_knowledge_service,
)


def canonical_json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def payload_integrity_hash(canonical_json: str) -> str:
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _clone_active_items(raw: Any) -> list[dict]:
    items = audit_knowledge_service.get_active_items(
        raw if isinstance(raw, list) else None
    )
    return [copy.deepcopy(item) for item in items]


def _section_has_support_content(section_payload: dict[str, Any]) -> bool:
    for key in METHOD_SUPPORT_SECTION_TEXT_KEYS:
        if str(section_payload.get(key) or "").strip():
            return True
    for key in METHOD_SUPPORT_SECTION_KEYS:
        if section_payload.get(key):
            return True
    return False


def _process_has_support_content(process_payload: dict[str, Any]) -> bool:
    for key in METHOD_SUPPORT_PROCESS_KEYS:
        if process_payload.get(key):
            return True
    return False


def build_support_payload_from_section(
    *,
    section: dict | None,
    process_knowledge: dict | None = None,
) -> tuple[dict[str, Any], str]:
    """Vrátí (payload, status available|empty)."""
    section = section or {}
    process_knowledge = process_knowledge or {}

    section_part: dict[str, Any] = {}
    for key in METHOD_SUPPORT_SECTION_TEXT_KEYS:
        value = str(section.get(key) or "").strip()
        section_part[key] = value
    for key in METHOD_SUPPORT_SECTION_KEYS:
        section_part[key] = _clone_active_items(section.get(key))

    process_part: dict[str, Any] = {}
    for key in METHOD_SUPPORT_PROCESS_KEYS:
        process_part[key] = _clone_active_items(process_knowledge.get(key))

    payload = {
        "schema_version": METHOD_SUPPORT_PAYLOAD_VERSION,
        "process": process_part,
        "section": section_part,
    }
    if _section_has_support_content(section_part) or _process_has_support_content(
        process_part
    ):
        status = METHOD_SUPPORT_STATUS_AVAILABLE
    else:
        status = METHOD_SUPPORT_STATUS_EMPTY
    return payload, status


def index_sections_from_knowledge_tree(
    roots: list[KnowledgeTreeNode] | tuple[KnowledgeTreeNode, ...],
) -> dict[tuple[str, str], tuple[dict, dict]]:
    """(process_id, section_id) → (section_dict, process_knowledge_dict)."""
    index: dict[tuple[str, str], tuple[dict, dict]] = {}
    for process_node in roots:
        process_id = str(process_node.process_id or process_node.node_id or "").strip()
        # Process knowledge: načti ze souboru jen pokud není v node — strom má section,
        # process file fields nejsou na KnowledgeTreeNode. Volající má předat process
        # knowledge mapu zvlášť, nebo se process fields berou prázdné a doplní se
        # z load při build_from_tree helperu níže.
        for section_node in process_node.children:
            section = dict(section_node.section or {})
            section_id = str(section.get("id") or section_node.node_id or "").strip()
            if not process_id or not section_id:
                continue
            index[(process_id, section_id)] = (section, {})
    return index


def build_section_index_with_process_knowledge(
    roots: list[KnowledgeTreeNode] | tuple[KnowledgeTreeNode, ...],
    *,
    process_knowledge_by_id: dict[str, dict] | None = None,
) -> dict[tuple[str, str], tuple[dict, dict]]:
    process_map = process_knowledge_by_id or {}
    index: dict[tuple[str, str], tuple[dict, dict]] = {}
    for process_node in roots:
        process_id = str(process_node.process_id or process_node.node_id or "").strip()
        process_knowledge = process_map.get(process_id) or {}
        for section_node in process_node.children:
            section = dict(section_node.section or {})
            section_id = str(section.get("id") or section_node.node_id or "").strip()
            if not process_id or not section_id:
                continue
            index[(process_id, section_id)] = (section, process_knowledge)
    return index


def load_process_knowledge_map_from_tree(
    roots: list[KnowledgeTreeNode] | tuple[KnowledgeTreeNode, ...],
) -> dict[str, dict]:
    """Jednorázově načte process JSON pro procesy ve stromu (bez ensure)."""
    result: dict[str, dict] = {}
    for process_node in roots:
        process_id = str(process_node.process_id or process_node.node_id or "").strip()
        if not process_id or process_id in result:
            continue
        process_def = audit_knowledge_service.get_process_by_id(process_id)
        if process_def is None or not process_def.has_knowledge_file:
            result[process_id] = {}
            continue
        result[process_id] = audit_knowledge_service.load_process_knowledge(
            process_def,
            ensure=False,
        ) or {}
    return result


def section_dict_from_payload(payload: dict[str, Any], *, base_section: dict) -> dict:
    """Obohatí snapshotovou sekci o zmrazenou podporu pro UI."""
    section = dict(base_section)
    section_part = payload.get("section") if isinstance(payload, dict) else None
    if not isinstance(section_part, dict):
        return section
    for key in METHOD_SUPPORT_SECTION_TEXT_KEYS:
        if key in section_part:
            section[key] = section_part.get(key) or ""
    for key in METHOD_SUPPORT_SECTION_KEYS:
        if key in section_part:
            section[key] = list(section_part.get(key) or [])
    return section


def process_knowledge_from_payload(payload: dict[str, Any]) -> dict:
    process_part = payload.get("process") if isinstance(payload, dict) else None
    if not isinstance(process_part, dict):
        return {}
    knowledge: dict[str, Any] = {}
    for key in METHOD_SUPPORT_PROCESS_KEYS:
        knowledge[key] = list(process_part.get(key) or [])
    return knowledge


def unavailable_payload() -> dict[str, Any]:
    return {
        "schema_version": METHOD_SUPPORT_PAYLOAD_VERSION,
        "process": {key: [] for key in METHOD_SUPPORT_PROCESS_KEYS},
        "section": {
            **{key: "" for key in METHOD_SUPPORT_SECTION_TEXT_KEYS},
            **{key: [] for key in METHOD_SUPPORT_SECTION_KEYS},
        },
    }
