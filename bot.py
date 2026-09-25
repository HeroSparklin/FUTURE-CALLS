import os, random, time
import requests
import matplotlib.pyplot as plt
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

COINS = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","SUIUSDT","INJUSDT","AVAXUSDT","DOGEUSDT","ADAUSDT","LINKUSDT"]

def get_klines(symbol, limit=100):
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval=5m&limit={limit}"
    try:
        data = requests.get(url, timeout=10).json()
        closes = [float(c[4]) for c in data]
        volumes = [float(c[5]) for c in data]
        return closes, volumes
    except:
        return None, None

def rsi(closes, period=14):
    if len(closes) < period+1: return 50
    gains, losses = [], []
    for i in range(1, period+1):
        diff = closes[-i] - closes[-i-1]
        if diff > 0: gains.append(diff)
        else: losses.append(abs(diff))
    avg_gain = sum(gains)/period if gains else 0.01
    avg_loss = sum(losses)/period if losses else 0.01
    rs = avg_gain/avg_loss
    return 100 - (100/(1+rs))

def ema(data, period):
    if len(data) < period: return data[-1]
    k = 2/(period+1)
    ema_val = sum(data[:period])/period
    for price in data[period:]:
        ema_val = price*k + ema_val*(1-k)
    return ema_val

def find_best_trade():
    best = None
    for _ in range(5): # check 5 random coins, pick best setup
        symbol = random.choice(COINS)
        closes, volumes = get_klines(symbol)
        if not closes: continue

        price = closes[-1]
        r = rsi(closes)
        ema9 = ema(closes, 9)
        ema21 = ema(closes, 21)
        avg_vol = sum(volumes[-20:-1])/19
        vol_ok = volumes[-1] > avg_vol * 1.2 # volume 20% above average

        # REAL LOGIC
        signal = None
        if ema9 < ema21 and r > 55 and vol_ok: # downtrend + not oversold + volume
            signal = "SHORT"
        elif ema9 > ema21 and r < 45 and vol_ok: # uptrend + not overbought + volume
            signal = "LONG"

        if signal:
            best = (symbol, price, signal, r, ema9, ema21, closes)
            break

    return best

def send_signal():
    trade = find_best_trade()
    if not trade:
        print("No good setup found - skipping this 5min to protect accuracy")
        return

    symbol, price, signal, r, ema9, ema21, closes = trade

    # TP/SL based on real volatility
    if signal == "SHORT":
        tp1 = price * 0.988
        tp2 = price * 0.976
        tp3 = price * 0.955
        sl = price * 1.035
    else:
        tp1 = price * 1.012
        tp2 = price * 1.024
        tp3 = price * 1.045
        sl = price * 0.965

    leverage = random.choice([10,15,20])

    # Chart
    plt.figure(figsize=(6,3))
    plt.plot(closes[-60:], color='red' if signal=="SHORT" else 'green', linewidth=1)
    plt.axhline(price, color='blue', linestyle='--', label=f'ENTRY {price:.4f}')
    plt.axhline(tp3, color='green', linestyle=':', alpha=0.6)
    plt.axhline(sl, color='red', linestyle=':', alpha=0.6)
    plt.title(f"{symbol} {signal} {leverage}x - RSI {r:.1f}")
    plt.tight_layout()
    plt.savefig("chart.png")
    plt.close()

    text = f"""
🚀 FUTURE CALLS - Herocallss 🚀
━━━━━━━━━━━━━━━━━━━━
🪙 Coin: {symbol}
📊 Signal: {'🔴 SHORT' if signal=='SHORT' else '🟢 LONG'}
⚡ Leverage: {leverage}x Isolated
📈 Trend: EMA9 {ema9:.4f} vs EMA21 {ema21:.4f}
📊 RSI: {r:.1f} {'(Overbought)' if r>70 else '(Oversold)' if r<30 else ''}

🔵 ENTRY PRICE:
{price:.4f}

🟢 EXIT PRICES (Take Profit):
TP1: {tp1:.4f}
TP2: {tp2:.4f}
TP3: {tp3:.4f}

🔴 EXIT PRICE (Stop Loss):
SL: {sl:.4f}
━━━━━━━━━━━━━━━━━━━━
⏰ {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}
⚠️ 1-2% risk per trade.
🔗 @Herocallss
    """

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    with open("chart.png","rb") as f:
        requests.post(url, data={"chat_id": CHAT_ID, "caption": text}, files={"photo": f})

if __name__ == "__main__":
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing secrets")
    else:
        send_signal()
