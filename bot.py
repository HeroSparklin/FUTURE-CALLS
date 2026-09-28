import os, requests, time
import ccxt

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BINANCE = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})

COINS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT","SHIBUSDT","DOTUSDT","LINKUSDT","TRXUSDT","MATICUSDT","LTCUSDT","BCHUSDT","NEARUSDT","UNIUSDT","PEPEUSDT","APTUSDT","ETCUSDT","FILUSDT","STXUSDT","ICPUSDT","ARBUSDT","HBARUSDT","MKRUSDT","INJUSDT","RNDRUSDT","SUIUSDT","OPUSDT","LDOUSDT","TAOUSDT","IMXUSDT","SEIUSDT","GRTUSDT","FETUSDT","ARUSDT","AGIXUSDT","THETAUSDT","FLOWUSDT","KAVAUSDT","ALGOUSDT","EGLDUSDT","AXSUSDT","SANDUSDT","MANAUSDT","CHZUSDT","CFXUSDT","AAVEUSDT","XTZUSDT","EOSUSDT","KLAYUSDT","NEOUSDT","IOTAUSDT","KSMUSDT","ZILUSDT","ENJUSDT","MINAUSDT","ROSEUSDT","COMPUSDT","ONEUSDT","LRCUSDT","QTUMUSDT","RVNUSDT","CELOUSDT","GMTUSDT","BLURUSDT","JASMYUSDT","SKLUSDT","GALAUSDT","JOEUSDT","MAGICUSDT","LINAUSDT","HIGHUSDT","HOOKUSDT","IDUSDT","RDNTUSDT","EDUUSDT","FLOKIUSDT","BONKUSDT","WIFUSDT","1000SATSUSDT","ORDIUSDT","JUPUSDT","STRKUSDT","WUSDT","ARKMUSDT","PIXELUSDT","PORTALUSDT","ACEUSDT","NFPUSDT","AIUSDT","XAIUSDT","ASTUSDT","MNTUSDT","ENAUSDT","EURUSDT","GBPUSDT","AUDUSDT","TRYUSDT","BRLUSDT","NGNUSDT","EURGBP","EURTRY","GBPUSDC","EURBUSD"]

def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)

def check(symbol):
    try:
        ohlcv = BINANCE.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        entry = closes[-1]
        ema9 = sum(closes[-9:])/9
        ema21 = sum(closes[-21:])/21

        # --- STRICT 80% FILTERS ---
        avg_vol = sum(volumes[-10:])/10
        if volumes[-1] < avg_vol * 1.2: # Must have high volume
            return None
        if abs(ema9 - ema21) / entry < 0.002: # Must have strong trend 0.2%
            return None

        if ema9 > ema21:
            return f"🟢 FUTURE-CALL: {symbol} - LONG\nInterval: 15m\n\n💰 Entry: `{entry:.4f}`\n\n🎯 TPs:\nTP1: `{entry*1.008:.4f}`\nTP2: `{entry*1.015:.4f}`\nTP3: `{entry*1.03:.4f}`\n\n🛑 SL: `{entry*0.97:.4f}`\n\nStrict ✅"
        else:
            return f"🔴 FUTURE-CALL: {symbol} - SHORT\nInterval: 15m\n\n💰 Entry: `{entry:.4f}`\n\n🎯 TPs:\nTP1: `{entry*0.992:.4f}`\nTP2: `{entry*0.985:.4f}`\nTP3: `{entry*0.97:.4f}`\n\n🛑 SL: `{entry*1.03:.4f}`\n\nStrict ✅"
    except:
        return None

found=0
for coin in COINS:
    s=check(coin)
    if s:
        send(s)
        found+=1
        if found>=3: break # STRICT = max 3 per run
    time.sleep(0.2)
print(f"Done. Found {found}")
