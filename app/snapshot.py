"""Daily snapshot: save every score, and make the monthly practice-portfolio picks.

Run by .github/workflows/daily.yml after the US close each weekday; the workflow
commits data/history/ and data/paper/ back to the repository so the record is permanent.
"""
import sys

import sectors
import tracking
import world


def main():
    s, w = sectors.build(), world.build()
    if len(s["rows"]) < 60 or len(w["rows"]) < 25:
        sys.exit(f"Too few markets loaded (sectors {len(s['rows'])}, countries {len(w['rows'])}); not saving a snapshot.")
    tracking.write_snapshot("sectors", s["rows"], "symbol", {"cycle": s["cycle"]["phase"]})
    tracking.write_snapshot("countries", w["rows"], "code", {"rules": [x["name"] for x in w["rules"] if x["active"]]})
    for page, rows, key in (("sectors", s["rows"], "symbol"), ("countries", w["rows"], "code")):
        if tracking.maybe_rebalance(page, rows, key):
            log = tracking.load_paper(page)
            print(f"{page}: new monthly picks: {', '.join(log['rebalances'][-1]['top'])}")
    print(f"Saved snapshot for {tracking.today_key()}: {len(s['rows'])} sector funds, {len(w['rows'])} countries.")


if __name__ == "__main__":
    main()
