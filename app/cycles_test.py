"""Test buying the dip in cyclical indices, once, as fixed in advance.

    py app/cycles_test.py

Fixed on 7 Oct 2026, before running (cycles.dip_test):

  Indices   The cyclical indices in cycles.INDICES (UK FTSE 350, STOXX Europe 600 and US sector indices), chosen as
            the classic boom-and-bust industries, with the data fixes in cycles.FIXES (found before the test ran).
            CNBC price indices, so dividends are left out.
  Measures  At each month-end, from month-end closes only: how far the index is below its highest month-end close
            of the past 5 years (60 month-ends), and its level against its average over those 60 month-ends and
            over the last 10. An index joins the test once it has 5 years of month-ends.
  Rules     A  "In a deep dip": 30% or more below its 5-year high.
            B  "Down but turning up": below its 5-year average and above its 10-month average.
  Measure   The index's change over the next 12 months, minus its own average 12-month change over all its test
            months (that is, against buying the same index at any time), averaged over every month-end the rule
            picked, all indices together.
  Fairness  Measuring against an average that includes the dips themselves flatters dip-buying even when there is
            nothing to find (on made-up random prices it showed about +2% a year). So each result is compared with
            1,000 reshuffled histories: the same months' changes in a random order, one order shared by all the
            indices (seed 2026), which keeps how bumpy the indices are and how they move together, but removes any
            pattern over time.
              edge = the real figure minus the reshuffled histories' average
              p    = the share of reshuffled histories at least as good as the real figure
  Bar       edge > 0 and p < 2.5% -> "Probably worked"; edge > 0 and p < 16% -> "Possibly worked";
            otherwise "Didn't work" (the one-sided equivalents of the t >= 2 and t >= 1 bars in the other tests).
            Also reported, not used to decide: each half of the period; the same over 3 years; the next 12 months
            against the region's whole market (FTSE All-Share, STOXX Europe 600, S&P 500); the share of picks that
            were higher a year later; how much further they fell first; and the same figures for each of the four
            phases and five dip depths.

Not to be tuned to the result. Known weaknesses: dips cluster in a few crises (1990-92, 2000-03, 2008-09, 2015-16,
2020, 2022), so there are far fewer separate dips than months; the indices were picked today as known cyclicals;
price indices leave out dividends; and an index can't be bought directly (a fund charges a fee, and no fund tracks
the UK FTSE 350 sectors).
"""
from datetime import datetime, timezone

import cycles


def main():
    month = lambda ts: datetime.fromtimestamp(ts, timezone.utc).strftime("%b %Y")
    pc = lambda v: "–" if v is None else f"{v * 100:+.1f}%"
    sh = lambda v: "–" if v is None else f"{v:.0%}"
    pv = lambda v: "–" if v is None else f"{v:.1%}"
    region_of = {x[0]: x[4] for x in cycles.INDICES}
    series, errors = cycles.load([x[0] for x in cycles.INDICES] + [r["market"] for r in cycles.REGIONS.values()] + sorted(cycles.AUX))
    if errors:
        print("Missing:", errors)
    test, _ = cycles.dip_test(series, region_of)
    print(f"{test['indices']} indices, {test['obs']} index-months, {month(test['from'])} to {month(test['to'])}; "
          f"{test['shuffles']} reshuffles; split at {month(test['mid'])}")
    for k, r in test["rules"].items():
        print(f"\n## {r['label']}")
        print(f"Picked {r['n']} index-months: {r['episodes']} separate dips in {r['indices']} indices")
        print(f"Next 12 months: {pc(r['avg'])} on average (all months {pc(r['avgAll'])}); higher a year later {sh(r['up'])} (all {sh(r['upAll'])})")
        print(f"vs the same index at any time: {pc(r['ex'])}; EDGE after the reshuffle check {pc(r['edge'])}, p = {pv(r['p'])}")
        for label, h in zip(("1st half", "2nd half"), r["halves"]):
            print(f"  {label} ({month(h['from'])}-{month(h['to'])}, {h['n']} picks): {pc(h['ex'])}, edge {pc(h['edge'])}, p = {pv(h['p'])}")
        print(f"Over 3 years: {pc(r['avg3'])} (all {pc(r['avg3All'])}); vs any time {pc(r['ex3'])}, edge {pc(r['edge3'])}, p = {pv(r['p3'])}")
        print(f"vs its region's whole market, next 12 months: {pc(r['vsMkt'])}, edge {pc(r['edgeMkt'])}, p = {pv(r['pMkt'])}")
        print(f"Fell further first: median {pc(r['low'])} (all {pc(r['lowAll'])}); worst {pc(r['worstLow'])}; 20%+ further {sh(r['fellMore20'])}")
        print("VERDICT (pre-registered bar):", r["verdict"])
    for kind in ("phases", "depths"):
        print(f"\n## By {kind[:-1]} (reported, not tested)")
        for r in test[kind]:
            print(f"  {r['label'][:34]:34} n {r['n']:5}  next 12m {pc(r['avg']):>7}  vs any time {pc(r['ex']):>7}  "
                  f"edge {pc(r['edge']):>7}  p {pv(r['p']):>6}  higher {sh(r['up'])}")


if __name__ == "__main__":
    main()
