# wake up scheduler - commit to main
import os, ccxt, requests
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"TG error: {e}")

# ===== 70/100 STRICT - 150 COINS =====
MIN_5M_CHANGE = 3.8
MIN_24H_CHANGE = 2.0
MIN_VOLUME_SPIKE = 2.1
MIN_VOL_USDT = 800000
BTC_MAX_DUMP = -1.2

exchange = ccxt.okx({'enableRateLimit': True})
found = 0
near_misses = []

try:
    btc = exchange.fetch_ticker('BTC/USDT')
    btc_24 = btc.get('percentage',0) or 0
    print(f"Using OKX exchange - OK | BTC 24h: {btc_24:.2f}%")

    if btc_24 < BTC_MAX_DUMP:
        print(f"BTC dumping {btc_24:.2f}% - pause")
        print("Done. Found 0")
        raise SystemExit

    tickers = exchange.fetch_tickers()
    usdt = {k:v for k,v in tickers.items() if '/USDT' in k}
    top = sorted(usdt.items(), key=lambda x: (x[1].get('quoteVolume',0) or 0), reverse=True)[:150]

    print(f"Scanning {len(top)} coins on okx... 70/100")

    for symbol in [c[0] for c in top]:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=20)
            if len(ohlcv) < 20: continue

            close_now = ohlcv[-1][4]
            close_prev = ohlcv[-2][4]
            change_5m = ((close_now - close_prev) / close_prev) * 100

            vol_now = ohlcv[-1][5]
            vol_avg = sum([c[5] for c in ohlcv[-11:-1]]) / 10
            vol_spike = vol_now / vol_avg if vol_avg > 0 else 0

            ticker = usdt.get(symbol, {})
            change_24h = ticker.get('percentage',0) or 0
            vol_usdt = ticker.get('quoteVolume',0) or 0

            # Track near misses to show bot is alive
            if change_5m >= 2.0 and vol_spike >= 1.4:
                near_misses.append(f"{symbol} {change_5m:.1f}%/{vol_spike:.1f}x")

            if change_5m >= MIN_5M_CHANGE and change_24h >= MIN_24H_CHANGE and vol_spike >= MIN_VOLUME_SPIKE and vol_usdt >= MIN_VOL_USDT:
                if ohlcv[-1][4] < ohlcv[-1][1]: continue
                if ohlcv[-2][4] < ohlcv[-2][1]: continue

                found += 1
                msg = f"""⚡ *70/100 PUMP* ⚡

*Coin:* `{symbol}`
*5m:* +{change_5m:.2f}% | *24h:* +{change_24h:.2f}%
*Vol Spike:* {vol_spike:.1f}x | *Vol:* ${vol_usdt/1e6:.1f}M
*BTC:* {btc_24:+.2f}%

`@Herocallss`
"""
                send_telegram(msg)
                if found >= 2: break
        except:
            continue

    if near_misses:
        print(f"Near miss (not 70/100): {', '.join(near_misses[:6])}")

    print(f"Done. Found {found}")
    if found == 0:
        print("No trend found - market sideways, will try next run")
        hour = datetime.now(timezone.utc).hour
        if hour == 8 and len(near_misses) == 0:
            send_telegram(f"✅ Bot Alive - 70/100 scan active | 150 coins scanned | BTC {btc_24:+.2f}% | Market sideways, no quality setup. Next scan in 5m.")

except Exception as e:
    print(f"Bot error: {e}")
    print(f"Done. Found {found}")
