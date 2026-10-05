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
            ("EXH7.DE", "Retail", "discr"),
            ("EXV9.DE", "Travel & Leisure", "discr"),
            ("EXH3.DE", "Food & Beverage", "staples"),
            ("EXH6.DE", "Personal & Household Goods", "staples"),
            ("EXH9.DE", "Utilities", "util"),
            ("EXV6.DE", "Basic Resources", "mat"),
            ("EXV7.DE", "Chemicals", "mat"),
            ("EXI5.DE", "Real Estate", "re"),
            ("EXV2.DE", "Telecommunications", "comm"),
            ("EXH8.DE", "Media", "comm"),
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
    ("HG=F", "Copper ($ a kilogram)"),
    ("BTC-USD", "Bitcoin ($)"),
]
