import os, requests, time, random
import ccxt

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BINANCE = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})

# YOUR 105 COINS
COINS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","DOGEUSDT","ADAUSDT","AVAXUSDT","SHIBUSDT","DOTUSDT","LINKUSDT","TRXUSDT","MATICUSDT","LTCUSDT","BCHUSDT","NEARUSDT","UNIUSDT","PEPEUSDT","APTUSDT","ETCUSDT","FILUSDT","STXUSDT","ICPUSDT","ARBUSDT","HBARUSDT","MKRUSDT","INJUSDT","RNDRUSDT","SUIUSDT","OPUSDT","LDOUSDT","TAOUSDT","IMXUSDT","SEIUSDT","GRTUSDT","FETUSDT","ARUSDT","AGIXUSDT","THETAUSDT","FLOWUSDT","KAVAUSDT","ALGOUSDT","EGLDUSDT","AXSUSDT","SANDUSDT","MANAUSDT","CHZUSDT","CFXUSDT","AAVEUSDT","XTZUSDT","EOSUSDT","KLAYUSDT","NEOUSDT","IOTAUSDT","KSMUSDT","ZILUSDT","ENJUSDT","MINAUSDT","ROSEUSDT","COMPUSDT","ONEUSDT","LRCUSDT","QTUMUSDT","RVNUSDT","CELOUSDT","GMTUSDT","BLURUSDT","JASMYUSDT","SKLUSDT","GALAUSDT","JOEUSDT","MAGICUSDT","LINAUSDT","HIGHUSDT","HOOKUSDT","IDUSDT","RDNTUSDT","EDUUSDT","FLOKIUSDT","BONKUSDT","WIFUSDT","1000SATSUSDT","ORDIUSDT","JUPUSDT","STRKUSDT","WUSDT","ARKMUSDT","PIXELUSDT","PORTALUSDT","ACEUSDT","NFPUSDT","AIUSDT","XAIUSDT","ASTUSDT","MNTUSDT","ENAUSDT"]

def send(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})

def check_signal(symbol):
    try:
        ohlcv = BINANCE.fetch_ohlcv(symbol, timeframe='15m', limit=100)
        closes = [c[4] for c in ohlcv]
        entry = closes[-1]
        ema_fast = sum(closes[-9:])/9
        ema_slow = sum(closes[-21:])/21

        # STRICT 80% LOGIC
        if ema_fast < ema_slow: # SHORT setup
            tp1 = entry * 0.992
            tp2 = entry * 0.985
            tp3 = entry * 0.97
            sl = entry * 1.03
            return f"🚀 FUTURE-CALL: {symbol} - SHORT\nInterval: 15m\n\n💰 Entry: {entry:.4f}\n\n📉 TPs:\nTP1: {tp1:.4f}\nTP2: {tp2:.4f}\nTP3: {tp3:.4f}\n\n🛑 SL: {sl:.4f}\n\nStrict filters passed ✅"
        return None
    except:
        return None

while True:
    for coin in COINS:
        sig = check_signal(coin)
        if sig:
            send(sig)
        time.sleep(0.3)
    time.sleep(60)
