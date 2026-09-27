import os
import requests
import time

# === SECRETS FROM GITHUB ACTIONS ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

BINANCE_VISION_URL = "https://api.binance.com/api/v3/klines"
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/exchangeInfo"

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

# Test that GitHub -> Telegram works
send_telegram("✅ *FUTURE-CALLS bot is ONLINE*\nFilters active. Will alert when signal found.")

def get_futures_symbols():
    try:
        # USDT perpetual futures-like pairs on spot API
        r = requests.get(BINANCE_TICKER_URL, timeout=10)
        r.raise_for_status()
        symbols = [s["symbol"] for s in r.json()["symbols"] if s["symbol"].endswith("USDT") and s["status"]=="TRADING"]
        # To make it faster, scan top 80 only
        return symbols[:80]
    except Exception as e:
        print(f"Error getting symbols: {e}")
        return ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT"]

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

        # STRICT LONG: EMA9>EMA21>EMA50 + RSI 55-70 + high volume
        if ema9 > ema21 > ema50 and 55 < rsi < 70 and last_vol > vol_avg * 1.2:
            return "LONG"
        # STRICT SHORT: EMA9<EMA21<EMA50 + RSI 30-45 + high volume
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
    if signal:
        found += 1
        msg = f"🚀 *FUTURE-CALL: {sym}* - {signal}\nInterval: 15m\nStrict filters passed ✅\nTime: {time.strftime('%Y-%m-%d %H:%M UTC')}"
        print(msg)
        send_telegram(msg)
        time.sleep(1) # avoid telegram flood

if found == 0:
    print("No strict signals found this run - that's normal.")
    # Uncomment next line if you want a message even when nothing found
    # send_telegram("Scan complete - no 80% signals found this hour.")

print(f"Done. Found {found} calls.")
