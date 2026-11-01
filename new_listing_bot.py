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
        ex = getattr(ccxt, name)({'enableRateLimit': True, 'timeout': 8000})
        ex.load_markets()
        return ex
    except:
        return None

def main():
    exs = [('gate', get_ex('gate')), ('mexc', get_ex('mexc'))]
    seen = load_seen()
    new_found = 0
    now_lagos = datetime.now(WAT)
    now_ts = int(datetime.now().timestamp())

    for ex_name, ex in exs:
        if not ex: continue
        try:
            tickers = ex.fetch_tickers()
            # FAST: Only USDT and sort by volume, take top 120
            usdt_tickers = {k:v for k,v in tickers.items() if '/USDT' in k}
            sorted_tickers = sorted(usdt_tickers.items(), key=lambda x: x[1].get('quoteVolume',0) or 0, reverse=True)[:120]
            
            for symbol, ticker in sorted_tickers:
                qv = ticker.get('quoteVolume',0) or 0
                if qv < 20000: continue
                last = ticker.get('last',0) or 0
                if last > 1000: continue
                if '3L' in symbol or '3S' in symbol: continue
                
                change = ticker.get('percentage',0) or 0
                # If no percentage, estimate from open
                if change == 0:
                    try:
                        o = ticker.get('open',0) or 0
                        if o: change = (last-o)/o*100
                    except: pass

                score = 0
                reasons = []
                direction = None

                if qv >= 50000: score+=20
                if qv >= 200000: score+=20; reasons.append("Vol>200k")
                if qv >= 500000: score+=10; reasons.append("Vol>500k")

                if change >= 12 and change <= 200:
                    score+=35; reasons.append(f"Pump +{change:.1f}%")
                    direction = "LONG"
                if change >= 30: score+=10; reasons.append(f"Strong +{change:.0f}%")
                
                if change <= -15:
                    score+=35; reasons.append(f"Dump {change:.1f}%")
                    direction = "SHORT"

                if score < 80 or not direction: continue
                key = f"{symbol}_{direction}"
                if key in seen: continue

                if direction == "LONG":
                    leverage = "5x-10x Isolated" if score>=90 else "3x-5x Isolated"
                    tp1 = last * 2.0; tp2 = last * 4.0; tp3 = last * 9.0; sl = last * 0.70
                    emoji = "🟢 LONG"
                    note = "Phase 1: PUMP"
                else:
                    leverage = "3x-5x Isolated"
                    tp1 = last * 0.65; tp2 = last * 0.40; tp3 = last * 0.20; sl = last * 1.35
                    emoji = "🔴 SHORT"
                    note = "Phase 2: DUMP"

                msg = f"""🚀 *NEW 10x {direction} - {score}/100* 🚀
*Coin:* `{symbol}` - {ex_name.upper()}
*Signal:* {emoji} | Score {score}/100
*Leverage:* {leverage}
*Phase:* {note}
*Reasons:* {', '.join(reasons)}
*Price:* {last}
*ENTRY:* {round(last,6) if last<1 else round(last,4)}
*TP1:* {round(tp1,6) if tp1<1 else round(tp1,4)}
*TP2:* {round(tp2,6) if tp2<1 else round(tp2,4)}
*TP3:* {round(tp3,6) if tp3<1 else round(tp3,4)}
*SL:* {round(sl,6) if sl<1 else round(sl,4)}
*Vol:* ${int(qv):,}"""
                send_text(msg)
                new_found+=1
                seen.add(key)
                if new_found >= 2: break
        except Exception as e:
            print(f"{ex_name} error {e}")
        if new_found >= 2: break

    # Alive every 6h
    last_alive = load_alive()
    if new_found == 0 and (now_ts - last_alive) >= 21600:
        send_text(f"✅ *NEW-LISTING Bot Alive*\n*Lagos:* {now_lagos.strftime('%H:%M %d-%b')}\nScanning GATE/MEXC - No 80% yet\nLONG+SHORT + Leverage ON")
        save_alive(now_ts)

    save_seen(seen)
    print(f"Done Lagos {now_lagos.strftime('%H:%M')} | Signals {new_found}")

if __name__ == "__main__":
    main()
