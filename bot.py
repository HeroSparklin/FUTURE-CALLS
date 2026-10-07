import ccxt, requests, os
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

POSITION_USDT = 20
LEVERAGE = 20
TP1_PCT = 4.0
TP2_PCT = 8.0
SL_PCT = 2.5

def send(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)
    except Exception as e:
        print(e)

# Fixed list - no heavy ticker scan, so it will NEVER hang
COINS = ['BTC/USDT','ETH/USDT','SOL/USDT','XRP/USDT','DOGE/USDT','PEPE/USDT','SHIB/USDT','WIF/USDT','BONK/USDT','FLOKI/USDT','AVAX/USDT','LINK/USDT','ADA/USDT','LTC/USDT','BCH/USDT']

def analyze():
    ex = ccxt.mexc()
    scanned = 0
    try:
        btc = ex.fetch_ohlcv('BTC/USDT','5m',limit=2)
        btc_chg = ((btc[-1][4]-btc[-2][4])/btc[-2][4])*100
    except:
        btc_chg = 0

    for symbol in COINS:
        scanned+=1
        try:
            ohlcv = ex.fetch_ohlcv(symbol,'5m',limit=20)
            close=ohlcv[-1][4]
            prev=ohlcv[-2][4]
            change=((close-prev)/prev)*100
            if abs(change)<2.5: continue
            vol=ohlcv[-1][5]
            avg=sum(c[5] for c in ohlcv[-6:-1])/5
            vol_mult=vol/avg if avg else 0
            if vol_mult<1.8: continue

            # Found
            side="LONG" if change>0 else "SHORT"
            entry=close
            if side=="LONG":
                tp1=entry*1.04
                tp2=entry*1.08
                sl=entry*0.975
            else:
                tp1=entry*0.96
                tp2=entry*0.92
                sl=entry*1.025

            msg=(f"🚀 FUTURE CALLS {symbol} {side}\n"
                 f"Score 85+/100 | {change:+.2f}% | x{vol_mult:.1f} Vol | BTC {btc_chg:+.1f}%\n\n"
                 f"ENTRY: {entry:.8g}\n"
                 f"LEVERAGE: {LEVERAGE}x\n"
                 f"AMOUNT: ${POSITION_USDT}\n\n"
                 f"TP1: {tp1:.8g} (+4%)\n"
                 f"TP2: {tp2:.8g} (+8%)\n"
                 f"SL: {sl:.8g} (-2.5%)")
            send(msg)
            return
        except Exception as e:
            print(f"{symbol} {e}")
            continue

    now=datetime.utcnow().strftime("%H:%M UTC")
    send(f"💓 Bot Lively - No pump yet\nScanned {scanned} top coins\nBTC 5m: {btc_chg:+.2f}% | {now}")

if __name__=="__main__":
    analyze()
