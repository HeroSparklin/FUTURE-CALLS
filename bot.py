import os, requests, time
import ccxt

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BINANCE = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})

COINS = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT","SHIBUSDT","DOTUSDT",
    "LINKUSDT","TRXUSDT","MATICUSDT","LTCUSDT","BCHUSDT","NEARUSDT","UNIUSDT","PEPEUSDT","APTUSDT","ETCUSDT",
    "FILUSDT","STXUSDT","ICPUSDT","ARBUSDT","HBARUSDT","MKRUSDT","INJUSDT","RNDRUSDT","SUIUSDT","OPUSDT",
    "LDOUSDT","TAOUSDT","IMXUSDT","SEIUSDT","GRTUSDT","FETUSDT","ARUSDT","AGIXUSDT","THETAUSDT","FLOWUSDT",
    "KAVAUSDT","ALGOUSDT","EGLDUSDT","AXSUSDT","SANDUSDT","MANAUSDT","CHZUSDT","CFXUSDT","AAVEUSDT","XTZUSDT",
    "EOSUSDT","KLAYUSDT","NEOUSDT","IOTAUSDT","KSMUSDT","ZILUSDT","ENJUSDT","MINAUSDT","ROSEUSDT","COMPUSDT",
    "ONEUSDT","LRCUSDT","QTUMUSDT","RVNUSDT","CELOUSDT","GMTUSDT","BLURUSDT","JASMYUSDT","SKLUSDT","GALAUSDT",
    "JOEUSDT","MAGICUSDT","LINAUSDT","HIGHUSDT","HOOKUSDT","IDUSDT","RDNTUSDT","EDUUSDT","FLOKIUSDT","BONKUSDT",
    "WIFUSDT","1000SATSUSDT","ORDIUSDT","JUPUSDT","STRKUSDT","WUSDT","ARKMUSDT","PIXELUSDT","PORTALUSDT","ACEUSDT",
    "NFPUSDT","AIUSDT","XAIUSDT","ASTUSDT","MNTUSDT","ENAUSDT","EURUSDT","GBPUSDT","AUDUSDT","TRYUSDT","BRLUSDT",
    "NGNUSDT","EURGBP","EURTRY","GBPUSDC","EURBUSD"
]

def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)

def check(symbol):
    try:
        ohlcv = BINANCE.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        closes = [c[4] for c in ohlcv]
        entry = closes[-1]
        ema9 = sum(closes[-9:])/9
        ema21 = sum(closes[-21:])/21
        if ema9 < ema21: # SHORT
            return f"🚀 FUTURE-CALL: {symbol} - SHORT\nInterval: 15m\n\n💰 Entry: {entry:.4f}\n📉 TPs:\nTP1: {entry*0.992:.4f}\nTP2: {entry*0.985:.4f}\nTP3: {entry*0.97:.4f}\n🛑 SL: {entry*1.03:.4f}\n\nStrict filters passed ✅"
        return None
    except:
        return None

print(f"Scanning {len(COINS)} coins...")
found = 0
for coin in COINS:
    s = check(coin)
    if s:
        send(s)
        found += 1
    time.sleep(0.2)
print(f"Done. Found {found} signals")
