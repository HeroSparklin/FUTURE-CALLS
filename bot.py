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

# ===== 70/100 STRICT SETTINGS =====
MIN_5M_CHANGE = 3.8      # 45/100 was 2.5% | 90/100 was 8% | 70/100 = 3.8%
MIN_24H_CHANGE = 2.0     # must be green on day
MIN_VOLUME_SPIKE = 2.1   # 45/100 was 1.6x | 90/100 was 3x | 70/100 = 2.1x
MIN_VOL_USDT = 1000000   # $1M+ only - filters shitcoins
BTC_MAX_DUMP = -1.2      # Pause only if BTC < -1.2%

exchange = ccxt.binance({'enableRateLimit': True})
found = 0

try:
    btc = exchange.fetch_ticker('BTC/USDT')
    btc_24 = btc.get('percentage', 0) or 0
    print(f"BTC 24h: {btc_24:.2f}%")

    if btc_24 < BTC_MAX_DUMP:
        print(f"BTC dumping {btc_24:.2f}% - skipping")
        print(f"Done. Found 0")
        print(f"No trend found - BTC weak")
        raise SystemExit

    # Get top coins by volume
    tickers = exchange.fetch_tickers()
    usdt = {k: v for k, v in tickers.items() if k.endswith('/USDT') and not k.startswith('USDC')}
    top = sorted(usdt.items(), key=lambda x: (x[1].get('quoteVolume', 0) or 0), reverse=True)[:60]
    coins = [c[0] for c in top]
    print(f"Scanning {len(coins)} coins for 70/100 setup...")

    for symbol in coins:
        try:
            # Get 5m candles for accurate pump detection
            ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=20)
            if len(ohlcv) < 20: continue

            close_now = ohlcv[-1][4]
            close_prev = ohlcv[-2][4]
            change_5m = ((close_now - close_prev) / close_prev) * 100

            # Volume spike calculation
            vol_now = ohlcv[-1][5]
            vol_avg = sum([c[5] for c in ohlcv[-11:-1]]) / 10
            vol_spike = vol_now / vol_avg if vol_avg > 0 else 0

            ticker = usdt.get(symbol, {})
            change_24h = ticker.get('percentage', 0) or 0
            vol_usdt = ticker.get('quoteVolume', 0) or 0

            # 70/100 FILTER - ALL must pass
            if change_5m >= MIN_5M_CHANGE and change_24h >= MIN_24H_CHANGE and vol_spike >= MIN_VOLUME_SPIKE and vol_usdt >= MIN_VOL_USDT:
                
                # Extra quality filter: last 2 candles must be green (momentum)
                if ohlcv[-1][4] < ohlcv[-1][1]: continue # last candle not green
                if ohlcv[-2][4] < ohlcv[-2][1]: continue # prev candle not green

                found += 1
                msg = f"""⚡ *QUALITY PUMP 70/100* ⚡

*Coin:* `{symbol}`
*5m:* +{change_5m:.2f}% | *24h:* +{change_24h:.2f}%
*Vol Spike:* {vol_spike:.1f}x | *Vol:* ${vol_usdt/1e6:.1f}M
*BTC:* {btc_24:+.2f}%

Momentum confirmed 2 candles.
`@Herocallss`

Not financial advice.
"""
                send_telegram(msg)
                time.sleep(1.2)
                if found >= 2: break # Max 2 signals per 5min run - very selective

        except Exception as e:
            continue

    print(f"Done. Found {found}")
    if found == 0:
        print("No trend found - market sideways, will try next run")

except Exception as e:
    print(f"Bot error: {e}")
    print(f"Done. Found {found}")
