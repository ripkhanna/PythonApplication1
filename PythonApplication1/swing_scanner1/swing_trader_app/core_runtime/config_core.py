"""Extracted runtime section from app_runtime.py lines 419-757.
Loaded by app_runtime with exec(..., globals()) to preserve the original single-file behavior.
"""

# ─────────────────────────────────────────────────────────────────────────────
# TICKER UNIVERSE  — v4 curated high-quality list (always scanned)
# Sector stocks from live ETF holdings are ADDED on top of this baseline
# Neither list gates the other — every ticker is scanned for both long & short
# ─────────────────────────────────────────────────────────────────────────────
US_TICKERS = [
    # Semiconductors
    "NVDA","AMD","AVGO","ARM","MU","TSM","SMCI","ASML","KLAC","LRCX",
    "AMAT","TER","ON","MCHP","MPWR","MRVL","ADI","NXPI","LSCC",
    "WOLF","INTC","QCOM","ALAB","AMBA","CEVA",
    # Hardware / Cloud infra
    "DELL","HPE","PSTG","ANET","VRT","STX","WDC","NTAP",
    # Software / Cloud
    "PLTR","MDB","SNOW","DDOG","NET","CRWD","ZS","OKTA","PANW","WDAY",
    "TEAM","SHOP","TTD","U","PATH","CFLT","S","TENB","QLYS","GTLB","ESTC","SAIL","DT",
    # AI / Data
    "SOUN","BBAI","IREN","VSCO","GFAI","CXAI",
    # Crypto / Fintech
    "COIN","MSTR","MARA","RIOT","CLSK","WULF","HUT","BITF",
    "HOOD","PYPL","SOFI","AFRM","UPST","NU","MELI","BILL","TOST","FLYW","FUTU","TIGR",
    # China Tech
    "BABA","PDD","JD","SE","LI","XPEV","BIDU","TCOM","VIPS","HUYA",
    # Mega Cap
    "MA","V","AMZN","NFLX","META","GOOGL","MSFT","AAPL",
    # Consumer / Travel / Gaming
    "DASH","ABNB","BKNG","CVNA","APP","UBER","LYFT","RCL","CCL","NCLH",
    "RBLX","TTWO","EA","DKNG","PENN","MGAM","LVS","WYNN","MGM","W","OPEN",
    # EV / Auto
    "TSLA","RIVN","LCID","NIO","XPEV","F","GM","STLA","CHPT","BLNK","EVGO",
    # Defense / Space
    "PLTR","AXON","KTOS","RKLB","ASTS","LUNR","SPCE","LMT","NOC","RTX","BAC","GD",
    # Nuclear / Clean Energy
    "OKLO","SMR","NNE","CEG","ENPH","SEDG","FSLR","RUN","BE","PLUG","ARRY","FLNC","SHLS",
    # Energy / Materials
    "FCX","AA","NUE","LAC","ALB","MP","VALE","OXY","DVN","HAL","SLB",
    "GOLD","KGC","AG","PAAS","WPM","NEM",
    # Biotech
    "MRNA","BNTX","VRTX","REGN","GILD","AMGN","BIIB",
    "BEAM","CRSP","NTLA","EDIT","RXRX","PACB","ILMN","EXAS","TWST","SDGR","ALNY","BMRN",
    # Healthcare Tech / GLP-1
    "HIMS","LLY","NVO","VEEV","DOCS","DXCM","TDOC",
    # Quantum
    "IONQ","QUBT","RGTI","ARQQ","QBTS",
    # High-beta / Meme
    "NVTS","ACHR","JOBY","GME","AMC","BBWI","BIRD","CLOV","MVIS","CPSH","SKIN","XPOF","PRCT",
    # SE Asia (US-listed, high US-market correlation)
    "GRAB","SEA",
    "CEG","VST","GEV","BWXT","DNN","URG","NNE","SMR","URA","NLR","URNM","UUUU",
    "CCJ","UEC","PALAF","LEU","NNE","XE",
    #ETF
    "URA","NLR","URNM",
    # AI Infrastructure / Data Centers / Power
    "NBIS",   # Nebius — AI cloud infrastructure
    "CORZ",   # Core Scientific — AI/HPC + crypto mining
    "IREN",   # IREN — AI/HPC + bitcoin mining
    "APLD",   # Applied Digital — AI data centers
    "CRWV",   # CoreWeave — AI cloud, if available in your yfinance
    "ETN",    # Eaton — power equipment / data center electrification
    "PWR",    # Quanta Services — grid/data center power
    "EME",    # EMCOR — data center construction/services
    "FIX",    # Comfort Systems — HVAC/data center infrastructure
    "TT",     # Trane — cooling/data center infrastructure
    "CARR",   # Carrier — cooling/HVAC
    "JCI",    # Johnson Controls — building/cooling systems

    # Photonics / Optical / Networking
    "LITE",   # Lumentum — photonics/optical
    "COHR",   # Coherent — optical/lasers/AI networking
    "CIEN",   # Ciena — optical networking
    "FN",     # Fabrinet — optical manufacturing
    "GLW",    # Corning — optical fiber/data center
    "AAOI",   # Applied Optoelectronics — high-beta optical
    "POET",   # POET Technologies — photonics, very high risk
    "ACMR",   # ACM Research — semiconductor equipment

    # More Semiconductors / AI Hardware
    "GFS",    # GlobalFoundries
    "MTSI",   # MACOM — RF/semis
    "RMBS",   # Rambus — memory/interface chips
    "AEHR",   # Aehr Test Systems — semicap/high beta
    "FORM",   # FormFactor — semicap testing
    "CAMT",   # Camtek — semicap inspection
    "ACLS",   # Axcelis — ion implantation
    "SITM",   # SiTime — timing chips
    "POWI",   # Power Integrations
    "SYNA",   # Synaptics
    "CRUS",   # Cirrus Logic

    # Nuclear / Uranium / Power
    "CCJ",    # Cameco
    "UEC",    # Uranium Energy
    "UUUU",   # Energy Fuels
    "DNN",    # Denison Mines
    "URG",    # Ur-Energy
    "LEU",    # Centrus Energy
    "BWXT",   # BWX Technologies
    "CEG",    # Constellation Energy
    "VST",    # Vistra
    "GEV",    # GE Vernova
    "OKLO",   # Oklo — SMR/high risk
    "SMR",    # NuScale — SMR/high risk
    "NNE",    # Nano Nuclear — very high risk
    "LTBR",   # Lightbridge — nuclear fuel/high risk

    # Quantum Computing
    "IONQ",   # IonQ
    "QBTS",   # D-Wave Quantum
    "RGTI",   # Rigetti
    "QUBT",   # Quantum Computing Inc
    "ARQQ",   # Arqit Quantum
    "QMCO",   # Quantum Corp — very speculative
    "IBM",    # IBM — safer quantum exposure

    # Robotics / Automation / Drones
    "SYM",    # Symbotic
    "SERV",   # Serve Robotics
    "TER",    # Teradyne — automation/robotics
    "ROK",    # Rockwell Automation
    "IRBT",   # iRobot — speculative
    "ONDS",   # Ondas — drones/communications
    "AVAV",   # AeroVironment — drones/defense
    "KTOS",   # Kratos — defense drones
    "ACHR",   # Archer Aviation
    "JOBY",   # Joby Aviation
    "EVTL",   # Vertical Aerospace

    # Space / Defense / Aerospace
    "RKLB",   # Rocket Lab
    "ASTS",   # AST SpaceMobile
    "LUNR",   # Intuitive Machines
    "RDW",    # Redwire
    "SPIR",   # Spire Global
    "BKSY",   # BlackSky
    "ACHR",   # eVTOL/space-adjacent momentum
    "HWM",    # Howmet Aerospace
    "TDG",    # TransDigm
    "HEI",    # HEICO

    # Crypto / Bitcoin / Fintech Momentum
    "GLXY",   # Galaxy Digital
    "BTDR",   # Bitdeer
    "CIFR",   # Cipher Mining
    "HIVE",   # HIVE Digital
    "IREN",   # IREN
    "CORZ",   # Core Scientific
    "APLD",   # Applied Digital
    "WULF",   # TeraWulf
    "CLSK",   # CleanSpark
    "MARA",   # MARA
    "RIOT",   # Riot
    "HUT",    # Hut 8
    "BITF",   # Bitfarms
    "HIMS",   # Hims — consumer/health fintech-like momentum
    "TOST",   # Toast
    "FOUR",   # Shift4 Payments
    "MQ",     # Marqeta
    "DLO",    # DLocal
    "STNE",   # StoneCo
    "PAGS",   # PagSeguro
    "NU",     # Nu Holdings

    # Software / Cyber / Data / AI Apps
    "AI",     # C3.ai
    "SOUN",   # SoundHound AI
    "BBAI",   # BigBear.ai
    "AIOT",   # AI/IoT, validate liquidity
    "TEM",    # Tempus AI
    "VERI",   # Veritone — speculative AI
    "UPST",   # Upstart
    "BILL",   # Bill Holdings
    "DOCN",   # DigitalOcean
    "IOT",    # Samsara
    "HUBS",   # HubSpot
    "APPF",   # AppFolio
    "FROG",   # JFrog
    "NCNO",   # nCino
    "ASAN",   # Asana
    "TWLO",   # Twilio
    "ZI",     # ZoomInfo

    # Biotech / High Beta Healthcare
    "VKTX",   # Viking Therapeutics
    "ALT",    # Altimmune
    "TGTX",   # TG Therapeutics
    "SMMT",   # Summit Therapeutics
    "IOVA",   # Iovance
    "ACLX",   # Arcellx
    "VIR",    # Vir Biotechnology
    "DNA",    # Ginkgo Bioworks
    "SANA",   # Sana Biotechnology
    "VERV",   # Verve Therapeutics
    "PRME",   # Prime Medicine
    "ARVN",   # Arvinas
    "RXRX",   # Recursion
    "SDGR",   # Schrödinger

    # Consumer / Retail / Turnaround / High Beta
    "CAVA",   # Cava
    "SG",     # Sweetgreen
    "BROS",   # Dutch Bros
    "SHAK",   # Shake Shack
    "WING",   # Wingstop
    "ELF",    # e.l.f. Beauty
    "CELH",   # Celsius
    "ONON",   # On Holding
    "CROX",   # Crocs
    "CHWY",   # Chewy
    "ETSY",   # Etsy
    "ROKU",   # Roku
    "PINS",   # Pinterest
    "SNAP",   # Snap
    "RDDT",   # Reddit
    "DJT",    # Trump Media — very speculative

    # Industrials / Materials / Cyclicals
    "X",      # US Steel
    "CLF",    # Cleveland-Cliffs
    "STLD",   # Steel Dynamics
    "SCCO",   # Southern Copper
    "TECK",   # Teck Resources
    "LTHM",   # Arcadium/Lithium exposure, validate ticker
    "ALTM",   # Arcadium Lithium, validate current ticker
    "PLL",    # Piedmont Lithium
    "SGML",   # Sigma Lithium
    "ALB",    # Albemarle
    "LAC",    # Lithium Americas

    # High-beta ETFs / Theme ETFs
    "TQQQ",   # 3x Nasdaq
    "SOXL",   # 3x Semiconductors
    "TECL",   # 3x Technology
    "LABU",   # 3x Biotech
    "TNA",    # 3x Russell 2000
    "ARKK",   # ARK Innovation
    "ARKG",   # Genomics
    "ARKW",   # Internet
    "ARKQ",   # Autonomous/robotics
    "BOTZ",   # Robotics/AI
    "ROBO",   # Robotics
    "AIQ",    # AI ETF
    "QTUM",   # Quantum/next-gen computing ETF
    "BLOK",   # Blockchain ETF
    "BITO",   # Bitcoin futures ETF
    "IBIT",   # Spot Bitcoin ETF
    "FBTC",   # Spot Bitcoin ETF
]

SG_TICKERS = [
    # Blue chips / STI 30
    "D05.SI",   # DBS Group
    "O39.SI",   # OCBC Bank
    "U11.SI",   # UOB
    "Z74.SI",   # Singtel
    "S68.SI",   # Singapore Exchange
    "BN4.SI",   # Keppel Corp
    "BS6.SI",   # Yangzijiang Shipbuilding — high beta
    "S58.SI",   # SATS
    "C6L.SI",   # Singapore Airlines
    "U96.SI",   # Sembcorp Industries
    "F34.SI",   # Wilmar International
    "V03.SI",   # Venture Corporation
    "C52.SI",   # ComfortDelGro
    "H78.SI",   # Hongkong Land
    "U14.SI",   # UOL Group
    "S51.SI",   # Seatrium — high beta offshore
    # REITs
    "C38U.SI",  # CapitaLand CICT
    "A17U.SI",  # CapitaLand Ascendas REIT
    "M44U.SI",  # Mapletree Logistics Trust
    "N2IU.SI",  # Mapletree Pan Asia Commercial
    # Growth / Higher beta
    "AIY.SI",   # iFAST — fintech
    "558.SI",   # UMS Holdings — semicon equipment
    "OYY.SI",   # PropNex
    "MZH.SI",   # Nanofilm Technologies
    "8AZ.SI",   # Aztech Global — volatile
    "40B.SI",   # HRnetGroup
    "1D0.SI",   # Nanofilm spin-off
    "E28.SI",   # Frencken
    "AWX.SI",   # AEM
    "I07.SI",   # ISDN
    "5EB.SI",   # Micro-Mechanics
    "C31.SI",   # CapitaLand Investment
    "AJBU.SI",  # Keppel DC REIT
    "ME8U.SI",  # Mapletree Industrial Trust
    "9CI.SI",   # CapitaLand India Trust
    "5WH.SI",   # Rex International
    "41B.SI",   # Dyna-Mac
    "5LY.SI",   # Marco Polo Marine
    "NO4.SI",   # Geo Energy
]

# Cloud-safe SGX fallback universe. The SGX public endpoint and Yahoo SGX
# metadata often fail or return partial data on Streamlit Cloud, so keep a
# broader liquid-ish fallback list instead of scanning only 40-55 names.
SGX_LIQUID_FALLBACK_TICKERS = [
    "D01.SI","D05.SI","O39.SI","U11.SI","Z74.SI","S68.SI","BN4.SI","BS6.SI",
    "S58.SI","C6L.SI","U96.SI","F34.SI","V03.SI","C52.SI","H78.SI","U14.SI",
    "S51.SI","C31.SI","Y92.SI","G13.SI","C07.SI","A17U.SI","C38U.SI","M44U.SI",
    "N2IU.SI","ME8U.SI","AJBU.SI","J69U.SI","J91U.SI","K71U.SI","T82U.SI",
    "BUOU.SI","BTOU.SI","SK6U.SI","P9D.SI","C2PU.SI","HMN.SI","CLR.SI",
    "SRT.SI","ES3.SI","G3B.SI","AIY.SI","558.SI","E28.SI","AWX.SI","I07.SI",
    "5EB.SI","MZH.SI","8AZ.SI","40B.SI","OYY.SI","Q0F.SI","AEM.SI","BVA.SI",
    "5WH.SI","41B.SI","5LY.SI","NO4.SI","RE4.SI","E6R.SI","T14.SI","S63.SI",
    "C09.SI","S08.SI","B58.SI","C6L.SI","C52.SI","M01.SI","OV8.SI","H02.SI",
    "D03.SI","U06.SI","Y03.SI","B61.SI","M04.SI","F99.SI","N01.SI","S59.SI",
    "G92.SI","B7K.SI","1D0.SI","5JS.SI","5AB.SI","BN2.SI","TQ5.SI","P40U.SI",
]
SG_TICKERS = list(dict.fromkeys(SG_TICKERS + SGX_LIQUID_FALLBACK_TICKERS))


HK_TICKERS = [
    # Hong Kong expanded liquid / volatile / high-beta universe for yfinance.
    # Includes the original 30-stock core plus HSI, HS Tech, EV, broker,
    # casino, property, biotech, semiconductor, and active China beta names.
    "0700.HK","9988.HK","3690.HK","1810.HK","1024.HK","9618.HK",
    "9888.HK","9999.HK","2015.HK","9868.HK","1211.HK","0981.HK",
    "2382.HK","2018.HK","6618.HK","1347.HK","0241.HK","9961.HK",
    "3888.HK","6690.HK","0772.HK","6611.HK","6060.HK","9992.HK",
    "2318.HK","0388.HK","2331.HK","2333.HK","0175.HK","1929.HK",

    # Hang Seng / blue-chip / liquid China beta
    "0001.HK","0002.HK","0003.HK","0005.HK","0006.HK","0011.HK",
    "0012.HK","0016.HK","0017.HK","0027.HK","0066.HK","0101.HK",
    "0267.HK","0291.HK","0316.HK","0322.HK","0386.HK","0669.HK",
    "0688.HK","0728.HK","0762.HK","0788.HK","0823.HK","0836.HK",
    "0857.HK","0868.HK","0881.HK","0883.HK","0939.HK","0960.HK",
    "0968.HK","0992.HK","1038.HK","1044.HK","1088.HK","1093.HK",
    "1109.HK","1113.HK","1177.HK","1209.HK","1299.HK","1378.HK",
    "1398.HK","1800.HK","1876.HK","1919.HK","1928.HK","1997.HK",
    "2020.HK","2313.HK","2319.HK","2388.HK","2628.HK","2688.HK",
    "2888.HK","2899.HK","3968.HK","3988.HK","9633.HK",

    # Higher-beta tech, EV, semiconductor, software, healthcare/biotech
    "0268.HK","0285.HK","0522.HK","0986.HK","1478.HK","1801.HK",
    "1833.HK","1877.HK","2013.HK","2238.HK","2268.HK","2269.HK",
    "2359.HK","3800.HK","3808.HK","6160.HK","6699.HK","6862.HK",
    "6969.HK","9863.HK","9866.HK","9896.HK","9926.HK","9969.HK",

    # Brokers / financial beta / Macau / property beta watchlist
    "0606.HK","0607.HK","0683.HK","0880.HK","1128.HK","1336.HK",
    "1339.HK","1658.HK","1776.HK","1918.HK","2007.HK","2282.HK",
    "2600.HK","3323.HK","3900.HK","6030.HK","6066.HK","6098.HK",
    "6178.HK","6666.HK","6881.HK","6886.HK","9600.HK","9869.HK",
]


INDIA_TICKERS = [
    # Nifty 50 Blue Chips
    "RELIANCE.NS","TCS.NS","INFY.NS","HDFCBANK.NS","ICICIBANK.NS",
    "SBIN.NS","AXISBANK.NS","WIPRO.NS","BAJFINANCE.NS","MARUTI.NS",
    "HCLTECH.NS","TECHM.NS","LTIM.NS","SUNPHARMA.NS","DRREDDY.NS",
    "CIPLA.NS","TATAMOTORS.NS","TATASTEEL.NS",
    # Adani Group (high beta)
    "ADANIENT.NS","ADANIPORTS.NS","ADANIGREEN.NS","ADANIPOWER.NS",
    # Metals
    "VEDL.NS","HINDALCO.NS","JSWSTEEL.NS","NMDC.NS","HINDZINC.NS","COALINDIA.NS",
    # New-age Tech / Fintech
    "ZOMATO.NS","PAYTM.NS","NYKAA.NS","DELHIVERY.NS","POLICYBZR.NS",
    # Defence / PSU
    "HAL.NS","BEL.NS","COCHINSHIP.NS","RVNL.NS","IRFC.NS","HUDCO.NS","NBCC.NS",
    # Renewable Energy
    "TATAPOWER.NS","SUZLON.NS","INOXWIND.NS",
    # Banking / Finance
    "INDUSINDBK.NS","KOTAKBANK.NS","PNB.NS","BANKBARODA.NS","HDFCAMC.NS",
    # Mid/Small-cap high beta
    "IRCTC.NS","BSESMD.NS","DIXON.NS","AMBER.NS","KAYNES.NS","GRAVITA.NS","PGEL.NS",
]

# Keep BASE_TICKERS as combined list for backward compatibility
BASE_TICKERS = US_TICKERS + SG_TICKERS + INDIA_TICKERS + HK_TICKERS

# ─────────────────────────────────────────────────────────────────────────────
# SECTOR ETF MAP
# ─────────────────────────────────────────────────────────────────────────────
SECTOR_ETFS = {
    "Technology":        "XLK",
    "Semiconductors":    "SOXX",
    "Communication":     "XLC",
    "Consumer Discret":  "XLY",
    "Financials":        "XLF",
    "Healthcare":        "XLV",
    "Energy":            "XLE",
    "Industrials":       "XLI",
    "Materials":         "XLB",
    "Clean Energy":      "ICLN",
    "Biotech":           "XBI",
    "Crypto/Blockchain": "BITO",
    "China Tech":        "KWEB",
    "EV / Autos":        "DRIV",
    "Cloud / SaaS":      "WCLD",
}

# ── India NSE sector indices ──────────────────────────────────────────────────
INDIA_SECTOR_ETFS = {
    "Nifty 50":       "^NSEI",
    "Banking":        "^NSEBANK",
    "IT":             "^CNXIT",
    "Pharma":         "^CNXPHARMA",
    "Auto":           "^CNXAUTO",
    "FMCG":           "^CNXFMCG",
    "PSU Bank":       "^CNXPSUBANK",
    "Energy":         "^CNXENERGY",
    "Metal":          "^CNXMETAL",
    "Realty":         "^CNXREALTY",
    "Infrastructure": "^CNXINFRA",
    "Financial Svc":  "^CNXFINSERVICE",
    "Midcap":         "^CNXMIDCAP",
    "Smallcap":       "^CNXSMALLCAP",
}

# ── SGX sector groups (avg of stocks — no liquid sector ETFs on SGX) ──────────
SG_SECTOR_GROUPS = {
    "Banks":       ["D05.SI","O39.SI","U11.SI"],
    "REITs":       ["C38U.SI","A17U.SI","M44U.SI","N2IU.SI"],
    "Industrials": ["BN4.SI","S58.SI","V03.SI"],
    "Telecoms":    ["Z74.SI"],
    "Transport":   ["C6L.SI","C52.SI"],
    "Property":    ["U14.SI","H78.SI"],
    "Energy":      ["U96.SI"],
    "Shipping":    ["BS6.SI","S51.SI"],
    "Finance":     ["S68.SI","AIY.SI"],
    "Tech":        ["558.SI","8AZ.SI","MZH.SI","1D0.SI"],
}

# ─────────────────────────────────────────────────────────────────────────────
# SIGNAL WEIGHTS  — v5 exact values
# ─────────────────────────────────────────────────────────────────────────────
LONG_WEIGHTS = {
    # ── Tier 1: High accuracy (>0.68) — volume + momentum confirmation ────────
    "vol_surge_up":    0.76,   # green candle + 2x vol + 1.5% up — #1 predictor
    "vol_breakout":    0.73,   # price at 10d high + vol ≥1.8× — breakout confirmed
    "pocket_pivot":    0.71,   # above MA20, vol surge on up day
    "stoch_confirmed": 0.71,   # oversold bounce — works in uptrends
    "bb_bull_squeeze": 0.69,   # compression before expansion
    "rs_momentum":     0.70,   # RS line trending up vs SPY (20d)
    "rel_strength":    0.69,   # stock beat SPY last 5 days
    "weekly_trend":    0.72,   # MA20 > MA60 OR breakout above MA20 on volume
    # ── Tier 2: Good context signals (0.63–0.68) ──────────────────────────────
    "full_ma_stack":   0.68,   # NEW — price > EMA8 > EMA21 > MA20 > MA60
    "momentum_3d":     0.67,   # NEW — up 3 of last 5 days (continuation)
    "macd_accel":      0.67,   # histogram rising 3 bars — momentum building
    "obv_rising":      0.66,   # OBV rising 5 days — institutional accumulation
    "near_52w_high":   0.65,   # within 10% of 52W high — momentum continuation
    "golden_cross":    0.65,   # EMA50 > EMA200 — macro trend aligned
    "sector_leader":   0.65,   # outperforming sector ETF
    "strong_close":    0.65,   # closes in top 25% of range — buyers in control
    "operator_accumulation": 0.69, # smart-money accumulation: volume + strong close + OBV/VWAP
    "vwap_support":    0.64,   # price holding above VWAP = controlled buyer support
    "higher_lows":     0.63,   # uptrend structure
    "trend_daily":     0.63,   # price > EMA8 > EMA21
    "vcp_tightness":   0.63,   # ATR contracting — coiling before move
    # ── Tier 3: Weak / noisy (0.55–0.62) — low weight, rarely decisive ────────
    "rsi_confirmed":   0.60,   # reduced — lagging for swing
    "macd_cross":      0.58,   # reduced — too late for 1-2 week holds
    "volume":          0.68,   # raised — pure vol surge is predictive
    "adx":             0.57,   # reduced — direction agnostic
    "bull_candle":     0.59,   # reduced — single candle unreliable alone
    "atr_expansion":   0.60,   # reduced
    # ── Removed from scoring (noise): rsi_divergence, consolidation ──────────
    # rsi_divergence: ~52% win rate, too early, causes premature entries
    # consolidation: fires in downtrends too, not predictive enough
    # ── v12: Options-derived signals (US tickers only, gated by sidebar) ─────
    # These come from compute_options_signals() — if options data is not
    # available (non-US ticker, illiquid chain, fetch failure), the keys
    # simply aren't present in long_sig and contribute nothing to the
    # Bayesian update. Weights are intentionally conservative pending a
    # walk-forward backtest of each flag's hit rate.
    "opt_unusual_call_flow":  0.70,   # near-money call vol > 3× OI — fresh positioning
    "opt_call_skew_bullish":  0.65,   # 10% OTM call IV ≥ 10% OTM put IV — call demand
    "opt_pc_volume_low":      0.62,   # put/call volume < 0.6 — call-biased session
    "opt_iv_cheap":           0.62,   # ATM IV < 0.85× realized vol — calm-bull regime
}
SHORT_WEIGHTS = {
    "stoch_overbought": 0.70, "bb_bear_squeeze": 0.68, "macd_decel":     0.66,
    "vol_breakdown":    0.65, "trend_bearish":   0.63, "lower_highs":    0.62,
    "macd_cross_bear":  0.60, "adx_bear":        0.57, "rsi_cross_bear": 0.59,
    "high_volume_down": 0.64,
    "operator_distribution": 0.67, # smart-money selling: high volume + weak close / failed breakout
    "below_vwap":       0.62, # price below VWAP confirms seller control
    # ── v12: Options-derived bearish signals (US tickers only) ────────────────
    "opt_unusual_put_flow":   0.68,   # near-money put vol > 3× OI — fresh hedging
    "opt_put_skew_bearish":   0.66,   # put IV >> call IV by ≥5 vol pts — fear bid
    "opt_term_inversion":     0.66,   # front-month IV > back-month IV — event/fear
    "opt_pc_volume_high":     0.64,   # put/call volume > 1.5 — defensive session
}
BASE_RATE = 0.50

# ─────────────────────────────────────────────────────────────────────────────
# v13.7: SIGNAL CORRELATION BUCKETS
# Bayesian probability assumes independent evidence. Many of our signals are
# heavily correlated — `trend_daily`, `weekly_trend`, `full_ma_stack`,
# `near_52w_high`, `golden_cross` all measure the same latent "uptrend"
# factor. When five correlated signals fire, the engine multiplies the odds
# ratio as if we had five independent witnesses, when really we have one
# witness shouting five times. This pegs probability at 95% on setups that
# historically win ~60%.
#
# Fix: group signals into categories. Within each bucket, sort by weight
# desc and shrink the k-th signal's contribution toward base rate by
# BUCKET_DECAY^k. So the strongest signal in a bucket counts in full, the
# next at half-strength, the third at quarter, etc. This preserves the
# Bayesian update math but stops correlated evidence from double-counting.
# ─────────────────────────────────────────────────────────────────────────────
SIGNAL_BUCKETS = {
    # ── Long buckets ──────────────────────────────────────────────────────────
    # Trend / structure of the prevailing direction
    "trend_daily":     "trend", "weekly_trend":   "trend",
    "full_ma_stack":   "trend", "golden_cross":   "trend",
    "near_52w_high":   "trend", "higher_lows":    "trend",
    # Momentum oscillators / acceleration
    "macd_accel":      "momentum", "macd_cross":      "momentum",
    "momentum_3d":     "momentum", "rsi_confirmed":   "momentum",
    "stoch_confirmed": "momentum", "atr_expansion":   "momentum",
    # Volume / accumulation footprints
    "volume":          "volume", "vol_surge_up":   "volume",
    "vol_breakout":    "volume", "pocket_pivot":   "volume",
    "obv_rising":      "volume", "operator_accumulation": "volume",
    # Volatility regime
    "bb_bull_squeeze": "volatility", "vcp_tightness": "volatility",
    # Intra-day / candle / VWAP structure
    "strong_close":    "structure", "vwap_support":  "structure",
    "bull_candle":     "structure",
    # Relative strength vs market / sector
    "rel_strength":    "relative", "rs_momentum":   "relative",
    "sector_leader":   "relative",
    # Forward-looking options layer
    "opt_unusual_call_flow": "options", "opt_call_skew_bullish": "options",
    "opt_pc_volume_low":     "options", "opt_iv_cheap":          "options",
    # Trend-strength regulator (single-signal bucket — never decayed)
    "adx":             "adx_long",

    # ── Short buckets (parallel categories) ───────────────────────────────────
    "trend_bearish":   "trend",    "lower_highs":    "trend",
    "macd_decel":      "momentum", "macd_cross_bear":"momentum",
    "rsi_cross_bear":  "momentum", "stoch_overbought":"momentum",
    "vol_breakdown":   "volume",   "high_volume_down":"volume",
    "operator_distribution": "volume",
    "bb_bear_squeeze": "volatility",
    "below_vwap":      "structure",
    "opt_unusual_put_flow":  "options", "opt_put_skew_bearish": "options",
    "opt_term_inversion":    "options", "opt_pc_volume_high":   "options",
    "adx_bear":        "adx_short",
}
BUCKET_DECAY = 0.5   # 1st in bucket: full · 2nd: half · 3rd: quarter · ...

# ─────────────────────────────────────────────────────────────────────────────
# FinanceDatabase
# ─────────────────────────────────────────────────────────────────────────────
try:
    import financedatabase as fd
    _fd_available = True
except ImportError:
    _fd_available = False

# ─────────────────────────────────────────────────────────────────────────────
# nsepython — optional dependency for NSE option chains (.NS tickers)
# Without this, India scans skip the options layer (same behaviour as SGX).
# Install: pip install nsepython
# ─────────────────────────────────────────────────────────────────────────────
try:
    from nsepython import nse_optionchain_scrapper as _nse_oc
    _nse_opt_available = True
except Exception:
    _nse_opt_available = False

# ─────────────────────────────────────────────────────────────────────────────
# Strategy Lab ML backends (optional)
# Install preferred backend: pip install lightgbm scikit-learn
# ─────────────────────────────────────────────────────────────────────────────
try:
    from lightgbm import LGBMClassifier
    _lgbm_available = True
except Exception:
    _lgbm_available = False

try:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score, accuracy_score, precision_score, brier_score_loss
    _sklearn_strategy_available = True
except Exception:
    _sklearn_strategy_available = False

# ─────────────────────────────────────────────────────────────────────────────
# streamlit-autorefresh — optional dependency for non-destructive auto-rerun
# Without this, the auto-refresh feature falls back to a manual "Rerun now"
# button. The previous implementation used window.parent.location.reload(),
# which destroyed the entire Streamlit session — including all sidebar
# widget values (market selector, refresh interval, every checkbox/slider).
# `st_autorefresh` triggers a server-side rerun without reloading the
# browser page, preserving session state perfectly.
# Install: pip install streamlit-autorefresh
# ─────────────────────────────────────────────────────────────────────────────
try:
    from streamlit_autorefresh import st_autorefresh
    _autorefresh_available = True
except Exception:
    _autorefresh_available = False

# ─────────────────────────────────────────────────────────────────────────────
