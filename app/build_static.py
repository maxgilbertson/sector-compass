"""Build the static site GitHub Pages serves: the pages plus site/api/data.json and site/api/world.json.

GitHub Actions runs this every 15 minutes (see .github/workflows/deploy.yml).
It exits with an error if a price fetch mostly failed, so the last good
version stays online instead of being replaced by an empty page.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

import server

HERE = Path(__file__).parent
OUT = HERE.parent / "site"
MINIMUM = {"data": 60, "world": 25}  # fewer markets than this means the fetch failed

# A fingerprint of the pages themselves. It goes into the data files, so a page that has been open
# since before a redesign can tell a newer version is live and reload, and onto the style and script
# links, so browsers fetch the new files instead of reusing cached ones.
VERSION = hashlib.sha1(b"".join((HERE / p).read_bytes() for p in sorted(server.PAGES))).hexdigest()[:10]

(OUT / "api").mkdir(parents=True, exist_ok=True)
for name, need in MINIMUM.items():
    data = json.loads(server.get_data(name))
    if len(data["rows"]) < need:
        sys.exit(f"{name}: only {len(data['rows'])} markets loaded (missing: {data['errors']}); keeping the previous deploy.")
    data["site"] = VERSION
    (OUT / "api" / f"{name}.json").write_text(json.dumps(data, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    print(f"{name}: {len(data['rows'])} markets")

for page in server.PAGES:
    text = (HERE / page).read_text(encoding="utf-8")
    if page.endswith(".html"):
        for old in ('href="common.css"', 'src="common.js"'):
            assert old in text, f"{old} missing from {page}"
            text = text.replace(old, old[:-1] + f'?v={VERSION}"')
    if page == "common.js":
        for old, new in (("const STATIC = false;", "const STATIC = true;"), ('const SITE_VERSION = "dev";', f'const SITE_VERSION = "{VERSION}";')):
            assert old in text, f"{old} missing from common.js"
            text = text.replace(old, new, 1)
    (OUT / page).write_text(text, encoding="utf-8")
if (HERE.parent / "data" / "briefings").exists():
    shutil.copytree(HERE.parent / "data" / "briefings", OUT / "briefings", dirs_exist_ok=True)
(OUT / ".nojekyll").write_text("")
print(f"Built site/ (version {VERSION})")
