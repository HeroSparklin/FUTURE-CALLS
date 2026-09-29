import ccxt
import time
import os
import requests
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
CHANNEL = "@Herocallss"

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN/CHAT_ID")
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_exchange(name):
    try:
        ex = getattr(ccxt, name)({'enableRateLimit': True})
        ex.load_markets()
        return ex
    except Exception as e:
        print(f"{name} failed: {e}")
        return None

def scan_exchange(exchange, limit=150):
    coins = []
    try:
        tickers = exchange.fetch_tickers()
        # sort by quote volume
        sorted_tickers = sorted(tickers.items(), key=lambda x: x[1].get('quoteVolume', 0) or 0, reverse=True)
        count = 0
        for symbol, data in sorted_tickers:
            if count >= limit: break
            if '/USDT' not in symbol: continue
            if 'BTC' in symbol or 'ETH' in symbol: continue
            try:
                # get 5m candles
                ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=6)
                if len(ohlcv) < 6: continue
                # calculate 5m change
                last_close = ohlcv[-1][4]
                prev_close = ohlcv[-2][4]
                change_5m = ((last_close - prev_close) / prev_close) * 100 if prev_close else 0

                # volume spike
                last_vol = ohlcv[-1][5]
                avg_vol = sum(c[5] for c in ohlcv[-6:-1]) / 5
                vol_mult = last_vol / avg_vol if avg_vol else 0

                # 70/100 quality filters (anti-rug)
                quote_vol = data.get('quoteVolume', 0) or 0
                if quote_vol < 500000: continue # min $500k 24h vol
                if change_5m < 3.8: continue
                if vol_mult < 2.0: continue

                # liquidity check via 24h volume is our rug protection
                score = 70
                if change_5m >= 5: score += 10
                if vol_mult >= 3: score += 10
                if quote_vol > 2000000: score += 10
                score = min(score, 100)

                coins.append({
                    'symbol': symbol,
                    'exchange': exchange.id,
                    'change': change_5m,
                    'vol_mult': vol_mult,
                    'score': score,
                    'price': last_close
                })
                count += 1
            except:
                continue
    except Exception as e:
        print(f"Scan error {exchange.id}: {e}")
    return coins

def main():
    okx = get_exchange('okx')
    gate = get_exchange('gate')

    all_found = []
    total_scanned = 0

    if okx:
        print("Using OKX exchange - OK")
        okx_coins = scan_exchange(okx, 150)
        total_scanned += 150
        # filter to only pumps
        all_found.extend([c for c in okx_coins if c['change'] >= 3.8])
        print(f"OKX scanned 150, pumps: {len(okx_coins)}")
        time.sleep(2)

    if gate:
        print("Using GATE exchange - OK")
        gate_coins = scan_exchange(gate, 150)
        total_scanned += 150
        all_found.extend([c for c in gate_coins if c['change'] >= 3.8])
        print(f"GATE scanned 150, pumps: {len(gate_coins)}")

    print(f"Scanning {total_scanned} coins on okx+gate... 70/100")
    print(f"Done. Found {len(all_found)}")

    # Heartbeat 9am Lagos = 8am UTC
    now = datetime.now(timezone.utc)
    if now.hour == 8 and now.minute < 10:
        send_telegram(f"✅ Bot Alive - {total_scanned}/100 active\nScanning OKX+GATE ({total_scanned} coins)")

    if not all_found:
        print("No trend found - market sideways, will try next run")
        return

    # Send signals
    for coin in sorted(all_found, key=lambda x: x['score'], reverse=True)[:3]:
        msg = f"🚀 *{coin['symbol']}* | {coin['exchange'].upper()}\n"
        msg += f"Change 5m: +{coin['change']:.2f}%\n"
        msg += f"Vol: {coin['vol_mult']:.1f}x | Score: {coin['score']}/100\n"
        msg += f"Price: ${coin['price']}\n"
        msg += f"#{coin['symbol'].replace('/','')} #pump"
        send_telegram(msg)
        print(f"Sent: {coin['symbol']}")
        time.sleep(1)

if __name__ == "__main__":
    main()
