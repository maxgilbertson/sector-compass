"""Sector Compass data: sector, theme and country funds, each scored against its local benchmark."""
import time

import engine
import funddata
from universe import GROUPS, MACRO

FX = {"EUR": "EURUSD=X", "JPY": "JPYUSD=X", "CAD": "CADUSD=X"}  # to put net assets on one scale

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
    symbols = ({g["bench"] for g in GROUPS} | {f[0] for g in GROUPS for f in g["funds"]}
               | {m[0] for m in MACRO} | set(FX.values()))
    raw = engine.fetch_all(sorted(symbols))
    usd = {"USD": 1.0, **{c: (raw.get(s) or {}).get("price") for c, s in FX.items()}}
    rf_at = engine.rate_at(raw.get("^IRX"))
    errors = sorted(s for s, d in raw.items() if not engine.usable(d))
    macro = engine.macro_block(raw, MACRO)

    rows, tracks, benches = [], [], {}
    now = max(d["t"][-1] for d in raw.values() if engine.usable(d))
    rf = rf_at(now)
    for g in GROUPS:
        b = raw.get(g["bench"])
        b = b if engine.usable(b) else None
        if b:
            bm = engine.analyse(engine.Track(b), b, rf)
            benches[g["id"]] = {"symbol": g["bench"], "name": g["bench_name"],
                                "m": {k: bm[k] for k in ("vs200", "r3m", "r6m", "r1y", "mdd")}}
        for sym, name, key in g["funds"]:
            d = raw.get(sym)
            if not engine.usable(d):
                continue
            tr = engine.Track(d, b)
            m = engine.analyse(tr, d, rf)
            if m:
                rows.append({"symbol": sym, "name": name, "key": key, "group": g["id"],
                             "fund": d["name"], "ccy": d["ccy"], "m": m})
                tracks.append(tr)
    hist_cuts = engine.apply_scores(rows, tracks, rf_at)
    t0 = time.time()
    bt = engine.backtest(tracks, rf_at)
    bt_seconds = round(time.time() - t0, 1)

    fund = funddata.load([r["symbol"] for r in rows] + [b["symbol"] for b in benches.values()])

    def facts(sym, ccy):
        f = dict((fund["funds"].get(sym) or {}).get("facts") or {})
        rate = usd.get(ccy)
        f["aumUsd"] = f["aum"] * rate if (f.get("aum") and rate) else None
        return f

    for r in rows:
        r["holdings"] = (fund["funds"].get(r["symbol"]) or {}).get("holdings")
        r["facts"] = facts(r["symbol"], r["ccy"])
    for g in GROUPS:
        if g["id"] in benches:
            benches[g["id"]]["facts"] = facts(g["bench"], (raw.get(g["bench"]) or {}).get("ccy"))
    cyc = cycle_read(macro, benches.get("us", {}).get("m"))
    for sym in macro:
        macro[sym].pop("c", None)
    return {
        "generated": time.time(), "marketTime": max((d.get("mtime") or 0) for d in raw.values() if "error" not in d),
        "groups": [{k: g[k] for k in ("id", "name", "bench", "bench_name", "ccy")} for g in GROUPS],
        "benches": benches, "rows": rows, "macro": macro, "cycle": cyc, "histCuts": hist_cuts,
        "weights": engine.WEIGHTS, "errors": errors, "holdingsAt": fund["fetched"],
        "backtest": bt, "backtestSeconds": bt_seconds,
    }
