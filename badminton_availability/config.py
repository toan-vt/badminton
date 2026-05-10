from datetime import date
from pathlib import Path

import pytz

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
CHECKPOINT_DIR = DATA_DIR / "checkpoints"
AVAILABILITY_FILE = DATA_DIR / "availability.json"
HTML_FILE = BASE_DIR / "index.html"
EVENT_LINKS_FILE = BASE_DIR / "event_links.csv"
EVENT_LINKS_NO_DESCRIPTIONS_FILE = BASE_DIR / "event_links_no_descriptions.csv"

COURT_NUMBER = 3
NUM_WORKERS = 4
TIMEZONE = pytz.timezone("US/Eastern")
SOURCE_URL = "https://25livepub.collegenet.com/calendars/25live-woodpec-cal"

OPERATING_HOURS = {
    "Monday": ("7am", "11pm"),
    "Tuesday": ("7am", "11pm"),
    "Wednesday": ("7am", "11pm"),
    "Thursday": ("7am", "11pm"),
    "Friday": ("7am", "8pm"),
    "Saturday": ("8am", "8pm"),
    "Sunday": ("8am", "8pm"),
}

SUMMER_HOURS_START = date(2026, 5, 12)
SUMMER_HOURS_END = date(2026, 8, 23)
SUMMER_OPERATING_HOURS = {
    "Monday": ("7am", "8pm"),
    "Tuesday": ("7am", "8pm"),
    "Wednesday": ("7am", "8pm"),
    "Thursday": ("7am", "8pm"),
    "Friday": ("7am", "8pm"),
    "Saturday": ("10am", "6pm"),
    "Sunday": ("10am", "6pm"),
}


def get_operating_hours(current_date):
    if SUMMER_HOURS_START <= current_date <= SUMMER_HOURS_END:
        return SUMMER_OPERATING_HOURS
    return OPERATING_HOURS
