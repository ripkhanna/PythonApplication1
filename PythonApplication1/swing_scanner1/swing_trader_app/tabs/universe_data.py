"""
universe_data.py
================
SINGLE SOURCE OF TRUTH for all ticker universes across every tab.

Design
------
* Each market has a BASE list  (existing curated/high-beta watchlist from config_core)
  PLUS an INDEX list            (actual S&P 500 / NASDAQ-100 / Nifty / HSI components).
* The merged result is deduplicated, order-preserved, and exposed via simple
  get_tickers() / get_universe() helpers.
* config_core.py imports US_TICKERS / SG_TICKERS / HK_TICKERS / INDIA_TICKERS
  from here — so the g-dict keys every tab already uses stay unchanged.
* app_runtime.py imports get_tickers_for_market() so _active_tickers is also
  driven from one place.

Adding new tickers
------------------
  US  → append to _US_BASE or _US_SP500 / _US_NDX100
  SGX → append to _SGX_BASE
  India → append to _INDIA_BASE
  HK  → append to _HK_BASE
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _dedup(lst: list[str]) -> list[str]:
    seen: set[str] = set()
    out:  list[str] = []
    for t in lst:
        t = str(t or "").strip().upper()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


# ═════════════════════════════════════════════════════════════════════════════
# US  ─  existing curated watchlist  +  S&P 500  +  NASDAQ-100
# ═════════════════════════════════════════════════════════════════════════════

# ---------- existing high-beta / sector-theme watchlist (from config_core) --
_US_BASE: list[str] = [
    # Semiconductors
    "NVDA","AMD","AVGO","ARM","MU","TSM","SMCI","ASML","KLAC","LRCX",
    "AMAT","TER","ON","MCHP","MPWR","MRVL","ADI","NXPI","LSCC",
    "WOLF","INTC","QCOM","ALAB","AMBA","CEVA","GFS","MTSI","RMBS",
    "AEHR","FORM","CAMT","ACLS","SITM","POWI","SYNA","CRUS",
    # Hardware / Cloud infra
    "DELL","HPE","PSTG","ANET","VRT","STX","WDC","NTAP",
    # Software / Cloud
    "PLTR","MDB","SNOW","DDOG","NET","CRWD","ZS","OKTA","PANW","WDAY",
    "TEAM","SHOP","TTD","U","PATH","CFLT","S","TENB","QLYS","GTLB",
    "ESTC","SAIL","DT","DOCN","IOT","HUBS","APPF","FROG","NCNO","ASAN",
    "TWLO","ZI","AI","VERI","UPST","BILL",
    # AI / Data
    "SOUN","BBAI","IREN","GFAI","CXAI","TEM","RXRX","SDGR",
    # Crypto / Bitcoin miners
    "COIN","MSTR","MARA","RIOT","CLSK","WULF","HUT","BITF",
    "GLXY","BTDR","CIFR","HIVE","CORZ","APLD","CRWV","NBIS",
    # Fintech
    "HOOD","PYPL","SOFI","AFRM","NU","MELI","BILL","TOST","FLYW",
    "FUTU","TIGR","FOUR","MQ","DLO","STNE","PAGS",
    # China Tech (US-listed)
    "BABA","PDD","JD","SE","LI","XPEV","BIDU","TCOM","VIPS","HUYA",
    # Mega Cap
    "MA","V","AMZN","NFLX","META","GOOGL","MSFT","AAPL",
    # Consumer / Travel / Gaming
    "DASH","ABNB","BKNG","CVNA","APP","UBER","LYFT","RCL","CCL","NCLH",
    "RBLX","TTWO","EA","DKNG","PENN","MGAM","LVS","WYNN","MGM","W","OPEN",
    "CAVA","SG","BROS","SHAK","WING","ELF","CELH","ONON","CROX","CHWY",
    "ETSY","ROKU","PINS","SNAP","RDDT","DJT",
    # EV / Auto
    "TSLA","RIVN","LCID","NIO","F","GM","STLA","CHPT","BLNK","EVGO",
    # Defense / Space
    "AXON","KTOS","RKLB","ASTS","LUNR","SPCE","LMT","NOC","RTX","GD",
    "RDW","SPIR","BKSY","HWM","TDG","HEI","AVAV","ACHR","JOBY","EVTL",
    # Nuclear / Clean Energy
    "OKLO","SMR","NNE","CEG","ENPH","SEDG","FSLR","RUN","BE","PLUG",
    "ARRY","FLNC","SHLS","CCJ","UEC","UUUU","DNN","URG","LEU","BWXT",
    "VST","GEV","LTBR",
    # Energy / Materials
    "FCX","AA","NUE","LAC","ALB","MP","VALE","OXY","DVN","HAL","SLB",
    "GOLD","KGC","AG","PAAS","WPM","NEM","X","CLF","STLD","SCCO","TECK",
    "PLL","SGML","LTHM",
    # Biotech / Healthcare
    "MRNA","BNTX","VRTX","REGN","GILD","AMGN","BIIB",
    "BEAM","CRSP","NTLA","EDIT","PACB","ILMN","EXAS","TWST","ALNY","BMRN",
    "HIMS","LLY","NVO","VEEV","DOCS","DXCM","TDOC",
    "VKTX","ALT","TGTX","SMMT","IOVA","ACLX","VIR","DNA","SANA","VERV",
    "PRME","ARVN",
    # Quantum
    "IONQ","QUBT","RGTI","ARQQ","QBTS","IBM",
    # Robotics / Automation / Drones
    "SYM","SERV","ROK","IRBT","ONDS",
    # Photonics / Optical
    "LITE","COHR","CIEN","FN","GLW","AAOI","POET","ACMR",
    # AI Data Centers / Power infra
    "ETN","PWR","EME","FIX","TT","CARR","JCI",
    # Industrials / Cyclicals
    "IRCTC",
    # High-beta ETFs
    "TQQQ","SOXL","TECL","LABU","TNA","ARKK","ARKG","ARKW","ARKQ",
    "BOTZ","ROBO","AIQ","QTUM","BLOK","BITO","IBIT","FBTC",
    "URA","NLR","URNM",
    # SE Asia
    "GRAB","SEA",
]

# ---------- S&P 500 constituents (mid-2025) ----------------------------------
_US_SP500: list[str] = [
    "MMM","AOS","ABT","ABBV","ACN","ADBE","AMD","AES","AFL","A","APD","ABNB",
    "AKAM","ALB","ARE","ALGN","ALLE","LNT","ALL","GOOGL","GOOG","MO","AMZN",
    "AMCR","AEE","AAL","AEP","AXP","AIG","AMT","AWK","AMP","AME","AMGN","APH",
    "ADI","ANSS","AON","APA","AAPL","AMAT","APTV","ACGL","ADM","ANET","AJG",
    "AIZ","T","ATO","ADSK","ADP","AVB","AVY","AXON","BKR","BALL","BAC","BAX",
    "BDX","BRK.B","BBY","TECH","BIIB","BLK","BX","BA","BCO","BSX","BMY","AVGO",
    "BR","BRO","BF.B","BLDR","BG","CDNS","CZR","CPT","CPB","COF","CAH","KMX",
    "CCL","CARR","CTLT","CAT","CBOE","CBRE","CDW","CE","COR","CNC","CNX","CDAY",
    "CF","CRL","SCHW","CHTR","CVX","CMG","CB","CHD","CI","CINF","CTAS","CSCO",
    "C","CFG","CLX","CME","CMS","KO","CTSH","CL","CMCSA","CMA","CAG","COP",
    "ED","STZ","CEG","COO","CPRT","GLW","CTVA","CSGP","COST","CTRA","CCI",
    "CSX","CMI","CVS","DHI","DHR","DRI","DVA","DAY","DECK","DE","DAL","DVN",
    "DXCM","FANG","DLR","DFS","DG","DLTR","D","DPZ","DOV","DOW","DTE","DUK",
    "DD","EMN","ETN","EBAY","ECL","EIX","EW","EA","ELV","LLY","EMR","ENPH",
    "ETR","EOG","EPAM","EQT","EFX","EQIX","EQR","ESS","EL","ETSY","EG","EVRG",
    "ES","EXC","EXPE","EXPD","EXR","XOM","FFIV","FDS","FICO","FAST","FRT","FDX",
    "FIS","FITB","FSLR","FE","FI","FMC","F","FTNT","FTV","FOXA","FOX","BEN",
    "FCX","GRMN","IT","GE","GEHC","GEN","GNRC","GD","GIS","GM","GPC","GILD",
    "GS","HAL","HIG","HAS","HCA","DOC","HSIC","HSY","HES","HPE","HLT","HOLX",
    "HD","HON","HRL","HST","HWM","HPQ","HUBB","HUM","HBAN","HII","IBM","IEX",
    "IDXX","ITW","ILMN","INCY","IR","PODD","INTC","ICE","IFF","IP","IPG","INTU",
    "ISRG","IVZ","INVH","IQV","IRM","JKHY","J","JNJ","JCI","JPM","JNPR","K",
    "KVUE","KDP","KEY","KEYS","KMB","KIM","KMI","KLAC","KHC","KR","LHX","LH",
    "LRCX","LW","LVS","LDOS","LEN","LIN","LYV","LKQ","LMT","L","LOW","LULU",
    "LYB","MTB","MRO","MPC","MKTX","MAR","MMC","MLM","MAS","MA","MTCH","MKC",
    "MCD","MCK","MDT","MRK","META","MET","MTD","MGM","MCHP","MU","MSFT","MAA",
    "MRNA","MHK","MOH","TAP","MDLZ","MPWR","MNST","MCO","MS","MOS","MSI","MSCI",
    "NDAQ","NTAP","NFLX","NEM","NWSA","NWS","NEE","NKE","NI","NDSN","NSC","NTRS",
    "NOC","NCLH","NRG","NUE","NVDA","NVR","NXPI","ORLY","OXY","ODFL","OMC",
    "ON","OKE","ORCL","OTIS","PCAR","PKG","PLTR","PANW","PARA","PH","PAYX",
    "PAYC","PYPL","PNR","PEP","PFE","PCG","PM","PSX","PNW","PNC","POOL","PPG",
    "PPL","PFG","PG","PGR","PRU","PLD","PTC","PSA","PHM","QRVO","PWR","QCOM",
    "DGX","RL","RJF","RTX","O","REG","REGN","RF","RSG","RMD","RVTY","ROK",
    "ROL","ROP","ROST","RCL","SPGI","CRM","SBAC","SLB","STX","SEE","SRE","NOW",
    "SHW","SPG","SWKS","SJM","SNA","SOLV","SO","LUV","SWK","SBUX","STT","STLD",
    "STE","SYK","SMCI","SYF","SNPS","SYY","TMUS","TROW","TTWO","TPR","TRGP",
    "TGT","TEL","TDY","TFX","TER","TSLA","TXN","TXT","TMO","TJX","TSCO","TT",
    "TDG","TRV","TRMB","TFC","TYL","TSN","USB","UBER","UDR","ULTA","UNP","UAL",
    "UPS","URI","UNH","UHS","VLO","VTR","VRSN","VRSK","VZ","VRTX","VLTO","V",
    "VST","VFC","VTRS","VICI","VNO","WAB","WBA","WMT","WBD","WDAY","WEC","WFC",
    "WELL","WST","WDC","WY","WHR","WMB","WTW","GWW","WYNN","XEL","XYL","YUM",
    "ZBRA","ZBH","ZTS",
]

# ---------- NASDAQ-100 (mid-2025) --------------------------------------------
_US_NDX100: list[str] = [
    "ADBE","AMD","ABNB","GOOGL","GOOG","AMZN","AEP","AMGN","ADI","ANSS","AAPL",
    "AMAT","ARM","ASML","AZN","TEAM","ADSK","ADP","AVGO","BIIB","BKNG","CDNS",
    "CDW","CHTR","CSGP","CSCO","CCEP","CTSH","CMCSA","CEG","CPRT","CTAS","CRWD",
    "CSX","DDOG","DXCM","FANG","DLTR","EA","EXC","FAST","GEHC","FTNT","GILD",
    "HON","IDXX","ILMN","INTC","INTU","ISRG","KDP","KLAC","KHC","LRCX","LIN",
    "LULU","MAR","MRVL","MELI","META","MCHP","MU","MSFT","MDLZ","MNST","NFLX",
    "NVDA","NXPI","ORLY","ODFL","ON","PAYX","PYPL","PANW","PEP","QCOM","ROST",
    "REGN","SBUX","SNPS","TTWO","TMUS","TSLA","TXN","VRSK","VRTX","WDAY","XEL",
    "ZS","MDB","OKTA","COIN","SHOP","PLTR","NET","SNOW","CRWD","DDOG","DOCU",
    "TTD","BILL","HOOD","SOFI","AFRM","UPST","RBLX","DASH","ZM","GTLB","MRNA",
]

# Merged US universe — base + S&P500 + NDX100, deduplicated
US_TICKERS: list[str] = _dedup(_US_BASE + _US_SP500 + _US_NDX100)


# ═════════════════════════════════════════════════════════════════════════════
# SGX  ─  existing curated  +  STI-30 / SGX Mainboard liquid
# ═════════════════════════════════════════════════════════════════════════════

_SGX_BASE: list[str] = [
    # STI 30 Blue Chips
    "D05.SI","O39.SI","U11.SI","Z74.SI","S68.SI","BN4.SI","BS6.SI","S58.SI",
    "C6L.SI","U96.SI","F34.SI","V03.SI","C52.SI","H78.SI","U14.SI","S51.SI",
    "C31.SI","Y92.SI","G13.SI","C07.SI","S63.SI","C09.SI","D01.SI","M01.SI",
    "S08.SI","C38U.SI","A17U.SI","J36.SI","D03.SI","U06.SI",
    # REITs
    "M44U.SI","N2IU.SI","ME8U.SI","AJBU.SI","J69U.SI","J91U.SI","K71U.SI",
    "T82U.SI","BUOU.SI","BTOU.SI","SK6U.SI","P9D.SI","C2PU.SI","9CI.SI",
    "CLR.SI","HMN.SI","SRT.SI","P40U.SI","ND8U.SI","RW0U.SI","ACV.SI",
    # Growth / Higher beta
    "AIY.SI","558.SI","OYY.SI","MZH.SI","8AZ.SI","40B.SI","1D0.SI","E28.SI",
    "AWX.SI","I07.SI","5EB.SI","5WH.SI","41B.SI","5LY.SI","NO4.SI",
    # SGX Liquid Fallback (from config_core SGX_LIQUID_FALLBACK_TICKERS)
    "Q0F.SI","AEM.SI","BVA.SI","RE4.SI","E6R.SI","T14.SI","OV8.SI","H02.SI",
    "Y03.SI","B61.SI","M04.SI","F99.SI","N01.SI","S59.SI","G92.SI","B7K.SI",
    "5JS.SI","5AB.SI","BN2.SI","TQ5.SI","S71.SI","G20.SI","Z25.SI","S41.SI",
    "1G1.SI","5WA.SI","531.SI","M15.SI","G41.SI","P8Z.SI","EB5.SI","U09.SI",
    "P07.SI","VC2.SI","YF8.SI","5NL.SI","5GI.SI","EH5.SI","F9D.SI","T6I.SI",
    "BEC.SI","BTU.SI","ES3.SI","G3B.SI","B58.SI",
]

SG_TICKERS:  list[str] = _dedup(_SGX_BASE)
# Alias for backward compat
SGX_LIQUID_FALLBACK_TICKERS: list[str] = SG_TICKERS


# ═════════════════════════════════════════════════════════════════════════════
# India  ─  existing curated  +  Nifty 50  +  Nifty Next-50  +  Midcap-50
# ═════════════════════════════════════════════════════════════════════════════

_INDIA_BASE: list[str] = [
    # Existing curated high-beta list from config_core
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
    "IRCTC.NS","DIXON.NS","AMBER.NS","KAYNES.NS","GRAVITA.NS","PGEL.NS",
]

_INDIA_INDEX: list[str] = [
    # Nifty 50
    "BHARTIARTL.NS","LT.NS","NTPC.NS","POWERGRID.NS","M&M.NS","BAJAJFINSV.NS",
    "TRENT.NS","NESTLEIND.NS","DIVISLAB.NS","BPCL.NS","HEROMOTOCO.NS",
    "GRASIM.NS","APOLLOHOSP.NS","EICHERMOT.NS","SHRIRAMFIN.NS","BAJAJ-AUTO.NS",
    "BRITANNIA.NS","TATACONSUM.NS","ULTRACEMCO.NS","ONGC.NS","TITAN.NS",
    "ASIANPAINT.NS",
    # Nifty Next 50
    "ABB.NS","AMBUJACEM.NS","ATGL.NS","BERGEPAINT.NS","BOSCHLTD.NS","CANBK.NS",
    "CHOLAFIN.NS","COLPAL.NS","DABUR.NS","DLF.NS","GAIL.NS","GODREJCP.NS",
    "GODREJPROP.NS","HAVELLS.NS","ICICIPRULI.NS","INDIANB.NS","INDUSTOWER.NS",
    "JIOFIN.NS","LTF.NS","LTTS.NS","LUPIN.NS","MANKIND.NS","MARICO.NS",
    "MCDOWELL-N.NS","MPHASIS.NS","MUTHOOTFIN.NS","NAUKRI.NS","NHPC.NS",
    "OBEROIRLTY.NS","OFSS.NS","OIL.NS","PAGEIND.NS","PERSISTENT.NS",
    "PIDILITIND.NS","PIIND.NS","PFC.NS","RECLTD.NS","SAIL.NS","SIEMENS.NS",
    "SRF.NS","TORNTPHARM.NS","TVSMOTOR.NS","UNIONBANK.NS","VBL.NS","VOLTAS.NS",
    "ZYDUSLIFE.NS",
    # Nifty Midcap 50
    "AARTIIND.NS","APLAPOLLO.NS","ASTRAL.NS","AUBANK.NS","AUROPHARMA.NS",
    "BALKRISIND.NS","BANDHANBNK.NS","BIOCON.NS","CANFINHOME.NS","CGPOWER.NS",
    "CONCOR.NS","CUMMINSIND.NS","DEEPAKNTR.NS","ELGIEQUIP.NS","EMAMILTD.NS",
    "ENGINERSIN.NS","ESCORTS.NS","FACT.NS","FEDERALBNK.NS","GLENMARK.NS",
    "GNFC.NS","GSPL.NS","HINDPETRO.NS","IDFCFIRSTB.NS","IGL.NS","INDHOTEL.NS",
    "INDIAMART.NS","IPCALAB.NS","JBCHEPHARM.NS","JKCEMENT.NS","JUBLFOOD.NS",
    "KAJARIACER.NS","KEI.NS","KPITTECH.NS","LALPATHLAB.NS","LAURUSLABS.NS",
    "LICHSGFIN.NS","MANAPPURAM.NS","METROPOLIS.NS","MFSL.NS","NATIONALUM.NS",
    "NLCINDIA.NS","PETRONET.NS","POLYCAB.NS","RADICO.NS","SUNDARMFIN.NS",
    "SUPREMEIND.NS","THERMAX.NS","UBL.NS","ZEEL.NS",
]

INDIA_TICKERS: list[str] = _dedup(_INDIA_BASE + _INDIA_INDEX)


# ═════════════════════════════════════════════════════════════════════════════
# Hong Kong  ─  existing curated  +  Hang Seng + HSI Tech constituents
# ═════════════════════════════════════════════════════════════════════════════

_HK_BASE: list[str] = [
    # Original curated volatile / high-beta list from config_core
    "0700.HK","9988.HK","3690.HK","1810.HK","1024.HK","9618.HK",
    "9888.HK","9999.HK","2015.HK","9868.HK","1211.HK","0981.HK",
    "2382.HK","2018.HK","6618.HK","1347.HK","0241.HK","9961.HK",
    "3888.HK","6690.HK","0772.HK","6611.HK","6060.HK","9992.HK",
    "2318.HK","0388.HK","2331.HK","2333.HK","0175.HK","1929.HK",
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
    "0268.HK","0285.HK","0522.HK","0986.HK","1478.HK","1801.HK",
    "1833.HK","1877.HK","2013.HK","2238.HK","2268.HK","2269.HK",
    "2359.HK","3800.HK","3808.HK","6160.HK","6699.HK","6862.HK",
    "6969.HK","9863.HK","9866.HK","9896.HK","9926.HK","9969.HK",
    "0606.HK","0607.HK","0683.HK","0880.HK","1128.HK","1336.HK",
    "1339.HK","1658.HK","1776.HK","1918.HK","2007.HK","2282.HK",
    "2600.HK","3323.HK","3900.HK","6030.HK","6066.HK","6098.HK",
    "6178.HK","6666.HK","6881.HK","6886.HK","9600.HK","9869.HK",
]

HK_TICKERS: list[str] = _dedup(_HK_BASE)
# Alias used by universe_core fallback
HK_VOLATILE_TICKERS: list[str] = HK_TICKERS


# ═════════════════════════════════════════════════════════════════════════════
# Legacy alias  (config_core imports this for BASE_TICKERS backward compat)
# ═════════════════════════════════════════════════════════════════════════════

BASE_TICKERS: list[str] = _dedup(US_TICKERS + SG_TICKERS + INDIA_TICKERS + HK_TICKERS)


# ═════════════════════════════════════════════════════════════════════════════
# Named universe presets  (used by Breakout Scanner universe dropdown)
# ═════════════════════════════════════════════════════════════════════════════

_US_SP500_DEDUP  = _dedup(_US_SP500)
_US_NDX_DEDUP   = _dedup(_US_NDX100)
_US_BASE_DEDUP  = _dedup(_US_BASE)

MARKET_UNIVERSES: dict[str, list[tuple[str, str, list[str]]]] = {
    "US": [
        ("sp500",      "S&P 500  (~500 stocks)",             _US_SP500_DEDUP),
        ("nasdaq100",  "NASDAQ 100  (~100 stocks)",          _US_NDX_DEDUP),
        ("sp500+ndx",  "S&P 500 + NASDAQ 100  (~550)",       _dedup(_US_SP500_DEDUP + _US_NDX_DEDUP)),
        ("momentum",   "High-Beta / Growth watchlist",       _US_BASE_DEDUP),
        ("sp500+mom",  "S&P 500 + Growth  (~630)",           _dedup(_US_SP500_DEDUP + _US_BASE_DEDUP)),
        ("all_us",     "All US  (S&P 500 + NDX + Growth)",   US_TICKERS),
    ],
    "SGX": [
        ("sgx_full",   "SGX Mainboard  (~120 stocks)",       SG_TICKERS),
    ],
    "India": [
        ("nifty50",    "Nifty 50",                           _dedup(_INDIA_BASE[:50])),
        ("nifty150",   "Nifty 150  (50 + Next50 + Mid50)",   INDIA_TICKERS),
    ],
    "Hong Kong": [
        ("hsi_full",   "Hang Seng + HSI Tech  (~130 stocks)", HK_TICKERS),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# Public API  (imported by tabs and app_runtime)
# ─────────────────────────────────────────────────────────────────────────────

def get_tickers_for_market(market_key: str) -> list[str]:
    """
    Return the FULL merged ticker list for a market.
    This is the single function all tabs should call instead of
    g.get("US_TICKERS") / g.get("SG_TICKERS") etc.

    market_key accepts both emoji form ("🇺🇸 US") and plain form ("US").
    """
    _norm = {
        "US": US_TICKERS,      "🇺🇸 US": US_TICKERS,
        "SGX": SG_TICKERS,     "🇸🇬 SGX": SG_TICKERS,
        "India": INDIA_TICKERS,"🇮🇳 India": INDIA_TICKERS,
        "Hong Kong": HK_TICKERS,"🇭🇰 HK": HK_TICKERS,
        "🇭🇰 Hong Kong": HK_TICKERS,
    }
    return _norm.get(market_key, US_TICKERS)


def universe_options_for_market(market_key: str) -> list[tuple[str, str]]:
    """Returns [(universe_id, display_label), ...] for the given market."""
    _norm = {"🇺🇸 US": "US", "🇸🇬 SGX": "SGX", "🇮🇳 India": "India",
             "🇭🇰 HK": "Hong Kong", "🇭🇰 Hong Kong": "Hong Kong"}
    key = _norm.get(market_key, market_key)
    return [(uid, label) for uid, label, _ in MARKET_UNIVERSES.get(key, [])]


def get_universe(market_key: str, universe_id: str) -> list[str]:
    """Return deduplicated ticker list for market + universe_id."""
    _norm = {"🇺🇸 US": "US", "🇸🇬 SGX": "SGX", "🇮🇳 India": "India",
             "🇭🇰 HK": "Hong Kong", "🇭🇰 Hong Kong": "Hong Kong"}
    key = _norm.get(market_key, market_key)
    for uid, _, tickers in MARKET_UNIVERSES.get(key, []):
        if uid == universe_id:
            return tickers
    return []
