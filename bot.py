import os, requests, time
import ccxt
import pandas as pd

# --- SECRETS ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BINANCE = ccxt.binance({"enableRateLimit": True})

MAJORS = ["BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT","XRP/USDT","ADA/USDT","AVAX/USDT","DOGE/USDT","DOT/USDT","LINK/USDT","LTC/USDT","BCH/USDT","XLM/USDT","ETC/USDT","TRX/USDT"]
ALTS = ["PEPE/USDT","WIF/USDT","BONK/USDT","PENGU/USDT","POPCAT/USDT","FLOKI/USDT","SHIB/USDT","NEAR/USDT","ARB/USDT","OP/USDT","APT/USDT","SUI/USDT","SEI/USDT","TIA/USDT","W/USDT","ENA/USDT","RENDER/USDT","FET/USDT","INJ/USDT","ONDO/USDT","ASTER/USDT","BRETT/USDT","MOG/USDT","MEW/USDT","BOME/USDT","PYTH/USDT","JUP/USDT","STRK/USDT","DYM/USDT","ALT/USDT","MANTA/USDT","XAI/USDT","JTO/USDT","PENDLE/USDT","AAVE/USDT","UNI/USDT","MATIC/USDT","FIL/USDT","STX/USDT"]
ALL_COINS = MAJORS + ALTS

def get_btc_dominance():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10).json()
        return r['data']['market_cap_percentage']['btc']
    except:
        return 59.6

def calc_mtf_score(symbol):
    try:
        scores = []
        for tf in ['1h','4h','1d']:
            ohlcv = BINANCE.fetch_ohlcv(symbol, tf, limit=100)
            df = pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v'])
            close = df['c']
            ema20 = close.ewm(span=20).mean().iloc[-1]
            ema50 = close.ewm(span=50).mean().iloc[-1]
            price = close.iloc[-1]
            delta = close.diff()
            gain = delta.where(delta>0,0).ewm(alpha=1/14).mean()
            loss = -delta.where(delta<0,0).ewm(alpha=1/14).mean()
            rs = gain/loss
            rsi = 100 - (100/(1+rs))
            rsi_val = rsi.iloc[-1]
            tf_score = 0
            if price > ema20 > ema50: tf_score += 35
            elif price < ema20 < ema50: tf_score += 8
            else: tf_score += 15
            if 55 < rsi_val < 75: tf_score += 25
            elif 45 < rsi_val < 55: tf_score += 15
            elif rsi_val > 75: tf_score += 10
            vol_ma = df['v'].rolling(20).mean().iloc[-1]
            if df['v'].iloc[-1] > vol_ma*1.5: tf_score += 15
            scores.append(min(tf_score, 35))
        total = sum(scores)
        if total > 70: total += 5
        return min(int(total), 95), df['c'].iloc[-1], ema20, rsi_val
    except:
        return 0, 0, 0, 50

def get_leverage(score, is_major, is_long):
    if not is_long: return 2
    if score >= 90: return 10 if is_major else 5
    if score >= 85: return 7 if is_major else 4
    if score >= 80: return 5 if is_major else 3
    return 0

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(f"MOCK: {msg}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)

btc_d = get_btc_dominance()
is_altseason = btc_d < 52
mode = "ALT SEASON 🚀" if is_altseason else "NORMAL MODE"
print(f"BTC.D {btc_d:.1f}% -> {mode}")

candidates = []
for symbol in ALL_COINS:
    score, price, ema20, rsi = calc_mtf_score(symbol)
    if score < 70: continue
    is_major = symbol in MAJORS
    is_alt = not is_major
    is_long = price > ema20
    if is_altseason and is_alt and not is_long: continue
    if score >= 80:
        lev = get_leverage(score, is_major, is_long)
        if lev == 0: continue
        candidates.append({"symbol": symbol, "score": score, "price": price, "rsi": rsi, "is_major": is_major, "is_long": is_long, "lev": lev})
    time.sleep(0.2)

candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)

if not candidates:
    msg = f"Bot Lively [V2 80% STRICT 55 COINS]\nStage1: {len(ALL_COINS)} coins | Stage2: 0 candidates\nNo 80+ signal | BTC.D {btc_d:.1f}% | {mode}"
    send_telegram(msg)
else:
    for c in candidates[:3]:
        side = "🟢 LONG" if c['is_long'] else "🔴 SHORT"
        coin_type = "MAJOR" if c['is_major'] else "ALT"
        entry = c['price']
        is_long = c['is_long']

        if is_altseason:
            tp1_pct, tp2_pct, tp3_pct, sl_pct = 0.05, 0.10, 0.20, 0.05
        else:
            tp1_pct, tp2_pct, tp3_pct, sl_pct = 0.03, 0.07, 0.12, 0.03

        if is_long:
            tp1 = entry * (1 + tp1_pct)
            tp2 = entry * (1 + tp2_pct)
            tp3 = entry * (1 + tp3_pct)
            sl = entry * (1 - sl_pct)
        else:
            tp1 = entry * (1 - tp1_pct)
            tp2 = entry * (1 - tp2_pct)
            tp3 = entry * (1 - tp3_pct)
            sl = entry * (1 + sl_pct)

        msg = f"""{side} {c['score']}% MTF | {coin_type} | {mode}
Coin: {c['symbol']}
Entry: {entry:.6f}
Leverage: {c['lev']}x Isolated

TP1: {tp1:.6f} ({tp1_pct*100:.0f}%)
TP2: {tp2:.6f} ({tp2_pct*100:.0f}%)
TP3: {tp3:.6f} ({tp3_pct*100:.0f}%)
SL: {sl:.6f} ({sl_pct*100:.0f}%)

RSI: {c['rsi']:.1f} | BTC.D {btc_d:.1f}%
"""
        send_telegram(msg)
        time.sleep(1)

print(f"Done - {len(candidates)} signals")
