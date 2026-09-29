import os
import ccxt
import time
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID: return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"TG error {e}")

# ===== 70/100 SETTINGS =====
MIN_5M_CHANGE = 3.8
MIN_24H_CHANGE = 2.0
MIN_VOLUME_SPIKE = 2.1
MIN_VOL_USDT = 800000
BTC_MAX_DUMP = -1.2

# FIX: Use OKX instead of Binance - no 451 block on GitHub
exchange = ccxt.okx({'enableRateLimit': True})
# Fallback if OKX fails: bybit
exchange_fallback = ccxt.bybit({'enableRateLimit': True})

found = 0

try:
    # Try OKX first
    try:
        btc = exchange.fetch_ticker('BTC/USDT')
        print("Using OKX exchange - OK")
    except:
        exchange = exchange_fallback
        btc = exchange.fetch_ticker('BTC/USDT')
        print("OKX failed, using Bybit - OK")

    btc_24 = btc.get('percentage', 0) or 0
    print(f"BTC 24h: {btc_24:.2f}%")

    if btc_24 < BTC_MAX_DUMP:
        print(f"BTC dumping {btc_24:.2f}% - skipping")
        print(f"Done. Found 0")
        raise SystemExit

    tickers = exchange.fetch_tickers()
    usdt = {k: v for k, v in tickers.items() if '/USDT' in k}
    top = sorted(usdt.items(), key=lambda x: (x[1].get('quoteVolume', 0) or 0), reverse=True)[:60]
    coins = [c[0] for c in top]
    print(f"Scanning {len(coins)} coins on {exchange.id}...")

    for symbol in coins:
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
            change_24h = ticker.get('percentage', 0) or 0
            vol_usdt = ticker.get('quoteVolume', 0) or 0

            if change_5m >= MIN_5M_CHANGE and change_24h >= MIN_24H_CHANGE and vol_spike >= MIN_VOLUME_SPIKE and vol_usdt >= MIN_VOL_USDT:
                if ohlcv[-1][4] < ohlcv[-1][1]: continue
                if ohlcv[-2][4] < ohlcv[-2][1]: continue

                found += 1
                msg = f"""⚡ *QUALITY PUMP 70/100* ⚡

*Coin:* `{symbol}` on {exchange.id.upper()}
*5m:* +{change_5m:.2f}% | *24h:* +{change_24h:.2f}%
*Vol Spike:* {vol_spike:.1f}x | *Vol:* ${vol_usdt/1e6:.1f}M
*BTC:* {btc_24:+.2f}%

`@Herocallss`
"""
                send_telegram(msg)
                time.sleep(1.2)
                if found >= 2: break

        except:
            continue

    print(f"Done. Found {found}")
    if found == 0:
        print("No trend found - market sideways, will try next run")

except Exception as e:
    print(f"Bot error: {e}")
    print(f"Done. Found {found}")
