import ccxt, time, os, requests
from datetime import datetime, timezone

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_text(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=15)
    print(f"Telegram: {r.status_code} ok={r.json().get('ok')}")
    return r

def get_ex(name):
    try:
        ex = getattr(ccxt, name)({'enableRateLimit': True})
        ex.load_markets()
        return ex
    except:
        return None

def scan_fast(ex, limit=150):
    found=[]
    try:
        tickers = ex.fetch_tickers()
        candidates=[]
        for symbol, t in tickers.items():
            if '/USDT' not in symbol: continue
            qv = t.get('quoteVolume',0) or 0
            ch = t.get('percentage',0) or 0
            if qv < 800000: continue
            if abs(ch) < 3.5: continue
            candidates.append((symbol, ch, qv))
        candidates = sorted(candidates, key=lambda x: abs(x[1]), reverse=True)[:limit]
        print(f"{ex.id} pre-filter: {len(candidates)} from {len(tickers)}")
        for symbol, ch, qv in candidates:
            try:
                ohlcv = ex.fetch_ohlcv(symbol, '5m', limit=20)
                if len(ohlcv)<20: continue
                last = ohlcv[-1][4]
                vol_last = ohlcv[-1][5]
                vol_avg = sum(v[5] for v in ohlcv[-6:-1])/5
                vol_mult = vol_last/vol_avg if vol_avg else 0
                if vol_mult < 2.0: continue
                ema7 = sum(v[4] for v in ohlcv[-7:])/7
                side = "LONG" if last>ema7 and ch>0 else "SHORT" if last<ema7 and ch<0 else None
                if not side: continue
                score = 50
                if abs(ch) >= 3.8: score+=10
                if abs(ch) >= 5.0: score+=10
                if vol_mult >= 2.5: score+=10
                if vol_mult >= 3.5: score+=10
                if qv > 2000000: score+=10
                score = min(score, 99)
                if score < 70: continue
                entry = last
                if side=="LONG":
                    tp1=entry*1.015; tp2=entry*1.03; tp3=entry*1.05; sl=entry*0.97
                else:
                    tp1=entry*0.985; tp2=entry*0.97; tp3=entry*0.95; sl=entry*1.03
                found.append({'symbol': symbol.replace('/',''), 'side': side, 'entry': entry, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'sl': sl, 'score': score})
                if len(found)>=5: break
            except:
                continue
    except Exception as e:
        print(f"{ex.id} {e}")
    return found

def main():
    okx = get_ex('okx')
    gate = get_ex('gate')
    bitget = get_ex('bitget')
    all_coins=[]; total=0
    for ex in [okx, gate, bitget]:
        if ex:
            print(f"Using {ex.id.upper()} - OK")
            r=scan_fast(ex,150)
            print(f"{ex.id.upper()} pumps: {len(r)}")
            all_coins.extend(r); total+=150; time.sleep(1)

    print(f"Done. Found {len(all_coins)} from {total}")

    now = datetime.now(timezone.utc)
    lagos_hour = (now.hour + 1) % 24
    if lagos_hour in [9, 15, 21] and now.minute < 10:
        send_text(f"✅ Bot Alive - {total}/450 active\nScanning OKX+GATE+BITGET - 70/100 strict\nTime: {lagos_hour}:00 Lagos - Running")

    if not all_coins: return

    for c in sorted(all_coins, key=lambda x: x['score'], reverse=True)[:2]:
        icon = "🔴 SHORT" if c['side']=="SHORT" else "🟢 LONG"
        caption = f"""🚀 FUTURE CALLS - Herocallss 🚀

🌐 Coin: {c['symbol']}
📊 Signal: {icon}
⚡ Leverage: 10x Isolated
⭐ Score: {c['score']}/100

🔵 ENTRY:
{round(c['entry'],6) if c['entry']<1 else round(c['entry'],4)}

🟢 Take Profit:
TP1: {round(c['tp1'],6) if c['tp1']<1 else round(c['tp1'],4)}
TP2: {round(c['tp2'],6) if c['tp2']<1 else round(c['tp2'],4)}
TP3: {round(c['tp3'],6) if c['tp3']<1 else round(c['tp3'],4)}

🔴 Stop Loss:
SL: {round(c['sl'],6) if c['sl']<1 else round(c['sl'],4)}

⏰ {now.strftime('%Y-%m-%d %H:%M UTC')}
⚠️ Risk 1-2% per trade.
@Herocallss
"""
        send_text(caption)

if __name__=="__main__":
    main()
