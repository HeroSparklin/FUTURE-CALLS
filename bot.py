import os
import requests
import time

# === SECRETS FROM GITHUB ACTIONS ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# FIXED: Use vision endpoint that works from GitHub Actions (US servers)
BINANCE_VISION_URL = "https://data-api.binance.vision/api/v3/klines"

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram secrets missing!")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        r = requests.post(url, data=data, timeout=10)
        print(f"Telegram response: {r.text}")
    except Exception as e:
        print(f"Telegram error: {e}")

# Test message to prove GitHub -> Telegram works
send_telegram("✅ *FUTURE-CALLS bot is ONLINE*\nFixed Binance 451 error. Filters active.")

def get_futures_symbols():
    # Hardcoded to avoid 451 error on exchangeInfo
    return ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT","LINKUSDT","LTCUSDT","TRXUSDT","DOTUSDT","MATICUSDT","SHIBUSDT","UNIUSDT","PEPEUSDT","NEARUSDT","APTUSDT","ARBUSDT","OPUSDT","SUIUSDT","ENAUSDT","WIFUSDT","BONKUSDT"]

def check_signal(symbol):
    try:
        if symbol in ["EURGBP", "EURTRY", "GBPUSDC", "EURBUSD", "NGNUSDT"]:
            return None
        params = {"symbol": symbol, "interval": "15m", "limit": 100}
        r = requests.get(BINANCE_VISION_URL, params=params, timeout=10)
        r.raise_for_status()
        klines = r.json()
        closes = [float(k[4]) for k in klines]
        volumes = [float(k[5]) for k in klines]
        if len(closes) < 50:
            return None

        # 80% STRICT FILTERS
        ema9 = sum(closes[-9:]) / 9
        ema21 = sum(closes[-21:]) / 21
        ema50 = sum(closes[-50:]) / 50

        # RSI simple
        gains = [max(0, closes[i]-closes[i-1]) for i in range(1,len(closes))]
        losses = [max(0, closes[i-1]-closes[i]) for i in range(1,len(closes))]
        avg_gain = sum(gains[-14:]) / 14
        avg_loss = sum(losses[-14:]) / 14
        if avg_loss == 0:
            return None
        rsi = 100 - (100 / (1 + avg_gain/avg_loss))

        vol_avg = sum(volumes[-20:]) / 20
        last_vol = volumes[-1]

        # STRICT LONG
        if ema9 > ema21 > ema50 and 55 < rsi < 70 and last_vol > vol_avg * 1.2:
            return "LONG"
        # STRICT SHORT
        if ema9 < ema21 < ema50 and 30 < rsi < 45 and last_vol > vol_avg * 1.2:
            return "SHORT"
        return None
    except Exception as e:
        print(f"Skip {symbol}: {e}")
        return None

# === MAIN ===
print(f"TELEGRAM_TOKEN: {'***' if TELEGRAM_TOKEN else 'MISSING'}")
print(f"TELEGRAM_CHAT_ID: {'***' if TELEGRAM_CHAT_ID else 'MISSING'}")
print("Scanning coins...")

symbols = get_futures_symbols()
found = 0
for sym in symbols:
    signal = check_signal(sym)
    print(f"Checked {sym}: {signal}")
    if signal:
        found += 1
        msg = f"🚀 *FUTURE-CALL: {sym}* - {signal}\nInterval: 15m\nStrict filters passed ✅"
        print(msg)
        send_telegram(msg)
        time.sleep(1)

if found == 0:
    print("No strict signals found this run - that's normal.")

print(f"Done. Found {found} calls.")
