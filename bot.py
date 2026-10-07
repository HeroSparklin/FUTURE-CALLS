# FAST 100 COIN BOT - FIXED LIVELY EVERY 5 MIN
import ccxt, time, os, requests, datetime, io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
EXCHANGES = ['okx', 'gate']

def send_tg(text):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def send_chart(caption, ohlcv):
    try:
        closes = [c[4] for c in ohlcv[-50:]]
        plt.figure(figsize=(8,4))
        plt.plot(closes)
        plt.title(caption)
        plt.grid(True, alpha=0.3)
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        plt.close()
        buf.seek(0)
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"}, files={"photo": buf}, timeout=20)
    except Exception as e:
        print(f"chart fail {e}")

def scan():
    all_pumps = []
    total = 0
    for ex_id in EXCHANGES:
        try:
            ex = getattr(ccxt, ex_id)({'enableRateLimit': True})
            ex.load_markets()
            tickers = ex.fetch_tickers()
            # ONLY 50 PER EXCHANGE = 100 TOTAL
            sorted_tickers = sorted(tickers.items(), key=lambda x: x[1].get('quoteVolume',0) or 0, reverse=True)[:50]
            print(f"{ex_id.upper()} scanned {len(sorted_tickers)}")
            for symbol, data in sorted_tickers:
                if '/USDT' not in symbol: continue
                try:
                    ohlcv = ex.fetch_ohlcv(symbol, '5m', limit=20)
                    if len(ohlcv) < 10: continue
                    total += 1
                    last = ohlcv[-1][4]
                    prev = ohlcv[-2][4]
                    change = (last-prev)/prev*100 if prev else 0
                    vol_last = ohlcv[-1][5]
                    vol_avg = sum(v[5] for v in ohlcv[-6:-1])/5
                    vol_mult = vol_last/vol_avg if vol_avg else 0
                    qv = data.get('quoteVolume',0) or 0
                    if qv < 500000: continue
                    if vol_mult < 1.5: continue
                    if abs(change) < 2.5: continue
                    ema7 = sum(v[4] for v in ohlcv[-7:])/7
                    side = "LONG" if last>ema7 and change>0 else "SHORT" if last<ema7 and change<0 else None
                    if not side: continue
                    score = 50
                    if abs(change) >= 2.5: score+=5
                    if abs(change) >= 3.5: score+=10
                    if abs(change) >= 5.0: score+=10
                    if vol_mult >= 1.5: score+=5
                    if vol_mult >= 2.5: score+=10
                    if vol_mult >= 3.5: score+=10
                    if qv > 2000000: score+=5
                    if qv > 5000000: score+=5
                    score = min(score, 99)
                    if score >= 80:
                        all_pumps.append((symbol, side, change, vol_mult, score, ex_id.upper(), ohlcv))
                except: continue
                time.sleep(0.1)
        except Exception as e:
            print(f"{ex_id} error {e}")

    print(f"Scanning {total} coins... Found {len(all_pumps)}")

    if not all_pumps:
        # FIXED: NOW SENDS EVERY 5 MIN, NOT 30 MIN
        now = datetime.datetime.utcnow()
        msg = f"💓 Bot Lively - No signal at the moment\nScanned {total} coins - all below 80/100\nNext scan in 5min - {now.strftime('%H:%M')} UTC"
        send_tg(msg)
        print("Lively sent")
        return

    for symbol, side, change, vol_mult, score, ex_name, ohlcv in sorted(all_pumps, key=lambda x: x[4], reverse=True)[:3]:
        cap = f"🚀 FUTURE CALLS {symbol} {side}\nEx: {ex_name} | Score {score}/100 | {change:.2f}% | x{vol_mult:.1f} Vol"
        send_chart(cap, ohlcv)

if __name__ == "__main__":
    scan()
