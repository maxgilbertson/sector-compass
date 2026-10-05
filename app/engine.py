"""Shared engine behind Sector Compass (sectors) and World Compass (countries).

Fetching, point-in-time metrics, the composite score, score history and the
backtest all live here. The live score, the history and the backtest call the
same `Track.inputs()` and `score()` functions, so the backtest tests exactly
the recipe the pages show.
"""
import bisect
import json
import math
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SectorCompass/1.0"}
RANGE = "10y"          # ten years, so the backtest covers the 2018, 2020 and 2022 sell-offs
MEMO_SECONDS = 120     # the two pages share symbols; don't download the same one twice per build
_memo, _memo_lock = {}, threading.Lock()

# ---------------------------------------------------------------- fetching

def _drop_spikes(pts, max_len=3):
    """Drop short glitches: up to 3 bars that jump more than 35% and then snap back.

    Yahoo's Tokyo data has a few (e.g. TOPIX at a tenth of its price on 30-31 March
    2026); left in, one bad print dominates a month of backtest returns. Real crashes
    and rallies don't snap back within days, so they are kept.
    """
    out, k = [], 0
    while k < len(pts):
        if out and out[-1][2]:
            base = out[-1][2]
            if abs(pts[k][2] / base - 1) > 0.35:
                back = next((j for j in range(k + 1, min(k + 1 + max_len, len(pts)))
                             if abs(pts[j][2] / base - 1) < 0.15), None)
                if back is not None:
                    k = back
                    continue
        out.append(pts[k])
        k += 1
    return out


def fetch(symbol, rng=RANGE):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(symbol)}"
           f"?range={rng}&interval=1d&includeAdjustedClose=true")
    err = "no data"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
                res = json.load(r)["chart"]["result"][0]
            ind = res["indicators"]
            closes = (ind.get("adjclose") or [{}])[0].get("adjclose") or ind["quote"][0]["close"]
            pts = _drop_spikes([(t, c, rc) for t, c, rc in zip(res.get("timestamp") or [], closes, ind["quote"][0]["close"])
                                if c is not None and rc is not None])
            meta = res["meta"]
            off = meta.get("gmtoffset") or 0
            t, c, raw = [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts]
            px, mt = meta.get("regularMarketPrice"), meta.get("regularMarketTime")
            # Safeguard: always score the latest trade, even if Yahoo's daily bar hasn't caught up with it.
            if px and mt and t and mt >= t[-1]:
                adj = c[-1] / raw[-1] if raw[-1] else 1.0
                if (mt + off) // 86400 == (t[-1] + off) // 86400:
                    raw[-1], c[-1] = px, px * adj
                elif mt - t[-1] > 3600:
                    t.append(mt); raw.append(px); c.append(px * adj)
            period = ((meta.get("currentTradingPeriod") or {}).get("regular") or {})
            return {
                "symbol": symbol, "t": t, "c": c, "raw": raw, "off": off,
                "price": px, "ccy": meta.get("currency"), "mtime": mt,
                "name": meta.get("longName") or meta.get("shortName") or symbol,
                "tz": meta.get("exchangeTimezoneName"),
                "period": {"start": period.get("start"), "end": period.get("end")},
            }
        except Exception as e:  # noqa: BLE001 - network hiccups are retried then reported
            err = str(e)
            time.sleep(0.6 * (attempt + 1))
    return {"symbol": symbol, "error": err}


def fetch_all(symbols):
    now, out, todo = time.time(), {}, []
    with _memo_lock:
        for s in symbols:
            hit = _memo.get(s)
            if hit and now - hit[0] < MEMO_SECONDS:
                out[s] = hit[1]
            else:
                todo.append(s)
    with ThreadPoolExecutor(max_workers=12) as ex:
        for d in ex.map(fetch, todo):
            out[d["symbol"]] = d
            if "error" not in d:
                with _memo_lock:
                    _memo[d["symbol"]] = (now, d)
    return out


def ffill(d, rate):
    """`rate`'s closes carried forward onto d's trading days (None before rate's history starts)."""
    return Track({"t": d["t"], "c": d["c"], "raw": d["raw"], "off": d.get("off", 0)}, rate).b


def cross(num, den):
    """num / den on num's dates, e.g. GBP per EUR = (GBP per USD) / (EUR per USD)."""
    dv = ffill(num, den)
    keep = [k for k, v in enumerate(dv) if v]
    return {"t": [num["t"][k] for k in keep], "c": [num["c"][k] / dv[k] for k in keep],
            "raw": [num["raw"][k] / dv[k] for k in keep], "off": num.get("off", 0)}


def invert(rate):
    return {"t": rate["t"], "c": [1 / v for v in rate["c"]], "raw": [1 / v for v in rate["raw"]], "off": rate.get("off", 0)}


def convert(d, rate):
    """Price series d re-expressed in another currency: multiply by `rate` (target units per d's unit)."""
    if rate is None:
        return d
    r = ffill(d, rate)
    keep = [k for k, v in enumerate(r) if v]
    return {"t": [d["t"][k] for k in keep], "c": [d["c"][k] * r[k] for k in keep],
            "raw": [d["raw"][k] * r[k] for k in keep], "off": d.get("off", 0),
            "price": d["raw"][-1] * r[-1] if r and r[-1] else None}


def usable(d, n=60):
    return bool(d) and "error" not in d and len(d.get("c", [])) >= n


def rate_at(irx):
    """Risk-free rate (US 3-month bill) as it stood on any date, for point-in-time Sharpe ratios."""
    if not usable(irx):
        return lambda ts: 0.04
    t, v = irx["t"], irx["raw"]
    return lambda ts: v[max(0, bisect.bisect_right(t, ts) - 1)] / 100

# ---------------------------------------------------------------- point-in-time metrics

class Track:
    """One price history, prepared so any metric can be read as of any past day in O(1).

    The benchmark is forward-filled onto this track's own trading days (by local
    date), so relative measures compare the same days even across exchange calendars.
    """

    def __init__(self, d, bench=None):
        self.t, self.c, self.raw, self.off = d["t"], d["c"], d["raw"], d.get("off", 0)
        self.n = n = len(self.c)
        self._ps = self._prefix(self.c)
        self._pr = self._prefix(d["raw"])
        r = [0.0] + [self.c[i] / self.c[i - 1] - 1 for i in range(1, n)]
        self._r1, self._r2 = self._prefix(r), self._prefix([x * x for x in r])
        self.b = self._ffill(bench) if bench and bench is not d else None

    @staticmethod
    def _prefix(xs):
        out, s = [0.0], 0.0
        for x in xs:
            s += x; out.append(s)
        return out

    def _ffill(self, bench):
        boff = bench.get("off", 0)
        bdays, bc, out, j = [(ts + boff) // 86400 for ts in bench["t"]], bench["c"], [], -1
        for ts in self.t:
            day = (ts + self.off) // 86400
            while j + 1 < len(bdays) and bdays[j + 1] <= day:
                j += 1
            out.append(bc[j] if j >= 0 else None)
        return out

    def at(self, ts):
        """Index of the last bar on or before timestamp `ts` (-1 if none)."""
        return bisect.bisect_right(self.t, ts) - 1

    def sma(self, i, n, raw=False):
        if i + 1 < n or i < 0:
            return None
        ps = self._pr if raw else self._ps
        return (ps[i + 1] - ps[i + 1 - n]) / n

    def ret(self, i, n):
        return self.c[i] / self.c[i - n] - 1 if 0 <= i - n and self.c[i - n] else None

    def rel(self, i, n):
        """Return over n bars minus the benchmark's return over the same bars."""
        if self.b is None or i - n < 0:
            return None
        b0, b1 = self.b[i - n], self.b[i]
        if not b0 or not b1:
            return None
        return self.c[i] / self.c[i - n] - b1 / b0

    def vol(self, i, n):
        """Annualised volatility of the last n daily returns ending at bar i."""
        if i - n + 1 < 1:
            return None
        s = self._r1[i + 1] - self._r1[i + 1 - n]
        s2 = self._r2[i + 1] - self._r2[i + 1 - n]
        return math.sqrt(max((s2 - s * s / n) / (n - 1), 0.0) * 252)

    def mdd(self, i, n=252):
        peak, worst = self.c[max(0, i - n)], 0.0
        for x in self.c[max(0, i - n):i + 1]:
            if x > peak:
                peak = x
            elif x / peak - 1 < worst:
                worst = x / peak - 1
        return worst

    def inputs(self, i, rf):
        """Every ingredient of the score as it stood at bar i. None until a year of history exists."""
        if i < 252:
            return None
        c = self.c
        m50, m200, m200_prev = self.sma(i, 50), self.sma(i, 200), self.sma(i - 21, 200)
        vs50, vs200 = c[i] / m50 - 1, c[i] / m200 - 1
        slope = m200 / m200_prev - 1
        r1y, vol1y = c[i] / c[i - 252] - 1, self.vol(i, 252)
        x = {
            "vs50": vs50, "vs200": vs200, "golden": m50 > m200, "slope200": slope,
            "trend": int(vs50 > 0) + int(vs200 > 0) + int(m50 > m200) + int(slope > 0),
            "r1y": r1y, "vol1y": vol1y, "sharpe": (r1y - rf) / vol1y if vol1y else None,
            "mdd": self.mdd(i), "rs3m": self.rel(i, 63), "rs6m": self.rel(i, 126), "rsMom": None,
        }
        if self.b is not None and self.b[i - 21] and self.b[i - 252]:
            # 12-1 momentum: the year to last month, skipping the most recent month (it tends to reverse)
            x["rsMom"] = c[i - 21] / c[i - 252] - self.b[i - 21] / self.b[i - 252]
        return x

# ---------------------------------------------------------------- the score

WEIGHTS = {  # composite score recipe; each ingredient is percentile-ranked across the whole universe
    "mom121_rel": 0.25,  # 12-1 month momentum vs local benchmark
    "rs6m": 0.20,        # 6-month relative strength
    "rs3m": 0.10,        # 3-month relative strength
    "trend": 0.20,       # price vs 50/200-day averages and slope
    "sharpe": 0.15,      # 1-year risk-adjusted return
    "mdd": 0.10,         # shallower 1-year drawdown is better
}
COMPONENTS = {
    "mom121_rel": lambda x: x["rsMom"],
    "rs6m": lambda x: x["rs6m"],
    "rs3m": lambda x: x["rs3m"],
    "trend": lambda x: x["trend"] + x["vs200"],
    "sharpe": lambda x: x["sharpe"],
    "mdd": lambda x: x["mdd"],
}


def pct_rank(values):
    """Percentile rank 0..100 of each value within the list (None stays None)."""
    idx = sorted((i for i, v in enumerate(values) if v is not None), key=lambda i: values[i])
    out, n = [None] * len(values), len(idx)
    for r, i in enumerate(idx):
        out[i] = 100 * r / (n - 1) if n > 1 else 50.0
    return out


def score(inputs, weights=None):
    """Cross-sectional composite for one date: [(score, parts)] aligned with `inputs`."""
    weights = weights or WEIGHTS
    ranks = {k: pct_rank([f(x) if x else None for x in inputs]) for k, f in COMPONENTS.items() if k in weights}
    out = []
    for i, x in enumerate(inputs):
        if x is None:
            out.append((None, {}))
            continue
        tot = wsum = 0.0
        parts = {}
        for k, w in weights.items():
            v = ranks[k][i]
            parts[k] = None if v is None else round(v)
            if v is not None:
                tot += v * w; wsum += w
        out.append((round(tot / wsum, 1) if wsum else None, parts))
    return out


def signal(s):
    return (None if s is None else "Strong overweight" if s >= 80 else "Overweight" if s >= 60
            else "Neutral" if s >= 40 else "Underweight" if s >= 20 else "Avoid")


def score_history(tracks, rf_at, current, weeks=13):
    """Each fund's score at the previous close and at weekly steps back, ranked as of those dates."""
    last = max(tr.t[-1] for tr in tracks)
    prev = score([tr.inputs(tr.n - 2, rf_at(tr.t[tr.n - 2])) for tr in tracks])
    cuts = [last - w * 7 * 86400 for w in range(weeks - 1, 0, -1)]
    past = [score([tr.inputs(tr.at(cut), rf_at(cut)) for tr in tracks]) for cut in cuts]
    out = []
    for k, now in enumerate(current):
        hist = [p[k][0] for p in past] + [now]
        d = lambda old: None if (now is None or old is None) else round(now - old, 1)
        out.append({"d1": d(prev[k][0]), "d1w": d(hist[-2]), "d1m": d(hist[-5]), "hist": hist})
    return out, cuts + [last]


def apply_scores(rows, tracks, rf_at):
    """Score every row now, add its score history, flags and signal. Rows and tracks are aligned."""
    now = max(tr.t[-1] for tr in tracks)
    sc = score([tr.inputs(tr.n - 1, rf_at(now)) for tr in tracks])
    hist, cuts = score_history(tracks, rf_at, [s for s, _ in sc])
    for r, (s, parts), h in zip(rows, sc, hist):
        r["m"].update(score=s, parts=parts, signal=signal(s), **h)
        r["m"]["flags"] = flags(r["m"])
    return cuts

# ---------------------------------------------------------------- display metrics

def rsi(c, n=14):
    if len(c) < n * 3:
        return None
    diffs = [c[i] - c[i - 1] for i in range(len(c) - n * 3, len(c))]
    ag = sum(max(d, 0) for d in diffs[:n]) / n
    al = sum(max(-d, 0) for d in diffs[:n]) / n
    for d in diffs[n:]:
        ag = (ag * (n - 1) + max(d, 0)) / n
        al = (al * (n - 1) + max(-d, 0)) / n
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def rrg(c, b):
    """Relative Rotation Graph coordinates (JdK-style approximation), weekly tail of 6 weeks.

    RS-Ratio: relative strength vs its own 50-day average, centred on 100.
    RS-Momentum: rate of change of RS-Ratio over 10 days, centred on 100.
    """
    pairs = [(x, y) for x, y in zip(c[-320:], b[-320:]) if y]
    if len(pairs) < 120:
        return None
    rs, a = [], 2 / (10 + 1)  # 10-day EMA takes out daily noise before measuring the trend
    for x, y in pairs:
        v = x / y
        rs.append(v if not rs else rs[-1] + a * (v - rs[-1]))
    ps = Track._prefix(rs)
    ratio = [None if i < 49 else 100 * rs[i] / ((ps[i + 1] - ps[i - 49]) / 50) for i in range(len(rs))]
    tail = []
    for k in range(6):
        i = len(rs) - 1 - k * 5
        j = i - 10
        if ratio[i] is None or j < 0 or ratio[j] is None:
            break
        tail.append([round(ratio[i], 3), round(100 * ratio[i] / ratio[j], 3)])
    return list(reversed(tail))


def quadrant(pt):
    if not pt:
        return None
    x, y = pt
    if x >= 100:
        return "Leading" if y >= 100 else "Weakening"
    return "Improving" if y >= 100 else "Lagging"


def period_returns(tr, i=None):
    """Returns over the standard periods, as of bar i (default: the latest)."""
    i = tr.n - 1 if i is None else i
    t, c = tr.t, tr.c
    ytd0 = tr.at(datetime(datetime.fromtimestamp(t[i], timezone.utc).year, 1, 1, tzinfo=timezone.utc).timestamp() - 1)
    ann = lambda n: None if tr.ret(i, n) is None else (1 + tr.ret(i, n)) ** (252 / n) - 1
    return {"r1d": tr.ret(i, 1), "r1w": tr.ret(i, 5), "r1m": tr.ret(i, 21), "r3m": tr.ret(i, 63),
            "r6m": tr.ret(i, 126), "ytd": c[i] / c[ytd0] - 1 if ytd0 >= 0 else None,
            "r1y": tr.ret(i, 252), "r3y": ann(756), "r5y": ann(1260)}


def analyse(tr, d, rf):
    """Everything the page shows for one fund, as of its latest bar."""
    if tr.n < 60:
        return None
    i, c, t, raw = tr.n - 1, tr.c, tr.t, tr.raw
    x = tr.inputs(i, rf) or {"trend": 0, "vs50": None, "vs200": None, "golden": None, "slope200": None,
                             "r1y": None, "vol1y": None, "sharpe": None, "mdd": tr.mdd(i),
                             "rs3m": None, "rs6m": None, "rsMom": None}
    yr = raw[-252:]
    m = {
        **x,
        **{k: v for k, v in period_returns(tr).items() if k != "r1y"},
        "price": d.get("price") or raw[-1],
        "mom121": c[i - 21] / c[i - 252] - 1 if i >= 252 else None,
        "vol": tr.vol(i, 63), "rsi": rsi(c),
        "offHigh": raw[-1] / max(yr) - 1, "offLow": raw[-1] / min(yr) - 1,
    }
    if tr.b is not None:
        m["rs1m"], m["rs1y"] = tr.rel(i, 21), tr.rel(i, 252)
        m["rrg"] = rrg(c, tr.b)
        m["quad"] = quadrant(m["rrg"][-1] if m["rrg"] else None)
        rel = [a / b for a, b in zip(c[-252:], tr.b[-252:]) if b]
        m["relSeries"] = [round(v / rel[0] * 100, 2) for v in rel] if rel else None
    lo = max(0, tr.n - 253)
    m["series"] = {"t": t[lo:], "c": [round(v, 4) for v in raw[lo:]]}
    m["ma50"] = [None if tr.sma(k, 50, True) is None else round(tr.sma(k, 50, True), 4) for k in range(lo, tr.n)]
    m["ma200"] = [None if tr.sma(k, 200, True) is None else round(tr.sma(k, 200, True), 4) for k in range(lo, tr.n)]
    step = list(range(tr.n - 1, -1, -5))[::-1]  # weekly points over the full ten years for the long chart
    m["long"] = {"t": [t[k] for k in step], "c": [round(raw[k], 4) for k in step]}
    return m


def flags(m):
    """Warning chips, each with a plain label and a tooltip that explains the rule behind it."""
    f = []
    rsi, vs200 = m.get("rsi"), m.get("vs200")
    if rsi is not None and rsi >= 70:
        f.append(("Rose fast", "warn", f"RSI {rsi:.0f}: it has risen unusually fast over the last 3 weeks or so ('overbought'). Sharp rises often pause."))
    if rsi is not None and rsi <= 30:
        f.append(("Fell fast", "info", f"RSI {rsi:.0f}: it has fallen unusually fast over the last 3 weeks or so ('oversold'). Short bounces are common."))
    if vs200 is not None and vs200 > 0.15:
        f.append(("Far above trend", "warn", f"The price is {vs200:.0%} above its 200-day (about 10-month) average. Gaps this big often narrow."))
    if m.get("offHigh") is not None and m["offHigh"] > -0.02:
        f.append(("Near 1-yr high", "pos", "Within 2% of its highest price of the past year."))
    if (m.get("mdd") or 0) < -0.25:
        f.append(("Big fall this year", "neg", f"It dropped {abs(m['mdd']):.0%} from a high at some point in the past year."))
    if m.get("golden") is False and vs200 is not None and vs200 < 0:
        f.append(("Downtrend", "neg", "The price is below its 200-day (about 10-month) average, and the 50-day average is below the 200-day."))
    return [{"label": a, "tone": b, "tip": c} for a, b, c in f]


# Commodity futures are quoted per barrel, troy ounce and pound; the pages show them per litre, gram and tonne (1,000 kg).
METRIC = {"CL=F": 1 / 158.987294928, "GC=F": 1 / 31.1034768, "HG=F": 1000 / 0.45359237}


def macro_block(raw, items):
    """Macro gauges: level, changes and a 6-month sparkline. Keeps `c` (as quoted) for rule-based reads."""
    out = {}
    for sym, label in items:
        d = raw.get(sym)
        if not usable(d):
            continue
        tr, c, k = Track(d), d["c"], METRIC.get(sym, 1)
        i = tr.n - 1
        out[sym] = {"label": label, "price": d["price"] * k, "c": c[-260:],
                    "r1d": tr.ret(i, 1), "r1m": tr.ret(i, 21), "r3m": tr.ret(i, 63), "r1y": tr.ret(i, 252),
                    "vs200": c[i] / tr.sma(i, 200) - 1 if tr.sma(i, 200) else None,
                    "spark": [round(v * k, 5) for v in c[-126:]]}
    return out


def corr_beta(tr, weeks=52):
    """Correlation and beta of weekly returns vs the benchmark over the past year."""
    if tr.b is None or tr.n < weeks * 5 + 1:
        return None, None
    idx = list(range(tr.n - 1 - weeks * 5, tr.n, 5))
    a = [tr.c[j] / tr.c[k] - 1 for k, j in zip(idx, idx[1:])]
    b = [tr.b[j] / tr.b[k] - 1 for k, j in zip(idx, idx[1:]) if tr.b[k]]
    if len(a) != len(b) or len(a) < 20:
        return None, None
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va, vb = sum((x - ma) ** 2 for x in a), sum((y - mb) ** 2 for y in b)
    if not va or not vb:
        return None, None
    return cov / math.sqrt(va * vb), cov / vb

# ---------------------------------------------------------------- backtest

def _spearman(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 5:
        return None
    rx, ry = pct_rank([p[0] for p in pairs]), pct_rank([p[1] for p in pairs])
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx, vy = sum((a - mx) ** 2 for a in rx), sum((b - my) ** 2 for b in ry)
    return cov / math.sqrt(vx * vy) if vx and vy else None


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _tstat(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 3:
        return None
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
    return m / (sd / math.sqrt(len(xs))) if sd else None


def _month_ends(t0, t1):
    d = datetime.fromtimestamp(t0, timezone.utc)
    y, mo, out = d.year, d.month, []
    while True:
        y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
        cut = datetime(y, mo, 1, tzinfo=timezone.utc).timestamp() - 1
        if cut > t1:
            return out
        out.append(cut)


COST_PER_TRADE = 0.0015  # assumed one-way cost of a trade: bid/ask spread plus commission


def _summary(months):
    """Headline statistics for a run of backtest months."""
    if len(months) < 6:
        return None
    sp = [m["spread"] for m in months]
    return {"from": months[0]["t"], "to": months[-1]["t"], "months": len(months),
            "topAnn": _mean([m["top"] for m in months]) * 12, "botAnn": _mean([m["bot"] for m in months]) * 12,
            "spreadAnn": _mean(sp) * 12, "spreadT": _tstat(sp), "hit": sum(s > 0 for s in sp) / len(sp),
            "topNetAnn": _mean([m["top"] - m["cost"] for m in months]) * 12}


def backtest(tracks, rf_at, min_funds=8, weights=None, cost=COST_PER_TRADE):
    """Monthly walk-forward test of the live score.

    At each month-end, every fund is scored using only data up to that day (the
    same `inputs()` and `score()` as the live page). We then measure what each
    fund did over the following month relative to its own benchmark, and ask
    whether higher scores were followed by better relative returns.
    """
    last = max(tr.t[-1] for tr in tracks)
    cuts = _month_ends(min(tr.t[0] for tr in tracks), last)
    months, curves = [], {"t": [], "top": [1.0], "mid": [1.0], "bot": [1.0]}
    bands = {b: [] for b in ("Strong overweight", "Overweight", "Neutral", "Underweight", "Avoid")}
    comp_ic = {k: [] for k in COMPONENTS}
    quint = [[] for _ in range(5)]
    fwd_spread = {3: [], 6: []}
    prev_top = None
    turnover = []

    def fwd(tr, i, j):
        if i < 0 or j <= i:
            return None
        r = tr.c[j] / tr.c[i] - 1
        if tr.b is None:
            return r
        return r - (tr.b[j] / tr.b[i] - 1) if tr.b[i] and tr.b[j] else None

    for k, cut in enumerate(cuts[:-1]):
        idx = [tr.at(cut) for tr in tracks]
        inputs = [tr.inputs(i, rf_at(cut)) if i >= 0 else None for tr, i in zip(tracks, idx)]
        if sum(x is not None for x in inputs) < min_funds:
            continue
        sc = [s for s, _ in score(inputs, weights)]
        nxt = [tr.at(cuts[k + 1]) for tr in tracks]
        f1 = [fwd(tr, i, j) if s is not None else None for tr, i, j, s in zip(tracks, idx, nxt, sc)]
        live = [(s, r, n) for n, (s, r) in enumerate(zip(sc, f1)) if s is not None and r is not None]
        if len(live) < min_funds:
            continue
        live.sort(key=lambda p: -p[0])
        q = [[] for _ in range(5)]
        for rank, (s, r, n) in enumerate(live):
            q[min(4, rank * 5 // len(live))].append(r)
        qm = [sum(g) / len(g) for g in q]
        for g, v in zip(quint, qm):
            g.append(v)
        for s, r, n in live:
            bands[signal(s)].append(r)
        top = {n for rank, (s, r, n) in enumerate(live) if rank * 5 // len(live) == 0}
        swapped = 1.0 if prev_top is None else (1 - len(top & prev_top) / len(top) if top else 0.0)
        if prev_top is not None and top:
            turnover.append(swapped)
        prev_top = top
        # swapping a share of the portfolio means selling that share and buying its replacement
        month_cost = swapped * 2 * cost if len(turnover) else 0.0
        for key, f in COMPONENTS.items():
            comp_ic[key].append(_spearman([f(x) if x else None for x in inputs], f1))
        for h in (3, 6):
            if k + h < len(cuts):
                fh = [fwd(tr, i, tr.at(cuts[k + h])) if s is not None else None for tr, i, s in zip(tracks, idx, sc)]
                lh = sorted([(s, r) for s, r in zip(sc, fh) if s is not None and r is not None], key=lambda p: -p[0])
                if len(lh) >= min_funds:
                    cut5 = max(1, len(lh) // 5)
                    fwd_spread[h].append(_mean([r for _, r in lh[:cut5]]) - _mean([r for _, r in lh[-cut5:]]))
        allm = sum(r for _, r, _ in live) / len(live)
        months.append({"t": cut, "top": qm[0], "bot": qm[4], "all": allm, "spread": qm[0] - qm[4], "cost": month_cost,
                       "ic": _spearman([p[0] for p in live], [p[1] for p in live]), "n": len(live)})
        curves["t"].append(cuts[k + 1])
        curves["top"].append(curves["top"][-1] * (1 + qm[0]))
        curves["mid"].append(curves["mid"][-1] * (1 + allm))
        curves["bot"].append(curves["bot"][-1] * (1 + qm[4]))

    if len(months) < 12:
        return None
    spreads = [m["spread"] for m in months]
    ics = [m["ic"] for m in months]
    recent = spreads[-12:]
    peak, dd = 1.0, 0.0
    level = 1.0
    for s in spreads:
        level *= 1 + s
        peak = max(peak, level)
        dd = min(dd, level / peak - 1)
    worst = min(months, key=lambda m: m["spread"])
    curves["t"] = [months[0]["t"]] + curves["t"]
    return {
        "from": months[0]["t"], "to": curves["t"][-1], "months": len(months),
        "avgFunds": round(sum(m["n"] for m in months) / len(months), 1),
        "topAnn": _mean(quint[0]) * 12, "botAnn": _mean(quint[4]) * 12, "allAnn": _mean([m["all"] for m in months]) * 12,
        "spreadAnn": _mean(spreads) * 12, "spreadT": _tstat(spreads),
        "hit": sum(s > 0 for s in spreads) / len(spreads),
        "ic": _mean(ics), "icT": _tstat(ics), "icHit": sum((x or 0) > 0 for x in ics) / len(ics),
        "recentSpreadAnn": _mean(recent) * 12, "recentHit": sum(s > 0 for s in recent) / len(recent),
        "spreadMaxDD": dd, "worstMonth": {"t": worst["t"], "spread": worst["spread"]},
        "fwd3": _mean(fwd_spread[3]), "fwd6": _mean(fwd_spread[6]),
        "turnover": _mean(turnover),
        "costPerTrade": cost, "costAnn": _mean([m["cost"] for m in months]) * 12,
        "topNetAnn": _mean([m["top"] - m["cost"] for m in months]) * 12,
        # the stricter check: does the result hold in both halves of the period, not just on average?
        "halves": [_summary(months[:len(months) // 2]), _summary(months[len(months) // 2:])],
        "quintiles": [_mean(g) * 12 for g in quint],
        "bands": {b: {"ann": _mean(v) * 12 if v else None, "n": len(v),
                      "hit": sum(x > 0 for x in v) / len(v) if v else None} for b, v in bands.items()},
        "components": {k: {"ic": _mean(v), "t": _tstat(v)} for k, v in comp_ic.items()},
        "curves": {k: [round(x, 5) for x in v] if k != "t" else v for k, v in curves.items()},
        "spreadByMonth": [[m["t"], round(m["spread"], 5)] for m in months],
    }


def clean(o):
    """Make a structure JSON-safe (NaN and infinity become null)."""
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    return o
