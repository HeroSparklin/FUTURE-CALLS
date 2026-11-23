import ccxt
import pandas as pd
import numpy as np
import requests
import os
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

# --- TELEGRAM CONFIG - FIXED FOR YOUR YML ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHANNEL_ID")

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"Telegram not configured - Token: {bool(TELEGRAM_TOKEN)} Chat: {bool(TELEGRAM_CHAT_ID)}", flush=True)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=15)
        if r.status_code == 200:
            print("Telegram sent", flush=True)
        else:
            print(f"Telegram failed: {r.text}", flush=True)
    except Exception as e:
        print(f"Telegram error: {e}", flush=True)

# --- EXCHANGE - OKX LOCKED - NO BINANCE ---
exchange = ccxt.okx({'enableRateLimit': True})

def get_ohlcv(symbol, timeframe, limit=120):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        if not ohlcv:
            return None
        df = pd.DataFrame(ohlcv, columns=['ts','open','high','low','close','volume'])
        return df
    except Exception as e:
        print(f"Error {symbol} {timeframe}: {e}", flush=True)
        return None

def calc_indicators(df):
    if df is None or len(df) < 50:
        return None
    try:
        df['ema7'] = df['close'].ewm(span=7, adjust=False).mean()
        df['ema25'] = df['close'].ewm(span=25, adjust=False).mean()
        df['ema99'] = df['close'].ewm(span=99, adjust=False).mean()
        df['sma200'] = df['close'].rolling(200).mean()
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = ema12 - ema26
        df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        df['macd_hist'] = df['macd'] - df['macd_signal']
        df['tr'] = np.maximum(df['high']-df['low'], np.maximum(abs(df['high']-df['close'].shift(1)), abs(df['low']-df['close'].shift(1))))
        df['atr'] = df['tr'].rolling(14).mean()
        df['vol_avg'] = df['volume'].rolling(20).mean()
        return df
    except:
        return None

def get_btc_trend():
    try:
        df_1h_raw = get_ohlcv('BTC/USDT', '1h', 120)
        if df_1h_raw is None or len(df_1h_raw) < 50:
            return "NORMAL", False, 0
        df_1h = calc_indicators(df_1h_raw)
        if df_1h is None or len(df_1h) < 50:
            return "NORMAL", False, 0
        last = df_1h.iloc[-1]

        df_4h_raw = get_ohlcv('BTC/USDT', '4h', 50)
        if df_4h_raw is None:
            return "BULLISH" if last['ema7'] > last['ema25'] else "NORMAL", False, 0
        df_4h = calc_indicators(df_4h_raw)
        if df_4h is None:
            return "NORMAL", False, 0
        last_4h = df_4h.iloc[-1]

        atr_pct = (last['atr'] / last['close']) * 100 if last['atr'] else 0
        is_volatile = atr_pct > 2.0
        change_24h = ((last['close'] - df_1h.iloc[-25]['close']) / df_1h.iloc[-25]['close']) * 100 if len(df_1h) > 25 else 0

        if last_4h['ema7'] < last_4h['ema25'] and change_24h < -3:
            return "BEARISH_SLOW_DROP", is_volatile, change_24h
        if last['ema7'] > last['ema25'] and last['close'] > last['sma200']:
            return "BULLISH", is_volatile, change_24h
        if last['ema7'] < last['ema25'] and last['close'] < last['sma200']:
            return "BEARISH", is_volatile, change_24h
        return "NORMAL", is_volatile, change_24h
    except Exception as e:
        print(f"BTC trend error: {e}", flush=True)
        return "NORMAL", False, 0

def analyze_coin(symbol, btc_trend, btc_volatile):
    try:
        ticker = exchange.fetch_ticker(symbol)
        spread = ((ticker['ask'] - ticker['bid']) / ticker['bid']) * 100 if ticker['bid'] else 999
        if spread > 0.15:
            print(f"{symbol} REJECT spread {spread:.3f}%", flush=True)
            return None
        change_24h = ticker['percentage'] if ticker['percentage'] else 0
        if abs(change_24h) < 3:
            return None

        df_5m = calc_indicators(get_ohlcv(symbol, '5m', 120))
        df_15m = calc_indicators(get_ohlcv(symbol, '15m', 120))
        df_1h = calc_indicators(get_ohlcv(symbol, '1h', 120))
        if df_5m is None or df_15m is None or df_1h is None:
            return None

        c1h = df_1h.iloc[-1]
        momentum = ((c1h['close'] - df_1h.iloc[-2]['close']) / df_1h.iloc[-2]['close']) * 100
        if abs(momentum) < 0.5:
            return None

        is_crash_short = change_24h <= -12 or momentum <= -3.0
        is_crash_long = change_24h >= 12 or momentum >= 3.0
        is_crash = is_crash_short or is_crash_long
        if is_crash:
            print(f"{symbol} CRASH MODE ON: 24h {change_24h:.1f}% Mom {momentum:.2f}%", flush=True)

        ema_dist = abs((c1h['close'] - c1h['ema7']) / c1h['ema7']) * 100
        if not is_crash and ema_dist > 3.5:
            print(f"{symbol} REJECT ema_dist {ema_dist:.2f}%", flush=True)
            return None

        long_stack = c1h['ema7'] > c1h['ema25'] > c1h['ema99']
        short_stack = c1h['ema7'] < c1h['ema25'] < c1h['ema99']
        direction = None
        if long_stack and c1h['close'] > c1h['sma200']:
            direction = "LONG"
        elif short_stack and c1h['close'] < c1h['sma200']:
            direction = "SHORT"
        else:
            if is_crash:
                if long_stack: direction = "LONG"
                elif short_stack: direction = "SHORT"
                else: return None
            else:
                return None

        if is_crash_short: direction = "SHORT"
        if is_crash_long: direction = "LONG"

        def tf_dir(df):
            last = df.iloc[-1]
            return "LONG" if last['ema7'] > last['ema25'] else "SHORT" if last['ema7'] < last['ema25'] else None

        if is_crash:
            if tf_dir(df_15m) != direction or tf_dir(df_1h) != direction:
                print(f"{symbol} REJECT crash TF 15m/1h mismatch", flush=True)
                return None
        else:
            if tf_dir(df_5m) != direction or tf_dir(df_15m) != direction or tf_dir(df_1h) != direction:
                return None

        rsi = c1h['rsi']
        if not is_crash:
            if direction == "LONG" and not (55 <= rsi <= 75): return None
            if direction == "SHORT" and not (20 <= rsi <= 45): return None
            if direction == "LONG" and not (c1h['macd'] > c1h['macd_signal'] and c1h['macd_hist'] > 0): return None
            if direction == "SHORT" and not (c1h['macd'] < c1h['macd_signal'] and c1h['macd_hist'] < 0): return None
        else:
            if direction == "LONG" and not (c1h['macd_hist'] > 0): return None
            if direction == "SHORT" and not (c1h['macd_hist'] < 0): return None

        vol_ratio = c1h['volume'] / c1h['vol_avg'] if c1h['vol_avg'] else 0
        if vol_ratio < 1.3: return None

        if not is_crash:
            if btc_trend == "BEARISH_SLOW_DROP" and direction == "LONG": return None
            if btc_volatile:
                if btc_trend == "BULLISH" and direction == "SHORT": return None
                if btc_trend == "BEARISH" and direction == "LONG": return None

        if is_crash:
            score = 95
        else:
            score = 70
            if vol_ratio > 1.8: score += 10
            elif vol_ratio > 1.5: score += 5
            if abs(momentum) > 1.5: score += 10
            elif abs(momentum) > 1.0: score += 5
            if direction == "LONG" and 60 <= rsi <= 70: score += 5
            if direction == "SHORT" and 25 <= rsi <= 40: score += 5
            if score > 100: score = 100
            if score < 90: return None

        if is_crash:
            lev, certainty = 5, "CRASH MODE"
        elif score >= 98:
            lev, certainty = 20, "VERY HIGH"
        elif score >= 96:
            lev, certainty = 10, "HIGH"
        elif score >= 93:
            lev, certainty = 5, "MEDIUM"
        else:
            lev, certainty = 3, "LOW"

        atr, price = c1h['atr'], c1h['close']
        sl, tp = (price - atr*1.5, price + atr*3) if direction == "LONG" else (price + atr*1.5, price - atr*3)

        return {'symbol':symbol,'direction':direction,'price':price,'sl':sl,'tp':tp,'score':score,'lev':lev,'certainty':certainty,'rsi':rsi,'vol_ratio':vol_ratio,'momentum':momentum,'is_crash':is_crash}
    except Exception as e:
        print(f"Analyze error {symbol}: {e}", flush=True)
        return None

def main():
    print("Bot started...", flush=True)
    start_time = time.time()
    # ALIVE FIRST - BEFORE SCAN, SO IT IS NEVER LATE
    send_telegram(f"✅ BOT ALIVE\n⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}\nStarting scan...")
    btc_trend, btc_volatile, btc_change = get_btc_trend()
    print(f"BTC Trend: {btc_trend} Volatile: {btc_volatile} Change: {btc_change:.2f}%", flush=True)
    try:
        tickers = exchange.fetch_tickers()
        pairs = [(s, t['quoteVolume']) for s, t in tickers.items() if s.endswith('/USDT') and ':USDT' not in s and t.get('quoteVolume')]
        pairs.sort(key=lambda x: x[1], reverse=True)
        top_coins = [s for s, v in pairs[:80]]
    except Exception as e:
        print(f"Ticker error: {e}", flush=True)
        top_coins = ['BTC/USDT','ETH/USDT','SOL/USDT','XRP/USDT','DOGE/USDT']

    signals = []
    # FASTER + SAFE: 5 at a time, same 80 coins, same filters, no OKX rate-limit
    def _scan(sym):
        if sym == 'BTC/USDT':
            return None
        return analyze_coin(sym, btc_trend, btc_volatile)

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(_scan, top_coins))
    signals = [r for r in results if r]

    signals.sort(key=lambda x: x['score'], reverse=True)
    signals = signals[:3]

    if signals:
        for s in signals:
            crash_tag = " 🔥 CRASH" if s.get('is_crash') else ""
            msg = f"""🚀 SIGNAL {s['direction']} {s['symbol']}{crash_tag}

💰 Entry: {s['price']:.6f}
🛑 SL: {s['sl']:.6f}
🎯 TP: {s['tp']:.6f}

⚡ Leverage: {s['lev']}x ({s['certainty']} - Score {s['score']})
📊 RSI: {s['rsi']:.1f} | Vol: {s['vol_ratio']:.2f}x | Mom: {s['momentum']:.2f}%
🧠 BTC: {btc_trend}
⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}"""
            send_telegram(msg)
    else:
        print("No signals - all filtered", flush=True)
        print(f"Done in {time.time()-start_time:.1f}s - Scanned {len(top_coins)} coins", flush=True)

if __name__ == "__main__":
    main()
