import os, requests, random
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

coins = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","LINKUSDT","AVAXUSDT","INJUSDT","NEARUSDT","PEPEUSDT","WIFUSDT","BONKUSDT","FLOKIUSDT","SUIUSDT"]

coin = random.choice(coins)
direction = random.choice(["LONG","SHORT"])
leverage = random.choice(["10x","15x","20x"])

# --- FIXED PRICE FETCH (works on GitHub) ---
def get_price(symbol):
    urls = [
        f"https://data-api.binance.vision/api/v3/ticker/price?symbol={symbol}",
        f"https://api.bybit.com/v5/market/tickers?category=linear&symbol={symbol}",
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=10).json()
            if 'price' in r:
                return float(r['price']), None
            if 'result' in r and 'list' in r['result']:
                return float(r['result']['list'][0]['lastPrice']), None
        except: pass
    return None, None

entry_price = None
closes = None

# Try Binance Vision klines for chart + price
try:
    k = requests.get(f"https://data-api.binance.vision/api/v3/klines?symbol={coin}&interval=1h&limit=60", timeout=10).json()
    closes = [float(x[4]) for x in k]
    entry_price = closes[-1]
except Exception as e:
    print("Klines failed", e)

if entry_price is None:
    entry_price, _ = get_price(coin)

if entry_price is None:
    entry_price = 65000 if "BTC" in coin else 3500 if "ETH" in coin else 100
    closes = [entry_price + random.uniform(-entry_price*0.02, entry_price*0.02) for _ in range(60)]

if closes is None:
    closes = [entry_price + random.uniform(-entry_price*0.01, entry_price*0.01) for _ in range(60)]

if direction == "LONG":
    tp1, tp2, tp3, sl = entry_price*1.015, entry_price*1.03, entry_price*1.05, entry_price*0.96
    color = "green"
    emoji = "🟢 LONG"
else:
    tp1, tp2, tp3, sl = entry_price*0.985, entry_price*0.97, entry_price*0.95, entry_price*1.04
    color = "red"
    emoji = "🔴 SHORT"

fmt = ".6f" if entry_price < 1 else ".2f"

plt.figure(figsize=(10,4))
plt.plot(closes, color=color, linewidth=2)
plt.axhline(entry_price, color='blue', linestyle='--', label=f"ENTRY {entry_price:{fmt}}")
plt.axhline(tp1, color='green', linestyle=':', alpha=0.7)
plt.axhline(sl, color='red', linestyle=':', alpha=0.7)
plt.title(f"{coin} {direction} {leverage} - ENTRY & EXIT", fontweight='bold')
plt.legend(fontsize=8)
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("chart.png", dpi=150)
plt.close()

caption = f"""
🚀 FUTURE CALLS - Herocallss 🚀
━━━━━━━━━━━━━━━━━━━━
🪙 Coin: {coin}
📊 Signal: {emoji}
⚡️ Leverage: {leverage} Isolated
━━━━━━━━━━━━━━━━━━━━
🔵 ENTRY PRICE:
   {entry_price:{fmt}}

🟢 EXIT PRICES (Take Profit):
   TP1: {tp1:{fmt}}
   TP2: {tp2:{fmt}}
   TP3: {tp3:{fmt}}

🔴 EXIT PRICE (Stop Loss):
   SL: {sl:{fmt}}
━━━━━━━━━━━━━━━━━━━━
⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
⚠️ 1-2% risk per trade.
🔗 @Herocallss
"""

url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
with open("chart.png","rb") as p:
    r = requests.post(url, data={"chat_id":CHAT_ID, "caption":caption}, files={"photo":p})
print(r.text, coin, entry_price)
