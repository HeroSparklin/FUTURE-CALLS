import ccxt, requests, os, time
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ======================================================
# MASTER V1 LOCKED - OPTIMIZED FOR SPEED
# ======================================================
POSITION_USDT = 20
LEVERAGE = 20
TP1_PCT = 4.0
TP2_PCT = 8.0
SL_PCT = 2.5
TIMEFRAMES = ['5m', '30m', '2h', '6h', '1d']
MIN_SCORE = 80
FILTER_5M_CHANGE_MIN = 2.5
FILTER_VOL_MULT_MIN = 1.8
FILTER_RSI_OVERBOUGHT = 80
FILTER_RSI_OVERSOLD = 20
FILTER_MTF_ALIGN_MIN = 4
FILTER_BTC_MAX_DUMP = -1.0
FILTER_BTC_MAX_PUMP = 1.0
# ======================================================

COINS = ['BTC/USDT','ETH/USDT','SOL/USDT','XRP/USDT','DOGE/USDT','PEPE/USDT','SHIB/USDT','WIF/USDT','BONK/USDT','FLOKI/USDT','AVAX/USDT','LINK/USDT','ADA/USDT','LTC/USDT','BCH/USDT','TAO/USDT','FET/USDT','ENA/USDT','ONDO/USDT','SUI/USDT']

def send(text):
    try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except: pass

def ema(data, period):
    if len(data) < period: return None
    k = 2/(period+1); e=sum(data[:period])/period
    for p in data[period:]: e=p*k+e*(1-k)
    return e

def rsi(closes, period=14):
    if len(closes)<period+1: return 50
    gains=[]; losses=[]
    for i in range(1,period+1):
        d=closes[-i]-closes[-i-1]
        if d>0: gains.append(d)
        else: losses.append(abs(d))
    ag=sum(gains)/period if gains else 0; al=sum(losses)/period if losses else 0.0001
    if al==0: return 100
    return 100-(100/(1+ag/al))

def macd(closes):
    if len(closes)<26: return 0
    e12=ema(closes,12); e26=ema(closes,26)
    return (e12-e26) if e12 and e26 else 0

def get_tf_data(ex, symbol, tf):
    try:
        ohlcv=ex.fetch_ohlcv(symbol,tf,limit=100)
        if len(ohlcv)<50: return None
        closes=[c[4] for c in ohlcv]
        close=closes[-1]; prev=closes[-2]
        change=((close-prev)/prev)*100
        ema7=ema(closes,7); ema20=ema(closes,20); ema50=ema(closes,50)
        return {"close":close,"change":change,"ema7":ema7,"ema20":ema20,"ema50":ema50,"rsi":rsi(closes),"macd":macd(closes),"trend": 1 if close>ema(closes,20) else -1, "vol_mult": (ohlcv[-1][5]/(sum(c[5] for c in ohlcv[-6:-1])/5) if tf=='5m' else 1), "closes":closes}
    except: return None

def analyze():
    ex=ccxt.mexc({'enableRateLimit':True})
    try: btc_chg=get_tf_data(ex,'BTC/USDT','5m')['change']
    except: btc_chg=0

    candidates=[]
    # STAGE 1: FAST 5m SCAN ONLY - 20 calls
    for symbol in COINS:
        d=get_tf_data(ex,symbol,'5m')
        if not d: continue
        if abs(d['change'])<FILTER_5M_CHANGE_MIN: continue
        if d['vol_mult']<FILTER_VOL_MULT_MIN: continue
        if d['rsi']>FILTER_RSI_OVERBOUGHT or d['rsi']<FILTER_RSI_OVERSOLD: continue
        if d['change']>0 and d['close']<d['ema7']: continue
        if d['change']<0 and d['close']>d['ema7']: continue
        if d['change']>0 and d['macd']<0: continue
        if d['change']<0 and d['macd']>0: continue
        candidates.append((symbol,d))

    # STAGE 2: Only check higher TFs for candidates that passed stage 1
    for symbol,m5 in candidates:
        tf_results={'5m':m5}
        for tf in ['30m','2h','6h','1d']:
            d=get_tf_data(ex,symbol,tf)
            if d: tf_results[tf]=d
            time.sleep(0.2) # small delay to avoid ban

        bullish=sum(1 for v in tf_results.values() if v['trend']==1)
        bearish=sum(1 for v in tf_results.values() if v['trend']==-1)
        side=None; align=0
        if m5['change']>0 and bullish>=FILTER_MTF_ALIGN_MIN: side="LONG"; align=bullish
        elif m5['change']<0 and bearish>=FILTER_MTF_ALIGN_MIN: side="SHORT"; align=bearish
        else: continue
        if side=="LONG" and btc_chg<FILTER_BTC_MAX_DUMP: continue
        if side=="SHORT" and btc_chg>FILTER_BTC_MAX_PUMP: continue

        score=60
        if abs(m5['change'])>=3.5: score+=10
        if abs(m5['change'])>=5: score+=10
        if m5['vol_mult']>=2.5: score+=10
        score+=align*2; score=min(score,99)
        if score<MIN_SCORE: continue

        entry=m5['close']
        tp1=entry*(1+TP1_PCT/100) if side=="LONG" else entry*(1-TP1_PCT/100)
        tp2=entry*(1+TP2_PCT/100) if side=="LONG" else entry*(1-TP2_PCT/100)
        sl=entry*(1-SL_PCT/100) if side=="LONG" else entry*(1+SL_PCT/100)
        mtf_line=" | ".join([f"{tf}:{tf_results[tf]['change']:+.1f}%" for tf in TIMEFRAMES if tf in tf_results])
        msg=(f"🚀 FUTURE CALLS {symbol} {side} | {score}/100 [LOCKED V1 FAST]\nMTF {align}/5 | {mtf_line}\n5m {m5['change']:+.2f}% x{m5['vol_mult']:.1f} RSI {m5['rsi']:.0f} MACD {'🟢' if m5['macd']>0 else '🔴'}\nEMA7:{m5['ema7']:.4g} EMA20:{m5['ema20']:.4g} EMA50:{m5['ema50']:.4g} | BTC {btc_chg:+.1f}%\n\nENTRY:{entry:.8g}\nLEV:{LEVERAGE}x ${POSITION_USDT}\nTP1:{tp1:.8g} TP2:{tp2:.8g} SL:{sl:.8g}\n\n✅ LOCKED: EMA7/20/50+MACD+RSI+VOL+MTF+BTC - 2 Stage Fast")
        send(msg)
        return

    now=datetime.utcnow().strftime("%H:%M UTC")
    send(f"💓 Bot Lively [LOCKED V1 FAST]\nStage1: {len(COINS)} coins | Stage2: {len(candidates)} candidates\nNo 80+ MTF signal | BTC {btc_chg:+.1f}% | {now}")

if __name__=="__main__":
    analyze()
