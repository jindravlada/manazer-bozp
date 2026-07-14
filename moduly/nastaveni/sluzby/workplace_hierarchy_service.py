from __future__ import annotations

from moduly.nastaveni.constants.workplace_hierarchy_constants import (
    WORKPLACE_ITEM_TYPE_LABELS,
    WORKPLACE_ITEM_TYPE_OPERATION,
    WORKPLACE_ITEM_TYPE_WORKPLACE,
    WORKPLACE_ITEM_TYPE_WORKPLACE_PART,
    WORKPLACE_ITEM_TYPES,
    WORKPLACE_PARENT_TYPE,
)
from moduly.nastaveni.modely.workplace import Workplace
from core.utils.czech_sort import czech_sorted


class WorkplaceHierarchyError(ValueError):
    pass


def workplace_item_type_label(item_type: str) -> str:
    return WORKPLACE_ITEM_TYPE_LABELS.get(item_type, item_type)


def _index_by_id(workplaces: list[Workplace]) -> dict[int, Workplace]:
    return {workplace.id: workplace for workplace in workplaces}


def _children_map(workplaces: list[Workplace]) -> dict[int | None, list[Workplace]]:
    grouped: dict[int | None, list[Workplace]] = {}
    for workplace in workplaces:
        grouped.setdefault(workplace.parent_id, []).append(workplace)
    return grouped


def sort_workplaces_for_tree(workplaces: list[Workplace]) -> list[Workplace]:
    by_id = _index_by_id(workplaces)
    children = _children_map(workplaces)

    def sort_siblings(items: list[Workplace]) -> list[Workplace]:
        return czech_sorted(items, key=lambda item: item.name)

    ordered: list[Workplace] = []

    def walk(parent_id: int | None) -> None:
        for item in sort_siblings(children.get(parent_id, [])):
            ordered.append(item)
            walk(item.id)

    for root in sort_siblings(children.get(None, [])):
        ordered.append(root)
        walk(root.id)

    for workplace in workplaces:
        if workplace.id not in {item.id for item in ordered}:
            ordered.append(workplace)

    return ordered


def get_active_children(
    workplaces: list[Workplace],
    parent_id: int,
) -> list[Workplace]:
    return [
        workplace
        for workplace in workplaces
        if workplace.parent_id == parent_id and workplace.active
    ]


def get_parent_candidates(
    workplaces: list[Workplace],
    *,
    item_type: str,
    current_id: int | None = None,
    active_only: bool = True,
) -> list[Workplace]:
    required_parent_type = WORKPLACE_PARENT_TYPE.get(item_type)
    if required_parent_type is None:
        return []

    candidates = [
        workplace
        for workplace in workplaces
        if workplace.item_type == required_parent_type
        and (not active_only or workplace.active or workplace.id == current_id)
        and workplace.id != current_id
    ]
    return czech_sorted(candidates, key=lambda item: item.name)


def would_create_cycle(
    workplaces: list[Workplace],
    *,
    workplace_id: int | None,
    parent_id: int | None,
) -> bool:
    if workplace_id is None or parent_id is None:
        return False
    if workplace_id == parent_id:
        return True

    by_id = _index_by_id(workplaces)
    current_id: int | None = parent_id
    seen: set[int] = set()
    while current_id is not None:
        if current_id == workplace_id:
            return True
        if current_id in seen:
            return True
        seen.add(current_id)
        parent = by_id.get(current_id)
        if parent is None:
            break
        current_id = parent.parent_id
    return False


def validate_workplace_hierarchy(
    workplaces: list[Workplace],
    *,
    workplace_id: int | None,
    item_type: str,
    parent_id: int | None,
) -> None:
    if item_type not in WORKPLACE_ITEM_TYPES:
        raise WorkplaceHierarchyError("Neplatný typ položky.")

    required_parent_type = WORKPLACE_PARENT_TYPE.get(item_type)
    by_id = _index_by_id(workplaces)

    if item_type == WORKPLACE_ITEM_TYPE_OPERATION:
        if parent_id is not None:
            raise WorkplaceHierarchyError("Provoz nemá nadřazenou položku.")
        return

    if parent_id is None:
        raise WorkplaceHierarchyError(
            f"{workplace_item_type_label(item_type)} musí mít nadřazenou položku."
        )

    parent = by_id.get(parent_id)
    if parent is None:
        raise WorkplaceHierarchyError("Nadřazená položka nebyla nalezena.")

    if parent.item_type != required_parent_type:
        expected = workplace_item_type_label(required_parent_type or "")
        raise WorkplaceHierarchyError(
            f"Nadřazená položka musí být typu {expected}."
        )

    if would_create_cycle(workplaces, workplace_id=workplace_id, parent_id=parent_id):
        raise WorkplaceHierarchyError("Nelze vytvořit cyklus v hierarchii.")

    if workplace_id is not None and parent_id == workplace_id:
        raise WorkplaceHierarchyError("Položka nemůže být vlastním rodičem.")

    current = by_id.get(workplace_id) if workplace_id is not None else None
    if current is None:
        return

    if current.item_type != item_type:
        children = [item for item in workplaces if item.parent_id == workplace_id]
        if children and item_type != current.item_type:
            child_types = {child.item_type for child in children}
            if item_type == WORKPLACE_ITEM_TYPE_WORKPLACE_PART and WORKPLACE_ITEM_TYPE_WORKPLACE in child_types:
                raise WorkplaceHierarchyError(
                    "Provoz s podřízenými pracovišti nelze změnit na část pracoviště."
                )
            if item_type == WORKPLACE_ITEM_TYPE_OPERATION and any(
                child.item_type != WORKPLACE_ITEM_TYPE_WORKPLACE for child in children
            ):
                raise WorkplaceHierarchyError(
                    "Položku s podřízenými částmi pracoviště nelze změnit na provoz."
                )
            if item_type == WORKPLACE_ITEM_TYPE_WORKPLACE and any(
                child.item_type == WORKPLACE_ITEM_TYPE_WORKPLACE_PART for child in children
            ):
                raise WorkplaceHierarchyError(
                    "Pracoviště s podřízenými částmi nelze změnit typ na nižší úroveň."
                )


def validate_item_type_change(
    workplaces: list[Workplace],
    *,
    workplace_id: int,
    new_item_type: str,
) -> None:
    children = [item for item in workplaces if item.parent_id == workplace_id]
    if not children:
        return

    child_types = {child.item_type for child in children}
    if new_item_type == WORKPLACE_ITEM_TYPE_WORKPLACE_PART:
        raise WorkplaceHierarchyError(
            "Položku s podřízenými záznamy nelze změnit na část pracoviště."
        )
    if new_item_type == WORKPLACE_ITEM_TYPE_WORKPLACE and WORKPLACE_ITEM_TYPE_WORKPLACE_PART in child_types:
        raise WorkplaceHierarchyError(
            "Provoz s podřízenými pracovišti nelze změnit na pracoviště."
        )
    if new_item_type == WORKPLACE_ITEM_TYPE_OPERATION and (
        WORKPLACE_ITEM_TYPE_WORKPLACE in child_types
        or WORKPLACE_ITEM_TYPE_WORKPLACE_PART in child_types
    ):
        if WORKPLACE_ITEM_TYPE_WORKPLACE_PART in child_types:
            raise WorkplaceHierarchyError(
                "Položku s podřízenými částmi pracoviště nelze změnit na provoz."
            )


class WorkplaceHierarchyService:
    def sort_for_tree(self, workplaces: list[Workplace]) -> list[Workplace]:
        return sort_workplaces_for_tree(workplaces)

    def active_children(self, workplaces: list[Workplace], parent_id: int) -> list[Workplace]:
        return get_active_children(workplaces, parent_id)

    def parent_candidates(
        self,
        workplaces: list[Workplace],
        *,
        item_type: str,
        current_id: int | None = None,
        active_only: bool = True,
    ) -> list[Workplace]:
        return get_parent_candidates(
            workplaces,
            item_type=item_type,
            current_id=current_id,
            active_only=active_only,
        )

    def validate(
        self,
        workplaces: list[Workplace],
        *,
        workplace_id: int | None,
        item_type: str,
        parent_id: int | None,
    ) -> None:
        validate_workplace_hierarchy(
            workplaces,
            workplace_id=workplace_id,
            item_type=item_type,
            parent_id=parent_id,
        )
        if workplace_id is not None:
            validate_item_type_change(
                workplaces,
                workplace_id=workplace_id,
                new_item_type=item_type,
            )


workplace_hierarchy_service = WorkplaceHierarchyService()
