"""Top-10 holdings for every fund, via yfinance.

Fund holdings are published monthly or quarterly, so they are cached on disk
and refreshed at most once every CACHE_HOURS rather than on every price poll.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CACHE = Path(__file__).parent / "holdings_cache.json"
CACHE_HOURS = 24


def _fetch_one(symbol):
    import yfinance as yf  # imported lazily so the price tracker still runs without it
    try:
        th = yf.Ticker(symbol).funds_data.top_holdings
    except Exception:  # noqa: BLE001 - a fund with no published holdings is not fatal
        return symbol, None
    rows = [{"sym": str(sym), "name": str(r.get("Name") or sym), "pct": float(r.get("Holding Percent") or 0)}
            for sym, r in th.head(10).iterrows()]
    return symbol, rows or None


def load(symbols):
    """Return {fund symbol: [{sym, name, pct}, ...]} plus the time it was fetched."""
    cached = {}
    if CACHE.exists():
        try:
            cached = json.loads(CACHE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = {}
    fresh = time.time() - cached.get("fetched", 0) < CACHE_HOURS * 3600
    missing = [s for s in symbols if s not in cached.get("funds", {})]
    if fresh and not missing:
        return cached
    try:
        with ThreadPoolExecutor(max_workers=8) as ex:
            got = dict(ex.map(_fetch_one, symbols))
    except ImportError:
        print("yfinance not installed: run  py -m pip install yfinance  to show holdings", flush=True)
        return cached or {"fetched": 0, "funds": {}}
    funds = {s: h for s, h in got.items() if h} or cached.get("funds", {})
    # keep yesterday's list for any fund that failed this time
    for s, h in cached.get("funds", {}).items():
        funds.setdefault(s, h)
    out = {"fetched": time.time(), "funds": funds}
    CACHE.write_text(json.dumps(out), encoding="utf-8")
    return out
