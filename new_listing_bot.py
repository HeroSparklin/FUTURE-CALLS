import ccxt, os, requests, json
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WAT = timezone(timedelta(hours=1))
SEEN_FILE = "seen_coins.json"

def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_seen(seen):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen)[-500:], f)
    except: pass

def send_text(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def get_ex(name):
    try:
        ex = getattr(ccxt, name)({'enableRateLimit': True, 'timeout': 10000})
        ex.load_markets()
        return ex
    except:
        return None

def score_new_coin(ex, symbol, ticker):
    score = 0
    reasons = []
    try:
        qv = ticker.get('quoteVolume', 0) or 0
        if qv < 20000: return 0, [], 0
        if qv >= 50000: score+=20; reasons.append("Vol>50k")
        if qv >= 200000: score+=20; reasons.append("Vol>200k")
        if qv >= 500000: score+=10; reasons.append("Vol>500k")

        pump_pct = 0
        try:
            ohlcv = ex.fetch_ohlcv(symbol, '1m', limit=10)
            if len(ohlcv) < 3: return 0, [], 0
            first = ohlcv[0][4]
            last = ohlcv[-1][4]
            if first == 0: return 0, [], 0
            pump_pct = ((last - first) / first * 100)
            if pump_pct >= 10: score+=20; reasons.append(f"Pump {pump_pct:.1f}%")
            if pump_pct >= 30: score+=10; reasons.append(f"Strong +{pump_pct:.0f}%")
            if pump_pct < -20: return 0, [], 0
            vol_last = ohlcv[-1][5]
            vol_avg = sum(v[5] for v in ohlcv[:-1]) / max(1, len(ohlcv)-1)
            if vol_avg > 0 and vol_last/vol_avg >= 2: score+=10; reasons.append("Vol x2")
        except:
            try:
                ohlcv = ex.fetch_ohlcv(symbol, '5m', limit=5)
                first = ohlcv[0][4]
                last = ohlcv[-1][4]
                pump_pct = ((last - first) / first * 100) if first else 0
                if pump_pct >= 15: score+=25; reasons.append(f"Pump {pump_pct:.1f}%")
            except:
                return 0, [], 0

        price = ticker.get('last', 0) or 0
        if price > 1000: return 0, [], 0
        if '3L' in symbol or '3S' in symbol or 'BULL' in symbol or 'BEAR' in symbol:
            return 0, [], 0

        try:
            bid = ticker.get('bid',0) or 0
            ask = ticker.get('ask',0) or 0
            if bid and ask:
                spread = (ask-bid)/ask*100
                if spread > 5: return 0, [], 0
                if spread < 1: score+=10; reasons.append("Good liq")
        except: pass

        return score, reasons, pump_pct
    except:
        return 0, [], 0

def main():
    exs = [('gate', get_ex('gate')), ('mexc', get_ex('mexc')), ('okx', get_ex('okx'))]
    seen = load_seen()
    new_found = 0
    now_lagos = datetime.now(WAT)

    for ex_name, ex in exs:
        if not ex: continue
        try:
            tickers = ex.fetch_tickers()
            for symbol, ticker in tickers.items():
                if '/USDT' not in symbol: continue
                if symbol in seen: continue
                score, reasons, pump_pct = score_new_coin(ex, symbol, ticker)
                if score >= 80:
                    price = ticker.get('last',0)
                    qv = ticker.get('quoteVolume',0) or 0
                    
                    if score >= 90:
                        leverage = "5x-10x Isolated"
                        tp1 = price * 2.0
                        tp2 = price * 4.0
                        tp3 = price * 9.0
                        sl = price * 0.70
                    else:
                        leverage = "3x-5x Isolated"
                        tp1 = price * 1.8
                        tp2 = price * 3.0
                        tp3 = price * 6.0
                        sl = price * 0.70

                    msg = f"""🚀 *NEW 10x COIN - {score}/100* 🚀
*Coin:* `{symbol}` - {ex_name.upper()}
*Signal:* 🟢 LONG | Score {score}/100
*Leverage:* {leverage}
*Reasons:* {', '.join(reasons)}
*Price:* {price}
*ENTRY:* {round(price,6) if price<1 else round(price,4)}
*TP1:* {round(tp1,6) if tp1<1 else round(tp1,4)} (+100%)
*TP2:* {round(tp2,6) if tp2<1 else round(tp2,4)} (+300%)
*TP3:* {round(tp3,6) if tp3<1 else round(tp3,4)} (+800%)
*SL:* {round(sl,6) if sl<1 else round(sl,4)} (-30%)
*Vol:* ${int(qv):,}
*Age:* JUST LISTED
⚠️ *New coin - Use $10-$20 only - 80% strict*"""
                    send_text(msg)
                    new_found+=1
                    print(f"NEW 80% + LEV: {symbol} {score} {leverage}")
                seen.add(symbol)
                if new_found >= 2: break
        except Exception as e:
            print(f"{ex_name} error {e}")
        if new_found >= 2: break

    save_seen(seen)
    print(f"Lagos {now_lagos.strftime('%H:%M')} | Seen {len(seen)} | New 80%: {new_found}")

if __name__ == "__main__":
    main()
