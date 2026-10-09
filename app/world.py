"""World Compass data: national stock markets, scored the way a global (US-dollar) investor experiences them.

Each country has a headline index (tracked in local currency) and a US-listed
country fund (total return in US dollars). The score, relative strength vs the
world and the backtest use the fund, so every market is measured on the same
basis: dividends included, currency moves included, against MSCI ACWI. Where
Yahoo has no index history, the fund converted back to local currency stands in.
"""
import time

import engine
import funddata
import tracking

WORLD, WORLD_NAME = "ACWI", "MSCI ACWI"

# code, name, region, index symbol (None = use the fund), index name, fund, currency, ISO numeric, [lon, lat], traits
# Traits describe what the stock market is exposed to, and drive the backdrop read below.
COUNTRIES = [
    ("US", "United States", "Americas", "^GSPC", "S&P 500", "SPY", "USD", "840", [-98, 39], ["tech", "haven"]),
    ("CA", "Canada", "Americas", "^GSPTSE", "S&P/TSX Composite", "EWC", "CAD", "124", [-100, 57], ["oil", "metals"]),
    ("MX", "Mexico", "Americas", "^MXX", "S&P/BMV IPC", "EWW", "MXN", "484", [-102, 23], ["em"]),
    ("BR", "Brazil", "Americas", "^BVSP", "Ibovespa", "EWZ", "BRL", "076", [-52, -10], ["em", "oil", "metals"]),
    ("AR", "Argentina", "Americas", "^MERV", "S&P Merval", "ARGT", "ARS", "032", [-64, -34], ["em", "fragile"]),
    ("CL", "Chile", "Americas", None, "MSCI Chile (via ECH)", "ECH", "CLP", "152", [-71, -33], ["em", "metals"]),
    ("GB", "United Kingdom", "Europe", "^FTSE", "FTSE 100", "EWU", "GBP", "826", [-2, 54], ["oil", "metals"]),
    ("DE", "Germany", "Europe", "^GDAXI", "DAX", "EWG", "EUR", "276", [10, 51], ["oil_user"]),
    ("FR", "France", "Europe", "^FCHI", "CAC 40", "EWQ", "EUR", "250", [2, 47], []),
    ("NL", "Netherlands", "Europe", "^AEX", "AEX", "EWN", "EUR", "528", [5, 52], ["tech"]),
    ("ES", "Spain", "Europe", "^IBEX", "IBEX 35", "EWP", "EUR", "724", [-4, 40], []),
    ("IT", "Italy", "Europe", "FTSEMIB.MI", "FTSE MIB", "EWI", "EUR", "380", [12, 43], []),
    ("CH", "Switzerland", "Europe", "^SSMI", "SMI", "EWL", "CHF", "756", [8, 47], ["haven"]),
    ("SE", "Sweden", "Europe", "^OMX", "OMX Stockholm 30", "EWD", "SEK", "752", [16, 62], []),
    ("NO", "Norway", "Europe", "OSEBX.OL", "Oslo Børs Benchmark", "NORW", "NOK", "578", [9, 61], ["oil"]),
    ("DK", "Denmark", "Europe", "^OMXC25", "OMX Copenhagen 25", "EDEN", "DKK", "208", [10, 56], []),
    ("BE", "Belgium", "Europe", "^BFX", "BEL 20", "EWK", "EUR", "056", [4.5, 50.6], []),
    ("PL", "Poland", "Europe", None, "MSCI Poland (via EPOL)", "EPOL", "PLN", "616", [19, 52], ["em"]),
    ("TR", "Turkey", "Europe", "XU100.IS", "BIST 100", "TUR", "TRY", "792", [35, 39], ["em", "fragile", "oil_user"]),
    ("JP", "Japan", "Asia-Pacific", "^N225", "Nikkei 225", "EWJ", "JPY", "392", [138, 37], ["oil_user"]),
    ("CN", "China", "Asia-Pacific", "000001.SS", "Shanghai Composite", "MCHI", "CNY", "156", [104, 35], ["em", "oil_user"]),
    ("HK", "Hong Kong", "Asia-Pacific", "^HSI", "Hang Seng", "EWH", "HKD", "344", [114.2, 22.3], []),
    ("IN", "India", "Asia-Pacific", "^NSEI", "Nifty 50", "INDA", "INR", "356", [79, 22], ["em", "oil_user"]),
    ("KR", "South Korea", "Asia-Pacific", "^KS11", "KOSPI", "EWY", "KRW", "410", [128, 36], ["em", "tech", "oil_user"]),
    ("TW", "Taiwan", "Asia-Pacific", "^TWII", "TAIEX", "EWT", "TWD", "158", [121, 23.7], ["em", "tech"]),
    ("AU", "Australia", "Asia-Pacific", "^AXJO", "S&P/ASX 200", "EWA", "AUD", "036", [134, -25], ["metals"]),
    ("NZ", "New Zealand", "Asia-Pacific", "^NZ50", "S&P/NZX 50", "ENZL", "NZD", "554", [172, -41], []),
    ("SG", "Singapore", "Asia-Pacific", "^STI", "Straits Times", "EWS", "SGD", "702", [103.8, 1.35], []),
    ("ID", "Indonesia", "Asia-Pacific", "^JKSE", "Jakarta Composite", "EIDO", "IDR", "360", [118, -2], ["em", "metals"]),
    ("MY", "Malaysia", "Asia-Pacific", "^KLSE", "FTSE Bursa Malaysia KLCI", "EWM", "MYR", "458", [102, 4], ["em", "oil"]),
    ("TH", "Thailand", "Asia-Pacific", None, "MSCI Thailand (via THD)", "THD", "THB", "764", [101, 15], ["em", "oil_user"]),
    ("PH", "Philippines", "Asia-Pacific", None, "MSCI Philippines (via EPHE)", "EPHE", "PHP", "608", [122, 12], ["em", "oil_user"]),
    ("VN", "Vietnam", "Asia-Pacific", None, "Vietnam equities (via VNM)", "VNM", "VND", "704", [106, 16], ["em"]),
    ("IL", "Israel", "Middle East & Africa", "^TA125.TA", "TA-125", "EIS", "ILS", "376", [35, 31.5], ["tech"]),
    ("SA", "Saudi Arabia", "Middle East & Africa", None, "MSCI Saudi Arabia (via KSA)", "KSA", "SAR", "682", [45, 24], ["em", "oil"]),
    ("ZA", "South Africa", "Middle East & Africa", "^J203.JO", "FTSE/JSE All Share", "EZA", "ZAR", "710", [24, -29], ["em", "metals", "fragile"]),
]
DEVELOPED = {"US", "CA", "GB", "DE", "FR", "NL", "ES", "IT", "CH", "SE", "NO", "DK", "BE", "JP", "HK", "AU", "NZ", "SG", "IL"}

# Where each country can be bought on IBKR by a UK retail investor: the US-listed funds scored here are blocked
# (no UK key information document), so this is a UCITS fund for the same country. "same" = the same MSCI index as
# the scored fund; "similar" = a close one (often the country's main local index, or without the cap on the biggest
# companies). Every ticker was found in IBKR's contract search on 7 Oct 2026. Countries not listed have no UCITS fund
# on IBKR. code: (IBKR ticker, exchange, fund name, match, what differs when "similar")
BUY_ON_IBKR = {
    "US": ("CSPX", "London", "iShares Core S&P 500 UCITS ETF", "same", ""),
    "CA": ("CSCA", "London", "iShares MSCI Canada UCITS ETF", "same", ""),
    "MX": ("XMEX", "London", "Xtrackers MSCI Mexico UCITS ETF", "similar", "large and mid-sized companies only, without the cap on the biggest"),
    "BR": ("IBZL", "London", "iShares MSCI Brazil UCITS ETF", "similar", "without the cap on the biggest companies"),
    "GB": ("ISF", "London", "iShares Core FTSE 100 UCITS ETF", "similar", "the FTSE 100 (the 100 biggest UK companies) rather than MSCI UK"),
    "DE": ("EXS1", "Xetra", "iShares Core DAX UCITS ETF (DE)", "similar", "the DAX, Germany's 40 biggest companies"),
    "FR": ("ISFR", "London", "iShares MSCI France UCITS ETF", "same", ""),
    "NL": ("IAEX", "Amsterdam", "iShares AEX UCITS ETF", "similar", "the AEX, the 25 biggest Dutch companies"),
    "ES": ("LYXIB", "Madrid", "Amundi IBEX 35 UCITS ETF", "similar", "the IBEX 35, Spain's 35 biggest companies"),
    "IT": ("IMIB", "London", "iShares FTSE MIB UCITS ETF", "similar", "the FTSE MIB, Italy's 40 biggest companies"),
    "CH": ("CSSMI", "Swiss exchange", "iShares SMI ETF (CH)", "similar", "the SMI, Switzerland's 20 biggest companies"),
    "SE": ("XACTOMXS3", "Stockholm", "XACT OMXS30 ESG UCITS ETF", "similar", "Stockholm's 30 most traded companies, with an ESG screen"),
    "NO": ("OBXD", "Oslo", "DNB OBX ETF", "similar", "the OBX, Oslo's 25 most traded companies"),
    "PL": ("IPOL", "London", "iShares MSCI Poland UCITS ETF", "similar", "large and mid-sized companies only"),
    "TR": ("ITKY", "London", "iShares MSCI Turkey UCITS ETF", "similar", "large and mid-sized companies only"),
    "JP": ("IJPN", "London", "iShares MSCI Japan UCITS ETF", "same", ""),
    "CN": ("ICHN", "Amsterdam", "iShares MSCI China UCITS ETF", "same", ""),
    "IN": ("NDIA", "London", "iShares MSCI India UCITS ETF", "same", ""),
    "KR": ("CSKR", "London", "iShares MSCI Korea UCITS ETF", "similar", "a different cap on the biggest companies (Samsung)"),
    "TW": ("ITWN", "London", "iShares MSCI Taiwan UCITS ETF", "similar", "a different cap on the biggest company (TSMC)"),
    "AU": ("SAUS", "London", "iShares MSCI Australia UCITS ETF", "same", ""),
    "SG": ("XBAS", "Xetra", "Xtrackers MSCI Singapore UCITS ETF", "similar", "without the cap on the biggest companies"),
    "ID": ("XMID", "London", "Xtrackers MSCI Indonesia Swap UCITS ETF", "similar", "large and mid-sized companies only, held through a swap"),
    "MY": ("XCS3", "London", "Xtrackers MSCI Malaysia UCITS ETF", "same", ""),
    "TH": ("XCS4", "London", "Xtrackers MSCI Thailand UCITS ETF", "similar", "large and mid-sized companies only"),
    "PH": ("XPQP", "Xetra", "Xtrackers MSCI Philippines UCITS ETF", "similar", "large and mid-sized companies only"),
    "VN": ("XFVT", "London", "Xtrackers FTSE Vietnam Swap UCITS ETF", "similar", "FTSE's Vietnam index, held through a swap"),
    "SA": ("IKSA", "London", "iShares MSCI Saudi Arabia Capped UCITS ETF", "similar", "large and mid-sized companies only, with a different cap"),
    "ZA": ("SRSA", "London", "iShares MSCI South Africa UCITS ETF", "similar", "without the cap on the biggest companies"),
}
# all world stocks, for the long-term core
WORLD_BUY = ("SSAC", "London", "iShares MSCI ACWI UCITS ETF", "same", "")


def buy_on_ibkr(code):
    t = BUY_ON_IBKR.get(code)
    return t and {"ticker": t[0], "exchange": t[1], "name": t[2], "match": t[3], "differs": t[4]}

TRAITS = {
    "em": "Emerging market", "oil": "Full of oil and gas companies", "oil_user": "Imports a lot of oil",
    "metals": "Full of mining companies", "tech": "Tech-heavy market", "haven": "Tends to hold up in sell-offs",
    "fragile": "Hurt by a strong dollar",
}

MACRO = [
    ("DX-Y.NYB", "US dollar vs major currencies"), ("^VIX", "Fear gauge (VIX)"), ("^TNX", "US 10-year interest rate"),
    ("CL=F", "Crude oil ($ a litre)"), ("HG=F", "Copper ($ a tonne)"), ("GC=F", "Gold ($ a gram)"),
]
EXTRA = ["^IRX", "SMH", "EEM"]  # rates for Sharpe; semis and EM to read tech and EM leadership


def backdrop_read(macro, world_m, smh_rel, eem_rel):
    """Which kinds of market today's global backdrop helps or hurts. Transparent rules, not a forecast."""
    rules = []

    def rule(name, active, note, tail=(), head=()):
        rules.append({"name": name, "active": active, "note": note, "tail": list(tail), "head": list(head)})

    g = lambda s, k: (macro.get(s) or {}).get(k)
    updown = lambda v: "up" if v >= 0 else "down"
    dxy = g("DX-Y.NYB", "r3m")
    if dxy is not None:
        if dxy >= 0.03:
            rule("Strong dollar", True, f"The US dollar has risen {dxy:.1%} against major currencies over 3 months. Gains made abroad shrink when converted back to dollars, and countries that borrowed in dollars find the debt harder to repay.", head=["em", "fragile"])
        elif dxy <= -0.03:
            rule("Weak dollar", True, f"The US dollar has fallen {abs(dxy):.1%} against major currencies over 3 months. Gains made abroad grow when converted back to dollars, and commodity prices usually firm.", tail=["em", "metals"])
        else:
            rule("Dollar", False, f"The US dollar is {updown(dxy)} {abs(dxy):.1%} against major currencies over 3 months: not enough to matter (the rule needs a 3% move).")
    oil = g("CL=F", "r3m")
    if oil is not None:
        if oil >= 0.10:
            rule("Oil rising", True, f"Oil is up {oil:.0%} over 3 months: a boost for oil-heavy markets, a cost for big oil importers.", tail=["oil"], head=["oil_user"])
        elif oil <= -0.10:
            rule("Oil falling", True, f"Oil is down {abs(oil):.0%} over 3 months: relief for big oil importers, a hit to oil-heavy markets.", tail=["oil_user"], head=["oil"])
        else:
            rule("Oil", False, f"Oil is {updown(oil)} {abs(oil):.0%} over 3 months: not enough to matter (the rule needs a 10% move).")
    cu = g("HG=F", "r3m")
    if cu is not None:
        if cu >= 0.08:
            rule("Metals rising", True, f"Copper, a gauge of demand for industrial metals, is up {cu:.0%} over 3 months: good for markets full of mining companies.", tail=["metals"])
        elif cu <= -0.08:
            rule("Metals falling", True, f"Copper, a gauge of demand for industrial metals, is down {abs(cu):.0%} over 3 months: bad for markets full of mining companies.", head=["metals"])
        else:
            rule("Metals", False, f"Copper, a gauge of demand for industrial metals, is {updown(cu)} {abs(cu):.0%} over 3 months: not enough to matter (the rule needs an 8% move).")
    vix, vs200 = g("^VIX", "price"), (world_m or {}).get("vs200")
    if vix is not None and vs200 is not None:
        trend = f"world stocks are {abs(vs200):.1%} {'above' if vs200 >= 0 else 'below'} their 200-day (about 10-month) average"
        if vix >= 25 or vs200 < 0:
            why = f"The fear gauge (VIX) is {'high' if vix >= 25 else 'at'} {vix:.1f}{' (over 25 = stressed)' if vix >= 25 else ''}, and {trend}."
            rule("Investors nervous", True, f"{why} Steadier markets then tend to hold up better, and emerging markets suffer most.", tail=["haven"], head=["em", "fragile"])
        elif vix <= 18 and vs200 > 0:
            rule("Investors confident", True, f"The fear gauge (VIX) is a calm {vix:.1f} (18 or less), and {trend}. Emerging markets usually benefit.", tail=["em"])
        else:
            rule("Investor mood", False, f"The fear gauge (VIX) is {vix:.1f}, and {trend}: a mixed picture, so no push either way.")
    if smh_rel is not None:
        if smh_rel >= 0.05:
            rule("Chip stocks leading", True, f"Chip-maker shares did {smh_rel:.1%} better than world stocks over 3 months: a boost for tech-heavy markets.", tail=["tech"])
        elif smh_rel <= -0.05:
            rule("Chip stocks falling behind", True, f"Chip-maker shares did {abs(smh_rel):.1%} worse than world stocks over 3 months: a drag on tech-heavy markets.", head=["tech"])
        else:
            rule("Chip stocks", False, f"Chip-maker shares did {abs(smh_rel):.1%} {'better' if smh_rel >= 0 else 'worse'} than world stocks over 3 months: not enough to matter (the rule needs 5%).")
    if eem_rel is not None:
        rule("Emerging vs world", False,
             f"Emerging markets as a group did {abs(eem_rel):.1%} {'better' if eem_rel >= 0 else 'worse'} than world stocks over 3 months. "
             "Shown for context only: each country's own score already captures this.")
    return rules


def _local_from_fund(fund, fx):
    """Rebuild a local-currency series from a US-dollar fund when Yahoo has no index history."""
    tr = engine.Track({"t": fund["t"], "c": fund["c"], "raw": fund["raw"], "off": fund.get("off", 0)}, fx)
    rate = tr.b  # local currency per US dollar, forward-filled onto the fund's days
    keep = [k for k, v in enumerate(rate) if v]
    return {"t": [fund["t"][k] for k in keep], "c": [fund["c"][k] * rate[k] for k in keep],
            "raw": [fund["raw"][k] * rate[k] for k in keep], "off": fund.get("off", 0),
            "price": fund["raw"][-1] * rate[-1] if rate[-1] else None}


def build():
    fx_sym = lambda ccy: f"{ccy}=X"
    symbols = ({WORLD} | {c[3] for c in COUNTRIES if c[3]} | {c[5] for c in COUNTRIES}
               | {fx_sym(c[6]) for c in COUNTRIES if c[6] != "USD"} | {m[0] for m in MACRO} | set(EXTRA))
    raw = engine.fetch_all(sorted(symbols))
    errors = sorted(s for s, d in raw.items() if not engine.usable(d))
    world = raw.get(WORLD)
    if not engine.usable(world):
        raise RuntimeError("world benchmark (ACWI) unavailable")
    rf_at = engine.rate_at(raw.get("^IRX"))
    now = max(d["t"][-1] for d in raw.values() if engine.usable(d))
    rf = rf_at(now)
    macro = engine.macro_block(raw, MACRO)
    world_tr = engine.Track(world)
    world_m = engine.analyse(world_tr, world, rf)
    gbp_rate = raw.get("GBP=X") if engine.usable(raw.get("GBP=X")) else None  # pounds per US dollar
    world_series = {"gbp": engine.convert(world, gbp_rate), "usd": world} if gbp_rate else None
    series = {}

    def rel3m(sym):
        d = raw.get(sym)
        if not engine.usable(d, 300):
            return None
        t = engine.Track(d, world)
        return t.rel(t.n - 1, 63)

    rows, tracks = [], []
    for code, name, region, idx_sym, idx_name, etf, ccy, iso, ll, traits in COUNTRIES:
        fund = raw.get(etf)
        if not engine.usable(fund, 300):
            continue
        fx = raw.get(fx_sym(ccy)) if ccy != "USD" else None
        fx = fx if engine.usable(fx) else None
        idx = raw.get(idx_sym) if idx_sym else None
        idx_ok = engine.usable(idx, 300)
        local_d = idx if idx_ok else (_local_from_fund(fund, fx) if fx else fund)
        tr = engine.Track(fund, world)
        m = engine.analyse(tr, fund, rf)
        ltr = engine.Track(local_d)
        lm = engine.analyse(ltr, local_d, rf)
        corr, beta = engine.corr_beta(tr)
        m.update(corr=corr, betaW=beta)
        cur = None
        if fx:
            ft = engine.Track(fx)
            i = ft.n - 1
            strength = lambda n: fx["c"][i - n] / fx["c"][i] - 1 if i >= n else None  # + = local currency gained vs USD
            cur = {"rate": fx["raw"][-1], "d1": strength(1), "w1": strength(5), "m1": strength(21), "m3": strength(63), "y1": strength(252),
                   "y3": strength(756), "spark": [round(1 / v, 8) for v in fx["c"][-253:]]}
        src = idx if idx_ok else fund
        fund_gbp = engine.convert(fund, gbp_rate) if gbp_rate else None
        if fund_gbp:
            series[code] = {"gbp": fund_gbp, "usd": fund}
        rows.append({
            "code": code, "symbol": code, "name": name, "region": region, "iso": iso, "ll": ll,
            "dm": code in DEVELOPED, "traits": traits, "buy": buy_on_ibkr(code),
            "index": {"symbol": idx_sym if idx_ok else None, "name": idx_name, "ccy": ccy, "proxy": not idx_ok},
            "etf": etf, "fund": fund["name"], "ccy": "USD",
            "m": m,
            "local": {k: lm.get(k) for k in ("price", "r1d", "r1w", "r1m", "r3m", "r6m", "ytd", "r1y", "r3y", "r5y",
                                              "rsi", "vs50", "vs200", "trend", "offHigh", "mdd", "vol",
                                              "series", "ma50", "ma200", "long")},
            "fx": cur,
            "gbp": engine.period_returns(engine.Track(fund_gbp)) if fund_gbp else None,
            "status": {"period": src.get("period"), "tz": src.get("tz"), "mtime": src.get("mtime")},
        })
        tracks.append(tr)

    hist_cuts = engine.apply_scores(rows, tracks, rf_at)
    t0 = time.time()
    bt = engine.backtest(tracks, rf_at)
    long_test = engine.long_hold_test(tracks, rf_at, [bool(r["buy"]) for r in rows])  # see longrun_test.py
    bt_seconds = round(time.time() - t0, 1)

    fund = funddata.load([r["etf"] for r in rows] + [WORLD])
    wf = (fund["funds"].get(WORLD) or {}).get("facts") or {}
    for r in rows:
        f = dict((fund["funds"].get(r["etf"]) or {}).get("facts") or {})
        f["aumUsd"] = f.get("aum")
        r["facts"] = f
        r["holdings"] = (fund["funds"].get(r["etf"]) or {}).get("holdings")
        r["m"]["pe"], r["m"]["yld"] = f.get("pe"), f.get("yld")
        r["m"]["peRel"] = f["pe"] / wf["pe"] - 1 if (f.get("pe") and wf.get("pe")) else None
    # Value score: cheaper P/E and higher dividend yield rank higher (percentile across countries)
    cheap = engine.pct_rank([-r["m"]["pe"] if r["m"].get("pe") else None for r in rows])
    yld = engine.pct_rank([r["m"].get("yld") for r in rows])
    for r, a, b in zip(rows, cheap, yld):
        parts = [(a, 0.6), (b, 0.4)]
        w = sum(wt for v, wt in parts if v is not None)
        r["m"]["value"] = round(sum(v * wt for v, wt in parts if v is not None) / w, 1) if w else None

    rules = backdrop_read(macro, world_m, rel3m("SMH"), rel3m("EEM"))
    for r in rows:
        tail = [x["name"] for x in rules if x["active"] and set(x["tail"]) & set(r["traits"])]
        head =[x["name"] for x in rules if x["active"] and set(x["head"]) & set(r["traits"])]
        r["m"]["tail"], r["m"]["head"], r["m"]["fit"] = tail, head, len(tail) - len(head)
    for sym in macro:
        macro[sym].pop("c", None)
    macro["SMH_REL"], macro["EEM_REL"] = rel3m("SMH"), rel3m("EEM")
    paper = tracking.paper_report("countries", series, {c: world_series for c in series}, world_series) if world_series else None
    changes = tracking.signal_log("countries", rows, "code")
    return {
        "generated": time.time(), "marketTime": max((d.get("mtime") or 0) for d in raw.values() if "error" not in d),
        "world": {"symbol": WORLD, "name": WORLD_NAME, "facts": wf,
                  "m": {k: world_m[k] for k in ("r1d", "r1w", "r1m", "r3m", "ytd", "r1y", "vs200", "trend")},
                  "gbp": engine.period_returns(engine.Track(world_series["gbp"])) if world_series else None,
                  "longRun": engine.long_run_record(world_series["gbp"]) if world_series else None,
                  "buy": dict(zip(("ticker", "exchange", "name", "match", "differs"), WORLD_BUY))},
        "rows": rows, "macro": macro, "rules": rules, "traits": TRAITS, "histCuts": hist_cuts,
        "weights": engine.WEIGHTS, "errors": errors, "holdingsAt": fund["fetched"],
        "backtest": bt, "backtestSeconds": bt_seconds, "longTest": long_test, "paper": paper, "changes": changes,
    }
