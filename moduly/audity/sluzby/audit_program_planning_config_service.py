from dataclasses import dataclass

from moduly.audity.modely.audit_program import AuditProgramWorkplace
from moduly.audity.sluzby.audit_auditable_workplace_service import (
    is_auditable_workplace,
    list_auditable_workplaces,
)
from moduly.nastaveni.sluzby.settings_service import settings_service
from moduly.nastaveni.sluzby.workplace_audit_planning import (
    parse_preferred_months_json,
)


@dataclass(frozen=True)
class WorkplacePlanningConfig:
    workplace_id: int
    workplace_name: str
    audit_enabled: bool
    audit_interval_months: int
    preferred_months: tuple[int, ...]


@dataclass(frozen=True)
class WorkplacePlanningChange:
    workplace_id: int
    workplace_name: str
    is_new_auditable_workplace: bool
    interval_changed: bool
    preferred_months_changed: bool
    audit_disabled_in_settings: bool
    snapshot: WorkplacePlanningConfig | None
    current: WorkplacePlanningConfig | None


class AuditProgramPlanningConfigService:
    def get_current_config(self, workplace_id: int | None) -> WorkplacePlanningConfig | None:
        if not workplace_id:
            return None

        workplace = settings_service.get_workplace_by_id(workplace_id)
        if workplace is None:
            return None

        return WorkplacePlanningConfig(
            workplace_id=workplace.id,
            workplace_name=workplace.name.strip(),
            audit_enabled=is_auditable_workplace(workplace),
            audit_interval_months=int(workplace.audit_interval_months),
            preferred_months=parse_preferred_months_json(workplace.preferred_months_json),
        )

    def get_program_workplace_snapshot(
        self,
        program_workplace: AuditProgramWorkplace,
    ) -> WorkplacePlanningConfig | None:
        if program_workplace.workplace_id is None:
            return None

        return WorkplacePlanningConfig(
            workplace_id=program_workplace.workplace_id,
            workplace_name=program_workplace.workplace_name.strip(),
            audit_enabled=True,
            audit_interval_months=int(program_workplace.audit_interval_months),
            preferred_months=parse_preferred_months_json(
                program_workplace.preferred_months_json
            ),
        )

    def detect_program_planning_changes(
        self,
        program_workplaces: list[AuditProgramWorkplace],
    ) -> tuple[WorkplacePlanningChange, ...]:
        changes: list[WorkplacePlanningChange] = []
        program_workplace_ids = {
            item.workplace_id
            for item in program_workplaces
            if item.workplace_id is not None
        }

        for program_workplace in program_workplaces:
            if program_workplace.workplace_id is None:
                continue

            snapshot = self.get_program_workplace_snapshot(program_workplace)
            current = self.get_current_config(program_workplace.workplace_id)
            if snapshot is None:
                continue

            if current is None:
                changes.append(
                    WorkplacePlanningChange(
                        workplace_id=program_workplace.workplace_id,
                        workplace_name=program_workplace.workplace_name,
                        is_new_auditable_workplace=False,
                        interval_changed=False,
                        preferred_months_changed=False,
                        audit_disabled_in_settings=True,
                        snapshot=snapshot,
                        current=None,
                    )
                )
                continue

            interval_changed = (
                current.audit_interval_months != snapshot.audit_interval_months
            )
            preferred_months_changed = (
                current.preferred_months != snapshot.preferred_months
            )
            audit_disabled_in_settings = not current.audit_enabled
            if (
                interval_changed
                or preferred_months_changed
                or audit_disabled_in_settings
            ):
                changes.append(
                    WorkplacePlanningChange(
                        workplace_id=current.workplace_id,
                        workplace_name=current.workplace_name or snapshot.workplace_name,
                        is_new_auditable_workplace=False,
                        interval_changed=interval_changed,
                        preferred_months_changed=preferred_months_changed,
                        audit_disabled_in_settings=audit_disabled_in_settings,
                        snapshot=snapshot,
                        current=current,
                    )
                )

        for workplace in list_auditable_workplaces():
            if workplace.id in program_workplace_ids:
                continue

            current = self.get_current_config(workplace.id)
            if current is None:
                continue

            changes.append(
                WorkplacePlanningChange(
                    workplace_id=current.workplace_id,
                    workplace_name=current.workplace_name,
                    is_new_auditable_workplace=True,
                    interval_changed=False,
                    preferred_months_changed=False,
                    audit_disabled_in_settings=False,
                    snapshot=None,
                    current=current,
                )
            )

        return tuple(changes)


audit_program_planning_config_service = AuditProgramPlanningConfigService()
