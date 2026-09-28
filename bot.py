def check(symbol):
    try:
        ohlcv = BINANCE.fetch_ohlcv(symbol, timeframe='15m', limit=50)
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        if len(closes) < 22: return None
        entry = closes[-1]
        ema9 = sum(closes[-9:])/9
        ema21 = sum(closes[-21:])/21

        # STRICT FILTERS
        avg_vol = sum(volumes[-10:])/10
        if volumes[-1] < avg_vol * 0.8: # need volume pump
            return None

        # Need strong trend distance (0.2%)
        diff_pct = (ema9 - ema21) / entry
        if abs(diff_pct) < 0.002:
            return None

        if diff_pct > 0: # LONG
            side="LONG"; tp1=entry*1.008; tp2=entry*1.015; tp3=entry*1.03; sl=entry*0.97
        else: # SHORT
            side="SHORT"; tp1=entry*0.992; tp2=entry*0.985; tp3=entry*0.97; sl=entry*1.03

        return f"🚀 FUTURE-CALL: {symbol} - {side}\nEntry: {entry:.4f}\nTP1: {tp1:.4f}\nTP2: {tp2:.4f}\nTP3: {tp3:.4f}\nSL: {sl:.4f}\n\nStrict ✅ Vol+Trend"
    except:
        return None
