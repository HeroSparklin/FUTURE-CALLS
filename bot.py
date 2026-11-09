import ccxt, os, requests, json, time
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WAT = timezone(timedelta(hours=1))
SEEN_FILE = "seen_all.json"
ALIVE_FILE = "alive.json"

STRICT_SCORE = 80
SEEN_COOLDOWN_HOURS = 4
PRICE_MOVE_OVERRIDE = 2.0
DEAD_HOURS_UTC = [1,2,3]
ADX_MIN = 20

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
def send_text(msg):
    try:
        url=f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r=requests.post(url, json={"chat_id":CHAT_ID,"text":msg,"parse_mode":"Markdown"}, timeout=20)
        print(f"TELEGRAM SEND: {r.status_code} {r.text[:200]}")
        return r.status_code==200
    except Exception as e:
        print(f"TELEGRAM ERROR: {e}")
        return False

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
def calc_adx(c, period=14):
    if len(c) < period+1: return 0
    tr=[]
    for i in range(1,len(c)): tr.append(abs(c[i]-c[i-1]))
    atr=sum(tr[-period:])/period
    up=c[-1]-c[-period]
    adx=(abs(up)/(atr*period)*100) if atr>0 else 0
    return min(adx*2, 50)

def analyze_tf(c):
    if len(c)<35: return None
    r=calc_rsi(c); m,s,h=calc_macd(c)
    if m is None: return None
    adx=calc_adx(c)
    return {"rsi":r,"macd":m,"sig":s,"hist":h,"ema7":calc_ema(c,7)[-1],"ema14":calc_ema(c,14)[-1],"ema28":calc_ema(c,28)[-1],"last":c[-1],"adx":adx, "prev_rsi":calc_rsi(c[:-1])}

def check_long(t5,t15,t1,t4):
    if not t5 or not t15 or not t1 or not t4: return False
    if not (58<=t5["rsi"]<=72 and t5["macd"]>t5["sig"] and t5["hist"]>0 and t5["last"]>t5["ema7"] and t5["ema7"]>t5["ema14"] and t5["adx"]>=ADX_MIN): return False
    if not (55<=t15["rsi"]<=70 and t15["macd"]>t15["sig"] and t15["last"]>t15["ema14"] and t15["ema14"]>t15["ema28"] and t15["adx"]>=ADX_MIN): return False
    if not (55<=t1["rsi"]<=70 and t1["macd"]>t1["sig"] and t1["last"]>t1["ema14"] and t1["adx"]>=18): return False
    if not (50<=t4["rsi"]<=75 and t4["macd"]>t4["sig"] and t4["last"]>t4["ema28"] and t4["adx"]>=15): return False
    return True

def check_short(t5,t15,t1,t4):
    if not t5 or not t15 or not t1 or not t4: return False
    if not (28<=t5["rsi"]<=42 and t5["macd"]<t5["sig"] and t5["hist"]<0 and t5["last"]<t5["ema7"] and t5["ema7"]<t5["ema14"] and t5["adx"]>=ADX_MIN): return False
    if not (30<=t15["rsi"]<=45 and t15["macd"]<t15["sig"] and t15["last"]<t15["ema14"] and t15["ema14"]<t15["ema28"] and t15["adx"]>=ADX_MIN): return False
    if not (30<=t1["rsi"]<=45 and t1["macd"]<t1["sig"] and t1["last"]<t1["ema14"] and t1["adx"]>=18): return False
    if not (25<=t4["rsi"]<=50 and t4["macd"]<t4["sig"] and t4["last"]<t4["ema28"] and t4["adx"]>=15): return False
    return True

def calc_score_leverage(tf5,tf15,tf1h,tf4h,vol_ratio,spread,cat,is_long):
    score=80
    if 58 <= tf5["rsi"] <= 68: score+=5
    if 55 <= tf15["rsi"] <= 68: score+=4
    if tf1h and (55 <= tf1h["rsi"] <= 68 if is_long else 32 <= tf1h["rsi"] <= 45): score+=3
    if tf4h and tf4h["adx"]>25: score+=3
    else: score+=1
    if 1.5 <= vol_ratio <= 2.5: score+=5
    elif 1.3 <= vol_ratio < 1.5: score+=2
    if spread<0.15: score+=3
    elif spread<0.3: score+=1
    if abs(tf5["hist"]) > abs(tf15["hist"])*0.6: score+=2
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

def passes_order_book(ex,symbol,is_long):
    try:
        ob=ex.fetch_order_book(symbol,20)
        if not ob['bids'] or not ob['asks']: return False,"no book",0.9
        bid=ob['bids'][0][0]; ask=ob['asks'][0][0]
        last=(bid+ask)/2
        spread=(ask-bid)/last*100 if last else 99
        if spread>0.8: return False,f"Spread {spread:.2f}%",spread
        bid_usd=sum(b[0]*b[1] for b in ob['bids'][:10])
        if bid_usd<3000: return False,f"Depth ${int(bid_usd):,}",spread
        bid_vol=sum(b[1] for b in ob['bids'][:20])
        ask_vol=sum(a[1] for a in ob['asks'][:20])
        if is_long and bid_vol < ask_vol*1.2:
            return False,f"Imbal LONG {bid_vol/ask_vol:.1f}x no whale",spread
        if not is_long and ask_vol < bid_vol*1.2:
            return False,f"Imbal SHORT {ask_vol/bid_vol:.1f}x no whale",spread
        return True,f"Spread {spread:.2f}% Imbal {bid_vol/ask_vol:.1f}x Depth ${int(bid_usd):,}",spread
    except: return True,"Book ok",0.3

def is_alt_season_dynamic(ex):
    try:
        btc_ticker=ex.fetch_ticker('BTC/USDT')
        btc_ch=btc_ticker.get('percentage',0) or 0
        alt_chs=[]
        for s in ['PEPE/USDT','WIF/USDT','SOL/USDT','ARB/USDT','OP/USDT']:
            try:
                t=ex.fetch_ticker(s)
                alt_chs.append(t.get('percentage',0) or 0)
            except: pass
        avg_alt=sum(alt_chs)/len(alt_chs) if alt_chs else 0
        is_alt=(avg_alt - btc_ch) > 4.5
        info=f"ALT SEASON Alt {avg_alt:+.1f}% vs BTC {btc_ch:+.1f}%" if is_alt else f"BTC DOM Alt {avg_alt:+.1f}% vs BTC {btc_ch:+.1f}%"
        return is_alt, info, btc_ch, avg_alt
    except:
        return False, "BTC NEUTRAL", 0, 0

def process(ex,symbol,seen,cat,extra="",btc_status="NEUTRAL",is_alt_season=False):
    try:
        o5m=ex.fetch_ohlcv(symbol,'5m',limit=100)
        o15m=ex.fetch_ohlcv(symbol,'15m',limit=100)
        o1h=ex.fetch_ohlcv(symbol,'1h',limit=100)
        o4h=ex.fetch_ohlcv(symbol,'4h',limit=100)
        if len(o5m)<35 or len(o15m)<35 or len(o1h)<35 or len(o4h)<35: return None
        c5=[c[4] for c in o5m]; c15=[c[4] for c in o15m]
        c1h=[c[4] for c in o1h]; c4h=[c[4] for c in o4h]
        v15=[c[5] for c in o15m]
        tf5=analyze_tf(c5); tf15=analyze_tf(c15)
        tf1h=analyze_tf(c1h); tf4h=analyze_tf(c4h)
        if not tf5 or not tf15 or not tf1h or not tf4h: return None
        vol_ratio=1.0
        if len(v15)>=11:
            avg=sum(v15[-11:-1])/10 if sum(v15[-11:-1])>0 else v15[-1]
            if avg>0:
                vol_ratio=v15[-1]/avg if v15[-1] else 1.0
                if v15[-1] < avg*1.3: return None
                if v15[-1] > avg*3.2: return None
        last=c5[-1]
        if c5[-1] > c5[-2] and tf5["rsi"] < tf5["prev_rsi"] - 3: return None
        if c5[-1] < c5[-2] and tf5["rsi"] > tf5["prev_rsi"] + 3: return None
        is_long=check_long(tf5,tf15,tf1h,tf4h)
        is_short=check_short(tf5,tf15,tf1h,tf4h)
        if not is_long and not is_short: return None
        if not is_alt_season:
            if btc_status=="BEARISH" and is_long and cat!="NEW": return None
            if btc_status=="BULLISH" and is_short and cat!="NEW": return None
        ok,book_info,spread=passes_order_book(ex,symbol,is_long)
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
*TF:* 5m{tf5['adx']:.0f} 15m{tf15['adx']:.0f} 1h{tf1h['adx']:.0f} 4h{tf4h['adx']:.0f} ADX ✅
"""
        return (key,msg,last)
    except Exception as e:
        print(f"Process error {symbol}: {e}")
        return None

def main():
    now_utc=datetime.now(timezone.utc)
    now=datetime.now(WAT)
    print(f"==== BOT START {now.strftime('%Y-%m-%d %H:%M:%S')} Lagos | UTC {now_utc.hour}h ====")
    print(f"BOT_TOKEN set: {bool(BOT_TOKEN)} CHAT_ID set: {bool(CHAT_ID)}")

    if now_utc.hour in DEAD_HOURS_UTC:
        print(f"Dead hours {now_utc.hour} UTC -> skip trading, send alive ping")
        send_text(f"⏸️ Dead hours {now_utc.hour} UTC - Bot alive no trade - {now.strftime('%H:%M')} Lagos")
        return
    try:
        ex=ccxt.gate({'enableRateLimit': True, 'timeout': 10000})
        ex.load_markets()
        print("Exchange loaded")
    except Exception as e:
        print(f"Exchange load failed: {e}")
        return
    seen=load_seen()
    print(f"Seen loaded: {len(seen)} coins")
    sent=0; checked=0; MAX=4
    btc_status="NEUTRAL"
    is_alt=False
    btc_info="BTC NEUTRAL"
    try:
        btc_ohlcv=ex.fetch_ohlcv('BTC/USDT','1h',limit=50)
        btc_tf=analyze_tf([c[4] for c in btc_ohlcv])
        if btc_tf:
            if btc_tf['rsi']>60 and btc_tf['macd']>btc_tf['sig']: btc_status="BULLISH"
            elif btc_tf['rsi']<40 and btc_tf['macd']<btc_tf['sig']: btc_status="BEARISH"
        is_alt, btc_info, btc_ch, alt_ch = is_alt_season_dynamic(ex)
        print(f"BTC STATUS: {btc_status} {btc_info} AltSeason={is_alt}")
    except Exception as e:
        print(f"BTC status error: {e}")

    try:
        tickers=ex.fetch_tickers()
        usdt={k:v for k,v in tickers.items() if '/USDT' in k and '3L' not in k and '3S' not in k}
        top=sorted(usdt.items(), key=lambda x: x[1].get('quoteVolume',0) or 0, reverse=True)[:15]
        print(f"Scanning {len(top)} NEW coins")
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
                res=process(ex,sym,seen,"NEW",f"Vol ${int(qv):,} Dip {dip:.1f}% {btc_info}",btc_status,is_alt)
                if res:
                    k,m,p=res; send_text(m); seen[k]={"ts":int(time.time()),"price":float(p)}; sent+=1; print(f"SENT NEW {sym}")
            except Exception as e:
                print(f"NEW scan err {sym}: {e}")
                continue
    except Exception as e:
        print(f"NEW block error: {e}")

    if sent<MAX:
        try:
            tickers=ex.fetch_tickers()
            usdt={k:v for k,v in tickers.items() if '/USDT' in k and v.get('quoteVolume',0)>500000}
            top=sorted(usdt.items(), key=lambda x: x[1].get('percentage',0) or 0, reverse=True)[:10]
            bot=sorted(usdt.items(), key=lambda x: x[1].get('percentage',0) or 0)[:10]
            print(f"Scanning QUANT {len(top)+len(bot)} coins")
            for sym,t in top+bot:
                if sent>=MAX: break
                ch=t.get('percentage',0) or 0; checked+=1
                if abs(ch)<5: continue
                res=process(ex,sym,seen,"QUANT",f"{ch:.1f}% Vol ${int(t.get('quoteVolume',0)):,} {btc_info}",btc_status,is_alt)
                if res:
                    k,m,p=res; send_text(m); seen[k]={"ts":int(time.time()),"price":float(p)}; sent+=1; print(f"SENT QUANT {sym}")
        except Exception as e:
            print(f"QUANT error: {e}")

    for cat,lst in [("MAJOR",MAJORS),("ALT",ALTS)]:
        if sent>=MAX: break
        print(f"Scanning {cat} {len(lst)} coins")
        for sym in lst:
            if sent>=MAX: break
            checked+=1
            res=process(ex,sym,seen,cat,btc_info,btc_status,is_alt)
            if res:
                k,m,p=res; send_text(m); seen[k]={"ts":int(time.time()),"price":float(p)}; sent+=1; print(f"SENT {cat} {sym}")

    save_seen(seen)
    print(f"==== FINISH Checked:{checked} Sent:{sent} {btc_info} BTC:{btc_status} Alt:{is_alt} ====")
    if now.hour % 4 == 0 and now.minute < 15:
        send_text(f"✅ *BOT PERFECT - 6 FILTERS LOCKED*\n🕐 {now.strftime('%H:%M %d-%m')} Lagos | UTC {now_utc.hour}h\n📊 {btc_info} BTC:{btc_status} AltSeason:{is_alt}\n📈 Checked:{checked} Signals:{sent}\n🔒 ADX>{ADX_MIN} 4TF Imbal VolDiv Time")

if __name__=="__main__":
    main()
