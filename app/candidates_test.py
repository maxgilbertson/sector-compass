"""Test the "candidates for a new holding" rule on past data, once, as fixed in advance.

    py app/candidates_test.py

Fixed on 7 Oct 2026, before running (see engine.is_candidate and engine.candidate_backtest):

  Rule      A buyable fund (UCITS itself or with a UCITS twin on IBKR, universe.buy_on_ibkr) with
            a score of 60 or more, at least 3 of the 4 uptrend checks, an RSI under 70, and a price
            no more than 15% above its 200-day average.
  Test      Each month-end since history allows: score every fund with data up to that day, hold the
            candidates in equal amounts for a month, measure the return against each fund's own market,
            charge 0.15% per trade on the money moved.
  Bar       Candidates (after costs) vs holding every buyable fund equally, per month:
              reliability t >= 2 and ahead  -> "Probably helped"
              t >= 1 and ahead              -> "Possibly helped"
              otherwise                     -> "Didn't help"
            Also reported, not used to decide: each half of the period, the result against the funds'
            own markets, the buyable top 20% by score, and how many candidates there were.

The rule is not to be changed in response to this result. Known weakness: which funds count as buyable
uses today's list, so the test assumes twins existed throughout (several launched only in 2021-23).

Result, run once on 7 Oct 2026 (Oct 2017 to Aug 2026, 107 months, 57 buyable funds):
  Candidates vs their own markets: -1.7% a year before costs, -3.7% after (t = -1.89)
  All buyable funds held equally: -0.6% a year; buyable top 20% by score: +1.9% a year (before costs)
  EDGE: -3.1% a year (t = -1.45); 1st half -2.6% (t = -0.87), 2nd half -3.6% (t = -1.16)
  VERDICT: Didn't help. Skipping funds that had risen fast removed the ones that kept rising, and the
  frequent switching cost about 2% a year. The rule is therefore NOT used to pick funds on the site; the
  "Worth opening a holding" section lists the buyable top 20% by score (the selection already tested by
  engine.backtest) and only shows fast rises as a warning.
"""
from datetime import datetime, timezone

import engine
import sectors
import universe


def page_tracks():
    """Run the Sectors build once and keep the rows and price tracks it scores."""
    captured, real = {}, engine.apply_scores

    def spy(rows, tracks, rf_at):
        captured.update(rows=rows, tracks=tracks, rf_at=rf_at)
        return real(rows, tracks, rf_at)

    engine.apply_scores = spy
    try:
        sectors.build()
    finally:
        engine.apply_scores = real
    return captured["rows"], captured["tracks"], captured["rf_at"]


def verdict(t, ahead):
    return "Probably helped" if ahead and t >= 2 else "Possibly helped" if ahead and t >= 1 else "Didn't help"


def main():
    rows, tracks, rf_at = page_tracks()
    buyable = [bool(universe.buy_on_ibkr(r["symbol"])) for r in rows]
    bt = engine.candidate_backtest(tracks, rf_at, buyable)
    month = lambda ts: datetime.fromtimestamp(ts, timezone.utc).strftime("%b %Y")
    pc = lambda v: f"{v * 100:+.1f}%"
    print(f"{sum(buyable)} of {len(rows)} funds buyable; {bt['months']} months, {month(bt['from'])} to {month(bt['to'])}")
    print(f"Candidates per month: {bt['avgPicks']:.1f} on average; {bt['emptyMonths']} months with none")
    print(f"Candidates vs their own markets, per year: {pc(bt['candAnn'])} before costs, {pc(bt['candNetAnn'])} after (t = {bt['candNetT']:.2f})")
    print(f"All buyable funds held equally, vs their markets: {pc(bt['allAnn'])} a year")
    print(f"Buyable top 20% by score, vs their markets: {pc(bt['topAnn'])} a year (before costs)")
    print(f"EDGE (candidates after costs minus all buyable): {pc(bt['edgeAnn'])} a year, t = {bt['edgeT']:.2f}, ahead in {bt['hit']:.0%} of months")
    for name, h in zip(("1st half", "2nd half"), bt["halves"]):
        print(f"  {name} ({month(h['from'])}-{month(h['to'])}): {pc(h['edgeAnn'])} a year, t = {h['edgeT']:.2f}")
    print("VERDICT (pre-registered bar):", verdict(bt["edgeT"] or 0, bt["edgeAnn"] > 0))


if __name__ == "__main__":
    main()
