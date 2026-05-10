# WoodPEC Court Availability

Generates a GitHub Pages site showing Woodruff PE Center Court #3 badminton availability from the Emory 25Live calendar.

The project fetches calendar events, extracts event descriptions, converts Court #3 bookings into open time slots, writes `data/availability.json`, and renders the static `index.html` page.

## Project Structure

```text
badminton_availability/
  config.py      Shared paths, constants, timezone, court number, source URL
  fetch.py       Selenium and requests-based event fetching
  process.py     Event parsing and availability calculation
  render.py      Static HTML generation

data/
  availability.json       Generated availability output
  checkpoints/            Generated event-description checkpoints

scripts/
  fetch_data.py      Fetch calendar events and checkpoint descriptions
  process_data.py    Generate data/availability.json from checkpoints
  generate_site.py   Generate index.html from availability JSON

tests/
  test_process.py    Unit tests for parsing and availability logic
  test_render.py     Unit tests for HTML generation
```

Generated outputs are intentionally tracked because the GitHub Actions workflow commits refreshed data and site files:

- `index.html`
- `data/availability.json`
- `event_links.csv`
- `event_links_no_descriptions.csv`
- `data/checkpoints/batch_*_checkpoint.json`

## GitHub Actions Workflow

[`.github/workflows/main.yml`](.github/workflows/main.yml) runs on:

- A schedule every 5 minutes
- Pushes to `main`
- Manual `workflow_dispatch`

The workflow:

1. Installs Python dependencies from `requirements.txt`.
2. Runs unit tests.
3. Fetches calendar data.
4. Processes checkpoint data into availability JSON.
5. Generates `index.html`.
6. Commits generated changes if any files changed.
7. Deploys the repository root to GitHub Pages.

## Local Setup

Use a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Run the unit tests:

```bash
.venv/bin/python -m unittest discover -v
```

Regenerate availability and the site from existing `data/checkpoints/` files:

```bash
.venv/bin/python scripts/process_data.py
.venv/bin/python scripts/generate_site.py
```

Fetch fresh live data:

```bash
.venv/bin/python scripts/fetch_data.py
```

The fetch step requires Chrome/WebDriver support through Selenium and network access to the 25Live calendar.

## Data Source

Availability is derived from the public 25Live calendar:

<https://25livepub.collegenet.com/calendars/25live-woodpec-cal>

The site is an unofficial view of Court #3 availability. Facility hours and bookings may be inaccurate during holidays, breaks, or calendar delays.
