"""The biggest companies in each cyclical index on the Cycles tab (keys as in cycles.INDICES).

Index providers don't publish their constituent weights for free, so each index uses the best free source:
  fund     A fund that tracks the index (the iShares STOXX Europe 600 funds, Invesco's SOXQ for the PHLX
           Semiconductor index, KBWB for the KBW Bank index): its latest published top-10 holdings, from Yahoo
           Finance. The fund's weights follow the index's, so these count as exact.
  lse      UK FTSE 350 sectors: the FTSE 350's members and their weights from the iShares FTSE 100 and FTSE 250
           funds' daily holdings files (the FTSE 250 fund holds about 237 of the 250, leaving out only small ones),
           and each company's sector code and market value from the London Stock Exchange. The funds follow FTSE's
           weights, which count only freely traded shares; they are put on one scale using the market values (for a
           typical company, freely traded value = market value), and a company's share is its freely traded value
           over the sector's total.
  capped   PHLX Housing, Oil Service and Gold/Silver: the members from Nasdaq (which runs these indices), and
           shares worked out from Yahoo Finance market values with each index's published caps. The indices reset
           their weights every quarter, so the real ones drift a little from these in between.
  price    Dow Jones Transportation Average: price-weighted, so a company's share is its share price over the
           total of the 20 prices. The members come from Wikipedia's list.

    py app/constituents.py        (run weekly by .github/workflows/constituents.yml; writes data/constituents.json)
"""
import csv
import io
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "constituents.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SectorCompass/1.0 (personal tracker)"}
TOP = 10

FUND = {  # cycles key: (fund on Yahoo Finance, what it tracks if not exactly the index)
    "eu-resources": ("EXV6.DE", ""), "eu-autos": ("EXV5.DE", ""), "eu-banks": ("EXV1.DE", ""), "eu-chem": ("EXV7.DE", ""),
    "eu-build": ("EXV8.DE", ""), "eu-travel": ("EXV9.DE", ""),
    "eu-energy": ("EXH1.DE", "the STOXX Europe 600 Oil & Gas index, almost the same companies"),
    "us-chips": ("SOXQ", ""), "us-banks": ("KBWB", ""),
}
FUND_NAMES = {"EXV6.DE": "iShares STOXX Europe 600 Basic Resources", "EXV5.DE": "iShares STOXX Europe 600 Automobiles & Parts",
              "EXV1.DE": "iShares STOXX Europe 600 Banks", "EXV7.DE": "iShares STOXX Europe 600 Chemicals",
              "EXV8.DE": "iShares STOXX Europe 600 Construction & Materials", "EXV9.DE": "iShares STOXX Europe 600 Travel & Leisure",
              "EXH1.DE": "iShares STOXX Europe 600 Oil & Gas", "SOXQ": "Invesco PHLX Semiconductor ETF",
              "KBWB": "Invesco KBW Bank ETF"}
LSE_SECTOR = {"uk-mining": "551020", "uk-oil": "601010", "uk-banks": "301010", "uk-homes": "402020", "uk-build": "501010",
              "uk-eng": "502040", "uk-transport": "502060", "uk-chem": "552010", "uk-travel": "405010", "uk-retail": "404010"}
ISHARES = {"FTSE 100": "https://www.ishares.com/uk/individual/en/products/251795/ishares-core-ftse-100-ucits-etf/latest-holdings.csv",
           "FTSE 250": "https://www.ishares.com/uk/individual/en/products/251796/ishares-ftse-250-ucits-etf/latest-holdings.csv"}
# Nasdaq's methodology documents: no company above c1 at first; then the k biggest keep that weight and the rest are
# capped at c2, with what is cut shared out among the others in proportion to their size.
CAPPED = {"us-housing": ("HGX", 0.15, 2, 0.08), "us-oilserv": ("OSX", 0.15, 2, 0.08), "us-gold": ("XAU", 0.08, 5, 0.04)}
PRICE = {"us-transport": "Dow Jones Transportation Average"}


def _get(url, data=None, headers=None, timeout=30, tries=3):
    err = None
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers={**UA, **(headers or {})}), timeout=timeout) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001 - retried, then raised
            err = e
            time.sleep(1.5 * (k + 1))
    raise err


# ---------------------------------------------------------------- names and values from Yahoo Finance

def yahoo_info(symbols):
    """{symbol: {"name", "cap", "price", "ccy"}} from Yahoo Finance, four at a time."""
    import yfinance as yf

    def one(s):
        for k in range(3):
            try:
                i = yf.Ticker(s).info or {}
                # the long name is the cleaner one ("Rio Tinto Group", not "Rio Tinto Plc Ord 10p")
                return s, {"name": i.get("longName") or i.get("shortName"), "cap": i.get("marketCap"),
                           "price": i.get("regularMarketPrice") or i.get("currentPrice"), "ccy": i.get("currency")}
            except Exception:  # noqa: BLE001
                time.sleep(2 * (k + 1))
        return s, {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        return dict(ex.map(one, sorted(set(symbols))))


ACRONYMS = {"HSBC", "BP", "IAG", "JD", "BAE", "BT", "GSK", "RELX", "ITV", "IMI", "WPP", "SSE", "DCC", "ICG", "ASOS", "B&M", "TBC", "IG",
            "US", "UK", "SPX", "AJ", "LSEG", "IHG", "BBVA", "BNP", "ING", "UPM", "ABB", "DSV", "CRH", "TUI", "SEB", "KBC", "NN",
            "NVIDIA", "AMD", "ASML", "BASF", "BMW", "UBS", "AIB", "RWE", "SAP", "ENI", "OMV", "SSAB", "NXP", "KLA", "SLB", "NOV", "CSX", "UPS", "ON", "TSMC", "PNC", "KB", "LNG", "II", "III"}
_LEGAL = r"(PLC|P\.L\.C\.?|Inc\.?|Incorporated|Corp(oration)?\.?|Company|Co\.?|Ltd\.?|Limited|S\.A\.?|SA|N\.V\.?|NV|AG|SE|ASA|AB( \(publ\))?|S\.p\.A\.?|SpA|Oyj|Group Plc|Aktiengesellschaft|KGaA)"


SHORT = {"Compagnie Générale des Établissements Michelin": "Michelin", "L'Air Liquide": "Air Liquide",
         "Compagnie de Saint-Gobain": "Saint-Gobain", "Banco Bilbao Vizcaya Argentaria": "BBVA", "Rio Tinto Group": "Rio Tinto",
         "International Consolidated Airlines Group": "IAG (British Airways)", "Bayerische Motoren Werke": "BMW",
         "Taiwan Semiconductor Manufacturing": "TSMC", "Lloyds Banking": "Lloyds Banking Group"}


def tidy(name):
    """Company names as people say them: 'Rio Tinto', not 'RIO TINTO PLC' or 'Rio Tinto Plc Ord 10p'."""
    if not name:
        return name
    n = re.sub(r"^The\s+", "", name.strip())
    n = re.sub(r"\s*\((The|Holding|Holdings|Switzerland|publ|[A-Z]{2,3})\)\s*$", "", n)                   # "(The)", "(Switzerland)"
    n = re.sub(r"\s+(Ord(inary)?( Shares)?|Class [A-Z]|Registered Shares|Shs|ADR|NY Reg|Reg|Pref)\b.*$", "", n, flags=re.I)
    n = re.sub(r"\s+(AG|SA|SE|NV|ASA|AB|SpA|Oyj|PLC)\b\.?\s+\S.*$", "", n, flags=re.I)                     # "Volkswagen AG Vz"
    n = re.sub(r"\s+N$", "", n)                                                                             # "Givaudan N" (registered shares)
    for _ in range(2):                                                                                      # "Co., Inc." takes two
        n = re.sub(r"(,|\s)+(&\s+)?" + _LEGAL + r"$", "", n.strip(" ,."), flags=re.I)
    if n.isupper():  # the exchange's capitals: "LLOYDS BANKING GROUP" -> "Lloyds Banking Group", but keep HSBC, BP...
        n = " ".join(w if w in ACRONYMS else w.capitalize() for w in n.split())
    n = re.sub(r"\s+(Soci[ée]t[ée] en commandite par actions|SCA|S\.C\.A\.)$", "", n.strip(" ,."))
    return SHORT.get(n, n) or name


# ---------------------------------------------------------------- the four kinds of source

def from_funds():
    import yfinance as yf
    out = {}
    for key, (fund, differs) in FUND.items():
        try:
            th = yf.Ticker(fund).funds_data.top_holdings
            rows = [{"sym": str(s), "name": str(r.get("Name") or s), "w": float(r.get("Holding Percent") or 0)} for s, r in th.head(TOP).iterrows()]
        except Exception as e:  # noqa: BLE001
            print(f"[{key}] {fund}: {e}", flush=True)
            continue
        if rows:
            out[key] = {"kind": "fund", "basis": "exact", "fund": fund, "fundName": FUND_NAMES.get(fund, fund), "differs": differs, "top": rows}
    names = yahoo_info([r["sym"] for v in out.values() for r in v["top"]])
    for v in out.values():
        for r in v["top"]:
            r["name"] = tidy((names.get(r["sym"]) or {}).get("name") or r["name"])
    return out


def ishares_members():
    """The FTSE 350 (FTSE 100 + FTSE 250) as held by iShares' funds: {ticker: (index, weight in that fund)}, and the date."""
    members, dates = {}, []
    for index, url in ISHARES.items():
        text = _get(url).decode("utf-8-sig")
        first, rest = text.split("\n", 1)
        m = re.search(r'"?(\d{1,2}/\w{3}/\d{4})"?', first)
        dates.append(datetime.strptime(m.group(1), "%d/%b/%Y").date().isoformat() if m else None)
        body = rest.lstrip("\r\n")
        for row in csv.DictReader(io.StringIO(body)):
            t = (row.get("Ticker") or "").strip()
            if t and (row.get("Asset Class") or "").strip() == "Equity":
                try:
                    w = float((row.get("Weight (%)") or "0").replace(",", "")) / 100
                except ValueError:
                    w = 0.0
                members[t] = (index, w)
    if len(members) < 300:
        raise RuntimeError(f"only {len(members)} FTSE 350 members found")
    return members, max(d for d in dates if d)


def lse_info(tickers):
    """{ticker: {"name", "sector", "cap"}} from the London Stock Exchange, three at a time with a short pause."""
    h = {"Accept": "application/json", "Origin": "https://www.londonstockexchange.com", "Referer": "https://www.londonstockexchange.com/"}

    def one(t):
        try:
            d = json.loads(_get("https://api.londonstockexchange.com/api/gw/lse/instruments/alldata/" + urllib.parse.quote(t), headers=h))
            time.sleep(0.3)
            return t, {"name": d.get("issuername") or d.get("shortname"), "sector": d.get("sectorcode"), "cap": d.get("marketcapitalization")}
        except Exception as e:  # noqa: BLE001
            print(f"[lse {t}] {e}", flush=True)
            return t, None
    with ThreadPoolExecutor(max_workers=3) as ex:
        return {t: v for t, v in ex.map(one, sorted(tickers)) if v}


def from_lse():
    members, as_of = ishares_members()
    info = lse_info(members)
    if len(info) < 0.9 * len(members):
        raise RuntimeError(f"London Stock Exchange data for only {len(info)} of {len(members)} companies")
    # each fund's weights on one scale: value = weight x the fund's typical market value per unit of weight
    # (a company whose shares are nearly all freely traded sits at the typical ratio; one with a big controlling
    # owner, such as Antofagasta, has a smaller weight for its size, as in FTSE's own index)
    scale = {}
    for index in ISHARES:
        ratios = sorted(float(info[t]["cap"]) / w for t, (ix, w) in members.items() if ix == index and w > 0 and (info.get(t) or {}).get("cap"))
        scale[index] = ratios[len(ratios) // 2] if ratios else None
    out = {}
    for key, code in LSE_SECTOR.items():
        rows = []
        for t, v in info.items():
            ix, w = members.get(t, (None, 0))
            if v.get("sector") == code and w > 0 and scale.get(ix):
                rows.append({"sym": t, "name": v["name"], "cap": w * scale[ix]})
        rows.sort(key=lambda r: -r["cap"])
        total = sum(r["cap"] for r in rows)
        if not rows or total <= 0:
            continue
        for r in rows:
            r["w"] = r["cap"] / total
        out[key] = {"kind": "lse", "basis": "estimated", "count": len(rows), "total": total, "ccy": "GBP", "holdingsAsOf": as_of,
                    "top": rows[:TOP]}
    names = yahoo_info([r["sym"].rstrip(".") + ".L" for v in out.values() for r in v["top"]])
    for v in out.values():
        for r in v["top"]:
            r["name"] = tidy((names.get(r["sym"].rstrip(".") + ".L") or {}).get("name") or r["name"])
    return out


def nasdaq_members(index):
    """The current members of a Nasdaq-run index (symbols and names), from its public weighting page."""
    h = {"Content-Type": "application/x-www-form-urlencoded", "X-Requested-With": "XMLHttpRequest", "Accept": "application/json"}
    day = date.today()
    for _ in range(7):  # the latest trading day with data
        day -= timedelta(days=1)
        if day.weekday() >= 5:
            continue
        data = urllib.parse.urlencode({"id": index, "tradeDate": f"{day.isoformat()}T00:00:00.000", "timeOfDay": "SOD"}).encode()
        rows = json.loads(_get("https://indexes.nasdaqomx.com/Index/WeightingData", data, h)).get("aaData") or []
        if rows:
            return [(r["Symbol"], r["Name"]) for r in rows], day.isoformat()
    raise RuntimeError(f"no members found for {index}")


def cap_weights(caps, c1, k, c2):
    """Market-value weights with the index's caps (see CAPPED), largest first in `caps`."""
    def capped(base, cap, total):
        w, fixed = [b * total / sum(base) for b in base], set()
        while True:
            over = [i for i, x in enumerate(w) if x > cap + 1e-12 and i not in fixed]
            if not over:
                return w
            fixed |= set(over)
            free = [i for i in range(len(w)) if i not in fixed]
            left, room = total - cap * len(fixed), sum(base[i] for i in free)
            if not free or room <= 0:
                return [cap if i in fixed else 0.0 for i in range(len(w))]
            w = [cap if i in fixed else base[i] * left / room for i in range(len(w))]
    w1 = capped(caps, c1, 1.0)
    rest = w1[k:]
    return w1[:k] + (capped(rest, c2, 1.0 - sum(w1[:k])) if rest else [])


def from_capped():
    out = {}
    for key, (index, c1, k, c2) in CAPPED.items():
        try:
            members, day = nasdaq_members(index)
        except Exception as e:  # noqa: BLE001
            print(f"[{key}] {e}", flush=True)
            continue
        info = yahoo_info([s for s, _ in members])
        rows = sorted(({"sym": s, "name": tidy((info.get(s) or {}).get("name") or n), "cap": float(info[s]["cap"])}
                       for s, n in members if (info.get(s) or {}).get("cap")), key=lambda r: -r["cap"])
        if len(rows) < 0.8 * len(members):
            print(f"[{key}] market values for only {len(rows)} of {len(members)}", flush=True)
            continue
        for r, w in zip(rows, cap_weights([r["cap"] for r in rows], c1, k, c2)):
            r["w"] = w
        rows.sort(key=lambda r: -r["w"])
        out[key] = {"kind": "capped", "basis": "estimated", "index": index, "count": len(members), "membersAsOf": day,
                    "caps": [c1, k, c2], "top": rows[:TOP]}
    return out


def from_prices():
    out = {}
    for key, page in PRICE.items():
        url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "parse", "page": page, "prop": "wikitext", "format": "json", "formatversion": 2})
        text = json.loads(_get(url))["parse"]["wikitext"]
        members = re.findall(r'!\s*scope="row"\s*\|\s*\[\[([^\]|]+)(?:\|([^\]]+))?\]\]\s*\n\s*\|\s*([A-Z][A-Z.]{0,5})\s*\n', text)
        members = [(t, label or link) for link, label, t in members]
        if not 15 <= len(members) <= 25:
            print(f"[{key}] found {len(members)} members on Wikipedia; skipped", flush=True)
            continue
        info = yahoo_info([t.replace(".", "-") for t, _ in members])
        rows = [{"sym": t, "name": tidy(n.strip()), "price": float((info.get(t.replace(".", "-")) or {}).get("price") or 0)} for t, n in members]
        if sum(r["price"] > 0 for r in rows) < len(rows):
            print(f"[{key}] prices missing for {[r['sym'] for r in rows if not r['price']]}; skipped", flush=True)
            continue
        total = sum(r["price"] for r in rows)
        for r in rows:
            r["w"] = r["price"] / total
        rows.sort(key=lambda r: -r["w"])
        out[key] = {"kind": "price", "basis": "exact", "count": len(rows), "top": rows[:TOP]}
    return out


def refresh():
    try:
        old = json.loads(OUT.read_text(encoding="utf-8")).get("indices", {})
    except (OSError, ValueError):
        old = {}
    new, errors = {}, []
    for name, fn in (("funds", from_funds), ("UK", from_lse), ("Nasdaq", from_capped), ("prices", from_prices)):
        try:
            got = fn()
            new.update(got)
            print(f"{name}: {len(got)} indices", flush=True)
        except Exception as e:  # noqa: BLE001 - one source failing keeps the others, and that source's last good copy
            errors.append(f"{name}: {e}")
            print(f"{name} failed: {e}", flush=True)
    today = datetime.now(timezone.utc).date().isoformat()
    for v in new.values():
        v["asOf"] = today
        v["topShare"] = sum(r["w"] for r in v["top"])
        for r in v["top"]:
            r["w"] = round(r["w"], 5)
            r.pop("cap", None)
            r.pop("price", None)
    indices = {**old, **new}
    OUT.write_text(json.dumps({"generated": time.time(), "indices": indices, "errors": errors}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"saved {len(new)} fresh, {len(indices) - len(new)} kept from before; errors: {errors or 'none'}")
    return len(new)


def load():
    try:
        return json.loads(OUT.read_text(encoding="utf-8")).get("indices", {})
    except (OSError, ValueError):
        return {}


if __name__ == "__main__":
    sys.exit(0 if refresh() else 1)
