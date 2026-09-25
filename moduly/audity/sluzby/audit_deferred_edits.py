"""Odložené úpravy uvnitř otevřeného AuditDialog — zápis až při Uložit."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from core.services.control_result_photo_service import control_result_photo_service
from core.shared.constants import (
    CONTROL_RESULT_NEKONTROLOVANO,
    ENTITY_AUDITY,
    ENTITY_FINDING,
    FINDING_STATUS_V_PROCESU,
)
from core.shared.section_summary import (
    normalize_section_summary_text,
    section_summary_key,
)
from core.shared.sluzby.control_result_service import ControlPointContext, control_result_service
from core.shared.sluzby.finding_service import finding_service
from core.shared.sluzby.finding_task_service import finding_task_service
from moduly.audity.sluzby.audit_section_summary_service import (
    audit_section_summary_service,
)
from moduly.audity.sluzby.audit_verification_service import audit_verification_service
from moduly.ukoly.sluzby.task_service import task_service


def _control_key(
    entity_type: str,
    entity_id: int,
    context: ControlPointContext,
) -> tuple:
    return (
        entity_type,
        entity_id,
        context.area_label.strip(),
        context.section_label.strip(),
        context.control_point_id.strip(),
    )


def _override_key(area_id: str, section_id: str, control_point_id: str) -> tuple[str, str, str]:
    return (
        str(area_id or "").strip(),
        str(section_id or "").strip(),
        str(control_point_id or "").strip(),
    )


@dataclass
class _PendingControlResult:
    entity_type: str
    entity_id: int
    context: ControlPointContext
    result: str
    note: str
    shared_experience: bool


@dataclass
class _PendingPhoto:
    entity_type: str
    entity_id: int
    context: ControlPointContext
    action: str  # "attach" | "remove"
    source_path: Path | None = None


@dataclass
class _PendingVerificationOverride:
    audit_id: int
    area_id: str
    section_id: str
    control_point_id: str
    verification_type: str
    methodology_type: str


@dataclass
class _PendingSectionSummary:
    entity_id: int | None
    process_id: str
    section_id: str
    summary_text: str


@dataclass
class AuditDeferredEdits:
    """In-memory změny zjištění / úkolů / výsledků kontroly / foto / Dok↔Terén do flush()."""

    _control_results: dict[tuple, _PendingControlResult] = field(default_factory=dict)
    _photos: dict[tuple, _PendingPhoto] = field(default_factory=dict)
    _verification_overrides: dict[tuple[str, str, str], _PendingVerificationOverride] = field(
        default_factory=dict
    )
    _finding_updates: dict[int, dict[str, Any]] = field(default_factory=dict)
    _finding_creates: dict[int, dict[str, Any]] = field(default_factory=dict)
    _finding_deletes: set[int] = field(default_factory=set)
    _task_updates: dict[int, dict[str, Any]] = field(default_factory=dict)
    _task_creates: dict[int, dict[str, Any]] = field(default_factory=dict)
    _section_summaries: dict[tuple[str, str], _PendingSectionSummary] = field(
        default_factory=dict
    )
    _next_temp_finding_id: int = -1
    _next_temp_task_id: int = -1

    def has_changes(self) -> bool:
        return bool(
            self._control_results
            or self._photos
            or self._verification_overrides
            or self._finding_updates
            or self._finding_creates
            or self._finding_deletes
            or self._task_updates
            or self._task_creates
            or self._section_summaries
        )

    def has_execution_changes(self) -> bool:
        """Provádění auditu. Dok↔Terén a výchozí Nekontrolováno sem nepatří."""
        from core.shared.constants import CONTROL_RESULT_NEKONTROLOVANO

        for pending in self._control_results.values():
            if str(getattr(pending, "result", "") or "") != CONTROL_RESULT_NEKONTROLOVANO:
                return True
            if str(getattr(pending, "note", "") or "").strip():
                return True
        if self._photos:
            return True
        if self._finding_updates or self._finding_creates or self._finding_deletes:
            return True
        if self._task_updates or self._task_creates:
            return True
        for summary in self._section_summaries.values():
            if str(summary.summary_text or "").strip():
                return True
        return False

    def clear(self) -> None:
        self._control_results.clear()
        self._photos.clear()
        self._verification_overrides.clear()
        self._finding_updates.clear()
        self._finding_creates.clear()
        self._finding_deletes.clear()
        self._task_updates.clear()
        self._task_creates.clear()
        self._section_summaries.clear()
        self._next_temp_finding_id = -1
        self._next_temp_task_id = -1

    # --- výsledky kontroly -------------------------------------------------

    def set_control_result(
        self,
        entity_type: str,
        entity_id: int,
        context: ControlPointContext,
        *,
        result: str,
        note: str = "",
        shared_experience: bool = False,
    ) -> None:
        key = _control_key(entity_type, entity_id, context)
        self._control_results[key] = _PendingControlResult(
            entity_type=entity_type,
            entity_id=entity_id,
            context=context,
            result=result,
            note=note,
            shared_experience=shared_experience,
        )

    def get_control_result_view(
        self,
        entity_type: str,
        entity_id: int,
        context: ControlPointContext,
    ) -> Any | None:
        key = _control_key(entity_type, entity_id, context)
        pending = self._control_results.get(key)
        stored = control_result_service.get_for_control_point(entity_type, entity_id, context)

        if pending is not None:
            photo_path = getattr(stored, "photo_path", "") or ""
            return SimpleNamespace(
                result=pending.result,
                note=pending.note,
                shared_experience=pending.shared_experience,
                photo_path=photo_path,
            )
        return stored

    def current_result(
        self,
        entity_type: str,
        entity_id: int,
        context: ControlPointContext,
    ) -> str:
        row = self.get_control_result_view(entity_type, entity_id, context)
        if row is None:
            return CONTROL_RESULT_NEKONTROLOVANO
        return row.result

    def set_section_summary(
        self,
        *,
        entity_id: int | None,
        process_id: str,
        section_id: str,
        summary_text: str,
    ) -> None:
        key = section_summary_key(process_id, section_id)
        if not key[0] or not key[1]:
            return
        self._section_summaries[key] = _PendingSectionSummary(
            entity_id=int(entity_id) if entity_id is not None else None,
            process_id=key[0],
            section_id=key[1],
            summary_text=normalize_section_summary_text(summary_text),
        )

    def get_section_summary(
        self,
        audit_id: int | None,
        *,
        process_id: str,
        section_id: str,
    ) -> str:
        key = section_summary_key(process_id, section_id)
        pending = self._section_summaries.get(key)
        if pending is not None:
            return pending.summary_text
        return audit_section_summary_service.get_text(
            audit_id,
            process_id=process_id,
            section_id=section_id,
        )

    # --- fotografie výsledků kontroly --------------------------------------

    def stage_photo_attach(
        self,
        entity_type: str,
        entity_id: int,
        context: ControlPointContext,
        source_path: Path,
    ) -> None:
        key = _control_key(entity_type, entity_id, context)
        self._photos[key] = _PendingPhoto(
            entity_type=entity_type,
            entity_id=entity_id,
            context=context,
            action="attach",
            source_path=Path(source_path).resolve(),
        )

    def stage_photo_remove(
        self,
        entity_type: str,
        entity_id: int,
        context: ControlPointContext,
    ) -> None:
        key = _control_key(entity_type, entity_id, context)
        pending = self._photos.get(key)
        if pending is not None and pending.action == "attach":
            # Zrušit odložené přidání — žádný soubor v úložišti nevznikl.
            del self._photos[key]
            return
        self._photos[key] = _PendingPhoto(
            entity_type=entity_type,
            entity_id=entity_id,
            context=context,
            action="remove",
            source_path=None,
        )

    def get_photo_preview_path(
        self,
        entity_type: str,
        entity_id: int,
        context: ControlPointContext,
    ) -> Path | None:
        """Absolutní cesta pro náhled (odložený zdroj nebo uložený soubor)."""
        key = _control_key(entity_type, entity_id, context)
        pending = self._photos.get(key)
        if pending is not None:
            if pending.action == "remove":
                return None
            if pending.action == "attach" and pending.source_path is not None:
                return pending.source_path if pending.source_path.is_file() else None

        row = control_result_service.get_for_control_point(entity_type, entity_id, context)
        return control_result_service.resolve_photo_path(row)

    def expected_stored_photo_relative_path(
        self,
        entity_type: str,
        entity_id: int,
        context: ControlPointContext,
    ) -> str:
        """Cílová relativní cesta souboru po attach (pro regresní kontrolu osiřelých souborů)."""
        return control_result_photo_service.relative_photo_path(
            entity_type,
            entity_id,
            area_id=context.area_id,
            section_id=context.section_id,
            control_point_id=context.control_point_id,
        )

    # --- Doklad ↔ Terén ----------------------------------------------------

    def stage_verification_override(
        self,
        audit_id: int,
        *,
        area_id: str,
        section_id: str,
        control_point_id: str,
        verification_type: str,
        methodology_type: str,
    ) -> None:
        key = _override_key(area_id, section_id, control_point_id)
        target = audit_verification_service.normalize_verification_type(verification_type)
        methodology = audit_verification_service.normalize_verification_type(methodology_type)
        self._verification_overrides[key] = _PendingVerificationOverride(
            audit_id=audit_id,
            area_id=key[0],
            section_id=key[1],
            control_point_id=key[2],
            verification_type=target,
            methodology_type=methodology,
        )

    def effective_overrides_map(self, audit_id: int | None) -> dict[tuple[str, str, str], str]:
        mapping = dict(audit_verification_service.overrides_map(audit_id))
        if audit_id is None:
            return mapping
        for key, pending in self._verification_overrides.items():
            if pending.audit_id != audit_id:
                continue
            if pending.verification_type == pending.methodology_type:
                mapping.pop(key, None)
            else:
                mapping[key] = pending.verification_type
        return mapping

    # --- zjištění ----------------------------------------------------------

    def stage_finding_update(self, finding_id: int, fields: dict[str, Any]) -> None:
        if finding_id < 0:
            if finding_id in self._finding_creates:
                self._finding_creates[finding_id].update(fields)
            return
        if finding_id in self._finding_deletes:
            return
        merged = dict(self._finding_updates.get(finding_id, {}))
        merged.update(fields)
        self._finding_updates[finding_id] = merged

    def stage_finding_create(self, entity_type: str, entity_id: int, fields: dict[str, Any]) -> int:
        temp_id = self._next_temp_finding_id
        self._next_temp_finding_id -= 1
        payload = dict(fields)
        payload["entity_type"] = entity_type
        payload["entity_id"] = entity_id
        self._finding_creates[temp_id] = payload
        return temp_id

    def stage_finding_delete(self, finding_id: int) -> None:
        if finding_id < 0:
            self._finding_creates.pop(finding_id, None)
            self._finding_deletes.discard(finding_id)
            return
        self._finding_updates.pop(finding_id, None)
        self._finding_deletes.add(finding_id)

    def get_finding(self, finding_id: int) -> Any | None:
        if finding_id in self._finding_deletes:
            return None
        if finding_id < 0:
            data = self._finding_creates.get(finding_id)
            if data is None:
                return None
            return self._fake_finding(finding_id, data)

        finding = finding_service.get_by_id(finding_id)
        if finding is None:
            return None
        patch = self._finding_updates.get(finding_id)
        if not patch:
            return finding
        return self._overlay_finding(finding, patch)

    def list_findings(self, entity_type: str, entity_id: int) -> list[Any]:
        rows: list[Any] = []
        for finding in finding_service.get_for_entity(entity_type, entity_id):
            if finding.id in self._finding_deletes:
                continue
            patch = self._finding_updates.get(finding.id)
            rows.append(self._overlay_finding(finding, patch) if patch else finding)

        for temp_id, data in sorted(self._finding_creates.items(), key=lambda item: item[0], reverse=True):
            if data.get("entity_type") != entity_type or int(data.get("entity_id", 0)) != entity_id:
                continue
            if temp_id in self._finding_deletes:
                continue
            rows.append(self._fake_finding(temp_id, data))
        return rows

    def summarize_findings(self, entity_type: str, entity_id: int) -> dict[str, int]:
        findings = self.list_findings(entity_type, entity_id)
        from core.shared.constants import (
            FINDING_STATUS_OTEVRENE,
            FINDING_STATUS_V_PROCESU,
            FINDING_STATUS_VYPORADANO,
            VALID_FINDING_TYPES,
        )

        summary = {
            "total": len(findings),
            FINDING_STATUS_OTEVRENE: 0,
            FINDING_STATUS_V_PROCESU: 0,
            FINDING_STATUS_VYPORADANO: 0,
        }
        for finding in findings:
            status = getattr(finding, "status", "")
            if status in summary:
                summary[status] += 1
        for finding_type in VALID_FINDING_TYPES:
            summary[finding_type] = sum(
                1 for finding in findings if getattr(finding, "finding_type", None) == finding_type
            )
        return summary

    def finding_for_control_point(
        self,
        audit_id: int,
        *,
        process_label: str,
        criterion_label: str,
        question_id: str,
    ) -> Any | None:
        for finding in self.list_findings(ENTITY_AUDITY, audit_id):
            if (
                (finding.source_area_label or "") == process_label
                and (finding.source_section_label or "") == criterion_label
                and (finding.source_control_point_id or "") == question_id
            ):
                return finding
        return None

    # --- úkoly -------------------------------------------------------------

    def stage_task_update(self, task_id: int, fields: dict[str, Any]) -> Any:
        if task_id < 0:
            if task_id in self._task_creates:
                self._task_creates[task_id]["data"] = dict(fields)
                return self.get_task(task_id)
            return None
        merged = dict(self._task_updates.get(task_id, {}))
        merged.update(fields)
        self._task_updates[task_id] = merged
        return self.get_task(task_id)

    def stage_task_from_finding(self, finding_id: int, data: dict[str, Any] | None = None) -> Any:
        """Připraví odložené vytvoření úkolu ze zjištění (bez zápisu do DB)."""
        finding = self.get_finding(finding_id)
        if finding is None:
            raise ValueError("Zjištění nebylo nalezeno.")

        existing_task_id = getattr(finding, "task_id", None)
        if existing_task_id:
            task = self.get_task(int(existing_task_id))
            if task is not None:
                if data:
                    return self.stage_task_update(int(existing_task_id), data)
                return task

        temp_id = self._next_temp_task_id
        self._next_temp_task_id -= 1

        if data is None:
            title = finding_task_service._task_title(finding)
            description = finding_task_service._task_description(finding)
            data = {
                "title": title,
                "description": description,
                "priority": "Normální",
                "due_date": finding.due_date,
                "remind_from": None,
                "responsible_person_id": finding.responsible_person_id,
                "workplace_id": None,
                "completed": False,
                "completed_date": None,
                "requires_verification": True,
                "check_due_date": None,
                "checked_date": None,
                "checked_by_id": None,
                "canceled": False,
                "note": "",
            }

        self._task_creates[temp_id] = {
            "finding_id": finding_id,
            "data": dict(data),
        }
        self.stage_finding_update(
            finding_id,
            {"task_id": temp_id, "status": FINDING_STATUS_V_PROCESU},
        )
        return self.get_task(temp_id)

    def get_task(self, task_id: int) -> Any | None:
        if task_id < 0:
            pending = self._task_creates.get(task_id)
            if pending is None:
                return None
            return self._fake_task(task_id, pending["data"], pending["finding_id"])

        task = task_service.get_task_by_id(task_id)
        if task is None:
            return None
        patch = self._task_updates.get(task_id)
        if not patch:
            return task
        return self._overlay_task(task, patch)

    def list_pending_tasks_for_audit(self, audit_id: int) -> list[Any]:
        rows: list[Any] = []
        for temp_id, pending in self._task_creates.items():
            finding = self.get_finding(int(pending["finding_id"]))
            if finding is None:
                continue
            if getattr(finding, "entity_type", None) != ENTITY_AUDITY:
                continue
            if int(getattr(finding, "entity_id", 0) or 0) != audit_id:
                continue
            task = self.get_task(temp_id)
            if task is not None:
                rows.append(task)
        return rows

    def get_task_action(self, finding_id: int | None) -> str:
        if finding_id is None:
            return "hidden"
        finding = self.get_finding(finding_id)
        if finding is None:
            return "hidden"
        from core.shared.constants import FINDING_STATUS_VYPORADANO

        if finding.status == FINDING_STATUS_VYPORADANO:
            return "hidden"
        task_id = getattr(finding, "task_id", None)
        if not task_id:
            return "create"
        if self.get_task(int(task_id)) is None:
            return "create"
        return "open"

    # --- flush -------------------------------------------------------------

    def flush(self, *, entity_id: int | None = None) -> dict[int, int]:
        """Zapíše všechny odložené změny. Vrací mapování temp_finding_id → reálné id."""
        finding_id_map: dict[int, int] = {}

        for pending in list(self._control_results.values()):
            control_result_service.set_result(
                pending.entity_type,
                pending.entity_id,
                pending.context,
                result=pending.result,
                note=pending.note,
                shared_experience=pending.shared_experience,
            )

        for pending in list(self._photos.values()):
            if pending.action == "attach" and pending.source_path is not None:
                control_result_service.attach_photo(
                    pending.entity_type,
                    pending.entity_id,
                    pending.context,
                    pending.source_path,
                )
            elif pending.action == "remove":
                control_result_service.remove_photo(
                    pending.entity_type,
                    pending.entity_id,
                    pending.context,
                )

        for pending in list(self._verification_overrides.values()):
            audit_verification_service.set_override(
                pending.audit_id,
                area_id=pending.area_id,
                section_id=pending.section_id,
                control_point_id=pending.control_point_id,
                verification_type=pending.verification_type,
                methodology_type=pending.methodology_type,
            )

        for pending in list(self._section_summaries.values()):
            target_id = pending.entity_id if pending.entity_id is not None else entity_id
            if target_id is None:
                continue
            audit_section_summary_service.set_text(
                int(target_id),
                process_id=pending.process_id,
                section_id=pending.section_id,
                summary_text=pending.summary_text,
            )

        for finding_id, fields in list(self._finding_updates.items()):
            if finding_id in self._finding_deletes or finding_id < 0:
                continue
            # temp task_id se nesmí zapsat dřív, než existuje reálný úkol
            clean = {k: v for k, v in fields.items() if not (k == "task_id" and isinstance(v, int) and v < 0)}
            if clean:
                finding_service.update(finding_id, **clean)

        for temp_id, data in sorted(self._finding_creates.items(), key=lambda item: item[0], reverse=True):
            if temp_id in self._finding_deletes:
                continue
            payload = dict(data)
            entity_type = payload.pop("entity_type")
            entity_id = int(payload.pop("entity_id"))
            payload.pop("task_id", None)
            created = finding_service.create(entity_type, entity_id, **payload)
            finding_id_map[temp_id] = created.id

        for finding_id in list(self._finding_deletes):
            if finding_id > 0:
                finding_service.delete(finding_id)

        for temp_id, pending in sorted(self._task_creates.items(), key=lambda item: item[0], reverse=True):
            finding_id = int(pending["finding_id"])
            real_finding_id = finding_id_map.get(finding_id, finding_id)
            if real_finding_id < 0:
                continue
            task = finding_task_service.create_task_from_finding(real_finding_id)
            data = dict(pending["data"])
            task_service.update_task(task_id=task.id, **data)

        for task_id, fields in list(self._task_updates.items()):
            if task_id < 0:
                continue
            task_service.update_task(task_id=task_id, **fields)
            finding_task_service.resolve_finding_for_verified_task(
                task_service.get_task_by_id(task_id)
            )

        self.clear()
        return finding_id_map

    # --- helpers -----------------------------------------------------------

    @classmethod
    def _overlay_finding(cls, finding: Any, patch: dict[str, Any]) -> Any:
        keys = (
            "id",
            "entity_type",
            "entity_id",
            "finding_type",
            "reference_label",
            "description",
            "source_area_label",
            "source_section_label",
            "source_control_point_id",
            "source_control_point_label",
            "recommended_action",
            "due_date",
            "responsible_person_id",
            "responsible_person_name",
            "status",
            "resolved_at",
            "resolution_note",
            "display_order",
            "task_id",
        )
        data = {key: getattr(finding, key, None) for key in keys}
        data.update(patch)
        return cls._fake_finding(int(data["id"]), data)

    @staticmethod
    def _fake_finding(temp_id: int, data: dict[str, Any]) -> Any:
        return SimpleNamespace(
            id=temp_id,
            entity_type=data.get("entity_type", ""),
            entity_id=data.get("entity_id"),
            finding_type=data.get("finding_type", ""),
            reference_label=data.get("reference_label", "") or "",
            description=data.get("description", "") or "",
            source_area_label=data.get("source_area_label", "") or "",
            source_section_label=data.get("source_section_label", "") or "",
            source_control_point_id=data.get("source_control_point_id", "") or "",
            source_control_point_label=data.get("source_control_point_label", "") or "",
            recommended_action=data.get("recommended_action", "") or "",
            due_date=data.get("due_date"),
            responsible_person_id=data.get("responsible_person_id"),
            responsible_person_name=data.get("responsible_person_name", "") or "",
            status=data.get("status", ""),
            resolved_at=data.get("resolved_at"),
            resolution_note=data.get("resolution_note", "") or "",
            display_order=data.get("display_order", 0) or 0,
            task_id=data.get("task_id"),
        )

    @classmethod
    def _overlay_task(cls, task: Any, patch: dict[str, Any]) -> Any:
        keys = (
            "id",
            "title",
            "description",
            "priority",
            "due_date",
            "remind_from",
            "responsible_person_id",
            "responsible_person",
            "workplace_id",
            "completed",
            "completed_date",
            "requires_verification",
            "check_due_date",
            "checked_date",
            "checked_by_id",
            "canceled",
            "note",
            "source_module",
            "source_record_id",
            "task_type",
        )
        data = {key: getattr(task, key, None) for key in keys}
        data.update(patch)
        ns = cls._fake_task(
            int(data["id"]),
            data,
            int(data["source_record_id"] or 0),
        )
        ns.responsible_person = data.get("responsible_person") or ""
        ns.computed_status = getattr(task, "computed_status", "Aktivní")
        return ns

    @staticmethod
    def _fake_task(temp_id: int, data: dict[str, Any], finding_id: int) -> Any:
        return SimpleNamespace(
            id=temp_id,
            title=data.get("title", "") or "",
            description=data.get("description", "") or "",
            priority=data.get("priority", "Normální") or "Normální",
            due_date=data.get("due_date"),
            remind_from=data.get("remind_from"),
            responsible_person_id=data.get("responsible_person_id"),
            responsible_person="",
            workplace_id=data.get("workplace_id"),
            completed=bool(data.get("completed")),
            completed_date=data.get("completed_date"),
            requires_verification=bool(data.get("requires_verification", True)),
            check_due_date=data.get("check_due_date"),
            checked_date=data.get("checked_date"),
            checked_by_id=data.get("checked_by_id"),
            canceled=bool(data.get("canceled")),
            note=data.get("note", "") or "",
            source_module=ENTITY_FINDING,
            source_record_id=finding_id if finding_id > 0 else None,
            task_type="",
            computed_status="Aktivní",
        )
