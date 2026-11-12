import ccxt, time, requests, os
print("STARTING BOT...", flush=True)
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
CHANNEL_ID = os.getenv("CHANNEL_ID") or os.getenv("TELEGRAM_BROADCAST_ID") or TELEGRAM_CHAT_ID
exchange = ccxt.mexc({'enableRateLimit': True})

MAJOR_ALT = ["BTC/USDT","ETH/USDT","SOL/USDT","AVAX/USDT","LINK/USDT","NEAR/USDT","ARB/USDT","OP/USDT","APT/USDT","SUI/USDT","SEI/USDT","TIA/USDT","ONDO/USDT","RENDER/USDT","FET/USDT","INJ/USDT","STX/USDT"]
QUANT = ["ATOM/USDT","DOT/USDT","MATIC/USDT","LTC/USDT","ETC/USDT","XRP/USDT","ADA/USDT","TRX/USDT","DOGE/USDT","SHIB/USDT","PEPE/USDT","WIF/USDT","BONK/USDT","FLOKI/USDT","BOME/USDT"]
NEW_MANUAL = ["PUMP/USDT","HUMA/USDT","WCT/USDT","KERNEL/USDT","INIT/USDT","SIGN/USDT","PARTI/USDT","SOON/USDT","SXT/USDT"]

def fetch_auto_new():
    print("Fetching auto new listings...", flush=True)
    blacklist_sub = ["USDC","FDUSD","USDE","DAI","XAUT","PAXG","GOLD","WBTC","BNB","BTC","ETH"]
    try:
        tickers = exchange.fetch_tickers()
        candidates = []
        existing = set(MAJOR_ALT+QUANT+NEW_MANUAL)
        for sym, t in tickers.items():
            if not sym.endswith("/USDT"): continue
            if sym in existing: continue
            if any(b in sym for b in blacklist_sub): continue
            if any(x in sym for x in ["3L","3S","5L","5S"]): continue
            qv = t.get('quoteVolume') or 0
            if qv < 3000000 or qv > 60000000: continue
            candidates.append((sym, qv))
        candidates.sort(key=lambda x: x[1], reverse=True)
        res = [s for s,_ in candidates[:20]]
        print(f"AUTO NEW FOUND: {res}", flush=True)
        return res
    except Exception as e:
        print(f"Auto fail {e}", flush=True)
        return []

def get_ohlcv(s,tf,l=100):
    try: return exchange.fetch_ohlcv(s,tf,limit=l)
    except: return None
def calc_ema(c,p):
    if len(c)<p: return None
    k=2/(p+1); e=sum(c[:p])/p
    for x in c[p:]: e=x*k+e*(1-k)
    return e
def calc_rsi(c,p=14):
    if len(c)<p+1: return 50
    g=l=0
    for i in range(1,p+1):
        d=c[-i]-c[-i-1]
        if d>0: g+=d
        else: l+=-d
    if l==0: return 70
    return 100-(100/(1+g/l))
def calc_adx(o,p=14):
    if len(o)<p+5: return 15
    highs=[x[2] for x in o]; lows=[x[3] for x in o]; closes=[x[4] for x in o]
    tr_sum=dm_p=dm_m=0
    for i in range(1,p+1):
        tr=max(highs[-i]-lows[-i], abs(highs[-i]-closes[-i-1]), abs(lows[-i]-closes[-i-1]))
        up=highs[-i]-highs[-i-1]; down=lows[-i-1]-lows[-i]
        dm_p+= up if up>down and up>0 else 0; dm_m+= down if down>up and down>0 else 0; tr_sum+=tr
    if tr_sum==0: return 15
    di_p=dm_p/tr_sum*100; di_m=dm_m/tr_sum*100
    if di_p+di_m==0: return 15
    return abs(di_p-di_m)/(di_p+di_m)*100
def get_trend(o):
    if not o or len(o)<30: return "NEUTRAL"
    c=[x[4] for x in o]; e20=calc_ema(c,20); e50=calc_ema(c,50)
    if not e20 or not e50: return "NEUTRAL"
    if c[-1]>e20>e50: return "BULL"
    if c[-1]<e20<e50: return "BEAR"
    return "NEUTRAL"
def get_btc_status():
    return get_trend(get_ohlcv("BTC/USDT","4h",50))
def send_telegram(msg):
    try:
        for cid in set([x for x in [TELEGRAM_CHAT_ID,CHANNEL_ID] if x]):
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id":cid,"text":msg,"parse_mode":"Markdown"}, timeout=10)
    except Exception as e: print(f"TG fail {e}", flush=True)

def score_coin(sym, btc_status):
    o5=get_ohlcv(sym,"5m",100); o15=get_ohlcv(sym,"15m",100); o30=get_ohlcv(sym,"30m",100); o4h=get_ohlcv(sym,"4h",100)
    if not all([o5,o15,o30,o4h]): return None, "NO_DATA"
    closes=[x[4] for x in o5]; vols=[x[5] for x in o5]; price=closes[-1]
    t5=get_trend(o5); t15=get_trend(o15); t30=get_trend(o30); t4h=get_trend(o4h)
    if not (t5==t15==t30==t4h): return None, f"TF_MISMATCH {t5}/{t15}/{t30}/{t4h}"
    direction=t5
    adx_needed=25 if (btc_status=="BEAR" and direction=="BULL") else 20
    adx=calc_adx(o5,14)
    if adx<adx_needed: return None, f"ADX_LOW {adx:.1f}<{adx_needed}"
    rsi=calc_rsi(closes,14)
    if direction=="BULL" and rsi>78: return None, f"RSI_HIGH {rsi:.1f}"
    if direction=="BEAR" and rsi<28: return None, f"RSI_LOW {rsi:.1f}"
    avg_vol=sum(vols[-21:-1])/20 if len(vols)>21 else 1
    vol_ratio=vols[-1]/avg_vol if avg_vol>0 else 0
    if vol_ratio<1.2: return None, f"VOL_LOW {vol_ratio:.2f}"
    e20=calc_ema(closes,20)
    if not e20: return None, "NO_EMA"
    dist=abs(price-e20)/e20*100
    if dist>0.8: return None, f"PULLBACK_FAR {dist:.2f}%"
    score=0; score+=min(adx*2,50); score+=20 if vol_ratio>=1.5 else 10; score+=20 if dist<=0.4 else 10; score+=10 if (50<=rsi<=68 if direction=="BULL" else 35<=rsi<=65) else 0
    if score<80: return None, f"SCORE_LOW {score}"
    atr=(max(closes[-14:])-min(closes[-14:]))/price*100 if closes else 1
    sl_pct=max(atr*1.2,1.5); tp1_pct=max(atr*1.5,2.0); tp2_pct=max(atr*3,4.0)
    if direction=="BULL": sl=price*(1-sl_pct/100); tp1=price*(1+tp1_pct/100); tp2=price*(1+tp2_pct/100)
    else: sl=price*(1+sl_pct/100); tp1=price*(1-tp1_pct/100); tp2=price*(1-tp2_pct/100)
    lev=15 if score>=95 else 10 if score>=90 else 5
    return {"symbol":sym,"direction":"LONG" if direction=="BULL" else "SHORT","price":price,"score":score,"adx":adx,"rsi":rsi,"vol_ratio":vol_ratio,"dist":dist,"btc":btc_status,"t":f"{t5}/{t15}/{t30}/{t4h}","sl":sl,"tp1":tp1,"tp2":tp2,"lev":lev}, "OK"

def run():
    AUTO_NEW=fetch_auto_new()
    ALL=MAJOR_ALT+QUANT+NEW_MANUAL+AUTO_NEW
    print(f"MANUAL NEW: {len(NEW_MANUAL)} | AUTO NEW: {len(AUTO_NEW)} | TOTAL: {len(ALL)}", flush=True)
    while True:
        btc_status=get_btc_status()
        checked=sent=0
        for sym in ALL:
            checked+=1
            result, reason=score_coin(sym, btc_status)
            if result:
                sent+=1
                msg=f"""*{result['symbol']} {result['direction']}*
Score: {result['score']} | Lev: {result['lev']}x
BTC: {result['btc']} | Trend: {result['t']}
ADX: {result['adx']:.1f} RSI: {result['rsi']:.1f} Vol: {result['vol_ratio']:.2f}x Dist: {result['dist']:.2f}%
Entry: {result['price']:.6f}
SL: {result['sl']:.6f}
TP1: {result['tp1']:.6f}
TP2: {result['tp2']:.6f}
"""
                send_telegram(msg)
                print(f"SENT {sym} {result['direction']} Score {result['score']}", flush=True)
            else:
                if sym=="BTC/USDT": print(f"BTC REJECT: {reason}", flush=True)
            time.sleep(0.3)
        print(f"FINISH Checked:{checked} Sent:{sent} | BTC:{btc_status} | AUTO NEW:{AUTO_NEW}", flush=True)
        time.sleep(300)

if __name__=="__main__":
    run()
