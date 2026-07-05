import unittest

from moduly.kontroly.sluzby.monthly_control_service import (
    MonthCell,
    MonthlyControlService,
    ThpYearRow,
)


class MonthlyControlServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = MonthlyControlService()

    def _sample_rows(self) -> list[ThpYearRow]:
        return [
            ThpYearRow(
                thp_worker_id=1,
                thp_worker_name="A",
                months={
                    1: MonthCell("ok"),
                    2: MonthCell("defect"),
                    3: MonthCell("excused"),
                    4: MonthCell("none"),
                },
            ),
            ThpYearRow(
                thp_worker_id=2,
                thp_worker_name="B",
                months={
                    1: MonthCell("none"),
                    2: MonthCell("excused"),
                    3: MonthCell("ok"),
                    4: MonthCell("none"),
                },
            ),
        ]

    def test_status_cycle_contains_excused(self) -> None:
        self.assertEqual(
            self.service.STATUS_CYCLE,
            ("none", "ok", "defect", "excused"),
        )

    def test_compute_summary_counts_excused_separately(self) -> None:
        summary = self.service.compute_summary(self._sample_rows())

        self.assertEqual(summary.thp_count, 2)
        self.assertEqual(summary.done_count, 3)
        self.assertEqual(summary.defect_count, 1)
        self.assertEqual(summary.excused_count, 2)
        self.assertEqual(summary.none_count, 19)

    def test_compute_monthly_summary_counts_excused(self) -> None:
        monthly = self.service.compute_monthly_summary(self._sample_rows())

        self.assertEqual(monthly.done_by_month[0], 1)
        self.assertEqual(monthly.defect_by_month[1], 1)
        self.assertEqual(monthly.excused_by_month[0], 0)
        self.assertEqual(monthly.excused_by_month[1], 1)
        self.assertEqual(monthly.excused_by_month[2], 1)
        self.assertEqual(monthly.none_by_month[0], 1)


if __name__ == "__main__":
    unittest.main()
