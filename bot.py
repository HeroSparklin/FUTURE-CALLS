import ccxt, time, os, requests
from datetime import datetime, timezone, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

QUANT_COINS = ['QNT','FET','RNDR','TAO','AGIX','OCEAN','GRT','LINK','INJ','AR']
WAT = timezone(timedelta(hours=1))

def send_text(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": msg}, timeout=15)
        print(f"Telegram: {r.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

def get_ex(name):
    for _ in range(2):
        try:
            ex = getattr(ccxt, name)({'enableRateLimit': True, 'timeout': 20000})
            ex.load_markets()
            return ex
        except Exception as e:
            print(f"{name} init fail: {e}")
            time.sleep(2)
    return None

def scan(ex, limit=40):
    found=[]
    try:
        tickers = ex.fetch_tickers()
        sorted_t = sorted(tickers.items(), key=lambda x: x[1].get('quoteVolume',0) or 0, reverse=True)
        c=0
        for symbol, data in sorted_t:
            if '/USDT' not in symbol: continue
            if c>=limit: break
            try:
                ohlcv = ex.fetch_ohlcv(symbol, '5m', limit=20)
                if len(ohlcv)<20: continue
                last = ohlcv[-1][4]
                prev = ohlcv[-2][4]
                change = ((last-prev)/prev*100) if prev else 0
                vol_last = ohlcv[-1][5]
                vol_avg = sum(v[5] for v in ohlcv[-6:-1])/5
                vol_mult = vol_last/vol_avg if vol_avg else 0
                qv = data.get('quoteVolume',0) or 0
                base = symbol.split('/')[0]
                is_quant = base in QUANT_COINS
                score=0
                if qv>=500000: score+=20
                if qv>=2000000: score+=10
                if vol_mult>=2.0: score+=20
                if vol_mult>=3.5: score+=10
                if abs(change)>=3.8: score+=20
                if abs(change)>=5.0: score+=20
                if is_quant:
                    if score<90: continue
                    label="90/100 QUANT"
                else:
                    if score<80: continue
                    label="80/100"
                ema7=sum(v[4] for v in ohlcv[-7:])/7
                side="LONG" if last>ema7 and change>0 else "SHORT" if last<ema7 and change<0 else None
                if not side: continue
                entry=last
                if side=="LONG":
                    tp1=entry*1.015; tp2=entry*1.03; tp3=entry*1.05; sl=entry*0.97
                else:
                    tp1=entry*0.985; tp2=entry*0.97; tp3=entry*0.95; sl=entry*1.03
                found.append({'symbol':symbol.replace('/',''), 'side':side, 'entry':entry, 'tp1':tp1, 'tp2':tp2, 'tp3':tp3, 'sl':sl, 'score':score, 'label':label, 'change':change, 'vol':vol_mult})
                c+=1
                if len(found)>=5: break
            except:
                continue
    except Exception as e:
        print(f"{ex.id} scan error: {e}")
    return found

def main():
    okx=get_ex('okx')
    gate=get_ex('gate')
    all_coins=[]
    total=0
    if okx:
        r=scan(okx,40)
        print(f"OKX scanned 40, pumps: {len(r)} - 80/100 strict")
        all_coins.extend(r)
        total+=40
        time.sleep(1)
    if gate:
        r=scan(gate,40)
        print(f"GATE scanned 40, pumps: {len(r)} - 90/100 quant strict")
        all_coins.extend(r)
        total+=40

    print(f"Scanning {total} coins on okx+gate... 80/100 big, 90/100 quant")
    print(f"Done. Found {len(all_coins)}")

    now_lagos = datetime.now(WAT)
    lagos_hour = now_lagos.hour
    print(f"Lagos time: {now_lagos.strftime('%H:%M')} - Hour {lagos_hour}")

    if lagos_hour % 3 == 0:
        send_text(f"✅ Bot Alive - {total}/300 active\nScanning OKX+GATE ({total} coins)\nBig: 80/100 | Quant: 90/100 | Time: {lagos_hour}:00 Lagos")

    if not all_coins:
        print("No trend found - sideways")
        return

    for c in sorted(all_coins, key=lambda x: x['score'], reverse=True)[:2]:
        red="🔴" if c['side']=="SHORT" else "🟢"
        caption=f"""🚀 FUTURE CALL - Pump Detected 🚀
Coin: {c['symbol']} ({c['label']})
Signal: {red} {c['side']} | {c['score']}/100
Pump: {c['change']:.2f}% | Vol x{c['vol']:.1f}
ENTRY: {round(c['entry'],6) if c['entry']<1 else round(c['entry'],4)}
TP1: {round(c['tp1'],6) if c['tp1']<1 else round(c['tp1'],4)} | TP2: {round(c['tp2'],6) if c['tp2']<1 else round(c['tp2'],4)} | TP3: {round(c['tp3'],6) if c['tp3']<1 else round(c['tp3'],4)}
SL: {round(c['sl'],6) if c['sl']<1 else round(c['sl'],4)}
"""
        send_text(caption)
        time.sleep(1)

if __name__=="__main__":
    main()
