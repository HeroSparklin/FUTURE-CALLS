import os
import ccxt
import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timezone

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MIN_SCORE = 90
TOP_COINS = 80

exchange = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})

def send_telegram(msg):
    try:
        if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
            print("Telegram secrets missing, skipping send")
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_indicators(df):
    try:
        close = df['close']
        ema7 = close.ewm(span=7, adjust=False).mean()
        ema14 = close.ewm(span=14, adjust=False).mean()
        ema28 = close.ewm(span=28, adjust=False).mean()
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / (loss.replace(0, np.nan))
        rsi = 100 - (100 / (1 + rs))
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        sig = macd.ewm(span=9, adjust=False).mean()
        hist = macd - sig
        vol = df['volume']
        vol_sma = vol.rolling(20).mean()
        vol_ratio = vol.iloc[-1] / vol_sma.iloc[-1] if vol_sma.iloc[-1] and vol_sma.iloc[-1] != 0 else 0
        mom = (close.iloc[-1] - close.iloc[-4]) / close.iloc[-4] * 100 if len(close) >= 5 else 0
        tr = pd.concat([df['high'] - df['low'], (df['high'] - close.shift()).abs(), (df['low'] - close.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        return {
            'price': float(close.iloc[-1]), 'ema7': float(ema7.iloc[-1]), 'ema14': float(ema14.iloc[-1]), 'ema28': float(ema28.iloc[-1]),
            'sma20': float(sma20.iloc[-1]) if not pd.isna(sma20.iloc[-1]) else 0,
            'sma50': float(sma50.iloc[-1]) if not pd.isna(sma50.iloc[-1]) else 0,
            'rsi': float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50,
            'macd': float(macd.iloc[-1]), 'sig': float(sig.iloc[-1]), 'hist': float(hist.iloc[-1]),
            'vol_ratio': float(vol_ratio), 'mom': float(mom),
            'atr': float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0,
        }
    except Exception as e:
        print(f"Indicator error: {e}")
        return None

def analyze_tf(df):
    ind = get_indicators(df)
    if not ind: return "NEUTRAL", None
    if ind['price'] > ind['ema7'] > ind['ema14'] and ind['macd'] > ind['sig'] and ind['rsi'] >= 55:
        return "BULLISH", ind
    if ind['price'] < ind['ema7'] < ind['ema14'] and ind['macd'] < ind['sig'] and ind['rsi'] <= 45:
        return "BEARISH", ind
    return "NEUTRAL", ind

def get_btc_trend():
    try:
        df = exchange.fetch_ohlcv("BTC/USDT", timeframe="1h", limit=60)
        df = pd.DataFrame(df, columns=['time','open','high','low','close','volume'])
        trend, _ = analyze_tf(df)
        df15 = exchange.fetch_ohlcv("BTC/USDT", timeframe="15m", limit=20)
        df15 = pd.DataFrame(df15, columns=['time','open','high','low','close','volume'])
        vol_pct = abs((df15['close'].iloc[-1] - df15['close'].iloc[0]) / df15['close'].iloc[0] * 100) if len(df15)>0 else 0
        vol_state = "VOLATILE" if vol_pct > 2.0 else "NORMAL"
        return trend, vol_state, vol_pct
    except Exception as e:
        print(f"BTC trend error: {e}")
        return "NEUTRAL", "NORMAL", 0

def is_btc_slow_drop():
    try:
        df4h = exchange.fetch_ohlcv("BTC/USDT", timeframe="4h", limit=60)
        df4h = pd.DataFrame(df4h, columns=['time','open','high','low','close','volume'])
        trend4h, _ = analyze_tf(df4h)
        df1h = exchange.fetch_ohlcv("BTC/USDT", timeframe="1h", limit=60)
        df1h = pd.DataFrame(df1h, columns=['time','open','high','low','close','volume'])
        prev_1h_low = float(df1h['low'].iloc[-2])
        curr_price = float(df1h['close'].iloc[-1])
        ticker = exchange.fetch_ticker("BTC/USDT")
        change_24h = float(ticker.get('percentage', 0) or 0)
        print(f"BTC SLOW-DROP CHECK: 4h={trend4h} Price={curr_price:.0f} Prev1hLow={prev_1h_low:.0f} 24hChange={change_24h:.2f}%")
        if trend4h == "BEARISH" and curr_price < prev_1h_low and change_24h <= -3.0:
            return True, f"4h BEARISH + Broke 1h Low {prev_1h_low:.0f} + 24h {change_24h:.2f}%"
        return False, ""
    except Exception as e:
        print(f"BTC slow-drop error: {e}")
        return False, ""

def calculate_score(ind15, tf5, tf15, tf1h, direction, vol_ratio):
    score = 0
    if direction == "LONG":
        if tf5 == "BULLISH": score += 15
        if tf15 == "BULLISH": score += 15
        if tf1h == "BULLISH": score += 20
        if ind15['price'] > ind15['ema7'] > ind15['ema14'] > ind15['ema28']: score += 10
        if ind15['price'] > ind15['sma20'] > ind15['sma50']: score += 10
        if 55 <= ind15['rsi'] <= 75: score += 10
        if ind15['macd'] > ind15['sig'] and ind15['hist'] > 0: score += 10
        if vol_ratio >= 1.3: score += 10
    else:
        if tf5 == "BEARISH": score += 15
        if tf15 == "BEARISH": score += 15
        if tf1h == "BEARISH": score += 20
        if ind15['price'] < ind15['ema7'] < ind15['ema14'] < ind15['ema28']: score += 10
        if ind15['price'] < ind15['sma20'] < ind15['sma50']: score += 10
        if 20 <= ind15['rsi'] <= 45: score += 10
        if ind15['macd'] < ind15['sig'] and ind15['hist'] < 0: score += 10
        if vol_ratio >= 1.3: score += 10
    return score

def main():
    try:
        print(f"--- Scan {datetime.now(timezone.utc)} ---")
        btc_trend, btc_vol_state, btc_vol_pct = get_btc_trend()
        print(f"BTC: {btc_trend} VOL:{btc_vol_pct:.2f}% {btc_vol_state}")
        btc_slow_drop, btc_slow_reason = is_btc_slow_drop()
        try:
            tickers = exchange.fetch_tickers()
        except Exception as e:
            print(f"Ticker fetch failed: {e}")
            return
        usdt_pairs = {s: t for s, t in tickers.items() if s.endswith("/USDT") and t.get('quoteVolume')}
        sorted_pairs = sorted(usdt_pairs.items(), key=lambda x: x[1]['quoteVolume'], reverse=True)[:TOP_COINS]
        for symbol, ticker in sorted_pairs:
            try:
                if symbol.split("/")[0] in ["USDC","USDT","DAI","FDUSD","TUSD","USDP","XAUT","PAXG"]:
                    continue
                change = float(ticker.get('percentage', 0) or 0)
                if abs(change) < 3:
                    continue
                df5 = pd.DataFrame(exchange.fetch_ohlcv(symbol, timeframe="5m", limit=60), columns=['time','open','high','low','close','volume'])
                df15 = pd.DataFrame(exchange.fetch_ohlcv(symbol, timeframe="15m", limit=60), columns=['time','open','high','low','close','volume'])
                df1h = pd.DataFrame(exchange.fetch_ohlcv(symbol, timeframe="1h", limit=60), columns=['time','open','high','low','close','volume'])
                df4h = pd.DataFrame(exchange.fetch_ohlcv(symbol, timeframe="4h", limit=60), columns=['time','open','high','low','close','volume'])
                tf5, _ = analyze_tf(df5)
                tf15, ind15 = analyze_tf(df15)
                tf1h, _ = analyze_tf(df1h)
                tf4h, _ = analyze_tf(df4h)
                if not ind15:
                    continue
                direction = "LONG" if change >= 3 else "SHORT"
                price = ind15['price']; mom = ind15['mom']; vol_ratio = ind15['vol_ratio']; rsi = ind15['rsi']
                is_btc = (symbol == "BTC/USDT")
                use_btc_slow = is_btc and direction == "SHORT" and btc_slow_drop
                if use_btc_slow:
                    print(f"BTC SLOW-DROP MODE ACTIVATED: {btc_slow_reason}")
                if not use_btc_slow:
                    if abs(mom) < 0.5:
                        print(f"REJECT {symbol}: MOM_LOW {mom:.2f}%")
                        continue
                    if direction == "LONG" and not (tf5 == "BULLISH" and tf15 == "BULLISH" and tf1h == "BULLISH"):
                        print(f"REJECT {symbol}: TF MISMATCH {tf5}/{tf15}/{tf1h}")
                        continue
                    if direction == "SHORT" and not (tf5 == "BEARISH" and tf15 == "BEARISH" and tf1h == "BEARISH"):
                        print(f"REJECT {symbol}: TF MISMATCH {tf5}/{tf15}/{tf1h}")
                        continue
                if direction == "LONG" and btc_trend == "BEARISH" and btc_vol_state == "VOLATILE":
                    if not use_btc_slow:
                        print(f"REJECT {symbol}: BTC BEAR VOLATILE BLOCK LONG")
                        continue
                if direction == "SHORT" and btc_trend == "BULLISH" and btc_vol_state == "VOLATILE":
                    if not use_btc_slow:
                        print(f"REJECT {symbol}: BTC BULL VOLATILE BLOCK SHORT")
                        continue
                score = calculate_score(ind15, tf5, tf15, tf1h, direction, vol_ratio)
                if use_btc_slow:
                    bonus = 0
                    if tf5 != "BEARISH": bonus += 15
                    if tf15 != "BEARISH": bonus += 15
                    if ind15['price'] < ind15['ema7'] and ind15['macd'] < ind15['sig']:
                        score += bonus
                if score < MIN_SCORE:
                    print(f"REJECT {symbol}: Score {score} MOM {mom:.2f}%")
                    continue
                atr = ind15['atr'] if ind15['atr'] else price * 0.01
                if direction == "LONG":
                    tp1 = price + atr * 1.5; tp2 = price + atr * 3.0; sl = price - atr * 1.0
                else:
                    tp1 = price - atr * 1.5; tp2 = price - atr * 3.0; sl = price + atr * 1.0
                extra = f"\n⚠️ BTC SLOW-DROP: {btc_slow_reason}" if use_btc_slow else ""
                msg = f"🚨 *SIGNAL {symbol} {direction}* Score {score}\nPrice: {price}\n24h: {change:.2f}%\nMOM: {mom:.2f}% | Vol: {vol_ratio:.2f}x | RSI: {rsi:.1f}\nTF: 5m {tf5} | 15m {tf15} | 1h {tf1h} | 4h {tf4h}\nTP1: {tp1:.4f} | TP2: {tp2:.4f} | SL: {sl:.4f}{extra}"
                print(msg)
                send_telegram(msg)
                time.sleep(1)
            except Exception as e:
                print(f"Error {symbol}: {e}")
                continue
    except Exception as e:
        print(f"MAIN ERROR but not failing: {e}")
    print("Scan finished OK")

if __name__ == "__main__":
    main()
