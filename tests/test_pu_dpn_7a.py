"""PU-DPN-7a – termín mimořádné prohlídky v 5 českých pracovních dnech."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from core.shared.working_days import (
    add_czech_workdays,
    easter_sunday,
    is_czech_public_holiday,
    is_czech_working_day,
)
from moduly.kniha_urazu.sluzby.accident_dpn_care import exam_deadline_from_return_date


class PuDpn7aTestCase(unittest.TestCase):
    def test_easter_and_public_holidays_are_offline(self) -> None:
        self.assertEqual(easter_sunday(2024), date(2024, 3, 31))
        self.assertEqual(easter_sunday(2025), date(2025, 4, 20))
        self.assertEqual(easter_sunday(2026), date(2026, 4, 5))
        self.assertEqual(easter_sunday(2027), date(2027, 3, 28))
        self.assertTrue(is_czech_public_holiday(date(2026, 1, 1)))
        self.assertTrue(is_czech_public_holiday(date(2026, 5, 1)))
        self.assertTrue(is_czech_public_holiday(date(2026, 5, 8)))
        self.assertTrue(is_czech_public_holiday(date(2026, 10, 28)))
        self.assertTrue(is_czech_public_holiday(date(2026, 4, 3)))
        self.assertTrue(is_czech_public_holiday(date(2026, 4, 6)))
        self.assertFalse(is_czech_public_holiday(date(2026, 4, 20)))
        self.assertFalse(is_czech_working_day(date(2026, 4, 4)))
        self.assertFalse(is_czech_working_day(date(2026, 5, 1)))
        self.assertTrue(is_czech_working_day(date(2026, 4, 20)))

    def test_plain_week_without_holiday(self) -> None:
        # Návrat v pondělí 20. 4. 2026 → Út–Pá + Po = 27. 4.
        self.assertEqual(exam_deadline_from_return_date(date(2026, 4, 20)), "2026-04-27")
        self.assertEqual(add_czech_workdays(date(2026, 4, 20), 5), date(2026, 4, 27))
        self.assertTrue(is_czech_working_day(date(2026, 4, 27)))

    def test_weekend_inside_period(self) -> None:
        # Návrat ve čtvrtek 11. 6. 2026: Pá, (So, Ne), Po–Čt.
        self.assertEqual(exam_deadline_from_return_date(date(2026, 6, 11)), "2026-06-18")
        # Návrat v pátek: víkend hned na začátku lhůty.
        self.assertEqual(exam_deadline_from_return_date(date(2026, 6, 12)), "2026-06-19")

    def test_state_holiday_inside_period(self) -> None:
        # 1. 5. 2026 pátek (Svátek práce) uvnitř lhůty od úterý 28. 4.
        self.assertEqual(exam_deadline_from_return_date(date(2026, 4, 28)), "2026-05-06")
        # 28. 10. 2026 středa (Den vzniku ČSR) uvnitř lhůty od úterý 27. 10.
        self.assertEqual(exam_deadline_from_return_date(date(2026, 10, 27)), "2026-11-04")
        # 6. 7. 2026 pondělí (upálení M. J. Husa) po víkendu s 5. 7.
        self.assertEqual(exam_deadline_from_return_date(date(2026, 7, 2)), "2026-07-10")

    def test_christmas(self) -> None:
        # Návrat v pondělí 21. 12. 2026: 24.–26. 12. se nepočítají.
        self.assertTrue(is_czech_public_holiday(date(2026, 12, 24)))
        self.assertTrue(is_czech_public_holiday(date(2026, 12, 25)))
        self.assertTrue(is_czech_public_holiday(date(2026, 12, 26)))
        self.assertEqual(exam_deadline_from_return_date(date(2026, 12, 21)), "2026-12-30")
        # Návrat těsně před svátky – 5. pracovní den až po nich.
        self.assertEqual(exam_deadline_from_return_date(date(2026, 12, 23)), "2027-01-04")

    def test_good_friday_and_easter_monday(self) -> None:
        self.assertEqual(easter_sunday(2026) - timedelta(days=2), date(2026, 4, 3))
        self.assertEqual(easter_sunday(2026) + timedelta(days=1), date(2026, 4, 6))
        # Návrat ve čtvrtek 2. 4. 2026: Velký pátek i Velikonoční pondělí ve lhůtě.
        self.assertEqual(exam_deadline_from_return_date(date(2026, 4, 2)), "2026-04-13")
        # Návrat ve středu 1. 4. 2026 – pátý pracovní den po Velikonocích.
        self.assertEqual(exam_deadline_from_return_date(date(2026, 4, 1)), "2026-04-10")
        # 2025: Velikonoční pondělí 21. 4., Velký pátek 18. 4.
        self.assertEqual(exam_deadline_from_return_date(date(2025, 4, 17)), "2025-04-28")

    def test_year_transition(self) -> None:
        # 1. 1. 2026 čtvrtek – Nový rok / Den obnovy samostatného českého státu.
        self.assertTrue(is_czech_public_holiday(date(2026, 1, 1)))
        self.assertEqual(exam_deadline_from_return_date(date(2025, 12, 29)), "2026-01-06")
        self.assertEqual(exam_deadline_from_return_date(date(2025, 12, 31)), "2026-01-08")
        self.assertTrue(is_czech_working_day(date(2026, 1, 6)))
        self.assertTrue(is_czech_working_day(date(2026, 1, 8)))

    def test_deadline_is_always_a_working_day(self) -> None:
        self.assertIsNone(exam_deadline_from_return_date(None))
        for start in (
            date(2026, 4, 20),
            date(2026, 4, 2),
            date(2026, 12, 23),
            date(2025, 12, 31),
            date(2026, 4, 28),
        ):
            deadline = date.fromisoformat(exam_deadline_from_return_date(start))
            self.assertTrue(is_czech_working_day(deadline), deadline)
            counted = 0
            cursor = start
            while cursor < deadline:
                cursor += timedelta(days=1)
                if is_czech_working_day(cursor):
                    counted += 1
            self.assertEqual(counted, 5)


if __name__ == "__main__":
    unittest.main()
