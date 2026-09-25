import os, requests, random

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

coins = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "SHIBUSDT", "DOTUSDT",
    "LINKUSDT", "TRXUSDT", "POLUSDT", "LTCUSDT", "BCHUSDT",
    "UNIUSDT", "XLMUSDT", "ETCUSDT", "FILUSDT", "ATOMUSDT",
    "HBARUSDT", "VETUSDT", "ICPUSDT", "NEARUSDT", "APTUSDT",
    "ARBUSDT", "OPUSDT", "SUIUSDT", "ENAUSDT", "TAOUSDT",
    "INJUSDT", "RNDRUSDT", "FETUSDT", "ARUSDT", "SEIUSDT",
    "WLDUSDT", "TIAUSDT", "STXUSDT", "IMXUSDT", "AAVEUSDT",
    "PEPEUSDT", "WIFUSDT", "BONKUSDT", "FLOKIUSDT", "MEMEUSDT",
    "BRETTUSDT", "POPCATUSDT", "PNUTUSDT", "1000PEPEUSDT", "1000BONKUSDT"
]

coin = random.choice(coins)
direction = random.choice(["LONG", "SHORT"])
leverage = random.choice(["5x", "10x", "15x", "20x", "25x"])

# --- FIXED PRICE FETCH - USE FUTURES API ---
entry_price = 0
try:
    # Try Futures API (works on GitHub)
    r = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={coin}", timeout=10)
    entry_price = float(r.json()['price'])
except:
    try:
        # Backup API
        r = requests.get(f"https://data-api.binance.vision/api/v3/ticker/price?symbol={coin}", timeout=10)
        entry_price = float(r.json()['price'])
    except:
        entry_price = 0

if entry_price == 0:
    # If both fail, skip this run and pick BTC as backup
    coin = "BTCUSDT"
    r = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={coin}", timeout=10)
    entry_price = float(r.json()['price'])

if direction == "LONG":
    tp1 = entry_price * 1.01
    tp2 = entry_price * 1.02
    tp3 = entry_price * 1.04
    sl = entry_price * 0.97
    emoji = "🟢 LONG"
else:
    tp1 = entry_price * 0.99
    tp2 = entry_price * 0.98
    tp3 = entry_price * 0.96
    sl = entry_price * 1.03
    emoji = "🔴 SHORT"

fmt = ".6f" if entry_price < 1 else ".2f" if entry_price > 100 else ".4f"

signal = f"""
🚀 FUTURE CALLS - Herocallss 🚀
━━━━━━━━━━━━━━━━━━━━

🪙 Coin: {coin}
📊 Signal: {emoji}
⚡️ Leverage: {leverage} Isolated

💰 Entry: {entry_price:{fmt}}

📈 Take Profits:
TP1: {tp1:{fmt}} (+1%)
TP2: {tp2:{fmt}} (+2%)
TP3: {tp3:{fmt}} (+4%)

🛑 Stop Loss: {sl:{fmt}}

━━━━━━━━━━━━━━━━━━━━
⚠️ Use 1-2% risk per trade.
🔗 @Herocallss
"""

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
r = requests.post(url, json={"chat_id": CHAT_ID, "text": signal})
print(r.text)
print(f"PRICE FETCHED: {entry_price} for {coin}")
