"""Sector Compass: a live global sector tracker.

Run:  py server.py   then open http://localhost:8765
Standard library only. Prices come from Yahoo Finance's public chart API and
are cached for CACHE_SECONDS so the page can poll without hammering it.
"""
import json
import math
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import holdings
from universe import GROUPS, MACRO

PORT = next((int(a) for a in sys.argv[1:] if a.isdigit()), 8765)
CACHE_SECONDS = 300
HERE = Path(__file__).parent
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SectorCompass/1.0"}

# ---------------------------------------------------------------- fetching

def fetch(symbol, rng="5y"):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(symbol)}"
           f"?range={rng}&interval=1d&includeAdjustedClose=true")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
                res = json.load(r)["chart"]["result"][0]
            ts = res.get("timestamp") or []
            ind = res["indicators"]
            closes = (ind.get("adjclose") or [{}])[0].get("adjclose") or ind["quote"][0]["close"]
            raw = ind["quote"][0]["close"]
            pts = [(t, c, rc) for t, c, rc in zip(ts, closes, raw) if c is not None and rc is not None]
            meta = res["meta"]
            return {
                "symbol": symbol,
                "t": [p[0] for p in pts],
                "c": [p[1] for p in pts],        # total-return (adjusted) closes
                "raw": [p[2] for p in pts],      # quoted prices
                "price": meta.get("regularMarketPrice"),
                "ccy": meta.get("currency"),
                "name": meta.get("longName") or meta.get("shortName") or symbol,
                "mtime": meta.get("regularMarketTime"),
            }
        except Exception as e:  # noqa: BLE001 - network hiccups are retried then reported
            err = str(e)
            time.sleep(0.6 * (attempt + 1))
    return {"symbol": symbol, "error": err}


def fetch_all(symbols):
    with ThreadPoolExecutor(max_workers=12) as ex:
        return {d["symbol"]: d for d in ex.map(fetch, symbols)}

# ---------------------------------------------------------------- analytics

def sma(xs, n):
    return sum(xs[-n:]) / n if len(xs) >= n else None


def ret(c, n):
    return c[-1] / c[-1 - n] - 1 if len(c) > n and c[-1 - n] else None


def ret_since(t, c, since_ts):
    for i, ts in enumerate(t):
        if ts >= since_ts:
            base = c[i - 1] if i > 0 else c[i]
            return c[-1] / base - 1
    return None


def stdev(xs):
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def rsi(c, n=14):
    if len(c) < n * 3:
        return None
    gains = losses = 0.0
    diffs = [c[i] - c[i - 1] for i in range(len(c) - n * 3, len(c))]
    for d in diffs[:n]:
        gains += max(d, 0); losses += max(-d, 0)
    ag, al = gains / n, losses / n
    for d in diffs[n:]:
        ag = (ag * (n - 1) + max(d, 0)) / n
        al = (al * (n - 1) + max(-d, 0)) / n
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def align(a, b):
    """Pair two series on common dates (day resolution)."""
    day = lambda ts: ts // 86400
    bm = {day(t): c for t, c in zip(b["t"], b["c"])}
    out = [(t, ca, bm[day(t)]) for t, ca in zip(a["t"], a["c"]) if day(t) in bm]
    return [x[0] for x in out], [x[1] for x in out], [x[2] for x in out]


def rrg(t, ca, cb):
    """Relative Rotation Graph coordinates (JdK-style approximation).

    RS-Ratio: relative strength vs its own 50-day average, centred on 100.
    RS-Momentum: rate of change of RS-Ratio over 10 days, centred on 100.
    Returns a weekly tail of the last 6 weeks.
    """
    raw_rs = [x / y for x, y in zip(ca, cb)]
    if len(raw_rs) < 120:
        return None
    rs, a = [], 2 / (10 + 1)  # 10-day EMA takes out daily noise before measuring the trend
    for v in raw_rs:
        rs.append(v if not rs else rs[-1] + a * (v - rs[-1]))
    ratio = []
    for i in range(len(rs)):
        if i < 49:
            ratio.append(None); continue
        ratio.append(100 * rs[i] / (sum(rs[i - 49:i + 1]) / 50))
    tail = []
    for k in range(6):
        i = len(rs) - 1 - k * 5
        j = i - 10
        if ratio[i] is None or j < 0 or ratio[j] is None:
            break
        mom = 100 * ratio[i] / ratio[j]
        tail.append([round(100 + (ratio[i] - 100) * 1.0, 3), round(mom, 3)])
    return list(reversed(tail))


def quadrant(pt):
    if not pt:
        return None
    x, y = pt
    if x >= 100 and y >= 100: return "Leading"
    if x >= 100: return "Weakening"
    if y >= 100: return "Improving"
    return "Lagging"


def analyse(d, bench, rf):
    t, c = d["t"], d["c"]
    if len(c) < 60:
        return None
    now = datetime.fromtimestamp(t[-1], timezone.utc)
    ytd_ts = datetime(now.year, 1, 1, tzinfo=timezone.utc).timestamp()
    daily = [c[i] / c[i - 1] - 1 for i in range(max(1, len(c) - 252), len(c))]
    d63 = daily[-63:]
    vol3 = stdev(d63) * math.sqrt(252) if len(d63) > 20 else None
    vol1y = stdev(daily) * math.sqrt(252) if len(daily) > 60 else None
    r1y = ret(c, 252)
    sharpe = (r1y - rf) / vol1y if (r1y is not None and vol1y) else None
    yr = c[-253:]
    peak, mdd = yr[0], 0.0
    for x in yr:
        peak = max(peak, x); mdd = min(mdd, x / peak - 1)
    hi52, lo52 = max(d["raw"][-252:]), min(d["raw"][-252:])
    m50, m200 = sma(c, 50), sma(c, 200)
    m200_prev = sum(c[-221:-21]) / 200 if len(c) >= 221 else None
    r3y = ret(c, 756)
    m = {
        "price": d["price"] if d["price"] is not None else d["raw"][-1],
        "r1d": ret(c, 1), "r1w": ret(c, 5), "r1m": ret(c, 21), "r3m": ret(c, 63),
        "r6m": ret(c, 126), "ytd": ret_since(t, c, ytd_ts), "r1y": r1y,
        "r3y": ((1 + r3y) ** (1 / 3) - 1) if r3y is not None else None,
        "mom121": (c[-22] / c[-253] - 1) if len(c) > 253 else None,
        "vol": vol3, "vol1y": vol1y, "sharpe": sharpe, "mdd": mdd,
        "offHigh": d["raw"][-1] / hi52 - 1, "offLow": d["raw"][-1] / lo52 - 1,
        "rsi": rsi(c),
        "vs50": c[-1] / m50 - 1 if m50 else None,
        "vs200": c[-1] / m200 - 1 if m200 else None,
        "golden": (m50 > m200) if (m50 and m200) else None,
        "slope200": (m200 / m200_prev - 1) if (m200 and m200_prev) else None,
    }
    trend_bits = [m["vs50"] is not None and m["vs50"] > 0, m["vs200"] is not None and m["vs200"] > 0,
                  bool(m["golden"]), m["slope200"] is not None and m["slope200"] > 0]
    m["trend"] = sum(trend_bits)  # 0..4
    if bench and bench is not d:
        bt, ca, cb = align(d, bench)
        if len(ca) > 70:
            for key, n in (("rs1m", 21), ("rs3m", 63), ("rs6m", 126), ("rs1y", 252)):
                ra, rb = ret(ca, n), ret(cb, n)
                m[key] = (ra - rb) if (ra is not None and rb is not None) else None
            if len(ca) > 253:
                m["rsMom"] = (ca[-22] / ca[-253]) - (cb[-22] / cb[-253])
            m["rrg"] = rrg(bt, ca, cb)
            m["quad"] = quadrant(m["rrg"][-1] if m["rrg"] else None)
            rel = [x / y for x, y in zip(ca[-252:], cb[-252:])]
            m["relSeries"] = [round(v / rel[0] * 100, 2) for v in rel]
    # one year of weekly-ish points for sparklines + a daily year for the detail chart
    yr_t, yr_c = t[-253:], d["raw"][-253:]
    m["series"] = {"t": yr_t, "c": [round(v, 4) for v in yr_c]}
    m["ma50"] = [round(sum(d["raw"][i - 49:i + 1]) / 50, 4) if i >= 49 else None
                 for i in range(len(d["raw"]) - len(yr_c), len(d["raw"]))]
    m["ma200"] = [round(sum(d["raw"][i - 199:i + 1]) / 200, 4) if i >= 199 else None
                  for i in range(len(d["raw"]) - len(yr_c), len(d["raw"]))]
    m["long"] = {"t": t[::5], "c": [round(v, 4) for v in d["raw"][::5]]}
    return m


def pct_rank(values):
    """Percentile rank 0..100 of each value within the list (None stays None)."""
    idx = [i for i, v in enumerate(values) if v is not None]
    order = sorted(idx, key=lambda i: values[i])
    out = [None] * len(values)
    n = len(order)
    for r, i in enumerate(order):
        out[i] = 100 * r / (n - 1) if n > 1 else 50
    return out


WEIGHTS = {  # composite score recipe; percentile-ranked across the whole universe
    "mom121_rel": 0.25,  # 12-1 month momentum vs local benchmark
    "rs6m": 0.20,        # 6-month relative strength
    "rs3m": 0.10,        # 3-month relative strength
    "trend": 0.20,       # price vs 50/200-day averages and slope
    "sharpe": 0.15,      # 1-year risk-adjusted return
    "mdd": 0.10,         # shallower 1-year drawdown is better
}


def score_all(rows):
    cols = {
        "mom121_rel": [r["m"].get("rsMom") for r in rows],
        "rs6m": [r["m"].get("rs6m") for r in rows],
        "rs3m": [r["m"].get("rs3m") for r in rows],
        "trend": [r["m"]["trend"] + (r["m"]["vs200"] or 0) for r in rows],
        "sharpe": [r["m"]["sharpe"] for r in rows],
        "mdd": [r["m"]["mdd"] for r in rows],
    }
    ranks = {k: pct_rank(v) for k, v in cols.items()}
    for i, r in enumerate(rows):
        tot = wsum = 0.0
        parts = {}
        for k, w in WEIGHTS.items():
            v = ranks[k][i]
            parts[k] = None if v is None else round(v)
            if v is not None:
                tot += v * w; wsum += w
        s = tot / wsum if wsum else None
        r["m"]["score"] = round(s, 1) if s is not None else None
        r["m"]["parts"] = parts
        r["m"]["signal"] = (None if s is None else "Strong overweight" if s >= 80 else "Overweight" if s >= 60
                            else "Neutral" if s >= 40 else "Underweight" if s >= 20 else "Avoid")


def flags(m):
    f = []
    if m["rsi"] is not None and m["rsi"] >= 70: f.append(("Overbought", "warn"))
    if m["rsi"] is not None and m["rsi"] <= 30: f.append(("Oversold", "info"))
    if m["vs200"] is not None and m["vs200"] > 0.15: f.append(("Stretched vs 200d", "warn"))
    if m["offHigh"] > -0.02: f.append(("At 52w high", "pos"))
    if m["mdd"] < -0.25: f.append(("Deep drawdown", "neg"))
    if m["golden"] is False and m["vs200"] is not None and m["vs200"] < 0: f.append(("Downtrend", "neg"))
    return [{"label": a, "tone": b} for a, b in f]


# Business-cycle read from macro gauges. Deliberately simple and transparent.
CYCLE_FAVOURS = {
    "Early cycle": ["discr", "fin", "re", "indu", "tech", "mat"],
    "Mid cycle": ["tech", "comm", "indu", "fin"],
    "Late cycle": ["energy", "mat", "staples", "health", "util"],
    "Contraction": ["staples", "health", "util"],
}


def cycle_read(macro, spy):
    ev = {"Early cycle": 0.0, "Mid cycle": 0.0, "Late cycle": 0.0, "Contraction": 0.0}
    notes = []
    g = lambda s, k: (macro.get(s) or {}).get(k)
    tnx, irx = g("^TNX", "price"), g("^IRX", "price")
    vix = g("^VIX", "price")
    if tnx is not None and irx is not None:
        curve = tnx - irx
        curve_3m = None
        a, b = macro.get("^TNX"), macro.get("^IRX")
        if a and b and len(a["c"]) > 63 and len(b["c"]) > 63:
            curve_3m = curve - (a["c"][-64] - b["c"][-64])
        if curve < 0:
            ev["Late cycle"] += 1; ev["Contraction"] += 0.5
            notes.append(f"Yield curve inverted ({curve:+.2f} pts, 10Y minus 3M): classic late-cycle warning.")
        elif curve_3m is not None and curve_3m > 0.2:
            ev["Early cycle"] += 1
            notes.append(f"Yield curve steepening ({curve:+.2f} pts, {curve_3m:+.2f} over 3M): often seen as growth re-accelerates.")
        else:
            ev["Mid cycle"] += 0.7
            notes.append(f"Yield curve positive and stable ({curve:+.2f} pts).")
    cu, au = macro.get("HG=F"), macro.get("GC=F")
    if cu and au and len(cu["c"]) > 63 and len(au["c"]) > 63:
        cg = (cu["c"][-1] / au["c"][-1]) / (cu["c"][-64] / au["c"][-64]) - 1
        if cg > 0.03:
            ev["Early cycle"] += 0.7; ev["Mid cycle"] += 0.5
            notes.append(f"Copper/gold ratio up {cg:+.1%} over 3M: markets pricing stronger industrial demand.")
        elif cg < -0.03:
            ev["Contraction"] += 0.8; ev["Late cycle"] += 0.3
            notes.append(f"Copper/gold ratio down {cg:+.1%} over 3M: growth worries, defensive tilt.")
        else:
            ev["Mid cycle"] += 0.4
            notes.append(f"Copper/gold ratio flat ({cg:+.1%} over 3M).")
    oil = macro.get("CL=F")
    if oil and len(oil["c"]) > 126:
        o6 = oil["c"][-1] / oil["c"][-127] - 1
        if o6 > 0.15:
            ev["Late cycle"] += 0.8
            notes.append(f"Oil up {o6:+.0%} over 6M: inflation pressure, typical of late cycle.")
        elif o6 < -0.15:
            ev["Contraction"] += 0.3; ev["Early cycle"] += 0.3
            notes.append(f"Oil down {o6:+.0%} over 6M: easing input costs, weaker demand.")
    if vix is not None:
        if vix >= 25:
            ev["Contraction"] += 1
            notes.append(f"VIX at {vix:.1f}: elevated fear.")
        elif vix <= 16:
            ev["Mid cycle"] += 0.6
            notes.append(f"VIX at {vix:.1f}: calm markets.")
        else:
            notes.append(f"VIX at {vix:.1f}: normal range.")
    if spy:
        if spy["vs200"] is not None and spy["vs200"] < 0:
            ev["Contraction"] += 1
            notes.append("S&P 500 below its 200-day average: broad downtrend.")
        elif spy["vs200"] is not None and spy["r6m"] is not None:
            ev["Mid cycle"] += 0.6
            if spy["mdd"] < -0.15 and spy["r3m"] > 0.08:
                ev["Early cycle"] += 0.8
                notes.append("S&P 500 recovering sharply from a drawdown.")
            else:
                notes.append("S&P 500 above its 200-day average: broad uptrend intact.")
    tot = sum(ev.values()) or 1
    w = {k: v / tot for k, v in ev.items()}
    order = sorted(w, key=w.get, reverse=True)
    # when two phases score within 10 points, report the blend and favour both sets
    phases = [p for p in order if w[p] >= w[order[0]] - 0.10][:2]
    order_idx = list(CYCLE_FAVOURS)
    phases.sort(key=order_idx.index)
    if phases == ["Early cycle", "Contraction"]:  # the cycle wraps: contraction leads into early
        phases.reverse()
    label = phases[0] if len(phases) == 1 else f"{phases[0].split()[0]}-to-{phases[1].lower()}"
    fav = [k for p in phases for k in CYCLE_FAVOURS[p]]
    return {"phase": label, "primary": order[0], "phases": phases,
            "weights": {k: round(v, 3) for k, v in w.items()}, "notes": notes,
            "favoured": list(dict.fromkeys(fav)), "favours": CYCLE_FAVOURS}


def build():
    symbols = {g["bench"] for g in GROUPS} | {f[0] for g in GROUPS for f in g["funds"]} | {m[0] for m in MACRO}
    raw = fetch_all(sorted(symbols))
    irx = raw.get("^IRX", {})
    rf = (irx.get("price") or 4.0) / 100
    errors = [s for s, d in raw.items() if "error" in d or len(d.get("c", [])) < 60]

    macro = {}
    for sym, label in MACRO:
        d = raw.get(sym)
        if not d or sym in errors:
            continue
        c = d["c"]
        macro[sym] = {"label": label, "price": d["price"], "c": c[-260:],
                      "r1d": ret(c, 1), "r1m": ret(c, 21), "r3m": ret(c, 63), "r1y": ret(c, 252),
                      "spark": [round(v, 4) for v in c[-126:]]}

    rows, benches = [], {}
    for g in GROUPS:
        b = raw.get(g["bench"])
        bm = analyse(b, None, rf) if b and g["bench"] not in errors else None
        if bm:
            benches[g["id"]] = {"symbol": g["bench"], "name": g["bench_name"], "m": bm}
        for sym, name, key in g["funds"]:
            d = raw.get(sym)
            if not d or sym in errors:
                continue
            m = analyse(d, b if bm else None, rf)
            if m:
                rows.append({"symbol": sym, "name": name, "key": key, "group": g["id"],
                             "fund": d["name"], "ccy": d["ccy"], "m": m})
    score_all(rows)
    hold = holdings.load([r["symbol"] for r in rows])
    for r in rows:
        r["m"]["flags"] = flags(r["m"])
        r["holdings"] = hold["funds"].get(r["symbol"])
    spy = benches.get("us", {}).get("m")
    cyc = cycle_read(macro, spy)
    for sym in macro:
        macro[sym].pop("c", None)
    last = max((d.get("mtime") or 0) for d in raw.values() if "error" not in d)
    return {
        "generated": time.time(), "marketTime": last, "rf": rf,
        "groups": [{k: g[k] for k in ("id", "name", "bench", "bench_name", "ccy")} for g in GROUPS],
        "benches": benches, "rows": rows, "macro": macro, "cycle": cyc,
        "weights": WEIGHTS, "errors": errors, "holdingsAt": hold["fetched"],
    }

# ---------------------------------------------------------------- server

_cache = {"at": 0, "body": None}
_lock = threading.Lock()


def get_data(force=False):
    with _lock:
        if force or not _cache["body"] or time.time() - _cache["at"] > CACHE_SECONDS:
            t0 = time.time()
            data = build()
            data["buildSeconds"] = round(time.time() - t0, 1)
            _cache["body"] = json.dumps(_clean(data), separators=(",", ":"), allow_nan=False).encode()
            _cache["at"] = time.time()
            print(f"[{datetime.now():%H:%M:%S}] refreshed {len(data['rows'])} funds in "
                  f"{data['buildSeconds']}s; missing: {data['errors'] or 'none'}", flush=True)
        return _cache["body"]


def _clean(o):
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path == "/api/data":
                body = get_data(force="force" in parse_qs(u.query))
                self._send(200, body, "application/json")
            elif u.path in ("/", "/index.html"):
                self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain")
        except Exception as e:  # noqa: BLE001
            self._send(500, json.dumps({"error": str(e)}).encode(), "application/json")

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if "--check" in sys.argv:
        d = json.loads(get_data())
        print("rows", len(d["rows"]), "errors", d["errors"], "cycle", d["cycle"]["phase"])
        sys.exit()
    lan = "--lan" in sys.argv  # also serve other devices on the same Wi-Fi (e.g. your phone)
    print(f"Sector Compass running at http://localhost:{PORT}  (Ctrl+C to stop)", flush=True)
    if lan:
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))  # no packets sent; just picks the Wi-Fi interface
                ip = s.getsockname()[0]
            print(f"\n  On your phone (same Wi-Fi), open:  http://{ip}:{PORT}\n", flush=True)
        except OSError:
            print("  Could not detect this PC's network address; run ipconfig to find it.", flush=True)
    threading.Thread(target=get_data, daemon=True).start()  # warm the cache
    ThreadingHTTPServer(("0.0.0.0" if lan else "127.0.0.1", PORT), Handler).serve_forever()
