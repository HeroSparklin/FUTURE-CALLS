import requests
import os
import time

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# This URL works on GitHub US - not blocked like normal Binance
BINANCE_VISION_URL = "https://data-api.binance.vision/api/v3/klines"

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
    "EURUSDT", "GBPUSDT", "AUDUSDT", "TRYUSDT", "BRLUSDT"
]

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(msg)
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        print(f"Sent: {msg}")
    except Exception as e:
        print(f"Telegram error: {e}")

def check_signal(symbol):
    try:
        # Skip forex like EURGBP which binance.vision doesn't have
        if symbol in ["EURGBP", "EURTRY", "GBPUSDC", "EURBUSD", "NGNUSDT"]:
            return None

        params = {"symbol": symbol, "interval": "15m", "limit": 50}
        r = requests.get(BINANCE_VISION_URL, params=params, timeout=10)
        r.raise_for_status()
        klines = r.json()
        closes = [float(k[4]) for k in klines]
        if len(closes) < 21:
            return None
        ema9 = sum(closes[-9:]) / 9
        ema21 = sum(closes[-21:]) / 21
        if ema9 > ema21 * 1.001:
            return "LONG"
        if ema9 < ema21 * 0.999:
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
    time.sleep(0.2) # avoid rate limit

if found == 0:
    print("No perfect setup found - protecting account")
print(f"Done. Found {found} signals")
