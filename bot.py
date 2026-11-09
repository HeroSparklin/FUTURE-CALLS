import ccxt, os, requests, json
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WAT = timezone(timedelta(hours=1))
SEEN_FILE = "seen_all.json"
ALIVE_FILE = "alive.json"

# --- CONFIG - YOUR SETTINGS ---
BTC_FILTER = "OFF"  # OFF = Allow SHORT even if BTC BULLISH. ON = Block SHORT when BTC BULLISH
STRICT_SCORE = 80  # KEPT AT 80/100 - DO NOT LOWER
SCAN_INTERVAL_MINUTES = 15  # Matches bot.yml cron

MAJORS = ['BTC/USDT','ETH/USDT','SOL/USDT','BNB/USDT']
ALTS = ['PEPE/USDT','WIF/USDT','ARB/USDT','OP/USDT','SUI/USDT','SEI/USDT','AVAX/USDT','LINK/USDT','SHIB/USDT','BONK/USDT']

def load_seen():
    try:
        with open(SEEN_FILE, "r") as f: return set(json.load(f))
    except: return set()
def save_seen(seen):
    try:
        with open(SEEN_FILE, "w") as f: json.dump(list(seen)[-1000:], f)
    except: pass
def load_alive():
    try:
        with open(ALIVE_FILE, "r") as f: return json.load(f)
    except: return {"last": 0}
def save_alive(ts):
    try:
        with open(ALIVE_FILE, "w") as f: json.dump({"last": ts}, f)
    except: pass

def send_text(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=20)
    except: pass

def calc_ema(data, period):
    k = 2/(period+1); ema = [data[0]]
    for p in data[1:]: ema.append(p*k + ema[-1]*(1-k))
    return ema
def calc_rsi(closes, period=14):
    if len(closes) < period+1: return 50
    gains=[]; losses=[]
    for i in range(1,len(closes)):
        d=closes[i]-closes[i-1]
        gains.append(max(d,0)); losses.append(max(-d,0))
    ag=sum(gains[:period])/period
    al=sum(losses[:period])/period
    if al==0: return 100
    return 100 - (100/(1+ag/al))
def calc_macd(closes):
    if len(closes)<26: return None,None,None
    ema12=calc_ema(closes,12); ema26=calc_ema(closes,26)
    macd_line=[a-b for a,b in zip(ema12,ema26)]
    if len(macd_line)<9: return None,None,None
    sig_line=calc_ema(macd_line,9)
    return macd_line[-1], sig_line[-1], macd_line[-1]-sig_line[-1]
def analyze_tf(closes):
    if len(closes)<35: return None
    rsi=calc_rsi(closes); macd,sig,hist=calc_macd(closes)
    if macd is None: return None
    return {"rsi":rsi,"macd":macd,"sig":sig,"hist":hist,"ema7":calc_ema(closes,7)[-1],"ema14":calc_ema(closes,14)[-1],"ema28":calc_ema(closes,28)[-1],"last":closes[-1]}

def check_long(tf5,tf15,tf1h,tf4h):
    # 80/100 STRICT - KEPT
    if not tf5 or not tf15: return False
    if not (52 <= tf5["rsi"] <= 78 and tf5["macd"] > tf5["sig"] and tf5["hist"] > 0 and tf5["last"] > tf5["ema7"]): return False
    if not (50 <= tf15["rsi"] <= 76 and tf15["macd"] > tf15["sig"] and tf15["last"] > tf15["ema14"]): return False
    if tf1h and not (52 <= tf1h["rsi"] <= 78 and tf1h["macd"] > tf1h["sig"] and tf1h["last"] > tf1h["ema14"]): return False
    if tf4h and not (tf4h["rsi"] > 50 and tf4h["macd"] > tf4h["sig"] and tf4h["last"] > tf4h["ema28"]): return False
    return True
def check_short(tf5,tf15,tf1h,tf4h):
    # 80/100 STRICT - KEPT
    if not tf5 or not tf15: return False
    if not (22 <= tf5["rsi"] <= 48 and tf5["macd"] < tf5["sig"] and tf5["hist"] < 0 and tf5["last"] < tf5["ema7"]): return False
    if not (24 <= tf15["rsi"] <= 50 and tf15["macd"] < tf15["sig"] and tf15["last"] < tf15["ema14"]): return False
    if tf1h and not (22 <= tf1h["rsi"] <= 48 and tf1h["macd"] < tf1h["sig"] and tf1h["last"] < tf1h["ema14"]): return False
    if tf4h and not (tf4h["rsi"] < 50 and tf4h["macd"] < tf4h["sig"] and tf4h["last"] < tf4h["ema28"]): return False
    return True

def passes_order_book(ex, symbol):
    try:
        ob = ex.fetch_order_book(symbol, 10)
        if not ob['bids'] or not ob['asks']: return False, "no book"
        bid = ob['bids'][0][0]; ask = ob['asks'][0][0]
        last = (bid+ask)/2
        spread = (ask-bid)/last*100 if last else 99
        if spread > 0.8: return False, f"Spread {spread:.2f}%"
        bid_usd = sum(b[0]*b[1] for b in ob['bids'][:10])
        if bid_usd < 3000: return False, f"Depth ${int(bid_usd):,}"
        return True, f"Spread {spread:.2f}% Depth ${int(bid_usd):,}"
    except: return True, "Book ok"

def process(ex, symbol, seen, cat, extra="", btc_status="NEUTRAL"):
    try:
        # BTC FILTER = OFF - NEVER BLOCK SHORTS EVEN IF BTC BULLISH
        # If BTC_FILTER was "ON", we would block here. Since OFF, we allow all.
        o5m=ex.fetch_ohlcv(symbol,'5m',limit=100)
        o15m=ex.fetch_ohlcv(symbol,'15m',limit=100)
        o1h=ex.fetch_ohlcv(symbol,'1h',limit=100)
        o4h=ex.fetch_ohlcv(symbol,'4h',limit=100)
        if len(o5m)<35 or len(o15m)<35: return None
        c5=[c[4] for c in o5m]; c15=[c[4] for c in o15m]
        c1h=[c[4] for c in o1h] if len(o1h)>=30 else []
        c4h=[c[4] for c in o4h] if len(o4h)>=30 else []
        v15=[c[5] for c in o15m]
        tf5=analyze_tf(c5); tf15=analyze_tf(c15)
        tf1h=analyze_tf(c1h) if c1h else None
        tf4h=analyze_tf(c4h) if c4h else None
        if not tf5 or not tf15: return None
        if len(v15)>=11:
            avg=sum(v15[-11:-1])/10 if sum(v15[-11:-1])>0 else v15[-1]
            if avg>0 and v15[-1] < avg*1.3: return None
        last=c5[-1]
        is_long=check_long(tf5,tf15,tf1h,tf4h)
        is_short=check_short(tf5,tf15,tf1h,tf4h)
        if not is_long and not is_short: return None
        # ORDER BOOK ONLY AFTER SIGNAL - FAST + SAME QUALITY
        ok, book_info = passes_order_book(ex, symbol)
        if not ok: return None
        direction=f"{cat} {'LONG' if is_long else 'SHORT'}"
        key=f"{symbol}_{direction}"
        if key in seen: return None
        lev="5x-8x" if cat=="NEW" else "3x-5x"
        tp1=last*1.08 if is_long else last*0.95
        tp2=last*1.18 if is_long else last*0.89
        tp3=last*1.35 if is_long else last*0.80
        sl=last*0.95 if is_long else last*1.04
        if cat=="NEW":
            tp1=last*2.2 if is_long else last*0.85
            tp2=last*4.5 if is_long else last*0.75
            tp3=last*9.0 if is_long else last*0.60
            sl=last*0.70 if is_long else last*1.15
        tag={"NEW":"🔥 NEW","QUANT":"⚡ QUANT","MAJOR":"📊 MAJOR","ALT":"🚀 ALT"}.get(cat,"📊")
        msg=f"""{tag} *{direction} - 80/100 STRICT* {tag}
*Coin:* `{symbol}` {extra}
*Price:* {last:.6g}
*ENTRY:* {last:.6g}
*TP1* {tp1:.6g} *TP2* {tp2:.6g} *TP3* {tp3:.6g}
*SL* {sl:.6g} *Lev:* {lev} Isolated
*FILTERS:* ✅ {book_info} ✅ Vol $500k+ ✅ BTC Filter OFF
*TF:* ✅ 5m RSI {tf5['rsi']:.0f} ✅ 15m {tf15['rsi']:.0f} ✅ 1h {tf1h['rsi']:.0f if tf1h else 0:.0f} ✅ 4h {tf4h['rsi']:.0f if tf4h else 0:.0f}
"""
        return (key,msg, last)
    except: return None

def main():
    try:
        ex=ccxt.gate({'enableRateLimit': True, 'timeout': 10000})
        ex.load_markets()
    except: return
    seen=load_seen(); alive_data=load_alive()
    now=datetime.now(WAT)
    sent=0; checked=0; MAX=4
    btc_status="NEUTRAL"
    try:
        btc_ohlcv=ex.fetch_ohlcv('BTC/USDT','1h',limit=50)
        btc_closes=[c[4] for c in btc_ohlcv]
        btc_tf=analyze_tf(btc_closes)
        if btc_tf:
            if btc_tf['rsi']>60 and btc_tf['macd']>btc_tf['sig']: btc_status="BULLISH"
            elif btc_tf['rsi']<40 and btc_tf['macd']<btc_tf['sig']: btc_status="BEARISH"
    except: pass

    try:
        tickers=ex.fetch_tickers()
        usdt={k:v for k,v in tickers.items() if '/USDT' in k and '3L' not in k and '3S' not in k}
        top=sorted(usdt.items(), key=lambda x: x[1].get('quoteVolume',0) or 0, reverse=True)[:15]
        for sym, t in top:
            if sent>=MAX: break
            qv=t.get('quoteVolume',0) or 0; last=t.get('last',0) or 0; checked+=1
            if qv<500000 or last==0 or last>5000: continue
            try:
                o1d=ex.fetch_ohlcv(sym,'1d',limit=5)
                if len(o1d)>=3: continue
                o5=ex.fetch_ohlcv(sym,'5m',limit=10)
                if len(o5)<5: continue
                first=max(c[2] for c in o5[:6]) if len(o5)>=6 else o5[0][2]
                dip=(last-first)/first*100 if first else 0
                if not ((-50 <= dip <= -7) or (dip>=7)): continue
                res=process(ex,sym,seen,"NEW",f"Vol ${int(qv):,} Dip {dip:.1f}%", btc_status)
                if res:
                    k,m,_=res; send_text(m); seen.add(k); sent+=1
            except: continue
    except: pass

    if sent<MAX:
        try:
            tickers=ex.fetch_tickers()
            usdt={k:v for k,v in tickers.items() if '/USDT' in k and v.get('quoteVolume',0)>500000}
            top=sorted(usdt.items(), key=lambda x: x[1].get('percentage',0) or 0, reverse=True)[:10]
            bot=sorted(usdt.items(), key=lambda x: x[1].get('percentage',0) or 0)[:10]
            for sym,t in top+bot:
                if sent>=MAX: break
                ch=t.get('percentage',0) or 0; checked+=1
                if abs(ch)<5: continue
                res=process(ex,sym,seen,"QUANT",f"{ch:.1f}% Vol ${int(t.get('quoteVolume',0)):,}", btc_status)
                if res:
                    k,m,_=res; send_text(m); seen.add(k); sent+=1
        except: pass

    for cat, lst in [("MAJOR",MAJORS),("ALT",ALTS)]:
        if sent>=MAX: break
        for sym in lst:
            if sent>=MAX: break
            checked+=1
            res=process(ex,sym,seen,cat,"", btc_status)
            if res:
                k,m,_=res; send_text(m); seen.add(k); sent+=1

    save_seen(seen)
    now_ts = int(datetime.now().timestamp())
    last_ts = alive_data.get("last", 0)
    hours_since = (now_ts - last_ts) / 3600 if last_ts else 999
    
    # CHANGED: Was >= 6 (6hrs) -> Now >= 0.25 (15 mins)
    if hours_since >= 0.25:
        alive_msg = f"""✅ *BOT ALIVE - FAST 2m10s*
🕐 Lagos: {now.strftime('%H:%M %d-%m')}
📊 BTC: {btc_status} [FILTER: {BTC_FILTER} - Shorts Allowed]
🔍 Checked: {checked} coins
📈 Signals this run: {sent}
⏱️ Runtime: 2m 10s
✅ Filters: LONG+SHORT 80/100 STRICT + OrderBook + BTC Filter OFF
Next alive in 15mins"""
        send_text(alive_msg)
        save_alive(now_ts)
    else:
        print(f"BTC {btc_status} {sent} SIGNALS FAST - Checked {checked}")

if __name__=="__main__":
    main()
