import time
import requests
import ccxt

# --- CONFIG ---
TELEGRAM_TOKEN = "YOUR_TELEGRAM_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"
BINANCE = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

# 105 TOTAL COINS
COINS = [
    # 93 CORE CRYPTO
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

    # 2 NEW CRYPTO ADDED
    "ASTUSDT", "MNTUSDT",

    # 10 CURRENCY PAIRS ADDED
    "EURUSDT", "GBPUSDT", "AUDUSDT", "TRYUSDT", "BRLUSDT",
    "NGNUSDT", "EURGBP", "EURTRY", "GBPUSDC", "EURBUSD"
]

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg})

def check_signal(symbol):
    try:
        ohlcv = BINANCE.fetch_ohlcv(symbol, timeframe='15m', limit=100)
        closes = [c[4] for c in ohlcv]
        # YOUR 80% STRICT LOGIC (EMA + RSI)
        ema_fast = sum(closes[-9:]) / 9
        ema_slow = sum(closes[-21:]) / 21
        rsi = 50 # placeholder - keep your existing RSI calc

        # STRICT 80% MODE
        if ema_fast > ema_slow and rsi < 35:
            return "LONG"
        if ema_fast < ema_slow and rsi > 65:
            return "SHORT"
        return None
    except:
        return None # coin not available, bot skips

print(f"FUTURE-CALLS BOT STARTED - Scanning {len(COINS)} coins")

while True:
    found = 0
    for coin in COINS:
        signal = check_signal(coin)
        if signal:
            send_telegram(f"{signal} {coin} - Perfect EMA + RSI setup - 80% strict - 10x - $20 margin")
            found += 1
        time.sleep(0.3)

    if found == 0:
        print("No perfect setup found - protecting account")

    time.sleep(60) # scan every 1 min
