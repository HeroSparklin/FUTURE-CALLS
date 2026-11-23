import os, ccxt, pandas as pd, requests, time, traceback
import concurrent.futures

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def fetch_funding(exchange, symbol):
    try:
        data = exchange.fetch_funding_rate(symbol)
        return float(data.get("fundingRate", 0) or 0)
    except: return 0.0

def get_btc_trend(exchange):
    try:
        ohlcv = exchange.fetch_ohlcv("BTC/USDT:USDT", "1h", limit=50)
        df = pd.DataFrame(ohlcv, columns=["ts","open","high","low","close","vol"])
        df["ema7"] = df["close"].ewm(span=7).mean()
        df["ema25"] = df["close"].ewm(span=25).mean()
        last, prev = df.iloc[-1], df.iloc[-2]
        mom = (last["close"]-prev["close"])/prev["close"]*100
        if last["ema7"]>last["ema25"] and mom>0.3: return "BULLISH"
        if last["ema7"]<last["ema25"] and mom<-0.3: return "BEARISH"
        if abs(mom)>0.8: return "VOLATILE"
        return "RANGING"
    except: return "RANGING"

def analyze_coin(exchange, symbol, btc_trend):
    try:
        o5 = exchange.fetch_ohlcv(symbol, "5m", limit=120)
        o15 = exchange.fetch_ohlcv(symbol, "15m", limit=120)
        o1h = exchange.fetch_ohlcv(symbol, "1h", limit=120)
        if len(o5)<100 or len(o15)<100 or len(o1h)<50: return None
        df5 = pd.DataFrame(o5, columns=["ts","open","high","low","close","vol"])
        df15 = pd.DataFrame(o15, columns=["ts","open","high","low","close","vol"])
        df1h = pd.DataFrame(o1h, columns=["ts","open","high","low","close","vol"])
        for df in [df5,df15,df1h]:
            df["ema7"]=df["close"].ewm(span=7).mean()
            df["ema25"]=df["close"].ewm(span=25).mean()
            df["ema99"]=df["close"].ewm(span=99).mean()
            df["sma200"]=df["close"].ewm(span=200).mean()
            delta=df["close"].diff()
            gain=delta.where(delta>0,0).rolling(14).mean()
            loss=-delta.where(delta<0,0).rolling(14).mean()
            rs=gain/loss.replace(0,0.001)
            df["rsi"]=100-(100/(1+rs))
            ema12=df["close"].ewm(span=12).mean()
            ema26=df["close"].ewm(span=26).mean()
            df["macd"]=ema12-ema26
            df["macd_signal"]=df["macd"].ewm(span=9).mean()
            df["macd_hist"]=df["macd"]-df["macd_signal"]
            df["vol_avg20"]=df["vol"].rolling(20).mean()
            df["atr"]=(df["high"]-df["low"]).rolling(14).mean()
            df["sma20"]=df["close"].rolling(20).mean()
            df["std20"]=df["close"].rolling(20).std()
            df["boll_upper"]=df["sma20"]+2*df["std20"]
            df["boll_lower"]=df["sma20"]-2*df["std20"]
        last5,last15,last1h,prev1h = df5.iloc[-1],df15.iloc[-1],df1h.iloc[-1],df1h.iloc[-2]
        ticker=exchange.fetch_ticker(symbol)
        spread=(ticker["ask"]-ticker["bid"])/ticker["ask"]*100 if ticker["ask"] and ticker["bid"] else 0
        if spread>0.15: return None
        change24h=ticker.get("percentage",0) or 0
        if abs(change24h)<3: return None
        momentum=(last1h["close"]-prev1h["close"])/prev1h["close"]*100
        if abs(momentum)<0.5: return None
        is_crash_short=change24h<=-12 or momentum<=-3
        is_crash_long=change24h>=12 or momentum>=3
        is_crash=is_crash_short or is_crash_long
        ema_dist=abs(last1h["close"]-last1h["ema7"])/last1h["close"]*100
        if ema_dist>3.5 and not is_crash: return None
        long_stack=last1h["ema7"]>last1h["ema25"]>last1h["ema99"] and last1h["close"]>last1h["sma200"]
        short_stack=last1h["ema7"]<last1h["ema25"]<last1h["ema99"] and last1h["close"]<last1h["sma200"]
        if not (long_stack or short_stack): return None
        direction="LONG" if long_stack else "SHORT"
        if not is_crash:
            if direction=="LONG":
                if not (last5["ema7"]>last5["ema25"] and last15["ema7"]>last15["ema25"]): return None
            else:
                if not (last5["ema7"]<last5["ema25"] and last15["ema7"]<last15["ema25"]): return None
        if not is_crash:
            if direction=="LONG":
                if not (55<=last1h["rsi"]<=75 and last1h["macd_hist"]>0): return None
            else:
                if not (20<=last1h["rsi"]<=45 and last1h["macd_hist"]<0): return None
        vol_ratio=last1h["vol"]/last1h["vol_avg20"] if last1h["vol_avg20"]>0 else 0
        if vol_ratio<1.1: return None
        funding=fetch_funding(exchange,symbol)
        if direction=="LONG" and funding>0.01: return None
        if direction=="SHORT" and funding<-0.01: return None
        boll_range=last5["boll_upper"]-last5["boll_lower"]
        boll_pos=0.5
        if boll_range>0:
            boll_pos=(last5["close"]-last5["boll_lower"])/boll_range
            if direction=="LONG" and boll_pos>0.6 and not is_crash_long: return None
            if direction=="SHORT" and boll_pos<0.4 and not is_crash_short: return None
        score=70
        if vol_ratio>=1.5: score+=5
        if vol_ratio>=1.8: score+=7
        if vol_ratio>=2.2: score+=5
        if abs(momentum)>=1.0: score+=5
        if abs(momentum)>=1.5: score+=5
        if is_crash: score=95
        if score<85: return None
        if 85<=score<=89 and vol_ratio<1.8: return None
        lev="5x CRASH" if score>=95 else ("5x MEDIUM" if score>=93 else "3x LOW")
        atr=last1h["atr"] if pd.notna(last1h["atr"]) else last1h["close"]*0.02
        return {"symbol":symbol,"direction":direction,"score":score,"vol_ratio":round(vol_ratio,2),
                "momentum":round(momentum,2),"funding":funding,"boll_pos":round(boll_pos,2),
                "rsi":round(last1h["rsi"],1),"price":last1h["close"],"atr":atr,"lev":lev}
    except: return None

def main():
    start=time.time()
    try:
        exchange=ccxt.okx({"enableRateLimit":True, "options":{"defaultType":"swap"}})
        exchange.load_markets()
        
        tickers=exchange.fetch_tickers()
        # OKX perp symbols end with :USDT and are swap
        usdt_perps={s:t for s,t in tickers.items() if ":USDT" in s and t.get("quoteVolume") is not None}
        sorted_syms=sorted(usdt_perps.items(), key=lambda x: x[1]["quoteVolume"] or 0, reverse=True)
        symbols=[s for s,_ in sorted_syms[:80] if "BTC" not in s][:80]
        # Ensure BTC for trend exists
        btc_sym="BTC/USDT:USDT"
        if btc_sym not in tickers:
            btc_sym="BTC/USDT"

        btc_trend=get_btc_trend(exchange)
        send_telegram(f"✅ BOT ALIVE - v2.3 OKX ONLY | BTC {btc_trend} | Scanning {len(symbols)} coins | Vol 1.1x + Funding + BOLL")

        results=[]
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures={executor.submit(analyze_coin,exchange,sym,btc_trend): sym for sym in symbols}
            for fut in concurrent.futures.as_completed(futures):
                r=fut.result()
                if r: results.append(r)
        results=sorted(results, key=lambda x: x["score"], reverse=True)[:3]
        for r in results:
            sl=r["price"]-r["atr"]*1.5 if r["direction"]=="LONG" else r["price"]+r["atr"]*1.5
            tp=r["price"]+r["atr"]*3 if r["direction"]=="LONG" else r["price"]-r["atr"]*3
            msg=(f"🚀 SIGNAL {r['direction']} {r['symbol']}\n"
                 f"Score:{r['score']} Vol:{r['vol_ratio']}x Mom:{r['momentum']}%\n"
                 f"RSI:{r['rsi']} BOLL:{r['boll_pos']} Funding:{r['funding']*100:.4f}%\n"
                 f"Price:{r['price']}\nSL:{sl:.4f} TP:{tp:.4f}\nLev:{r['lev']} BTC:{btc_trend} Ex:OKX")
            send_telegram(msg)
        print(f"Done {len(results)} signals in {time.time()-start:.1f}s using OKX")
    except Exception as e:
        print(traceback.format_exc())
        send_telegram(f"❌ BOT ERROR OKX: {str(e)[:300]}")

if __name__=="__main__": main()
