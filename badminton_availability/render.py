import json
from datetime import datetime, timedelta

from jinja2 import Template

from badminton_availability.config import AVAILABILITY_FILE, HTML_FILE, TIMEZONE


HTML_TEMPLATE = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta http-equiv="refresh" content="900"> <!-- Refresh every 15 minutes -->
            <title>Woodpec PE Court #3 Availability</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 1000px;
                    margin: 0 auto;
                    padding: 20px;
                    line-height: 1.6;
                }
                h1 {
                    text-align: center;
                    color: #2c3e50;
                }
                h3 {
                    text-align: center;
                    color: #2c3e50;
                }
                .updated {
                    text-align: center;
                    font-style: italic;
                    color: #7f8c8d;
                    margin-bottom: 20px;
                }
                .day-container {
                    margin-bottom: 30px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 15px;
                }
                h2 {
                    margin-top: 0;
                    color: #3498db;
                    border-bottom: 1px solid #eee;
                    padding-bottom: 10px;
                }
                .slots {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                }
                .slot {
                    background-color: #2ecc71;
                    color: white;
                    padding: 8px 12px;
                    border-radius: 4px;
                    display: inline-block;
                }
                .no-slots {
                    color: #e74c3c;
                    font-style: italic;
                }
                .no-data {
                    color: #f39c12;
                    font-style: italic;
                }
                .disclaimer {
                    background-color: #f8f9fa;
                    border: 1px solid #e9ecef;
                    border-radius: 5px;
                    padding: 12px;
                    margin: 15px auto;
                    max-width: 800px;
                    color: #6c757d;
                    font-size: 0.85em;
                    line-height: 1.5;
                    text-align: center;
                }
                .disclaimer strong {
                    color: #495057;
                    display: inline;
                    font-weight: 500;
                }
                @media (max-width: 600px) {
                    body {
                        padding: 10px;
                    }
                    .day-container {
                        padding: 10px;
                    }
                }
            </style>
        </head>
        <body>
            <h1>Woodruff PE Center Court #3 Availability</h1>
            <h3> Badminton Courts at WoodPEC, Emory University <h3>
            <div class="disclaimer">
                <strong>⚠️ Disclaimer:</strong>
                Hours may be inaccurate during holidays/breaks. Please check the <a href="https://recwell.emory.edu/about/hrs.html" target="_blank">official website</a> for latest announcements.
            </div>
            <p class="updated">Last updated: {{ last_updated }}</p>

            {% for day in dates %}
            <div class="day-container">
                <h2>{{ day.display }}</h2>
                <div class="slots">
                    {% if day.no_data %}
                        <p class="no-data">No data available</p>
                    {% elif day.slots %}
                        {% for slot in day.slots %}
                            <div class="slot">{{ slot }}</div>
                        {% endfor %}
                    {% else %}
                        <p class="no-slots">No available slots</p>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
            <footer class="byline">Coded by Claude 3.7 & GPT4, prompted & put them together by <a href="https://toan-vt.github.io" target="_blank">Toan Tran</a> | Data source: <a href="https://25livepub.collegenet.com/calendars/25live-woodpec-cal" target="_blank">WPEC Calendar</a> | I am not responsible for any errors in court availability information :) | Created in a random boring evening :) on March 3, 2025 </footer>
        </body>
        </html>
        """


def build_dates(availability):
    today = datetime.now(TIMEZONE)
    dates = []

    for i in range(8):
        date = today + timedelta(days=i)
        date_str = date.strftime("%Y-%m-%d")
        date_display = datetime.strptime(date_str, "%Y-%m-%d").strftime("%A %m-%d-%Y")

        dates.append(
            {
                "date_str": date_str,
                "display": date_display,
                "slots": availability.get(date_str, []),
                "no_data": date_str not in availability,
            }
        )

    return dates


def generate_html(data_file=AVAILABILITY_FILE, html_file=HTML_FILE):
    """Generate the HTML page using saved availability data."""
    try:
        with open(data_file, encoding="utf-8") as f:
            data = json.load(f)

        availability = data["availability"]
        last_updated = data["last_updated"]
        rendered_html = Template(HTML_TEMPLATE).render(
            dates=build_dates(availability),
            last_updated=last_updated,
        )

        with open(html_file, "w", encoding="utf-8") as f:
            f.write(rendered_html)

        print(f"HTML generated at {datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"Error generating HTML: {e}")


def main():
    generate_html()

