"""Test alternative score recipes the careful way, without touching the live one.

    py research.py

Each candidate recipe is backtested and judged on the FIRST half of the period only.
A change is worth adopting only if it beats the current recipe there AND still beats it
on the second half, which it never saw. Anything else is likely fitting to the past.
"""
from datetime import datetime, timezone

import engine
import sectors
import world

CANDIDATES = {
    "Current recipe": engine.WEIGHTS,
    "Momentum only (12-1)": {"mom121_rel": 1.0},
    "Relative returns only": {"mom121_rel": 0.4, "rs6m": 0.4, "rs3m": 0.2},
    "Trend only": {"trend": 1.0},
    "Momentum + trend": {"mom121_rel": 0.5, "trend": 0.5},
    "Risk measures only": {"sharpe": 0.5, "mdd": 0.5},
}


def page_tracks(module):
    """Run the page's normal build once and keep the price tracks it scores."""
    captured = {}
    real = engine.apply_scores

    def spy(rows, tracks, rf_at):
        captured["tracks"], captured["rf_at"] = tracks, rf_at
        return real(rows, tracks, rf_at)

    engine.apply_scores = spy
    try:
        module.build()
    finally:
        engine.apply_scores = real
    return captured["tracks"], captured["rf_at"]


def fmt(v, pct=True):
    return "–" if v is None else (f"{v * 100:+.1f}%" if pct else f"{v:.1f}")


def main():
    month = lambda ts: datetime.fromtimestamp(ts, timezone.utc).strftime("%b %Y")
    for name, module in (("Sectors", sectors), ("Countries", world)):
        tracks, rf_at = page_tracks(module)
        print(f"\n## {name}\n")
        print("| Recipe | 1st half: gap/yr (t) | 2nd half: gap/yr (t) | Top group after costs/yr | Verdict |")
        print("|---|---|---|---|---|")
        base = None
        for label, weights in CANDIDATES.items():
            bt = engine.backtest(tracks, rf_at, weights=weights)
            h1, h2 = bt["halves"]
            if base is None:
                base = (h1["spreadAnn"], h2["spreadAnn"])
                verdict = "baseline"
            else:
                better1, better2 = h1["spreadAnn"] > base[0], h2["spreadAnn"] > base[1]
                # an improvement must hold on the half it never saw, be positive there, and be reasonably reliable
                convincing = better1 and better2 and h2["spreadAnn"] > 0 and (h2["spreadT"] or 0) >= 1
                verdict = ("beats current in both halves and holds up on unseen data: worth a closer look" if convincing
                           else "slightly better in both halves, but too weak to trust" if better1 and better2
                           else "better on the 1st half only: likely luck" if better1
                           else "not better on the 1st half: reject")
            print(f"| {label} | {fmt(h1['spreadAnn'])} ({fmt(h1['spreadT'], False)}) | {fmt(h2['spreadAnn'])} ({fmt(h2['spreadT'], False)}) "
                  f"| {fmt(bt['topNetAnn'])} | {verdict} |")
        print(f"\nHalves: {month(h1['from'])}–{month(h1['to'])} and {month(h2['from'])}–{month(h2['to'])}. "
              "Gap = top-scored 20% minus lowest-scored 20%, vs their markets, per year on average.")


if __name__ == "__main__":
    main()
