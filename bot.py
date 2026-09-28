import os, requests, time
import ccxt
TOKEN=os.getenv("BOT_TOKEN"); CHAT_ID=os.getenv("CHAT_ID")
BINANCE=ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})

COINS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","AVAXUSDT","LINKUSDT","ADAUSDT","SHIBUSDT","DOTUSDT","MATICUSDT","LTCUSDT","BCHUSDT","NEARUSDT","UNIUSDT","PEPEUSDT","APTUSDT","ARBUSDT","SUIUSDT","OPUSDT","TAOUSDT","ENAUSDT","WIFUSDT","BONKUSDT","FLOKIUSDT","FILUSDT","INJUSDT","RNDRUSDT","STXUSDT"]

def send(m):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": m, "parse_mode": "Markdown"}, timeout=10)

def check(sym):
    try:
        o=BINANCE.fetch_ohlcv(sym, '15m', limit=30)
        c=[x[4] for x in o]; v=[x[5] for x in o]
        entry=c[-1]; e9=sum(c[-9:])/9; e21=sum(c[-21:])/21
        # STRICT: need 0.12% trend + volume above average
        if abs(e9-e21)/entry < 0.0012: return None
        if v[-1] < sum(v[-10:])/10 * 0.9: return None
        if e9>e21:
            return f"🟢 FUTURE-CALL: {sym} - LONG\nInterval: 15m\n\n💰 Entry: `{entry:.4f}`\n\n🎯 TPs:\nTP1: `{entry*1.008:.4f}`\nTP2: `{entry*1.015:.4f}`\nTP3: `{entry*1.03:.4f}`\n\n🛑 SL: `{entry*0.97:.4f}`\n\nStrict ✅ Vol+Trend"
        else:
            return f"🔴 FUTURE-CALL: {sym} - SHORT\nInterval: 15m\n\n💰 Entry: `{entry:.4f}`\n\n🎯 TPs:\nTP1: `{entry*0.992:.4f}`\nTP2: `{entry*0.985:.4f}`\nTP3: `{entry*0.97:.4f}`\n\n🛑 SL: `{entry*1.03:.4f}`\n\nStrict ✅ Vol+Trend"
    except: return None

found=0
for coin in COINS:
    s=check(coin)
    if s:
        send(s); found+=1
        if found>=3: break
    time.sleep(0.2)
print(f"Done. Found {found}")
