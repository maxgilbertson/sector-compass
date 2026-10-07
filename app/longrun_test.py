"""Test the score as a long-term investor would use it: buy the top fifth and keep them a year. Run once, as fixed.

    py app/longrun_test.py

Fixed on 7 Oct 2026, before running (engine.long_hold_test):

  Rule      At each month-end, the buyable funds (Sectors) or countries (Countries) in the top fifth by
            score, scored across the whole page with data up to that day. Hold them in equal amounts
            for 12 months. Buyable = has a UCITS version on IBKR (universe.buy_on_ibkr, world.buy_on_ibkr).
  Measure   Each holding's 12-month return minus its own market's (Sectors: its region's market;
            Countries: world stocks), minus one round of trading costs (0.15% to buy, 0.15% to sell).
  Bar       That, minus the same for every buyable fund held equally. Twelve-month periods started
            each month overlap, so reliability is a Newey-West t-statistic (11 lags):
              t >= 2 and ahead -> "Probably helped"; t >= 1 and ahead -> "Possibly helped";
              otherwise -> "Didn't help".
            Also reported, not used to decide: each half of the period, the result against the
            markets themselves, and the share of 12-month periods that beat their markets.

Not to be tuned to the result. Known weaknesses: about nine years of data gives only nine
non-overlapping years; the buyable list is today's, so it assumes twins existed throughout.

Result, run once on 7 Oct 2026 (96 start months, Oct 2017 to Sep 2025):
  Sectors    top fifth vs their markets after costs +0.5% a year (t = 0.24); all buyable +0.1%;
             EDGE +0.4% a year (t = 0.20); halves -1.2% then +2.0%.          VERDICT: Didn't help
  Countries  top fifth vs world stocks after costs -4.4% a year (t = -2.83); all buyable -3.5%;
             EDGE -0.9% a year (t = -1.03); halves -0.1% then -1.7%.         VERDICT: Didn't help
  So over a year, neither score picked better than holding everything buyable, and single countries
  lagged world stocks. The pages' "For the long run" sections lead with whole-market funds instead.
"""
from datetime import datetime, timezone

import engine
import sectors
import universe
import world


def page_tracks(module):
    captured, real = {}, engine.apply_scores

    def spy(rows, tracks, rf_at):
        captured.update(rows=rows, tracks=tracks, rf_at=rf_at)
        return real(rows, tracks, rf_at)

    engine.apply_scores = spy
    try:
        module.build()
    finally:
        engine.apply_scores = real
    return captured["rows"], captured["tracks"], captured["rf_at"]


def verdict(t, ahead):
    return "Probably helped" if ahead and t >= 2 else "Possibly helped" if ahead and t >= 1 else "Didn't help"


def main():
    month = lambda ts: datetime.fromtimestamp(ts, timezone.utc).strftime("%b %Y")
    pc = lambda v: f"{v * 100:+.1f}%"
    for name, module, buy in (("Sectors", sectors, lambda r: universe.buy_on_ibkr(r["symbol"])),
                              ("Countries", world, lambda r: world.buy_on_ibkr(r["code"]))):
        rows, tracks, rf_at = page_tracks(module)
        bt = engine.long_hold_test(tracks, rf_at, [bool(buy(r)) for r in rows])
        print(f"\n## {name}: {sum(bool(buy(r)) for r in rows)} of {len(rows)} buyable; "
              f"{bt['starts']} start months, {month(bt['from'])} to {month(bt['to'])}, held {bt['hold']} months")
        print(f"Top fifth vs their markets, after costs: {pc(bt['topNetAnn'])} a year (t = {bt['topNetT']:.2f}); "
              f"beat their markets in {bt['beatMarketShare']:.0%} of 12-month periods")
        print(f"All buyable held equally, vs their markets: {pc(bt['allAnn'])} a year")
        print(f"EDGE (top fifth after costs minus all buyable): {pc(bt['edgeAnn'])} a year, t = {bt['edgeT']:.2f}, ahead in {bt['hit']:.0%}")
        for label, h in zip(("1st half", "2nd half"), bt["halves"]):
            print(f"  {label} ({month(h['from'])}-{month(h['to'])}): {pc(h['edgeAnn'])} a year, t = {h['edgeT'] if h['edgeT'] is None else round(h['edgeT'], 2)}")
        print("VERDICT (pre-registered bar):", verdict(bt["edgeT"] or 0, bt["edgeAnn"] > 0))


if __name__ == "__main__":
    main()
