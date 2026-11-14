import ccxt
import pandas as pd
import numpy as np
import requests
import os
import time
from datetime import datetime, timezone

# --- TELEGRAM CONFIG - FIXED FOR YOUR YML ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID") or os.getenv("TELEGRAM_CHANNEL_ID")

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(f"Telegram not configured - Token: {bool(TELEGRAM_TOKEN)} Chat: {bool(TELEGRAM_CHAT_ID)}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=15)
        if r.status_code == 200:
            print("Telegram sent")
        else:
            print(f"Telegram failed: {r.text}")
    except Exception as e:
        print(f"Telegram error: {e}")

# --- EXCHANGE ---
exchange = ccxt.okx({
    'enableRateLimit': True,
})

def get_ohlcv(symbol, timeframe, limit=120):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['ts','open','high','low','close','volume'])
        return df
    except Exception as e:
        print(f"Error {symbol} {timeframe}: {e}")
        return None

def calc_indicators(df):
    if df is None or len(df) < 100:
        return None
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

def get_btc_trend():
    try:
        df_1h = calc_indicators(get_ohlcv('BTC/USDT', '1h', 120))
        last = df_1h.iloc[-1]
        df_4h = calc_indicators(get_ohlcv('BTC/USDT', '4h', 50))
        last_4h = df_4h.iloc[-1]
        atr_pct = (last['atr'] / last['close']) * 100
        is_volatile = atr_pct > 0.8
        change_24h = ((last['close'] - df_1h.iloc[-25]['close']) / df_1h.iloc[-25]['close']) * 100
        slow_drop = False
        if last_4h['ema7'] < last_4h['ema25'] and change_24h < -3:
            slow_drop = True
        if slow_drop:
            return "BEARISH_SLOW_DROP", is_volatile, change_24h
        if last['ema7'] > last['ema25'] and last['close'] > last['sma200']:
            return "BULLISH", is_volatile, change_24h
        if last['ema7'] < last['ema25'] and last['close'] < last['sma200']:
            return "BEARISH", is_volatile, change_24h
        return "NORMAL", is_volatile, change_24h
    except Exception as e:
        print(f"BTC trend error: {e}")
        return "NORMAL", False, 0

def analyze_coin(symbol, btc_trend, btc_volatile):
    try:
        ticker = exchange.fetch_ticker(symbol)
        spread = ((ticker['ask'] - ticker['bid']) / ticker['bid']) * 100 if ticker['bid'] else 999
        if spread > 0.15:
            return None
        change_24h = ticker['percentage'] if ticker['percentage'] else 0
        if abs(change_24h) < 3:
            return None

        df_5m = calc_indicators(get_ohlcv(symbol, '5m', 120))
        df_15m = calc_indicators(get_ohlcv(symbol, '15m', 120))
        df_1h = calc_indicators(get_ohlcv(symbol, '1h', 120))
        if df_5m is None or df_15m is None or df_1h is None:
            return None

        c5, c15, c1h = df_5m.iloc[-1], df_15m.iloc[-1], df_1h.iloc[-1]

        momentum = ((c1h['close'] - df_1h.iloc[-2]['close']) / df_1h.iloc[-2]['close']) * 100
        if abs(momentum) < 0.5:
            return None
        ema_dist = abs((c1h['close'] - c1h['ema7']) / c1h['ema7']) * 100
        if ema_dist > 3.5:
            return None

        long_stack = c1h['ema7'] > c1h['ema25'] > c1h['ema99']
        short_stack = c1h['ema7'] < c1h['ema25'] < c1h['ema99']
        direction = None
        if long_stack and c1h['close'] > c1h['sma200']:
            direction = "LONG"
        elif short_stack and c1h['close'] < c1h['sma200']:
            direction = "SHORT"
        else:
            return None

        def tf_dir(df):
            last = df.iloc[-1]
            return "LONG" if last['ema7'] > last['ema25'] else "SHORT" if last['ema7'] < last['ema25'] else None

        if tf_dir(df_5m) != direction or tf_dir(df_15m) != direction or tf_dir(df_1h) != direction:
            return None

        rsi = c1h['rsi']
        if direction == "LONG" and not (55 <= rsi <= 75):
            return None
        if direction == "SHORT" and not (20 <= rsi <= 45):
            return None
        if direction == "LONG" and not (c1h['macd'] > c1h['macd_signal'] and c1h['macd_hist'] > 0):
            return None
        if direction == "SHORT" and not (c1h['macd'] < c1h['macd_signal'] and c1h['macd_hist'] < 0):
            return None

        vol_ratio = c1h['volume'] / c1h['vol_avg'] if c1h['vol_avg'] else 0
        if vol_ratio < 1.3:
            return None

        if btc_trend == "BEARISH_SLOW_DROP" and direction == "LONG":
            return None
        if btc_volatile:
            if btc_trend == "BULLISH" and direction == "SHORT":
                return None
            if btc_trend == "BEARISH" and direction == "LONG":
                return None

        score = 70
        if vol_ratio > 1.8: score += 10
        elif vol_ratio > 1.5: score += 5
        if abs(momentum) > 1.5: score += 10
        elif abs(momentum) > 1.0: score += 5
        if direction == "LONG" and 60 <= rsi <= 70: score += 5
        if direction == "SHORT" and 25 <= rsi <= 40: score += 5
        if score > 100: score = 100
        if score < 90: return None

        # DYNAMIC LEVERAGE BY CERTAINTY
        if score >= 98:
            lev, certainty = 20, "VERY HIGH"
        elif score >= 96:
            lev, certainty = 10, "HIGH"
        elif score >= 93:
            lev, certainty = 5, "MEDIUM"
        else:
            lev, certainty = 3, "LOW"

        atr, price = c1h['atr'], c1h['close']
        sl, tp = (price - atr*1.5, price + atr*3) if direction == "LONG" else (price + atr*1.5, price - atr*3)

        return {'symbol':symbol,'direction':direction,'price':price,'sl':sl,'tp':tp,'score':score,'lev':lev,'certainty':certainty,'rsi':rsi,'vol_ratio':vol_ratio,'momentum':momentum}
    except Exception as e:
        print(f"Analyze error {symbol}: {e}")
        return None

def main():
    print("Bot started...")
    btc_trend, btc_volatile, btc_change = get_btc_trend()
    print(f"BTC Trend: {btc_trend} Volatile: {btc_volatile} Change: {btc_change:.2f}%")
    try:
        tickers = exchange.fetch_tickers()
        pairs = [(s, t['quoteVolume']) for s, t in tickers.items() if s.endswith('/USDT') and ':USDT' not in s and t.get('quoteVolume')]
        pairs.sort(key=lambda x: x[1], reverse=True)
        top_coins = [s for s, v in pairs[:80]]
    except Exception as e:
        print(f"Ticker error: {e}")
        top_coins = ['BTC/USDT','ETH/USDT','SOL/USDT','XRP/USDT','DOGE/USDT']

    signals = []
    for sym in top_coins:
        if sym == 'BTC/USDT': continue
        res = analyze_coin(sym, btc_trend, btc_volatile)
        if res: signals.append(res)
        time.sleep(0.2)

    signals.sort(key=lambda x: x['score'], reverse=True)
    signals = signals[:3]
    utc_hour = datetime.now(timezone.utc).hour

    if signals:
        for s in signals:
            msg = f"""🚀 SIGNAL {s['direction']} {s['symbol']}

💰 Entry: {s['price']:.6f}
🛑 SL: {s['sl']:.6f}
🎯 TP: {s['tp']:.6f}

⚡ Leverage: {s['lev']}x ({s['certainty']} Certainty - Score {s['score']})
📊 RSI: {s['rsi']:.1f} | Vol: {s['vol_ratio']:.2f}x | Mom: {s['momentum']:.2f}%
🧠 BTC: {btc_trend}
⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}"""
            send_telegram(msg)
    else:
        print("No signals - all filtered")
        if utc_hour % 4 == 0:
            msg = f"""✅ BOT ALIVE

🧠 BTC Trend: {btc_trend} ({btc_change:.2f}%)
🔍 Scanned 80 coins - No signals, all filtered
⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}
Bot is running normally."""
            send_telegram(msg)

if __name__ == "__main__":
    main()
