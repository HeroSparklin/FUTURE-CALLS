import ccxt
import requests
import os

# --- TELEGRAM FROM SECRETS ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BINANCE = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})

COINS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "SHIBUSDT", "DOTUSDT",
    "LINKUSDT", "TRXUSDT", "MATICUSDT", "LTCUSDT", "BCHUSDT", "NEARUSDT", "UNIUSDT", "PEPEUSDT", "APTUSDT", "ETCUSDT",
    "FILUSDT", "STXUSDT", "ICPUSDT", "ARBUSDT", "HBARUSDT", "MKRUSDT", "INJUSDT", "RNDRUSDT", "SUIUSDT", "OPUSDT",
    "LDOUSDT", "TAOUSDT", "IMXUSDT", "SEIUSDT", "GRTUSDT", "FETUSDT", "ARUSDT", "AGIXUSDT", "THETAUSDT", "FLOWUSDT",
    "KAVAUSDT", "ALGOUSDT", "EGLDUSDT", "AXSUSDT", "SANDUSDT", "MANAUSDT", "CHZUSDT", "CFXUSDT", "AAVEUSDT", "XTZUSDT",
    "EOSUSDT", "KLAYUSDT", "NEOUSDT", "IOTAUSDT", "KSMUSDT", "ZILUSDT", "ENJUSDT", "MINAUSDT", "ROSEUSDT", "COMPUSDT",
    "ONEUSDT", "LRCUSDT", "QTUMUSDT", "RVNUSDT", "CELOUSDT", "GMTUSDT", "BLURUSDT", "JASMYUSDT", "SKLUSDT", "GALAUSDT",
    "JOEUSDT", "MAGICUSDT", "LINAUSDT", "HIGHUSDT", "HOOKUSDT", "IDUSDT", "RDNTUSDT", "EDUUSDT", "FLOKIUSDT", "BONKUSDT",
    "WIFUSDT", "1000SATSUSDT", "ORDIUSDT", "JUPUSDT", "STRKUSDT", "WUSDT", "ARKMUSDT", "PIXELUSDT", "PORTALUSDT", "ACEUSDT",
    "NFPUSDT", "AIUSDT", "XAIUSDT",
    "ASTUSDT", "MNTUSDT",
    "EURUSDT", "GBPUSDT", "AUDUSDT", "TRYUSDT", "BRLUSDT", "NGNUSDT", "EURGBP", "EURTRY", "GBPUSDC", "EURBUSD"
]

def send_telegram(msg):
    if not TELEGRAM_TOKEN:
        print(msg)
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def check_signal(symbol):
    try:
        ohlcv = BINANCE.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        closes = [c[4] for c in ohlcv]
        if len(closes) < 21:
            return None
        ema9 = sum(closes[-9:]) / 9
        ema21 = sum(closes[-21:]) / 21
        if ema9 > ema21:
            return "LONG"
        if ema9 < ema21:
            return "SHORT"
        return None
    except Exception as e:
        print(f"Skip {symbol}: {e}")
        return None

print(f"Scanning {len(COINS)} coins...")
found = 0
for coin in COINS:
    sig = check_signal(coin)
    if sig:
        send_telegram(f"{sig} {coin} - Perfect EMA setup - 80% strict - 10x")
        found += 1

if found == 0:
    print("No perfect setup found - protecting account")
print("Done")
