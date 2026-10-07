"""Společný zápis odložených zjištění a úkolů v jedné už otevřené transakci.

Fyzické smazání existujícího zjištění zůstává. Maže text zjištění bez historie.
Tento modul ho nemění; jen brání tomu, aby se ve stejném flush zakládal úkol
pro zjištění, které se zároveň odstraňuje.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from core.services.control_result_photo_service import control_result_photo_service
from core.shared.sluzby.finding_service import finding_service
from core.shared.sluzby.finding_task_service import finding_task_service
from moduly.ukoly.sluzby.task_service import task_service


def delete_retired_photos(relative_paths: list[str]) -> None:
    """Smaže nahrazené soubory až po commitu. Chyba souboru nesmí vrátit transakci."""
    for relative in relative_paths:
        if not relative:
            continue
        try:
            control_result_photo_service.delete_photo(relative)
        except OSError:
            continue


def discard_staged_finding(edits: Any, finding_id: int) -> None:
    """Vyřadí zjištění ze staged stavu včetně ještě nevytvořeného úkolu."""
    _drop_task_creates_for_finding(edits, finding_id)
    if finding_id < 0:
        edits._finding_creates.pop(finding_id, None)
        edits._finding_deletes.discard(finding_id)
        return
    edits._finding_updates.pop(finding_id, None)
    edits._finding_deletes.add(finding_id)


def apply_staged_findings_and_tasks(edits: Any, session: Session) -> dict[int, int]:
    """Zapíše zjištění a úkoly do předané session. Nepřivolává commit ani clear."""
    finding_id_map: dict[int, int] = {}
    deleted_ids = {int(finding_id) for finding_id in edits._finding_deletes if int(finding_id) > 0}

    for finding_id, fields in list(edits._finding_updates.items()):
        if finding_id in edits._finding_deletes or finding_id < 0:
            continue
        clean = {
            key: value
            for key, value in fields.items()
            if not (key == "task_id" and isinstance(value, int) and value < 0)
        }
        if clean:
            finding_service.update(finding_id, session=session, **clean)

    for temp_id, data in sorted(edits._finding_creates.items(), key=lambda item: item[0], reverse=True):
        if temp_id in edits._finding_deletes:
            continue
        payload = dict(data)
        entity_type = payload.pop("entity_type")
        entity_id = int(payload.pop("entity_id"))
        payload.pop("task_id", None)
        created = finding_service.create(entity_type, entity_id, session=session, **payload)
        finding_id_map[temp_id] = created.id

    for finding_id in list(edits._finding_deletes):
        if finding_id > 0:
            finding_service.delete(finding_id, session=session)

    for _temp_id, pending in sorted(edits._task_creates.items(), key=lambda item: item[0], reverse=True):
        finding_id = int(pending["finding_id"])
        if finding_id in deleted_ids or finding_id in edits._finding_deletes:
            continue
        real_finding_id = finding_id_map.get(finding_id, finding_id)
        if real_finding_id < 0 or real_finding_id in deleted_ids:
            continue
        task = finding_task_service.create_task_from_finding(real_finding_id, session=session)
        data = dict(pending["data"])
        task_service.update_task(task_id=task.id, session=session, **data)

    for task_id, fields in list(edits._task_updates.items()):
        if task_id < 0:
            continue
        task_service.update_task(task_id=task_id, session=session, **fields)
        finding_task_service.resolve_finding_for_verified_task(
            task_service.get_task_by_id(task_id, session=session),
            session=session,
        )

    return finding_id_map


def _drop_task_creates_for_finding(edits: Any, finding_id: int) -> None:
    doomed = [
        temp_id
        for temp_id, pending in edits._task_creates.items()
        if int(pending.get("finding_id") or 0) == int(finding_id)
    ]
    for temp_id in doomed:
        edits._task_creates.pop(temp_id, None)
        edits._task_updates.pop(temp_id, None)
