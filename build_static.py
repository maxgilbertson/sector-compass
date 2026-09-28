"""Build the static site GitHub Pages serves: site/index.html + site/api/data.json.

GitHub Actions runs this every 15 minutes (see .github/workflows/deploy.yml).
It exits with an error if the price fetch mostly failed, so the last good
version stays online instead of being replaced by an empty page.
"""
import json
import sys
from pathlib import Path

import server

HERE = Path(__file__).parent
OUT = HERE / "site"

body = server.get_data()
data = json.loads(body)
if len(data["rows"]) < 60:
    sys.exit(f"Only {len(data['rows'])} funds loaded (missing: {data['errors']}); keeping the previous deploy.")

(OUT / "api").mkdir(parents=True, exist_ok=True)
(OUT / "api" / "data.json").write_bytes(body)
html = (HERE / "index.html").read_text(encoding="utf-8")
marker = "const STATIC = false;"
assert marker in html, "static-mode marker missing from index.html"
(OUT / "index.html").write_text(html.replace(marker, "const STATIC = true;", 1), encoding="utf-8")
(OUT / ".nojekyll").write_text("")
print(f"Built site/ with {len(data['rows'])} funds.")
