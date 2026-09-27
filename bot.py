def check_signal(symbol):
    try:
        if symbol in ["EURGBP", "EURTRY", "GBPUSDC", "EURBUSD", "NGNUSDT"]:
            return None
        params = {"symbol": symbol, "interval": "15m", "limit": 100}
        r = requests.get(BINANCE_VISION_URL, params=params, timeout=10)
        r.raise_for_status()
        klines = r.json()
        closes = [float(k[4]) for k in klines]
        volumes = [float(k[5]) for k in klines]
        if len(closes) < 50:
            return None

        # 80% STRICT FILTERS
        ema9 = sum(closes[-9:]) / 9
        ema21 = sum(closes[-21:]) / 21
        ema50 = sum(closes[-50:]) / 50

        # RSI simple
        gains = [max(0, closes[i]-closes[i-1]) for i in range(1,len(closes))]
        losses = [max(0, closes[i-1]-closes[i]) for i in range(1,len(closes))]
        avg_gain = sum(gains[-14:]) / 14
        avg_loss = sum(losses[-14:]) / 14
        if avg_loss == 0: return None
        rsi = 100 - (100 / (1 + avg_gain/avg_loss))

        vol_avg = sum(volumes[-20:]) / 20
        last_vol = volumes[-1]

        # STRICT LONG: EMA9>EMA21>EMA50 + RSI 55-70 + high volume
        if ema9 > ema21 > ema50 and 55 < rsi < 70 and last_vol > vol_avg * 1.2:
            return "LONG"
        # STRICT SHORT: EMA9<EMA21<EMA50 + RSI 30-45 + high volume
        if ema9 < ema21 < ema50 and 30 < rsi < 45 and last_vol > vol_avg * 1.2:
            return "SHORT"
        return None
    except Exception as e:
        print(f"Skip {symbol}: {e}")
        return None
