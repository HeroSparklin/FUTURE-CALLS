import ccxt
import requests
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import io
from datetime import datetime

# ===== TELEGRAM =====
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# ===== LOCKED TRADE PLAN - EDIT HERE ONLY =====
POSITION_USDT = 20 # $ per trade
LEVERAGE = 20 # 20x
TP1_PCT = 4.0 # TP1 %
TP2_PCT = 8.0 # TP2 %
SL_PCT = 2.5 # SL %
# ==============================================

# ===== EXCHANGES =====
EXCHANGES = {
 'GATE': ccxt.gate(),
 'OKX': ccxt.okx(),
 'MEXC': ccxt.mexc(),
 'BITGET': ccxt.bitget(),
}

THRESHOLD = 80 # Strict 80/100
TIMEFRAME = '5m'

def send_telegram(text):
 if not BOT_TOKEN or not CHAT_ID:
 print("Missing BOT_TOKEN/CHAT_ID")
 return
 url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
 try:
 requests.post(url, json={"chat_id": CHAT_ID, "text": text}, timeout=10)
 except Exception as e:
 print(f"Telegram error: {e}")

def send_chart(symbol, side, ex_name, score, change, vol_mult, ohlcv, entry_price):
 if not BOT_TOKEN or not CHAT_ID:
 return

 # Calculate TP/SL
 if side == "LONG":
 tp1 = entry_price * (1 + TP1_PCT/100)
 tp2 = entry_price * (1 + TP2_PCT/100)
 sl = entry_price * (1 - SL_PCT/100)
 else:
 tp1 = entry_price * (1 - TP1_PCT/100)
 tp2 = entry_price * (1 - TP2_PCT/100)
 sl = entry_price * (1 + SL_PCT/100)

 closes = [c[4] for c in ohlcv[-50:]]

 # Chart
 plt.figure(figsize=(8,4))
 plt.plot(closes, linewidth=2)
 plt.title(f"{symbol} {side} - Score {score}/100")
 plt.grid(True, alpha=0.3)
 plt.tight_layout()
 buf = io.BytesIO()
 plt.savefig(buf, format='png')
 plt.close()
 buf.seek(0)

 # Locked plan text
 caption = (
 f"🚀 FUTURE CALLS {symbol} {side}\n"
 f"Ex: {ex_name} | Score {score}/100 | {change:+.2f}% | x{vol_mult:.1f} Vol\n\n"
 f"ENTRY: {entry_price:.8g} (MARKET)\n"
 f"LEVERAGE: {LEVERAGE}x Isolated\n"
 f"AMOUNT: ${POSITION_USDT} (~${POSITION_USDT*LEVERAGE} position)\n\n"
 f"TP1: +{TP1_PCT}% -> {tp1:.8g} (50%)\n"
 f"TP2: +{TP2_PCT}% -> {tp2:.8g} (50%)\n"
 f"SL: -{SL_PCT}% -> {sl:.8g}\n\n"
 f"Risk: ${POSITION_USDT*SL_PCT/100:.2f} | Set SL tight!"
 )

 url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
 try:
 requests.post(url, data={"chat_id": CHAT_ID, "caption": caption}, files={"photo": buf}, timeout=15)
 except Exception as e:
 print(f"Chart send error: {e}")
 send_telegram(caption)

def get_ema(data, period):
 if len(data) < period: return None
 return sum(data[-period:]) / period

def analyze():
 all_markets = {}
 btc_change_5m = 0

 # Get BTC trend first
 try:
 btc_ticker = EXCHANGES['GATE'].fetch_ohlcv('BTC/USDT', TIMEFRAME, limit=6)
 if len(btc_ticker) >= 2:
 btc_change_5m = ((btc_ticker[-1][4] - btc_ticker[-2][4]) / btc_ticker[-2][4]) * 100
 except:
 pass

 scanned = 0
 signals = []

 for ex_name, ex in EXCHANGES.items():
 try:
 ex.load_markets()
 tickers = ex.fetch_tickers()
 # Top 50 by quoteVolume USDT only
 usdt = {s: t for s, t in tickers.items() if '/USDT' in s and t.get('quoteVolume')}
 sorted_coins = sorted(usdt.items(), key=lambda x: x[1]['quoteVolume'] or 0, reverse=True)[:50]

 for symbol, ticker in sorted_coins:
 if symbol in all_markets: continue
 all_markets[symbol] = True
 scanned += 1
 try:
 ohlcv = ex.fetch_ohlcv(symbol, TIMEFRAME, limit=50)
 if len(ohlcv) < 20: continue

 last = ohlcv[-1]
 prev = ohlcv[-2]
 close = last[4]
 prev_close = prev[4]
 change = ((close - prev_close) / prev_close) * 100
 vol = last[5]
 avg_vol = sum([c[5] for c in ohlcv[-6:-1]]) / 5
 if avg_vol == 0: continue
 vol_mult = vol / avg_vol
 qv = ticker.get('quoteVolume', 0) or 0
 closes = [c[4] for c in ohlcv]

 # STRICT FILTERS
 if qv < 500000: continue
 if abs(change) < 2.5: continue
 if vol_mult < 1.5: continue

 ema7 = get_ema(closes, 7)
 if not ema7: continue
 if change > 0 and close < ema7: continue
 if change < 0 and close > ema7: continue

 # BTC FILTER
 if change > 0 and btc_change_5m < -1.0: continue # Don't long if BTC dumping
 if change < 0 and btc_change_5m > 1.0: continue # Don't short if BTC pumping

 # SCORING
 score = 50
 if abs(change) >= 2.5: score += 5
 if abs(change) >= 3.5: score += 10
 if abs(change) >= 5.0: score += 10
 if vol_mult >= 1.5: score += 5
 if vol_mult >= 2.5: score += 10
 if vol_mult >= 3.5: score += 10
 if qv > 2000000: score += 5
 if qv > 5000000: score += 5
 score = min(score, 99)

 if score >= THRESHOLD:
 side = "LONG" if change > 0 else "SHORT"
 signals.append((symbol, side, ex_name, score, change, vol_mult, ohlcv, close))
 if len(signals) >= 3: break
 except:
 continue
 if len(signals) >= 3: break
 except Exception as e:
 print(f"{ex_name} error {e}")
 continue

 # SEND
 if signals:
 for sym, side, exn, score, chg, vm, ohlcv_data, entry in signals:
 send_chart(sym, side, exn, score, chg, vm, ohlcv_data, entry)
 else:
 now = datetime.utcnow().strftime("%H:%M UTC")
 send_telegram(f"💓 Bot Lively - No signal at the moment\nScanned {scanned} coins - all below 80/100\nBTC 5m: {btc_change_5m:+.2f}% | Next scan in 5min - {now}")

if _name_ == "_main_":
 analyze()
