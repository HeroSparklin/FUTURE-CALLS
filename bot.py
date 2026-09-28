import os, requests, time
import ccxt

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BINANCE = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})

COINS = ["BTCUSDT","ETHUSDT","BNBUSDT","SOLUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT","SHIBUSDT","DOTUSDT","LINKUSDT","TRXUSDT","MATICUSDT","LTCUSDT","BCHUSDT","NEARUSDT","UNIUSDT","PEPEUSDT","APTUSDT","ETCUSDT","FILUSDT","STXUSDT","ICPUSDT","ARBUSDT","HBARUSDT","MKRUSDT","INJUSDT","RNDRUSDT","SUIUSDT","OPUSDT","LDOUSDT","TAOUSDT","IMXUSDT","SEIUSDT","GRTUSDT","FETUSDT","ARUSDT","AGIXUSDT","THETAUSDT","FLOWUSDT","KAVAUSDT","ALGOUSDT","EGLDUSDT","AXSUSDT","SANDUSDT","MANAUSDT","CHZUSDT","CFXUSDT","AAVEUSDT","XTZUSDT","EOSUSDT","KLAYUSDT","NEOUSDT","IOTAUSDT","KSMUSDT","ZILUSDT","ENJUSDT","MINAUSDT","ROSEUSDT","COMPUSDT","ONEUSDT","LRCUSDT","QTUMUSDT","RVNUSDT","CELOUSDT","GMTUSDT","BLURUSDT","JASMYUSDT","SKLUSDT","GALAUSDT","JOEUSDT","MAGICUSDT","LINAUSDT","HIGHUSDT","HOOKUSDT","IDUSDT","RDNTUSDT","EDUUSDT","FLOKIUSDT","BONKUSDT","WIFUSDT","1000SATSUSDT","ORDIUSDT","JUPUSDT","STRKUSDT","WUSDT","ARKMUSDT","PIXELUSDT","PORTALUSDT","ACEUSDT","NFPUSDT","AIUSDT","XAIUSDT","ASTUSDT","MNTUSDT","ENAUSDT"]

def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)

def check(symbol):
    try:
        ohlcv = BINANCE.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        closes = [c[4] for c in ohlcv]
        entry = closes[-1]
        ema9 = sum(closes[-9:])/9
        ema21 = sum(closes[-21:])/21

        # BALANCED FILTER - 0.05% gap only (not 0.2%)
        if abs(ema9 - ema21) / entry < 0.0005:
            return None

        if ema9 > ema21: # LONG
            side="LONG"; emoji="🟢"
            tp1=entry*1.008; tp2=entry*1.015; tp3=entry*1.03; sl=entry*0.97
        else: # SHORT
            side="SHORT"; emoji="🔴"
            tp1=entry*0.992; tp2=entry*0.985; tp3=entry*0.97; sl=entry*1.03

        return f"{emoji} FUTURE-CALL: {symbol} - {side}\nInterval: 15m\n\n💰 Entry: `{entry:.4f}`\n\n🎯 TPs:\nTP1: `{tp1:.4f}`\nTP2: `{tp2:.4f}`\nTP3: `{tp3:.4f}`\n\n🛑 SL: `{sl:.4f}`"
    except:
        return None

found=0
for coin in COINS:
    s=check(coin)
    if s:
        send(s)
        found+=1
        if found>=4: break
    time.sleep(0.15)
print(f"Done. Found {found}")
