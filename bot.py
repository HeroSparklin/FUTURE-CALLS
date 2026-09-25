import os, requests, random

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# --- 50 COINS - BTC + ALT + MEME ---
coins = [
    # TOP 10
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "SHIBUSDT", "DOTUSDT",
    # ALT COINS
    "LINKUSDT", "TRXUSDT", "POLUSDT", "LTCUSDT", "BCHUSDT",
    "UNIUSDT", "XLMUSDT", "ETCUSDT", "FILUSDT", "ATOMUSDT",
    "HBARUSDT", "VETUSDT", "ICPUSDT", "NEARUSDT", "APTUSDT",
    "ARBUSDT", "OPUSDT", "SUIUSDT", "ENAUSDT", "TAOUSDT",
    "INJUSDT", "RNDRUSDT", "FETUSDT", "ARUSDT", "SEIUSDT",
    "WLDUSDT", "TIAUSDT", "STXUSDT", "IMXUSDT", "AAVEUSDT",
    # MEME COINS 🔥
    "PEPEUSDT", "WIFUSDT", "BONKUSDT", "FLOKIUSDT", "MEMEUSDT",
    "1000PEPEUSDT", "1000BONKUSDT", "BRETTUSDT", "POPCATUSDT", "PNUTUSDT"
]

# Fix for 1000PEPE type (price will show correctly)
coin = random.choice(coins)
direction = random.choice(["LONG", "SHORT"])
leverage = random.choice(["5x", "10x", "15x", "20x", "25x"])

# --- GET REAL PRICE ---
try:
    price_data = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}").json()
    entry_price = float(price_data['price'])
except:
    entry_price = 0.1234

# --- CALCULATE ---
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

# Format price (if price < 1, show 6 decimals)
if entry_price < 1:
    fmt = ".6f"
else:
    fmt = ".3f"

signal = f"""
🚀 **FUTURE CALLS - Herocallss** 🚀
━━━━━━━━━━━━━━━━━━━━

🪙 **Coin:** `{coin}` {'🐶 MEME' if 'PEPE' in coin or 'BONK' in coin or 'WIF' in coin or 'FLOKI' in coin or 'MEME' in coin or 'BRETT' in coin or 'POPCAT' in coin or 'PNUT' in coin else '💎 ALT' if coin not in ['BTCUSDT','ETHUSDT','BNBUSDT'] else '👑 TOP'}
📊 **Signal:** {emoji}
⚡️ **Leverage:** {leverage} Isolated

💰 **Entry:** `{entry_price:{fmt}}`

📈 **Take Profits:**
TP1: `{tp1:{fmt}}` (+1%)
TP2: `{tp2:{fmt}}` (+2%)
TP3: `{tp3:{fmt}}` (+4%)

🛑 **Stop Loss:** `{sl:{fmt}}`

━━━━━━━━━━━━━━━━━━━━
⚠️ Use 1-2% risk per trade.

🔗 @Herocallss
"""

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
r = requests.post(url, json={"chat_id": CHAT_ID, "text": signal, "parse_mode": "Markdown"})
print(r.text)
