import os, requests, time
import ccxt

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BINANCE = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})

COINS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","ADAUSDT","SHIBUSDT","DOTUSDT","MATICUSDT","LTCUSDT","BCHUSDT","NEARUSDT","UNIUSDT","PEPEUSDT","APTUSDT","SUIUSDT","OPUSDT","ENAUSDT","WIFUSDT","BONKUSDT","FLOKIUSDT","FILUSDT","STXUSDT","RNDRUSDT","INJUSDT","SEIUSDT","TAOUSDT"]

def send(m):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": m, "parse_mode": "Markdown"}, timeout=10)

def check(sym):
    try:
        o = BINANCE.fetch_ohlcv(sym, '15m', limit=30)
        c = [x[4] for x in o]
        entry = c[-1]
        e9 = sum(c[-9:])/9
        e21 = sum(c[-21:])/21
        gap = abs(e9 - e21) / entry

        # SAFE MODE: Need 0.06% minimum gap to confirm trend
        if gap < 0.0006:
            return None

        if e9 > e21:
            return f"🟢 FUTURE-CALL: {sym} - LONG\nInterval: 15m\n\n💰 Entry: `{entry:.6f}`\n🎯 TP1: `{entry*1.008:.6f}`\nTP2: `{entry*1.015:.6f}`\nTP3: `{entry*1.03:.6f}`\n🛑 SL: `{entry*0.97:.6f}`\n\nTrend: +{gap*100:.3f}% ✅"
        else:
            return f"🔴 FUTURE-CALL: {sym} - SHORT\nInterval: 15m\n\n💰 Entry: `{entry:.6f}`\n🎯 TP1: `{entry*0.992:.6f}`\nTP2: `{entry*0.985:.6f}`\nTP3: `{entry*0.97:.6f}`\n🛑 SL: `{entry*1.03:.6f}`\n\nTrend: -{gap*100:.3f}% ✅"
    except:
        return None

found = 0
for coin in COINS:
    s = check(coin)
    if s:
        send(s)
        found += 1
        if found >= 3: break
    time.sleep(0.15)

print(f"Done. Found {found}")
if found == 0:
    print("No trend found - market sideways, will try next run")
else:
    print(f"Sent {found} safe signals")
