import os, requests, json, csv, time
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_BROADCAST_ID")
BROADCAST_ID = os.getenv("TELEGRAM_BROADCAST_ID") or CHAT_ID

# ===== 65 COINS - MAX ALT EDITION =====
TOTAL_COINS = [
    # MAJORS 10
    "BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","LTCUSDT","BCHUSDT",
    # L1 / L2 / DEFI ALTS 20
    "NEARUSDT","UNIUSDT","APTUSDT","ARBUSDT","FILUSDT","OPUSDT","INJUSDT","STXUSDT","TIAUSDT","SUIUSDT",
    "SEIUSDT","SAGAUSDT","STRKUSDT","JUPUSDT","PYTHUSDT","MNTUSDT","IMXUSDT","GRTUSDT","RUNEUSDT","AAVEUSDT",
    # AI / QUANT / BIG DATA 10
    "RNDRUSDT","FETUSDT","WLDUSDT","ARKMUSDT","TAOUSDT","RENDERUSDT","AGIXUSDT","OCEANUSDT","AKTUSDT","NMRUSDT",
    # MEME / HIGH VOL 10
    "PEPEUSDT","WIFUSDT","BONKUSDT","FLOKIUSDT","SHIBUSDT","MEMEUSDT","ORDIUSDT","1000SATSUSDT","BOMEUSDT","POPCATUSDT",
    # NEWEST 2024-2026 LISTINGS 15
    "ENAUSDT","NOTUSDT","ZKUSDT","WUSDT","OMUSDT","ONDOUSDT","JTOUSDT","DYMUSDT","ALTUSDT","PIXELUSDT",
    "PORTALUSDT","AEVOUSDT","ETHFIUSDT","WIFUSDT","ENAUSDT"
]

# Remove duplicates keep order
TOTAL_COINS = list(dict.fromkeys(TOTAL_COINS))

STRICTNESS=92; MAX_SPREAD=0.40; MODE="LONG+SHORT 65 ALT MAX 90/100"; ENTRY_START_HOUR=0; ENTRY_END_HOUR=24
BTC_EXTREME_VOL=4.0; COOLDOWN_FILE="cooldown.json"; COOLDOWN_HOURS=2; HTF_INTERVAL="1h"; MAX_RISK_PCT=2.5; MAX_ATR_PCT=6.0; LOG_FILE="signals_log.csv"

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID: return
    for cid in set([CHAT_ID, BROADCAST_ID]):
        if not cid: continue
        try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id":cid,"text":text,"parse_mode":"Markdown"}, timeout=10)
        except: pass

def log_signal(symbol, direction, score, entry, sl, tp, rsi, adx, spread, btc_trend, risk_pct, tag):
    try:
        fe=os.path.exists(LOG_FILE)
        with open(LOG_FILE,"a",newline="",encoding="utf-8") as f:
            w=csv.writer(f)
            if not fe: w.writerow(["time","symbol","direction","score","entry","sl","tp","rsi","adx","spread","btc_trend","risk_pct","tag"])
            w.writerow([datetime.utcnow().isoformat(),symbol,direction,score,entry,sl,tp,rsi,adx,spread,btc_trend,risk_pct,tag])
    except: pass

def get_klines_okx(symbol="BTCUSDT", interval="15m", limit=100):
    try:
        okx_symbol=symbol.replace("USDT","-USDT")
        okx_interval="15m" if interval=="15m" else "1H"
        url=f"https://www.okx.com/api/v5/market/candles?instId={okx_symbol}&bar={okx_interval}&limit={limit}"
        r=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
        data=r.json().get("data",[])
        if not data: return []
        kl=[]
        for c in reversed(data): kl.append({"time":int(c[0]),"open":float(c[1]),"high":float(c[2]),"low":float(c[3]),"close":float(c[4]),"vol":float(c[5])})
        return kl
    except: return []

def get_spread_pct(symbol):
    try:
        okx_symbol=symbol.replace("USDT","-USDT")
        url=f"https://www.okx.com/api/v5/market/ticker?instId={okx_symbol}"
        r=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
        data=r.json().get("data",[])
        if not data: return 0
        ask=float(data[0].get("askPx",0)); bid=float(data[0].get("bidPx",0))
        return (ask-bid)/bid*100 if bid!=0 else 0
    except: return 0

def get_auto_new_listings():
    new_coins=[]
    try:
        url="https://www.okx.com/api/v5/market/tickers?instType=SPOT"
        r=requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=15)
        data=r.json().get("data",[])
        usdt_pairs=[d for d in data if d.get("instId","").endswith("-USDT")]
        usdt_pairs.sort(key=lambda x: float(x.get("volCcy24h",0)), reverse=True)
        top_100=usdt_pairs[:100]
        for t in top_100:
            inst=t.get("instId","").replace("-","")
            if inst in TOTAL_COINS: continue
            if any(x in inst for x in ["USDC","FDUSD","DAI","EUR","TRY"]): continue
            kl=get_klines_okx(inst,"15m",60)
            if len(kl)>0 and len(kl)<55:
                new_coins.append(inst)
            if len(new_coins)>=5: break
    except: pass
    return new_coins

def calc_rsi(closes, period=14):
    if len(closes)<period+1: return 50
    gains=[]; losses=[]
    for i in range(1,period+1):
        diff=closes[-i]-closes[-i-1]
        (gains if diff>0 else losses).append(abs(diff) if diff<=0 else diff)
    avg_gain=sum(gains)/period if gains else 0; avg_loss=sum(losses)/period if losses else 0.000001
    if avg_loss==0: return 100
    return 100-(100/(1+avg_gain/avg_loss))

def calc_atr(klines, period=14):
    if len(klines)<period+1: return 0
    tr=[]
    for i in range(1,period+1): h=klines[-i]["high"]; l=klines[-i]["low"]; pc=klines[-i-1]["close"]; tr.append(max(h-l, abs(h-pc), abs(l-pc)))
    return sum(tr)/len(tr)

def calc_adx(klines, period=14):
    if len(klines)<period*2+1: return 0,0,0
    trs=[]; pdm=[]; mdm=[]
    for i in range(1,len(klines)):
        h=klines[i]["high"]; l=klines[i]["low"]; ph=klines[i-1]["high"]; pl=klines[i-1]["low"]; pc=klines[i-1]["close"]
        trs.append(max(h-l, abs(h-pc), abs(l-pc))); up=h-ph; down=pl-l
        pdm.append(up if (up>down and up>0) else 0); mdm.append(down if (down>up and down>0) else 0)
    def smooth(v,p):
        res=[sum(v[:p])]
        for i in range(p,len(v)): res.append(res[-1]-res[-1]/p+v[i])
        return res
    tr_s=smooth(trs,period); p_s=smooth(pdm,period); m_s=smooth(mdm,period)
    mlen=min(len(tr_s),len(p_s),len(m_s)); tr_s=tr_s[-mlen:]; p_s=p_s[-mlen:]; m_s=m_s[-mlen:]
    dx=[]; lp=0; lm=0
    for i in range(len(tr_s)):
        if tr_s[i]==0: dx.append(0); continue
        pdi=100*p_s[i]/tr_s[i]; mdi=100*m_s[i]/tr_s[i]; dx.append(100*abs(pdi-mdi)/(pdi+mdi) if (pdi+mdi)!=0 else 0)
        if i==len(tr_s)-1: lp=pdi; lm=mdi
    return (sum(dx[-period:])/period if len(dx)>=period else 0), lp, lm

def load_cooldown():
    try:
        if os.path.exists(COOLDOWN_FILE):
            with open(COOLDOWN_FILE,"r") as f: return json.load(f)
    except: pass
    return {}
def save_cooldown(d):
    try: 
        with open(COOLDOWN_FILE,"w") as f: json.dump(d,f)
    except: pass
def is_on_cooldown(s,d):
    if s not in d: return False,0
    try:
        last=datetime.fromisoformat(d[s]); diff=datetime.utcnow()-last; lim=timedelta(hours=COOLDOWN_HOURS)
        if diff<lim: return True,int((lim-diff).total_seconds()/60)
        return False,0
    except: return False,0
def set_cooldown(s,d): d[s]=datetime.utcnow().isoformat(); save_cooldown(d)

def check_htf(s,trend):
    htf=get_klines_okx(s,HTF_INTERVAL,100)
    if len(htf)<50: return False,"HTF_NO_DATA"
    closes=[k["close"] for k in htf]; sma50=sum(closes[-50:])/50; price=closes[-1]
    if trend=="BULL": return (price>sma50, f"HTF_OK {price:.2f}>SMA50") if price>sma50 else (False,f"HTF_REJECT LONG {price:.2f}<{sma50:.2f}")
    else: return (price<sma50, f"HTF_OK {price:.2f}<SMA50") if price<sma50 else (False,f"HTF_REJECT SHORT {price:.2f}>{sma50:.2f}")

def get_btc():
    kl=get_klines_okx("BTCUSDT","1H",100)
    if not kl: return "UNKNOWN",0,"NORMAL",55,45,25,False,"NO_DATA"
    closes=[k["close"] for k in kl]; vol=(closes[-1]-closes[-5])/closes[-5]*100 if closes[-5]!=0 else 0
    sma20=sum(closes[-20:])/20; sma50=sum(closes[-50:])/50; curr=closes[-1]
    trend="BULL" if curr>sma20>sma50 else "BEAR" if curr<sma20<sma50 else "SIDE"
    if abs(vol)>BTC_EXTREME_VOL: return trend,vol,"EXTREME",60,40,30,True,f"EXTREME {vol:.2f}%"
    elif abs(vol)>2: return trend,vol,"VOLATILE",60,40,30,False,"VOLATILE"
    elif abs(vol)>1: return trend,vol,"NORMAL",55,45,25,False,"NORMAL"
    else: return trend,vol,"CALM",50,50,20,False,"CALM"

def calc_score(klines, btc_trend, btc_regime, rsi_long_min, rsi_short_max, adx_min):
    if len(klines)<30: return None,None,["NO_DATA"],0,0,0,""
    is_new=len(klines)<55; closes=[k["close"] for k in klines]; vols=[k["vol"] for k in klines]; highs=[k["high"] for k in klines]; lows=[k["low"] for k in klines]
    curr=closes[-1]; sma20=sum(closes[-20:])/20; sma50=sma20 if is_new else sum(closes[-50:])/50
    rsi=calc_rsi(closes,14); adx,pdi,mdi=calc_adx(klines,14); tag="NEW_LISTING" if is_new else "NORMAL"
    if curr>sma20>sma50: trend="BULL"
    elif curr<sma20<sma50: trend="BEAR"
    elif is_new and curr>sma20: trend="BULL"
    elif is_new and curr<sma20: trend="BEAR"
    else: return 50,"SIDE",["50 SIDE"],rsi,0,adx,tag
    score=70
    avg_vol=sum(vols[-20:-1])/19 if len(vols)>20 else sum(vols[:-1])/max(1,len(vols)-1); vr=vols[-1]/avg_vol if avg_vol!=0 else 0
    if vr<1.3: return score,trend,[f"{score} VOL_LOW {vr:.2f}x"],rsi,0,adx,tag
    score+=15; change=(curr-closes[-5])/closes[-5]*100 if closes[-5]!=0 else 0
    if trend=="BULL" and change<1.5: return score,trend,[f"{score} MOM_LOW {change:.2f}%"],rsi,0,adx,tag
    if trend=="BEAR" and change>-1.5: return score,trend,[f"{score} MOM_LOW {change:.2f}%"],rsi,0,adx,tag
    score+=10
    if trend=="BULL":
        ph=max(highs[-21:-1]) if len(highs)>=21 else max(highs[:-1])
        if curr<=ph: return score,trend,[f"{score} NO_BREAKOUT"],rsi,0,adx,tag
    else:
        pl=min(lows[-21:-1]) if len(lows)>=21 else min(lows[:-1])
        if curr>=pl: return score,trend,[f"{score} NO_BREAKDOWN"],rsi,0,adx,tag
    score+=6
    if trend=="BULL" and rsi<rsi_long_min:
        if not (rsi<35 and change>1.5 and vr>1.3): return score,trend,[f"{score} RSI_LOW {rsi:.0f}"],rsi,0,adx,tag
    if trend=="BEAR" and rsi>rsi_short_max:
        if not (rsi>65 and change<-1.5 and vr>1.3): return score,trend,[f"{score} RSI_HIGH {rsi:.0f}"],rsi,0,adx,tag
    atr=calc_atr(klines,14); atr_pct=atr/curr*100 if curr!=0 else 0
    if atr_pct<0.3: return score,trend,[f"{score} ATR_LOW {atr_pct:.2f}%"],rsi,atr,adx,tag
    if atr_pct>MAX_ATR_PCT: return score,trend,[f"{score} ATR_HIGH {atr_pct:.2f}%"],rsi,atr,adx,tag
    if adx<adx_min: return score,trend,[f"{score} ADX_WEAK {adx:.1f}"],rsi,atr,adx,tag
    if trend=="BULL" and pdi<mdi: return score,trend,[f"{score} DI_WRONG"],rsi,atr,adx,tag
    if trend=="BEAR" and mdi<pdi: return score,trend,[f"{score} DI_WRONG"],rsi,atr,adx,tag
    if score>100: score=100
    return score,trend,[f"{score} ALL_PASS RSI:{rsi:.0f} ADX:{adx:.1f} ATR:{atr_pct:.2f}% BTC:{btc_trend} {btc_regime} {tag}"],rsi,atr,adx,tag

def main():
    auto_new=get_auto_new_listings()
    final_coins=list(dict.fromkeys(TOTAL_COINS + auto_new))
    print(f"Total Coins: {len(final_coins)} = {len(TOTAL_COINS)} base + {len(auto_new)} auto-new | {MODE}")
    print(f"Auto-new: {auto_new if auto_new else 'None'}")
    btc_trend,btc_vol,btc_regime,rsi_l,rsi_s,adx_min,block_all,msg=get_btc()
    print(f"BTC: {btc_trend} VOL:{btc_vol:.2f}% {btc_regime} BLOCK:{block_all}")
    if block_all: print(f"STOP {msg}"); return
    cd=load_cooldown(); print(f"SCAN {datetime.now().strftime('%H:%M:%S')} UTC BTC:{btc_trend} 24HRS:ON")
    found=0
    for sym in final_coins:
        time.sleep(1.0)
        spread=get_spread_pct(sym)
        if spread>MAX_SPREAD: print(f"REJECT {sym}: SPREAD_HIGH {spread:.3f}%"); continue
        kl=get_klines_okx(sym,"15m",100)
        score,trend,reasons,rsi,atr,adx,tag=calc_score(kl,btc_trend,btc_regime,rsi_l,rsi_s,adx_min)
        if score is None: print(f"REJECT {sym}: NO_DATA"); continue
        if score>=STRICTNESS:
            htf_ok,htf_msg=check_htf(sym,trend)
            if not htf_ok: print(f"REJECT {sym}: {score} {trend} {htf_msg}"); continue
            on_cool,mins=is_on_cooldown(sym,cd)
            if on_cool: print(f"HOLD {sym}: {score} COOLDOWN {mins}min"); continue
            entry=kl[-1]['close']
            if trend=="BULL": direction="LONG"; emoji="🚀"; sl=entry-atr*1.5; tp=entry+atr*3
            else: direction="SHORT"; emoji="🔻"; sl=entry+atr*1.5; tp=entry-atr*3
            if trend=="BULL" and sl>=entry: sl=entry*0.98; tp=entry*1.04
            if trend=="BEAR" and sl<=entry: sl=entry*1.02; tp=entry*0.96
            risk=abs(entry-sl)/entry*100 if entry!=0 else 0
            if risk>MAX_RISK_PCT: print(f"REJECT {sym}: RISK_HIGH {risk:.2f}%"); continue
            if risk<0.4: print(f"REJECT {sym}: RISK_LOW {risk:.2f}%"); continue
            found+=1; set_cooldown(sym,cd)
            tmsg=f"{emoji} *{sym}* {direction} - {score}/100 {tag}\nTrend:{trend} HTF:✅\nEntry:{entry}\nSL:{sl:.6f} ({risk:.2f}%)\nTP:{tp:.6f}\nSpread:{spread:.3f}% ADX:{adx:.1f} BTC:{btc_trend}\n{reasons[0]}"
            print(f"FOUND {sym}: {score} {direction} {tag} {risk:.2f}%"); send_telegram(tmsg); log_signal(sym,direction,score,entry,sl,tp,rsi,adx,spread,btc_trend,risk,tag)
        else: print(f"REJECT {sym}: {reasons} Spread {spread:.3f}%")
    if found==0: print("SCAN DONE - 0 signals - filtered correctly")

if __name__=="__main__": main()
