# Sector Compass

A live tracker of 100+ sector, theme and country funds across the US, Europe, Japan, Canada and global markets.
Each fund gets a 0–100 score from momentum, relative strength, trend, risk-adjusted return and drawdown,
plus fund facts (net assets, P/E, yield, beta, fees), a business-cycle read, a rotation map, top-10 holdings and a plain-English verdict.

**Live site:** https://maxgilbertson.github.io/sector-compass/ (updated every ~15 minutes by GitHub Actions)

## Run it on your own PC

Needs Python 3.10+. Double-click `Start Sector Compass.bat`, or:

```
pip install -r requirements.txt
py server.py              # http://localhost:8765, refreshes every 5 minutes
py server.py --lan        # also reachable from phones on the same Wi-Fi
```

## Files

- `universe.py`: the funds tracked and their benchmarks. Add or remove tickers here.
- `server.py`: fetches prices from Yahoo Finance and computes every metric and score.
- `funddata.py`: top-10 holdings and fund facts (net assets, P/E, yield, beta, expense ratio), cached for a day.
- `index.html`: the dashboard.
- `build_static.py` + `.github/workflows/deploy.yml`: build and publish the GitHub Pages copy.

For research and education only; not investment advice.
