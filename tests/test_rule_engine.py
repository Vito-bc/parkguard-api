from datetime import datetime
from zoneinfo import ZoneInfo
import unittest

from rule_engine import evaluate_recurring_window, parse_days_spec


NY = ZoneInfo("America/New_York")


class ParseDaysSpecTests(unittest.TestCase):
    def test_mon_fri(self) -> None:
        self.assertEqual(parse_days_spec("Mon-Fri"), {0, 1, 2, 3, 4})

    def test_weekends(self) -> None:
        self.assertEqual(parse_days_spec("weekends"), {5, 6})

    def test_list(self) -> None:
        self.assertEqual(parse_days_spec("Mon, Wed, Fri"), {0, 2, 4})


class EvaluateRecurringWindowTests(unittest.TestCase):
    def test_before_window_same_day(self) -> None:
        now = datetime(2026, 2, 23, 5, 30, tzinfo=NY)  # Monday
        result = evaluate_recurring_window(
            now=now,
            days_spec="Mon-Fri",
            start_time="06:00",
            end_time="09:00",
        )
        self.assertFalse(result.active_now)
        self.assertEqual(result.countdown_mode, "until_start")
        self.assertEqual(result.next_start.hour, 6)
        self.assertEqual(result.next_start.minute, 0)

    def test_during_window(self) -> None:
        now = datetime(2026, 2, 23, 7, 15, tzinfo=NY)  # Monday
        result = evaluate_recurring_window(
            now=now,
            days_spec="Mon-Fri",
            start_time="06:00",
            end_time="09:00",
        )
        self.assertTrue(result.active_now)
        self.assertEqual(result.countdown_mode, "until_end")
        self.assertIsNotNone(result.current_end)
        self.assertEqual(result.current_end.hour, 9)

    def test_after_window_goes_to_next_weekday(self) -> None:
        now = datetime(2026, 2, 23, 10, 0, tzinfo=NY)  # Monday
        result = evaluate_recurring_window(
            now=now,
            days_spec="Mon-Fri",
            start_time="06:00",
            end_time="09:00",
        )
        self.assertFalse(result.active_now)
        self.assertEqual(result.next_start.date().day, 24)  # Tuesday
        self.assertEqual(result.next_start.hour, 6)

    def test_weekend_skips_to_monday(self) -> None:
        now = datetime(2026, 2, 22, 12, 0, tzinfo=NY)  # Sunday
        result = evaluate_recurring_window(
            now=now,
            days_spec="Mon-Fri",
            start_time="06:00",
            end_time="09:00",
        )
        self.assertFalse(result.active_now)
        self.assertEqual(result.next_start.weekday(), 0)
        self.assertEqual(result.next_start.hour, 6)


if __name__ == "__main__":
    unittest.main()
