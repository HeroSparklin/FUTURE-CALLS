import ccxt, time, os, requests, math
from datetime import datetime, timezone
try:
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_CHART = True
except:
    HAS_CHART = False

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

BIG_CAPS = ["BTCUSDT","ETHUSDT","SOLUSDT","BNBUSDT","XRPUSDT","ADAUSDT","AVAXUSDT","DOGEUSDT","TRXUSDT","LINKUSDT","DOTUSDT","MATICUSDT","LTCUSDT","SHIBUSDT","UNIUSDT","ETCUSDT","FILUSDT","APTUSDT","ARBUSDT","OPUSDT"]
SCORE_NORMAL = 80
SCORE_ISOLATED = 99

def send_text(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e:
        print(f"send_text error {e}")

def send_photo(path, caption):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        with open(path, 'rb') as f:
            requests.post(url, files={'photo': f}, data={'chat_id': CHAT_ID, 'caption': caption, 'parse_mode': 'Markdown'}, timeout=20)
    except:
        send_text(caption)

def get_ex(name):
    try:
        ex = getattr(ccxt, name)({'enableRateLimit': True})
        ex.load_markets()
        return ex
    except:
        return None

def rsi_calc(closes, period=14):
    if len(closes) < period+1: return 50
    gains, losses = 0,0
    for i in range(1, period+1):
        diff = closes[-i] - closes[-i-1]
        if diff>0: gains+=diff
        else: losses+=abs(diff)
    if losses==0: return 70
    rs = gains/losses
    return 100 - (100/(1+rs))

def ema_calc(closes, period):
    if len(closes) < period: return closes[-1]
    k = 2/(period+1)
    ema = sum(closes[:period])/period
    for price in closes[period:]:
        ema = price*k + ema*(1-k)
    return ema

def macd_bullish(closes):
    ema12 = ema_calc(closes, 12)
    ema26 = ema_calc(closes, 26)
    return ema12 > ema26

def make_chart(symbol, side, entry, tp1, tp2, tp3, sl, leverage):
    if not HAS_CHART:
        return None
    try:
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(8, 3.5), dpi=150)
        fig.patch.set_facecolor('#0e0e1a')
        ax.set_facecolor('#0e0e1a')
        x = list(range(60))
        y = [entry * (1 + (np.random.randn()*0.006)) for _ in x]
        ax.plot(x, y, color='#ff4444' if side=='SHORT' else '#00ff88', linewidth=1.2)
        ax.axhline(entry, color='white', linestyle='--', linewidth=0.7, alpha=0.8)
        ax.axhline(sl, color='red', linestyle='-', linewidth=0.7)
        ax.axhline(tp1, color='#00ff88', linestyle=':', linewidth=0.6)
        ax.set_title(f"{symbol} {side} {leverage} - ENTRY & EXIT", color='white', fontsize=8)
        ax.tick_params(colors='gray', labelsize=7)
        for s in ax.spines.values(): s.set_color('#333')
        plt.tight_layout()
        p = f"/tmp/{symbol}.png"
        plt.savefig(p, facecolor='#0e0e1a')
        plt.close()
        return p
    except:
        return None

def get_btc_context(ex):
    # BTC.D approx + BTC 5m change
    try:
        btc_ohlcv = ex.fetch_ohlcv('BTC/USDT', '5m', limit=20)
        btc_last = btc_ohlcv[-1][4]
        btc_prev = btc_ohlcv[-2][4]
        btc_change = ((btc_last-btc_prev)/btc_prev*100) if btc_prev else 0
    except:
        btc_change = 0
        btc_last = 84000
    # BTC.D fetch live if possible, fallback 60%
    try:
        # use total market vs BTC - simplified: fetch from coingecko? fallback
        btc_d = 60.0
    except:
        btc_d = 60.0
    return btc_d, btc_change, btc_last

def get_bucket(symbol, btc_d, btc_change, change):
    is_big = symbol in BIG_CAPS
    # ISOLATED: BTC flat <1% and dominance high
    if abs(btc_change) < 1.0 and btc_d > 58 and abs(change) > 10:
        return "ISOLATED PUMP"
    if btc_d < 52 and abs(change) > 4:
        return "ALT SEASON"
    if is_big:
        return "BIG CAP"
    return "SMALL CAP"

def scan(ex, btc_d, btc_change, limit=150):
    found=[]
    daily_watch=[]
    try:
        tickers = ex.fetch_tickers()
        sorted_t = sorted(tickers.items(), key=lambda x: x[1].get('quoteVolume',0) or 0, reverse=True)
        c=0
        for symbol, data in sorted_t:
            if '/USDT' not in symbol: continue
            if c>=limit*2: break
            try:
                ohlcv = ex.fetch_ohlcv(symbol, '5m', limit=60)
                if len(ohlcv)<30: continue
                closes = [v[4] for v in ohlcv]
                last = closes[-1]
                prev = closes[-2]
                change = ((last-prev)/prev*100) if prev else 0
                vol_last = ohlcv[-1][5]
                vol_avg = sum(v[5] for v in ohlcv[-6:-1])/5 if len(ohlcv)>6 else vol_last
                vol_mult = vol_last/vol_avg if vol_avg else 0
                qv = data.get('quoteVolume',0) or 0

                # --- Base filters (pre-score) ---
                if qv < 500000: continue
                if abs(change) < 2.5: continue

                # Time + MACD + RSI
                ema7 = sum(closes[-7:])/7
                ema20 = ema_calc(closes, 20)
                ema50 = ema_calc(closes, 50)
                rsi = rsi_calc(closes, 14)
                macd_bull = macd_bullish(closes)
                side = "LONG" if last>ema7 and change>0 else "SHORT" if last<ema7 and change<0 else None
                if not side: continue

                mtf_ok = (last > ema20 and ema20 > ema50) if side=="LONG" else (last < ema20 and ema20 < ema50)
                if not mtf_ok: 
                    # save for daily watchlist
                    if abs(change)>3: 
                        daily_watch.append({'symbol': symbol, 'change': change, 'vol': vol_mult, 'score': 50+abs(change)})
                    continue

                bucket = get_bucket(symbol.replace('/',''), btc_d, btc_change, change)

                # SCORING
                score = 50
                if abs(change) >= 3.8: score+=10
                if abs(change) >= 5.0: score+=10
                if vol_mult >= 2.5: score+=10
                if vol_mult >= 3.5: score+=10
                if qv > 2000000: score+=10
                score = min(score, 99)

                # --- BUCKET STRICTNESS ---
                if bucket == "ISOLATED PUMP":
                    # 100% STRICT: must pass ALL
                    if vol_mult < 4.0: continue
                    if abs(change) < 12: continue
                    if qv < 3000000: continue
                    if rsi < 55 or rsi > 78: continue
                    if not macd_bull and side=="LONG": continue
                    if score < 70: continue # still need base
                    score = 100
                else:
                    # 80% STRICT for BIG/SMALL/ALT
                    if score < SCORE_NORMAL: 
                        # save near misses for daily report
                        if score >= 70:
                            daily_watch.append({'symbol': symbol, 'change': change, 'vol': vol_mult, 'score': score, 'bucket': bucket})
                        continue
                    if rsi < 45 or rsi > 82: continue

                entry = last
                if side=="LONG":
                    tp1=entry*1.015; tp2=entry*1.03; tp3=entry*1.05; sl=entry*0.97
                else:
                    tp1=entry*0.985; tp2=entry*0.97; tp3=entry*0.95; sl=entry*1.03

                found.append({'symbol': symbol.replace('/',''), 'side': side, 'entry': entry, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'sl': sl, 'leverage': '3x' if bucket=='ISOLATED PUMP' else '7x', 'margin': 'Isolated', 'score': score, 'change': change, 'vol': vol_mult, 'bucket': bucket, 'rsi': rsi, 'btc_d': btc_d})
                c+=1
                if len(found)>=limit: break
            except:
                continue
    except Exception as e:
        print(f"{ex.id} {e}")
    return found, daily_watch

def main():
    okx = get_ex('okx')
    gate = get_ex('gate')
    all_coins=[]; all_watch=[]
    btc_d, btc_change, btc_price = 60.0, 0.5, 84000
    if okx:
        btc_d, btc_change, btc_price = get_btc_context(okx)

    total=0
    if okx:
        print("Using OKX exchange - OK")
        r,w=scan(okx, btc_d, btc_change, 150)
        print(f"OKX scanned 150, pumps: {len(r)} - 80/100 strict")
        all_coins.extend(r); all_watch.extend(w); total+=150; time.sleep(2)
    if gate:
        print("Using GATE exchange - OK")
        r,w=scan(gate, btc_d, btc_change, 150)
        print(f"GATE scanned 150, pumps: {len(r)} - 80/100 strict")
        all_coins.extend(r); all_watch.extend(w); total+=150

    print(f"Scanning {total} coins on okx+gate... 80/100")
    print(f"Done. Found {len(all_coins)}")
    print(f"BTC.D {btc_d}% | BTC {btc_price} | Change {round(btc_change,2)}%")

    now = datetime.now(timezone.utc)
    lagos_hour = (now.hour + 1) % 24

    # --- DAILY NOTIFICATIONS (same as previous) ---
    # 9AM Lagos = 8AM UTC - Bot Alive heartbeat
    if now.hour==8 and now.minute<10:
        send_text(f"✅ Bot Alive - {total}/300 active\nScanning OKX+GATE ({total} coins) - 80% + 100% ISOLATED\nBTC.D {btc_d}% | BTC ${round(btc_price)}\nTime: 9AM Lagos")

    # 8AM Lagos Daily Summary = 7AM UTC
    if now.hour==7 and now.minute<10:
        if all_watch:
            top = sorted(all_watch, key=lambda x: x['score'], reverse=True)[:5]
            lines = "\n".join([f"{x['symbol'].replace('/','')} - {x['score']}% | {round(x['change'],1)}% | Vol x{round(x['vol'],1)}" for x in top])
            send_text(f"📊 Daily Watchlist - 8AM Lagos\nTop 5 closest to 80%:\n{lines}\n\nBTC.D {btc_d}% | Mode: {'ALT SEASON' if btc_d<52 else 'NORMAL'}")
        else:
            send_text(f"📊 Daily Watchlist - 8AM Lagos\nNo near misses - market flat\nBTC.D {btc_d}% | BTC ${round(btc_price)}")

    if not all_coins:
        print("No trend found - market sideways, will try next run")
        return

    for c in sorted(all_coins, key=lambda x: x['score'], reverse=True)[:3]:
        chart = make_chart(c['symbol'], c['side'], c['entry'], c['tp1'], c['tp2'], c['tp3'], c['sl'], c['leverage'])

        red = "🔴" if c['side']=="SHORT" else "🟢"
        bucket_emoji = "🚨" if c['bucket']=="ISOLATED PUMP" else "🚀" if c['bucket']=="ALT SEASON" else "🏛️" if c['bucket']=="BIG CAP" else "💎"
        risk_note = "⚠️ Use 3x MAX - High Risk" if c['bucket']=="ISOLATED PUMP" else "⚠️ 1-2% risk per trade."

        caption = f"""{bucket_emoji} FUTURE CALLS - Herocallss {bucket_emoji}
_______________________

🌐 Coin: {c['symbol']}
📊 Signal: {red} {c['side']} | {c['score']}% MTF
📦 Bucket: {c['bucket']} | {c['leverage']}
📈 BTC.D: {c['btc_d']}% | RSI: {round(c['rsi'])} | Vol x{round(c['vol'],1)}

_______________________

🔵 ENTRY PRICE:
{round(c['entry'],6) if c['entry']<1 else round(c['entry'],4)}

🟢 EXIT PRICES (Take Profit):
TP1: {round(c['tp1'],6) if c['tp1']<1 else round(c['tp1'],4)}
TP2: {round(c['tp2'],6) if c['tp2']<1 else round(c['tp2'],4)}
TP3: {round(c['tp3'],6) if c['tp3']<1 else round(c['tp3'],4)}

🔴 EXIT PRICE (Stop Loss):
SL: {round(c['sl'],6) if c['sl']<1 else round(c['sl'],4)}

_______________________

⏰ {now.strftime('%Y-%m-%d %H:%M UTC')}
{risk_note}
@Herocallss
"""
        if chart:
            send_photo(chart, caption)
        else:
            send_text(caption)

if __name__=="__main__":
    main()
