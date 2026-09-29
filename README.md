# Sector Compass

Two live trackers on one site, sharing one scoring engine:

- **Sectors** (`index.html`): 86 sector and theme funds across the US, Europe, Japan, Canada and global markets (no whole-country funds),
  each scored 0–100 against its own local benchmark, with a business-cycle read, rotation map, fund facts, top-10 holdings,
  score history and a plain-English verdict.
- **Countries** (`world.html`): 36 national stock markets, with each headline index in local currency and a US-listed country fund
  in US dollars. Includes a world map, currency effects, valuation (P/E, yield, value score), correlation with world stocks,
  a global-backdrop read (dollar, oil, metals, risk appetite) and open/closed market status.

Both pages include a **backtest**: every month for the past ~9 years, every market is re-scored using only the data
available at the time, and its next-month return is compared with its benchmark.

**Live site:** https://maxgilbertson.github.io/sector-compass/ (updated every ~15 minutes by GitHub Actions)

## Run it on your own PC

Needs Python 3.10+. Double-click `Start Sector Compass.bat`, or:

```
pip install -r requirements.txt
py server.py              # http://localhost:8765, refreshes every 5 minutes
py server.py --lan        # also reachable from phones on the same Wi-Fi
```

## Files

- `engine.py`: fetching, point-in-time metrics, the score, score history and the backtest (shared by both pages).
- `universe.py` + `sectors.py`: the sector funds and their benchmarks, and the sector page's data (including the cycle read).
- `world.py`: the countries, their indices, funds and currencies, and the country page's data (including the backdrop rules).
- `funddata.py`: top-10 holdings and fund facts (net assets, P/E, yield, beta, expense ratio), cached for a day.
- `index.html`, `world.html`, `common.css`, `common.js`: the two pages and what they share.
- `server.py`: the local web server. `build_static.py` + `.github/workflows/deploy.yml`: build and publish the GitHub Pages copy.

For research and education only; not investment advice.
