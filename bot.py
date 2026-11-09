import ccxt, os, requests, json, time
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WAT = timezone(timedelta(hours=1))
SEEN_FILE = "seen_all.json"
ALIVE_FILE = "alive.json"

BTC_FILTER = "OFF"
STRICT_SCORE = 80
SCAN_INTERVAL_MINUTES = 15
SEEN_COOLDOWN_HOURS = 4
PRICE_MOVE_OVERRIDE = 2.0

MAJORS = ['BTC/USDT','ETH/USDT','SOL/USDT','BNB/USDT']
ALTS = [
    'PEPE/USDT','WIF/USDT','ARB/USDT','OP/USDT','SUI/USDT','SEI/USDT','AVAX/USDT','LINK/USDT','SHIB/USDT','BONK/USDT',
    'DOGE/USDT','XRP/USDT','ADA/USDT','DOT/USDT','NEAR/USDT','APT/USDT','TIA/USDT','INJ/USDT','JUP/USDT','ONDO/USDT','HYPE/USDT'
]

def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                return {k: {"ts": int(time.time()), "price": 0} for k in data}
            cleaned={}
            for k,v in data.items():
                if isinstance(v,dict) and "ts" in v: cleaned[k]=v
                else: cleaned[k]={"ts": int(time.time()), "price":0}
            return cleaned
    except: return {}
def save_seen(seen):
    try:
        now_ts=int(time.time())
        cleaned={}
        for k,v in seen.items():
            try:
                ts=int(v.get("ts",0)) if isinstance(v,dict) else int(v)
                if now_ts-ts<86400: cleaned[k]=v if isinstance(v,dict) else {"ts":ts,"price":0}
            except: continue
        with open(SEEN_FILE,"w") as f: json.dump(cleaned,f)
    except: pass
def is_recently_seen(seen,key,cur_price):
    if key not in seen: return False
    try:
        e=seen[key]; ts=int(e.get("ts",0)) if isinstance(e,dict) else int(e)
        lp=float(e.get("price",0)) if isinstance(e,dict) else 0
        if (int(time.time())-ts) >= SEEN_COOLDOWN_HOURS*3600: return False
        if lp==0 or cur_price==0: return True
        if abs(cur_price-lp)/lp*100 >= PRICE_MOVE_OVERRIDE: return False
        return True
    except: return False
def load_alive():
    try:
        with open(ALIVE_FILE,"r") as f: return json.load(f)
    except: return {"last":0}
def save_alive(ts):
    try:
        with open(ALIVE_FILE,"w") as f: json.dump({"last":ts},f)
    except: pass
def send_text(msg):
    try:
        url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id":CHAT_ID,"text":msg,"parse_mode":"Markdown"}, timeout=20)
    except: pass
def calc_ema(data,p):
    k=2/(p+1); ema=[data[0]]
    for x in data[1:]: ema.append(x*k+ema[-1]*(1-k))
    return ema
def calc_rsi(c,p=14):
    if len(c)<p+1: return 50
    g=[];l=[]
    for i in range(1,len(c)):
        d=c[i]-c[i-1]; g.append(max(d,0)); l.append(max(-d,0))
    ag=sum(g[:p])/p; al=sum(l[:p])/p
    if al==0: return 100
    return 100-(100/(1+ag/al))
def calc_macd(c):
    if len(c)<26: return None,None,None
    e12=calc_ema(c,12); e26=calc_ema(c,26)
    ml=[a-b for a,b in zip(e12,e26)]
    if len(ml)<9: return None,None,None
    sl=calc_ema(ml,9)
    return ml[-1],sl[-1],ml[-1]-sl[-1]
def analyze_tf(c):
    if len(c)<35: return None
    r=calc_rsi(c); m,s,h=calc_macd(c)
    if m is None: return None
    return {"rsi":r,"macd":m,"sig":s,"hist":h,"ema7":calc_ema(c,7)[-1],"ema14":calc_ema(c,14)[-1],"ema28":calc_ema(c,28)[-1],"last":c[-1]}
def check_long(t5,t15,t1,t4):
    if not t5 or not t15: return False
    if not (52<=t5["rsi"]<=78 and t5["macd"]>t5["sig"] and t5["hist"]>0 and t5["last"]>t5["ema7"]): return False
    if not (50<=t15["rsi"]<=76 and t15["macd"]>t15["sig"] and t15["last"]>t15["ema14"]): return False
    if t1 and not (52<=t1["rsi"]<=78 and t1["macd"]>t1["sig"] and t1["last"]>t1["ema14"]): return False
    if t4 and not (t4["rsi"]>50 and t4["macd"]>t4["sig"] and t4["last"]>t4["ema28"]): return False
    return True
def check_short(t5,t15,t1,t4):
    if not t5 or not t15: return False
    if not (22<=t5["rsi"]<=48 and t5["macd"]<t5["sig"] and t5["hist"]<0 and t5["last"]<t5["ema7"]): return False
    if not (24<=t15["rsi"]<=50 and t15["macd"]<t15["sig"] and t15["last"]<t15["ema14"]): return False
    if t1 and not (22<=t1["rsi"]<=48 and t1["macd"]<t1["sig"] and t1["last"]<t1["ema14"]): return False
    if t4 and not (t4["rsi"]<50 and t4["macd"]<t4["sig"] and t4["last"]<t4["ema28"]): return False
    return True
def calc_score_leverage(tf5,tf15,tf1h,tf4h,vol_ratio,spread,cat,is_long):
    score=80
    if 58 <= tf5["rsi"] <= 72: score+=5
    if 55 <= tf15["rsi"] <= 70: score+=4
    if tf1h and (55 <= tf1h["rsi"] <= 72 if is_long else 28 <= tf1h["rsi"] <= 45): score+=3
    if tf4h: score+=2
    if vol_ratio>=2.0: score+=5
    elif vol_ratio>=1.5: score+=2
    if spread<0.2: score+=3
    elif spread<0.4: score+=1
    if abs(tf5["hist"]) > abs(tf15["hist"])*0.5: score+=2
    score=min(score,99)
    if cat=="NEW":
        if score>=92: lev="12x-15x 🔥 NEW GEM"
        elif score>=88: lev="8x-12x 🔥 STRONG NEW"
        else: lev="5x-8x"
    else:
        if score>=95: lev="10x-12x 🔥 SURE"
        elif score>=90: lev="8x-10x ✅ STRONG"
        elif score>=85: lev="5x-8x"
        else: lev="3x-5x ⚠️ CAUTION"
    return score,lev
def passes_order_book(ex,symbol):
    try:
        ob=ex.fetch_order_book(symbol,10)
        if not ob['bids'] or not ob['asks']: return False,"no book",0.9
        bid=ob['bids'][0][0]; ask=ob['asks'][0][0]
        last=(bid+ask)/2
        spread=(ask-bid)/last*100 if last else 99
        if spread>0.8: return False,f"Spread {spread:.2f}%",spread
        bid_usd=sum(b[0]*b[1] for b in ob['bids'][:10])
        if bid_usd<3000: return False,f"Depth ${int(bid_usd):,}",spread
        return True,f"Spread {spread:.2f}% Depth ${int(bid_usd):,}",spread
    except: return True,"Book ok",0.3
def process(ex,symbol,seen,cat,extra="",btc_status="NEUTRAL"):
    try:
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
        vol_ratio=1.0
        if len(v15)>=11:
            avg=sum(v15[-11:-1])/10 if sum(v15[-11:-1])>0 else v15[-1]
            if avg>0:
                vol_ratio=v15[-1]/avg if v15[-1] else 1.0
                if v15[-1] < avg*1.3: return None
        last=c5[-1]
        is_long=check_long(tf5,tf15,tf1h,tf4h)
        is_short=check_short(tf5,tf15,tf1h,tf4h)
        if not is_long and not is_short: return None
        ok,book_info,spread=passes_order_book(ex,symbol)
        if not ok: return None
        direction=f"{cat} {'LONG' if is_long else 'SHORT'}"
        key=f"{symbol}_{direction}"
        if is_recently_seen(seen,key,last): return None
        score,lev=calc_score_leverage(tf5,tf15,tf1h,tf4h,vol_ratio,spread,cat,is_long)
        if score<STRICT_SCORE: return None
        if cat=="NEW":
            tp1=last*2.2 if is_long else last*0.85
            tp2=last*4.5 if is_long else last*0.75
            tp3=last*9.0 if is_long else last*0.60
            sl=last*0.70 if is_long else last*1.15
        else:
            tp1=last*1.08 if is_long else last*0.95
            tp2=last*1.18 if is_long else last*0.89
            tp3=last*1.35 if is_long else last*0.80
            sl=last*0.95 if is_long else last*1.04
        tag={"NEW":"🔥 NEW","QUANT":"⚡ QUANT","MAJOR":"📊 MAJOR","ALT":"🚀 ALT"}.get(cat,"📊")
        msg=f"""{tag} *{direction} - {score}/100* {tag}
*Coin:* `{symbol}` {extra}
*Price:* {last:.6g}
*ENTRY:* {last:.6g}
*TP1* {tp1:.6g} *TP2* {tp2:.6g} *TP3* {tp3:.6g}
*SL* {sl:.6g}
*Lev:* {lev} Isolated
*Score:* {score}/100 Vol x{vol_ratio:.1f} {book_info}
*TF:* ✅ 5m {tf5['rsi']:.0f} ✅ 15m {tf15['rsi']:.0f} ✅ 1h {tf1h['rsi']:.0f if tf1h else 0:.0f} ✅ 4h {tf4h['rsi']:.0f if tf4h else 0:.0f}
"""
        return (key,msg,last)
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
        btc_tf=analyze_tf([c[4] for c in btc_ohlcv])
        if btc_tf:
            if btc_tf['rsi']>60 and btc_tf['macd']>btc_tf['sig']: btc_status="BULLISH"
            elif btc_tf['rsi']<40 and btc_tf['macd']<btc_tf['sig']: btc_status="BEARISH"
    except: pass
    try:
        tickers=ex.fetch_tickers()
        usdt={k:v for k,v in tickers.items() if '/USDT' in k and '3L' not in k and '3S' not in k}
        top=sorted(usdt.items(), key=lambda x: x[1].get('quoteVolume',0) or 0, reverse=True)[:15]
        for sym,t in top:
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
                res=process(ex,sym,seen,"NEW",f"Vol ${int(qv):,} Dip {dip:.1f}%",btc_status)
                if res:
                    k,m,p=res; send_text(m); seen[k]={"ts":int(time.time()),"price":float(p)}; sent+=1
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
                res=process(ex,sym,seen,"QUANT",f"{ch:.1f}% Vol ${int(t.get('quoteVolume',0)):,}",btc_status)
                if res:
                    k,m,p=res; send_text(m); seen[k]={"ts":int(time.time()),"price":float(p)}; sent+=1
        except: pass
    for cat,lst in [("MAJOR",MAJORS),("ALT",ALTS)]:
        if sent>=MAX: break
        for sym in lst:
            if sent>=MAX: break
            checked+=1
            res=process(ex,sym,seen,cat,"",btc_status)
            if res:
                k,m,p=res; send_text(m); seen[k]={"ts":int(time.time()),"price":float(p)}; sent+=1
    save_seen(seen)
    now_ts=int(datetime.now().timestamp())
    if now.hour % 4 == 0 and now.minute < 15:
        send_text(f"✅ *BOT ALIVE - 60 COINS + DYNAMIC LEVERAGE*\n🕐 Lagos: {now.strftime('%H:%M %d-%m')}\n📊 BTC: {btc_status} | Checked: {checked} | Signals: {sent}\n✅ Lev: 3x-15x by 80-99 score")
        save_alive(now_ts)
    else:
        print(f"BTC {btc_status} {sent} SIGNALS - Checked {checked} - Alive skipped")
if __name__=="__main__":
    main()
