import requests, os

# CONFIG - 80/100 STRICT - ALL BYBIT FUTURES
MIN_SCORE = 80
MIN_VOL = 2000000
MAJORS = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT"]

def get_tickers():
    url = "https://api.bybit.com/v5/market/tickers?category=linear"
    return requests.get(url, timeout=10).json()['result']['list']

def calc(t):
    try:
        last = float(t['lastPrice'])
        change = float(t['price24hPcnt'])*100
        vol = float(t['turnover24h'])
        high = float(t['highPrice24h'])
        low = float(t['lowPrice24h'])
        vol24 = ((high-low)/low*100) if low else 0
        if vol < MIN_VOL: return None
        if vol24 < 3: return None
        score = 0
        if vol > 50000000: score+=30
        elif vol > 10000000: score+=20
        else: score+=15
        if vol24 > 15: score+=40
        elif vol24 > 8: score+=30
        else: score+=20
        if abs(change) > 10: score+=30
        elif abs(change) > 5: score+=20
        else: score+=10
        score = min(score,100)
        if score < MIN_SCORE: return None
        
        is_major = t['symbol'] in MAJORS
        direction = "LONG" if change>0 else "SHORT"
        entry = last
        lev = 5 if is_major else 10
        tp1 = entry*1.02 if direction=="LONG" else entry*0.98
        tp2 = entry*1.045 if direction=="LONG" else entry*0.955
        sl = entry*0.985 if direction=="LONG" else entry*1.015
        
        return f"🔥 {t['symbol']} {score}/100 STRICT {direction}\nENTRY: {entry}\nLEV: {lev}x Isolated\nTP1: {tp1:.4f} (+2%) TP2: {tp2:.4f} (+4.5%)\nSL: {sl:.4f}\nVol: {vol24:.1f}% Change: {change:.1f}%"
    except:
        return None

def main():
    print("Fetching Bybit Futures...")
    tickers = get_tickers()
    print(f"Got {len(tickers)} tickers")
    found=0
    for t in tickers:
        if not t['symbol'].endswith('USDT'): continue
        sig = calc(t)
        if sig:
            print(sig)
            print("---")
            found+=1
            if found>=10: break
    if found==0:
        print("No 80/100 signals this scan - market quiet, this is normal for strict mode")

if __name__=="__main__":
    main()
