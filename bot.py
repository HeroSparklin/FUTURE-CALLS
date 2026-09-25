import os, requests, random
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

coins = [
    "BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","DOGEUSDT",
    "ADAUSDT","AVAXUSDT","LINKUSDT","TRXUSDT","LTCUSDT","INJUSDT",
    "NEARUSDT","APTUSDT","ARBUSDT","SUIUSDT","PEPEUSDT","WIFUSDT",
    "BONKUSDT","FLOKIUSDT"
]

coin = random.choice(coins)
direction = random.choice(["LONG","SHORT"])
leverage = random.choice(["5x","10x","15x","20x"])

# REAL PRICE - spot API works 100%
try:
    r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}", timeout=10).json()
    entry_price = float(r['price'])
    kl = requests.get(f"https://api.binance.com/api/v3/klines?symbol={coin}&interval=1h&limit=60", timeout=10).json()
    closes = [float(x[4]) for x in kl]
except Exception as e:
    print(f"API error {e}, using fallback")
    entry_price = 100.0
    closes = [100 + random.uniform(-2,2) for _ in range(60)]

if direction == "LONG":
    tp1, tp2, tp3, sl = entry_price*1.012, entry_price*1.025, entry_price*1.045, entry_price*0.97
    emoji, color = "🟢 LONG", "green"
else:
    tp1, tp2, tp3, sl = entry_price*0.988, entry_price*0.975, entry_price*0.955, entry_price*1.03
    emoji, color = "🔴 SHORT", "red"

fmt = ".6f" if entry_price < 1 else ".2f" if entry_price > 100 else ".4f"

# CHART
plt.figure(figsize=(10,4))
plt.plot(closes, color=color, linewidth=2)
plt.axhline(entry_price, color='blue', linestyle='--', linewidth=1.5, label=f"ENTRY {entry_price:{fmt}}")
plt.axhline(tp1, color='green', linestyle=':', label="TP1/SL")
plt.axhline(sl, color='red', linestyle=':', label="SL")
plt.title(f"{coin} {direction} {leverage} | ENTRY & EXIT", fontweight='bold')
plt.legend()
plt.grid(True, alpha=0.3)
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
    requests.post(url, data={"chat_id":CHAT_ID, "caption":caption}, files={"photo":p})
print("Posted", coin, entry_price)
