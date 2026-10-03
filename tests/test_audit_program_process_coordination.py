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
    from moduly.audity.sluzby.audit_program_process_distribution import (
        PlannedVisitSlot,
        WorkplaceProcessPlan,
        per_visit_process_quotas,
        plan_coordinated_process_distribution,
    )
    from moduly.audity.sluzby.audit_program_service import audit_program_service


def _processes(count: int) -> list[str]:
    return [f"p{index}" for index in range(count)]


def _visits(workplace_ordinal: int, years: tuple[int, ...], month: int = 4) -> tuple[PlannedVisitSlot, ...]:
    return tuple(
        PlannedVisitSlot(
            visit_id=workplace_ordinal * 100 + index + 1,
            year=year,
            month=month,
        )
        for index, year in enumerate(years)
    )


def _workplaces(count: int, years: tuple[int, ...]) -> tuple[WorkplaceProcessPlan, ...]:
    return tuple(
        WorkplaceProcessPlan(ordinal=index, visits=_visits(index, years))
        for index in range(count)
    )


def _by_visit(assignments) -> dict[int, list[str]]:
    grouped: dict[int, list[str]] = {}
    for assignment in assignments:
        grouped.setdefault(assignment.visit_id, []).append(assignment.process_id)
    return grouped


class ProcessDistributionCoordinationTestCase(unittest.TestCase):
    def test_quotas_match_legacy_round_robin_counts(self) -> None:
        cases = ((26, 6), (9, 3), (10, 3), (4, 2), (3, 5), (5, 1), (0, 4))
        for process_count, visit_count in cases:
            expected = [0] * visit_count
            for index in range(process_count):
                expected[index % visit_count] += 1
            self.assertEqual(
                per_visit_process_quotas(process_count, visit_count),
                expected,
            )

    def test_workplaces_rotate_process_groups_across_years(self) -> None:
        processes = _processes(9)
        years = (2026, 2027, 2028)
        workplaces = _workplaces(3, years)

        first = plan_coordinated_process_distribution(processes, workplaces)
        second = plan_coordinated_process_distribution(processes, workplaces)
        self.assertEqual(first, second)

        grouped = _by_visit(first)
        expected = {
            1: ["p0", "p1", "p2"],
            101: ["p3", "p4", "p5"],
            201: ["p6", "p7", "p8"],
            2: ["p3", "p4", "p5"],
            102: ["p6", "p7", "p8"],
            202: ["p0", "p1", "p2"],
            3: ["p6", "p7", "p8"],
            103: ["p0", "p1", "p2"],
            203: ["p3", "p4", "p5"],
        }
        self.assertEqual(grouped, expected)

        for workplace in workplaces:
            covered = [
                process_id
                for visit in workplace.visits
                for process_id in grouped[visit.visit_id]
            ]
            self.assertEqual(sorted(covered), processes)
            self.assertEqual(len(covered), len(set(covered)))

        for year_index, year in enumerate(years):
            planned = [
                process_id
                for workplace in workplaces
                for process_id in grouped[workplace.visits[year_index].visit_id]
            ]
            self.assertEqual(sorted(set(planned)), processes)
            self.assertEqual(len(planned), len(processes))

    def test_first_visits_do_not_share_the_opening_group(self) -> None:
        assignments = plan_coordinated_process_distribution(
            _processes(9),
            _workplaces(3, (2026, 2027, 2028)),
        )
        grouped = _by_visit(assignments)
        first_visits = [grouped[1], grouped[101], grouped[201]]

        self.assertEqual(len({tuple(visit) for visit in first_visits}), 3)
        self.assertTrue(set(first_visits[0]).isdisjoint(first_visits[1]))
        self.assertTrue(set(first_visits[0]).isdisjoint(first_visits[2]))
        self.assertTrue(set(first_visits[1]).isdisjoint(first_visits[2]))

    def test_each_workplace_keeps_full_cycle_coverage_when_counts_are_uneven(self) -> None:
        processes = _processes(10)
        workplaces = _workplaces(3, (2026, 2027, 2028))
        assignments = plan_coordinated_process_distribution(processes, workplaces)
        grouped = _by_visit(assignments)
        quotas = per_visit_process_quotas(10, 3)

        for workplace in workplaces:
            covered: list[str] = []
            for visit, quota in zip(workplace.visits, quotas, strict=True):
                visit_processes = grouped[visit.visit_id]
                self.assertEqual(len(visit_processes), quota)
                covered.extend(visit_processes)
            self.assertEqual(sorted(covered), processes)

        first_year = [
            process_id
            for workplace in workplaces
            for process_id in grouped[workplace.visits[0].visit_id]
        ]
        self.assertEqual(sorted(set(first_year)), processes)

    def test_unavoidable_repetition_stays_deterministic_and_does_not_align_everyone(self) -> None:
        processes = _processes(4)
        workplaces = _workplaces(3, (2026, 2027))
        first = plan_coordinated_process_distribution(processes, workplaces)
        second = plan_coordinated_process_distribution(processes, workplaces)
        self.assertEqual(first, second)

        grouped = _by_visit(first)
        opening = [tuple(grouped[workplace.visits[0].visit_id]) for workplace in workplaces]
        self.assertEqual(len(set(opening)), 2)
        self.assertNotEqual(opening[0], opening[1])

        for workplace in workplaces:
            covered = [
                process_id
                for visit in workplace.visits
                for process_id in grouped[visit.visit_id]
            ]
            self.assertEqual(sorted(covered), processes)

    def test_existing_assignments_stay_in_place_and_steer_other_workplaces(self) -> None:
        processes = _processes(9)
        saved_doprava = WorkplaceProcessPlan(
            ordinal=0,
            visits=_visits(0, (2026, 2027, 2028)),
            fill=False,
            assigned_process_ids=frozenset(processes),
            assigned_by_visit=(
                (1, frozenset({"p0", "p1", "p2"})),
                (2, frozenset({"p3", "p4", "p5"})),
                (3, frozenset({"p6", "p7", "p8"})),
            ),
        )
        saved_jih = WorkplaceProcessPlan(
            ordinal=1,
            visits=_visits(1, (2026, 2027, 2028)),
            fill=False,
            assigned_process_ids=frozenset(processes),
            assigned_by_visit=(
                (101, frozenset({"p0", "p1", "p2"})),
                (102, frozenset({"p3", "p4", "p5"})),
                (103, frozenset({"p6", "p7", "p8"})),
            ),
        )
        sever_first_visit = frozenset({"p0", "p1", "p2"})
        sever = WorkplaceProcessPlan(
            ordinal=2,
            visits=_visits(2, (2026, 2027, 2028)),
            assigned_process_ids=sever_first_visit,
            assigned_by_visit=((201, sever_first_visit),),
        )

        assignments = plan_coordinated_process_distribution(
            processes,
            (saved_doprava, saved_jih, sever),
        )

        self.assertTrue(assignments)
        self.assertTrue(
            all(assignment.visit_id in {202, 203} for assignment in assignments)
        )
        self.assertTrue(
            all(assignment.process_id not in sever_first_visit for assignment in assignments)
        )

        grouped = _by_visit(assignments)
        covered = set(sever_first_visit)
        covered.update(assignment.process_id for assignment in assignments)
        self.assertEqual(covered, set(processes))
        self.assertEqual(grouped[202], ["p6", "p7", "p8"])
        self.assertEqual(grouped[203], ["p3", "p4", "p5"])


class AuditProgramProcessCoordinationServiceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PySide6.QtWidgets import QApplication

        cls._app = QApplication.instance() or QApplication([])

    def _create_program_with_workplaces(self):
        program = audit_program_service.create_program(
            name="Interní audity 2026–2029",
            date_from=date(2026, 4, 1),
            date_to=date(2029, 3, 31),
            standards=list(DEFAULT_AUDIT_PROGRAM_STANDARDS),
        )
        for workplace_id, name in ((101, "Doprava"), (102, "Jih"), (103, "Sever")):
            audit_program_service.add_workplace(
                program.id,
                workplace_id=workplace_id,
                workplace_name=name,
                audit_interval_months=12,
            )
        audit_program_service.generate_visits(program.id)
        return program

    def _stored_pairs(self, program_id: int):
        overview = audit_program_service.get_program_overview(program_id)
        assert overview is not None
        return {
            (item.id, item.visit_id, item.process_id)
            for item in overview.visit_processes
        }, overview

    def test_fresh_distribution_coordinates_workplaces_and_covers_each_cycle(self) -> None:
        program = self._create_program_with_workplaces()
        processes = audit_program_service._processes_for_program(program)
        self.assertGreater(len(processes), 3)

        first = audit_program_service.distribute_processes(program.id)
        second = audit_program_service.distribute_processes(program.id)
        self.assertGreater(len(first.created_processes), 0)
        self.assertEqual(len(second.created_processes), 0)

        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None
        process_ids = [process.id for process in processes]
        visits_by_workplace: dict[int, list] = {}
        for visit in overview.visits:
            visits_by_workplace.setdefault(visit.workplace_id, []).append(visit)
        processes_by_visit: dict[int, list[str]] = {}
        for item in overview.visit_processes:
            processes_by_visit.setdefault(item.visit_id, []).append(item.process_id)

        self.assertEqual(len(visits_by_workplace), 3)
        first_visit_sets: list[set[str]] = []
        first_year_processes: list[str] = []
        first_year_slots = 0
        quotas = per_visit_process_quotas(len(process_ids), 3)

        for workplace_visits in visits_by_workplace.values():
            workplace_visits.sort(
                key=lambda visit: (visit.planned_year or 0, visit.planned_month or 0, visit.id)
            )
            self.assertGreaterEqual(len(workplace_visits), 3)
            covered: list[str] = []
            for visit, quota in zip(workplace_visits, quotas, strict=False):
                visit_processes = processes_by_visit.get(visit.id, [])
                if visit.planned_year == workplace_visits[0].planned_year:
                    first_year_slots += len(visit_processes)
                    first_year_processes.extend(visit_processes)
                covered.extend(visit_processes)
            counted = [
                len(processes_by_visit.get(visit.id, []))
                for visit in workplace_visits
            ]
            self.assertEqual(counted, quotas)
            self.assertEqual(sorted(covered), sorted(process_ids))
            self.assertEqual(len(covered), len(set(covered)))
            first_visit_sets.append(set(processes_by_visit[workplace_visits[0].id]))

        self.assertEqual(len(first_visit_sets), 3)
        self.assertEqual(len({tuple(sorted(items)) for items in first_visit_sets}), 3)
        self.assertEqual(
            len(set(first_year_processes)),
            min(len(process_ids), first_year_slots),
        )

        coverage = audit_program_service.get_program_coverage(program.id)
        assert coverage is not None
        for workplace_coverage in coverage.missing_by_workplace:
            self.assertEqual(workplace_coverage.missing_process_ids, ())

    def test_saved_plan_is_not_rewritten(self) -> None:
        program = self._create_program_with_workplaces()
        processes = audit_program_service._processes_for_program(program)
        overview = audit_program_service.get_program_overview(program.id)
        assert overview is not None

        visits_by_workplace: dict[int, list] = {}
        for visit in overview.visits:
            visits_by_workplace.setdefault(visit.workplace_id, []).append(visit)

        for workplace_visits in visits_by_workplace.values():
            workplace_visits.sort(
                key=lambda visit: (visit.planned_year or 0, visit.planned_month or 0, visit.id)
            )
            for index, process in enumerate(processes):
                target = workplace_visits[index % len(workplace_visits)]
                audit_program_service.add_visit_process(
                    target.id,
                    process_id=process.id,
                    process_name=process.nazev,
                )

        before, _overview = self._stored_pairs(program.id)
        self.assertEqual(len(before), len(processes) * len(visits_by_workplace))

        distribution = audit_program_service.distribute_processes(program.id)
        after, _overview = self._stored_pairs(program.id)

        self.assertEqual(len(distribution.created_processes), 0)
        self.assertEqual(after, before)
