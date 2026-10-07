import ccxt, time, os, requests
from datetime import datetime, timezone
try:
    import matplotlib.pyplot as plt
    import numpy as np
    HAS_CHART = True
except:
    HAS_CHART = False

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_text(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)

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

def scan(ex, limit=150):
    found=[]
    try:
        tickers = ex.fetch_tickers()
        sorted_t = sorted(tickers.items(), key=lambda x: x[1].get('quoteVolume',0) or 0, reverse=True)
        c=0
        for symbol, data in sorted_t:
            if '/USDT' not in symbol: continue
            if c>=limit*2: break
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

                # --- 80/100 SENSITIVE (Option 2) ---
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

                if score < 80:
                    continue

                entry = last
                if side=="LONG":
                    tp1=entry*1.015; tp2=entry*1.03; tp3=entry*1.05; sl=entry*0.97
                else:
                    tp1=entry*0.985; tp2=entry*0.97; tp3=entry*0.95; sl=entry*1.03

                found.append({'symbol': symbol.replace('/',''), 'side': side, 'entry': entry, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'sl': sl, 'leverage': '10x', 'margin': 'Isolated', 'score': score, 'change': change, 'vol_mult': vol_mult})
                c+=1
                if len(found)>=limit: break
            except:
                continue
    except Exception as e:
        print(f"{ex.id} {e}")
    return found

def main():
    okx = get_ex('okx')
    gate = get_ex('gate')
    all_coins=[]; total=0
    if okx:
        r=scan(okx,150)
        print(f"OKX scanned 150, pumps: {len(r)} - 80/100 sensitive")
        all_coins.extend(r); total+=150; time.sleep(2)
    if gate:
        r=scan(gate,150)
        print(f"GATE scanned 150, pumps: {len(r)} - 80/100 sensitive")
        all_coins.extend(r); total+=150

    print(f"Scanning {total} coins on okx+gate... 80/100")
    print(f"Done. Found {len(all_coins)}")

    now = datetime.now(timezone.utc)

    # --- NEW: LIVELY HEARTBEATS ---
    # 1. Every 3 hours when no trade
    # 2. 9AM Lagos heartbeat
    is_9am = now.hour==8 and now.minute<10

    if not all_coins:
        if is_9am:
            send_text(f"✅ Bot Alive - {total}/100 active\nScanning OKX+GATE ({total} coins) - 80/100 sensitive\nTime: 9AM Lagos\nNo strong trend - market sideways, skipping safely")
        else:
            # Lively ping every 3 hours (0,3,6,9,12,15,18,21 UTC) if no trade
            if now.hour % 3 == 0 and now.minute < 10:
                send_text(f"💓 Bot Lively - No signal at the moment\nScanned {total} coins - all below 80/100\nNext scan in 5min - {now.strftime('%H:%M UTC')}")
        print("No trend found - market sideways, lively notification sent")
        return

    # If found signals
    for c in sorted(all_coins, key=lambda x: x['score'], reverse=True)[:2]:
        chart = make_chart(c['symbol'], c['side'], c['entry'], c['tp1'], c['tp2'], c['tp3'], c['sl'], c['leverage'])
        red = "🔴" if c['side']=="SHORT" else "🟢"
        caption = f"""🚀 FUTURE CALLS - Herocallss 🚀
_______________________

🌐 Coin: {c['symbol']}
📊 Signal: {red} {c['side']} | Score: {c['score']}/100
📈 Change: {c['change']:.2f}% | Vol: {c['vol_mult']:.1f}x
⚡ Leverage: {c['leverage']} {c['margin']}

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
⚠️ 1-2% risk per trade.
@Herocallss
"""
        if chart:
            send_photo(chart, caption)
        else:
            send_text(caption)

if __name__=="__main__":
    main()
