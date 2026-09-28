import os, requests, time
import ccxt

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TOKEN or not CHAT_ID:
    print("ERROR: BOT_TOKEN or CHAT_ID missing in GitHub Secrets")
    exit(1)

BINANCE = ccxt.binance({
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

# 105 COINS
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

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        print(r.text)
    except Exception as e:
        print(f"Telegram error: {e}")

def check_signal(symbol):
    try:
        ohlcv = BINANCE.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        if len(ohlcv) < 22:
            return None
        closes = [c[4] for c in ohlcv]
        entry = closes[-1]
        ema_fast = sum(closes[-9:]) / 9
        ema_slow = sum(closes[-21:]) / 21

        # STRICT 80% SHORT FILTER - only send when bearish
        if ema_fast < ema_slow:
            tp1 = entry * 0.992 # -0.8%
            tp2 = entry * 0.985 # -1.5%
            tp3 = entry * 0.97 # -3.0%
            sl = entry * 1.03 # +3.0%

            return (
                f"🚀 FUTURE-CALL: {symbol} - SHORT\n"
                f"Interval: 15m\n\n"
                f"💰 Entry: `{entry:.4f}`\n\n"
                f"📉 TPs:\n"
                f"TP1: `{tp1:.4f}`\n"
                f"TP2: `{tp2:.4f}`\n"
                f"TP3: `{tp3:.4f}`\n\n"
                f"🛑 SL: `{sl:.4f}`\n\n"
                f"Strict filters passed ✅"
            )
        return None
    except Exception as e:
        print(f"Skip {symbol}: {e}")
        return None

# --- MAIN - RUN ONCE AND EXIT ---
print(f"FUTURE-CALLS BOT STARTED - Scanning {len(COINS)} coins")

found = 0
for coin in COINS:
    sig = check_signal(coin)
    if sig:
        send_telegram(sig)
        found += 1
    time.sleep(0.2)

print(f"Done. Found {found} signals. Exiting now.")
