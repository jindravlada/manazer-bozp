import importlib
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

_TMP = Path(tempfile.mkdtemp())

with patch.object(Path, "home", return_value=_TMP):
    import core.services.storage_service as storage_module

    importlib.reload(storage_module)
    storage_module.storage_service.ensure_structure()

    import core.database.session as session_module

    importlib.reload(session_module)

    from core.database.database_initializer import initialize_database

    initialize_database()

    from moduly.audity.constants import DEFAULT_AUDIT_PROGRAM_STANDARDS
    from moduly.audity.sluzby.audit_program_service import audit_program_service
    from moduly.nastaveni.constants.workplace_audit_constants import (
        DEFAULT_PREFERRED_AUDIT_MONTHS,
    )
    from moduly.nastaveni.sluzby.settings_service import settings_service
    from moduly.nastaveni.sluzby.workplace_audit_planning import (
        dump_preferred_months,
        plan_visit_months,
    )


class WorkplaceAuditPlanningTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def test_plan_visit_months_rotates_preferred_months(self) -> None:
        planned = plan_visit_months(
            date(2026, 4, 1),
            date(2029, 3, 31),
            6,
            DEFAULT_PREFERRED_AUDIT_MONTHS,
        )

        self.assertEqual(
            planned,
            [(2026, 4), (2026, 10), (2027, 3), (2027, 11), (2028, 5), (2028, 9)],
        )

    def test_plan_visit_months_respects_interval(self) -> None:
        planned = plan_visit_months(
            date(2026, 1, 1),
            date(2027, 12, 31),
            12,
            (3, 9),
        )

        self.assertEqual(planned, [(2026, 3), (2027, 9)])

    def test_plan_visit_months_without_preferences_uses_anchors(self) -> None:
        from moduly.nastaveni.sluzby.workplace_audit_planning import iter_visit_month_anchors

        date_from = date(2026, 4, 1)
        date_to = date(2029, 3, 31)
        anchors = iter_visit_month_anchors(date_from, date_to, 6)
        planned = plan_visit_months(date_from, date_to, 6, ())

        self.assertEqual(planned, anchors)


class AuditProgramIntelligentPlanningTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def _create_program(self):
        return audit_program_service.create_program(
            name="Interní audity 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )

    def _save_workplace(self, **fields):
        return settings_service.save_workplace(**fields)

    def _add_program_workplace(self, program_id: int, workplace):
        return audit_program_service.add_workplace(
            program_id,
            workplace_id=workplace.id,
            workplace_name=workplace.name,
            audit_interval_months=workplace.audit_interval_months,
            preferred_months_json=workplace.preferred_months_json,
        )

    def test_sync_skips_non_auditable_workplace(self) -> None:
        program = self._create_program()
        auditable = self._save_workplace(name="Auditované", audit_enabled=True)
        non_auditable = self._save_workplace(name="Bez auditu", audit_enabled=False)

        with patch.object(
            settings_service,
            "get_workplaces",
            return_value=[auditable, non_auditable],
        ):
            created = audit_program_service.sync_workplaces_from_settings(program.id)

        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None
        self.assertEqual(created, 1)
        workplace_ids = {item.workplace_id for item in overview.workplaces}
        self.assertEqual(workplace_ids, {auditable.id})

    def test_generate_respects_settings_interval_and_preferred_months(self) -> None:
        program = self._create_program()
        workplace = self._save_workplace(
            name="Provoz Gamma",
            audit_interval_months=6,
            preferred_months_json=dump_preferred_months(DEFAULT_PREFERRED_AUDIT_MONTHS),
        )
        self._add_program_workplace(program.id, workplace)

        result = audit_program_service.generate_visits(program.id)

        self.assertEqual(len(result.created_visits), 6)
        self.assertEqual(
            [(visit.planned_year, visit.planned_month) for visit in result.created_visits],
            [(2026, 4), (2026, 10), (2027, 3), (2027, 11), (2028, 5), (2028, 9)],
        )

    def test_generate_rotates_instead_of_repeating_same_months(self) -> None:
        program = self._create_program()
        workplace = self._save_workplace(name="Rotace")
        self._add_program_workplace(program.id, workplace)

        result = audit_program_service.generate_visits(program.id)
        months_by_year: dict[int, list[int]] = {}
        for visit in result.created_visits:
            assert visit.planned_year is not None
            assert visit.planned_month is not None
            months_by_year.setdefault(visit.planned_year, []).append(visit.planned_month)

        self.assertNotEqual(months_by_year[2026], months_by_year[2027])
        self.assertNotEqual(months_by_year[2027], months_by_year[2028])

    def test_settings_change_does_not_rewrite_existing_plan(self) -> None:
        program = self._create_program()
        workplace = self._save_workplace(
            name="Stabilní plán",
            preferred_months_json=dump_preferred_months((4, 10)),
        )
        self._add_program_workplace(program.id, workplace)
        first = audit_program_service.generate_visits(program.id)
        original = {
            visit.id: (visit.planned_year, visit.planned_month)
            for visit in first.created_visits
        }

        settings_service.save_workplace(
            id=workplace.id,
            name="Stabilní plán",
            audit_interval_months=12,
            preferred_months_json=dump_preferred_months((3, 9)),
        )

        second = audit_program_service.generate_visits(program.id)

        for visit_id, planned in original.items():
            stored = audit_program_service.repository.get_visit(visit_id)
            assert stored is not None
            self.assertEqual((stored.planned_year, stored.planned_month), planned)

        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None
        stored_original = [
            (visit.planned_year, visit.planned_month)
            for visit in overview.visits
            if visit.id in original
        ]
        self.assertEqual(stored_original, list(original.values()))

    def test_detect_planning_config_changes(self) -> None:
        program = self._create_program()
        tracked = self._save_workplace(name="Sledované")
        self._add_program_workplace(program.id, tracked)

        before = audit_program_service.detect_planning_config_changes(program.id)
        self.assertFalse(any(change.workplace_id == tracked.id for change in before))

        settings_service.save_workplace(
            id=tracked.id,
            name="Sledované",
            audit_interval_months=12,
            preferred_months_json=dump_preferred_months((3, 4, 5, 9, 10, 11)),
        )
        new_workplace = self._save_workplace(name="Nové auditované")

        changes = audit_program_service.detect_planning_config_changes(program.id)
        tracked_change = next(
            change for change in changes if change.workplace_id == tracked.id
        )
        new_change = next(
            change for change in changes if change.workplace_id == new_workplace.id
        )

        self.assertTrue(tracked_change.interval_changed)
        self.assertFalse(tracked_change.preferred_months_changed)
        self.assertTrue(new_change.is_new_auditable_workplace)


if __name__ == "__main__":
    unittest.main()
