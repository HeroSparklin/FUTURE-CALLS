import requests, time, os

MIN_SCORE = 80
MIN_VOL = 2000000
MAJORS = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","TONUSDT"]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

def get_tickers():
    url = "https://api.bybit.com/v5/market/tickers?category=linear"
    for i in range(3): # 3 retries
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            print(f"Status: {r.status_code}, Length: {len(r.text)}")
            if r.status_code != 200:
                print(f"Bybit error: {r.text[:500]}")
                time.sleep(2)
                continue
            data = r.json()
            if 'result' in data and 'list' in data['result']:
                return data['result']['list']
            else:
                print(f"Unexpected JSON: {data}")
                time.sleep(2)
        except Exception as e:
            print(f"Attempt {i+1} failed: {e}")
            print(f"Raw response: {r.text[:500] if 'r' in locals() else 'no response'}")
            time.sleep(3)
    print("Failed to get tickers after 3 tries - Bybit may be rate limiting GitHub IP")
    return []

def calc(t):
    try:
        last = float(t['lastPrice'])
        change = float(t['price24hPcnt'])*100
        vol = float(t['turnover24h'])
        high = float(t['highPrice24h'])
        low = float(t['lowPrice24h'])
        vol24 = ((high-low)/low*100) if low else 0
        if vol < MIN_VOL or vol24 < 3: return None
        
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
        
        if direction=="LONG":
            tp1, tp2, sl = entry*1.02, entry*1.045, entry*0.985
        else:
            tp1, tp2, sl = entry*0.98, entry*0.955, entry*1.015
        
        tag = "BIG PnL 80/100" if score>=90 else "80/100 STRICT"
        return f"{tag} | {t['symbol']} {score}/100 {direction}\nENTRY: {entry}\nLEV: {lev}x Isolated\nTP1: {tp1:.6f} (+2%) TP2: {tp2:.6f} (+4.5%)\nSL: {sl:.6f} (-1.5%)\n24h: {change:.2f}% Vol24: {vol24:.1f}%"
    except Exception as e:
        return None

def main():
    print("=== Bybit Futures 80/100 Strict Scan ===")
    tickers = get_tickers()
    print(f"Scanning {len(tickers)} tickers...")
    count=0
    for t in tickers:
        if not t['symbol'].endswith('USDT'): continue
        if t['symbol'] in ["USDTUSDT","USDCUSDT","DAIUSDT","USDEUSDT"]:
            continue
        sig = calc(t)
        if sig:
            print(sig)
            print("---")
            count+=1
            if count>=10: break
    if count==0:
        print("No 80/100 signals this scan - strict filter, normal.")
        # Don't exit with error - exit 0 so GitHub shows green
    print(f"Done - {count} signals found")

if __name__=="__main__":
    main()
