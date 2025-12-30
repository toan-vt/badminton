import os
import json
import time
from datetime import datetime, timedelta
import requests
from flask import Flask, render_template_string
# from fetch_data import save_availability_to_file
import subprocess
import pytz

# Configuration
REPO_NAME = "court-availability"
DATA_FILE = "data/availability.json"
HTML_FILE = "index.html"
timezone = pytz.timezone('US/Eastern')

def generate_html():
    """Generate the HTML page using the saved data."""
    try:
        with open(DATA_FILE, 'r') as f:
            data = json.load(f)
        
        availability = data["availability"]
        last_updated = data["last_updated"]
        
        all_date_strs = data["availability"].keys() # this format: 2025-03-22
        today = datetime.now(timezone)
        dates_str = []
        for i in range(7):
            date = today + timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            dates_str.append(date_str)

        dates = []
        for date_str in dates_str:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            date_display = date.strftime("%A %m-%d-%Y")
            
            if date_str not in all_date_strs:
                # Add the date with a special flag indicating no data available
                dates.append({
                    "date_str": date_str,
                    "display": date_display,
                    "slots": [],
                    "no_data": True
                })
            else:
                dates.append({
                    "date_str": date_str,
                    "display": date_display,
                    "slots": availability.get(date_str, []),
                    "no_data": False
                })
        
        # HTML template
        html_template = """
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
        
        # Render the template with the data
        from jinja2 import Template
        template = Template(html_template)
        rendered_html = template.render(dates=dates, last_updated=last_updated)
        
        # Write the HTML to file
        with open(HTML_FILE, 'w') as f:
            f.write(rendered_html)
            
        print(f"HTML generated at {datetime.now(timezone).strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"Error generating HTML: {e}")

def update_data():
    """Fetch new data and update the website."""
    # save_availability_to_file()
    generate_html()
    commit_and_push_changes()

def commit_and_push_changes():
    """Commit and push changes to GitHub."""
    subprocess.run(["git", "add", HTML_FILE, DATA_FILE])
    subprocess.run(["git", "commit", "-m", f"Update court availability {datetime.now(timezone).strftime('%Y-%m-%d %H:%M:%S')}"])
    subprocess.run(["git", "push", "origin", "main"])

if __name__ == "__main__":
    # Initial data fetch and page generation
    update_data()
