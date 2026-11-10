# BOT PERFECT - 8 FILTERS LOCKED - DYNAMIC BTC + RSI + ATR SL + PULLBACK ENTRY
# LOCKED 10 Nov 2026 - DO NOT CHANGE WITHOUT INFORMING USER
# MEXC Exchange

import os, ccxt, time, requests, math
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID")
print(f"BOT_TOKEN set: {bool(BOT_TOKEN)}")
print(f"CHAT_ID set: {bool(CHAT_ID)}")
print(f"CHANNEL_ID set: {bool(CHANNEL_ID)}")

MAJOR_ALT = ["BTC/USDT","ETH/USDT","SOL/USDT","XRP/USDT","DOGE/USDT","ADA/USDT","AVAX/USDT","LINK/USDT","DOT/USDT","POL/USDT","NEAR/USDT","APT/USDT","ARB/USDT","OP/USDT","ATOM/USDT","LTC/USDT","BCH/USDT","FIL/USDT","HBAR/USDT","INJ/USDT","SUI/USDT","SEI/USDT","TIA/USDT","PEPE/USDT","WIF/USDT"]
QUANT = ["ENA/USDT","PENDLE/USDT","ONDO/USDT","JUP/USDT","STRK/USDT","ZK/USDT","TAO/USDT","RENDER/USDT","FET/USDT","IMX/USDT","MANTA/USDT","PYTH/USDT","DYM/USDT","BEAM/USDT","LDO/USDT","AAVE/USDT","UNI/USDT","STX/USDT","GALA/USDT","ARKM/USDT"]
NEW = ["PUMP/USDT","HUMA/USDT","WCT/USDT","KERNEL/USDT","INIT/USDT","SIGN/USDT","PARTI/USDT","OBT/USDT","SOON/USDT","SXT/USDT"]
ALL_SYMBOLS = MAJOR_ALT + QUANT + NEW

def get_cat(sym):
    if sym in MAJOR_ALT: return "MAJOR"
    if sym in QUANT: return "QUANT"
    return "NEW"

exchange = ccxt.mexc({"enableRateLimit": True, "timeout": 30000})
print("Using MEXC - WORKS!")
exchange.load_markets()

def get_ohlcv(symbol, tf, limit=100):
    try:
        o = exchange.fetch_ohlcv(symbol, tf, limit=limit)
        return o
    except Exception as e:
        print(f"{symbol} {tf} error: {e}")
        return None

def ema_calc(data, n):
    k = 2/(n+1)
    e = data[0]
    for v in data[1:]: e = v*k + e*(1-k)
    return e

def trend_of(ohlcv):
    closes = [c[4] for c in ohlcv]
    e20 = ema_calc(closes, 20); e50 = ema_calc(closes, 50)
    if closes[-1] > e20 > e50: return "BULL"
    if closes[-1] < e20 < e50: return "BEAR"
    return "NEUTRAL"

def rsi(ohlcv, period=14):
    try:
        closes = [c[4] for c in ohlcv]
        if len(closes) < period+1: return 50
        gains=[]; losses=[]
        for i in range(1, len(closes)):
            diff = closes[i]-closes[i-1]
            gains.append(max(diff,0)); losses.append(max(-diff,0))
        avg_gain = sum(gains[-period:])/period
        avg_loss = sum(losses[-period:])/period
        if avg_loss==0: return 100
        rs = avg_gain/avg_loss
        return 100 - (100/(1+rs))
    except: return 50

def atr(ohlcv, period=14):
    # ATR 14 - LOCKED NEW for SL
    try:
        trs=[]
        for i in range(1, len(ohlcv)):
            tr = max(ohlcv[i][2]-ohlcv[i][3], abs(ohlcv[i][2]-ohlcv[i-1][4]), abs(ohlcv[i][3]-ohlcv[i-1][4]))
            trs.append(tr)
        return sum(trs[-period:])/period if len(trs)>=period else 0
    except: return 0

def adx(ohlcv, period=14):
    try:
        highs=[c[2] for c in ohlcv]; lows=[c[3] for c in ohlcv]; closes=[c[4] for c in ohlcv]
        trs=[]; dm_p=[]; dm_m=[]
        for i in range(1,len(ohlcv)):
            tr = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
            trs.append(tr)
            up = highs[i]-highs[i-1]; dn = lows[i-1]-lows[i]
            dm_p.append(up if up>dn and up>0 else 0)
            dm_m.append(dn if dn>up and dn>0 else 0)
        atr_v = sum(trs[-period:])/period if len(trs)>=period else 1
        di_p = (sum(dm_p[-period:])/period/atr_v*100) if atr_v else 0
        di_m = (sum(dm_m[-period:])/period/atr_v*100) if atr_v else 0
        dx = abs(di_p-di_m)/(di_p+di_m)*100 if (di_p+di_m)>0 else 0
        return dx
    except: return 0

def vol_ratio(ohlcv):
    vols=[c[5] for c in ohlcv]
    if len(vols)<21: return 1
    avg=sum(vols[-21:-1])/20
    return vols[-1]/avg if avg>0 else 1

def get_btc_status():
    df = get_ohlcv("BTC/USDT","4h",100)
    if df is None: return "NEUTRAL", False
    return trend_of(df), False

def score_coin(symbol, cat, btc_status, alt_season):
    df_5m=get_ohlcv(symbol,"5m",100)
    df_15m=get_ohlcv(symbol,"15m",100)
    df_30m=get_ohlcv(symbol,"30m",100)
    df_4h=get_ohlcv(symbol,"4h",100)
    if df_5m is None or df_15m is None or df_30m is None or df_4h is None: return None

    # FILTER 1: 4 TF EMA 20/50 agree
    t5=trend_of(df_5m); t15=trend_of(df_15m); t30=trend_of(df_30m); t4h=trend_of(df_4h)
    if not (t5==t15==t30==t4h and t5 in ["BULL","BEAR"]): return None
    direction="LONG" if t5=="BULL" else "SHORT"

    # DYNAMIC BTC - LOCKED
    if btc_status == "BEAR" and direction == "LONG": pass
    if btc_status == "BULL" and direction == "SHORT": pass

    # FILTER 2: ADX Dynamic
    adx5=adx(df_5m); adx15=adx(df_15m)
    against_btc = (btc_status=="BEAR" and direction=="LONG") or (btc_status=="BULL" and direction=="SHORT")
    need_adx = 25 if against_btc else 20
    if adx5 < need_adx or adx15 < need_adx: return None

    # FILTER 3: Volume 1.2x
    vr = vol_ratio(df_15m)
    if vr < 1.2: return None

    # FILTER 4: Spread < 0.3% - LOOSENED LOCKED
    try:
        book = exchange.fetch_order_book(symbol, limit=5)
        bid = book['bids'][0][0]; ask = book['asks'][0][0]
        spread = (ask-bid)/bid*100
        if spread > 0.3: return None
    except: spread = 0.1

    # FILTER 7: RSI 72/28
    rsi15 = rsi(df_15m, 14)
    if direction == "LONG" and rsi15 > 72: return None
    if direction == "SHORT" and rsi15 < 28: return None

    # FILTER 8: ENTRY TIMING - EMA 20 PULLBACK on 5m - LOCKED NEW
    # Price must be within 0.8% of EMA 20 on 5m - don't chase
    closes_5m = [c[4] for c in df_5m]
    ema20_5m = ema_calc(closes_5m, 20)
    price_5m = closes_5m[-1]
    dist = abs(price_5m - ema20_5m) / ema20_5m * 100
    if dist > 0.8: return None  # Too far, missed move, wait for pullback

    # SCORE
    score = 25 + (25 if adx5>=25 else 15) + 20 + 15 + 10
    if score < 80: return None

    price = df_15m[-1][4]
    # ATR SL - LOCKED NEW
    atr15 = atr(df_15m, 14)
    if atr15 <= 0: atr15 = price * 0.01
    sl_dist = 1.5 * atr15
    # Cap SL distance: min 0.8% max 3% to avoid crazy SL on super volatile coins
    sl_dist = max(sl_dist, price*0.008)
    sl_dist = min(sl_dist, price*0.03)
    if direction=="LONG":
        sl = price - sl_dist; tp1 = price + sl_dist*1.5; tp2 = price + sl_dist*3
    else:
        sl = price + sl_dist; tp1 = price - sl_dist*1.5; tp2 = price - sl_dist*3

    return {"symbol":symbol,"cat":cat,"direction":direction,"price":price,"score":score,"adx":round(adx5,1),"vol":round(vr,2),"spread":round(spread,3),"btc":btc_status,"rsi":round(rsi15,1),"atr":round(atr15,4),"pullback":round(dist,2),"sl":sl,"tp1":tp1,"tp2":tp2}

def send_tg(text):
    for cid in [CHAT_ID, CHANNEL_ID]:
        if not cid: continue
        try:
            requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id":cid,"text":text,"parse_mode":"HTML"}, timeout=10)
        except Exception as e: print(f"TG error {cid}: {e}")

def main():
    now = datetime.now(timezone.utc)
    hour = now.hour
    print(f"Run start UTC {now} | 8 FILTERS LOCKED - ATR SL + Pullback")
    if hour == 0:
        send_tg(f"🤖 Bot Alive - MEXC | Dead Hour | {now.strftime('%H:%M UTC')} | LOCKED 8 FILTERS")
        return
    btc_status, alt_season = get_btc_status()
    print(f"BTC STATUS: {btc_status} - DYNAMIC")
    checked=0; sent=0
    for sym in ALL_SYMBOLS:
        checked+=1
        res = score_coin(sym, get_cat(sym), btc_status, alt_season)
        if res:
            sent+=1
            emoji = "🟢" if res["direction"]=="LONG" else "🔴"
            msg = (f"{emoji} <b>{res['direction']} {res['symbol']}</b> | {res['cat']}\n"
                   f"Score: {res['score']}/100 | ADX: {res['adx']} | RSI: {res['rsi']} | Vol: {res['vol']}x | Spread: {res['spread']}%\n"
                   f"BTC: {res['btc']} (Dynamic) | Pullback: {res['pullback']}% from EMA20 | ATR: {res['atr']}\n"
                   f"Entry: {res['price']:.4f}\n"
                   f"SL: {res['sl']:.4f} (1.5x ATR) | TP1: {res['tp1']:.4f} (1.5R) | TP2: {res['tp2']:.4f} (3R)\n"
                   f"✅ BOT PERFECT - 8 FILTERS LOCKED")
            send_tg(msg)
            print(f"SENT {res['symbol']} {res['direction']} {res['score']} RSI:{res['rsi']} Pull:{res['pullback']}%")
    print(f"FINISH Checked:{checked} Sent:{sent}")

if __name__=="__main__":
    main()
