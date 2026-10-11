import os, requests, time
import ccxt
import pandas as pd
import numpy as np

# --- CONFIG ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BINANCE = ccxt.binance({"enableRateLimit": True})

MAJORS = ["BTC/USDT","ETH/USDT","SOL/USDT","BNB/USDT","XRP/USDT","ADA/USDT","AVAX/USDT","DOGE/USDT","DOT/USDT","LINK/USDT","LTC/USDT","BCH/USDT","XLM/USDT","ETC/USDT","TRX/USDT"]
ALTS = ["PEPE/USDT","WIF/USDT","BONK/USDT","PENGU/USDT","POPCAT/USDT","FLOKI/USDT","SHIB/USDT","NEAR/USDT","ARB/USDT","OP/USDT","APT/USDT","SUI/USDT","SEI/USDT","TIA/USDT","W/USDT","ENA/USDT","RENDER/USDT","FET/USDT","INJ/USDT","ONDO/USDT","ASTER/USDT","BRETT/USDT","MOG/USDT","MEW/USDT","BOME/USDT","PYTH/USDT","JUP/USDT","STRK/USDT","DYM/USDT","ALT/USDT","MANTA/USDT","XAI/USDT","JTO/USDT","PENDLE/USDT","AAVE/USDT","UNI/USDT","MATIC/USDT","FIL/USDT","STX/USDT","RNDR/USDT"]
ALL_COINS = MAJORS + ALTS

def get_btc_dominance():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10).json()
        return r['data']['market_cap_percentage']['btc']
    except:
        return 58.5

def calc_mtf_score(symbol):
    try:
        scores = []
        # Multi-Timeframe: 1h, 4h, 1d
        for tf in ['1h','4h','1d']:
            ohlcv = BINANCE.fetch_ohlcv(symbol, tf, limit=100)
            df = pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v'])
            close = df['c']
            
            # EMA Trend
            ema20 = close.ewm(span=20).mean().iloc[-1]
            ema50 = close.ewm(span=50).mean().iloc[-1]
            price = close.iloc[-1]
            
            # RSI
            delta = close.diff()
            gain = delta.where(delta>0,0).ewm(alpha=1/14).mean()
            loss = -delta.where(delta<0,0).ewm(alpha=1/14).mean()
            rs = gain/loss
            rsi = 100 - (100/(1+rs))
            rsi_val = rsi.iloc[-1]
            
            tf_score = 0
            if price > ema20 > ema50: tf_score += 35  # Uptrend
            elif price < ema20 < ema50: tf_score += 5  # Downtrend for short
            else: tf_score += 15
            
            if 55 < rsi_val < 75: tf_score += 25
            elif 45 < rsi_val < 55: tf_score += 15
            elif rsi_val > 75: tf_score += 10
            
            # Volume spike
            vol_ma = df['v'].rolling(20).mean().iloc[-1]
            if df['v'].iloc[-1] > vol_ma*1.5: tf_score += 15
            
            scores.append(min(tf_score, 35))
        
        total = sum(scores) # max 105
        # Add BTC correlation bonus
        if total > 70: total += 5
        
        return min(int(total), 95), price, ema20, rsi_val
    except Exception as e:
        # print(f"{symbol} err {e}")
        return 0, 0, 0, 50

def get_leverage(score, is_major, is_long):
    if not is_long: return 1  # short safer
    if score >= 90: return 10 if is_major else 5
    if score >= 85: return 7 if is_major else 4
    if score >= 80: return 5 if is_major else 3
    return 0

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print(f"TELEGRAM MOCK: {msg}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    print("Telegram sent")

# --- MAIN ---
btc_d = get_btc_dominance()
is_altseason = btc_d < 52
mode = "ALT SEASON 🚀" if is_altseason else "NORMAL"
print(f"BTC.D {btc_d:.1f}% -> {mode}")

stage1_count = len(ALL_COINS)
candidates = []

for symbol in ALL_COINS:
    score, price, ema20, rsi = calc_mtf_score(symbol)
    is_major = symbol in MAJORS
    is_alt = not is_major
    
    if score < 70: continue
    
    # ALT SEASON RULE: No Alt Shorts
    is_long = price > ema20
    if is_altseason and is_alt and not is_long:
        continue
    
    if score >= 80:
        lev = get_leverage(score, is_major, is_long)
        if lev == 0: continue
        candidates.append({
            "symbol": symbol, "score": score, "price": price, "rsi": rsi,
            "is_major": is_major, "is_long": is_long, "lev": lev
        })
    time.sleep(0.2) # rate limit

# Sort by score
candidates = sorted(candidates, key=lambda x: x['score'], reverse=True)

if not candidates:
    msg = f"Bot Lively [NORMAL V2 FAST 55 COINS]\nStage1: {stage1_count} coins (Major {len(MAJORS)} + Alt {len(ALTS)}) | Stage2: 0 candidates\nNo 80+ MTF signal | BTC.D {btc_d:.1f}%"
    send_telegram(msg)
else:
    for c in candidates[:3]: # Top 3 only to avoid spam
        side = "🟢 LONG" if c['is_long'] else "🔴 SHORT"
        coin_type = "MAJOR" if c['is_major'] else "ALT"
        tp = "5/10/20%" if is_altseason else "3/7/12%"
        sl = "5%" if is_altseason else "3%"
        
        msg = f"""{side} {c['score']}% MTF | {coin_type} | {mode} | BTC.D {btc_d:.1f}%
Coin: {c['symbol']}
Price: {c['price']:.4f}
RSI: {c['rsi']:.1f}
Leverage: {c['lev']}x Isolated
TP: {tp} | SL: {sl}
"""
        send_telegram(msg)
        time.sleep(1)

print(f"Scan complete - {len(candidates)} signals")
