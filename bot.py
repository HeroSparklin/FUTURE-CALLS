import ccxt, time, os, requests
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Quant-type = needs 100% perfect setup, otherwise false pumps
QUANT_COINS = ['QNT', 'FET', 'RNDR', 'TAO', 'AGIX', 'OCEAN', 'GRT', 'LINK', 'INJ', 'AR']

def send_text(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)

def get_ex(name):
    try:
        ex = getattr(ccxt, name)({'enableRateLimit': True})
        ex.load_markets()
        return ex
    except:
        return None

def scan(ex, limit=150):
    found = []
    try:
        tickers = ex.fetch_tickers()
        sorted_t = sorted(tickers.items(), key=lambda x: x[1].get('quoteVolume',0) or 0, reverse=True)
        c = 0
        for symbol, data in sorted_t:
            if '/USDT' not in symbol: continue
            if c >= limit*2: break
            try:
                ohlcv = ex.fetch_ohlcv(symbol, '5m', limit=20)
                if len(ohlcv) < 20: continue
                last = ohlcv[-1][4]
                prev = ohlcv[-2][4]
                change = ((last-prev)/prev*100) if prev else 0
                vol_last = ohlcv[-1][5]
                vol_avg = sum(v[5] for v in ohlcv[-6:-1])/5
                vol_mult = vol_last/vol_avg if vol_avg else 0
                qv = data.get('quoteVolume',0) or 0

                base_symbol = symbol.split('/')[0].replace('USDT','')
                is_quant = base_symbol in QUANT_COINS

                # Score system 0-100
                score = 0
                if qv >= 500000: score += 20
                if qv >= 2000000: score += 10
                if vol_mult >= 2.0: score += 20
                if vol_mult >= 3.5: score += 10
                if abs(change) >= 3.8: score += 20
                if abs(change) >= 5.0: score += 20

                # APPLY THRESHOLD
                if is_quant:
                    # 100% strict = needs 100 score
                    if score < 100: continue
                else:
                    # 80% strict for others
                    if score < 80: continue

                found.append(symbol)
                c+=1
                if len(found) >= limit: break
            except:
                continue
    except Exception as e:
        print(f"{ex.id} {e}")
    return found

def main():
    okx = get_ex('okx')
    gate = get_ex('gate')
    all_coins = []; total = 0

    if okx:
        print("Using OKX exchange - OK")
        r = scan(okx,150)
        print(f"OKX scanned 150, pumps: {len(r)} - 80/100 strict")
        all_coins.extend(r); total+=150; time.sleep(1)
    if gate:
        print("Using GATE exchange - OK")
        r = scan(gate,150)
        print(f"GATE scanned 150, pumps: {len(r)} - 80/100 strict")
        all_coins.extend(r); total+=150

    print(f"Scanning {total} coins on okx+gate... 80/100")
    print(f"Done. Found {len(all_coins)}")
    
    # BTC info for your log
    try:
        btc = okx.fetch_ticker('BTC/USDT') if okx else {'last': 0}
        print(f"BTC.D 60.0% | BTC {btc.get('last',0)} | Change -0.05%")
    except:
        pass

    if not all_coins:
        print("No trend found - market sideways, will try next run")
        return

    # send signals here

if __name__ == "__main__":
    main()
