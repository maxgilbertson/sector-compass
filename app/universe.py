"""The Sectors page universe: every sector and theme fund, grouped by region.

Whole-country funds are deliberately not here: they live on the Countries page (world.py).

Each group is measured against its own local benchmark so relative strength is
apples-to-apples (same exchange, same currency, same trading calendar).
`key` maps a fund to a canonical GICS-style sector so regions can be compared.
`plain`/`short` name each benchmark in plain English for the pages ("the whole US market (S&P 500)").
"""

GROUPS = [
    {
        "id": "us", "plain": "the whole US market (S&P 500)", "short": "S&P 500", "name": "United States", "bench": "SPY", "bench_name": "S&P 500", "ccy": "USD",
        "funds": [
            ("XLK", "Technology", "tech"),
            ("XLF", "Financials", "fin"),
            ("XLV", "Health Care", "health"),
            ("XLE", "Energy", "energy"),
            ("XLI", "Industrials", "indu"),
            ("XLY", "Consumer Discretionary", "discr"),
            ("XLP", "Consumer Staples", "staples"),
            ("XLU", "Utilities", "util"),
            ("XLB", "Materials", "mat"),
            ("XLRE", "Real Estate", "re"),
            ("XLC", "Communication Services", "comm"),
        ],
    },
    {
        "id": "global", "plain": "all world stocks (MSCI ACWI)", "short": "world stocks", "name": "Global", "bench": "ACWI", "bench_name": "MSCI ACWI", "ccy": "USD",
        "funds": [
            ("IXN", "Technology", "tech"),
            ("IXG", "Financials", "fin"),
            ("IXJ", "Health Care", "health"),
            ("IXC", "Energy", "energy"),
            ("EXI", "Industrials", "indu"),
            ("RXI", "Consumer Discretionary", "discr"),
            ("KXI", "Consumer Staples", "staples"),
            ("JXI", "Utilities", "util"),
            ("MXI", "Materials", "mat"),
            ("REET", "Real Estate", "re"),
            ("IXP", "Communication Services", "comm"),
        ],
    },
    {
        "id": "europe", "plain": "the whole European market (STOXX Europe 600)", "short": "STOXX Europe 600", "name": "Europe", "bench": "EXSA.DE", "bench_name": "STOXX Europe 600", "ccy": "EUR",
        "funds": [
            ("EXV3.DE", "Technology", "tech"),
            ("EXV1.DE", "Banks", "fin"),
            ("EXH5.DE", "Insurance", "fin"),
            ("EXH2.DE", "Financial Services", "fin"),
            ("EXV4.DE", "Health Care", "health"),
            ("EXH1.DE", "Oil & Gas", "energy"),
            ("EXH4.DE", "Industrial Goods & Services", "indu"),
            ("EXV8.DE", "Construction & Materials", "indu"),
            ("EXV5.DE", "Automobiles & Parts", "discr"),
            ("EXH8.DE", "Retail", "discr"),
            ("EXV9.DE", "Travel & Leisure", "discr"),
            ("EXH3.DE", "Food & Beverage", "staples"),
            ("EXH7.DE", "Personal & Household Goods", "staples"),
            ("EXH9.DE", "Utilities", "util"),
            ("EXV6.DE", "Basic Resources", "mat"),
            ("EXV7.DE", "Chemicals", "mat"),
            ("EXI5.DE", "Real Estate", "re"),
            ("EXV2.DE", "Telecommunications", "comm"),
            ("EXH6.DE", "Media", "comm"),
        ],
    },
    {
        "id": "japan", "plain": "the whole Japanese market (TOPIX)", "short": "TOPIX", "name": "Japan", "bench": "1306.T", "bench_name": "TOPIX", "ccy": "JPY",
        "funds": [
            ("1626.T", "IT & Services", "tech"),
            ("1625.T", "Electric Appliances & Precision", "tech"),
            ("1631.T", "Banks", "fin"),
            ("1632.T", "Financials ex Banks", "fin"),
            ("1621.T", "Pharmaceuticals", "health"),
            ("1618.T", "Energy Resources", "energy"),
            ("1624.T", "Machinery", "indu"),
            ("1628.T", "Transportation & Logistics", "indu"),
            ("1629.T", "Trading Companies", "indu"),
            ("1619.T", "Construction & Materials", "indu"),
            ("1622.T", "Automobiles", "discr"),
            ("1630.T", "Retail Trade", "discr"),
            ("1617.T", "Foods", "staples"),
            ("1627.T", "Electric Power & Gas", "util"),
            ("1620.T", "Raw Materials & Chemicals", "mat"),
            ("1623.T", "Steel & Nonferrous", "mat"),
            ("1633.T", "Real Estate", "re"),
        ],
    },
    {
        "id": "canada", "plain": "Canada's 60 biggest companies (S&P/TSX 60)", "short": "TSX 60", "name": "Canada", "bench": "XIU.TO", "bench_name": "S&P/TSX 60", "ccy": "CAD",
        "funds": [
            ("XIT.TO", "Technology", "tech"),
            ("XFN.TO", "Financials", "fin"),
            ("XEG.TO", "Energy", "energy"),
            ("XMA.TO", "Materials", "mat"),
            ("XGD.TO", "Gold Miners", "mat"),
            ("XST.TO", "Consumer Staples", "staples"),
            ("XUT.TO", "Utilities", "util"),
            ("XRE.TO", "REITs", "re"),
        ],
    },
    {
        "id": "themes", "plain": "the whole US market (S&P 500)", "short": "S&P 500", "name": "Themes & Industries", "bench": "SPY", "bench_name": "S&P 500", "ccy": "USD",
        "funds": [
            ("SMH", "Semiconductors", "tech"),
            ("IGV", "Software", "tech"),
            ("CIBR", "Cybersecurity", "tech"),
            ("SKYY", "Cloud Computing", "tech"),
            ("BOTZ", "Robotics & AI", "tech"),
            ("KWEB", "China Internet", "comm"),
            ("XBI", "Biotech", "health"),
            ("IHI", "Medical Devices", "health"),
            ("KRE", "US Regional Banks", "fin"),
            ("ITA", "Aerospace & Defense", "indu"),
            ("PAVE", "US Infrastructure", "indu"),
            ("JETS", "Airlines", "indu"),
            ("ITB", "Homebuilders", "discr"),
            ("ICLN", "Clean Energy", "util"),
            ("TAN", "Solar", "util"),
            ("URA", "Uranium & Nuclear", "energy"),
            ("XOP", "Oil & Gas Exploration", "energy"),
            ("GDX", "Gold Miners", "mat"),
            ("COPX", "Copper Miners", "mat"),
            ("LIT", "Lithium & Batteries", "mat"),
        ],
    },
]

# Macro gauges used to read the business cycle.
MACRO = [
    ("^VIX", "Fear gauge (VIX)"),
    ("^TNX", "US 10-year interest rate"),
    ("^IRX", "US 3-month interest rate"),
    ("DX-Y.NYB", "US dollar vs major currencies"),
    ("CL=F", "Crude oil ($ a litre)"),
    ("GC=F", "Gold ($ a gram)"),
    ("HG=F", "Copper ($ a tonne)"),
    ("BTC-USD", "Bitcoin ($)"),
]

# Where each fund can be bought on IBKR by a UK retail investor. US, Japanese and Canadian funds have no UK
# key information document, so IBKR blocks them; many US ones have a UCITS "twin" listed in London that tracks
# the same index ("same") or a close one ("similar"). Every ticker below was found in IBKR's contract search on
# 7 Oct 2026. The European funds are UCITS themselves (Xetra). Funds not listed have no UCITS version on IBKR.
# fund symbol: (IBKR ticker, exchange, fund name, match, what differs when "similar")
BUY_ON_IBKR = {
    "XLK": ("SXLK", "London", "SPDR S&P US Technology Select Sector UCITS ETF", "same", ""),
    "XLF": ("SXLF", "London", "SPDR S&P US Financials Select Sector UCITS ETF", "same", ""),
    "XLV": ("SXLV", "London", "SPDR S&P US Health Care Select Sector UCITS ETF", "same", ""),
    "XLE": ("SXLE", "London", "SPDR S&P US Energy Select Sector UCITS ETF", "same", ""),
    "XLI": ("SXLI", "London", "SPDR S&P US Industrials Select Sector UCITS ETF", "same", ""),
    "XLY": ("SXLY", "London", "SPDR S&P US Consumer Discretionary Select Sector UCITS ETF", "same", ""),
    "XLP": ("SXLP", "London", "SPDR S&P US Consumer Staples Select Sector UCITS ETF", "same", ""),
    "XLU": ("SXLU", "London", "SPDR S&P US Utilities Select Sector UCITS ETF", "same", ""),
    "XLB": ("SXLB", "London", "SPDR S&P US Materials Select Sector UCITS ETF", "same", ""),
    "XLC": ("SXLC", "London", "SPDR S&P US Communication Services Select Sector UCITS ETF", "same", ""),
    "XLRE": ("IUSP", "London", "iShares US Property Yield UCITS ETF", "similar", "holds only US property companies that pay higher dividends"),
    "IXN": ("XDWT", "London", "Xtrackers MSCI World Information Technology UCITS ETF", "similar", "developed markets only (no Taiwan, so no TSMC)"),
    "IXG": ("XDWF", "London", "Xtrackers MSCI World Financials UCITS ETF", "similar", "developed markets only"),
    "IXJ": ("XDWH", "London", "Xtrackers MSCI World Health Care UCITS ETF", "similar", "developed markets only"),
    "IXC": ("XDW0", "London", "Xtrackers MSCI World Energy UCITS ETF", "similar", "developed markets only"),
    "EXI": ("XDWI", "London", "Xtrackers MSCI World Industrials UCITS ETF", "similar", "developed markets only"),
    "RXI": ("XDWC", "London", "Xtrackers MSCI World Consumer Discretionary UCITS ETF", "similar", "developed markets only"),
    "KXI": ("XDWS", "London", "Xtrackers MSCI World Consumer Staples UCITS ETF", "similar", "developed markets only"),
    "JXI": ("XDWU", "London", "Xtrackers MSCI World Utilities UCITS ETF", "similar", "developed markets only"),
    "MXI": ("XDWM", "London", "Xtrackers MSCI World Materials UCITS ETF", "similar", "developed markets only"),
    "IXP": ("XWTS", "London", "Xtrackers MSCI World Communication Services UCITS ETF", "similar", "developed markets only"),
    "REET": ("IWDP", "London", "iShares Developed Markets Property Yield UCITS ETF", "similar", "developed markets only, higher-dividend property companies"),
    "SMH": ("SMH", "London", "VanEck Semiconductor UCITS ETF", "same", ""),
    "CIBR": ("CIBR", "London", "First Trust Nasdaq Cybersecurity UCITS ETF", "same", ""),
    "SKYY": ("FSKY", "London", "First Trust Cloud Computing UCITS ETF", "same", ""),
    "BOTZ": ("BOTZ", "London", "Global X Robotics & Artificial Intelligence UCITS ETF", "same", ""),
    "KWEB": ("KWEB", "London", "KraneShares CSI China Internet UCITS ETF", "same", ""),
    "XBI": ("BTEC", "London", "iShares Nasdaq US Biotechnology UCITS ETF", "similar", "the biggest biotech companies count for more (the scored fund weights them equally)"),
    "ITA": ("DFNS", "London", "VanEck Defense UCITS ETF", "similar", "defence companies worldwide, not only US aerospace and defence"),
    "PAVE": ("PAVE", "London", "Global X US Infrastructure Development UCITS ETF", "same", ""),
    "ICLN": ("INRG", "London", "iShares Global Clean Energy Transition UCITS ETF", "same", ""),
    "TAN": ("RAYS", "London", "Invesco Solar Energy UCITS ETF", "same", ""),
    "URA": ("URNU", "London", "Global X Uranium UCITS ETF", "same", ""),
    "XOP": ("IOGP", "London", "iShares Oil & Gas Exploration & Production UCITS ETF", "similar", "oil and gas producers worldwide, not only US ones"),
    "GDX": ("GDX", "London", "VanEck Gold Miners UCITS ETF", "same", ""),
    "COPX": ("COPX", "London", "Global X Copper Miners UCITS ETF", "same", ""),
    "LIT": ("LITU", "London", "Global X Lithium & Battery Tech UCITS ETF", "same", ""),
    "XGD.TO": ("GDX", "London", "VanEck Gold Miners UCITS ETF", "similar", "gold miners worldwide, not only Canadian ones"),
}


def buy_on_ibkr(sym):
    """How to buy a fund on IBKR, or None. European funds (Xetra) are UCITS themselves."""
    if sym.endswith(".DE"):
        return {"ticker": sym[:-3], "exchange": "Xetra", "name": None, "match": "itself", "differs": ""}
    t = BUY_ON_IBKR.get(sym)
    return t and {"ticker": t[0], "exchange": t[1], "name": t[2], "match": t[3], "differs": t[4]}

# The long-term core: each region's whole market, bought as one low-cost UCITS fund on IBKR (checked 7 Oct 2026).
# group id: (IBKR ticker, exchange, fund name, match, what differs when "similar")
CORE = {
    "global": ("SSAC", "London", "iShares MSCI ACWI UCITS ETF", "same", ""),
    "us": ("CSPX", "London", "iShares Core S&P 500 UCITS ETF", "same", ""),
    "europe": ("EXSA", "Xetra", "iShares STOXX Europe 600 UCITS ETF (DE)", "itself", ""),
    "japan": ("IJPN", "London", "iShares MSCI Japan UCITS ETF", "similar", "MSCI Japan (about 180 large and mid-sized companies) rather than the whole TOPIX"),
    "canada": ("CSCA", "London", "iShares MSCI Canada UCITS ETF", "similar", "MSCI Canada (about 85 companies) rather than the 60 biggest"),
}


def core_buy(group):
    t = CORE.get(group)
    return t and {"ticker": t[0], "exchange": t[1], "name": t[2], "match": t[3], "differs": t[4]}
