"""Sector Compass data: sector and theme funds, each scored against its own region's whole stock market."""
import time

import engine
import funddata
import tracking
from universe import GROUPS, MACRO, buy_on_ibkr, core_buy

FX = {"EUR": "EURUSD=X", "JPY": "JPYUSD=X", "CAD": "CADUSD=X"}  # to put net assets on one scale
PER_USD = {"GBP": "GBP=X", "EUR": "EUR=X", "JPY": "JPY=X", "CAD": "CAD=X"}  # units per US dollar, for pound returns

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
        rates = f"The 10-year US interest rate ({tnx:.2f}%)"
        if curve < 0:
            ev["Late cycle"] += 1; ev["Contraction"] += 0.5
            notes.append(f"Short-term US interest rates (3-month, {irx:.2f}%) are {abs(curve):.2f}% above 10-year rates ({tnx:.2f}%). "
                         "This 'inverted yield curve' has come before most US recessions: a classic late-cycle warning.")
        elif curve_3m is not None and curve_3m > 0.2:
            ev["Early cycle"] += 1
            notes.append(f"{rates} is {curve:.2f}% above the 3-month rate ({irx:.2f}%), and that gap has widened by "
                         f"{curve_3m:.2f}% in 3 months: often a sign that growth is picking up.")
        elif curve_3m is not None and curve_3m < -0.2:
            # a fast-shrinking gap ("flattening") tends to come late in an expansion
            ev["Late cycle"] += 0.6; ev["Mid cycle"] += 0.3
            notes.append(f"{rates} is {curve:.2f}% above the 3-month rate ({irx:.2f}%), but the gap has shrunk by "
                         f"{abs(curve_3m):.2f}% in 3 months: a shrinking gap often comes late in an expansion.")
        else:
            ev["Mid cycle"] += 0.7
            notes.append(f"{rates} is {curve:.2f}% above the 3-month rate ({irx:.2f}%), a normal gap that has changed little in 3 months.")
    cu, au = macro.get("HG=F"), macro.get("GC=F")
    if cu and au and len(cu["c"]) > 63 and len(au["c"]) > 63:
        cg = (cu["c"][-1] / au["c"][-1]) / (cu["c"][-64] / au["c"][-64]) - 1
        if cg > 0.03:
            ev["Early cycle"] += 0.7; ev["Mid cycle"] += 0.5
            notes.append(f"Copper has gained {cg:.1%} on gold over 3 months. Copper follows factory and building demand, "
                         "while gold is bought in worrying times, so this points to stronger growth.")
        elif cg < -0.03:
            ev["Contraction"] += 0.8; ev["Late cycle"] += 0.3
            notes.append(f"Copper has lost {abs(cg):.1%} against gold over 3 months: a sign investors are worried about growth and moving to safer holdings.")
        else:
            ev["Mid cycle"] += 0.4
            notes.append(f"Copper and gold have moved about the same over 3 months ({cg:+.1%} for copper vs gold): no strong growth signal.")
    oil = macro.get("CL=F")
    if oil and len(oil["c"]) > 126:
        o6 = oil["c"][-1] / oil["c"][-127] - 1
        if o6 > 0.15:
            ev["Late cycle"] += 0.8
            notes.append(f"Oil is up {o6:.0%} in 6 months. That pushes prices up across the economy (inflation), which is typical late in a boom.")
        elif o6 < -0.15:
            ev["Contraction"] += 0.3; ev["Early cycle"] += 0.3
            notes.append(f"Oil is down {abs(o6):.0%} in 6 months: lower costs for businesses, but often a sign of weaker demand.")
    if vix is not None:
        if vix >= 25:
            ev["Contraction"] += 1
            notes.append(f"Fear gauge (VIX) at {vix:.1f}: investors are nervous (over 25 = stressed).")
        elif vix <= 16:
            ev["Mid cycle"] += 0.6
            notes.append(f"Fear gauge (VIX) at {vix:.1f}: markets are calm (under 16 = calm, over 25 = stressed).")
        else:
            notes.append(f"Fear gauge (VIX) at {vix:.1f}: normal (16 to 25).")
    if spy:
        if spy["vs200"] is not None and spy["vs200"] < 0:
            ev["Contraction"] += 1
            notes.append("The US stock market (S&P 500) is below its 200-day (about 10-month) average price: a broad downtrend.")
        elif spy["vs200"] is not None and spy["r6m"] is not None:
            ev["Mid cycle"] += 0.6
            if spy["mdd"] < -0.15 and spy["r3m"] > 0.08:
                ev["Early cycle"] += 0.8
                notes.append(f"The US stock market (S&P 500) is bouncing back strongly: up {spy['r3m']:.0%} in 3 months, "
                             f"having fallen as much as {abs(spy['mdd']):.0%} from a peak at some point in the past year.")
            else:
                notes.append("The US stock market (S&P 500) is above its average price over the last 200 trading days "
                             "(about 10 months): its long-term uptrend is intact.")
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
               | {m[0] for m in MACRO} | set(FX.values()) | set(PER_USD.values()))
    raw = engine.fetch_all(sorted(symbols))
    # conversion rates: into pounds and into US dollars, from each fund's own currency
    per_usd = {c: raw.get(sym) for c, sym in PER_USD.items() if engine.usable(raw.get(sym))}
    gbp = per_usd.get("GBP")
    to_gbp = {"USD": gbp, **{c: engine.cross(gbp, v) for c, v in per_usd.items() if c != "GBP" and gbp}}
    to_usd = {"USD": None, **{c: engine.invert(v) for c, v in per_usd.items() if c != "GBP"}}
    in_ccys = lambda d, ccy: {"gbp": engine.convert(d, to_gbp.get(ccy)) if to_gbp.get(ccy) or ccy == "GBP" else None,
                              "usd": engine.convert(d, to_usd.get(ccy)) if ccy in to_usd else None}
    usd = {"USD": 1.0, **{c: (raw.get(s) or {}).get("price") for c, s in FX.items()}}
    rf_at = engine.rate_at(raw.get("^IRX"))
    errors = sorted(s for s, d in raw.items() if not engine.usable(d))
    macro = engine.macro_block(raw, MACRO)

    rows, tracks, benches, series, market_of = [], [], {}, {}, {}
    now = max(d["t"][-1] for d in raw.values() if engine.usable(d))
    rf = rf_at(now)
    for g in GROUPS:
        b = raw.get(g["bench"])
        b = b if engine.usable(b) else None
        if b:
            bm = engine.analyse(engine.Track(b), b, rf)
            b_ccy = in_ccys(b, b.get("ccy"))
            benches[g["id"]] = {"symbol": g["bench"], "name": g["bench_name"],
                                "m": {k: bm[k] for k in ("vs200", "r1d", "r1w", "r3m", "r6m", "r1y", "mdd", "vol")},
                                "gbp": engine.period_returns(engine.Track(b_ccy["gbp"])) if b_ccy["gbp"] else None,
                                # the long run: how this whole market has done over every 1, 3 and 5-year stretch, in pounds
                                "longRun": engine.long_run_record(b_ccy["gbp"]) if b_ccy["gbp"] else None, "buy": core_buy(g["id"])}
        for sym, name, key in g["funds"]:
            d = raw.get(sym)
            if not engine.usable(d):
                continue
            tr = engine.Track(d, b)
            m = engine.analyse(tr, d, rf)
            if m:
                conv = in_ccys(d, d["ccy"])
                rows.append({"symbol": sym, "name": name, "key": key, "group": g["id"],
                             "fund": d["name"], "ccy": d["ccy"], "m": m, "buy": buy_on_ibkr(sym),
                             "gbp": engine.period_returns(engine.Track(conv["gbp"])) if conv["gbp"] else None})
                tracks.append(tr)
                if conv["gbp"] and conv["usd"]:
                    series[sym] = conv
                    if b:
                        market_of[sym] = in_ccys(b, b.get("ccy"))
    hist_cuts = engine.apply_scores(rows, tracks, rf_at)
    t0 = time.time()
    bt = engine.backtest(tracks, rf_at)
    # the same test on the funds a UK investor can buy on IBKR (and the candidate rule that failed it; see candidates_test.py)
    buy_test = engine.candidate_backtest(tracks, rf_at, [bool(r["buy"]) for r in rows])
    long_test = engine.long_hold_test(tracks, rf_at, [bool(r["buy"]) for r in rows])  # see longrun_test.py
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
    acwi = raw.get("ACWI")
    world_series = {"gbp": engine.convert(acwi, to_gbp["USD"]), "usd": acwi} if engine.usable(acwi) and gbp else None
    paper = tracking.paper_report("sectors", series, market_of, world_series) if world_series else None
    changes = tracking.signal_log("sectors", rows, "symbol")
    for sym in macro:
        macro[sym].pop("c", None)
    return {
        "generated": time.time(), "marketTime": max((d.get("mtime") or 0) for d in raw.values() if "error" not in d),
        "groups": [{k: g[k] for k in ("id", "name", "bench", "bench_name", "ccy", "plain", "short")} for g in GROUPS],
        "benches": benches, "rows": rows, "macro": macro, "cycle": cyc, "histCuts": hist_cuts,
        "weights": engine.WEIGHTS, "errors": errors, "holdingsAt": fund["fetched"],
        "backtest": bt, "backtestSeconds": bt_seconds, "buyTest": buy_test, "longTest": long_test, "paper": paper, "changes": changes,
    }
