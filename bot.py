import os, ccxt, requests
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

# ===== 70/100 STRICT - FINAL =====
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
    top = sorted(usdt.items(), key=lambda x: (x[1].get('quoteVolume',0) or 0), reverse=True)[:60]

    print(f"Scanning 60 coins on okx...")
    for symbol in [c[0] for c in top]:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=20)
            if len(ohlcv) < 20: continue

            change_5m = ((ohlcv[-1][4]-ohlcv[-2][4])/ohlcv[-2][4])*100
            vol_spike = ohlcv[-1][5] / (sum([c[5] for c in ohlcv[-11:-1]])/10) if sum([c[5] for c in ohlcv[-11:-1]])>0 else 0

            t = usdt.get(symbol,{})
            change_24h = t.get('percentage',0) or 0
            vol_usdt = t.get('quoteVolume',0) or 0

            # Log near misses so you see it's alive
            if change_5m >= 2.0 and vol_spike >= 1.4:
                near_misses.append(f"{symbol} {change_5m:.1f}%/{vol_spike:.1f}x")

            if change_5m >= MIN_5M_CHANGE and change_24h >= MIN_24H_CHANGE and vol_spike >= MIN_VOLUME_SPIKE and vol_usdt >= MIN_VOL_USDT:
                if ohlcv[-1][4] < ohlcv[-1][1] or ohlcv[-2][4] < ohlcv[-2][1]: continue
                found +=1
                send_telegram(f"⚡ *70/100 PUMP* ⚡\n\n*Coin:* `{symbol}`\n*5m:* +{change_5m:.2f}% | *24h:* +{change_24h:.2f}%\n*Vol Spike:* {vol_spike:.1f}x\n*BTC:* {btc_24:+.2f}%\n\n`@Herocallss`")
                if found >=2: break
        except: continue

    if near_misses:
        print(f"Near miss (didn't meet 70/100): {', '.join(near_misses[:5])}")

    print(f"Done. Found {found}")
    if found==0:
        print("No trend found - market sideways, will try next run")
        # Heartbeat once at 8am UTC so you know bot is alive
        hour = datetime.now(timezone.utc).hour
        if hour == 8 and len(near_misses)==0:
            send_telegram(f"✅ Bot Alive - 70/100 scan active. BTC {btc_24:+.2f}%. Market sideways, no quality setup. Next scan in 5m.")

except Exception as e:
    print(f"Bot error: {e}")
    print(f"Done. Found {found}")
