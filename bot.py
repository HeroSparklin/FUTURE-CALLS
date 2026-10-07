import ccxt, requests, os
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

POSITION_USDT = 20
LEVERAGE = 20
TP1_PCT = 4.0
TP2_PCT = 8.0
SL_PCT = 2.5
THRESHOLD = 80

EXCHANGES = {
    'GATE': ccxt.gate(),
    'MEXC': ccxt.mexc(),
}

def send(text):
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing token")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)

def analyze():
    btc_change = 0
    try:
        o = EXCHANGES['GATE'].fetch_ohlcv('BTC/USDT', '5m', limit=2)
        btc_change = ((o[-1][4]-o[-2][4])/o[-2][4])*100
    except:
        pass

    scanned = 0
    found = False

    for ex_name, ex in EXCHANGES.items():
        try:
            ex.load_markets()
            tickers = ex.fetch_tickers()
            usdt = {s:t for s,t in tickers.items() if '/USDT' in s and t.get('quoteVolume',0) > 500000}
            top = sorted(usdt.items(), key=lambda x: x[1]['quoteVolume'], reverse=True)[:25]

            for symbol, ticker in top:
                scanned += 1
                try:
                    ohlcv = ex.fetch_ohlcv(symbol, '5m', limit=20)
                    if len(ohlcv) < 10: continue
                    close = ohlcv[-1][4]
                    prev = ohlcv[-2][4]
                    change = ((close-prev)/prev)*100
                    if abs(change) < 2.5: continue

                    vol = ohlcv[-1][5]
                    avg = sum(c[5] for c in ohlcv[-6:-1])/5
                    if avg == 0: continue
                    vol_mult = vol/avg
                    if vol_mult < 1.5: continue
                    if change>0 and btc_change<-1: continue
                    if change<0 and btc_change>1: continue

                    score = 50
                    if abs(change)>=3.5: score+=15
                    if abs(change)>=5: score+=10
                    if vol_mult>=2.5: score+=15
                    if vol_mult>=3.5: score+=10

                    if score >= THRESHOLD:
                        side="LONG" if change>0 else "SHORT"
                        entry=close
                        if side=="LONG":
                            tp1=entry*(1+TP1_PCT/100)
                            tp2=entry*(1+TP2_PCT/100)
                            sl=entry*(1-SL_PCT/100)
                        else:
                            tp1=entry*(1-TP1_PCT/100)
                            tp2=entry*(1-TP2_PCT/100)
                            sl=entry*(1+SL_PCT/100)

                        msg = (
                            f"🚀 FUTURE CALLS {symbol} {side}\n"
                            f"Ex: {ex_name} | Score {score}/100 | {change:+.2f}% | x{vol_mult:.1f} Vol\n"
                            f"BTC 5m: {btc_change:+.2f}%\n\n"
                            f"ENTRY: {entry:.8g} (MARKET)\n"
                            f"LEVERAGE: {LEVERAGE}x Isolated\n"
                            f"AMOUNT: ${POSITION_USDT}\n\n"
                            f"TP1: +{TP1_PCT}% -> {tp1:.8g}\n"
                            f"TP2: +{TP2_PCT}% -> {tp2:.8g}\n"
                            f"SL: -{SL_PCT}% -> {sl:.8g}"
                        )
                        send(msg)
                        found=True
                        return
                except:
                    continue
        except Exception as e:
            print(f"{ex_name} {e}")
            continue

    if not found:
        now=datetime.utcnow().strftime("%H:%M UTC")
        send(f"💓 Bot Lively - No signal\nScanned {scanned} coins <80/100\nBTC 5m: {btc_change:+.2f}% | Next in 5m - {now}")

if __name__=="__main__":
    analyze()
