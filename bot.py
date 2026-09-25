import os, requests, random

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

coins = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
coin = random.choice(coins)
direction = random.choice(["LONG 🟢", "SHORT 🔴"])
leverage = random.choice(["5x", "10x", "20x"])

signal = f"""
🚀 FUTURE CALLS - Herocallss 🚀

Coin: {coin}
Signal: {direction}
Leverage: {leverage} Isolated

Entry: Market Price
Take Profit:
TP1: +40%
TP2: +80%
TP3: +150%

Stop Loss: -30%

⚠️ Not financial advice. Trade with risk management.

Join: @Herocallss
"""

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
r = requests.post(url, json={"chat_id": CHAT_ID, "text": signal, "parse_mode": "Markdown"})
print(r.text)
