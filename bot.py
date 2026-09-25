import os, requests, random
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

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

# --- GET REAL PRICE & CHART DATA ---
try:
    r = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={coin}", timeout=10)
    entry_price = float(r.json()['price'])
    kl = requests.get(f"https://fapi.binance.com/fapi/v1/klines?symbol={coin}&interval=1h&limit=50", timeout=10).json()
    closes = [float(x[4]) for x in kl]
except:
    entry_price = 50000
    closes = [50000 + random.uniform(-100,100) for _ in range(50)]

# --- CALCULATE EXIT PRICES ---
if direction == "LONG":
    tp1, tp2, tp3, sl = entry_price*1.01, entry_price*1.02, entry_price*1.04, entry_price*0.97
    emoji, color = "🟢 LONG", "green"
else:
    tp1, tp2, tp3, sl = entry_price*0.99, entry_price*0.98, entry_price*0.96, entry_price*1.03
    emoji, color = "🔴 SHORT", "red"

fmt = ".6f" if entry_price < 1 else ".2f" if entry_price > 100 else ".4f"

# --- CREATE CHART ---
plt.figure(figsize=(10,4))
plt.plot(closes, color=color, linewidth=2, label=f"{coin} Price")
plt.axhline(entry_price, color='blue', linestyle='--', label=f"ENTRY {entry_price:{fmt}}")
plt.axhline(tp1, color='green', linestyle=':', alpha=0.7, label=f"TP1")
plt.axhline(sl, color='red', linestyle=':', alpha=0.7, label=f"SL")
plt.title(f"{coin} {direction} {leverage} - ENTRY & EXIT LEVELS", fontsize=12, fontweight='bold')
plt.legend(fontsize=8)
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("chart.png", dpi=150)
plt.close()

# --- NEW SIGNAL WITH ENTRY & EXIT ---
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
   TP1: {tp1:{fmt}} (+1%)
   TP2: {tp2:{fmt}} (+2%)
   TP3: {tp3:{fmt}} (+4%)

🔴 EXIT PRICE (Stop Loss):
   SL: {sl:{fmt}} (-3%)
━━━━━━━━━━━━━━━━━━━━

⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
⚠️ 1-2% risk per trade.
🔗 @Herocallss
"""

url_photo = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
with open("chart.png", "rb") as photo:
    r = requests.post(url_photo, data={"chat_id": CHAT_ID, "caption": caption}, files={"photo": photo})
print(r.text)
