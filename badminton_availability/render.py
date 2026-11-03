import json
from datetime import datetime, timedelta

from jinja2 import Template

from badminton_availability.config import AVAILABILITY_FILE, DAYS_SHOWN, HTML_FILE, TIMEZONE


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="900"> <!-- Refresh every 15 minutes -->
<title>Woodpec PE Court #3 Availability</title>
<style>
  :root {
    color-scheme: light;
    --bg: #ffffff;
    --surface: #ffffff;
    --text: #1a202c;
    --muted: #5f6b7a;
    --border: #dde2e8;
    --accent: #2563eb;
    --open-bg: #d1fadf;
    --open-text: #0b4d26;
    --full: #c0262d;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 24px 16px 32px;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    font-size: 17px;
    line-height: 1.4;
  }
  .wrap { max-width: 1100px; margin: 0 auto; }
  h1 { font-size: 1.8rem; margin: 0 0 6px; text-align: center; }
  .subtitle { text-align: center; color: var(--muted); margin: 0 0 18px; }
  a { color: var(--accent); }

  .calendar {
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
  }
  .dow {
    text-align: center; font-weight: 700; color: var(--muted);
    padding: 10px 2px; border-bottom: 1px solid var(--border);
  }
  .day {
    min-width: 0;
    min-height: 120px;
    padding: 8px;
    border-right: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
  }
  .calendar > .day:nth-child(7n) { border-right: none; }
  .day.outside { opacity: 0.35; }
  .date { font-size: 1.15rem; font-weight: 700; margin-bottom: 6px; }
  .today .date { color: var(--accent); }
  .today { background: color-mix(in srgb, var(--accent) 8%, transparent); }
  .slots { display: flex; flex-direction: column; gap: 6px; }
  .slot {
    background: var(--open-bg); color: var(--open-text);
    font-weight: 600; border-radius: 6px; padding: 4px 6px;
  }
  .slot .t { white-space: nowrap; }
  .full { color: var(--full); font-weight: 700; }

  .note { text-align: center; color: var(--muted); margin: 18px auto 0; max-width: 760px; font-size: 0.95rem; }
  footer { margin-top: 14px; font-size: 0.85rem; color: var(--muted); text-align: center; }

  @media (max-width: 760px) {
    body { padding: 16px 6px 24px; font-size: 16px; }
    h1 { font-size: 1.35rem; }
    .dow { font-size: 0.85rem; padding: 8px 0; }
    .day { padding: 6px 3px; min-height: 90px; }
    .date { font-size: 1rem; text-align: center; }
    .day { padding: 6px 2px; }
    .slot { font-size: 0.78rem; padding: 3px 0; text-align: center; line-height: 1.25; letter-spacing: -0.01em; }
    .slot .t { display: block; }
    .slot .dash { display: none; }
    .full { font-size: 0.85rem; text-align: center; }
  }
</style>
</head>
<body>
<div class="wrap">
  <h1>WoodPEC Court #3 Availability</h1>
  <p class="subtitle">Open badminton times, next {{ weeks_shown }} weeks &middot; Updated {{ last_updated }}</p>

  <div class="calendar">
    {% for name in weekday_names %}<div class="dow">{{ name }}</div>{% endfor %}
    {% for day in days %}
    <div class="day{% if not day.in_range %} outside{% endif %}{% if day.is_today %} today{% endif %}">
      <div class="date">{{ day.label }}</div>
      {% if day.in_range %}
        {% if day.slots %}
        <div class="slots">
          {% for start, end in day.slots %}<div class="slot"><span class="t">{{ start }}</span><span class="dash"> - </span><span class="t">{{ end }}</span></div>{% endfor %}
        </div>
        {% else %}
        <div class="full">Full</div>
        {% endif %}
      {% endif %}
    </div>
    {% endfor %}
  </div>

  <p class="note">Unofficial. Hours may differ during holidays/breaks &mdash; check the <a href="https://recwell.emory.edu/about/hrs.html" target="_blank">official website</a>.</p>
  <footer class="byline">Coded by Claude 3.7, GPT4 & Claude Code, prompted & put them together by <a href="https://toan-vt.github.io" target="_blank">Toan Tran</a> | Data source: <a href="https://25livepub.collegenet.com/calendars/25live-woodpec-cal" target="_blank">WPEC Calendar</a> | I am not responsible for any errors in court availability information :) | Created in a random boring evening :) on March 3, 2025 </footer>
</div>
</body>
</html>
"""

WEEKDAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def _split_slot(slot):
    start, _, end = slot.partition(" - ")
    return start.strip(), end.strip()


def build_calendar(availability, today=None, days_shown=DAYS_SHOWN):
    """Build a Sunday-first grid covering today .. today + days_shown - 1."""
    today = today or datetime.now(TIMEZONE).date()
    last_day = today + timedelta(days=days_shown - 1)
    grid_start = today - timedelta(days=(today.weekday() + 1) % 7)  # previous Sunday
    grid_end = last_day + timedelta(days=(5 - last_day.weekday()) % 7)  # following Saturday

    days = []
    current = grid_start
    while current <= grid_end:
        show_month = current == grid_start or current.day == 1
        days.append(
            {
                "iso": current.isoformat(),
                "label": f"{current.strftime('%b')} {current.day}" if show_month else str(current.day),
                "in_range": today <= current <= last_day,
                "is_today": current == today,
                "slots": [_split_slot(s) for s in availability.get(current.isoformat(), [])],
            }
        )
        current += timedelta(days=1)

    return {"days": days, "weekday_names": WEEKDAY_NAMES, "weeks_shown": days_shown // 7}


def generate_html(data_file=AVAILABILITY_FILE, html_file=HTML_FILE, today=None):
    """Generate the HTML page using saved availability data."""
    try:
        with open(data_file, encoding="utf-8") as f:
            data = json.load(f)

        rendered_html = Template(HTML_TEMPLATE).render(
            last_updated=data["last_updated"],
            **build_calendar(data["availability"], today=today),
        )

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(rendered_html)

        print(f"HTML generated at {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"Error generating HTML: {e}")


def main():
    generate_html()
