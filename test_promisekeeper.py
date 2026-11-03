"""Run with:  python -m unittest -v   (no dependencies)"""
import unittest
from datetime import date, datetime

from promisekeeper import extract, parse_due, to_ics

TUE = date(2026, 11, 3)  # a Tuesday


class TestDates(unittest.TestCase):
    def test_relative(self):
        self.assertEqual(parse_due("do it tomorrow", TUE), date(2026, 11, 4))
        self.assertEqual(parse_due("by friday", TUE), date(2026, 11, 6))
        self.assertEqual(parse_due("in 2 weeks", TUE), date(2026, 11, 17))
        self.assertEqual(parse_due("next week", TUE), date(2026, 11, 9))

    def test_next_weekday_skips_this_week(self):
        self.assertEqual(parse_due("next friday", TUE), date(2026, 11, 13))
        self.assertEqual(parse_due("next monday", TUE), date(2026, 11, 9))

    def test_calendar_dates(self):
        self.assertEqual(parse_due("on Dec 1st", TUE), date(2026, 12, 1))
        self.assertEqual(parse_due("by 5 jan", TUE), date(2027, 1, 5))  # rolls to next year
        self.assertEqual(parse_due("2026-12-25", TUE), date(2026, 12, 25))
        self.assertEqual(parse_due("before the 20th", TUE), date(2026, 11, 20))

    def test_times(self):
        self.assertEqual(parse_due("tomorrow at 9am", TUE), datetime(2026, 11, 4, 9))
        self.assertEqual(parse_due("friday 5:30pm", TUE), datetime(2026, 11, 6, 17, 30))
        self.assertEqual(parse_due("today by noon", TUE), datetime(2026, 11, 3, 12))

    def test_no_date(self):
        self.assertIsNone(parse_due("sometime, whenever", TUE))


class TestExtraction(unittest.TestCase):
    def test_commitment_binds_speaker(self):
        (p,) = extract("Alex: I'll send the report tomorrow", me="Alex", today=TUE)
        self.assertEqual((p.direction, p.who), ("i_owe", "Alex"))
        (p,) = extract("Sam: I'll send the report tomorrow", me="Alex", today=TUE)
        self.assertEqual((p.direction, p.who), ("owed_to_me", "Sam"))

    def test_request_binds_other_person(self):
        (p,) = extract("Sam: Can you call mum today?", me="Alex", today=TUE)
        self.assertEqual(p.direction, "i_owe")
        (p,) = extract("Alex: Can you call mum today?\nSam: ok", me="Alex", today=TUE)
        self.assertEqual(p.direction, "owed_to_me")

    def test_whatsapp_prefix_and_plain_text(self):
        (p,) = extract("12/03/2026, 10:15 - Sam: please sign the form by friday", me="Alex", today=TUE)
        self.assertEqual(p.due, "2026-11-06")
        (p,) = extract("I need to book flights next week.", today=TUE)
        self.assertEqual(p.direction, "i_owe")

    def test_ignores_chatter_and_dedupes(self):
        text = "Lunch was great!\nI'll call you tomorrow.\nI'll call you tomorrow."
        self.assertEqual(len(extract(text, today=TUE)), 1)

    def test_sorted_by_due_and_priority(self):
        ps = extract("I'll do A on friday.\nI'll do B tomorrow asap.\nI'll do C someday.", today=TUE)
        self.assertIn("tomorrow", ps[0].task)
        self.assertEqual(ps[0].priority, "HIGH")
        self.assertIsNone(ps[-1].due)


class TestICS(unittest.TestCase):
    def test_valid_calendar(self):
        ics = to_ics(extract("I'll pay rent tomorrow at 9am, ok?", today=TUE))
        self.assertTrue(ics.startswith("BEGIN:VCALENDAR"))
        self.assertIn("DTSTART:20261104T090000", ics)
        self.assertTrue(ics.strip().endswith("END:VCALENDAR"))


if __name__ == "__main__":
    unittest.main()
