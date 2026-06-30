from dataclasses import dataclass

from moduly.vysetrovani_mu.constants import (
    ISHIKAWA_CATEGORIES,
    ISHIKAWA_OTHER_FACTOR,
    ISHIKAWA_STATUS_LABELS,
    ISHIKAWA_STATUS_VYVRACENO,
)

_REJECTED_CAUSE_STATUSES = {
    ISHIKAWA_STATUS_VYVRACENO,
    "vyvracena",
    "vyvrácena",
    "vyvráceno",
    "vylouceno",
    "vyloučeno",
    "vyloučena",
    "vyloučená",
}


@dataclass(frozen=True)
class CauseChainStructure:
    by_id: dict[str, dict]
    children: dict[str, list[str]]
    roots: list[str]


def _text_preview(text: str | None, max_len: int = 80) -> str:
    value = (text or "").strip()
    if not value:
        return "—"
    if len(value) <= max_len:
        return value
    return value[: max_len - 1].rstrip() + "…"


def _factor_display(cause: dict) -> str:
    factor = (cause.get("factor") or "").strip()
    custom_factor = (cause.get("custom_factor") or "").strip()
    if factor == ISHIKAWA_OTHER_FACTOR and custom_factor:
        return custom_factor
    return factor


def chain_cause_label(cause: dict) -> str:
    factor = _factor_display(cause)
    if factor:
        return factor

    description = (cause.get("description") or "").strip()
    if description:
        return _text_preview(description, max_len=60)

    category = (cause.get("category") or "").strip()
    return category or "—"


def has_cause_chain_cycle(causes: list[dict]) -> bool:
    by_id = {str(cause.get("id") or ""): cause for cause in causes if cause.get("id")}
    for cause in causes:
        cause_id = str(cause.get("id") or "")
        if not cause_id:
            continue
        visited: set[str] = set()
        current_id = cause_id
        while current_id:
            if current_id in visited:
                return True
            visited.add(current_id)
            parent_id = str(by_id.get(current_id, {}).get("triggered_by_cause_id") or "")
            if not parent_id or parent_id not in by_id:
                break
            current_id = parent_id
    return False


def sorted_causes(causes: list[dict]) -> list[dict]:
    category_index = {category: index for index, category in enumerate(ISHIKAWA_CATEGORIES)}

    def sort_key(item: tuple[int, dict]) -> tuple[int, int]:
        index, cause = item
        return (category_index.get(cause.get("category"), len(ISHIKAWA_CATEGORIES)), index)

    indexed = list(enumerate(causes))
    indexed.sort(key=sort_key)
    return [cause for _, cause in indexed]


def build_cause_chain_structure(causes: list[dict]) -> CauseChainStructure | None:
    by_id = {
        str(cause.get("id") or ""): cause
        for cause in causes
        if str(cause.get("id") or "")
    }
    if not by_id:
        return None

    cause_order = {
        str(cause.get("id") or ""): index
        for index, cause in enumerate(sorted_causes(causes))
    }
    children: dict[str, list[str]] = {}
    roots: list[str] = []

    for cause_id, cause in by_id.items():
        parent_id = str(cause.get("triggered_by_cause_id") or "")
        if parent_id and parent_id in by_id:
            children.setdefault(parent_id, []).append(cause_id)
        else:
            roots.append(cause_id)

    for child_ids in children.values():
        child_ids.sort(key=lambda item: cause_order.get(item, 0))
    roots.sort(key=lambda item: cause_order.get(item, 0))

    return CauseChainStructure(by_id=by_id, children=children, roots=roots)


def is_rejected_cause(cause: dict) -> bool:
    raw = str(cause.get("status") or "").strip().lower()
    return raw in _REJECTED_CAUSE_STATUSES


def _cause_status_label(cause: dict) -> str:
    status = str(cause.get("status") or "").strip().lower()
    return ISHIKAWA_STATUS_LABELS.get(status, status or "—")


def _descendant_branch_strings(
    node_id: str,
    children: dict[str, list[str]],
    by_id: dict[str, dict],
) -> list[str]:
    branches: list[str] = []

    def walk(current_id: str, path: list[str]) -> None:
        current_path = [*path, chain_cause_label(by_id[current_id])]
        child_ids = children.get(current_id, [])
        if not child_ids:
            branches.append(" → ".join(current_path))
            return
        for child_id in child_ids:
            walk(child_id, current_path)

    for child_id in children.get(node_id, []):
        walk(child_id, [])

    return branches


def build_rejected_cause_chain_warnings(causes: list[dict]) -> list[str]:
    if not causes or has_cause_chain_cycle(causes):
        return []

    structure = build_cause_chain_structure(causes)
    if structure is None:
        return []

    warnings: list[str] = []
    for cause_id, cause in structure.by_id.items():
        if not is_rejected_cause(cause):
            continue

        branches = _descendant_branch_strings(cause_id, structure.children, structure.by_id)
        if not branches:
            continue

        label = chain_cause_label(cause)
        status_label = _cause_status_label(cause)
        if len(branches) == 1:
            branch_text = branches[0]
            warnings.append(
                f'Příčina „{label}“ ({status_label}) → navazuje: {branch_text}'
            )
        else:
            branch_lines = "\n    ".join(f"• {branch}" for branch in branches)
            warnings.append(
                f'Příčina „{label}“ ({status_label}) → navazují větve:\n    {branch_lines}'
            )

    return warnings


def format_rejected_cause_chain_warning_text(causes: list[dict]) -> str:
    warnings = build_rejected_cause_chain_warnings(causes)
    if not warnings:
        return ""

    header = (
        "⚠ Upozornění: na vyvrácenou nebo vyloučenou příčinu navazují další příčiny. "
        "Následník nemusí být nutně chybný, ale větev stojí na problematickém předpokladu."
    )
    return header + "\n\n" + "\n\n".join(warnings)


def build_cause_chain_text(causes: list[dict]) -> str:
    if not causes:
        return "Zatím nejsou definovány žádné příčiny."

    if has_cause_chain_cycle(causes):
        return "⚠ Zjištěna neplatná cyklická vazba mezi příčinami."

    structure = build_cause_chain_structure(causes)
    if structure is None:
        return "Zatím nejsou definovány žádné příčiny."

    by_id = structure.by_id
    children = structure.children
    roots = structure.roots

    branches: list[str] = []

    def format_path(path: list[str]) -> str:
        labels = [chain_cause_label(by_id[node_id]) for node_id in path]
        return "\n    ↓\n".join(labels)

    def walk(node_id: str, path: list[str]) -> None:
        current_path = [*path, node_id]
        child_ids = children.get(node_id, [])
        if not child_ids:
            branches.append(format_path(current_path))
            return
        for child_id in child_ids:
            walk(child_id, current_path)

    for root_id in roots:
        walk(root_id, [])

    if not branches:
        return "Zatím nejsou definovány žádné příčiny."

    if len(branches) == 1:
        return branches[0]

    branch_separator = "────────────────────────────"
    formatted_branches: list[str] = []
    for index, branch in enumerate(branches, start=1):
        formatted_branches.append(f"Větev {index}\n───────\n\n{branch}")

    return f"\n\n{branch_separator}\n\n".join(formatted_branches)
