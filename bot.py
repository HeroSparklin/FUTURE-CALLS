import os, ccxt, requests, time
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try: requests.post(url, data=data, timeout=15)
    except: pass

def main():
    try:
        exchange = ccxt.okx({'enableRateLimit': True})
        print("Using OKX exchange - OK", end=" | ")
        try:
            btc = exchange.fetch_ticker('BTC/USDT')
            btc_24 = btc.get('percentage', 0) or 0
            print(f"BTC 24h: {btc_24:.2f}%")
        except:
            btc_24 = 0
            print("BTC 24h: 0.00%")

        tickers = exchange.fetch_tickers()
        usdt = [k for k in tickers if '/USDT' in k and tickers[k].get('quoteVolume')]
        coins = sorted(usdt, key=lambda x: tickers[x]['quoteVolume'] or 0, reverse=True)[:150]
        print(f"Scanning 150 coins on okx... 70/100")

        found = 0
        for symbol in coins:
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=25)
                if len(ohlcv) < 24: continue
                last_close = ohlcv[-1][4]
                prev_close = ohlcv[-2][4]
                change_5m = ((last_close - prev_close) / prev_close) * 100
                last_vol = ohlcv[-1][5]
                avg_vol = sum(c[5] for c in ohlcv[-20:-1]) / 19
                vol_mult = last_vol / avg_vol if avg_vol > 0 else 0
                change_1h = ((ohlcv[-1][4] - ohlcv[-12][4]) / ohlcv[-12][4]) * 100

                if change_5m >= 3.8 and vol_mult >= 2.0 and change_1h > 0:
                    found += 1
                    msg = f"🚀 *70/100 PUMP*\n\nCoin: `{symbol}`\n5m: +{change_5m:.2f}%\n1h: +{change_1h:.2f}%\nVol: {vol_mult:.1f}x\nPrice: {last_close}\n@Herocallss"
                    send_telegram(msg)
                    time.sleep(1)
            except: continue

        print(f"Done. Found {found}")
        if found == 0:
            print("No trend found - market sideways, will try next run")
            now_utc = datetime.now(timezone.utc)
            # Heartbeat 9:00 Lagos = 8:00 UTC - will ALWAYS send now
            if now_utc.hour == 8 and now_utc.minute < 10:
                send_telegram(f"✅ *Bot Alive - 70/100 active*\nScanned 150 coins\nBTC {btc_24:+.2f}% | No setup yet\nNext scan in 5m @Herocallss")
    except Exception as e:
        print(f"Fatal: {e}")

if __name__ == "__main__":
    main()
