import ccxt, time, os
import pandas as pd
import numpy as np
from datetime import datetime

# ========= CONFIG - LOCKED OKX =========
EXCHANGE_ID = 'okx'
SYMBOLS_LIMIT = 80
TIMEFRAME_ENTRY = '5m'
TIMEFRAME_TREND = '15m'
TIMEFRAME_HTF = '1h'
BTC_SYMBOL = 'BTC/USDT'

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# ========= EXCHANGE =========
exchange = ccxt.okx({
    'enableRateLimit': True,
})

def get_btc_trend():
    try:
        ohlcv_1h = exchange.fetch_ohlcv(BTC_SYMBOL, '1h', limit=20)
        df = pd.DataFrame(ohlcv_1h, columns=['ts','open','high','low','close','vol'])
        ema7 = df['close'].ewm(span=7).mean().iloc[-1]
        ema25 = df['close'].ewm(span=25).mean().iloc[-1]
        trend = "BULLISH" if ema7 > ema25 else "BEARISH"
        # volatility check 15m
        ohlcv_15m = exchange.fetch_ohlcv(BTC_SYMBOL, '15m', limit=2)
        chg = abs(ohlcv_15m[-1][4] - ohlcv_15m[-2][4]) / ohlcv_15m[-2][4] * 100
        vol_state = "VOLATILE" if chg > 2 else "NORMAL"
        return trend, vol_state
    except:
        return "NEUTRAL", "NORMAL"

def is_btc_slow_drop():
    try:
        ohlcv_4h = exchange.fetch_ohlcv(BTC_SYMBOL, '4h', limit=10)
        df4 = pd.DataFrame(ohlcv_4h, columns=['ts','open','high','low','close','vol'])
        ema7_4h = df4['close'].ewm(span=7).mean().iloc[-1]
        ema25_4h = df4['close'].ewm(span=25).mean().iloc[-1]
        bear_4h = ema7_4h < ema25_4h
        
        ohlcv_1h = exchange.fetch_ohlcv(BTC_SYMBOL, '1h', limit=3)
        prev_low = ohlcv_1h[-2][3]
        curr_price = ohlcv_1h[-1][4]
        broke = curr_price < prev_low
        
        ticker = exchange.fetch_ticker(BTC_SYMBOL)
        change_24h = ticker.get('percentage', 0) or 0
        
        print(f"BTC SLOW-DROP CHECK: 4h={'BEARISH' if bear_4h else 'BULLISH'} Price={curr_price} Prev1hLow={prev_low} 24h={change_24h:.2f}%")
        return bear_4h and broke and change_24h <= -3
    except Exception as e:
        print(f"Slow drop check error: {e}")
        return False

def analyze_symbol(symbol, btc_trend, btc_vol):
    try:
        # --- TICKER FOR FILTERS ---
        ticker = exchange.fetch_ticker(symbol)
        if ticker['bid'] is None or ticker['ask'] is None:
            return None
        spread = (ticker['ask'] - ticker['bid']) / ticker['ask'] * 100
        
        # FILTER 13: SPREAD PROTECTION (NEW)
        if spread > 0.15:
            return None

        change_24h = ticker.get('percentage', 0) or 0
        # FILTER: 24h change >=3%
        if abs(change_24h) < 3:
            return None

        # --- OHLCV ---
        ohlcv_5m = exchange.fetch_ohlcv(symbol, TIMEFRAME_ENTRY, limit=100)
        ohlcv_15m = exchange.fetch_ohlcv(symbol, TIMEFRAME_TREND, limit=100)
        ohlcv_1h = exchange.fetch_ohlcv(symbol, TIMEFRAME_HTF, limit=100)
        
        df5 = pd.DataFrame(ohlcv_5m, columns=['ts','open','high','low','close','vol'])
        df15 = pd.DataFrame(ohlcv_15m, columns=['ts','open','high','low','close','vol'])
        df1h = pd.DataFrame(ohlcv_1h, columns=['ts','open','high','low','close','vol'])

        close5, close15, close1h = df5['close'], df15['close'], df1h['close']
        price = close5.iloc[-1]

        # --- INDICATORS ---
        ema7_5 = close5.ewm(span=7).mean()
        ema25_5 = close5.ewm(span=25).mean()
        ema99_5 = close5.ewm(span=99).mean()
        sma200_1h = close1h.rolling(200).mean()

        # MOM
        mom = (close1h.iloc[-1] - close1h.iloc[-4]) / close1h.iloc[-4] * 100
        if abs(mom) < 0.5:
            return None

        # FILTER 14: EMA DISTANCE PROTECTION (NEW)
        ema7_val = ema7_5.iloc[-1]
        ema_dist = abs(price - ema7_val) / ema7_val * 100
        if ema_dist > 3.5:
            return None

        # TF ALIGNMENT
        ema7_15 = close15.ewm(span=7).mean().iloc[-1]
        ema25_15 = close15.ewm(span=25).mean().iloc[-1]
        ema7_1h = close1h.ewm(span=7).mean().iloc[-1]
        ema25_1h = close1h.ewm(span=25).mean().iloc[-1]
        
        bull_5 = ema7_5.iloc[-1] > ema25_5.iloc[-1]
        bull_15 = ema7_15 > ema25_15
        bull_1h = ema7_1h > ema25_1h
        bear_5 = not bull_5
        bear_15 = not bull_15
        bear_1h = not bull_1h

        long_tf = bull_5 and bull_15 and bull_1h
        short_tf = bear_5 and bear_15 and bear_1h

        # BTC SLOW DROP BYPASS
        btc_slow_drop = False
        if symbol == BTC_SYMBOL:
            btc_slow_drop = is_btc_slow_drop()
            if btc_slow_drop:
                short_tf = True  # force short even if 5m green

        if not long_tf and not short_tf:
            return None

        # EMA STACK
        if long_tf:
            if not (ema7_5.iloc[-1] > ema25_5.iloc[-1] > ema99_5.iloc[-1]):
                return None
        if short_tf:
            if not (ema7_5.iloc[-1] < ema25_5.iloc[-1] < ema99_5.iloc[-1]):
                return None

        # SMA TREND
        if pd.isna(sma200_1h.iloc[-1]):
            return None
        if long_tf and price < sma200_1h.iloc[-1]:
            return None
        if short_tf and price > sma200_1h.iloc[-1]:
            return None

        # RSI
        delta = close5.diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iloc[-1]
        if long_tf and not (55 <= rsi_val <= 75):
            return None
        if short_tf and not (20 <= rsi_val <= 45):
            if not btc_slow_drop:  # allow bypass for BTC slow drop
                return None

        # MACD
        ema12 = close5.ewm(span=12).mean()
        ema26 = close5.ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        hist = macd - signal
        if long_tf and not (macd.iloc[-1] > signal.iloc[-1] and hist.iloc[-1] > 0):
            return None
        if short_tf and not (macd.iloc[-1] < signal.iloc[-1] and hist.iloc[-1] < 0):
            if not btc_slow_drop:
                return None

        # VOL RATIO
        vol_sma = df5['vol'].rolling(20).mean().iloc[-1]
        if vol_sma == 0:
            return None
        vol_ratio = df5['vol'].iloc[-1] / vol_sma
        if vol_ratio < 1.3:
            return None

        # BTC DYNAMIC BLOCK
        if btc_vol == "VOLATILE":
            if btc_trend == "BEARISH" and long_tf:
                return None
            if btc_trend == "BULLISH" and short_tf:
                return None

        # SCORE
        score = 70
        if vol_ratio >= 1.5: score += 10
        if abs(mom) >= 1: score += 10
        if btc_slow_drop: score += 10
        if rsi_val >= 60 and long_tf: score += 5
        if rsi_val <= 35 and short_tf: score += 5

        if score < 90:
            return None

        direction = "LONG" if long_tf else "SHORT"
        if btc_slow_drop:
            direction = "SHORT"

        # TP/SL ATR
        tr = pd.concat([df5['high']-df5['low'], (df5['high']-close5.shift()).abs(), (df5['low']-close5.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        if direction == "LONG":
            sl = price - atr*1.5
            tp = price + atr*3
        else:
            sl = price + atr*1.5
            tp = price - atr*3

        return {
            'symbol': symbol,
            'direction': direction,
            'price': price,
            'sl': sl,
            'tp': tp,
            'score': score,
            'rsi': rsi_val,
            'vol': vol_ratio,
            'mom': mom,
            'spread': spread,
            'ema_dist': ema_dist
        }
    except Exception as e:
        print(f"Error {symbol}: {e}")
        return None

def main():
    btc_trend, btc_vol = get_btc_trend()
    print(f"BTC Trend: {btc_trend} {btc_vol}")
    # ... rest of your loop with telegram send ...
    # Format: ENTRY: {price} / SL: {sl} / etc.

if __name__ == "__main__":
    main()
