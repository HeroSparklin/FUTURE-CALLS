# wake up scheduler - commit to main
import os, ccxt, requests, time
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN or CHAT_ID")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        r = requests.post(url, data=data, timeout=15)
        print(f"Telegram status: {r.status_code} | {r.text[:200]}")
    except Exception as e:
        print(f"Telegram error: {e}")

def main():
    try:
        exchange = ccxt.okx({'enableRateLimit': True})
        print("Using OKX exchange - OK", end=" | ")

        # BTC 24h check
        try:
            btc = exchange.fetch_ticker('BTC/USDT')
            btc_24 = btc.get('percentage', 0) or 0
            print(f"BTC 24h: {btc_24:.2f}%")
        except:
            btc_24 = 0
            print("BTC 24h: 0.00%")

        # Get top 150 coins by volume
        markets = exchange.load_markets()
        tickers = exchange.fetch_tickers()
        usdt_tickers = [k for k in tickers if '/USDT' in k and tickers[k].get('quoteVolume')]
        sorted_coins = sorted(usdt_tickers, key=lambda x: tickers[x]['quoteVolume'] or 0, reverse=True)[:150]

        print(f"Scanning 150 coins on okx... 70/100")

        found = 0
        near_misses = []

        for symbol in sorted_coins:
            try:
                # Fetch last 25 5m candles
                ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=25)
                if len(ohlcv) < 24:
                    continue

                # Current 5m change
                last_close = ohlcv[-1][4]
                prev_close = ohlcv[-2][4]
                change_5m = ((last_close - prev_close) / prev_close) * 100

                # Volume spike check
                last_vol = ohlcv[-1][5]
                avg_vol = sum(c[5] for c in ohlcv[-20:-1]) / 19
                vol_mult = last_vol / avg_vol if avg_vol > 0 else 0

                # 1H trend
                change_1h = ((ohlcv[-1][4] - ohlcv[-12][4]) / ohlcv[-12][4]) * 100 if len(ohlcv) >= 12 else 0

                # 70/100 LOGIC
                # Need +3.8% in 5m + 2.0x volume + uptrend
                if change_5m >= 3.8 and vol_mult >= 2.0 and change_1h > 0:
                    found += 1
                    price = last_close
                    msg = f"🚀 *70/100 PUMP DETECTED*\n\nCoin: `{symbol}`\n5m: +{change_5m:.2f}%\n1h: +{change_1h:.2f}%\nVol: {vol_mult:.1f}x avg\nPrice: {price}\n\nExchange: OKX\n@Herocallss"
                    send_telegram(msg)
                    time.sleep(1)

                # Track near misses for debug
                if change_5m >= 2.0:
                    near_misses.append(f"{symbol} +{change_5m:.1f}%")

            except Exception as e:
                continue

        print(f"Done. Found {found}")
        if found == 0:
            print("No trend found - market sideways, will try next run")
            now_utc = datetime.now(timezone.utc)
            print(f"Current UTC: {now_utc.hour}:{now_utc.minute} | near_misses: {len(near_misses)}")
            # HEARTBEAT: 9:00-9:10 Lagos = 8:00-8:10 UTC - send even if near_misses exist
            if now_utc.hour == 8 and now_utc.minute < 10:
                print("Sending heartbeat...")
                send_telegram(f"✅ *Bot Alive - 70/100 active*\nScanned 150 coins on OKX\nBTC {btc_24:+.2f}% | Market sideways, no 70/100 setup yet.\nNext scan in 5m. @Herocallss")

    except Exception as e:
        print(f"Fatal error: {e}")
        # send_telegram(f"⚠️ Bot error: {e}")

if __name__ == "__main__":
    main()
