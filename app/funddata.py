"""Slow-moving fund data via yfinance: top-10 holdings and fund facts
(net assets, P/E, yield, beta, expense ratio).

Providers update these monthly or quarterly, so they are cached on disk and
refreshed at most once every CACHE_HOURS rather than on every price poll.
"""
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CACHE = Path(__file__).parent.parent / "data" / "fund_cache.json"
CACHE_HOURS = 24


def _num(v, scale=1.0):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v * scale


def _fetch_one(symbol):
    import yfinance as yf  # imported lazily so the price tracker still runs without it
    t = yf.Ticker(symbol)
    out = {}
    try:
        th = t.funds_data.top_holdings
        out["holdings"] = [{"sym": str(s), "name": str(r.get("Name") or s), "pct": float(r.get("Holding Percent") or 0)}
                           for s, r in th.head(10).iterrows()] or None
    except Exception:  # noqa: BLE001 - a fund with no published holdings is not fatal
        out["holdings"] = None
    try:
        info = t.info
        out["facts"] = {
            "aum": _num(info.get("netAssets") or info.get("totalAssets")),  # fund currency
            "pe": _num(info.get("trailingPE")),
            "yld": _num(info.get("yield")),                                   # fraction, e.g. 0.0043
            "beta": _num(info.get("beta3Year")),                              # Yahoo: "Beta (5Y Monthly)"
            "fee": _num(info.get("netExpenseRatio"), 0.01),                   # Yahoo gives percent
        }
    except Exception:  # noqa: BLE001
        out["facts"] = None
    return symbol, out


def load(symbols):
    """Return {"fetched": ts, "funds": {symbol: {"holdings": [...], "facts": {...}}}}."""
    cached = {}
    if CACHE.exists():
        try:
            cached = json.loads(CACHE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = {}
    old = cached.get("funds", {})
    fresh = time.time() - cached.get("fetched", 0) < CACHE_HOURS * 3600
    if fresh and all(s in old for s in symbols):
        return cached
    try:
        with ThreadPoolExecutor(max_workers=8) as ex:
            got = dict(ex.map(_fetch_one, symbols))
    except ImportError:
        print("yfinance not installed: run  py -m pip install yfinance  to show holdings and fund facts", flush=True)
        return cached or {"fetched": 0, "funds": {}}
    funds = {}
    for s in set(symbols) | set(old):
        new, prev = got.get(s, {}), old.get(s, {})
        # keep the previous day's data for any part that failed this time
        funds[s] = {"holdings": new.get("holdings") or prev.get("holdings"),
                    "facts": new.get("facts") or prev.get("facts")}
    out = {"fetched": time.time(), "funds": funds}
    CACHE.write_text(json.dumps(out), encoding="utf-8")
    return out
