import requests, os, time

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MIN_SCORE = 80
HEADERS = {"User-Agent": "Mozilla/5.0"}

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print(text)
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(text)

def get_tickers():
    # OKX SWAP - WORKS FROM US GITHUB - FREE - NO 403/451
    url = "https://www.okx.com/api/v5/market/tickers?instType=SWAP"
    r = requests.get(url, headers=HEADERS, timeout=15)
    print(f"Status: {r.status_code}")
    data = r.json()
    return data['data']  # OKX returns data array

def calc(t):
    try:
        symbol = t['instId']  # e.g. BTC-USDT-SWAP
        if "USDT" not in symbol: return None
        last = float(t['last'])
        change = float(t['sodUtc8']) if 'sodUtc8' in t and t['sodUtc8'] else float(t.get('open24h', last))
        # Calculate % change from open24h
        open24 = float(t['open24h']) if t.get('open24h') else last
        change_pct = ((last - open24) / open24 * 100) if open24 else 0
        vol = float(t['volCcy24h']) if t.get('volCcy24h') else float(t.get('vol24h',0))
        high = float(t['high24h'])
        low = float(t['low24h'])
        vol24 = ((high-low)/low*100) if low else 0
        
        if vol < 1000000: return None
        if vol24 < 2: return None
        if abs(change_pct) < 1.5: return None
        
        score = 0
        if vol > 50000000: score += 30
        elif vol > 10000000: score += 22
        else: score += 15
        if vol24 > 15: score += 40
        elif vol24 > 8: score += 30
        else: score += 20
        if abs(change_pct) > 10: score += 30
        elif abs(change_pct) > 5: score += 22
        else: score += 12
        if score < MIN_SCORE: return None
        
        clean_sym = symbol.replace("-","").replace("SWAP","")  # BTC-USDT-SWAP -> BTCUSDT
        majors = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT"]
        is_major = clean_sym in majors
        direction = "LONG" if change_pct > 0 else "SHORT"
        entry = last
        leverage = 5 if is_major else 10
        
        if direction == "LONG":
            tp1 = entry * 1.02
            tp2 = entry * 1.045
            tp3 = entry * 1.07
            sl = entry * 0.985
        else:
            tp1 = entry * 0.98
            tp2 = entry * 0.955
            tp3 = entry * 0.93
            sl = entry * 1.015
        
        tag = "🔥 BIG PnL" if score >= 90 else "✅ 80/100 STRICT"
        msg = f"""{tag} | {clean_sym} | {direction}

*ENTRY:* `{entry}`
*LEVERAGE:* {leverage}x Isolated

*TP1:* `{tp1:.6f}` (+2%)
*TP2:* `{tp2:.6f}` (+4.5%)
*TP3:* `{tp3:.6f}` (+7%)

*SL:* `{sl:.6f}` (-1.5%)

Score: {score}/100 | 24h: {change_pct:.2f}% | Volat: {vol24:.1f}%
Pair: {symbol} (OKX Futures = Bybit Futures pair)
"""
        return msg
    except Exception as e:
        # print(f"calc error {e} for {t.get('instId')}")
        return None

def main():
    print("=== OKX Futures 80/100 Strict - FREE US GitHub ===")
    tickers = get_tickers()
    print(f"Scanning {len(tickers)} coins")
    sent = 0
    for t in tickers:
        sig = calc(t)
        if sig and sent < 8:
            send_telegram(sig)
            print(sig)
            print("---")
            sent += 1
            time.sleep(0.8)
    if sent == 0:
        print("No 80/100 signals - strict filter, normal")
    print(f"Done - {sent} signals")

if __name__ == "__main__":
    main()
