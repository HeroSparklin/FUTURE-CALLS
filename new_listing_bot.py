import ccxt, os, requests, json
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
WAT = timezone(timedelta(hours=1))
SEEN_FILE = "seen_coins.json"
ALIVE_FILE = "last_alive_new.json"

def load_seen():
    try:
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_seen(seen):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen)[-1000:], f)
    except: pass

def load_alive():
    try:
        with open(ALIVE_FILE, "r") as f:
            return json.load(f).get("last", 0)
    except:
        return 0

def save_alive(ts):
    try:
        with open(ALIVE_FILE, "w") as f:
            json.dump({"last": ts}, f)
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
    direction = None
    try:
        qv = ticker.get('quoteVolume', 0) or 0
        if qv < 20000: return 0, [], 0, None
        if qv >= 50000: score+=15; reasons.append("Vol>50k")
        if qv >= 200000: score+=15; reasons.append("Vol>200k")
        if qv >= 500000: score+=10; reasons.append("Vol>500k")

        try:
            ohlcv = ex.fetch_ohlcv(symbol, '1m', limit=15)
            if len(ohlcv) < 5: return 0, [], 0, None
            first = ohlcv[0][4]
            last = ohlcv[-1][4]
            high = max(c[2] for c in ohlcv)
            if first == 0: return 0, [], 0, None
            pump_pct = ((last - first) / first * 100)
            dump_from_high = ((last - high) / high * 100) if high else 0
            
            if pump_pct >= 10 and pump_pct <= 150:
                score+=25; reasons.append(f"Pump +{pump_pct:.1f}%")
                direction = "LONG"
            if pump_pct >= 30 and pump_pct <= 200:
                score+=10; reasons.append(f"Strong +{pump_pct:.0f}%")
                direction = "LONG"
            
            if dump_from_high <= -15 and pump_pct >= 50:
                score+=25; reasons.append(f"Dump from high {dump_from_high:.1f}%")
                direction = "SHORT"
            if pump_pct <= -12:
                score+=20; reasons.append(f"Crash {pump_pct:.1f}%")
                direction = "SHORT"
                
            if abs(pump_pct) < 10 and dump_from_high > -10: return 0, [], 0, None

            vol_last = ohlcv[-1][5]
            vol_avg = sum(v[5] for v in ohlcv[:-1]) / max(1, len(ohlcv)-1)
            if vol_avg > 0 and vol_last/vol_avg >= 2: score+=15; reasons.append("Vol x2")
        except:
            return 0, [], 0, None

        price = ticker.get('last', 0) or 0
        if price > 1000: return 0, [], 0, None
        if '3L' in symbol or '3S' in symbol: return 0, [], 0, None

        try:
            bid = ticker.get('bid',0) or 0
            ask = ticker.get('ask',0) or 0
            if bid and ask:
                spread = (ask-bid)/ask*100
                if spread > 5: return 0, [], 0, None
                if spread < 1: score+=10; reasons.append("Good liq")
        except: pass

        return score, reasons, pump_pct, direction
    except:
        return 0, [], 0, None

def main():
    exs = [('gate', get_ex('gate')), ('mexc', get_ex('mexc')), ('okx', get_ex('okx'))]
    seen = load_seen()
    new_found = 0
    now_lagos = datetime.now(WAT)
    now_ts = int(datetime.now().timestamp())

    for ex_name, ex in exs:
        if not ex: continue
        try:
            tickers = ex.fetch_tickers()
            for symbol, ticker in tickers.items():
                if '/USDT' not in symbol: continue
                score, reasons, pump_pct, direction = score_new_coin(ex, symbol, ticker)
                if not direction: continue
                key = f"{symbol}_{direction}"
                if key in seen: continue
                if score >= 80 and direction:
                    price = ticker.get('last',0)
                    qv = ticker.get('quoteVolume',0) or 0
                    
                    if direction == "LONG":
                        leverage = "5x-10x Isolated" if score>=90 else "3x-5x Isolated"
                        tp1 = price * 2.0; tp2 = price * 4.0; tp3 = price * 9.0; sl = price * 0.70
                        emoji = "🟢 LONG"
                        note = "Phase 1: PUMP"
                    else:
                        leverage = "3x-5x Isolated"
                        tp1 = price * 0.65; tp2 = price * 0.40; tp3 = price * 0.20; sl = price * 1.35
                        emoji = "🔴 SHORT"
                        note = "Phase 2: DUMP"

                    msg = f"""🚀 *NEW 10x {direction} - {score}/100* 🚀
*Coin:* `{symbol}` - {ex_name.upper()}
*Signal:* {emoji} | Score {score}/100
*Leverage:* {leverage}
*Phase:* {note}
*Reasons:* {', '.join(reasons)}
*Price:* {price}
*ENTRY:* {round(price,6) if price<1 else round(price,4)}
*TP1:* {round(tp1,6) if tp1<1 else round(tp1,4)}
*TP2:* {round(tp2,6) if tp2<1 else round(tp2,4)}
*TP3:* {round(tp3,6) if tp3<1 else round(tp3,4)}
*SL:* {round(sl,6) if sl<1 else round(sl,4)}
*Vol:* ${int(qv):,}"""
                    send_text(msg)
                    new_found+=1
                    seen.add(key)
                    print(f"NEW {direction} {symbol} {score}")
                if new_found >= 3: break
        except Exception as e:
            print(f"{ex_name} error {e}")
        if new_found >= 3: break

    # ALIVE EVERY 6 HOURS - Option B
    last_alive = load_alive()
    if new_found == 0 and (now_ts - last_alive) >= 21600: # 6 hours = 21600 sec
        alive_msg = f"""✅ *NEW-LISTING Bot Alive*
*Lagos:* {now_lagos.strftime('%H:%M %d-%b')}
*Status:* Scanning GATE/MEXC/OKX
*Last check:* No 80% new coin yet
*Next scan:* 5 mins
*System:* LONG+SHORT 80% strict + Leverage ON"""
        send_text(alive_msg)
        save_alive(now_ts)
        print(f"Alive sent - {now_lagos}")

    save_seen(seen)
    print(f"Lagos {now_lagos.strftime('%H:%M')} | Seen {len(seen)} | Signals {new_found}")

if __name__ == "__main__":
    main()
