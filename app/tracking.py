"""Tracking over time: daily score snapshots, a log of signal changes, and practice portfolios.

The files live in the repository (data/history/, data/paper/) and are written by the daily
GitHub Action (snapshot.py), so the record builds up whether or not a PC is on.
A backtest can be tuned until it looks good; this live record can't, because each
month's picks are saved before anyone knows how they'll do.
"""
import bisect
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import engine

DATA = Path(__file__).parent.parent / "data"
HISTORY = DATA / "history"
PAPER = DATA / "paper"
START_VALUE = 10_000


def today_key(ts=None):
    return datetime.fromtimestamp(ts or time.time(), timezone.utc).strftime("%Y-%m-%d")


def _day_end(key):
    return datetime.strptime(key, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() + 86399

# ---------------------------------------------------------------- daily snapshots

def _read_lines(path):
    out = []
    for line in path.read_text(encoding="utf-8").splitlines() if path.exists() else []:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def write_snapshot(page, rows, key, extra=None, date=None):
    """One line per day in a yearly file per page (e.g. sectors-2026.jsonl):
    {date, rows: {market: [score, signal, price]}, plus page-level context}. Re-running a day replaces its line."""
    date = date or today_key()
    path = HISTORY / f"{page}-{date[:4]}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    snap = {r[key]: [r["m"]["score"], r["m"]["signal"], None if r["m"].get("price") is None else round(r["m"]["price"], 4)]
            for r in rows}
    days = [d for d in _read_lines(path) if d.get("date") != date] + [{"date": date, "rows": snap, **(extra or {})}]
    path.write_text("".join(json.dumps(d, separators=(",", ":")) + "\n" for d in sorted(days, key=lambda d: d["date"])),
                    encoding="utf-8")
    return path


def load_history(page):
    days = [d for f in sorted(HISTORY.glob(f"{page}-*.jsonl")) for d in _read_lines(f) if "date" in d]
    return sorted(days, key=lambda d: d["date"])


def signal_log(page, rows, key):
    """Every recorded change of signal, from the saved daily snapshots plus today's live signal."""
    seq = [(h["date"], {s: v[1] for s, v in h["rows"].items()}, False) for h in load_history(page)]
    live = {r[key]: r["m"]["signal"] for r in rows}
    today = today_key()
    if seq and seq[-1][0] == today:
        seq[-1] = (today, live, True)
    else:
        seq.append((today, live, True))
    prev, changes = {}, []
    for date, sigs, is_live in seq:
        for s, sig in sigs.items():
            if sig and prev.get(s) and sig != prev[s]:
                changes.append({"date": date, "key": s, "from": prev[s], "to": sig, "live": is_live})
            if sig:
                prev[s] = sig
    return {"since": seq[0][0], "days": len(seq), "changes": changes[-300:]}

# ---------------------------------------------------------------- practice ("paper") portfolios

def _paper_path(page):
    return PAPER / f"{page}.json"


def load_paper(page):
    p = _paper_path(page)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def maybe_rebalance(page, rows, key, now=None):
    """At the first snapshot of each month, save the new top / bottom 20% by score. Returns True if it did."""
    now = now or time.time()
    date = today_key(now)
    log = load_paper(page) or {"page": page, "started": date, "startValue": START_VALUE,
                               "costPerTrade": engine.COST_PER_TRADE, "rebalances": [],
                               "rule": "Each month, hold the 20% of markets with the highest scores in equal amounts; "
                                       "compare with the lowest-scored 20% and with the same money in each holding's own market."}
    if log["rebalances"] and log["rebalances"][-1]["date"][:7] == date[:7]:
        return False
    ranked = sorted((r for r in rows if r["m"].get("score") is not None), key=lambda r: -r["m"]["score"])
    k = max(1, round(len(ranked) / 5))
    log["rebalances"].append({"date": date, "ts": int(now),
                              "top": [r[key] for r in ranked[:k]], "bottom": [r[key] for r in ranked[-k:]],
                              "scores": {r[key]: r["m"]["score"] for r in ranked}})
    PAPER.mkdir(exist_ok=True)
    _paper_path(page).write_text(json.dumps(log, indent=1), encoding="utf-8")
    return True


def _value_at(series, ts):
    i = bisect.bisect_right(series["t"], ts) - 1
    return series["c"][i] if i >= 0 else None


def paper_report(page, series, market_of, world):
    """Rebuild each practice portfolio's value from the saved monthly picks and the latest price history.

    series[key] = {"gbp": price dict, "usd": price dict} for every market on the page (dividends included);
    market_of[key] = the same for that market's own benchmark; world = the same for MSCI ACWI.
    Every line starts at 10,000 in each currency. At each monthly pick the portfolio is reset to equal
    amounts in the new holdings, paying the assumed trading cost on the share it had to swap.
    """
    log = load_paper(page)
    if not log or not log["rebalances"]:
        return None
    rebs, cost = log["rebalances"], log.get("costPerTrade", engine.COST_PER_TRADE)
    first = _day_end(rebs[0]["date"])
    # one point per day from the first pick to today (just the one point on the first day)
    days = [first + 86400 * k for k in range(max(0, int((time.time() - first) // 86400)) + 1)]
    mean = lambda xs: sum(xs) / len(xs) if xs else 1.0

    def line(group, cur):
        value, path, held_prev = float(START_VALUE), [], None
        for k, reb in enumerate(rebs):
            seg_start = _day_end(reb["date"])
            seg_end = _day_end(rebs[k + 1]["date"]) if k + 1 < len(rebs) else None
            if group == "world":
                legs = [world[cur]]
            else:
                names = reb["bottom"] if group == "bottom" else reb["top"]
                src = market_of if group == "mkt" else series
                legs = [src[n][cur] for n in names if n in src]
                if group in ("top", "bottom"):
                    held = set(names)
                    swapped = 1.0 if held_prev is None else 1 - len(held & held_prev) / len(held)
                    value *= 1 - swapped * (1 if held_prev is None else 2) * cost  # buying (and selling) costs money
                    held_prev = held
            base = [(leg, _value_at(leg, seg_start)) for leg in legs]
            base = [(leg, b) for leg, b in base if b]
            for d in days:
                if d >= seg_start and (seg_end is None or d < seg_end):
                    path.append(round(value * mean([(_value_at(leg, d) or b) / b for leg, b in base]), 2))
            if seg_end is not None:
                value *= mean([(_value_at(leg, seg_end) or b) / b for leg, b in base])
        return path

    out = {"started": rebs[0]["date"], "costPerTrade": cost, "rule": log.get("rule"), "t": days,
           "rebalances": [{"date": r["date"], "top": r["top"], "bottom": r["bottom"]} for r in rebs]}
    for cur in ("gbp", "usd"):
        out[cur] = {g: line(g, cur) for g in ("top", "bottom", "mkt", "world")}
    last = rebs[-1]
    seg_start = _day_end(last["date"])
    def since(names):
        rows = []
        for n in names:
            s = series.get(n, {}).get("gbp")
            b, now_v = (_value_at(s, seg_start), _value_at(s, days[-1])) if s else (None, None)
            rows.append({"key": n, "sinceGbp": (now_v / b - 1) if (b and now_v) else None})
        return sorted(rows, key=lambda x: -(x["sinceGbp"] if x["sinceGbp"] is not None else -9))
    # both portfolios are tracked the same way: the top-scored picks and the lowest-scored for comparison
    out["holdings"], out["bottomHoldings"] = since(last["top"]), since(last["bottom"])
    d = datetime.fromtimestamp(days[-1], timezone.utc)
    out["nextRebalance"] = datetime(d.year + (d.month == 12), d.month % 12 + 1, 1, tzinfo=timezone.utc).strftime("%Y-%m-%d")
    return out
