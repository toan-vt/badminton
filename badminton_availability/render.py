import json
from datetime import datetime, timedelta

from jinja2 import Template

from badminton_availability.config import (
    AVAILABILITY_FILE,
    DAYS_SHOWN,
    HTML_FILE,
    TIMEZONE,
    get_operating_hours,
)
from badminton_availability.process import parse_time


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="900"> <!-- Refresh every 15 minutes -->
<title>Woodpec PE Court #3 Availability</title>
<style>
  :root {
    --bg: #f6f7f9;
    --surface: #ffffff;
    --text: #1f2933;
    --muted: #6b7785;
    --border: #e1e5ea;
    --accent: #2563eb;
    --open: #16a34a;
    --open-soft: #dcfce7;
    --open-text: #14532d;
    --booked: #cbd2d9;
    --full: #b91c1c;
    --closed: #eef1f4;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0f1419;
      --surface: #1a2029;
      --text: #e6e9ed;
      --muted: #9aa5b1;
      --border: #2c3440;
      --accent: #60a5fa;
      --open: #22c55e;
      --open-soft: #133524;
      --open-text: #bbf7d0;
      --booked: #3e4754;
      --full: #f87171;
      --closed: #232a34;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    padding: 20px 16px 32px;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    line-height: 1.45;
  }
  .wrap { max-width: 1100px; margin: 0 auto; }
  h1 { font-size: clamp(1.25rem, 4vw, 1.75rem); margin: 0 0 4px; text-align: center; }
  .subtitle { text-align: center; color: var(--muted); margin: 0 0 12px; font-size: 0.95rem; }
  .disclaimer {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 12px;
    margin: 0 auto 10px;
    max-width: 800px;
    color: var(--muted);
    font-size: 0.85rem;
    text-align: center;
  }
  a { color: var(--accent); }
  .updated { text-align: center; color: var(--muted); font-size: 0.85rem; margin: 0 0 14px; }

  .legend {
    display: flex; flex-wrap: wrap; justify-content: center; gap: 6px 16px;
    font-size: 0.8rem; color: var(--muted); margin-bottom: 10px;
  }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .swatch { width: 12px; height: 12px; border-radius: 3px; display: inline-block; }

  .calendar {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }
  .grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); }
  .dow {
    text-align: center; font-size: 0.75rem; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.04em;
    padding: 8px 2px; border-bottom: 1px solid var(--border);
  }
  .day {
    all: unset;
    box-sizing: border-box;
    min-width: 0;
    min-height: 132px;
    padding: 6px 6px 8px;
    border-right: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    display: flex; flex-direction: column; gap: 6px;
    cursor: pointer;
  }
  .grid > .day:nth-child(7n) { border-right: none; }
  .day:hover { background: color-mix(in srgb, var(--accent) 6%, transparent); }
  .day:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  .day[aria-pressed="true"] { box-shadow: inset 0 0 0 2px var(--accent); }
  .day.outside { cursor: default; opacity: 0.35; background: none; }
  .day-head { display: flex; align-items: center; gap: 4px; font-size: 0.85rem; }
  .num { font-weight: 600; }
  .mon { color: var(--muted); font-size: 0.75rem; }
  .today .num {
    background: var(--accent); color: #fff; border-radius: 999px;
    min-width: 22px; height: 22px; display: inline-flex; align-items: center; justify-content: center;
    padding: 0 6px;
  }
  .day-body { display: flex; gap: 6px; flex: 1; min-height: 0; }
  .bar {
    position: relative; width: 10px; flex: none; border-radius: 4px; overflow: hidden;
    background: var(--closed); min-height: 84px;
  }
  .bar .hours { position: absolute; left: 0; right: 0; background: var(--booked); }
  .bar .free { position: absolute; left: 0; right: 0; background: var(--open); }
  .bar.nodata {
    background: repeating-linear-gradient(45deg, var(--closed) 0 4px, var(--booked) 4px 6px);
  }
  .info { min-width: 0; display: flex; flex-direction: column; gap: 3px; }
  .chip {
    font-size: 0.72rem; line-height: 1.25; white-space: nowrap;
    background: var(--open-soft); color: var(--open-text);
    border-radius: 4px; padding: 2px 5px;
    overflow: hidden; text-overflow: ellipsis;
  }
  .total { font-size: 0.72rem; color: var(--muted); }
  .status-full { font-size: 0.75rem; color: var(--full); font-weight: 600; }
  .status-nodata { font-size: 0.75rem; color: var(--muted); font-style: italic; }

  .detail {
    margin-top: 12px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 14px;
  }
  .detail h2 { font-size: 1.05rem; margin: 0 0 8px; }
  .detail .slots { display: flex; flex-wrap: wrap; gap: 8px; }
  .detail .slot {
    background: var(--open); color: #fff; font-weight: 600;
    padding: 8px 12px; border-radius: 6px; font-size: 0.95rem;
  }
  .detail .hint { color: var(--muted); font-size: 0.8rem; margin: 10px 0 0; }
  .detail-day[hidden] { display: none; }

  footer { margin-top: 20px; font-size: 0.78rem; color: var(--muted); text-align: center; }

  /* Narrow screens: compact cells (bar + free hours), details shown below the grid. */
  @media (max-width: 760px) {
    body { padding: 14px 8px 24px; }
    .day { min-height: 104px; padding: 4px 3px 6px; align-items: center; }
    .day-head { flex-direction: column; gap: 0; font-size: 0.8rem; }
    .day-body { flex-direction: column; align-items: center; gap: 4px; }
    .bar { width: 14px; min-height: 60px; }
    .chip { display: none; }
    .info { align-items: center; }
    .total, .status-full, .status-nodata { font-size: 0.7rem; text-align: center; }
    .status-full .long, .status-nodata .long, .total .long { display: none; }
    .dow { font-size: 0.68rem; padding: 6px 0; }
  }
  @media (min-width: 761px) {
    .status-full .short, .status-nodata .short { display: none; }
  }
</style>
</head>
<body>
<div class="wrap">
  <h1>Woodruff PE Center Court #3 Availability</h1>
  <p class="subtitle">Badminton Courts at WoodPEC, Emory University &middot; next {{ days_shown }} days</p>
  <div class="disclaimer">
    <strong>&#9888;&#65039; Disclaimer:</strong>
    Hours may be inaccurate during holidays/breaks. Please check the <a href="https://recwell.emory.edu/about/hrs.html" target="_blank">official website</a> for latest announcements.
  </div>
  <p class="updated">Last updated: {{ last_updated }}</p>

  <div class="legend" aria-hidden="true">
    <span><i class="swatch" style="background:var(--open)"></i>Open</span>
    <span><i class="swatch" style="background:var(--booked)"></i>Booked</span>
    <span><i class="swatch" style="background:var(--closed);border:1px solid var(--border)"></i>Facility closed</span>
    <span>Bars: {{ scale_label }}, top to bottom &middot; hours = free time</span>
  </div>

  <div class="calendar">
    <div class="grid" role="grid" aria-label="Court #3 availability calendar">
      {% for name in weekday_names %}<div class="dow" role="columnheader">{{ name }}</div>{% endfor %}
      {% for day in days %}
      {% if day.in_range %}
      <button type="button" class="day{% if day.is_today %} today{% endif %}" data-date="{{ day.iso }}"
              aria-pressed="{{ 'true' if day.is_today else 'false' }}"
              aria-label="{{ day.long_label }}: {{ day.summary }}">
        <div class="day-head">
          <span class="num">{{ day.day_num }}</span>{% if day.show_month %}<span class="mon">{{ day.month_abbr }}</span>{% endif %}
        </div>
        <div class="day-body">
          {% if day.no_data %}
          <div class="bar nodata"></div>
          {% else %}
          <div class="bar">
            <div class="hours" style="top:{{ day.hours_top }}%;height:{{ day.hours_height }}%"></div>
            {% for b in day.blocks %}<div class="free" style="top:{{ b.top }}%;height:{{ b.height }}%"></div>{% endfor %}
          </div>
          {% endif %}
          <div class="info">
            {% if day.no_data %}
              <span class="status-nodata"><span class="long">No data</span><span class="short">?</span></span>
            {% elif day.slots %}
              {% for slot in day.slots %}<span class="chip">{{ slot }}</span>{% endfor %}
              <span class="total">{{ day.free_label }}<span class="long"> free</span></span>
            {% else %}
              <span class="status-full"><span class="long">Fully booked</span><span class="short">Full</span></span>
            {% endif %}
          </div>
        </div>
      </button>
      {% else %}
      <div class="day outside" aria-hidden="true">
        <div class="day-head"><span class="num">{{ day.day_num }}</span>{% if day.show_month %}<span class="mon">{{ day.month_abbr }}</span>{% endif %}</div>
      </div>
      {% endif %}
      {% endfor %}
    </div>
  </div>

  <div class="detail" aria-live="polite">
    {% for day in days if day.in_range %}
    <section class="detail-day" data-date="{{ day.iso }}"{% if not day.is_today %} hidden{% endif %}>
      <h2>{{ day.long_label }}{% if day.is_today %} (today){% endif %}</h2>
      {% if day.no_data %}
        <p class="status-nodata">No data available</p>
      {% elif day.slots %}
        <div class="slots">{% for slot in day.slots %}<span class="slot">{{ slot }}</span>{% endfor %}</div>
      {% else %}
        <p class="status-full">No available slots</p>
      {% endif %}
      <p class="hint">Facility hours: {{ day.hours_label }}. Tap or click any day to see its open times.</p>
    </section>
    {% endfor %}
  </div>

  <footer class="byline">Coded by Claude 3.7, GPT4 & Claude Code, prompted & put them together by <a href="https://toan-vt.github.io" target="_blank">Toan Tran</a> | Data source: <a href="https://25livepub.collegenet.com/calendars/25live-woodpec-cal" target="_blank">WPEC Calendar</a> | I am not responsible for any errors in court availability information :) | Created in a random boring evening :) on March 3, 2025 </footer>
</div>
<script>
  (function () {
    var buttons = document.querySelectorAll('.day[data-date]');
    var panels = document.querySelectorAll('.detail-day');
    function select(date) {
      buttons.forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.date === date ? 'true' : 'false'); });
      panels.forEach(function (p) { p.hidden = p.dataset.date !== date; });
    }
    buttons.forEach(function (b) {
      b.addEventListener('click', function () { select(b.dataset.date); });
    });
  })();
</script>
</body>
</html>
"""

WEEKDAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def _hours(dt):
    return dt.hour + dt.minute / 60


def _parse_slot(slot):
    start_str, end_str = [part.strip() for part in slot.split("-", 1)]
    return _hours(parse_time(start_str, end_str)), _hours(parse_time(end_str))


def _format_hours(value):
    whole = int(value)
    if abs(value - whole) < 1e-6:
        return f"{whole}h"
    if abs(value - whole - 0.5) < 1e-6:
        return f"{whole}½h"
    return f"{value:.1f}h"


def _clock_label(value):
    hour = int(value)
    minute = round((value - hour) * 60)
    suffix = "am" if hour < 12 or hour == 24 else "pm"
    hour12 = hour % 12 or 12
    return f"{hour12}:{minute:02d}{suffix}" if minute else f"{hour12}{suffix}"


def _operating_range(day):
    open_str, close_str = get_operating_hours(day)[day.strftime("%A")]
    return _hours(parse_time(open_str)), _hours(parse_time(close_str))


def build_calendar(availability, today=None, days_shown=DAYS_SHOWN):
    """Build a Sunday-first grid covering today .. today + days_shown - 1."""
    today = today or datetime.now(TIMEZONE).date()
    last_day = today + timedelta(days=days_shown - 1)
    grid_start = today - timedelta(days=(today.weekday() + 1) % 7)  # previous Sunday
    grid_end = last_day + timedelta(days=(5 - last_day.weekday()) % 7)  # following Saturday

    shown = [today + timedelta(days=i) for i in range(days_shown)]
    ranges = [_operating_range(d) for d in shown]
    scale_start = min(r[0] for r in ranges)
    scale_end = max(r[1] for r in ranges)
    span = scale_end - scale_start

    def pct(value):
        return round((value - scale_start) / span * 100, 2)

    days = []
    current = grid_start
    while current <= grid_end:
        iso = current.isoformat()
        in_range = today <= current <= last_day
        day = {
            "iso": iso,
            "day_num": current.day,
            "month_abbr": current.strftime("%b"),
            "show_month": current == grid_start or current.day == 1,
            "in_range": in_range,
            "is_today": current == today,
            "long_label": f"{current.strftime('%A, %B')} {current.day}",
        }
        if in_range:
            open_h, close_h = _operating_range(current)
            slots = availability.get(iso)
            day["no_data"] = slots is None
            day["slots"] = slots or []
            day["hours_top"] = pct(open_h)
            day["hours_height"] = round(pct(close_h) - pct(open_h), 2)
            day["hours_label"] = f"{_clock_label(open_h)} - {_clock_label(close_h)}"

            blocks = []
            free = 0.0
            for slot in day["slots"]:
                try:
                    start, end = _parse_slot(slot)
                except ValueError:
                    continue
                free += max(0.0, end - start)
                blocks.append({"top": pct(start), "height": round(pct(end) - pct(start), 2)})
            day["blocks"] = blocks
            day["free_label"] = _format_hours(free)

            if day["no_data"]:
                day["summary"] = "no data"
            elif day["slots"]:
                day["summary"] = f"{day['free_label']} free, " + ", ".join(day["slots"])
            else:
                day["summary"] = "fully booked"
        days.append(day)
        current += timedelta(days=1)

    return {
        "days": days,
        "weekday_names": WEEKDAY_NAMES,
        "scale_label": f"{_clock_label(scale_start)} - {_clock_label(scale_end)}",
        "days_shown": days_shown,
    }


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
