import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime
from pathlib import Path

from badminton_availability.config import TIMEZONE
from badminton_availability.render import build_calendar, generate_html


class RenderTests(unittest.TestCase):
    def test_generate_html_renders_slots_and_last_updated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            data_file = tmpdir / "availability.json"
            today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
            html_file = tmpdir / "index.html"
            data_file.write_text(
                json.dumps(
                    {
                        "availability": {
                            today: ["7am - 8am"],
                        },
                        "last_updated": "2026-05-10 12:00:00",
                    }
                ),
                encoding="utf-8",
            )

            with redirect_stdout(io.StringIO()):
                generate_html(data_file=data_file, html_file=html_file)

            html = html_file.read_text(encoding="utf-8")
            self.assertIn("WoodPEC Court #3 Availability", html)
            self.assertIn("Updated 2026-05-10 12:00:00", html)
            self.assertIn('<span class="t">7am</span><span class="dash"> - </span><span class="t">8am</span>', html)


class CalendarTests(unittest.TestCase):
    def test_two_weeks_cross_month_boundary(self):
        # Saturday, October 31, 2026
        cal = build_calendar({"2026-11-01": ["8am - 8pm"]}, today=date(2026, 10, 31), days_shown=14)
        active = [d["iso"] for d in cal["days"] if d["in_range"]]

        self.assertEqual(len(active), 14)
        self.assertEqual(active[0], "2026-10-31")
        self.assertEqual(active[-1], "2026-11-13")
        # Grid is whole Sunday-Saturday weeks.
        self.assertEqual(cal["days"][0]["iso"], "2026-10-25")
        self.assertEqual(cal["days"][-1]["iso"], "2026-11-14")
        self.assertEqual(len(cal["days"]) % 7, 0)

        nov1 = next(d for d in cal["days"] if d["iso"] == "2026-11-01")
        self.assertEqual(nov1["label"], "Nov 1")
        self.assertEqual(nov1["slots"], [("8am", "8pm")])

    def test_day_states(self):
        cal = build_calendar(
            {"2026-11-03": ["7am - 4:30pm", "9:30pm - 11pm"], "2026-11-04": []},
            today=date(2026, 11, 3),
        )
        by_iso = {d["iso"]: d for d in cal["days"]}

        self.assertEqual(by_iso["2026-11-03"]["slots"], [("7am", "4:30pm"), ("9:30pm", "11pm")])
        self.assertTrue(by_iso["2026-11-03"]["is_today"])
        self.assertEqual(by_iso["2026-11-04"]["slots"], [])
        self.assertFalse(by_iso["2026-11-01"]["in_range"])

    def test_default_shows_four_weeks(self):
        cal = build_calendar({}, today=date(2026, 11, 3))
        active = [d["iso"] for d in cal["days"] if d["in_range"]]
        self.assertEqual(len(active), 28)
        self.assertEqual(active[-1], "2026-11-30")
        self.assertEqual(cal["weeks_shown"], 4)


if __name__ == "__main__":
    unittest.main()
