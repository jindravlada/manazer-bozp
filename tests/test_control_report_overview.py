"""CONTROL-REPORT-RESULTS-OVERVIEW-3: společné řádky Přehledu výsledků."""

from __future__ import annotations

import unittest

from core.shared.sluzby.control_activity_statistics_service import (
    ControlActivityStatistics,
)
from core.shared.sluzby.control_report_overview import (
    format_result_overview_rating_lines,
    rating_category_sum,
    warn_if_checked_points_mismatch,
)


def _stats(**overrides) -> ControlActivityStatistics:
    values = dict(
        areas_checked=1,
        sections_checked=1,
        control_points_checked=485,
        ratings_vyhovuje=383,
        ratings_nevyhovuje=0,
        ratings_netyka_se=97,
        ratings_nehodnoceno=12,
        findings_total=5,
        tasks_total=5,
        ratings_vyhovuje_s_doporucenim=5,
    )
    values.update(overrides)
    return ControlActivityStatistics(**values)


class ControlReportOverviewTestCase(unittest.TestCase):
    def test_invariant_485(self) -> None:
        stats = _stats()
        self.assertEqual(485, stats.control_points_checked)
        self.assertEqual(
            485,
            stats.ratings_vyhovuje
            + stats.ratings_vyhovuje_s_doporucenim
            + stats.ratings_nevyhovuje
            + stats.ratings_netyka_se,
        )
        self.assertEqual(485, rating_category_sum(stats))
        self.assertFalse(warn_if_checked_points_mismatch(stats))

        lines = format_result_overview_rating_lines(
            stats,
            scope_label="Kontrolovaných oblastí",
            scope_count=stats.areas_checked,
            points_label="Kontrolních bodů",
        )
        text = "\n".join(lines)
        self.assertEqual(
            [
                "Kontrolovaných oblastí: 1",
                "Kontrolních bodů: 485",
                "Vyhovuje: 383",
                "Vyhovuje s doporučením: 5",
                "Nevyhovuje: 0",
                "Nelze posoudit: 97",
            ],
            lines,
        )
        self.assertNotIn("Netýká se", text)
        self.assertNotIn("Není relevantní", text)
        self.assertNotIn("Nekontrolováno", text)
        self.assertNotIn("nehodnoceno", text.casefold())

    def test_nelze_posoudit_zero_still_listed(self) -> None:
        stats = _stats(
            control_points_checked=4,
            ratings_vyhovuje=4,
            ratings_vyhovuje_s_doporucenim=0,
            ratings_nevyhovuje=0,
            ratings_netyka_se=0,
            ratings_nehodnoceno=0,
        )
        lines = format_result_overview_rating_lines(
            stats,
            scope_label="Auditovaných procesů",
            scope_count=2,
            points_label="Auditních tvrzení",
        )
        self.assertIn("Nelze posoudit: 0", lines)
        self.assertEqual(4, rating_category_sum(stats))

    def test_unevaluated_not_in_sum(self) -> None:
        stats = _stats(
            control_points_checked=6,
            ratings_vyhovuje=3,
            ratings_vyhovuje_s_doporucenim=1,
            ratings_nevyhovuje=0,
            ratings_netyka_se=2,
            ratings_nehodnoceno=8,
        )
        self.assertEqual(6, rating_category_sum(stats))
        self.assertEqual(6, stats.control_points_checked)
        self.assertNotEqual(
            stats.control_points_checked + stats.ratings_nehodnoceno,
            rating_category_sum(stats),
        )

    def test_mismatch_logs_warning_and_keeps_values(self) -> None:
        stats = _stats(
            control_points_checked=400,
            ratings_vyhovuje=383,
            ratings_vyhovuje_s_doporucenim=5,
            ratings_nevyhovuje=0,
            ratings_netyka_se=97,
        )
        self.assertEqual(485, rating_category_sum(stats))
        with self.assertLogs(
            "core.shared.sluzby.control_report_overview",
            level="WARNING",
        ) as captured:
            lines = format_result_overview_rating_lines(
                stats,
                scope_label="Kontrolovaných oblastí",
                scope_count=3,
                points_label="Kontrolních bodů",
            )
        self.assertEqual("Kontrolních bodů: 400", lines[1])
        self.assertEqual("Vyhovuje: 383", lines[2])
        self.assertEqual("Nelze posoudit: 97", lines[5])
        joined = "\n".join(captured.output)
        self.assertIn("control_points_checked=400", joined)
        self.assertIn("vyhovuje=383", joined)
        self.assertIn("vyhovuje_s_doporucenim=5", joined)
        self.assertIn("nevyhovuje=0", joined)
        self.assertIn("nelze_posoudit=97", joined)
        self.assertIn("soucet_kategorii=485", joined)


if __name__ == "__main__":
    unittest.main()
