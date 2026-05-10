import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

from badminton_availability.config import (
    AVAILABILITY_FILE,
    CHECKPOINT_DIR,
    COURT_NUMBER,
    TIMEZONE,
    get_operating_hours,
)


def parse_time(time_str, context_time_str=None):
    """
    Parse time strings with flexible formats.

    If a bare number is provided without am/pm, infer from context_time_str when
    possible.
    """
    time_str = time_str.lower().strip()

    if re.match(r"^\d+$", time_str) and context_time_str:
        if "pm" in context_time_str.lower():
            time_str += "pm"
        elif "am" in context_time_str.lower():
            time_str += "am"

    patterns = [
        "%I%p",
        "%I:%M%p",
        "%H:%M",
    ]

    for pattern in patterns:
        try:
            return datetime.strptime(time_str, pattern)
        except ValueError:
            continue

    raise ValueError(f"Time format not recognized: {time_str}")


def parse_schedule_data(events_list: List[str]) -> List[Dict]:
    """Parse schedule data from event description strings."""
    parsed_events = []
    for event in events_list:
        if not event.strip():
            continue

        range_pattern = (
            r"([A-Za-z]+, [A-Za-z]+ \d+), (\d+(?::\d+)?(?:am|pm)?) - "
            r"([A-Za-z]+, [A-Za-z]+ \d+, \d{4}), (\d+(?::\d+)?(?:am|pm)?)(.+)"
        )
        match_range = re.match(range_pattern, event)
        if match_range:
            start_day_str, start_time, end_day_str, end_time, location = match_range.groups()
            start_date = datetime.strptime(f"{start_day_str}, {end_day_str[-4:]}", "%A, %B %d, %Y")
            end_date = datetime.strptime(end_day_str, "%A, %B %d, %Y")
            location = location.strip()

            current_date = start_date
            while current_date <= end_date:
                if current_date == start_date:
                    st, et = start_time, "11:59pm"
                elif current_date == end_date:
                    st, et = "12am", end_time
                else:
                    st, et = "12am", "11:59pm"

                parsed_events.append(
                    {
                        "date": current_date.strftime("%A, %B %d, %Y"),
                        "start_time": st,
                        "end_time": et,
                        "location": location,
                    }
                )
                current_date += timedelta(days=1)
            continue

        single_day_pattern = (
            r"([A-Za-z]+, [A-Za-z]+ \d+, \d{4})(?:, (\d+(?::\d+)?(?:am|pm)?) - "
            r"(\d+(?::\d+)?(?:am|pm)?))?(.+)"
        )
        match_single = re.match(single_day_pattern, event)
        if match_single:
            date_str, start_time, end_time, location = match_single.groups()
            location = location.strip()

            time_match = re.match(r",?\s*(\d+(?::\d+)?(?:am|pm)?) - (\d+(?::\d+)?(?:am|pm)?)(.*)", location)
            if time_match and not start_time:
                start_time, end_time, location = time_match.groups()
                location = location.strip()

            if not start_time:
                start_time = "12am"
            if not end_time:
                end_time = "11:59pm"

            parsed_events.append(
                {
                    "date": date_str.strip(),
                    "start_time": start_time,
                    "end_time": end_time,
                    "location": location,
                }
            )
        else:
            print(f"Failed to parse event: {event}")

    return parsed_events


def fetch_events(date, events_data, court_number=COURT_NUMBER):
    """Fetch events for the specified date and court number."""
    date_str = date.strftime("%A, %B %d, %Y")
    print(f"Looking for events on {date_str} for Court #{court_number}")

    matching_events = []
    for event in events_data:
        if event["date"] == date_str:
            print(f"Found event on {date_str}: {event}")
            court_pattern = f"Court #{court_number}"
            if court_pattern in event["location"]:
                print(f"  - Court #{court_number} found in location")
                matching_events.append((event["start_time"], event["end_time"]))

    return matching_events


def normalize_date_format(date_str):
    """Ensure date strings have consistent format."""
    try:
        date_obj = datetime.strptime(date_str, "%A, %B %d, %Y")
        return date_obj.strftime("%A, %B %d, %Y")
    except ValueError:
        print(f"Error normalizing date: {date_str}")
        return date_str


def get_available_times(date, events_data, court_number=COURT_NUMBER):
    """Get available time slots for the specified court on the given date."""
    for event in events_data:
        event["date"] = normalize_date_format(event["date"])

    day_name = date.strftime("%A")
    operating_hours = get_operating_hours(date)
    open_time_str, close_time_str = operating_hours[day_name]
    open_time = datetime.combine(date, parse_time(open_time_str).time())
    close_time = datetime.combine(date, parse_time(close_time_str).time())

    events = fetch_events(date, events_data, court_number)

    if not events:
        return [(open_time, close_time)]

    parsed_events = []
    for start, end in events:
        try:
            start_dt = datetime.combine(date, parse_time(start, end).time())
            end_dt = datetime.combine(date, parse_time(end).time())
            parsed_events.append((start_dt, end_dt))
        except ValueError as e:
            print(f"Error parsing event time: {start} - {end}: {e}")

    parsed_events.sort()

    available_times = []
    current_time = open_time

    for start, end in parsed_events:
        if current_time + timedelta(minutes=1) < start:
            available_times.append((current_time, start))
        current_time = max(current_time, end)

    if current_time < close_time:
        available_times.append((current_time, close_time))

    return available_times


def format_datetime(dt):
    """Format datetime for readability."""
    return dt.strftime("%A, %B %d, %Y %I:%M %p")


def format_time(dt):
    if dt.minute != 0:
        return dt.strftime("%-I:%M%p").lower().replace(":00", "")
    return dt.strftime("%-I%p").lower()


def fetch_availability_data(unique_dates, parsed_events):
    """Return availability data keyed by ISO date."""
    try:
        availability_data = {}
        for date in unique_dates:
            date_str = date.strftime("%Y-%m-%d")
            available_slots = []
            available_times = get_available_times(date.date(), parsed_events, court_number=COURT_NUMBER)

            for start, end in available_times:
                available_slots.append(f"{format_time(start)} - {format_time(end)}")

            availability_data[date_str] = available_slots

        return {
            "availability": availability_data,
            "last_updated": datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        print(f"Error generating availability data: {e}")
        return {
            "availability": {},
            "last_updated": datetime.now(TIMEZONE).strftime("%Y-%m-%d %H:%M:%S"),
        }


def save_availability_to_file(unique_dates, parsed_events, filename=AVAILABILITY_FILE):
    """Save the availability data to a JSON file."""
    try:
        filename = Path(filename)
        filename.parent.mkdir(parents=True, exist_ok=True)
        data = fetch_availability_data(unique_dates, parsed_events)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f)
        print(f"Availability data saved to {filename}")
        return data
    except Exception as e:
        print(f"Error saving availability data: {e}")
        return None


def load_checkpoint_events(checkpoint_dir=CHECKPOINT_DIR, num_batches=4):
    """Load event records from checkpoint files."""
    data = []
    for i in range(num_batches):
        checkpoint_file = checkpoint_dir / f"batch_{i}_checkpoint.json"
        with open(checkpoint_file, encoding="utf-8") as f:
            data.extend(json.load(f))
    return data


def normalize_event_times(parsed_events):
    """Normalize missing am/pm values inferred from event end times."""
    for event in parsed_events:
        if "m" not in event["start_time"] and "pm" in event["end_time"]:
            event["start_time"] += "pm"
        elif "m" not in event["start_time"] and "am" in event["end_time"]:
            event["start_time"] += "am"
        if not event["end_time"]:
            event["end_time"] = "11:59pm"
        if not event["start_time"]:
            event["start_time"] = "12:00am"
    return parsed_events


def main():
    data = load_checkpoint_events()
    print(f"Total events: {len(data)}")

    descs = [d["description"] for d in data]
    parsed_events = parse_schedule_data(descs)
    parsed_dates = [datetime.strptime(event["date"], "%A, %B %d, %Y") for event in parsed_events]
    unique_dates = sorted(set(parsed_dates))
    print(f"Unique dates: {unique_dates}")

    parsed_events = normalize_event_times(parsed_events)
    print(f"Parsed {len(parsed_events)} events")
    save_availability_to_file(unique_dates, parsed_events)
