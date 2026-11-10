# bot.py - FINAL FIX for 451/403 - MEXC edition
import os, json, time, ccxt, pandas as pd, requests
from datetime import datetime, timezone

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BROADCAST_ID = os.getenv("TELEGRAM_BROADCAST_ID", "")

SEEN_FILE = "seen.json"
ALIVE_FILE = "last_alive.txt"

MAJOR_ALT = ["BTC/USDT","ETH/USDT","SOL/USDT","XRP/USDT","DOGE/USDT","ADA/USDT","AVAX/USDT","LINK/USDT","DOT/USDT","MATIC/USDT","NEAR/USDT","APT/USDT","ARB/USDT","OP/USDT","ATOM/USDT","LTC/USDT","BCH/USDT","FIL/USDT","HBAR/USDT","INJ/USDT","SUI/USDT","SEI/USDT","TIA/USDT","PEPE/USDT","WIF/USDT"]
QUANT = ["ENA/USDT","PENDLE/USDT","ONDO/USDT","JUP/USDT","STRK/USDT","ZK/USDT","TAO/USDT","RENDER/USDT","FET/USDT","IMX/USDT","MANTA/USDT","ALT/USDT","PYTH/USDT","DYM/USDT","BEAM/USDT","LDO/USDT","AAVE/USDT","UNI/USDT","STX/USDT","GALA/USDT"]
NEW_EXTRA = ["INIT/USDT","EIGEN/USDT","SCR/USDT","DRIFT/USDT","ZRO/USDT","LISTA/USDT","ME/USDT","MOVE/USDT","S/USDT","BABY/USDT","PUMP/USDT","HYPE/USDT","VIRTUAL/USDT","AERO/USDT","ATH/USDT"]
ALL_JOBS = [(s,"MAJOR/ALT") for s in MAJOR_ALT] + [(s,"QUANT") for s in QUANT] + [(s,"NEW") for s in NEW_EXTRA]

def get_working_exchange():
    candidates = [
        ("mexc", ccxt.mexc({'enableRateLimit': True})),
        ("kucoin", ccxt.kucoin({'enableRateLimit': True})),
        ("gate", ccxt.gate({'enableRateLimit': True})),
        ("bitget", ccxt.bitget({'enableRateLimit': True})),
    ]
    for name, ex in candidates:
        try:
            ex.load_markets()
            ex.fetch_ticker("BTC/USDT")
            print(f"Using {name.upper()} - WORKS!")
            return ex
        except Exception as e:
            print(f"{name} failed {str(e)[:100]}")
            continue
    print("All failed, using MEXC anyway")
    return ccxt.mexc({'enableRateLimit': True})

exchange = get_working_exchange()

def send_telegram(msg):
    if not TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for cid in [CHAT_ID, BROADCAST_ID]:
        if not cid: continue
        try: requests.post(url, json={"chat_id": cid, "text": msg, "parse_mode": "HTML"}, timeout=15)
        except Exception as e: print(f"TG error {e}")

def load_seen():
    try:
        with open(SEEN_FILE) as f: return json.load(f)
    except: return {}
def save_seen(s):
    with open(SEEN_FILE,"w") as f: json.dump(s,f)
def should_send_alive():
    try:
        with open(ALIVE_FILE) as f: last=float(f.read().strip())
        return (time.time()-last)/3600 >= 4
    except: return True
def mark_alive():
    with open(ALIVE_FILE,"w") as f: f.write(str(time.time()))
def ema(s,p): return s.ewm(span=p, adjust=False).mean()
def adx(df, period=14):
    try:
        h=df['high']; l=df['low']; c=df['close']
        pdm=h.diff(); mdm=-l.diff()
        pdm[pdm<0]=0; mdm[mdm<0]=0
        tr=pd.concat([h-l, abs(h-c.shift()), abs(l-c.shift())], axis=1).max(axis=1)
        atr=tr.rolling(period).mean()
        pdi=100*(pdm.rolling(period).mean()/atr)
        mdi=100*(mdm.rolling(period).mean()/atr)
        dx=abs(pdi-mdi)/(pdi+mdi)*100
        return dx.rolling(period).mean().iloc[-1]
    except: return 0

def get_ohlcv(symbol, tf, limit=100):
    try:
        ohlcv=exchange.fetch_ohlcv(symbol, tf, limit=limit)
        df=pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
        df['ema7']=ema(df['close'],7); df['ema14']=ema(df['close'],14); df['ema28']=ema(df['close'],28)
        return df
    except Exception as e:
        print(f"{symbol} {tf} err {e}"); return None

def trend_of(df):
    if df is None or len(df)<30: return "NEUTRAL"
    last=df.iloc[-1]
    if last['close']>last['ema7']>last['ema14']>last['ema28']: return "BULL"
    if last['close']<last['ema7']<last['ema14']<last['ema28']: return "BEAR"
    return "NEUTRAL"

def get_btc_status():
    df=get_ohlcv("BTC/USDT","4h",50)
    return (trend_of(df), df.iloc[-1]['close']) if df is not None else ("NEUTRAL",0)

def is_alt_season():
    try:
        tickers=exchange.fetch_tickers(["PEPE/USDT","WIF/USDT","SOL/USDT","BTC/USDT"])
        alt_vals=[tickers[s]['percentage'] for s in ["PEPE/USDT","WIF/USDT","SOL/USDT"] if s in tickers and tickers[s].get('percentage') is not None]
        btc_chg=tickers["BTC/USDT"]['percentage'] if "BTC/USDT" in tickers and tickers["BTC/USDT"].get('percentage') else 0
        if not alt_vals: return False,0,btc_chg
        avg=sum(alt_vals)/len(alt_vals)
        return (avg-btc_chg)>4.5, avg, btc_chg
    except: return False,0,0

def score_coin(symbol, cat, btc_status, alt_season):
    df_5m=get_ohlcv(symbol,"5m",100)
    df_15m=get_ohlcv(symbol,"15m",100)
    df_30m=get_ohlcv(symbol,"30m",100)
    df_4h=get_ohlcv(symbol,"4h",100)
    if None in [df_5m,df_15m,df_30m,df_4h]: return None
    t5=trend_of(df_5m); t15=trend_of(df_15m); t30=trend_of(df_30m); t4h=trend_of(df_4h)
    if not (t5==t15==t30==t4h and t5 in ["BULL","BEAR"]): return None
    direction="LONG" if t5=="BULL" else "SHORT"
    if not alt_season:
        if btc_status=="BEAR" and direction=="LONG" and cat!="NEW": return None
        if btc_status=="BULL" and direction=="SHORT" and cat!="NEW": return None
    adx5=adx(df_5m); adx15=adx(df_15m)
    if adx5<20 or adx15<20: return None
    vol=df_5m.iloc[-1]['volume']; vol_avg=df_5m['volume'].rolling(20).mean().iloc[-1]
    if vol < vol_avg*1.2: return None
    try:
        ob=exchange.fetch_order_book(symbol, limit=10)
        bid=ob['bids'][0][0] if ob['bids'] else 0
        ask=ob['asks'][0][0] if ob['asks'] else 0
        if bid and (ask-bid)/bid>0.002: return None
    except: pass
    score=25+ (25 if adx5>30 else 15) +20+15+10+5
    if score<80: return None
    price=df_5m.iloc[-1]['close']
    if direction=="LONG": sl=price*0.985; tp1=price*1.02; tp2=price*1.04; tp3=price*1.06
    else: sl=price*1.015; tp1=price*0.98; tp2=price*0.96; tp3=price*0.94
    return {"symbol":symbol,"direction":direction,"score":score,"price":price,"sl":sl,"tp1":tp1,"tp2":tp2,"tp3":tp3,"adx5":round(adx5,1),"adx15":round(adx15,1),"cat":cat}

def format_signal(s):
    emoji="🟢" if s['direction']=="LONG" else "🔴"
    return f"{emoji} <b>{s['symbol']} {s['direction']}</b> | {s['cat']}\nScore: {s['score']}/100 | ADX {s['adx5']}/{s['adx15']}\nEntry: {s['price']:.5f}\nSL: {s['sl']:.5f}\nTP1: {s['tp1']:.5f} TP2: {s['tp2']:.5f} TP3: {s['tp3']:.5f}"

def main():
    now=datetime.now(timezone.utc); print(f"Run start UTC {now}")
    seen=load_seen(); btc_status,btc_price=get_btc_status(); alt_season,avg_alt,btc_chg=is_alt_season()
    print(f"BTC STATUS: {btc_status} AltSeason={alt_season}")
    if now.hour in [0,1]:
        if should_send_alive():
            send_telegram(f"🤖 <b>Bot Alive</b>\nDead hours {now.hour} UTC - No trade\nBTC: {btc_status} ${btc_price:.0f}")
            mark_alive()
        return
    sent=0
    for symbol,cat in ALL_JOBS:
        if symbol in seen:
            last=seen[symbol]; hrs=(time.time()-last.get("time",0))/3600
            if hrs<4:
                try:
                    cur=exchange.fetch_ticker(symbol)['last']
                    if last.get("price") and abs(cur-last["price"])/last["price"]<0.02: continue
                except: continue
        res=score_coin(symbol,cat,btc_status,alt_season)
        if res:
            if symbol in seen:
                prev=seen[symbol]; hrs=(time.time()-prev.get("time",0))/3600
                if hrs<4 and prev.get("direction")==res['direction'] and abs(res['price']-prev.get("price",0))/prev.get("price",1)<0.02: continue
            send_telegram(format_signal(res))
            seen[symbol]={"time":time.time(),"price":res['price'],"direction":res['direction']}
            sent+=1
    save_seen(seen)
    print(f"Checked:{len(ALL_JOBS)} Sent:{sent}")
    if should_send_alive() or sent>0:
        send_telegram(f"🤖 <b>Bot Alive - MEXC</b>\nChecked: {len(ALL_JOBS)} | Sent: {sent}\nBTC: {btc_status} ${btc_price:.0f} | Alt: {alt_season}")
        mark_alive()

if __name__=="__main__": main()
