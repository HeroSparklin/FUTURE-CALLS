import ccxt, time, os, requests
from datetime import datetime, timezone
import matplotlib.pyplot as plt
import numpy as np

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_signal_with_chart(chart_path, caption):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        with open(chart_path, 'rb') as photo:
            files = {'photo': photo}
            data = {'chat_id': CHAT_ID, 'caption': caption, 'parse_mode': 'Markdown'}
            requests.post(url, files=files, data=data, timeout=20)
    except Exception as e:
        print(f"Telegram photo error: {e}")

def send_text(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(e)

def get_exchange(name):
    try:
        ex = getattr(ccxt, name)({'enableRateLimit': True})
        ex.load_markets()
        return ex
    except:
        return None

def generate_chart(symbol, side, entry, tp1, tp2, tp3, sl, leverage):
    # fake price history + projection
    try:
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(8, 3.5), dpi=150)
        fig.patch.set_facecolor('#0e0e1a')
        ax.set_facecolor('#0e0e1a')

        # generate sample line
        x = np.arange(0, 60)
        y = entry + np.cumsum(np.random.randn(60) * 0.01 * entry)
        y = np.clip(y, entry*0.92, entry*1.08)

        ax.plot(x, y, color='#ff4444' if side=='SHORT' else '#00ff88', linewidth=1.5)
        ax.axhline(entry, color='white', linestyle='--', linewidth=0.8, alpha=0.7)
        ax.axhline(tp1, color='#00ff88', linestyle=':', linewidth=0.6, alpha=0.5)
        ax.axhline(sl, color='#ff0000', linestyle='-', linewidth=0.8, alpha=0.8)

        ax.set_title(f"{symbol} {side} {leverage} - ENTRY & EXIT", color='white', fontsize=9, pad=10)
        ax.tick_params(colors='gray', labelsize=7)
        for spine in ax.spines.values():
            spine.set_color('#333')

        plt.tight_layout()
        path = f"/tmp/{symbol.replace('/','')}.png"
        plt.savefig(path, facecolor='#0e0e1a')
        plt.close()
        return path
    except Exception as e:
        print(f"Chart error {e}")
        return None

def scan_exchange(exchange, limit=150):
    pumps = []
    try:
        tickers = exchange.fetch_tickers()
        sorted_t = sorted(tickers.items(), key=lambda x: x[1].get('quoteVolume',0) or 0, reverse=True)
        for symbol, data in sorted_t[:limit*3]:
            if '/USDT' not in symbol: continue
            if len(pumps) >= limit: break
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, '5m', limit=20)
                if len(ohlcv) < 20: continue
                last = ohlcv[-1][4]
                prev = ohlcv[-2][4]
                change_5m = ((last-prev)/prev*100) if prev else 0
                last_vol = ohlcv[-1][5]
                avg_vol = sum(c[5] for c in ohlcv[-6:-1]) / 5
                vol_mult = last_vol / avg_vol if avg_vol else 0
                quote_vol = data.get('quoteVolume',0) or 0
                if quote_vol < 500000: continue
                if vol_mult < 2.0: continue
                if abs(change_5m) < 3.8: continue

                ema7 = sum(c[4] for c in ohlcv[-7:]) / 7
                side = "LONG" if last > ema7 and change_5m > 0 else "SHORT" if last < ema7 and change_5m < 0 else None
                if not side: continue

                score = 70
                if abs(change_5m) >= 5: score+=10
                if vol_mult >= 3: score+=10
                if quote_vol > 2000000: score+=10
                score = min(score, 99)

                entry = last
                if side == "LONG":
                    tp1 = entry * 1.015
                    tp2 = entry * 1.03
                    tp3 = entry * 1.05
                    sl = entry * 0.97
                else:
                    tp1 = entry * 0.985
                    tp2 = entry * 0.97
                    tp3 = entry * 0.95
                    sl = entry * 1.03

                leverage = "10x" if score >= 80 else "8x"
                margin = "Isolated"

                pumps.append({
                    'symbol': symbol.replace('/',''), 'symbol_ccxt': symbol,
                    'exchange': exchange.id, 'change': change_5m,
                    'vol_mult': vol_mult, 'score': score, 'side': side,
                    'entry': entry, 'tp1': tp1, 'tp2': tp2, 'tp3': tp3, 'sl': sl,
                    'leverage': leverage, 'margin': margin
                })
            except:
                continue
    except Exception as e:
        print(f"{exchange.id} error {e}")
    return pumps

def main():
    okx = get_exchange('okx')
    gate = get_exchange('gate')
    all_found = []
    total = 0

    if okx:
        print("Using OKX exchange - OK")
        r = scan_exchange(okx, 150)
        print(f"OKX scanned 150, pumps: {len(r)}")
        all_found.extend(r); total+=150; time.sleep(2)
    if gate:
        print("Using GATE exchange - OK")
        r = scan_exchange(gate, 150)
        print(f"GATE scanned 150, pumps: {len(r)}")
        all_found.extend(r); total+=150

    print(f"Scanning {total} coins on okx+gate... 70/100")
    print(f"Done. Found {len(all_found)}")

    now = datetime.now(timezone.utc)
    if now.hour == 8 and now.minute < 10:
        send_text(f"✅ Bot Alive - {total}/100 active\nScanning OKX+GATE ({total} coins)")

    if not all_found:
        print("No trend found - market sideways, will try next run")
        return

    for c in sorted(all_found, key=lambda x: x['score'], reverse=True)[:2]:
        chart_path = generate_chart(c['symbol'], c['side'], c['entry'], c['tp1'], c['tp2'], c['tp3'], c['sl'], c['leverage'])

        # EXACT FORMAT FROM YOUR SCREENSHOT
        color_emoji = "🔴" if c['side']=="SHORT" else "🟢"
        caption = f"""🚀 FUTURE CALLS - Herocallss 🚀
_______________________

🪙 Coin: {c['symbol']}
📊 Signal: {color_emoji} {c['side']}
⚡ Leverage: {c['leverage']} {c['margin']}

_______________________

🔵 ENTRY PRICE:
{round(c['entry'], 6) if c['entry'] < 1 else round(c['entry'], 4)}

🟢 EXIT PRICES (Take Profit):
TP1: {round(c['tp1'], 6) if c['tp1'] < 1 else round(c['tp1'], 4)}
TP2: {round(c['tp2'], 6) if c['tp2'] < 1 else round(c['tp2'], 4)}
TP3: {round(c['tp3'], 6) if c['tp3'] < 1 else round(c['tp3'], 4)}

🔴 EXIT PRICE (Stop Loss):
SL: {round(c['sl'], 6) if c['sl'] < 1 else round(c['sl'], 4)}

_______________________

⏰ {now.strftime('%Y-%m-%d %H:%M UTC')}
⚠️ 1-2% risk per trade.
@Herocallss
"""
        if chart_path:
            send_signal_with_chart(chart_path, caption)
        else:
            send_text(caption)
        print(f"Sent {c['symbol']} {c['side']}")
        time.sleep(2)

if __name__ == "__main__":
    main()
