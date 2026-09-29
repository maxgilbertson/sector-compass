# Sector Compass

Two live trackers on one site, sharing one scoring engine:

- **Sectors** (`index.html`): 86 sector and theme funds across the US, Europe, Japan, Canada and global markets (no whole-country funds),
  each scored 0–100 against its own local benchmark, with a business-cycle read, rotation map, fund facts, top-10 holdings,
  score history and a plain-English verdict.
- **Countries** (`world.html`): 36 national stock markets, with each headline index in local currency and a US-listed country fund
  in US dollars. Includes a world map, currency effects, valuation (P/E, yield, value score), correlation with world stocks,
  a global-backdrop read (dollar, oil, metals, risk appetite) and open/closed market status.

Both pages include a **backtest**: every month for the past ~9 years, every market is re-scored using only the data
available at the time, and its next-month return is compared with its benchmark. It also reports the result after an
assumed 0.15% trading cost, and separately for the first and second half of the period.

Returns can be shown in **pounds** as well as the local currency (and US dollars on the Countries page).

**Keeping a real record from now on:**

- **Daily snapshots** (`history/`): every weekday after the US close, `daily.yml` runs `snapshot.py` and saves every score
  and signal, so the pages can show when each signal last changed.
- **Practice portfolios** (`paper/`): on the first snapshot of each month, pretend £10,000 portfolios buy the top-scored 20%
  and the lowest-scored 20% on each page, equally weighted, paying the assumed trading cost. They're compared with the
  same money in their markets and in world stocks.
- **Weekly briefing** (`briefing.html`, `briefings/`): every Saturday at about 07:30 UK time, `briefing.yml` runs `briefing.py`,
  which saves the week's numbers (`briefings/facts/<date>.json`) and an automatic draft. At 09:00, a scheduled Claude task
  on Max's PC rewrites the draft following `BRIEFING_PROMPT.md` and publishes it. If the PC is off, the draft stays up until
  the task runs.
- **Research** (`research.py`): tests other score recipes the careful way. Each one is judged on the first half of the
  history and must still win on the second half, which it never saw. It only reports; it never changes the live score.

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
- `tracking.py` + `snapshot.py`: daily snapshots, the signal-change log and the practice portfolios.
- `briefing.py` + `briefing.html` + `BRIEFING_PROMPT.md`: the weekly briefing's facts, draft, page and writing rules.
- `index.html`, `world.html`, `common.css`, `common.js`: the two pages and what they share.
- `server.py`: the local web server. `build_static.py` + `.github/workflows/deploy.yml`: build and publish the GitHub Pages copy. `daily.yml` and `briefing.yml` run the snapshot and the briefing facts.

For research and education only; not investment advice.
