"""Cycles: cyclical stock-market indices (indices, not funds) and where each one is in its cycle.

Industries such as mining, oil, banks, housebuilding and chips rise and fall with the economy and with commodity
prices, often by 40% or more. For each index this measures how far it is below its highest point of the past five
years, whether it is above or below its five-year average (the middle of its recent cycle), and whether it has
turned up (above its 200-day average) or is still falling. It also lists the index's past big falls and what came
after them, and tests whether buying in a dip has paid off (dip_test, fixed in advance: see cycles_test.py).

Data: CNBC's daily closing levels. These are price indices, so dividends are not included. The full history is
downloaded once a day and kept in data/cycles_cache.json; each build adds the last few weeks.
"""
import bisect
import json
import math
import random
import time
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import engine

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "cycles_cache.json"
UA = {"User-Agent": "SectorCompass/1.0 (personal tracker)"}
DAY = 86400
YEAR = 365.25 * DAY
FULL_EVERY = 20 * 3600  # re-download the whole history this often; in between, only the last few weeks

REGIONS = {
    "uk": {"name": "UK", "market": ".FTAS", "marketName": "FTSE All-Share", "ccy": "GBP"},
    "europe": {"name": "Europe", "market": ".STOXX", "marketName": "STOXX Europe 600", "ccy": "EUR"},
    "us": {"name": "US", "market": ".SPX", "marketName": "S&P 500", "ccy": "USD"},
}

DRIVES = {
    "metals": "Metal prices, above all copper and iron ore, which follow building and factory demand, especially in China.",
    "gold": "The gold and silver prices. Miners' profits rise faster than the metal when it climbs, and fall faster when it drops.",
    "oil": "Oil and gas prices.",
    "oilserv": "How much oil companies spend on drilling, which follows the oil price.",
    "banks": "The economy, interest rates and how many loans go bad.",
    "homes": "House prices, mortgage rates and how many homes are being built.",
    "build": "Building and infrastructure spending.",
    "eng": "Business investment and factory activity.",
    "transport": "Trade and freight volumes, and fuel costs.",
    "chem": "Factory demand, and energy and raw-material costs.",
    "travel": "Consumer spending and fuel costs; shocks such as the pandemic hit it hard.",
    "retail": "Shoppers' spending power: wages, prices and interest rates.",
    "autos": "Car sales, which follow consumer confidence and interest rates, and trade disputes.",
    "chips": "The boom-and-bust cycle of chip demand and stockpiles, and spending on AI.",
}

# The cyclical indices, chosen in advance as the classic boom-and-bust industries (fixed before the dip test ran).
# buy: the nearest fund on IBKR, (ticker, exchange, fund name, "same" | "similar", what differs); None = no fund tracks it.
_EXV = lambda t, n: (t, "Xetra", f"iShares STOXX Europe 600 {n} UCITS ETF (DE)", "same", "")
INDICES = [
    # UK: FTSE 350 sector indices (ICB codes)
    (".FTNMX551020", "uk-mining", "Mining", "FTSE 350 Industrial Metals and Mining", "uk", "metals",
     "The big metal miners: what is usually called the FTSE 350 Mining index.", "Rio Tinto, Glencore, Anglo American and Antofagasta", None),
    (".FTNMX601010", "uk-oil", "Oil & gas", "FTSE 350 Oil, Gas and Coal", "uk", "oil",
     "Oil and gas producers.", "Shell and BP", None),
    (".FTNMX301010", "uk-banks", "Banks", "FTSE 350 Banks", "uk", "banks",
     "The big UK-listed banks.", "HSBC, Barclays, Lloyds, NatWest and Standard Chartered", None),
    (".FTNMX402020", "uk-homes", "Housebuilders", "FTSE 350 Household Goods and Home Construction", "uk", "homes",
     "Mostly the big housebuilders.", "Barratt Redrow, Persimmon, Berkeley and Taylor Wimpey", None),
    (".FTNMX501010", "uk-build", "Construction & materials", "FTSE 350 Construction and Materials", "uk", "build",
     "Builders and makers of building materials.", "", None),
    (".FTNMX502040", "uk-eng", "Industrial engineering", "FTSE 350 Industrial Engineering", "uk", "eng",
     "Makers of machinery and industrial equipment.", "", None),
    (".FTNMX502060", "uk-transport", "Industrial transport", "FTSE 350 Industrial Transportation", "uk", "transport",
     "Freight, shipping, delivery and equipment-leasing companies.", "", None),
    (".FTNMX552010", "uk-chem", "Chemicals", "FTSE 350 Chemicals", "uk", "chem",
     "Chemical makers.", "Croda and Johnson Matthey", None),
    (".FTNMX405010", "uk-travel", "Travel & leisure", "FTSE 350 Travel and Leisure", "uk", "travel",
     "Airlines, hotels, restaurants, caterers and betting firms.", "IAG (British Airways), Compass, InterContinental Hotels and easyJet", None),
    (".FTNMX404010", "uk-retail", "Retailers", "FTSE 350 Retailers", "uk", "retail",
     "Shops and online retailers.", "Next, JD Sports and Kingfisher", None),
    # Europe: STOXX Europe 600 sector indices, each tracked exactly by an iShares fund on Xetra
    (".SXPP", "eu-resources", "Basic resources", "STOXX Europe 600 Basic Resources", "europe", "metals",
     "Miners, steelmakers, and paper and forestry companies.", "Rio Tinto, Glencore and Anglo American", _EXV("EXV6", "Basic Resources")),
    (".SXAP", "eu-autos", "Cars & parts", "STOXX Europe 600 Automobiles and Parts", "europe", "autos",
     "Carmakers and their suppliers.", "Ferrari, Mercedes-Benz, BMW, Volkswagen and Stellantis", _EXV("EXV5", "Automobiles & Parts")),
    (".SX7P", "eu-banks", "Banks", "STOXX Europe 600 Banks", "europe", "banks",
     "Europe's big banks.", "HSBC, Santander, BNP Paribas and UBS", _EXV("EXV1", "Banks")),
    (".SX4P", "eu-chem", "Chemicals", "STOXX Europe 600 Chemicals", "europe", "chem",
     "Chemical makers.", "Air Liquide, BASF and Sika", _EXV("EXV7", "Chemicals")),
    (".SXOP", "eu-build", "Construction & materials", "STOXX Europe 600 Construction and Materials", "europe", "build",
     "Builders and makers of building materials.", "Vinci, Saint-Gobain and Holcim", _EXV("EXV8", "Construction & Materials")),
    (".SXTP", "eu-travel", "Travel & leisure", "STOXX Europe 600 Travel and Leisure", "europe", "travel",
     "Airlines, hotels, restaurants, caterers and betting firms.", "Compass, Ryanair and Accor", _EXV("EXV9", "Travel & Leisure")),
    (".SXEP", "eu-energy", "Energy", "STOXX Europe 600 Energy", "europe", "oil",
     "Oil and gas producers.", "Shell, TotalEnergies, BP and Eni",
     ("EXH1", "Xetra", "iShares STOXX Europe 600 Oil & Gas UCITS ETF (DE)", "similar", "the STOXX Europe 600 Oil & Gas index, almost the same companies")),
    # US
    (".SOX", "us-chips", "Semiconductors", "PHLX Semiconductor Index", "us", "chips",
     "30 big US-listed chip companies.", "Nvidia, Broadcom, AMD and TSMC",
     ("SMH", "London", "VanEck Semiconductor UCITS ETF", "similar", "the 25 biggest US-listed chip companies (a MarketVector index) rather than these 30")),
    (".HGX", "us-housing", "Housing", "PHLX Housing Index", "us", "homes",
     "Housebuilders, building-products firms and home-improvement stores.", "D.R. Horton, Lennar and Home Depot", None),
    (".BKX", "us-banks", "Banks", "KBW Nasdaq Bank Index", "us", "banks",
     "24 big US banks.", "JPMorgan, Bank of America, Wells Fargo and Citigroup", None),
    (".DJT", "us-transport", "Transport", "Dow Jones Transportation Average", "us", "transport",
     "20 airlines, railways, truckers and delivery firms.", "Union Pacific, FedEx, UPS and Delta", None),
    (".OSX", "us-oilserv", "Oil services", "PHLX Oil Service Index", "us", "oilserv",
     "Companies that drill and service oil and gas wells.", "SLB, Halliburton and Baker Hughes", None),
    (".XAU", "us-gold", "Gold & silver miners", "PHLX Gold/Silver Sector Index", "us", "gold",
     "Gold and silver miners listed in the US.", "Newmont, Agnico Eagle and Barrick",
     ("GDX", "London", "VanEck Gold Miners UCITS ETF", "similar", "gold miners worldwide (the NYSE Arca Gold Miners index)")),
]

DIP = -0.30   # "in a deep dip": at least 30% below the highest close of the past five years
SWING = 0.20  # a "big fall" (and a rise that ends it) is a move of at least 20%, or the index's usual yearly swing if bigger

# Breaks in CNBC's history, found on 7 Oct 2026 before the test ran, by checking every one-day move of more than 20% and
# each UK index against its biggest companies' share prices before and after the March 2021 sector reshuffle (ICB).
#  - Mining: CNBC keeps the old FTSE 350 Mining index (Rio Tinto, Anglo American...) under the Precious Metals code until
#    23 Mar 2021; its Industrial Metals and Mining history before then is a different, smaller sector. Joined on that day.
#  - Housebuilders: before 24 Mar 2021 the index mostly followed Reckitt (household products), so it starts then.
#    (UK gold and silver miners have no history of their own before that day either, so they are left out.)
#  - PHLX Housing: at twice its true level before 1 Feb 2006 (Yahoo Finance's copy runs on smoothly), so halved.
SWITCH = "2021-03-24"
FIXES = {".FTNMX551020": {"splice": (".FTNMX551030", SWITCH)}, ".FTNMX402020": {"start": SWITCH},
         ".HGX": {"before": "2006-02-01", "scale": 0.5}}
NOTES = {
    "uk-mining": "Before 24 March 2021 this is the old FTSE 350 Mining index, joined to today's on that day (the sectors were reorganised).",
    "uk-homes": "History only from March 2021: before the sectors were reorganised, this index mostly followed Reckitt (household products).",
}
PHASES = ("Down and still falling", "Down but turning up", "Up and still rising", "Up but turning down")


# ---------------------------------------------------------------- fetching (CNBC daily closes, cached)

def _bars(sym, start):
    end = (date.today() + timedelta(days=1)).strftime("%Y%m%d")
    url = (f"https://ts-api.cnbc.com/harmony/app/bars/{urllib.parse.quote(sym)}/1D/"
           f"{start}000000/{end}000000/adjusted/EST5EDT.json")
    err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                bars = (json.load(r).get("barData") or {}).get("priceBars") or []
            out = {}
            for b in bars:
                try:
                    v = float(str(b.get("close")).replace(",", ""))
                except (TypeError, ValueError):
                    continue
                s = str(b.get("tradeTime") or "")
                if v > 0 and len(s) >= 8:
                    out[int(datetime(int(s[:4]), int(s[4:6]), int(s[6:8]), tzinfo=timezone.utc).timestamp())] = v
            return sorted(out.items())
        except Exception as e:  # noqa: BLE001 - retried, then reported
            err = e
            time.sleep(1 + attempt)
    print(f"[cycles {sym}] {err}", flush=True)
    return None


def load(symbols):
    """Daily closes for each symbol: the saved full history (re-downloaded every 20 hours) plus the last few weeks."""
    try:
        saved = json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    data, at = saved.get("data") or {}, saved.get("at") or 0
    stale = time.time() - at > FULL_EVERY
    full = [s for s in symbols if stale or s not in data]
    with ThreadPoolExecutor(max_workers=6) as ex:
        got = dict(zip(full, ex.map(lambda s: _bars(s, "19800101"), full)))
    fresh = [s for s, b in got.items() if b and len(b) > 300]
    for s in fresh:
        data[s] = got[s]
    if fresh:
        if stale and len(fresh) >= 0.8 * len(symbols):
            at = time.time()
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps({"at": at, "data": data}, separators=(",", ":")), encoding="utf-8")
    # everything not just downloaded in full: add the last few weeks
    recent = [s for s in symbols if s in data and s not in fresh]
    start = (date.today() - timedelta(days=24)).strftime("%Y%m%d")
    with ThreadPoolExecutor(max_workers=6) as ex:
        for s, b in zip(recent, ex.map(lambda s: _bars(s, start), recent)):
            if b:
                data[s] = [p for p in data[s] if p[0] < b[0][0]] + [list(p) for p in b]
    out, errors = {}, []
    for s in symbols:
        if s in AUX:
            continue
        pts = data.get(s)
        if pts and "splice" in FIXES.get(s, {}):
            old, on = FIXES[s]["splice"]
            pts = _splice(data.get(old), pts, _day(on))
        if not pts or len(pts) < 1000:
            errors.append(s)
            continue
        out[s] = _fix(s, pts)
    return out, errors


AUX = {f["splice"][0] for f in FIXES.values() if "splice" in f}  # downloaded only to be joined onto another index


def _day(iso):
    return int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp())


def _splice(old, new, on):
    """old's closes before day `on`, rescaled to meet new's, then new's."""
    if not old:
        return None
    before = [p for p in old if p[0] < on]
    meet = next((p[1] for p in reversed(new) if p[0] <= before[-1][0]), None) if before else None
    if not meet:
        return None
    k = meet / before[-1][1]
    return [(p[0], p[1] * k) for p in before] + [tuple(p) for p in new if p[0] >= on]


def _fix(sym, pts):
    """The known breaks (FIXES), then bad prints: a jump of more than 12% undone the next day (back within 4%),
    and bigger one-to-three-day glitches (engine._drop_spikes)."""
    f = FIXES.get(sym, {})
    if "start" in f:
        pts = [p for p in pts if p[0] >= _day(f["start"])]
    if "before" in f:
        pts = [(p[0], p[1] * f["scale"]) if p[0] < _day(f["before"]) else p for p in pts]
    out, k = [], 0
    while k < len(pts):
        if out and k + 1 < len(pts):
            base = out[-1][1]
            if abs(pts[k][1] / base - 1) > 0.12 and abs(pts[k + 1][1] / base - 1) < 0.04:
                k += 1
                continue
        out.append(pts[k])
        k += 1
    out = engine._drop_spikes([(p[0], p[1], p[1]) for p in out])
    return [p[0] for p in out], [p[1] for p in out]


def yearly_swing(c):
    """How much the index typically moves in a year (the volatility of its daily changes, scaled to a year)."""
    r = [math.log(c[i] / c[i - 1]) for i in range(1, len(c))]
    m = sum(r) / len(r)
    return math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1) * 252)


# ---------------------------------------------------------------- the cycle measures

def rolling(t, c):
    """For every day: the highest close and the average close of the five years up to it (None until five years of
    history), and the 200-day average."""
    n, pre = len(c), [0.0]
    for v in c:
        pre.append(pre[-1] + v)
    hi, avg, ma = [None] * n, [None] * n, [None] * n
    dq, j = deque(), 0
    for i in range(n):
        while dq and c[dq[-1]] <= c[i]:
            dq.pop()
        dq.append(i)
        while t[j] < t[i] - 5 * YEAR:
            j += 1
        while dq[0] < j:
            dq.popleft()
        if t[i] - t[0] >= 5 * YEAR - 7 * DAY:
            hi[i], avg[i] = c[dq[0]], (pre[i + 1] - pre[j]) / (i + 1 - j)
        if i >= 199:
            ma[i] = (pre[i + 1] - pre[i - 199]) / 200
    return hi, avg, ma


def state(c, hi, avg, ma, i):
    if hi[i] is None or ma[i] is None:
        return None
    return {"dd5": c[i] / hi[i] - 1, "vs5y": c[i] / avg[i] - 1, "vs200": c[i] / ma[i] - 1}


def phase_of(s):
    """Below or above the five-year average (the middle of its recent cycle), and above or below the 200-day
    average (turned up, or still falling)."""
    if s is None:
        return None
    if s["vs5y"] < 0:
        return PHASES[1] if s["vs200"] > 0 else PHASES[0]
    return PHASES[2] if s["vs200"] > 0 else PHASES[3]


def _ym(ts):
    d = datetime.fromtimestamp(ts, timezone.utc)
    return d.year * 12 + d.month - 1


def _ym_ts(ym):
    return int(datetime(ym // 12, ym % 12 + 1, 1, tzinfo=timezone.utc).timestamp())


def month_ends(t):
    """{month: index of its last close}, leaving out the current, unfinished month."""
    out = {}
    for i, ts in enumerate(t):
        out[_ym(ts)] = i
    out.pop(_ym(t[-1]), None)
    return out


def swings(c, move=SWING):
    """Turning points: peaks and troughs in turn, each at least `move` away from the one before (a zig-zag).
    Returns the turns, whether the latest move is down or up (None before the first), and its extreme so far."""
    turns, mode, hi, lo = [], None, 0, 0
    for i in range(1, len(c)):
        if mode != "down":
            if c[i] > c[hi]:
                hi = i
            if c[i] <= c[hi] * (1 - move):
                turns.append(("peak", hi))
                mode, lo = "down", i
                continue
        if mode != "up":
            if c[i] < c[lo]:
                lo = i
            if c[i] >= c[lo] * (1 + move):
                turns.append(("trough", lo))
                mode, hi = "up", i
    return turns, mode, (lo if mode == "down" else hi)


def big_falls(t, c, move=SWING):
    """Every fall of `move` or more from a peak to a trough, with how long it took, the rise in the year after the
    trough, and when (if ever) the index got back to the peak."""
    turns, mode, ext = swings(c, move)
    out = []
    for (k1, p), (k2, q) in zip(turns, turns[1:]):
        if k1 != "peak" or k2 != "trough":
            continue
        y1 = bisect.bisect_left(t, t[q] + YEAR)
        back = next((k for k in range(q, len(c)) if c[k] >= c[p]), None)
        out.append({"peak": t[p], "trough": t[q], "fall": c[q] / c[p] - 1, "months": (t[q] - t[p]) / (YEAR / 12),
                    "after1y": c[y1] / c[q] - 1 if y1 < len(c) else None, "regained": t[back] if back is not None else None})
    now = None
    if mode == "down" and turns and turns[-1][0] == "peak":
        p = turns[-1][1]
        now = {"kind": "fall", "from": t[p], "fromV": c[p], "low": c[ext] / c[p] - 1, "lowAt": t[ext], "now": c[-1] / c[p] - 1,
               "months": (t[-1] - t[p]) / (YEAR / 12)}
    elif mode == "up" and turns and turns[-1][0] == "trough":
        q = turns[-1][1]
        now = {"kind": "rise", "from": t[q], "fromV": c[q], "high": c[ext] / c[q] - 1, "highAt": t[ext], "now": c[-1] / c[q] - 1,
               "months": (t[-1] - t[q]) / (YEAR / 12)}
    return out, now


# ---------------------------------------------------------------- the buy-the-dip test (fixed in advance: cycles_test.py)

HOLD, LONG, SHUFFLES, SEED = 12, 36, 1000, 2026
TEST_CACHE = ROOT / "data" / "cycles_test.json"
TEST_VERSION = 1  # bump if the test code changes, so a saved result is recomputed
RULES = {
    "dip": "In a deep dip: 30% or more below its 5-year high",
    "turn": "Down but turning up: below its 5-year average, above its 10-month average",
}
DEPTHS = [("0 to 10% below its 5-year high", -0.10, 9.0), ("10 to 20% below", -0.20, -0.10),
          ("20 to 30% below", -0.30, -0.20), ("30 to 50% below", -0.50, -0.30), ("More than 50% below", -9.0, -0.50)]
GROUPS = [("rule", k) for k in RULES] + [("phase", p) for p in PHASES] + [("depth", d[0]) for d in DEPTHS]


def monthly(t, c):
    """Month-end closes as one unbroken run: (first month, closes); a month with no trading repeats the last close."""
    me = month_ends(t)
    ms, out = sorted(me), []
    for ym in range(ms[0], ms[-1] + 1):
        out.append(c[me[ym]] if ym in me else out[-1])
    return ms[0], out


def _measures(m):
    """At each month-end: the change from the 5-year high, and the level against the 5-year and 10-month averages
    (all from month-end closes; None until there are five years of them)."""
    n, pre = len(m), [0.0]
    for v in m:
        pre.append(pre[-1] + v)
    dd, v5, v10, dq = [None] * n, [None] * n, [None] * n, deque()
    for k in range(n):
        while dq and m[dq[-1]] <= m[k]:
            dq.pop()
        dq.append(k)
        while dq[0] <= k - 60:
            dq.popleft()
        if k >= 59:
            dd[k] = m[k] / m[dq[0]] - 1
            v5[k] = m[k] / ((pre[k + 1] - pre[k - 59]) / 60) - 1
            v10[k] = m[k] / ((pre[k + 1] - pre[k - 9]) / 10) - 1
    return dd, v5, v10


def _groups(dd, v5, v10):
    """Which of GROUPS a month-end belongs to: the two rules, one phase, one depth."""
    g = [0] if dd <= DIP else []
    if v5 < 0 < v10:
        g.append(1)
    g.append(2 + (0 if v5 < 0 and v10 <= 0 else 1 if v5 < 0 else 2 if v10 > 0 else 3))
    g.append(2 + len(PHASES) + next(i for i, (_, a, b) in enumerate(DEPTHS) if a < dd <= b))
    return g


def _core(ms, mk, region_of, mid, keep=None):
    """For every group, the average of: each month's next-12-month change minus the same index's average over all
    its test months (whole test, before `mid`, from `mid`), the same over 3 years, and the next 12 months minus the
    region's whole market. keep: a list to collect every observation in (for the descriptive figures)."""
    G = len(GROUPS)
    acc = {k: [0.0] * G for k in ("ex", "n", "exA", "nA", "exB", "nB", "ex3", "n3", "vm", "nm")}
    for sym, (ym0, m) in ms.items():
        if sym not in region_of:
            continue
        dd, v5, v10 = _measures(m)
        ks = range(59, len(m) - HOLD)
        if len(ks) < 24:
            continue
        fwd = {k: m[k + HOLD] / m[k] - 1 for k in ks}
        f3 = {k: m[k + LONG] / m[k] - 1 for k in ks if k + LONG < len(m)}
        avg, avg3 = sum(fwd.values()) / len(fwd), (sum(f3.values()) / len(f3) if f3 else 0)
        mym0, mm = mk.get(region_of[sym], (None, None))
        for k in ks:
            ym, e = ym0 + k, fwd[k] - avg
            j = ym - mym0 if mm else -1
            mf = mm[j + HOLD] / mm[j] - 1 if mm and 0 <= j and j + HOLD < len(mm) else None
            gs = _groups(dd[k], v5[k], v10[k])
            for g in gs:
                acc["ex"][g] += e; acc["n"][g] += 1
                h = "A" if ym < mid else "B"
                acc["ex" + h][g] += e; acc["n" + h][g] += 1
                if k in f3:
                    acc["ex3"][g] += f3[k] - avg3; acc["n3"][g] += 1
                if mf is not None:
                    acc["vm"][g] += fwd[k] - mf; acc["nm"][g] += 1
            if keep is not None:
                keep.append({"sym": sym, "ym": ym, "g": gs, "dd": dd[k], "fwd": fwd[k], "f3": f3.get(k), "mkt": mf,
                             "low": min(m[k:k + HOLD + 1]) / m[k] - 1})
    div = lambda s, n: [a / b if b else None for a, b in zip(acc[s], acc[n])]
    return {"ex": div("ex", "n"), "exA": div("exA", "nA"), "exB": div("exB", "nB"), "ex3": div("ex3", "n3"), "vm": div("vm", "nm")}


def _shuffle(ms, rnd):
    """The same months' changes in a random order, one order shared by every index (so they still rise and fall
    together), which keeps how bumpy each index is but removes any pattern over time."""
    months = sorted({ym for ym0, m in ms.values() for ym in range(ym0 + 1, ym0 + len(m))})
    rnd.shuffle(months)
    out = {}
    for sym, (ym0, m) in ms.items():
        lo, hi = ym0 + 1, ym0 + len(m) - 1
        new = [m[0]]
        for ym in months:
            if lo <= ym <= hi:
                new.append(new[-1] * m[ym - ym0] / m[ym - ym0 - 1])
        out[sym] = (ym0, new)
    return out


def verdict(edge, p):
    if edge is None or p is None:
        return "Not enough data"
    return "Probably worked" if edge > 0 and p < 0.025 else "Possibly worked" if edge > 0 and p < 0.16 else "Didn't work"


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def _episodes(picked):
    """Separate dips: a run of consecutive months for the same index counts once."""
    seen, n = set(), 0
    for o in sorted(picked, key=lambda o: (o["sym"], o["ym"])):
        if (o["sym"], o["ym"] - 1) not in seen:
            n += 1
        seen.add((o["sym"], o["ym"]))
    return n


def _group_stats(obs, gi):
    """What actually happened after the month-ends in group gi (no reshuffling: these are the plain averages)."""
    p = [o for o in obs if gi in o["g"]]
    return {"n": len(p), "episodes": _episodes(p), "indices": len({o["sym"] for o in p}),
            "avg": _mean([o["fwd"] for o in p]), "avgAll": _mean([o["fwd"] for o in obs]),
            "up": _mean([o["fwd"] > 0 for o in p]), "upAll": _mean([o["fwd"] > 0 for o in obs]),
            "low": _median([o["low"] for o in p]), "lowAll": _median([o["low"] for o in obs]),
            "worstLow": min((o["low"] for o in p), default=None), "fellMore20": _mean([o["low"] <= -0.20 for o in p]),
            "avg3": _mean([o["f3"] for o in p]), "avg3All": _mean([o["f3"] for o in obs]),
            "up3": _mean([o["f3"] > 0 for o in p if o["f3"] is not None]),
            "up3All": _mean([o["f3"] > 0 for o in obs if o["f3"] is not None])}


def dip_test(series, region_of, shuffles=SHUFFLES):
    """Did buying in a dip beat buying the same index at any time? The rules and the bar were fixed in advance
    (cycles_test.py). Returns the result, and every observation (for each index's own record)."""
    ms = {s: monthly(*v) for s, v in series.items()}
    markets = lambda d: {r: d[reg["market"]] for r, reg in REGIONS.items() if reg["market"] in d}
    obs = []
    _core(ms, markets(ms), region_of, 10 ** 9, keep=obs)
    if len(obs) < 200:
        return None, obs
    yms = sorted({o["ym"] for o in obs})
    mid = yms[len(yms) // 2]
    real = _core(ms, markets(ms), region_of, mid)
    rnd, sims = random.Random(SEED), []
    for _ in range(shuffles):
        sh = _shuffle(ms, rnd)
        sims.append(_core(sh, markets(sh), region_of, mid))

    def judged(stat, g):
        """The real figure, how much better it is than the reshuffled histories' average (the edge), and the share
        of reshuffles at least as good (p: under 2.5% is about as convincing as t >= 2)."""
        a, s = real[stat][g], [x[stat][g] for x in sims if x[stat][g] is not None]
        if a is None or len(s) < shuffles * 0.9:
            return a, None, None
        return a, a - sum(s) / len(s), (1 + sum(x >= a for x in s)) / (1 + len(s))

    def block(g):
        ex, edge, p = judged("ex", g)
        ex3, edge3, p3 = judged("ex3", g)
        vm, edge_m, p_m = judged("vm", g)
        halves = []
        for stat, part in (("exA", [o for o in obs if o["ym"] < mid]), ("exB", [o for o in obs if o["ym"] >= mid])):
            hx, he, hp = judged(stat, g)
            halves.append({"from": _ym_ts(min(o["ym"] for o in part)), "to": _ym_ts(max(o["ym"] for o in part)),
                           "n": sum(g in o["g"] for o in part), "ex": hx, "edge": he, "p": hp})
        return {**_group_stats(obs, g), "ex": ex, "edge": edge, "p": p, "verdict": verdict(edge, p),
                "ex3": ex3, "edge3": edge3, "p3": p3, "vsMkt": vm, "edgeMkt": edge_m, "pMkt": p_m, "halves": halves}

    out = {"from": _ym_ts(yms[0]), "to": _ym_ts(yms[-1]), "months": len(yms), "obs": len(obs),
           "indices": len({o["sym"] for o in obs}), "hold": HOLD, "shuffles": shuffles, "dip": DIP, "mid": _ym_ts(mid),
           "rules": {}, "phases": [], "depths": []}
    for g, (kind, name) in enumerate(GROUPS):
        b = block(g)
        if kind == "rule":
            out["rules"][name] = {"label": RULES[name], **b}
        else:
            out[kind + "s"].append({"label": name, **b})
    return out, obs


def cached_test(series, region_of):
    """The test uses complete months only, so it is re-run when a new month completes (or the code or list changes)."""
    last = max(_ym(t[-1]) for t, _ in series.values())
    key = f"{TEST_VERSION}|{last}|{','.join(sorted(series))}"
    try:
        saved = json.loads(TEST_CACHE.read_text(encoding="utf-8"))
        if saved.get("key") == key:
            return saved["test"], saved["own"]
    except (OSError, ValueError):
        pass
    test, obs = dip_test(series, region_of)
    own = {s: own_record(obs, s) for s in region_of}
    TEST_CACHE.parent.mkdir(parents=True, exist_ok=True)
    TEST_CACHE.write_text(json.dumps(engine.clean({"key": key, "test": test, "own": own}), separators=(",", ":")), encoding="utf-8")
    return test, own


def own_record(obs, sym):
    """The same two rules in one index's own history: a handful of dips at most, so a story rather than a test."""
    mine = sorted((o for o in obs if o["sym"] == sym), key=lambda o: o["ym"])
    if len(mine) < 36:
        return None
    out = {"from": _ym_ts(mine[0]["ym"]), "to": _ym_ts(mine[-1]["ym"]), "months": len(mine),
           "avgAll": _mean([o["fwd"] for o in mine]), "upAll": _mean([o["fwd"] > 0 for o in mine])}
    for g, k in enumerate(RULES):
        p = [o for o in mine if g in o["g"]]
        out[k] = {"months": len(p), "episodes": _episodes(p), "avg": _mean([o["fwd"] for o in p]),
                  "up": _mean([o["fwd"] > 0 for o in p]), "worstLow": min((o["low"] for o in p), default=None),
                  "last": _ym_ts(p[-1]["ym"]) if p else None}
    return out


# ---------------------------------------------------------------- the page's data

def _sig(v, n=5):
    return float(f"{v:.{n}g}")


def describe(t, c):
    """Today's cycle measures for one index, its past big falls, and the price history the charts need."""
    hi, avg, ma = rolling(t, c)
    i = len(c) - 1
    s = state(c, hi, avg, ma, i)
    if s is None:
        return None
    j5 = bisect.bisect_left(t, t[i] - 5 * YEAR)
    k_hi = max(range(j5, i + 1), key=lambda k: c[k])
    k_lo = min(range(j5, i + 1), key=lambda k: c[k])
    ago = lambda days: c[i] / c[max(0, bisect.bisect_right(t, t[i] - days * DAY) - 1)] - 1
    me = month_ends(t)
    trail = [state(c, hi, avg, ma, me[ym]) for ym in sorted(me)[-6:]] + [s]
    swing = max(SWING, round(yearly_swing(c) * 20) / 20)  # to the nearest 5%
    falls, now = big_falls(t, c, swing)
    months, long_c = sorted(me), []
    for ym in range(months[0], months[-1] + 1):  # a month with no trading carries the last close forward
        long_c.append(_sig(c[me[ym]]) if ym in me else long_c[-1])
    k0 = max(0, i - 259)
    return {
        **{k: round(v, 5) for k, v in s.items()}, "phase": phase_of(s), "level": c[i], "at": t[i], "since": t[0],
        "hi5": c[k_hi], "hi5At": t[k_hi], "lo5": c[k_lo], "lo5At": t[k_lo],
        "r1w": ago(7), "r3m": ago(91), "r1y": ago(365),
        "trail": [[round(x["vs5y"], 4), round(x["vs200"], 4)] for x in trail if x],
        "swing": swing, "falls": falls, "now": now,
        # month-end closes for the long chart (from the first full month), and the last year day by day with its 200-day average
        "long": {"ym0": _ym_ts(months[0]), "c": long_c + [_sig(c[i])]},
        "recent": {"t0": t[k0], "d": [(t[k] - t[k0]) // DAY for k in range(k0, i + 1)], "c": [_sig(v) for v in c[k0:]],
                   "ma": [_sig(v) for v in ma[k0:]]},
    }


def build():
    region_of = {x[0]: x[4] for x in INDICES}
    markets = [r["market"] for r in REGIONS.values()]
    series, errors = load([x[0] for x in INDICES] + markets + sorted(AUX))
    t0 = time.time()
    test, own = cached_test(series, region_of)
    rows = []
    for sym, key, name, full, region, drives, what, includes, buy in INDICES:
        if sym not in series:
            continue
        d = describe(*series[sym])
        if not d:
            continue
        rows.append({"symbol": sym, "key": key, "name": name, "full": full, "region": region, "drives": DRIVES[drives],
                     "what": what, "includes": includes, "note": NOTES.get(key, ""),
                     "buy": buy and {"ticker": buy[0], "exchange": buy[1], "name": buy[2], "match": buy[3], "differs": buy[4]},
                     "own": own.get(sym), **d})
    mkts = {}
    for r, reg in REGIONS.items():
        if reg["market"] in series:
            d = describe(*series[reg["market"]])
            if d:
                mkts[r] = {"symbol": reg["market"], "name": reg["marketName"],
                           **{k: d[k] for k in ("dd5", "vs5y", "vs200", "phase", "level", "at", "r1y", "hi5At")}}
    return {"generated": time.time(), "marketTime": max((r["at"] for r in rows), default=None),
            "regions": {k: {"name": v["name"], "marketName": v["marketName"], "ccy": v["ccy"]} for k, v in REGIONS.items()},
            "rows": rows, "markets": mkts, "test": test, "testSeconds": round(time.time() - t0, 1),
            "phases": PHASES, "dipLine": DIP, "swing": SWING, "errors": errors}


if __name__ == "__main__":
    d = build()
    for r in d["rows"]:
        print(f"{r['name'][:24]:24} {r['region']:6} {r['dd5']:+7.1%} {r['vs5y']:+7.1%} {r['vs200']:+7.1%}  {r['phase']}")
    print("errors:", d["errors"], "markets:", list(d["markets"]))
