import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from badminton_availability.render import generate_html


class RenderTests(unittest.TestCase):
    def test_generate_html_renders_slots_and_last_updated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            data_file = tmpdir / "availability.json"
            html_file = tmpdir / "index.html"
            data_file.write_text(
                json.dumps(
                    {
                        "availability": {
                            "2026-05-11": ["7am - 8am"],
                        },
                        "last_updated": "2026-05-10 12:00:00",
                    }
                ),
                encoding="utf-8",
            )

            with redirect_stdout(io.StringIO()):
                generate_html(data_file=data_file, html_file=html_file)

            html = html_file.read_text(encoding="utf-8")
            self.assertIn("Woodruff PE Center Court #3 Availability", html)
            self.assertIn("Last updated: 2026-05-10 12:00:00", html)
            self.assertIn("7am - 8am", html)


if __name__ == "__main__":
    unittest.main()
