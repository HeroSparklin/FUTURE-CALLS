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
        print(f"Telegram error: {e}")
        print(text)

def get_tickers():
    url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
    r = requests.get(url, headers=HEADERS, timeout=15)
    print(f"Status: {r.status_code}")
    data = r.json()
    return data

def calc(t):
    try:
        symbol = t['symbol']
        if not symbol.endswith("USDT"): return None
        if symbol in ["USDCUSDT","BUSDUSDT","USDTUSDT"]: return None
        last = float(t['lastPrice'])
        change = float(t['priceChangePercent'])
        vol = float(t['quoteVolume'])
        high = float(t['highPrice'])
        low = float(t['lowPrice'])
        vol24 = ((high-low)/low*100) if low else 0
        if vol < 2000000 or vol24 < 3 or abs(change) < 2: return None
        score = 0
        if vol > 100000000: score += 30
        elif vol > 20000000: score += 22
        else: score += 15
        if vol24 > 15: score += 40
        elif vol24 > 8: score += 30
        else: score += 20
        if abs(change) > 10: score += 30
        elif abs(change) > 5: score += 22
        else: score += 12
        if score < MIN_SCORE: return None
        majors = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT"]
        is_major = symbol in majors
        direction = "LONG" if change > 0 else "SHORT"
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
        msg = f"""{tag} | {symbol} | {direction}

*ENTRY:* `{entry}`
*LEVERAGE:* {leverage}x Isolated

*TP1:* `{tp1:.6f}` (+2%)
*TP2:* `{tp2:.6f}` (+4.5%)
*TP3:* `{tp3:.6f}` (+7%)

*SL:* `{sl:.6f}` (-1.5%)

Score: {score}/100 | 24h: {change:.2f}% | Volat: {vol24:.1f}%
Exchange: Binance Futures (Bybit pair exists)
"""
        return msg
    except:
        return None

def main():
    print("=== Binance Futures 80/100 Strict - FREE GitHub ===")
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
            time.sleep(1)
    if sent == 0:
        print("No 80/100 signals - strict filter, normal")
    print(f"Done - {sent} signals")

if __name__ == "__main__":
    main()
