"""Weekly briefing: gather the week's facts from both pages and write a factual draft.

Run by .github/workflows/briefing.yml every Saturday morning. It saves
  data/briefings/facts/<date>.json  - every number the briefing may use
  data/briefings/<date>.md          - a plain factual draft (published straight away)
  data/briefings/index.json         - the archive list the site reads
A weekly scheduled Claude task then rewrites the draft into a proper briefing
using only those facts (see BRIEFING_PROMPT.md). If that doesn't run, the draft stays up.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import engine
import sectors
import world

HERE = Path(__file__).parent
OUT = HERE.parent / "data" / "briefings"


def pctw(v, dp=1):
    if v is None:
        return "n/a"
    return "flat" if abs(v) < 0.5 * 10 ** -(dp + 2) else f"{'up' if v >= 0 else 'down'} {abs(v) * 100:.{dp}f}%"


def signed(v, dp=1):
    if v is None:
        return "n/a"
    return f"{0:.{dp}f}%" if abs(v) < 0.5 * 10 ** -(dp + 2) else f"{v * 100:+.{dp}f}%"


PEGGED = {"SAR", "HKD"}  # pegged to the US dollar: any big weekly move is a data error, not news


def long_date(iso, weekday=True):
    """'Friday 2 October 2026' without platform-specific strftime flags."""
    d = datetime.fromisoformat(iso)
    return f"{d.strftime('%A') + ' ' if weekday else ''}{d.day} {d.strftime('%B %Y')}"


def week_ending(now):
    """The last trading day the week's numbers run to: the most recent Friday at a weekend
    (the normal Saturday run), otherwise today, because weekday prices run to today."""
    return (now - timedelta(days=now.weekday() - 4)).date() if now.weekday() >= 5 else now.date()


def gather():
    s, w = sectors.build(), world.build()
    now = datetime.now(timezone.utc)

    def sector_row(r):
        m, g = r["m"], r.get("gbp") or {}
        prev = m["hist"][-2] if len(m.get("hist") or []) > 1 else None
        return {"name": r["name"], "region": next(x["name"] for x in s["groups"] if x["id"] == r["group"]),
                "vs": next(x["plain"] for x in s["groups"] if x["id"] == r["group"]),
                "score": round(m["score"]) if m["score"] is not None else None, "signal": m["signal"],
                "scoreChangeWeek": m.get("d1w"), "signalWeekAgo": engine.signal(prev),
                "weekReturnOwnCurrency": m.get("r1w"), "weekReturnGbp": g.get("r1w"), "yearReturnGbp": g.get("r1y"),
                "rotation": m.get("quad"), "flags": [f["label"] for f in m.get("flags", [])]}

    def country_row(r):
        m, g, fx = r["m"], r.get("gbp") or {}, r.get("fx") or {}
        prev = m["hist"][-2] if len(m.get("hist") or []) > 1 else None
        return {"name": r["name"], "index": r["index"]["name"], "score": round(m["score"]) if m["score"] is not None else None,
                "signal": m["signal"], "scoreChangeWeek": m.get("d1w"), "signalWeekAgo": engine.signal(prev),
                "weekReturnUsd": m.get("r1w"), "weekReturnGbp": g.get("r1w"), "weekReturnLocalIndex": r["local"].get("r1w"),
                "yearReturnGbp": g.get("r1y"), "currencyWeekVsUsd": fx.get("w1"), "currency": r["index"]["ccy"],
                "valueScore": m.get("value"), "rotation": m.get("quad"), "flags": [f["label"] for f in m.get("flags", [])],
                "conditionsHelping": m.get("tail"), "conditionsHurting": m.get("head")}

    srows = [sector_row(r) for r in s["rows"]]
    crows = [country_row(r) for r in w["rows"]]
    by = lambda rows, k, rev=True, n=5: [x for x in sorted((x for x in rows if x.get(k) is not None), key=lambda x: x[k], reverse=rev)][:n]
    changed = lambda rows: [x for x in rows if x["signalWeekAgo"] and x["signal"] and x["signalWeekAgo"] != x["signal"]]

    s_names = {r["symbol"]: f"{r['name']} ({next(x['name'] for x in s['groups'] if x['id'] == r['group'])})" for r in s["rows"]}
    w_names = {r["code"]: r["name"] for r in w["rows"]}

    def paper(p, names):
        if not p:
            return None
        last = lambda cur, g: next((v for v in reversed(p[cur][g]) if v is not None), None)
        hold = lambda hs: [{"name": names.get(h["key"], h["key"]), "sinceStartGbp": h.get("sinceGbp")} for h in hs]
        return {"started": p["started"], "holdings": hold(p["holdings"]), "bottomHoldings": hold(p["bottomHoldings"]),
                "valueGbp": {g: last("gbp", g) for g in ("top", "bottom", "mkt", "world")}, "startValue": 10000,
                "nextPicks": p["nextRebalance"]}

    us = s["benches"].get("us", {})
    facts = {
        "generated": now.strftime("%Y-%m-%d %H:%M UTC"),
        "weekEnding": week_ending(now).isoformat(),
        "worldStocks": {"name": "MSCI ACWI (all world stocks)", "weekUsd": w["world"]["m"].get("r1w"),
                        "weekGbp": (w["world"].get("gbp") or {}).get("r1w"), "yearGbp": (w["world"].get("gbp") or {}).get("r1y")},
        "usMarket": {"name": "S&P 500", "weekUsd": us.get("m", {}).get("r1w"), "weekGbp": (us.get("gbp") or {}).get("r1w")},
        "economicRead": {"phase": s["cycle"]["phase"], "notes": s["cycle"]["notes"],
                         "sectorsThatUsuallyDoWell": s["cycle"]["favoured"]},
        "todaysConditions": [{"rule": x["name"], "note": x["note"]} for x in w["rules"] if x["active"]],
        "sectors": {"count": len(srows), "highestScores": by(srows, "score"), "lowestScores": by(srows, "score", False),
                    "biggestScoreRises": by(srows, "scoreChangeWeek"), "biggestScoreFalls": by(srows, "scoreChangeWeek", False),
                    "signalChanges": changed(srows), "bestWeekGbp": by(srows, "weekReturnGbp"), "worstWeekGbp": by(srows, "weekReturnGbp", False)},
        "countries": {"count": len(crows), "highestScores": by(crows, "score"), "lowestScores": by(crows, "score", False),
                      "biggestScoreRises": by(crows, "scoreChangeWeek"), "biggestScoreFalls": by(crows, "scoreChangeWeek", False),
                      "signalChanges": changed(crows), "bestWeekGbp": by(crows, "weekReturnGbp"), "worstWeekGbp": by(crows, "weekReturnGbp", False),
                      "biggestCurrencyMoves": sorted((x for x in crows if x["currencyWeekVsUsd"] is not None and x["currency"] not in PEGGED),
                                                     key=lambda x: -abs(x["currencyWeekVsUsd"]))[:4],
                      "cheapWithHoldingUp": [x for x in crows if (x["valueScore"] or 0) >= 60 and (x["score"] or 0) >= 45][:5]},
        "practicePortfolios": {"sectors": paper(s.get("paper"), s_names), "countries": paper(w.get("paper"), w_names)},
        "scoreTestOnThePast": {
            "sectors": {"topVsLowestGroupPerYear": s["backtest"]["spreadAnn"], "reliabilityT": s["backtest"]["spreadT"],
                        "topAfterCostsPerYear": s["backtest"]["topNetAnn"]} if s.get("backtest") else None,
            "countries": {"topVsLowestGroupPerYear": w["backtest"]["spreadAnn"], "reliabilityT": w["backtest"]["spreadT"],
                          "topAfterCostsPerYear": w["backtest"]["topNetAnn"]} if w.get("backtest") else None},
    }
    return facts


def draft(f):
    """A plain, factual Markdown draft built only from the facts."""
    L = [f"# Weekly briefing: week to {long_date(f['weekEnding'])}", "",
         "*Automatic factual draft. Claude rewrites this into a fuller briefing each Saturday morning.*", "",
         "## The big picture", ""]
    ws, us = f["worldStocks"], f["usMarket"]
    L.append(f"- World stocks (MSCI ACWI) were {pctw(ws['weekGbp'])} this week in pounds ({pctw(ws['weekUsd'])} in US dollars), and {pctw(ws['yearGbp'])} over the past year in pounds.")
    L.append(f"- The US market (S&P 500) was {pctw(us['weekUsd'])} this week in US dollars ({pctw(us['weekGbp'])} in pounds).")
    L.append(f"- Our economic read: **{f['economicRead']['phase']}**. " + " ".join(f["economicRead"]["notes"][:3]))
    if f["todaysConditions"]:
        L.append("- Conditions affecting countries: " + "; ".join(c["rule"] for c in f["todaysConditions"]) + ".")
    for label, key, own in (("Sectors", "sectors", "weekReturnOwnCurrency"), ("Countries", "countries", "weekReturnUsd")):
        d = f[key]
        L += ["", f"## {label}", ""]
        L.append("- Highest scores: " + ", ".join(f"{x['name']}{' (' + x['region'] + ')' if key == 'sectors' else ''} {x['score']}" for x in d["highestScores"]) + ".")
        L.append("- Lowest scores: " + ", ".join(f"{x['name']}{' (' + x['region'] + ')' if key == 'sectors' else ''} {x['score']}" for x in d["lowestScores"]) + ".")
        rises = [x for x in d["biggestScoreRises"] if (x["scoreChangeWeek"] or 0) >= 1]
        falls = [x for x in d["biggestScoreFalls"] if (x["scoreChangeWeek"] or 0) <= -1]
        if rises:
            L.append("- Biggest score rises this week: " + ", ".join(f"{x['name']}{' (' + x['region'] + ')' if key == 'sectors' else ''} up {round(x['scoreChangeWeek'])}" for x in rises) + ".")
        if falls:
            L.append("- Biggest score falls this week: " + ", ".join(f"{x['name']}{' (' + x['region'] + ')' if key == 'sectors' else ''} down {abs(round(x['scoreChangeWeek']))}" for x in falls) + ".")
        if d["signalChanges"]:
            L.append("- Signal changes this week: " + "; ".join(f"{x['name']}{' (' + x['region'] + ')' if key == 'sectors' else ''}: {x['signalWeekAgo']} → {x['signal']}" for x in d["signalChanges"][:12]) + ".")
        else:
            L.append("- No signal changes this week.")
        nm = lambda x: f"{x['name']} ({x['region']})" if key == "sectors" else x["name"]
        L.append("- Best this week (in pounds): " + ", ".join(f"{nm(x)} {signed(x['weekReturnGbp'])}" for x in d["bestWeekGbp"]) + ".")
        L.append("- Worst this week (in pounds): " + ", ".join(f"{nm(x)} {signed(x['weekReturnGbp'])}" for x in d["worstWeekGbp"]) + ".")
        if key == "countries" and d["biggestCurrencyMoves"]:
            L.append("- Biggest currency moves against the US dollar: " + ", ".join(f"{x['currency']} {signed(x['currencyWeekVsUsd'])}" for x in d["biggestCurrencyMoves"]) + ".")
    L += ["", "## Practice portfolios", ""]
    for label, key in (("Sectors", "sectors"), ("Countries", "countries")):
        p = f["practicePortfolios"][key]
        if not p:
            L.append(f"- {label}: not started yet.")
            continue
        v = p["valueGbp"]
        L.append(f"- {label} (started {p['started']} with £10,000): top-scored picks £{v['top']:,.0f}, lowest-scored £{v['bottom']:,.0f}, "
                 f"same money in the picks' own markets £{v['mkt']:,.0f}, world stocks £{v['world']:,.0f}. Next monthly picks: {p['nextPicks']}.")
    t = f["scoreTestOnThePast"]
    L += ["", "## Keep in mind", ""]
    if t["sectors"]:
        L.append(f"- Tested on the past, the top-scored sector funds did {signed(t['sectors']['topVsLowestGroupPerYear'])} a year compared with the lowest-scored (reliability t = {t['sectors']['reliabilityT']:.1f}; 2 or more is convincing).")
    if t["countries"]:
        L.append(f"- For countries the same test gave {signed(t['countries']['topVsLowestGroupPerYear'])} a year (t = {t['countries']['reliabilityT']:.1f}): the score has not reliably picked winning countries.")
    L.append("- Scores describe past price behaviour; they are not forecasts or advice.")
    return "\n".join(L) + "\n"


def main():
    facts = gather()
    date = facts["weekEnding"]
    md = OUT / f"{date}.md"
    written_by_claude = md.exists() and "author: Claude" in md.read_text(encoding="utf-8")[:300]
    if not written_by_claude:  # once Claude has written the week up, its facts and text stay as they are
        (OUT / "facts").mkdir(parents=True, exist_ok=True)
        (OUT / "facts" / f"{date}.json").write_text(json.dumps(engine.clean(facts), indent=1), encoding="utf-8")
        md.write_text(draft(facts), encoding="utf-8")
    index_path = OUT / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
    index = [e for e in index if e["date"] != date]
    title = f"Week to {long_date(date, weekday=False)}"
    index.insert(0, {"date": date, "title": title, "file": f"{date}.md", "author": "Claude" if written_by_claude else "draft"})
    index_path.write_text(json.dumps(sorted(index, key=lambda e: e["date"], reverse=True), indent=1), encoding="utf-8")
    print(f"Briefing facts and {'existing Claude briefing kept' if written_by_claude else 'draft written'} for week to {date}.")


if __name__ == "__main__":
    main()
