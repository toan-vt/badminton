import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime
from pathlib import Path

from badminton_availability.process import (
    fetch_events,
    get_available_times,
    load_checkpoint_events,
    normalize_event_times,
    parse_schedule_data,
    parse_time,
    save_availability_to_file,
)


def call_silently(func, *args, **kwargs):
    with redirect_stdout(io.StringIO()):
        return func(*args, **kwargs)


class ParseTimeTests(unittest.TestCase):
    def test_parse_time_supports_common_formats(self):
        self.assertEqual(parse_time("7pm").strftime("%H:%M"), "19:00")
        self.assertEqual(parse_time("10:30am").strftime("%H:%M"), "10:30")
        self.assertEqual(parse_time("14:30").strftime("%H:%M"), "14:30")

    def test_parse_time_infers_missing_meridiem_from_context(self):
        self.assertEqual(parse_time("7", "9pm").strftime("%H:%M"), "19:00")
        self.assertEqual(parse_time("7", "9am").strftime("%H:%M"), "07:00")

    def test_parse_time_rejects_unknown_format(self):
        with self.assertRaises(ValueError):
            parse_time("not a time")


class ScheduleParsingTests(unittest.TestCase):
    def test_parse_schedule_data_handles_single_day_event(self):
        events = parse_schedule_data(
            [
                "Monday, May 11, 2026, 7pm - 9pm Woodruff PE Center Court #3",
            ]
        )

        self.assertEqual(
            events,
            [
                {
                    "date": "Monday, May 11, 2026",
                    "start_time": "7pm",
                    "end_time": "9pm",
                    "location": "Woodruff PE Center Court #3",
                }
            ],
        )

    def test_parse_schedule_data_extracts_time_from_location_when_missing(self):
        events = parse_schedule_data(
            [
                "Monday, May 11, 2026 7pm - 9pm Woodruff PE Center Court #3",
            ]
        )

        self.assertEqual(events[0]["start_time"], "7pm")
        self.assertEqual(events[0]["end_time"], "9pm")
        self.assertEqual(events[0]["location"], "Woodruff PE Center Court #3")

    def test_parse_schedule_data_expands_multi_day_event(self):
        events = parse_schedule_data(
            [
                "Monday, May 11, 7pm - Wednesday, May 13, 2026, 9am Woodruff PE Center Court #3",
            ]
        )

        self.assertEqual(
            events,
            [
                {
                    "date": "Monday, May 11, 2026",
                    "start_time": "7pm",
                    "end_time": "11:59pm",
                    "location": "Woodruff PE Center Court #3",
                },
                {
                    "date": "Tuesday, May 12, 2026",
                    "start_time": "12am",
                    "end_time": "11:59pm",
                    "location": "Woodruff PE Center Court #3",
                },
                {
                    "date": "Wednesday, May 13, 2026",
                    "start_time": "12am",
                    "end_time": "9am",
                    "location": "Woodruff PE Center Court #3",
                },
            ],
        )


class AvailabilityTests(unittest.TestCase):
    def test_fetch_events_filters_by_date_and_court(self):
        events = [
            {
                "date": "Monday, May 11, 2026",
                "start_time": "7pm",
                "end_time": "9pm",
                "location": "Woodruff PE Center Court #3",
            },
            {
                "date": "Monday, May 11, 2026",
                "start_time": "5pm",
                "end_time": "6pm",
                "location": "Woodruff PE Center Court #2",
            },
            {
                "date": "Tuesday, May 12, 2026",
                "start_time": "7pm",
                "end_time": "9pm",
                "location": "Woodruff PE Center Court #3",
            },
        ]

        result = call_silently(fetch_events, date(2026, 5, 11), events, court_number=3)

        self.assertEqual(result, [("7pm", "9pm")])

    def test_get_available_times_returns_open_to_close_when_no_events(self):
        available = call_silently(get_available_times, date(2026, 5, 11), [], court_number=3)

        self.assertEqual(
            [(start.strftime("%H:%M"), end.strftime("%H:%M")) for start, end in available],
            [("07:00", "23:00")],
        )

    def test_get_available_times_excludes_overlapping_events(self):
        events = [
            {
                "date": "Monday, May 11, 2026",
                "start_time": "8am",
                "end_time": "10am",
                "location": "Woodruff PE Center Court #3",
            },
            {
                "date": "Monday, May 11, 2026",
                "start_time": "9:30am",
                "end_time": "11am",
                "location": "Woodruff PE Center Court #3",
            },
            {
                "date": "Monday, May 11, 2026",
                "start_time": "1pm",
                "end_time": "2pm",
                "location": "Woodruff PE Center Court #3",
            },
        ]

        available = call_silently(get_available_times, date(2026, 5, 11), events, court_number=3)

        self.assertEqual(
            [(start.strftime("%H:%M"), end.strftime("%H:%M")) for start, end in available],
            [("07:00", "08:00"), ("11:00", "13:00"), ("14:00", "23:00")],
        )

    def test_save_availability_to_file_writes_json(self):
        events = [
            {
                "date": "Monday, May 11, 2026",
                "start_time": "8am",
                "end_time": "10am",
                "location": "Woodruff PE Center Court #3",
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "data" / "availability.json"
            result = call_silently(
                save_availability_to_file,
                [datetime(2026, 5, 11)],
                events,
                filename=output_file,
            )

            self.assertTrue(output_file.exists())
            saved = json.loads(output_file.read_text(encoding="utf-8"))
            self.assertEqual(saved, result)
            self.assertEqual(saved["availability"]["2026-05-11"], ["7am - 8am", "10am - 11pm"])


class CheckpointTests(unittest.TestCase):
    def test_load_checkpoint_events_combines_batches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_dir = Path(tmpdir)
            (checkpoint_dir / "batch_0_checkpoint.json").write_text(
                json.dumps([{"event_id": "a"}]),
                encoding="utf-8",
            )
            (checkpoint_dir / "batch_1_checkpoint.json").write_text(
                json.dumps([{"event_id": "b"}]),
                encoding="utf-8",
            )

            self.assertEqual(
                load_checkpoint_events(checkpoint_dir=checkpoint_dir, num_batches=2),
                [{"event_id": "a"}, {"event_id": "b"}],
            )

    def test_normalize_event_times_fills_missing_values(self):
        events = [
            {"start_time": "7", "end_time": "9pm"},
            {"start_time": "8", "end_time": "10am"},
            {"start_time": "", "end_time": ""},
        ]

        self.assertEqual(
            normalize_event_times(events),
            [
                {"start_time": "7pm", "end_time": "9pm"},
                {"start_time": "8am", "end_time": "10am"},
                {"start_time": "12:00am", "end_time": "11:59pm"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
