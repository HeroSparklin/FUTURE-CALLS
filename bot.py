import ccxt
import time
import requests
import os

# FIXED TO MATCH YOUR bot.yml FROM SCREENSHOT
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID") or os.getenv("TELEGRAM_BROADCAST_ID") or TELEGRAM_CHAT_ID

MEXC_API_KEY = ""
MEXC_SECRET = ""

exchange = ccxt.mexc({'apiKey': MEXC_API_KEY, 'secret': MEXC_SECRET, 'enableRateLimit': True})

MAJOR_ALT = ["BTC/USDT","ETH/USDT","SOL/USDT","AVAX/USDT","LINK/USDT","NEAR/USDT","ARB/USDT","OP/USDT","APT/USDT","SUI/USDT","SEI/USDT","TIA/USDT","ONDO/USDT","RENDER/USDT","FET/USDT","INJ/USDT","STX/USDT"]
QUANT = ["ATOM/USDT","DOT/USDT","MATIC/USDT","LTC/USDT","ETC/USDT","XRP/USDT","ADA/USDT","TRX/USDT","DOGE/USDT","SHIB/USDT","PEPE/USDT","WIF/USDT","BONK/USDT","FLOKI/USDT","BOME/USDT"]
NEW_MANUAL = ["PUMP/USDT","HUMA/USDT","WCT/USDT","KERNEL/USDT","INIT/USDT","SIGN/USDT","PARTI/USDT","SOON/USDT","SXT/USDT"]

def fetch_auto_new_symbols(exchange, existing_symbols, min_vol_usd=5000000, max_new=20):
    try:
        tickers = exchange.fetch_tickers()
        auto_new = []
        existing_set = set(existing_symbols)
        for symbol, ticker in tickers.items():
            if not symbol.endswith('/USDT'): continue
            if '/USDT:' in symbol: continue
            if symbol in existing_set: continue
            qv = ticker.get('quoteVolume') or 0
            if qv < min_vol_usd: continue
            if not ticker.get('last'): continue
            if '3L' in symbol or '3S' in symbol: continue
            auto_new.append((symbol, qv))
        auto_new.sort(key=lambda x: x[1], reverse=True)
        return [s for s,_ in auto_new[:max_new]]
    except Exception as e:
        print(f"Auto NEW fetch fail: {e}")
        return []

print("Fetching auto new listings...")
AUTO_NEW = fetch_auto_new_symbols(exchange, MAJOR_ALT + QUANT + NEW_MANUAL)
ALL_SYMBOLS = MAJOR_ALT + QUANT + NEW_MANUAL + AUTO_NEW
print(f"MANUAL NEW: {len(NEW_MANUAL)} | AUTO NEW: {len(AUTO_NEW)} {AUTO_NEW} | TOTAL: {len(ALL_SYMBOLS)}")

def get_ohlcv(symbol, timeframe, limit=100):
    try: return exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    except: return None
def calc_ema(closes, period):
    if len(closes) < period: return None
    k = 2/(period+1)
    ema = sum(closes[:period])/period
    for c in closes[period:]: ema = c*k + ema*(1-k)
    return ema
def calc_rsi(closes, period=14):
    if len(closes) < period+1: return 50
    gains, losses = 0,0
    for i in range(1, period+1):
        diff = closes[-i] - closes[-i-1]
        if diff>0: gains+=diff
        else: losses+= -diff
    if losses==0: return 70
    rs = gains/losses
    return 100 - (100/(1+rs))
def calc_adx(ohlcv, period=14):
    if len(ohlcv) < period+5: return 15
    highs = [x[2] for x in ohlcv]; lows = [x[3] for x in ohlcv]; closes = [x[4] for x in ohlcv]
    tr_sum, dm_plus_sum, dm_minus_sum = 0,0,0
    for i in range(1, period+1):
        tr = max(highs[-i]-lows[-i], abs(highs[-i]-closes[-i-1]), abs(lows[-i]-closes[-i-1]))
        up = highs[-i]-highs[-i-1]; down = lows[-i-1]-lows[-i]
        dm_plus = up if up>down and up>0 else 0; dm_minus = down if down>up and down>0 else 0
        tr_sum+=tr; dm_plus_sum+=dm_plus; dm_minus_sum+=dm_minus
    if tr_sum==0: return 15
    di_plus = dm_plus_sum/tr_sum*100; di_minus = dm_minus_sum/tr_sum*100
    if (di_plus+di_minus)==0: return 15
    return abs(di_plus-di_minus)/(di_plus+di_minus)*100
def get_trend(ohlcv):
    if not ohlcv or len(ohlcv)<30: return "NEUTRAL"
    closes = [x[4] for x in ohlcv]
    ema20 = calc_ema(closes,20); ema50 = calc_ema(closes,50)
    if not ema20 or not ema50: return "NEUTRAL"
    if closes[-1] > ema20 > ema50: return "BULL"
    if closes[-1] < ema20 < ema50: return "BEAR"
    return "NEUTRAL"
def get_btc_status():
    ohlcv_4h = get_ohlcv("BTC/USDT","4h",50)
    return get_trend(ohlcv_4h)
def send_telegram(msg):
    try:
        targets = [TELEGRAM_CHAT_ID, CHANNEL_ID]
        for cid in set([x for x in targets if x]):
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": cid, "text": msg, "parse_mode": "Markdown"})
    except Exception as e: print(f"TG fail {e}")

def score_coin(symbol):
    ohlcv_5m = get_ohlcv(symbol,"5m",100); ohlcv_15m = get_ohlcv(symbol,"15m",100); ohlcv_30m = get_ohlcv(symbol,"30m",100); ohlcv_4h = get_ohlcv(symbol,"4h",100)
    if not all([ohlcv_5m, ohlcv_15m, ohlcv_30m, ohlcv_4h]): return None, "NO_DATA"
    closes_5m = [x[4] for x in ohlcv_5m]; vols_5m = [x[5] for x in ohlcv_5m]; price = closes_5m[-1]
    t5 = get_trend(ohlcv_5m); t15 = get_trend(ohlcv_15m); t30 = get_trend(ohlcv_30m); t4h = get_trend(ohlcv_4h)
    if not (t5==t15==t30==t4h): return None, f"TF_MISMATCH {t5}/{t15}/{t30}/{t4h}"
    direction = t5; btc_status = get_btc_status()
    adx_needed = 25 if (btc_status=="BEAR" and direction=="BULL") else 20
    adx = calc_adx(ohlcv_5m,14)
    if adx < adx_needed: return None, f"ADX_LOW {adx:.1f}<{adx_needed}"
    rsi = calc_rsi(closes_5m,14)
    if direction=="BULL" and rsi>78: return None, f"RSI_HIGH {rsi:.1f}"
    if direction=="BEAR" and rsi<28: return None, f"RSI_LOW {rsi:.1f}"
    avg_vol = sum(vols_5m[-21:-1])/20 if len(vols_5m)>21 else 1
    vol_ratio = vols_5m[-1]/avg_vol if avg_vol>0 else 0
    if vol_ratio < 1.2: return None, f"VOL_LOW {vol_ratio:.2f}"
    try:
        ticker = exchange.fetch_ticker(symbol)
        spread = (ticker['ask']-ticker['bid'])/ticker['last']*100 if ticker['last'] else 0
        if spread>0.5: return None, f"SPREAD_HIGH {spread:.2f}%"
    except: pass
    ema20 = calc_ema(closes_5m,20)
    if not ema20: return None, "NO_EMA"
    dist = abs(price-ema20)/ema20*100
    if dist>0.8: return None, f"PULLBACK_FAR {dist:.2f}%"
    score = 0; score+= min(adx*2,50); score+= 20 if vol_ratio>=1.5 else 10; score+= 20 if dist<=0.4 else 10
    if direction=="BULL": score+= 10 if 50<=rsi<=68 else 0
    else: score+= 10 if 35<=rsi<=65 else 0
    if score<80: return None, f"SCORE_LOW {score}"
    atr_pct = (max(closes_5m[-14:]) - min(closes_5m[-14:]))/price*100 if closes_5m else 1
    sl_pct = max(atr_pct*1.2,1.5); tp1_pct = max(atr_pct*1.5,2.0); tp2_pct = max(atr_pct*3,4.0)
    if direction=="BULL": sl=price*(1-sl_pct/100); tp1=price*(1+tp1_pct/100); tp2=price*(1+tp2_pct/100)
    else: sl=price*(1+sl_pct/100); tp1=price*(1-tp1_pct/100); tp2=price*(1-tp2_pct/100)
    lev = 15 if score>=95 else 10 if score>=90 else 5
    return {"symbol":symbol,"direction":"LONG" if direction=="BULL" else "SHORT","price":price,"score":score,"adx":adx,"rsi":rsi,"vol_ratio":vol_ratio,"dist":dist,"btc":btc_status,"t":f"{t5}/{t15}/{t30}/{t4h}","sl":sl,"tp1":tp1,"tp2":tp2,"lev":lev}, "OK"

def run():
    while True:
        btc_status = get_btc_status()
        global AUTO_NEW, ALL_SYMBOLS
        AUTO_NEW = fetch_auto_new_symbols(exchange, MAJOR_ALT+QUANT+NEW_MANUAL)
        ALL_SYMBOLS = MAJOR_ALT+QUANT+NEW_MANUAL+AUTO_NEW
        checked=0; sent=0
        for symbol in ALL_SYMBOLS:
            checked+=1
            result, reason = score_coin(symbol)
            if result:
                sent+=1
                msg = f"""*{result['symbol']} {result['direction']}*
Score: {result['score']} | Lev: {result['lev']}x
BTC: {result['btc']} | Trend: {result['t']}
ADX: {result['adx']:.1f} RSI: {result['rsi']:.1f} Vol: {result['vol_ratio']:.2f}x Dist: {result['dist']:.2f}%
Entry: {result['price']:.4f}
SL: {result['sl']:.4f}
TP1: {result['tp1']:.4f}
TP2: {result['tp2']:.4f}
"""
                send_telegram(msg)
                print(f"SENT {symbol} {result['direction']} Score {result['score']}")
            else:
                if symbol=="BTC/USDT": print(f"BTC REJECT: {reason}")
            time.sleep(0.3)
        print(f"FINISH Checked:{checked} Sent:{sent} | BTC:{btc_status} | AUTO NEW:{AUTO_NEW}")
        time.sleep(300)

if __name__=="__main__":
    run()
