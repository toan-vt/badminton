import io
import unittest
from contextlib import redirect_stdout
from datetime import date

from badminton_availability.fetch import build_description, fetch_raw_events, to_event_record
from badminton_availability.process import parse_schedule_data


def feed_event(event_id, start, end, location="Woodruff PE Center Court #3", **extra):
    event = {
        "eventID": event_id,
        "title": "CS Badminton",
        "location": location,
        "startDateTime": start,
        "endDateTime": end,
        "allDay": False,
        "canceled": False,
        "permaLinkUrl": f"https://example.test/?eventid={event_id}",
    }
    event.update(extra)
    return event


class BuildDescriptionTests(unittest.TestCase):
    def test_single_day_event(self):
        desc = build_description(feed_event(1, "2026-11-03T16:30:00", "2026-11-03T19:00:00"))
        self.assertEqual(desc, "Tuesday, November 3, 2026, 4:30pm - 7pm Woodruff PE Center Court #3")
        parsed = parse_schedule_data([desc])
        self.assertEqual(
            parsed,
            [
                {
                    "date": "Tuesday, November 3, 2026",
                    "start_time": "4:30pm",
                    "end_time": "7pm",
                    "location": "Woodruff PE Center Court #3",
                }
            ],
        )

    def test_event_ending_at_midnight_stays_on_same_day(self):
        desc = build_description(feed_event(1, "2026-11-03T20:00:00", "2026-11-04T00:00:00"))
        self.assertEqual(desc, "Tuesday, November 3, 2026, 8pm - 11:59pm Woodruff PE Center Court #3")

    def test_multi_day_event_round_trips_through_parser(self):
        desc = build_description(feed_event(1, "2026-11-06T18:00:00", "2026-11-08T09:00:00"))
        parsed = parse_schedule_data([desc])
        self.assertEqual(
            [(e["date"], e["start_time"], e["end_time"]) for e in parsed],
            [
                ("Friday, November 06, 2026", "6pm", "11:59pm"),
                ("Saturday, November 07, 2026", "12am", "11:59pm"),
                ("Sunday, November 08, 2026", "12am", "9am"),
            ],
        )
        self.assertTrue(all(e["location"] == "Woodruff PE Center Court #3" for e in parsed))

    def test_all_day_event_blocks_whole_day(self):
        desc = build_description(
            feed_event(1, "2026-11-03T00:00:00", "2026-11-04T00:00:00", allDay=True)
        )
        parsed = parse_schedule_data([desc])
        self.assertEqual(
            [(e["date"], e["start_time"], e["end_time"]) for e in parsed],
            [("Tuesday, November 3, 2026", "12am", "11:59pm")],
        )

    def test_record_unescapes_html_entities(self):
        record = to_event_record(
            feed_event(7, "2026-11-04T19:00:00", "2026-11-04T22:00:00", title="CS Men&#39;s Volleyball")
        )
        self.assertEqual(record["title"], "CS Men's Volleyball")
        self.assertEqual(record["event_id"], "7")


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class FakeSession:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params["startdate"])
        return FakeResponse(self.pages[params["startdate"]])


class FetchRawEventsTests(unittest.TestCase):
    def test_pages_forward_and_dedupes(self):
        pages = {
            "20261103": [
                feed_event(1, "2026-11-03T08:00:00", "2026-11-03T09:00:00"),
                feed_event(2, "2026-11-05T08:00:00", "2026-11-05T09:00:00"),
            ],
            "20261105": [
                feed_event(2, "2026-11-05T08:00:00", "2026-11-05T09:00:00"),
                feed_event(3, "2026-11-06T08:00:00", "2026-11-06T09:00:00"),
                feed_event(4, "2026-11-30T08:00:00", "2026-11-30T09:00:00"),
            ],
        }
        session = FakeSession(pages)
        with redirect_stdout(io.StringIO()):
            events = fetch_raw_events(date(2026, 11, 3), date(2026, 11, 10), session=session, page_size=2)
        self.assertEqual([e["eventID"] for e in events], [1, 2, 3])
        self.assertEqual(session.calls, ["20261103", "20261105"])


if __name__ == "__main__":
    unittest.main()
