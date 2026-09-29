"""Build the static site GitHub Pages serves: the pages plus site/api/data.json and site/api/world.json.

GitHub Actions runs this every 15 minutes (see .github/workflows/deploy.yml).
It exits with an error if a price fetch mostly failed, so the last good
version stays online instead of being replaced by an empty page.
"""
import json
import shutil
import sys
from pathlib import Path

import server

HERE = Path(__file__).parent
OUT = HERE / "site"
MINIMUM = {"data": 60, "world": 25}  # fewer markets than this means the fetch failed

(OUT / "api").mkdir(parents=True, exist_ok=True)
for name, need in MINIMUM.items():
    body = server.get_data(name)
    data = json.loads(body)
    if len(data["rows"]) < need:
        sys.exit(f"{name}: only {len(data['rows'])} markets loaded (missing: {data['errors']}); keeping the previous deploy.")
    (OUT / "api" / f"{name}.json").write_bytes(body)
    print(f"{name}: {len(data['rows'])} markets")

for page in server.PAGES:
    shutil.copy(HERE / page, OUT / page)
js = (OUT / "common.js").read_text(encoding="utf-8")
marker = "const STATIC = false;"
assert marker in js, "static-mode marker missing from common.js"
(OUT / "common.js").write_text(js.replace(marker, "const STATIC = true;", 1), encoding="utf-8")
if (HERE / "briefings").exists():
    shutil.copytree(HERE / "briefings", OUT / "briefings", dirs_exist_ok=True)
(OUT / ".nojekyll").write_text("")
print("Built site/")
