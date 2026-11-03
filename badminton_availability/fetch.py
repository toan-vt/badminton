"""Fetch WoodPEC calendar events from the public 25Live (Trumba) JSON feed.

The hosted calendar page no longer renders events in a scrapable iframe, but the
same data is published as JSON at ``<SOURCE_URL>.json``. Each request returns at
most ``FEED_PAGE_SIZE`` events starting at ``startdate``, so we page forward
until the look-ahead window is covered.

Events are written in the same shape the old scraper produced (title, url,
event_id, description) where ``description`` is
``"<Weekday>, <Month> <D>, <YYYY>, <start> - <end> <location>"`` so that
``process.py`` can consume the checkpoints unchanged.
"""

import csv
import html
import json
import os
import time
from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from badminton_availability.config import (
    CHECKPOINT_DIR,
    DAYS_AHEAD,
    EVENT_LINKS_FILE,
    EVENT_LINKS_NO_DESCRIPTIONS_FILE,
    FEED_PAGE_SIZE,
    FEED_URL,
    NUM_WORKERS,
    TIMEZONE,
)

USER_AGENT = "Mozilla/5.0 (compatible; woodpec-availability/1.0)"
MAX_PAGES = 20


def create_session_with_retries():
    """Create a requests session with automatic retries."""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return session


def fetch_feed_page(session, start_date, page_size=FEED_PAGE_SIZE):
    """Fetch one page of raw feed events starting on start_date (a date)."""
    params = {"startdate": start_date.strftime("%Y%m%d"), "events": page_size}
    response = session.get(FEED_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list):
        raise ValueError(f"Unexpected feed payload type: {type(data).__name__}")
    return data


def fetch_raw_events(start_date, end_date, session=None, page_size=FEED_PAGE_SIZE):
    """Fetch all raw feed events from start_date through end_date (inclusive)."""
    session = session or create_session_with_retries()
    events_by_id = {}
    page_start = start_date

    for _ in range(MAX_PAGES):
        page = fetch_feed_page(session, page_start, page_size)
        print(f"Fetched {len(page)} events starting {page_start.isoformat()}")
        for event in page:
            events_by_id.setdefault(event["eventID"], event)

        if len(page) < page_size:
            break

        # The page was full: continue from the last day we saw. Events from that
        # day are re-fetched and deduplicated by eventID.
        last_day = _parse_feed_datetime(page[-1]["startDateTime"]).date()
        if last_day > end_date:
            break
        if last_day <= page_start:
            # A single day with more events than a page; step forward to avoid looping.
            print(f"Warning: page starting {page_start} was full within one day; some events may be missing")
            last_day = page_start + timedelta(days=1)
        page_start = last_day
    else:
        print(f"Warning: stopped after {MAX_PAGES} pages")

    events = [
        e for e in events_by_id.values() if _parse_feed_datetime(e["startDateTime"]).date() <= end_date
    ]
    events.sort(key=lambda e: e["startDateTime"])
    return events


def _parse_feed_datetime(value):
    return datetime.strptime(value[:19], "%Y-%m-%dT%H:%M:%S")


def _format_date(dt):
    return f"{dt.strftime('%A, %B')} {dt.day}, {dt.year}"


def _format_clock(dt):
    hour = dt.hour % 12 or 12
    suffix = "am" if dt.hour < 12 else "pm"
    if dt.minute:
        return f"{hour}:{dt.minute:02d}{suffix}"
    return f"{hour}{suffix}"


def build_description(event):
    """Build a description string in the format process.parse_schedule_data expects."""
    start = _parse_feed_datetime(event["startDateTime"])
    end = _parse_feed_datetime(event.get("endDateTime") or event["startDateTime"])
    location = html.unescape(event.get("location") or "").strip()

    if event.get("allDay"):
        # No time component -> parser treats it as 12am - 11:59pm.
        last_day = end - timedelta(days=1) if end > start else start
        if last_day.date() <= start.date():
            return f"{_format_date(start)} {location}"
        return f"{start.strftime('%A, %B')} {start.day}, 12am - {_format_date(last_day)}, 11:59pm {location}"

    # An event ending exactly at midnight belongs to the previous day.
    if end > start and end.time() == datetime.min.time():
        end = end - timedelta(minutes=1)

    if end.date() <= start.date():
        return f"{_format_date(start)}, {_format_clock(start)} - {_format_clock(end)} {location}"

    return (
        f"{start.strftime('%A, %B')} {start.day}, {_format_clock(start)} - "
        f"{_format_date(end)}, {_format_clock(end)} {location}"
    )


def to_event_record(event):
    """Convert a raw feed event into the record format stored in checkpoints/CSVs."""
    return {
        "title": html.unescape(event.get("title") or ""),
        "url": event.get("permaLinkUrl") or "",
        "event_id": str(event["eventID"]),
        "description": build_description(event),
    }


def fetch_event_records(start_date=None, days_ahead=DAYS_AHEAD, session=None):
    """Fetch non-canceled events and return them as checkpoint records."""
    start_date = start_date or datetime.now(TIMEZONE).date()
    end_date = start_date + timedelta(days=days_ahead)
    raw_events = fetch_raw_events(start_date, end_date, session=session)
    return [to_event_record(e) for e in raw_events if not e.get("canceled")]


def split_into_batches(items, num_batches):
    """Split items into num_batches as evenly as possible."""
    avg_size = len(items) // num_batches
    remainder = len(items) % num_batches

    result = []
    start = 0
    for i in range(num_batches):
        end = start + avg_size + (1 if i < remainder else 0)
        result.append(items[start:end])
        start = end
    return result


def write_checkpoints(records, num_batches=NUM_WORKERS, checkpoint_dir=CHECKPOINT_DIR):
    """Write records to the batch checkpoint files read by process.py."""
    os.makedirs(checkpoint_dir, exist_ok=True)
    for i, batch in enumerate(split_into_batches(records, num_batches)):
        checkpoint_file = os.path.join(checkpoint_dir, f"batch_{i}_checkpoint.json")
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(batch, f, ensure_ascii=False, indent=2)


def save_to_csv(records, filename, fieldnames=("title", "url", "event_id", "description")):
    """Save event records to a CSV file."""
    if not records:
        print("No event links to save.")
        return

    with open(filename, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow(record)

    print(f"Saved {len(records)} event links to {filename}")


def main():
    start_time = time.time()
    records = fetch_event_records()

    if not records:
        # Fail loudly so CI doesn't silently publish stale/empty data.
        raise SystemExit("No events were fetched from the calendar feed.")

    save_to_csv(records, EVENT_LINKS_NO_DESCRIPTIONS_FILE, fieldnames=("title", "url", "event_id"))
    write_checkpoints(records)
    save_to_csv(records, EVENT_LINKS_FILE)

    elapsed_time = time.time() - start_time
    print(f"\nFetched {len(records)} events in {elapsed_time:.2f} seconds")
